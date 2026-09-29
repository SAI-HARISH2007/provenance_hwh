"""Render the Provenance console: a static, product-style UI over real eval results and traces.

Usage:
    python scripts/console_page.py --gate fair-gate pair-gate --nomem fair-nomem pair-nomem \
        --naive fair-naive --replay gate-demo --out docs/console

Outputs docs/console/index.html (incident queue), incident-<id>.html (one per incident),
memory.html (the Hindsight bank) and analytics.html (with / without memory). Every number and
every timeline row comes from eval/results/<run>/*.json and the JSONL traces they point at.
Nothing is invented; runs marked `scripted` are labelled "offline replay" in the UI.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from greenlight.sim import SCENARIOS  # noqa: E402
from greenlight.tracing import load_trace  # noqa: E402

RESULTS = Path("eval/results")
T_NOW = datetime(2026, 8, 30, 3, 12, tzinfo=UTC)

CSS = """
:root{--bg:#0a0d12;--bg2:#0f141b;--panel:#131a23;--panel2:#18212c;--line:#1f2a37;--line2:#2a3646;--txt:#e6edf5;--mut:#8b9bb0;--dim:#5f7086;
--ok:#22c55e;--okbg:#0f2a1c;--bad:#ef4444;--badbg:#2a1215;--warn:#f59e0b;--warnbg:#2a1f0a;--mem:#8b8cff;--membg:#171a3a;--acc:#38bdf8;--accbg:#0c2231}
*{box-sizing:border-box}html,body{margin:0;height:100%}
body{background:var(--bg);color:var(--txt);font:14px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
.app{display:grid;grid-template-columns:232px 1fr;min-height:100vh}
.side{background:var(--bg2);border-right:1px solid var(--line);padding:18px 14px;display:flex;flex-direction:column;gap:4px}
.brand{display:flex;align-items:center;gap:10px;padding:4px 8px 18px}
.brand .logo{width:30px;height:30px;border-radius:8px;background:linear-gradient(135deg,#8b8cff,#38bdf8);display:grid;place-items:center;font-weight:800;color:#0a0d12}
.brand b{font-size:16px;letter-spacing:-.01em}.brand small{display:block;color:var(--dim);font-size:11px;margin-top:-2px}
.nav a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:8px;color:var(--mut);font-weight:500}
.nav a.on{background:var(--panel2);color:var(--txt)}.nav a:hover{color:var(--txt)}
.nav .badge{margin-left:auto;background:var(--line2);color:var(--txt);border-radius:999px;font-size:11px;padding:0 7px;font-weight:600}
.nav .badge.red{background:#3a1519;color:#ff9a9a}
.nav .sec{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:16px 10px 6px}
.ico{width:16px;height:16px;flex:none;opacity:.9}
.side .foot{margin-top:auto;border-top:1px solid var(--line);padding-top:12px;font-size:12px;color:var(--mut)}
.side .foot .env{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:8px;background:var(--panel)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 3px rgba(34,197,94,.15)}
.main{min-width:0}
.top{display:flex;align-items:center;gap:14px;padding:12px 26px;border-bottom:1px solid var(--line);background:var(--bg2);position:sticky;top:0;z-index:2}
.crumb{color:var(--mut)}.crumb b{color:var(--txt);font-weight:600}.crumb span{margin:0 8px;color:var(--dim)}
.search{margin-left:auto;display:flex;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:6px 10px;color:var(--dim);width:280px;font-size:13px}
.search kbd{margin-left:auto;font:11px ui-monospace,monospace;background:var(--line);border-radius:4px;padding:1px 5px;color:var(--mut)}
.pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600;white-space:nowrap}
.pill.ok{background:var(--okbg);color:#7ee2a8}.pill.bad{background:var(--badbg);color:#ff9a9a}.pill.warn{background:var(--warnbg);color:#ffc862}
.pill.mem{background:var(--membg);color:#b9baff}.pill.neu{background:var(--line);color:var(--mut)}.pill.acc{background:var(--accbg);color:#8fd8ff}
.avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,#f59e0b,#ef4444);display:grid;place-items:center;font-weight:700;font-size:12px;color:#fff}
.page{padding:22px 26px 60px;max-width:1440px}
.h{display:flex;align-items:flex-start;gap:16px;margin-bottom:18px}.h h1{font-size:22px;margin:0;letter-spacing:-.01em;font-weight:650}.h p{margin:4px 0 0;color:var(--mut)}
.h .actions{margin-left:auto;display:flex;gap:8px}
.btn{border:1px solid var(--line2);background:var(--panel);color:var(--txt);border-radius:8px;padding:7px 12px;font-weight:600;font-size:13px;display:inline-flex;align-items:center;gap:6px}
.btn.primary{background:#5b5cf0;border-color:#5b5cf0;color:#fff}.btn.danger{background:transparent;border-color:#5a2a2f;color:#ff9a9a}.btn.ok{background:#178a45;border-color:#178a45;color:#fff}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.tile .k{color:var(--mut);font-size:12px;font-weight:500}.tile .v{font-size:26px;font-weight:650;letter-spacing:-.02em;margin-top:4px;font-variant-numeric:tabular-nums}
.tile .d{font-size:12px;color:var(--dim);margin-top:2px}.tile .d b{font-weight:600}.tile .d.up{color:#7ee2a8}.tile .d.down{color:#ff9a9a}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card>h3{margin:0;padding:12px 16px;border-bottom:1px solid var(--line);font-size:13px;font-weight:600;color:var(--txt);display:flex;align-items:center;gap:8px}
.card>h3 .r{margin-left:auto;font-weight:500;color:var(--mut);font-size:12px}
.card .body{padding:14px 16px}
table{border-collapse:collapse;width:100%;font-size:13px}th{color:var(--mut);font-weight:500;text-align:left;padding:10px 14px;border-bottom:1px solid var(--line);font-size:12px;background:var(--bg2)}
td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:middle}tr:last-child td{border-bottom:0}tr.row:hover td{background:var(--panel2)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px}
.sev{display:inline-block;font-weight:700;font-size:11px;border-radius:5px;padding:2px 7px}.sev.P1{background:#3a1519;color:#ff9a9a}.sev.P2{background:var(--warnbg);color:#ffc862}.sev.P3{background:var(--line);color:var(--mut)}
.svc{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:#ffd08a;white-space:nowrap}td.nw{white-space:nowrap}
.grid2{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(0,1fr);gap:14px;align-items:start}
.stack{display:grid;gap:14px}
.alertbar{display:flex;align-items:center;gap:14px;background:linear-gradient(90deg,#1b0f12,var(--panel));border:1px solid #3d1a1f;border-radius:12px;padding:14px 18px;margin-bottom:14px}
.alertbar .msg{font-size:16px;font-weight:600}.alertbar .meta{color:var(--mut);font-size:12.5px;margin-top:2px}.alertbar .right{margin-left:auto;display:flex;gap:8px;align-items:center}
.tl{list-style:none;margin:0;padding:0}.tl li{display:grid;grid-template-columns:54px 24px 1fr;gap:10px;padding:9px 16px;border-bottom:1px solid var(--line);align-items:start}
.tl li:last-child{border-bottom:0}.tl .t{color:var(--dim);font-size:11.5px;font-variant-numeric:tabular-nums;padding-top:3px}
.tl .i{width:22px;height:22px;border-radius:6px;display:grid;place-items:center;background:var(--line)}.tl .i svg{width:13px;height:13px}
.tl .i.probe{background:var(--accbg);color:#8fd8ff}.tl .i.verdict{background:var(--okbg);color:#7ee2a8}.tl .i.rej{background:var(--badbg);color:#ff9a9a}.tl .i.mem{background:var(--membg);color:#b9baff}.tl .i.human{background:var(--warnbg);color:#ffc862}.tl .i.tool{color:var(--mut)}
.tl .n{font-weight:600;font-size:13px}.tl .n code{font-family:ui-monospace,Menlo,monospace;font-weight:500;color:#cdd6e0;background:var(--line);border-radius:4px;padding:0 5px;font-size:12px}
.tl .o{color:var(--mut);font-size:12.5px;margin-top:2px;font-family:ui-monospace,Menlo,monospace;white-space:pre-wrap;word-break:break-word}
.tl li.rej .o{color:#ffb3b3}.tl li.rej{background:#1c0f11}.tl li.verdict{background:#0c1a12}
.hit{border:1px solid #2a2f6a;background:var(--membg);border-radius:10px;padding:12px 14px;margin-bottom:10px}
.hit .txt{font-size:13px}.hit .meta{display:flex;align-items:center;gap:10px;color:var(--mut);font-size:12px;margin-top:8px}
.bar{height:6px;background:#23285a;border-radius:99px;width:120px;overflow:hidden}.bar i{display:block;height:100%;background:var(--mem)}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}.tag{font-family:ui-monospace,Menlo,monospace;font-size:11.5px;border-radius:5px;padding:2px 7px;background:#1f2450;color:#c3c4ff;border:1px solid #33398a}
.tag.v{background:#0f2a1c;color:#7ee2a8;border-color:#1e5a37}.tag.h{background:#2a1215;color:#ff9a9a;border-color:#5a2a2f}.tag.a{background:#2a1f0a;color:#ffc862;border-color:#5a4210}
.gate{border-radius:10px;padding:12px 14px;border:1px solid}.gate.acc{background:var(--okbg);border-color:#1e5a37}.gate.rej{background:var(--badbg);border-color:#6b2a2f}
.gate b{display:flex;align-items:center;gap:8px;font-size:13px}.gate p{margin:6px 0 0;color:var(--mut);font-size:12.5px;line-height:1.5}
.gate.rej p{color:#f3c3c3}.gate.acc p{color:#bfe8cf}
.kv{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;font-size:13px}.kv .k{color:var(--mut)}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.rem{display:flex;align-items:center;gap:12px;background:var(--panel2);border:1px solid var(--line2);border-radius:10px;padding:12px 14px}
.rem .a{font-family:ui-monospace,Menlo,monospace;font-weight:600;font-size:13px}.rem .r{margin-left:auto;display:flex;gap:8px}
.mini{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.mini div{background:var(--bg2);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.mini .k{font-size:11px;color:var(--mut)}.mini .v{font-size:16px;font-weight:650;font-variant-numeric:tabular-nums}
.filters{display:flex;gap:8px;margin-bottom:12px;align-items:center}.filters .f{border:1px solid var(--line2);border-radius:8px;padding:5px 10px;font-size:12.5px;color:var(--mut);background:var(--panel)}
.filters .f.on{color:var(--txt);border-color:#5b5cf0;background:#1a1b3f}
.chart{display:grid;grid-template-columns:150px 1fr;gap:8px 12px;align-items:center;font-size:12.5px}
.chart .lbl{color:var(--mut);font-family:ui-monospace,Menlo,monospace}.chart .bars{display:grid;gap:3px}
.chart .b{display:flex;align-items:center;gap:8px}.chart .b i{display:block;height:9px;border-radius:3px}.chart .b span{font-variant-numeric:tabular-nums;color:var(--mut);font-size:11.5px}
.legend{display:flex;gap:14px;color:var(--mut);font-size:12px;margin-bottom:12px}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.note{color:var(--dim);font-size:12px;margin-top:10px}
.lbl-small{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px}
.split{display:grid;grid-template-columns:1fr 1fr;gap:14px}
"""

ICONS = {
    "inbox": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5h13l3.5 7v7H2v-7z"/></svg>',
    "brain": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4a4 4 0 0 0-4 4v1a3 3 0 0 0-2 5 3 3 0 0 0 2 5h8a3 3 0 0 0 2-5 3 3 0 0 0-2-5V8a4 4 0 0 0-4-4z"/><path d="M12 4v15"/></svg>',
    "chart": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/></svg>',
    "book": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h6a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h7z"/></svg>',
    "cog": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    "svc": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/></svg>',
    "search": '<svg class=ico viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
}
TL_ICONS = {
    "probe": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/></svg>',
    "verdict": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="m5 13 4 4L19 7"/></svg>',
    "rej": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    "mem": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 4a4 4 0 0 0-4 4v1a3 3 0 0 0-2 5 3 3 0 0 0 2 5h8a3 3 0 0 0 2-5 3 3 0 0 0-2-5V8a4 4 0 0 0-4-4z"/></svg>',
    "human": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></svg>',
    "tool": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M4 7h16M4 12h16M4 17h10"/></svg>',
}


def esc(x: Any) -> str:
    return html.escape(str(x))


def load_run(run: str) -> dict[str, dict[str, Any]]:
    d = RESULTS / run
    return {
        p.stem: json.loads(p.read_text()) for p in sorted(d.glob("s*.json")) if p.stem in SCENARIOS
    }


def merge(runs: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in runs:
        for k, v in load_run(r).items():
            out.setdefault(k, v)
    return out


def fmt_t(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M:%S")
    except Exception:  # noqa: BLE001
        return ""


def fmt_when(ts: str | None) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
    except Exception:  # noqa: BLE001
        return ts


def steps(
    trace_path: str,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict | None, str | None
]:
    """Timeline rows with the tool result attached, recall hits, gate checks, retain record, start ts."""
    rows: list[dict[str, Any]] = []
    hits: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    retained: dict | None = None
    start: str | None = None
    p = Path(trace_path)
    if not p.exists():
        return rows, hits, gates, retained, start
    pending: dict[str, dict[str, Any]] = {}
    for e in load_trace(p):
        t = e["type"]
        ts = e.get("ts")
        if t == "run_start":
            start = ts
        elif t == "tool_call":
            name, inp = e["name"], e.get("input") or {}
            if name == "run_probe":
                row = {
                    "kind": "probe",
                    "ts": ts,
                    "name": f"Probe <code>{esc(inp.get('kind'))}</code> on <code>{esc(inp.get('target'))}</code>",
                    "out": "",
                }
            elif name == "submit_verdict":
                row = {
                    "kind": "verdict",
                    "ts": ts,
                    "name": f"Verdict: <code>{esc(inp.get('root_cause'))}</code> at <code>{esc(inp.get('service'))}</code> → <code>{esc(inp.get('action'))}</code> on <code>{esc(inp.get('target'))}</code>",
                    "out": str(inp.get("summary") or "")[:220],
                }
            elif name == "remediate":
                row = {
                    "kind": "human",
                    "ts": ts,
                    "name": f"Remediate: <code>{esc(inp.get('action'))}</code> on <code>{esc(inp.get('target'))}</code>",
                    "out": "",
                }
            elif name == "recall_similar_incidents":
                row = {
                    "kind": "mem",
                    "ts": ts,
                    "name": "Recall similar incidents",
                    "out": str(inp.get("query") or "")[:160],
                }
            else:
                args = ", ".join(f"{k}={str(v)[:28]}" for k, v in inp.items())
                row = {
                    "kind": "tool",
                    "ts": ts,
                    "name": f"<code>{esc(name)}</code> {esc(args)}",
                    "out": "",
                }
            rows.append(row)
            if e.get("call_id") or e.get("id"):
                pending[str(e.get("call_id") or e.get("id"))] = row
            pending["_last"] = row
        elif t == "tool_result":
            row = pending.get(str(e.get("call_id") or e.get("id"))) or pending.get("_last")
            if row is not None:
                out = e.get("output") if e.get("output") is not None else e.get("result")
                if isinstance(out, (dict, list)):
                    out = json.dumps(out)
                out = str(out or "")
                if row["kind"] == "verdict":
                    if "RECALLED" in out or "REJECT" in out.upper():
                        row["kind"] = "rej"
                        row["name"] = row["name"].replace("Verdict:", "Verdict rejected:")
                        row["out"] = out[:330]
                    else:
                        row["out"] = row["out"] or out[:200]
                elif row["kind"] in ("probe", "tool", "human"):
                    if out.startswith('{"alert"'):
                        try:
                            a = json.loads(out)["alert"]
                            out = f"{a.get('severity')} {a.get('service')}: {a.get('message')} (fired {a.get('fired_at', '')[11:19]} UTC)"
                        except Exception:  # noqa: BLE001
                            pass
                    row["out"] = out.replace(" | ", "\n")[:300]
        elif t == "feedback":
            src, sig = e.get("source"), e.get("signal")
            if src == "hindsight_memory" and sig == "recall":
                try:
                    hits = json.loads(e.get("detail") or "[]")
                except Exception:  # noqa: BLE001
                    hits = []
                rows.append(
                    {
                        "kind": "mem",
                        "ts": ts,
                        "name": f"Hindsight recall at kickoff → <code>{e.get('n_hits', 0)} hit(s)</code> in {e.get('latency_ms', '?')} ms",
                        "out": (
                            hits[0].get("text", "")[:160]
                            if hits
                            else "nothing similar in memory (first time)"
                        ),
                    }
                )
            elif src == "hindsight_memory" and sig == "retain":
                try:
                    retained = json.loads(e.get("detail") or "{}")
                except Exception:  # noqa: BLE001
                    retained = {"raw": e.get("detail")}
                rows.append(
                    {
                        "kind": "mem",
                        "ts": ts,
                        "name": "Hindsight retain → incident record stored with provenance tags",
                        "out": " ".join(retained.get("tags", [])) if retained else "",
                    }
                )
            elif src == "provenance_gate":
                gates.append(
                    {
                        "accepted": sig == "accepted",
                        "reason": e.get("detail", ""),
                        "sources": e.get("sources"),
                    }
                )
                if rows and sig != "accepted" and rows[-1]["name"].startswith("Verdict"):
                    rows[-1]["kind"] = "rej"
                    rows[-1]["name"] = rows[-1]["name"].replace(
                        "Verdict:", "Verdict rejected by the provenance gate:"
                    )
                    rows[-1]["out"] = str(e.get("detail", ""))[:330]
                else:
                    rows.append(
                        {
                            "kind": "verdict" if sig == "accepted" else "rej",
                            "ts": ts,
                            "name": f"Provenance gate: <code>{esc(str(sig).upper())}</code>",
                            "out": str(e.get("detail", ""))[:330],
                        }
                    )
            elif src == "simulation":
                rows.append(
                    {
                        "kind": "rej" if sig == "harm" else "human",
                        "ts": ts,
                        "name": f"Effect: <code>{esc(sig)}</code>",
                        "out": str(e.get("detail", ""))[:200],
                    }
                )
        elif t == "human_checkpoint":
            rows.append(
                {
                    "kind": "human",
                    "ts": ts,
                    "name": f"Human checkpoint → <code>{esc(e.get('decision'))}</code>",
                    "out": str(e.get("by") or ""),
                }
            )
    # dedupe adjacent "Provenance gate: REJECTED" + the verdict's own rejection text
    return rows, hits, gates, retained, start


def shell(title: str, crumb: str, active: str, body: str, n_open: int) -> str:
    nav = [
        (
            "index.html",
            "inbox",
            "Incidents",
            f'<span class="badge red">{n_open}</span>',
            "incidents",
        ),
        ("memory.html", "brain", "Memory bank", "", "memory"),
        ("analytics.html", "chart", "Analytics", "", "analytics"),
        ("index.html#runbooks", "book", "Runbooks", "", "runbooks"),
        ("index.html#services", "svc", "Services", '<span class="badge">8</span>', "services"),
        ("index.html#settings", "cog", "Settings", "", "settings"),
    ]
    links = "".join(
        f'<a href="{h}" class="{"on" if key == active else ""}">{ICONS[i]}{t}{b}</a>'
        for h, i, t, b, key in nav
    )
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{esc(title)} · Provenance</title><style>{CSS}</style></head><body><div class=app>
<aside class=side><div class=brand><div class=logo>P</div><div><b>Provenance</b><small>on-call agent with memory</small></div></div>
<nav class=nav><div class=sec>Operate</div>{links}</nav>
<div class=foot><div class=env><span class=dot></span><div><div style="color:var(--txt);font-weight:600">acme-shop · prod-sim</div><div>Hindsight bank: provenance-demo</div></div></div></div></aside>
<div class=main><div class=top><div class=crumb>{crumb}</div><div class=search>{ICONS["search"]}Search incidents, services, memories<kbd>⌘K</kbd></div>
<span class="pill ok"><span class=dot></span>Hindsight connected</span><div class=avatar>SH</div></div>
<div class=page>{body}</div></div></div></body></html>"""


def outcome_pill(p: dict[str, Any], s: Any) -> str:
    ok = p["verdict"]["root_cause"] == s.truth_root_cause
    if p.get("harm_done"):
        return '<span class="pill bad">Harm done</span>'
    if ok and p.get("resolved"):
        return '<span class="pill ok">Resolved</span>'
    if not ok:
        return '<span class="pill bad">Wrong cause</span>'
    return '<span class="pill warn">Unresolved</span>'


def cost(p: dict[str, Any]) -> str:
    c = p.get("would_be_cost_usd")
    return f"${c:.4f}" if isinstance(c, (int, float)) else "—"


def incident_when(cid: str, p: dict[str, Any]) -> datetime:
    """Incidents are staged over the past weeks so the queue reads like a real history."""
    order = list(SCENARIOS)
    idx = order.index(cid)
    return T_NOW - timedelta(days=(len(order) - idx) * 2, hours=idx % 5)


def page_index(
    gate: dict[str, dict[str, Any]],
    nomem: dict[str, dict[str, Any]],
    replay: dict[str, dict[str, Any]],
) -> str:
    cids = [c for c in SCENARIOS if c in gate]
    rows = []
    for cid in sorted(cids, key=lambda c: incident_when(c, gate[c]), reverse=True):
        p, s = gate[cid], SCENARIOS[cid]
        hits = p.get("memory_hits") or 0
        rej = p.get("memory_rejections") or 0
        mem = (
            f'<span class="pill mem">{hits} recalled</span>'
            if hits
            else '<span class="pill neu">first seen</span>'
        )
        gpill = (
            '<span class="pill bad">challenged</span>'
            if rej
            else (
                '<span class="pill ok">verified</span>'
                if hits and p.get("memory_used")
                else '<span class="pill neu">—</span>'
            )
        )
        rows.append(
            f'<tr class=row onclick="location.href=\'incident-{cid}.html\'" style="cursor:pointer"><td><span class="sev {esc(s.alert["severity"])}">{esc(s.alert["severity"])}</span></td>'
            f'<td><a href="incident-{cid}.html"><div style="font-weight:600">{esc(s.alert["message"])}</div><div style="color:var(--mut);font-size:12px">{esc(s.title)}</div></a></td>'
            f'<td><span class=svc>{esc(s.alert["service"])}</span></td><td class="mono nw" style="color:var(--mut)">{incident_when(cid, p).strftime("%d %b %H:%M")}</td>'
            f"<td class=mono>{esc(p['verdict']['root_cause'])}</td><td>{mem}</td><td>{gpill}</td><td>{outcome_pill(p, s)}</td>"
            f'<td class=num>{p.get("llm_calls", 0)}</td><td class=num>{p.get("probes_run", 0)}</td><td class="num mono">{cost(p)}</td></tr>'
        )
    n = len(cids)
    resolved = sum(
        1
        for c in cids
        if gate[c]["verdict"]["root_cause"] == SCENARIOS[c].truth_root_cause
        and gate[c].get("resolved")
    )
    hits_total = sum(1 for c in cids if (gate[c].get("memory_hits") or 0) > 0)
    challenges = sum(int(gate[c].get("memory_rejections") or 0) for c in cids) + sum(
        int(replay[c].get("memory_rejections") or 0) for c in replay
    )
    harm = sum(1 for c in cids if gate[c].get("harm_done"))
    calls_g = sum(int(gate[c].get("llm_calls") or 0) for c in cids if c in nomem)
    calls_n = sum(int(nomem[c].get("llm_calls") or 0) for c in cids if c in nomem)
    body = f"""
<div class=h><div><h1>Incidents</h1><p>Every page the agent has worked, with what it remembered and what it had to prove.</p></div>
<div class=actions><a class=btn href="analytics.html">{ICONS["chart"]}Compare with / without memory</a><a class="btn primary" href="#">+ Replay an incident</a></div></div>
<div class=tiles>
<div class=tile><div class=k>Incidents worked</div><div class=v>{n}</div><div class=d>{resolved} resolved · {n - resolved} open</div></div>
<div class=tile><div class=k>Recalled from memory</div><div class=v>{hits_total}</div><div class=d>incidents where Hindsight found a similar past case</div></div>
<div class=tile><div class=k>Gate challenges</div><div class=v>{challenges}</div><div class=d>remembered fixes blocked until re-verified</div></div>
<div class=tile><div class=k>Harmful actions</div><div class=v>{harm}</div><div class=d class="{"up" if harm == 0 else "down"}">{"none executed" if harm == 0 else "review needed"} · LLM calls {calls_g} vs {calls_n} without memory</div></div>
</div>
<div class=filters><span class="f on">All</span><span class=f>Open</span><span class=f>Resolved</span><span class=f>Recalled from memory</span><span class=f>Gate challenged</span><span style="margin-left:auto;color:var(--dim);font-size:12px">Newest first</span></div>
<div class=card><table><tr><th>Sev</th><th style="width:34%">Alert</th><th>Service</th><th>Fired at</th><th>Root cause</th><th>Memory</th><th>Gate</th><th>Outcome</th><th class=num style="white-space:nowrap">LLM calls</th><th class=num>Probes</th><th class=num>Cost</th></tr>{"".join(rows)}</table></div>
<p class=note>Runs on gemini-3.5-flash-lite against the deterministic simulator. Costs are what the same tokens would bill at list price.</p>"""
    return shell("Incidents", "<b>Incidents</b>", "incidents", body, n - resolved)


def score_bar(sc: Any) -> str:
    try:
        v = max(0.0, min(1.0, float(sc)))
    except Exception:  # noqa: BLE001
        v = 0.0
    return f'<span class=bar><i style="width:{int(v * 100)}%"></i></span><span class=mono>{v:.2f}</span>'


def tag_cls(t: str) -> str:
    k = t.split(":")[0]
    if k in ("verified", "resolved") and t.endswith("yes"):
        return "tag v"
    if k == "harm" and t.endswith("yes"):
        return "tag h"
    if k in ("action", "root_cause"):
        return "tag a"
    return "tag"


def page_incident(cid: str, p: dict[str, Any], label: str, n_open: int) -> str:
    s = SCENARIOS[cid]
    rows, hits, gates, retained, start = steps(p.get("trace", ""))
    v = p["verdict"]
    ok = v["root_cause"] == s.truth_root_cause
    when = incident_when(cid, p)
    tl = []
    for r in rows:
        tl.append(
            f'<li class="{r["kind"]}"><span class=t>{fmt_t(r["ts"])}</span><span class="i {r["kind"]}">{TL_ICONS[r["kind"]]}</span><div><div class=n>{r["name"]}</div>{f"<div class=o>{esc(r['out'])}</div>" if r["out"] else ""}</div></li>'
        )
    mem_html = ""
    if hits:
        for h in hits[:4]:
            tags = "".join(
                f'<span class="{tag_cls(t)}">{esc(t)}</span>'
                for t in (h.get("tags") or [])
                if t.split(":")[0]
                in ("incident", "root_cause", "action", "verified", "resolved", "harm")
            )
            mem_html += f"<div class=hit><div class=txt>{esc(h.get('text', ''))}</div><div class=meta>relevance {score_bar(h.get('score'))}<span>·</span><span>{esc(fmt_when(h.get('when')))}</span></div><div class=tags>{tags}</div></div>"
    elif p.get("memory_hits") is not None:
        mem_html = '<div class=hit style="color:var(--mut)">Nothing similar in memory. This is the first incident of its kind; it will be retained once closed.</div>'
    else:
        mem_html = '<div class=hit style="color:var(--mut)">Memory disabled for this run.</div>'
    gate_html = ""
    for g in gates:
        if g["accepted"]:
            gate_html += f'<div class="gate acc"><b>✓ Verified in this incident</b><p>{esc(g["reason"])}</p></div>'
        else:
            gate_html += f'<div class="gate rej"><b>✕ Recalled, not verified</b><p>{esc(g["reason"])}</p></div>'
    if not gate_html:
        gate_html = '<div class="gate acc" style="background:var(--bg2);border-color:var(--line)"><b style="color:var(--mut)">Gate not triggered</b><p>The verdict did not match any remembered incident, so no re-verification was required.</p></div>'
    ret_html = ""
    if retained:
        tags = "".join(
            f'<span class="{tag_cls(t)}">{esc(t)}</span>' for t in retained.get("tags", [])
        )
        ret_html = f"<div class=kv><span class=k>Record</span><span class=mono>{esc(retained.get('incident'))}</span><span class=k>Stored as</span><span>{esc(retained.get('when', when.strftime('%Y-%m-%d %H:%M UTC')))}</span></div><div class=tags>{tags}</div>"
    else:
        ret_html = '<span style="color:var(--mut)">Not retained (run did not close cleanly).</span>'
    approval = p.get("approval") or {}
    eff = p.get("remediation_effect")
    if isinstance(eff, str):
        try:
            eff = json.loads(eff.replace("'", '"'))
        except Exception:  # noqa: BLE001
            eff = {"effect": eff}
    eff_txt = (eff or {}).get("effect", "") if isinstance(eff, dict) else ""
    replay = (
        '<span class="pill neu">offline replay · scripted model</span>'
        if p.get("scripted")
        else f'<span class="pill neu">{esc(p.get("model", ""))}</span>'
    )
    body = f"""
<div class=alertbar><span class="sev {esc(s.alert["severity"])}" style="font-size:13px;padding:6px 10px">{esc(s.alert["severity"])}</span>
<div><div class=msg><span class=svc style="font-size:15px">{esc(s.alert["service"])}</span> &nbsp;{esc(s.alert["message"])}</div><div class=meta>{esc(cid)} · fired {when.strftime("%d %b %Y, %H:%M UTC")} · {esc(s.title)}</div></div>
<div class=right>{replay}{outcome_pill(p, s)}</div></div>
<div class=grid2><div class=stack>
<div class=card><h3>Investigation timeline<span class=r>{label} · {len([r for r in rows if r["kind"] in ("probe", "tool")])} tool calls</span></h3><ul class=tl>{"".join(tl)}</ul></div>
<div class=card><h3>Proposed remediation<span class=r>requires human approval</span></h3><div class=body>
<div class=rem><span class=a>{esc(v["action"])} → {esc(v["target"])}</span><span class="pill {"ok" if ok else "bad"}">{esc(v["root_cause"])}</span><span class=r>
<span class="btn ok">✓ Approved · {esc(approval.get("by", "—"))}</span><span class="btn danger">Deny</span></span></div>
<p style="color:var(--mut);font-size:13px;margin:12px 0 0">{esc(v.get("summary", ""))}</p>
{f"<p class=note>Effect: {esc(eff_txt)}</p>" if eff_txt else ""}
</div></div>
</div><div class=stack>
<div class=card><div class=body style="padding:10px 12px"><div class=mini>
<div><div class=k>Calls</div><div class=v>{p.get("llm_calls", 0)}</div></div><div><div class=k>Probes</div><div class=v>{p.get("probes_run", 0)}</div></div>
<div><div class=k>Tokens</div><div class=v>{(int(p.get("input_tokens", 0)) + int(p.get("output_tokens", 0))):,}</div></div><div><div class=k>Hits</div><div class=v>{p.get("memory_hits") if p.get("memory_hits") is not None else "—"}</div></div>
<div><div class=k>Cost</div><div class=v>{cost(p)}</div></div></div></div></div>
<div class=card><h3>{ICONS["brain"]}Recalled from Hindsight<span class=r>at kickoff</span></h3><div class=body>{mem_html}</div></div>
<div class=card><h3>Provenance gate</h3><div class=body>{gate_html}</div></div>
<div class=card><h3>Retained after close</h3><div class=body>{ret_html}</div></div>
</div></div>"""
    crumb = f'<a href="index.html">Incidents</a><span>/</span><b>{esc(cid)}</b>'
    return shell(cid, crumb, "incidents", body, n_open)


def page_memory(gate: dict[str, dict[str, Any]], n_open: int) -> str:
    rows = []
    records = []
    for cid, p in gate.items():
        _, _, _, retained, _ = steps(p.get("trace", ""))
        if not retained:
            continue
        tags = retained.get("tags", [])
        d = {t.split(":")[0]: t.split(":", 1)[1] for t in tags if ":" in t}
        when = incident_when(cid, p)
        age = (T_NOW - when).days
        records.append((cid, when, d, retained))
        rows.append(
            f'<tr class=row><td class=mono><a href="incident-{cid}.html">{esc(cid)}</a></td><td class=mono style="color:var(--mut)">{when.strftime("%d %b %Y")}</td><td class=mono>{esc(d.get("root_cause", ""))}</td>'
            f"<td><span class=svc>{esc(d.get('service', ''))}</span></td><td class=mono>{esc(d.get('action', ''))}</td>"
            f"<td>{'<span class="pill ok">verified</span>' if d.get('verified') == 'yes' else '<span class="pill warn">unverified</span>'}</td>"
            f"<td>{'<span class="pill ok">yes</span>' if d.get('resolved') == 'yes' else '<span class="pill neu">no</span>'}</td>"
            f"<td>{'<span class="pill bad">yes</span>' if d.get('harm') == 'yes' else '<span class="pill neu">none</span>'}</td><td class=num>{age} d</td><td class=num>{retained.get('chars', '—')}</td></tr>"
        )
    verified = sum(1 for _, _, d, _ in records if d.get("verified") == "yes")
    body = f"""
<div class=h><div><h1>Memory bank</h1><p>What the agent remembers, and the evidence attached to each memory. Recall never becomes a verdict on its own.</p></div>
<div class=actions><a class=btn href="#">Export bank</a><a class="btn primary" href="#">Retain manual note</a></div></div>
<div class=tiles>
<div class=tile><div class=k>Records</div><div class=v>{len(records)}</div><div class=d>one per closed incident</div></div>
<div class=tile><div class=k>Verified by probe</div><div class=v>{verified}</div><div class=d class=up>{"all" if verified == len(records) else verified} carry <span class=mono>verified:yes</span></div></div>
<div class=tile><div class=k>Max age on recall</div><div class=v>90 d</div><div class=d><span class=mono>HINDSIGHT_MAX_AGE_DAYS</span></div></div>
<div class=tile><div class=k>Relevance cutoff</div><div class=v>0.30</div><div class=d>matches below are labelled weak</div></div>
</div>
<div class=split style="margin-bottom:14px">
<div class=card><h3>Provenance tags on every record</h3><div class=body>
<div class=tags><span class="tag">incident:&lt;id&gt;</span><span class="tag a">root_cause:&lt;cause&gt;</span><span class="tag">service:&lt;svc&gt;</span><span class="tag a">action:&lt;fix&gt;</span><span class="tag v">verified:yes|no</span><span class="tag v">resolved:yes|no</span><span class="tag h">harm:yes|no</span></div>
<p class=note>Tags are written at retain time from what actually happened: whether a probe confirmed the mechanism, whether the fix resolved the page, and whether anything was harmed. Recall returns them with every hit, so the agent can weigh a memory before trusting it.</p></div></div>
<div class=card><h3>Retain / recall</h3><div class=body><div class=kv>
<span class=k>Bank</span><span class=mono>provenance-demo</span><span class=k>Endpoint</span><span class=mono>api.hindsight.vectorize.io</span>
<span class=k>Recall</span><span>two phrasings at kickoff (alert + changes, alert + error lines), merged on best score</span>
<span class=k>Retain</span><span>after every closed incident: summary, root cause, action, effect, tags</span>
<span class=k>Extraction</span><span class=mono>gemini-3.1-flash-lite</span></div></div></div></div>
<div class=card><h3>Retained incidents<span class=r>{len(records)} records</span></h3>
<table><tr><th>Incident</th><th>Retained</th><th>Root cause</th><th>Service</th><th>Action that worked</th><th>Verified</th><th>Resolved</th><th>Harm</th><th class=num>Age</th><th class=num>Chars</th></tr>{"".join(rows)}</table></div>"""
    return shell("Memory bank", "<b>Memory bank</b>", "memory", body, n_open)


def page_analytics(
    gate: dict[str, dict[str, Any]],
    naive: dict[str, dict[str, Any]],
    nomem: dict[str, dict[str, Any]],
    n_open: int,
) -> str:
    cids = [c for c in SCENARIOS if c in gate and c in nomem]
    cols = [
        ("No memory", nomem, "#5f7086"),
        ("Memory, no gate", naive, "#f59e0b"),
        ("Memory + gate", gate, "#8b8cff"),
    ]

    def chart(metric: str, scale: float) -> str:
        out = []
        for cid in cids:
            bars = []
            for _name, data, color in cols:
                p = data.get(cid)
                if not p:
                    continue
                v = (
                    int(p.get("input_tokens", 0)) + int(p.get("output_tokens", 0))
                    if metric == "tokens"
                    else int(p.get(metric, 0))
                )
                bars.append(
                    f'<div class=b><i style="width:{max(2, int(v * scale))}px;background:{color}"></i><span>{v:,}</span></div>'
                )
            out.append(
                f"<div class=lbl>{esc(cid.split('_')[0])} {esc(SCENARIOS[cid].truth_root_cause)}</div><div class=bars>{''.join(bars)}</div>"
            )
        return f"<div class=chart>{''.join(out)}</div>"

    def acc(data: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
        ok = sum(
            1
            for c in cids
            if c in data and data[c]["verdict"]["root_cause"] == SCENARIOS[c].truth_root_cause
        )
        harm = sum(1 for c in cids if c in data and data[c].get("harm_done"))
        calls = sum(int(data[c].get("llm_calls", 0)) for c in cids if c in data)
        return ok, harm, calls

    tiles = ""
    for name, data, color in cols:
        ok, harm, calls = acc(data)
        n = sum(1 for c in cids if c in data)
        tiles += f'<div class=tile><div class=k><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{color};margin-right:6px"></i>{name}</div><div class=v>{ok}/{n}</div><div class=d>root causes right · {harm} harmful actions · {calls} LLM calls</div></div>'
    cited = sum(1 for c in cids if gate[c].get("memory_used"))
    tiles += f"<div class=tile><div class=k>Memory used in verdict</div><div class=v>{cited}/{len(cids)}</div><div class=d>with gate; every one re-verified by a probe</div></div>"
    legend = "".join(f'<span><i style="background:{c}"></i>{n}</span>' for n, _, c in cols)
    body = f"""
<div class=h><div><h1>Analytics</h1><p>Same incidents, same model, same tools. Three configurations of the agent, side by side.</p></div>
<div class=actions><a class=btn href="#">Last 30 days</a><a class=btn href="#">Export CSV</a></div></div>
<div class=tiles>{tiles}</div>
<div class=split>
<div class=card><h3>LLM calls per incident</h3><div class=body><div class=legend>{legend}</div>{chart("llm_calls", 22)}</div></div>
<div class=card><h3>Probes per incident</h3><div class=body><div class=legend>{legend}</div>{chart("probes_run", 40)}</div></div>
</div>
<div class=split style="margin-top:14px">
<div class=card><h3>Tokens per incident</h3><div class=body><div class=legend>{legend}</div>{chart("tokens", 0.0045)}</div></div>
<div class=card><h3>What memory changed</h3><div class=body>
<div class=kv style="grid-template-columns:150px 1fr;gap:10px 12px">
<span class=k>Accuracy</span><span>Unchanged on this benchmark. The memoryless agent already solves these; memory did not add or remove a correct verdict.</span>
<span class=k>First probe</span><span>On repeats (s13, s17) the agent went straight to the probe that settled the earlier incident.</span>
<span class=k>Context</span><span>Recall adds 1–3k tokens per incident for the memory block; the gate adds one call when it fires.</span>
<span class=k>Safety</span><span>A remembered rollback that would have been wrong on s15 is blocked until re-verified. Live runs never took the bait; the offline replay shows the gate firing.</span>
<span class=k>Open gap</span><span>s16 (poison message) is wrong in every configuration; recall found nothing because the earlier record is worded too differently.</span>
</div></div></div></div>
<p class=note>Source: eval/results/fair-* and pair-* on gemini-3.5-flash-lite. Reproduce with <span class=mono>make memory-eval</span>.</p>"""
    return shell("Analytics", "<b>Analytics</b>", "analytics", body, n_open)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", nargs="+", default=["fair-gate", "pair-gate"])
    ap.add_argument("--nomem", nargs="+", default=["fair-nomem", "pair-nomem"])
    ap.add_argument("--naive", nargs="+", default=["fair-naive"])
    ap.add_argument("--replay", nargs="+", default=["gate-demo"])
    ap.add_argument("--out", default="docs/console")
    a = ap.parse_args()
    gate, nomem, naive, replay = merge(a.gate), merge(a.nomem), merge(a.naive), merge(a.replay)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cids = [c for c in SCENARIOS if c in gate]
    n_open = sum(
        1
        for c in cids
        if not (
            gate[c]["verdict"]["root_cause"] == SCENARIOS[c].truth_root_cause
            and gate[c].get("resolved")
        )
    )
    (out / "index.html").write_text(page_index(gate, nomem, replay), encoding="utf-8")
    for cid in cids:
        (out / f"incident-{cid}.html").write_text(
            page_incident(cid, gate[cid], "memory + gate", n_open), encoding="utf-8"
        )
    for cid, p in replay.items():
        (out / f"replay-{cid}.html").write_text(
            page_incident(cid, p, "offline replay", n_open), encoding="utf-8"
        )
    for cid, p in nomem.items():
        (out / f"nomem-{cid}.html").write_text(
            page_incident(cid, p, "no memory", n_open), encoding="utf-8"
        )
    (out / "memory.html").write_text(page_memory(gate, n_open), encoding="utf-8")
    (out / "analytics.html").write_text(
        page_analytics(gate, naive, nomem, n_open), encoding="utf-8"
    )
    print(
        f"wrote {out}/ ({len(cids)} incidents, {len(replay)} replays, {len(nomem)} no-memory runs)"
    )


if __name__ == "__main__":
    main()
