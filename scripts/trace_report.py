"""Render traces/*.jsonl into human-readable Markdown under docs/traces/."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from greenlight.tracing import load_trace


def render(path: Path) -> str:
    ev = list(load_trace(path))
    if not ev:
        return f"# {path.stem}\n\n(empty)\n"
    start = next((e for e in ev if e["type"] == "run_start"), {})
    end = next((e for e in reversed(ev) if e["type"] == "run_end"), {})
    counts = Counter(e["type"] for e in ev)
    lines = [f"# Trace `{path.stem}`", ""]
    lines += [
        (
            f"- problem: `{start.get('problem_id')}`  model: `{start.get('model')}`  "
            f"sandbox: `{start.get('sandbox')}`  agent_version: `{start.get('agent_version')}`"
        ),
        (
            f"- status: **{end.get('status', 'incomplete')}**  score: {end.get('score')}  "
            f"tokens: {end.get('total_tokens')}  wall: {end.get('wall_ms')} ms"
        ),
        f"- events: {dict(counts)}",
        "",
    ]
    lines += ["## Timeline", "", "| seq | type | summary |", "|---|---|---|"]
    for e in ev:
        t = e["type"]
        if t == "instruction":
            s = f"{e['role']} `{e['name']}` ({len(e['content'])} chars)"
        elif t == "llm_response":
            s = f"{e['stop_reason']}; tools={[c['name'] for c in e.get('tool_calls', [])]}; {e['latency_ms']} ms"
        elif t == "tool_call":
            s = f"`{e['name']}` attempt {e['attempt']}: `{str(e['input'])[:120]}`"
        elif t == "tool_result":
            s = f"ok={e['ok']} exit={e.get('exit_code')} {e['duration_ms']} ms: `{e['output'][:120]!r}`"
        elif t == "error":
            s = f"**{e['kind']}** @{e['where']} recoverable={e['recoverable']}: {e['message'][:120]}"
        elif t == "retry":
            s = f"retry of #{e['of']} attempt {e['attempt']} via {e['strategy']}: {e['reason'][:100]}"
        elif t == "feedback":
            s = f"{e['source']} → **{e['signal']}**: {e['detail'][:120]}"
        elif t == "decision":
            s = f"{e['summary']} → chose `{e['chosen']}` ({e['rationale'][:100]})"
        elif t == "human_checkpoint":
            s = f"❓ {e['question']} → **{e['decision']}** by {e['by']}"
        elif t == "run_end":
            s = f"{e['status']} score={e['score']}"
        else:
            s = ""
        lines.append(f"| {e['seq']} | {t} | {s.replace('|', '\\|')} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    root = Path("traces")
    out = Path("docs/traces")
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(root.glob("*.jsonl"))
    for f in files:
        (out / f"{f.stem}.md").write_text(render(f), encoding="utf-8")
    print(f"rendered {len(files)} trace(s) -> {out}/")


if __name__ == "__main__":
    main()
