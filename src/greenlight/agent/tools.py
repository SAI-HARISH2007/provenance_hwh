"""Tool schemas (OpenAI function-calling format) and dispatch onto a World."""

from __future__ import annotations

import json
from typing import Any

from ..sim import ACTIONS, ROOT_CAUSES, World


def _f(name: str, desc: str, props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOLS: list[dict[str, Any]] = [
    _f(
        "get_alert", "The alert that paged you, plus the list of services and their status.", {}, []
    ),
    _f(
        "recent_changes",
        "Deploys, config edits, feature flags, infra and migrations in the last N hours.",
        {"last_hours": {"type": "integer", "default": 24}},
        [],
    ),
    _f(
        "query_logs",
        "Search one service's logs from the last 30 minutes (most recent last).",
        {
            "service": {"type": "string"},
            "pattern": {"type": "string", "description": "case-insensitive substring"},
            "level": {"type": "string", "description": "ERROR|WARN|INFO|DEBUG|LOG|PANIC|FATAL"},
            "limit": {"type": "integer", "default": 20},
        },
        ["service"],
    ),
    _f(
        "get_metrics",
        "A 30-minute, 1/min series for one metric of one service (summary + values).",
        {
            "service": {"type": "string"},
            "metric": {
                "type": "string",
                "description": "e.g. error_rate_pct, latency_p95_ms, cpu_pct, mem_pct, connections_used, locks_waiting, disk_pct, used_memory_pct, evicted_keys_per_min, hit_rate_pct, restarts",
            },
        },
        ["service", "metric"],
    ),
    _f(
        "get_config",
        "Current config and version of a service.",
        {"service": {"type": "string"}},
        ["service"],
    ),
    _f(
        "run_probe",
        "Actively check something right now. kinds: http (a service or external host), tcp, dns (a hostname), db (target=postgres: connections/locks/ownership), disk, cert, clock.",
        {
            "kind": {
                "type": "string",
                "enum": ["http", "tcp", "dns", "db", "disk", "cert", "clock"],
            },
            "target": {"type": "string"},
        },
        ["kind", "target"],
    ),
    _f(
        "submit_verdict",
        "Submit the final root cause, proposed remediation and incident report. Call exactly once.",
        {
            "root_cause": {"type": "string", "enum": ROOT_CAUSES},
            "service": {"type": "string", "description": "service where the cause lives"},
            "action": {"type": "string", "enum": ACTIONS},
            "target": {"type": "string", "description": "service the action applies to"},
            "confidence": {"type": "number"},
            "summary": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "tool results that support the verdict",
            },
            "report_markdown": {
                "type": "string",
                "description": "Incident report: Summary, Timeline, Root cause, Evidence, Proposed remediation (with why it is safe), Follow-ups",
            },
        },
        [
            "root_cause",
            "service",
            "action",
            "target",
            "confidence",
            "summary",
            "evidence",
            "report_markdown",
        ],
    ),
]


def _spark(vals: list[float]) -> str:
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return "▁" * len(vals)
    bars = "▁▂▃▄▅▆▇█"
    return "".join(bars[min(7, int((v - lo) / (hi - lo) * 7.999))] for v in vals)


RECALL_TOOL: dict[str, Any] = _f(
    "recall_similar_incidents",
    "Search long-term memory (Hindsight) for past incidents similar to a description. Returns what "
    "was verified then and which fixes worked or failed. Memory is about the past: re-verify with a "
    "probe before acting on it.",
    {"query": {"type": "string", "description": "symptoms, services, error text, suspected cause"}},
    ["query"],
)


def dispatch(world: World, name: str, args: dict[str, Any]) -> str:
    """Execute a read-only tool and return a compact string for the model."""
    if name == "get_alert":
        return json.dumps({"alert": world.alert(), "services": world.services()})
    if name == "recent_changes":
        ch = world.recent_changes(int(args.get("last_hours", 24)))
        return (
            "\n".join(
                f"{c['at']} [{c['kind']}] {c['service']}: {c['summary']} (by {c['author']})"
                + (f"\n    detail: {c['detail']}" if c["detail"] else "")
                for c in ch
            )
            or "no changes"
        )
    if name == "query_logs":
        lines = world.query_logs(
            args["service"],
            args.get("pattern", "") or "",
            args.get("level", "") or "",
            int(args.get("limit", 20) or 20),
        )
        return "\n".join(lines) if lines else "(no matching log lines)"
    if name == "get_metrics":
        m = world.get_metrics(args["service"], args["metric"])
        vals = [p["v"] for p in m["points"]]
        return (
            f"{m['service']}.{m['metric']} last 30 min (1/min, oldest→newest)\n"
            f"min={m['min']} max={m['max']} last={m['last']}  {_spark(vals)}\n"
            f"values: {' '.join(f'{v:g}' for v in vals)}"
        )
    if name == "get_config":
        return json.dumps(world.get_config(args["service"]))
    if name == "run_probe":
        return world.run_probe(args["kind"], args["target"])
    raise KeyError(name)
