"""Hindsight memory layer with provenance.

The investigator remembers past incidents through Hindsight (retain / recall / reflect). The
design rule that gives this project its name: a recalled memory is a *claim about the past*,
never a fact about the incident in front of you. Recall is used to decide which probe to run
first; the probe decides. The provenance gate in `agent/investigator.py` rejects any verdict that
matches a recalled incident unless the mechanism was re-verified by a probe in *this* incident.

What gets retained, and how it is labelled:
  * the alert, the verdict, the probes that were run and what they returned
  * whether the verdict was verified by a probe, whether the fix resolved the incident, whether
    it caused harm — as tags (`verified:yes`, `resolved:no`, `harm:yes`) so recall can show them
  * failed or harmful remediations are retained too, as negative evidence

Synthetic incident dates are weeks apart so "recall from weeks ago" is literally what happens.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .common import Verdict
from .sim import Scenario

BANK_MISSION = (
    "You are the long-term memory of an on-call incident investigator for a small e-commerce "
    "platform (api-gateway, orders-api, payments-api, inventory-api, auth-api, postgres, redis, "
    "worker). For each incident remember: the alert, the verified root cause and the service it "
    "lived in, the probe that proved it, the remediation that worked, and any remediation that "
    "was tried and did not work or caused harm. Keep verified facts separate from unverified "
    "hypotheses."
)

# First incident date; each retained incident is ~9 days after the previous one.
EPOCH = datetime(2026, 7, 6, 2, 10, tzinfo=UTC)


def _with_retries(fn, attempts: int = 4, first_wait: float = 2.0):
    """Retry transient memory-server failures (provider quota, 5xx) with backoff."""
    wait = first_wait
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            transient = any(k in msg for k in ("429", "500", "502", "503", "quota", "Quota", "rate", "deferred"))
            if not transient or i == attempts - 1:
                raise
            time.sleep(wait)
            wait *= 2


def incident_time(ordinal: int) -> datetime:
    return EPOCH + timedelta(days=9 * ordinal, hours=(ordinal * 7) % 24)


@dataclass
class MemoryHit:
    text: str
    type: str
    when: str
    score: float
    tags: list[str] = field(default_factory=list)

    def _tag(self, key: str) -> str | None:
        for t in self.tags:
            if t.startswith(key + ":"):
                return t.split(":", 1)[1]
        return None

    @property
    def incident_id(self) -> str | None:
        return self._tag("incident")

    @property
    def root_cause(self) -> str | None:
        return self._tag("root_cause")

    @property
    def action(self) -> str | None:
        return self._tag("action")

    @property
    def verified(self) -> bool:
        return self._tag("verified") == "yes"

    def line(self) -> str:
        flag = "verified" if self.verified else "UNVERIFIED"
        src = self.incident_id or "unknown incident"
        return f"- [{src} · {self.when[:10] or 'undated'} · {flag}] {self.text}"

    def age_days(self, now: datetime) -> float | None:
        """How many days before `now` this hit happened, or None if `when` has no parsable date.

        `when` is whatever the memory server returned: ISO 8601, sometimes with an offset,
        sometimes empty or a bare date. A timestamp without an offset is read as UTC.
        """
        raw = self.when.strip()
        if not raw:
            return None
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        return (now - when).total_seconds() / 86400.0


def filter_by_age(
    hits: list[MemoryHit], max_age_days: int, now: datetime | None = None
) -> list[MemoryHit]:
    """Drop hits older than `max_age_days`; a non-positive limit keeps everything.

    Hits whose date cannot be parsed are kept: an undated memory is a weak claim, not a
    reason to hide it.
    """
    if max_age_days <= 0:
        return list(hits)
    ref = now if now is not None else datetime.now(UTC)
    return [h for h in hits if (age := h.age_days(ref)) is None or age <= max_age_days]


class HindsightMemory:
    """Thin wrapper around the Hindsight client that knows what an incident record looks like."""

    def __init__(self, bank_id: str, base_url: str | None = None, api_key: str | None = None):
        from hindsight_client import Hindsight  # imported lazily: optional dependency

        self.client = Hindsight(
            base_url=base_url or os.environ.get("HINDSIGHT_BASE_URL", "http://localhost:8888"),
            api_key=api_key or os.environ.get("HINDSIGHT_API_KEY") or None,
            timeout=60.0,
        )
        self.bank_id = bank_id
        self.min_score = float(os.environ.get("HINDSIGHT_MIN_SCORE", "0.3"))
        self.max_incidents = int(os.environ.get("HINDSIGHT_MAX_INCIDENTS", "3"))
        self.max_age_days = int(os.environ.get("HINDSIGHT_MAX_AGE_DAYS", "0"))  # 0 = no age limit
        self.ordinal = 0  # how many incidents this bank has lived through (drives the dates)
        self.retained: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ bank
    def ensure_bank(self) -> None:
        try:
            self.client.create_bank(
                bank_id=self.bank_id,
                name="Provenance on-call memory",
                mission=BANK_MISSION,
                disposition={"skepticism": 5, "literalism": 4, "empathy": 1},
                # one extraction call per retain; consolidation would add more free-tier calls
                enable_observations=False,
            )
        except Exception as e:  # noqa: BLE001 — "already exists" is fine
            if "exist" not in str(e).lower() and "409" not in str(e):
                raise

    def reset(self) -> None:
        """Start from an empty bank (used so eval sequences are reproducible)."""
        delete = getattr(self.client, "delete_bank", None)
        if delete is not None:
            try:
                delete(bank_id=self.bank_id)
            except Exception:  # noqa: BLE001 — bank may not exist yet
                pass
        self.ordinal = 0
        self.retained = []
        self.ensure_bank()

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            try:
                close()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ recall
    def recall(
        self, query: str, max_tokens: int = 1500, budget: str = "mid", min_score: float | None = None
    ) -> list[MemoryHit]:
        min_score = self.min_score if min_score is None else min_score
        res = _with_retries(
            lambda: self.client.recall(
                bank_id=self.bank_id,
                query=query,
                types=["world", "experience", "observation"],
                max_tokens=max_tokens,
                budget=budget,
            )
        )
        hits: list[MemoryHit] = []
        for r in getattr(res, "results", []) or []:
            scores = getattr(r, "scores", None)
            score = 0.0
            if scores is not None:
                score = float(getattr(scores, "final", 0.0) or 0.0)
            hits.append(
                MemoryHit(
                    text=(getattr(r, "text", "") or "").strip(),
                    type=str(getattr(r, "type", "") or ""),
                    when=str(getattr(r, "occurred_start", "") or ""),
                    score=score,
                    tags=list(getattr(r, "tags", None) or []),
                )
            )
        hits.sort(key=lambda h: -h.score)
        return filter_by_age([h for h in hits if h.score >= min_score], self.max_age_days)

    def brief(
        self,
        alert: dict[str, Any],
        changes: list[dict[str, Any]],
        error_lines: list[str] | None = None,
    ) -> list[MemoryHit]:
        """Recall at kickoff: two phrasings of the same question, merged on the best score.

        The reranker is strict about wording, so one query describes the alert and the recent
        changes (what an engineer would say) and the other quotes the alerting service's own error
        lines (what the logs say). A past incident that matches either is worth showing.
        """
        ch = "; ".join(f"{c['kind']} {c['service']}: {c['summary']}" for c in changes[:6])
        q1 = (
            f"Alert on {alert.get('service')} ({alert.get('severity')}): {alert.get('message')}. "
            f"Recent changes: {ch or 'none'}. Have we seen an incident like this before? What was "
            "the verified root cause, which probe proved it, and which fix worked or failed?"
        )
        queries = [q1]
        if error_lines:
            errs = " | ".join(line[:120] for line in error_lines[:5])
            queries.append(
                f"{alert.get('service')} alert: {alert.get('message')}. Errors: {errs}. Changes: "
                + "; ".join(f"{c['kind']} {c['service']}" for c in changes[:4])
            )
        best: dict[str, MemoryHit] = {}
        for q in queries:
            for h in self.recall(q):
                key = h.text
                if key not in best or h.score > best[key].score:
                    best[key] = h
        return sorted(best.values(), key=lambda h: -h.score)

    @staticmethod
    def group_by_incident(hits: list[MemoryHit]) -> list[tuple[str, list[MemoryHit]]]:
        """Group facts by source incident, strongest incident first, strongest fact first."""
        groups: dict[str, list[MemoryHit]] = {}
        for h in hits:
            groups.setdefault(h.incident_id or "unknown", []).append(h)
        ordered = sorted(groups.items(), key=lambda kv: -max(h.score for h in kv[1]))
        return [(k, sorted(v, key=lambda h: -h.score)) for k, v in ordered]

    @staticmethod
    def format_hits(hits: list[MemoryHit], limit: int = 3, facts_per_incident: int = 3) -> str:
        if not hits:
            return (
                "# Recalled incidents (Hindsight memory)\n(no similar incident in memory — this is "
                "the first time you see this)"
            )
        blocks = []
        for inc, facts in HindsightMemory.group_by_incident(hits)[:limit]:
            top = facts[0]
            strength = "strong match" if top.score >= 0.6 else ("match" if top.score >= 0.3 else "WEAK match")
            head = (
                f"- {inc} · {top.when[:10] or 'undated'} · "
                f"{'verified by probe' if top.verified else 'UNVERIFIED'} · "
                f"cause {top.root_cause or '?'} · fix {top.action or '?'} "
                f"({strength} {top.score:.2f})"
            )
            body = "\n".join(f"    · {f.text[:180]}" for f in facts[:facts_per_incident])
            blocks.append(head + "\n" + body)
        body = "\n".join(blocks)
        return (
            "# Recalled incidents (Hindsight memory — claims about the PAST, unverified for THIS "
            "incident)\n"
            f"{body}\n"
            "Use these to choose which probe to run first. Do not reuse a remembered fix until a "
            "probe in this incident shows the same mechanism."
        )

    # ------------------------------------------------------------------ retain
    def remember(
        self,
        scenario: Scenario,
        verdict: Verdict,
        probes: list[str],
        meta: dict[str, Any],
        when: datetime | None = None,
    ) -> dict[str, Any]:
        when = when or incident_time(self.ordinal)
        verified = bool(meta.get("verified"))
        resolved = bool(meta.get("resolved"))
        harm = bool(meta.get("harm_done"))
        executed = meta.get("actions_executed") or []
        effect = (meta.get("remediation_effect") or {}).get("effect", "")
        decision = (meta.get("approval") or {}).get("decision", "skipped")
        date = when.strftime("%Y-%m-%d %H:%M UTC")

        if not executed:
            outcome = f"Proposed remediation: {verdict.action} on {verdict.target}; approval: {decision}; not executed."
        elif harm:
            outcome = (
                f"Remediation {verdict.action} on {verdict.target} was executed and CAUSED HARM: "
                f"{effect}. Do not repeat it for this symptom without proof."
            )
        elif resolved:
            outcome = f"Remediation {verdict.action} on {verdict.target} was executed and RESOLVED the incident: {effect}."
        else:
            outcome = f"Remediation {verdict.action} on {verdict.target} was executed and did NOT resolve the incident: {effect}."

        probe_txt = "; ".join(p[:160] for p in probes[:4]) or "no probes were run"
        content = (
            f"Incident {scenario.id} on {date}. Alert: \"{scenario.alert.get('message')}\" "
            f"({scenario.alert.get('severity')}) on {scenario.alert.get('service')}.\n"
            f"{'Verified' if verified else 'UNVERIFIED'} root cause: {verdict.root_cause} in service "
            f"{verdict.service} (verified by probe: {'yes' if verified else 'no'}).\n"
            f"Probes run and their results: {probe_txt}.\n"
            f"{outcome}\n"
            f"Investigator summary: {verdict.summary[:600]}"
        )
        tags = [
            f"incident:{scenario.id}",
            f"root_cause:{verdict.root_cause}",
            f"service:{verdict.service}",
            f"action:{verdict.action}",
            f"verified:{'yes' if verified else 'no'}",
            f"resolved:{'yes' if resolved else 'no'}",
            f"harm:{'yes' if harm else 'no'}",
        ]
        _with_retries(
            lambda: self.client.retain(
                bank_id=self.bank_id,
                content=content,
                context="on-call incident record written after the incident was closed",
                timestamp=when,
                tags=tags,
                metadata={t.split(":", 1)[0]: t.split(":", 1)[1] for t in tags},
            )
        )
        rec = {"incident": scenario.id, "when": date, "tags": tags, "chars": len(content)}
        self.retained.append(rec)
        self.ordinal += 1
        return rec


def hits_to_json(hits: list[MemoryHit], limit: int = 12) -> str:
    """Trace-safe JSON: cap the number of hits and the text length instead of slicing the string."""
    rows = []
    for h in hits[:limit]:
        d = asdict(h)
        d["text"] = d["text"][:300]
        rows.append(d)
    return json.dumps(rows)
