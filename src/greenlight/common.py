"""Shared output contract + result persistence for baseline and agent runs."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .sim import ACTIONS, ROOT_CAUSES

RESULTS_DIR = Path("eval/results")


@dataclass
class Verdict:
    root_cause: str = "unknown"
    service: str = "unknown"
    action: str = "no_action"
    target: str = ""
    confidence: float = 0.0
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    report_markdown: str = ""

    def normalized(self) -> Verdict:
        self.root_cause = _closest(self.root_cause, ROOT_CAUSES)
        self.action = _closest(self.action, ACTIONS)
        return self


def _closest(value: str, options: list[str]) -> str:
    v = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if v in options:
        return v
    for o in options:  # tolerate "root_cause: db_connection_pool_exhausted"
        if o in v:
            return o
    return value or "unknown"


def parse_json_block(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model text (handles ```json fences)."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    cand = m.group(1) if m else None
    if cand is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("no JSON object in model output")
        cand = text[start : end + 1]
    return json.loads(cand)


def verdict_from_dict(d: dict[str, Any]) -> Verdict:
    return Verdict(
        root_cause=str(d.get("root_cause", "unknown")),
        service=str(d.get("service", "unknown")),
        action=str(d.get("action", "no_action")),
        target=str(d.get("target", "")),
        confidence=float(d.get("confidence", 0) or 0),
        summary=str(d.get("summary", "")),
        evidence=[str(e) for e in (d.get("evidence") or [])],
        report_markdown=str(d.get("report_markdown", "")),
    ).normalized()


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def write_case_result(run_dir: Path, case_id: str, verdict: Verdict, meta: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = {"case_id": case_id, "verdict": asdict(verdict), **meta}
    # explicit utf-8: these files are read back by the scorer and can carry non-ASCII evidence,
    # and the platform default encoding is not utf-8 everywhere (Windows cp1252)
    (run_dir / f"{case_id}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (run_dir / f"{case_id}.report.md").write_text(
        verdict.report_markdown or "(no report)", encoding="utf-8"
    )
