"""JSONL agent-trajectory writer.

One file per run: traces/<run_id>.jsonl, one event per line. Schema is documented in
docs/TRACE_SCHEMA.md. Outputs larger than ARTIFACT_THRESHOLD bytes are spilled to
traces/<run_id>/artifacts/<seq>.txt and referenced by `output_ref`.
Secrets are redacted at write time.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

ARTIFACT_THRESHOLD = 4096
HEAD_CHARS = 500

_SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[=:]\s*)[\"']?([^\s\"',;]{6,})"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"AQ\.[0-9A-Za-z_\-]{30,}"),
    re.compile(r"gsk_[0-9A-Za-z]{20,}"),
    re.compile(r"csk-[0-9a-z]{20,}"),
]


def redact(text: str) -> str:
    out = text
    out = _SECRET_PATTERNS[0].sub("sk-ant-[REDACTED]", out)
    out = _SECRET_PATTERNS[1].sub("sk-[REDACTED]", out)
    out = _SECRET_PATTERNS[2].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", out)
    out = _SECRET_PATTERNS[3].sub("gh*_[REDACTED]", out)
    out = _SECRET_PATTERNS[4].sub("AIza[REDACTED]", out)
    out = _SECRET_PATTERNS[5].sub("AQ.[REDACTED]", out)
    out = _SECRET_PATTERNS[6].sub("gsk_[REDACTED]", out)
    out = _SECRET_PATTERNS[7].sub("csk-[REDACTED]", out)
    return out


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_run_id(slug: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", slug.lower()).strip("-")[:40]
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{slug}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _redact_obj(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: _redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(v) for v in obj]
    return obj


class TraceWriter:
    """Append-only JSONL trajectory writer."""

    def __init__(self, run_id: str, root: Path | str = "traces"):
        self.run_id = run_id
        self.root = Path(root)
        self.path = self.root / f"{run_id}.jsonl"
        self.artifact_dir = self.root / run_id / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        self._seq = 0
        self._t0 = time.monotonic()
        self._fh = self.path.open("a", encoding="utf-8")

    # ---- core -------------------------------------------------------------------
    def event(self, type: str, **fields: Any) -> int:
        self._seq += 1
        rec: dict[str, Any] = {"run_id": self.run_id, "seq": self._seq, "ts": _now(), "type": type}
        rec.update(_redact_obj(fields))
        self._fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()
        return self._seq

    def _spill(self, text: str, seq_hint: int) -> tuple[str, str | None]:
        """Return (head, output_ref). Spills to artifacts if text is large."""
        text = redact(text)
        if len(text.encode()) <= ARTIFACT_THRESHOLD:
            return text, None
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        p = self.artifact_dir / f"{seq_hint}.txt"
        p.write_text(text, encoding="utf-8")
        return text[:HEAD_CHARS], str(p.relative_to(self.root))

    # ---- typed helpers ----------------------------------------------------------
    def run_start(
        self,
        *,
        problem_id: str,
        agent_version: str,
        model: str,
        params: dict,
        tools: list[str],
        sandbox: str,
        prompt_hashes: dict[str, str] | None = None,
        **extra: Any,
    ) -> int:
        return self.event(
            "run_start",
            problem_id=problem_id,
            agent_version=agent_version,
            model=model,
            params=params,
            tools=tools,
            sandbox=sandbox,
            prompt_hashes=prompt_hashes or {},
            **extra,
        )

    def instruction(self, *, role: str, name: str, content: str) -> int:
        return self.event(
            "instruction",
            role=role,
            name=name,
            content=redact(content),
            sha256=sha256_text(content),
        )

    def llm_request(
        self,
        *,
        n_messages: int,
        tools_offered: list[str],
        input_tokens: int | None = None,
        **extra: Any,
    ) -> int:
        return self.event(
            "llm_request",
            n_messages=n_messages,
            tools_offered=tools_offered,
            input_tokens=input_tokens,
            **extra,
        )

    def llm_response(
        self,
        *,
        stop_reason: str,
        text: str,
        tool_calls: list[dict],
        output_tokens: int | None,
        latency_ms: int,
        **extra: Any,
    ) -> int:
        head, ref = self._spill(text, self._seq + 1)
        return self.event(
            "llm_response",
            stop_reason=stop_reason,
            text=head,
            output_ref=ref,
            tool_calls=tool_calls,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            **extra,
        )

    def tool_call(self, *, tool_call_id: str, name: str, input: dict, attempt: int = 1) -> int:
        return self.event(
            "tool_call", tool_call_id=tool_call_id, name=name, input=input, attempt=attempt
        )

    def tool_result(
        self,
        *,
        tool_call_id: str,
        ok: bool,
        output: str,
        duration_ms: int,
        exit_code: int | None = None,
        stderr: str | None = None,
        **extra: Any,
    ) -> int:
        head, ref = self._spill(output, self._seq + 1)
        return self.event(
            "tool_result",
            tool_call_id=tool_call_id,
            ok=ok,
            output=head,
            output_ref=ref,
            duration_ms=duration_ms,
            exit_code=exit_code,
            stderr=(redact(stderr)[:2000] if stderr else None),
            **extra,
        )

    def error(self, *, where: str, kind: str, message: str, recoverable: bool) -> int:
        return self.event(
            "error", where=where, kind=kind, message=redact(message)[:4000], recoverable=recoverable
        )

    def retry(self, *, of: int, attempt: int, strategy: str, reason: str) -> int:
        return self.event("retry", of=of, attempt=attempt, strategy=strategy, reason=reason)

    def feedback(self, *, source: str, signal: str, detail: str, **extra: Any) -> int:
        head, ref = self._spill(detail, self._seq + 1)
        return self.event(
            "feedback", source=source, signal=signal, detail=head, output_ref=ref, **extra
        )

    def decision(
        self, *, summary: str, options_considered: list[str], chosen: str, rationale: str
    ) -> int:
        return self.event(
            "decision",
            summary=summary,
            options_considered=options_considered,
            chosen=chosen,
            rationale=rationale,
        )

    def human_checkpoint(
        self, *, question: str, decision: str, by: str = "human", detail: str = ""
    ) -> int:
        return self.event(
            "human_checkpoint", question=question, decision=decision, by=by, detail=detail
        )

    def run_end(
        self,
        *,
        status: str,
        final_output: str,
        score: float | None = None,
        total_tokens: int | None = None,
        cost_usd: float | None = None,
        **extra: Any,
    ) -> int:
        head, ref = self._spill(final_output, self._seq + 1)
        wall_ms = int((time.monotonic() - self._t0) * 1000)
        return self.event(
            "run_end",
            status=status,
            final_output=head,
            output_ref=ref,
            score=score,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            wall_ms=wall_ms,
            **extra,
        )

    def close(self) -> None:
        self._fh.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def load_trace(path: Path | str) -> Iterator[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)
