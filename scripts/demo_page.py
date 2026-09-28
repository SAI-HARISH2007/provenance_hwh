"""Render an offline demo page from eval results + traces: docs/demo/index.html.

Usage: python scripts/demo_page.py --runs seq-nomem seq-mem [--title ...]
The first run is the "before" column, the last is the "after" column. One self-contained HTML
file, no network, so it can be screen-recorded without anything live.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from greenlight.sim import SCENARIOS  # noqa: E402
from greenlight.tracing import load_trace  # noqa: E402

RESULTS = Path("eval/results")

CSS = """
:root{--bg:#0b0f14;--panel:#121820;--line:#22303d;--txt:#dbe4ee;--mut:#8aa0b4;--ok:#2ecc71;--bad:#ff5c5c;--warn:#ffb020;--mem:#7aa2ff;--acc:#38bdf8}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.45 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 20px 80px}h1{font-size:28px;margin:0 0 4px}h1 span{color:var(--mem)}
.sub{color:var(--mut);margin:0 0 26px}h2{font-size:20px;margin:36px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
th{background:#0f151c;color:var(--mut);font-weight:600}td.num{text-align:right;font-variant-numeric:tabular-nums}
.alert{background:#1a1113;border:1px solid #5a2a2f;border-left:6px solid var(--bad);border-radius:8px;padding:12px 16px;margin:18px 0 10px;display:flex;gap:18px;align-items:center}
.alert .sev{background:var(--bad);color:#fff;font-weight:700;border-radius:6px;padding:4px 10px}.alert .svc{font-family:ui-monospace,Menlo,monospace;color:var(--warn)}
.alert small{color:var(--mut)}.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:900px){.cols{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.panel h3{margin:0 0 10px;font-size:15px;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.panel h3 b{color:var(--txt)}.tl{list-style:none;margin:0;padding:0}.tl li{padding:5px 0 5px 14px;border-left:2px solid var(--line);font-family:ui-monospace,Menlo,monospace;font-size:13px}
.tl li.probe{border-left-color:var(--acc)}.tl li.verdict{border-left-color:var(--ok)}.tl li.rej{border-left-color:var(--bad);color:#ffb3b3}.tl li.mem{border-left-color:var(--mem);color:#cdd9ff}
.tl li.human{border-left-color:var(--warn)}.tl li small{color:var(--mut)}.mem{background:#0f1526;border:1px solid #2b3a66;border-radius:10px;padding:12px 14px;margin-top:12px}
.mem h4{margin:0 0 8px;color:var(--mem);font-size:14px}.hit{font-size:13px;margin:4px 0;padding-left:10px;border-left:2px solid var(--mem)}.hit .tag{display:inline-block;background:#1b2a4a;color:#b8c8ff;border-radius:4px;padding:0 6px;margin-left:4px;font-size:11px}
.gate{margin-top:8px;padding:8px 10px;border-radius:8px;font-size:13px}.gate.rej{background:#2a1416;border:1px solid #6b2a2f}.gate.acc{background:#122417;border:1px solid #275a35}
.out{margin-top:12px;font-size:14px}.pill{display:inline-block;border-radius:999px;padding:2px 10px;font-size:12px;font-weight:600;margin-right:6px}.ok{background:#153b25;color:#8ff0b4}.bad{background:#4a1a1e;color:#ffb3b3}.neu{background:#1c2733;color:#b8c8d8}
.stat{display:flex;gap:14px;flex-wrap:wrap;margin-top:8px}.stat div{background:#0f151c;border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:13px}.stat b{font-size:16px;display:block}
.foot{color:var(--mut);font-size:13px;margin-top:40px}
"""


def load_run(run: str) -> dict[str, dict[str, Any]]:
    d = RESULTS / run
    return {p.stem: json.loads(p.read_text()) for p in sorted(d.glob("s*.json")) if p.stem in SCENARIOS}


def timeline(trace_path: str) -> tuple[list[tuple[str, str]], list[dict[str, Any]], list[dict[str, Any]], dict | None]:
    """Return (timeline items, recall hits, gate checks, retain record) from a JSONL trace."""
    items: list[tuple[str, str]] = []
    hits: list[dict[str, Any]] = []
    gates: list[dict[str, Any]] = []
    retained: dict | None = None
    p = Path(trace_path)
    if not p.exists():
        return [("rej", f"trace missing: {trace_path}")], hits, gates, retained
    for e in load_trace(p):
        t = e["type"]
        if t == "tool_call":
            name, inp = e["name"], e.get("input") or {}
            if name == "run_probe":
                items.append(("probe", f"run_probe {inp.get('kind')} {inp.get('target')}"))
            elif name == "submit_verdict":
                items.append(("verdict", f"submit_verdict {inp.get('root_cause')} @ {inp.get('service')} → {inp.get('action')}:{inp.get('target')}"))
            elif name == "remediate":
                items.append(("human", f"remediate {inp.get('action')} on {inp.get('target')}"))
            elif name == "recall_similar_incidents":
                items.append(("mem", f"recall_similar_incidents({str(inp.get('query'))[:60]}…)"))
            else:
                args = ", ".join(f"{k}={str(v)[:24]}" for k, v in inp.items())
                items.append(("tool", f"{name}({args})"))
        elif t == "feedback":
            src, sig = e.get("source"), e.get("signal")
            if src == "hindsight_memory" and sig == "recall":
                try:
                    hits = json.loads(e.get("detail") or "[]")
                except Exception:  # noqa: BLE001
                    hits = []
                items.append(("mem", f"memory recall → {e.get('n_hits', 0)} hit(s) in {e.get('latency_ms', '?')} ms"))
            elif src == "hindsight_memory" and sig == "retain":
                try:
                    retained = json.loads(e.get("detail") or "{}")
                except Exception:  # noqa: BLE001
                    retained = {"raw": e.get("detail")}
                items.append(("mem", "memory retain → incident record stored"))
            elif src == "provenance_gate":
                gates.append({"accepted": sig == "accepted", "reason": e.get("detail", ""), "sources": e.get("sources")})
                items.append(("rej" if sig == "rejected" else "verdict", f"provenance gate: {sig.upper()}"))
            elif src == "verification_gate":
                items.append(("rej", "verification gate: REJECTED (no probe)"))
            elif src == "reviewer_agent" and sig in ("rejected", "reject"):
                items.append(("rej", "reviewer: rejected"))
            elif src == "simulation":
                items.append(("human" if sig != "harm" else "rej", f"effect: {sig} — {e.get('detail', '')[:90]}"))
        elif t == "human_checkpoint":
            items.append(("human", f"human checkpoint → {e.get('decision')} ({e.get('by')})"))
    return items, hits, gates, retained


def esc(x: Any) -> str:
    return html.escape(str(x))


def render_case(cid: str, runs: list[str], payloads: dict[str, dict[str, Any]]) -> str:
    s = SCENARIOS[cid]
    out = [
        f'<div class="alert"><span class="sev">{esc(s.alert["severity"])}</span>'
        f'<div><div><span class="svc">{esc(s.alert["service"])}</span> &nbsp;{esc(s.alert["message"])}</div>'
        f'<small>{esc(cid)} · {esc(s.title)}</small></div></div>',
        '<div class="cols">',
    ]
    for run in runs:
        p = payloads.get(run)
        if p is None:
            continue  # this run did not include the incident; no empty panel
        items, hits, gates, retained = timeline(p.get("trace", ""))
        v = p["verdict"]
        correct = v["root_cause"] == s.truth_root_cause
        harm = bool(p.get("harm_done"))
        if "demo" in run or p.get("scripted"):
            label = "scripted trap (offline test, fake model)"
        elif "nomem" in run or p.get("memory_hits") is None:
            label = "without memory"
        elif "naive" in run:
            label = "memory, no provenance gate"
        else:
            label = "memory + provenance gate"
        out.append(f'<div class="panel"><h3>{esc(run)} · <b>{label}</b></h3><ul class="tl">')
        for kind, text in items:
            out.append(f'<li class="{kind}">{esc(text)}</li>')
        out.append("</ul>")
        if hits or gates or retained:
            out.append('<div class="mem"><h4>Hindsight memory</h4>')
            if hits:
                out.append(f"<div>recalled {len(hits)} fact(s) at kickoff:</div>")
                for h in hits[:5]:
                    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in (h.get("tags") or []) if t.split(":")[0] in ("incident", "verified", "action"))
                    out.append(f'<div class="hit">{esc(h.get("text", "")[:170])}{tags}</div>')
            elif p.get("memory_hits") == 0:
                out.append("<div>recall at kickoff: <i>nothing similar in memory (first time)</i></div>")
            for g in gates:
                cls = "acc" if g["accepted"] else "rej"
                out.append(f'<div class="gate {cls}"><b>provenance gate {"accepted" if g["accepted"] else "REJECTED"}</b>: {esc(g["reason"][:260])}</div>')
            if retained:
                out.append(f'<div style="margin-top:8px;font-size:13px;color:#b8c8ff">retained: {esc(retained.get("incident"))} · {esc(retained.get("when", ""))} · {esc(" ".join(t for t in retained.get("tags", []) if t.split(":")[0] in ("verified", "resolved", "harm")))}</div>')
            out.append("</div>")
        pills = [
            f'<span class="pill {"ok" if correct else "bad"}">root cause {"✓" if correct else "✗"}</span>',
            f'<span class="pill {"bad" if harm else "ok"}">{"HARM DONE" if harm else "no harm"}</span>',
            f'<span class="pill {"ok" if p.get("resolved") else "neu"}">{"resolved" if p.get("resolved") else "not resolved"}</span>',
        ]
        eff = (p.get("remediation_effect") or {}).get("effect", "")
        out.append(f'<div class="out">{"".join(pills)}<div style="margin-top:6px">verdict: <code>{esc(v["root_cause"])}</code> @ {esc(v["service"])} → <code>{esc(v["action"])}</code> on {esc(v["target"])}</div>')
        if eff:
            out.append(f'<div style="color:var(--mut);font-size:13px;margin-top:4px">effect: {esc(eff[:200])}</div>')
        out.append('<div class="stat">'
                   f'<div>LLM calls<b>{p.get("llm_calls", 0)}</b></div><div>probes<b>{p.get("probes_run", 0)}</b></div>'
                   f'<div>tokens<b>{(p.get("input_tokens", 0) + p.get("output_tokens", 0)):,}</b></div><div>wall<b>{p.get("wall_s", 0):.0f}s</b></div>'
                   + (f'<div>memory hits<b>{p.get("memory_hits", 0)}</b></div><div>gate challenges<b>{p.get("memory_rejections", 0)}</b></div>' if p.get("memory_hits") is not None else "")
                   + "</div></div></div>")
    out.append("</div>")
    return "\n".join(out)


def summary_table(runs: list[str], data: dict[str, dict[str, dict[str, Any]]], order: list[str]) -> str:
    head = "<tr><th>Incident</th>" + "".join(f"<th colspan=5>{esc(r)}</th>" for r in runs) + "</tr>"
    sub = "<tr><th></th>" + "".join("<th>cause</th><th>calls</th><th>probes</th><th>tokens</th><th>harm</th>" for _ in runs) + "</tr>"
    rows = []
    for cid in order:
        cells = [f"<td>{esc(cid)}</td>"]
        for r in runs:
            p = data[r].get(cid)
            if not p:
                cells.append("<td colspan=5>—</td>")
                continue
            ok = p["verdict"]["root_cause"] == SCENARIOS[cid].truth_root_cause
            cells.append(
                f'<td>{"✓" if ok else "✗"}</td><td class="num">{p.get("llm_calls", 0)}</td><td class="num">{p.get("probes_run", 0)}</td>'
                f'<td class="num">{(p.get("input_tokens", 0) + p.get("output_tokens", 0)):,}</td>'
                f'<td>{"<b style=color:var(--bad)>YES</b>" if p.get("harm_done") else "no"}</td>'
            )
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table>{head}{sub}{''.join(rows)}</table>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default="docs/demo/index.html")
    ap.add_argument("--title", default="Provenance — an on-call agent whose memory has to prove itself")
    a = ap.parse_args()
    data = {r: load_run(r) for r in a.runs}
    order = [c for c in SCENARIOS if any(c in data[r] for r in a.runs)]
    parts = [
        "<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>",
        f"<title>{esc(a.title)}</title><style>{CSS}</style></head><body><main>",
        f"<h1>Provenance <span>· memory with evidence</span></h1><p class=sub>{esc(a.title)}. Same incidents, same model, same tools. Columns: no memory · Hindsight memory without the gate · Hindsight memory with the provenance gate · and, for the trap incident only, a scripted offline replay that shows the gate firing.</p>",
        "<h2>Before / after</h2>", summary_table(a.runs, data, order),
    ]
    for cid in order:
        parts.append(render_case(cid, a.runs, {r: data[r].get(cid) for r in a.runs}))
    parts.append('<p class=foot>Generated from eval/results and traces/*.jsonl. Every number on this page is reproducible from the repo.</p></main></body></html>')
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes) for {len(order)} incident(s)")


if __name__ == "__main__":
    main()
