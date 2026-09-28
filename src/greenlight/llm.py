"""Single LLM gateway: OpenAI-compatible client over free-tier providers, with
deterministic disk cache, 429 backoff, provider fallback and per-call accounting.

Providers (all free tier, user-owned keys in .env):
  gemini : https://generativelanguage.googleapis.com/v1beta/openai/  (primary)
  groq   : https://api.groq.com/openai/v1                            (fallback)

Every call returns an LLMResponse; callers (baseline/agent) log it to the trace.
The cache is content-addressed (model + messages + tools + temperature) and lives in
`llm_cache/` — committed to the repo so `make eval-replay` needs zero API calls.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

load_dotenv(os.environ.get("DOTENV_PATH", ".env"))

PROVIDERS: dict[str, dict[str, str]] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-120b",
    },
}

# Published list prices (USD per 1M tokens) used only to report a *would-be* cost;
# actual cost on the free tier is $0. Update if you change models.
PRICE_PER_M = {
    "gemini-3.5-flash-lite": (0.10, 0.40),  # assumed = 2.5-flash-lite list price
    "gemini-3.5-flash": (0.30, 2.50),  # assumed = 2.5-flash list price
    "gemini-3.7-flash": (0.30, 2.50),
    "gemini-2.5-flash": (0.30, 2.50),
    "openai/gpt-oss-120b": (0.15, 0.60),
}

CACHE_DIR = Path(os.environ.get("LLM_CACHE_DIR", "llm_cache"))


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str
    provider: str
    cached: bool
    raw_message: dict[str, Any] = field(default_factory=dict)

    @property
    def would_be_cost_usd(self) -> float:
        pin, pout = PRICE_PER_M.get(self.model, (0.0, 0.0))
        return (self.input_tokens * pin + self.output_tokens * pout) / 1_000_000


class DailyQuotaExhausted(RuntimeError):
    """The provider's per-day free-tier quota for this model is used up; retrying is pointless."""


def _quota_info(err: Exception) -> tuple[bool, float | None]:
    """Return (is_daily_quota, retry_delay_s) parsed from a Gemini/OpenAI-style 429 body."""
    body = getattr(err, "body", None) or {}
    try:
        details = body.get("error", body).get("details", []) if isinstance(body, dict) else []
    except AttributeError:
        details = []
    daily, delay = False, None
    for det in details:
        for v in det.get("violations", []) or []:
            if "PerDay" in str(v.get("quotaId", "")):
                daily = True
        rd = det.get("retryDelay")
        if rd:
            try:
                delay = float(str(rd).rstrip("s"))
            except ValueError:
                pass
    if "PerDay" in str(err):
        daily = True
    return daily, delay


GROQ_MAX_REQUEST_TOKENS = 7000  # free tier TPM is 8000; larger requests are rejected with 413


class LLM:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        fallback: str | None = "groq",
        temperature: float = 0.0,
        use_cache: bool = True,
        replay_only: bool = False,
        max_retries: int = 6,
        on_event=None,
    ):
        self.provider = provider or os.environ.get("LLM_PROVIDER", "gemini")
        self.model = (
            model or os.environ.get("LLM_MODEL") or PROVIDERS[self.provider]["default_model"]
        )
        self.fallback = fallback if fallback != self.provider else None
        self.temperature = temperature
        self.use_cache = use_cache
        self.replay_only = replay_only or os.environ.get("LLM_REPLAY_ONLY") == "1"
        self.max_retries = max_retries
        self.on_event = (
            on_event  # callback(kind:str, **fields) -> None, used for trace 'retry'/'error'
        )
        self.calls = 0
        self.cache_hits = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._clients: dict[str, OpenAI] = {}

    # ------------------------------------------------------------------ helpers
    def _client(self, provider: str) -> OpenAI:
        if provider not in self._clients:
            spec = PROVIDERS[provider]
            key = os.environ.get(spec["key_env"])
            if not key:
                raise RuntimeError(f"{spec['key_env']} not set (see REPRODUCE.md)")
            self._clients[provider] = OpenAI(
                base_url=spec["base_url"], api_key=key, max_retries=0, timeout=120
            )
        return self._clients[provider]

    @staticmethod
    def _cache_key(
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int = 4096,
    ) -> str:
        blob = json.dumps(
            {
                "m": model,
                "msgs": messages,
                "tools": tools,
                "t": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _emit(self, event_type: str, **fields: Any) -> None:
        if self.on_event:
            try:
                self.on_event(event_type, **fields)
            except Exception:  # noqa: BLE001 — tracing must never break a call
                pass

    # ------------------------------------------------------------------ public
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        key = self._cache_key(self.model, messages, tools, self.temperature, max_tokens)
        cpath = CACHE_DIR / f"{key}.json"
        if self.use_cache and cpath.exists():
            d = json.loads(cpath.read_text(encoding="utf-8"))
            self.cache_hits += 1
            self.calls += 1
            self.input_tokens += d["input_tokens"]
            self.output_tokens += d["output_tokens"]
            return self._from_dict(d, cached=True)
        if self.replay_only:
            raise RuntimeError(f"replay-only mode: no cached response for key {key[:12]}…")

        providers = [self.provider] + ([self.fallback] if self.fallback else [])
        last_err: Exception | None = None
        for pi, prov in enumerate(providers):
            model = self.model if pi == 0 else PROVIDERS[prov]["default_model"]
            for attempt in range(1, self.max_retries + 1):
                t0 = time.monotonic()
                try:
                    kwargs: dict[str, Any] = dict(
                        model=model,
                        messages=messages,
                        temperature=self.temperature,
                        max_tokens=max_tokens,
                    )
                    if tools:
                        kwargs["tools"] = tools
                        if tool_choice:
                            kwargs["tool_choice"] = tool_choice
                    if response_format:
                        kwargs["response_format"] = response_format
                    resp = self._client(prov).chat.completions.create(**kwargs)
                    latency = int((time.monotonic() - t0) * 1000)
                    d = self._to_dict(resp, model, prov, latency)
                    if self.use_cache:
                        CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        cpath.write_text(
                            json.dumps(d, ensure_ascii=False, indent=0), encoding="utf-8"
                        )
                    self.calls += 1
                    self.input_tokens += d["input_tokens"]
                    self.output_tokens += d["output_tokens"]
                    return self._from_dict(d, cached=False)
                except (RateLimitError, APIConnectionError, APIStatusError) as e:
                    last_err = e
                    status = getattr(e, "status_code", None)
                    daily, retry_delay = _quota_info(e)
                    retryable = isinstance(e, (RateLimitError, APIConnectionError)) or (
                        status is not None and status >= 500
                    )
                    self._emit(
                        "error",
                        where="llm",
                        kind=type(e).__name__,
                        message=f"{prov}/{model} attempt {attempt}: {str(e)[:300]}",
                        recoverable=retryable and not daily,
                    )
                    if daily:
                        break  # per-day quota: retrying cannot help
                    if not retryable:
                        break
                    if attempt < self.max_retries:
                        delay = (
                            retry_delay
                            if retry_delay
                            else min(60.0, (2**attempt) + random.uniform(0, 1.5))
                        )
                        delay = min(delay + random.uniform(0, 1.0), 90.0)
                        self._emit(
                            "retry",
                            of=-1,
                            attempt=attempt + 1,
                            strategy="backoff",
                            reason=f"{type(e).__name__} from {prov}; sleeping {delay:.1f}s",
                        )
                        time.sleep(delay)
            if pi + 1 < len(providers):
                nxt = providers[pi + 1]
                est_tokens = len(json.dumps(messages)) // 4 + (
                    len(json.dumps(tools)) // 4 if tools else 0
                )
                if nxt == "groq" and est_tokens > GROQ_MAX_REQUEST_TOKENS:
                    self._emit(
                        "decision",
                        summary="skip groq fallback",
                        options_considered=["groq", "fail"],
                        chosen="fail",
                        rationale=f"request ~{est_tokens} tokens exceeds groq free-tier 8k TPM",
                    )
                    break
                self._emit(
                    "retry",
                    of=-1,
                    attempt=1,
                    strategy="fallback-provider",
                    reason=f"{prov} exhausted; switching to {nxt}",
                )
        if last_err is not None and _quota_info(last_err)[0]:
            raise DailyQuotaExhausted(
                f"{self.provider}/{self.model}: daily free-tier quota exhausted — "
                f"switch model (LLM_MODEL=...) or wait for reset (midnight Pacific)"
            )
        raise RuntimeError(f"LLM call failed after retries: {last_err}")

    # ------------------------------------------------------------------ (de)serialise
    @staticmethod
    def _to_dict(resp: Any, model: str, provider: str, latency_ms: int) -> dict[str, Any]:
        msg = resp.choices[0].message
        tcs = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            tcs.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        usage = resp.usage
        # Keep the provider's full assistant message (Gemini 3.x needs each tool call's
        # extra_content.google.thought_signature echoed back on the next turn).
        raw = msg.model_dump(exclude_none=True)
        raw.setdefault("role", "assistant")
        if raw.get("content") is None:
            raw["content"] = ""
        return {
            "text": msg.content or "",
            "tool_calls": tcs,
            "stop_reason": resp.choices[0].finish_reason or "stop",
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "latency_ms": latency_ms,
            "model": model,
            "provider": provider,
            "raw_message": raw,
        }

    @staticmethod
    def _from_dict(d: dict[str, Any], cached: bool) -> LLMResponse:
        return LLMResponse(
            text=d["text"],
            tool_calls=[ToolCall(**tc) for tc in d["tool_calls"]],
            stop_reason=d["stop_reason"],
            input_tokens=d["input_tokens"],
            output_tokens=d["output_tokens"],
            latency_ms=d["latency_ms"],
            model=d["model"],
            provider=d["provider"],
            cached=cached,
            raw_message=d.get("raw_message", {}),
        )

    def stats(self) -> dict[str, Any]:
        pin, pout = PRICE_PER_M.get(self.model, (0.0, 0.0))
        return {
            "calls": self.calls,
            "cache_hits": self.cache_hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "would_be_cost_usd": round(
                (self.input_tokens * pin + self.output_tokens * pout) / 1e6, 5
            ),
            "actual_cost_usd": 0.0,
        }
