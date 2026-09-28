"""Simple baseline: one direct prompt with the evidence dump ("paste the logs into chat").

Same model, same cases, same taxonomy as the agent. No tools, no verification.
Usage: python -m greenlight.baseline [--cases s01_… ...] [--model M] [--tag name]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .common import (
    RESULTS_DIR,
    Verdict,
    git_sha,
    parse_json_block,
    verdict_from_dict,
    write_case_result,
)
from .llm import LLM
from .sim import ACTIONS, ROOT_CAUSES, SCENARIOS, World
from .tracing import TraceWriter, new_run_id, sha256_text

PROMPT_PATH = Path(__file__).parent / "prompts" / "baseline_system.md"
MAX_OUT = 16384  # Gemini 3.x emits visible reasoning before the JSON; 4096 truncated 3/12 answers


def system_prompt() -> str:
    return (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{ROOT_CAUSES}}", json.dumps(ROOT_CAUSES))
        .replace("{{ACTIONS}}", json.dumps(ACTIONS))
    )


def run_case(case_id: str, llm: LLM, run_dir: Path, trace_root: Path, scope: str = "alert") -> dict:
    world = World(SCENARIOS[case_id])
    run_id = new_run_id(f"baseline-{case_id}")
    sys_p = system_prompt()
    t0 = time.monotonic()
    with TraceWriter(run_id, root=trace_root) as tw:
        llm.on_event = lambda et, **f: getattr(tw, et)(**f)
        tw.run_start(
            problem_id=case_id,
            agent_version=git_sha(),
            model=llm.model,
            params={"temperature": llm.temperature, "max_tokens": MAX_OUT},
            tools=[],
            sandbox="simulation",
            prompt_hashes={"baseline_system.md": sha256_text(sys_p)},
            variant="baseline",
        )
        tw.instruction(role="system", name="baseline_system.md", content=sys_p)
        user = "Here is what I have from the dashboards:\n\n" + world.evidence_dump(scope=scope)
        tw.instruction(role="user", name="evidence_dump", content=user)
        msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": user}]
        tw.llm_request(n_messages=2, tools_offered=[])
        resp = llm.chat(msgs, max_tokens=MAX_OUT)
        tw.llm_response(
            stop_reason=resp.stop_reason,
            text=resp.text,
            tool_calls=[],
            output_tokens=resp.output_tokens,
            latency_ms=resp.latency_ms,
            input_tokens=resp.input_tokens,
            cached=resp.cached,
            provider=resp.provider,
        )
        try:
            verdict = verdict_from_dict(parse_json_block(resp.text))
            status = "success"
        except Exception as e:  # noqa: BLE001
            tw.error(where="parser", kind=type(e).__name__, message=str(e), recoverable=False)
            verdict, status = Verdict(summary=f"unparseable output: {e}"), "fail"
        wall = round(time.monotonic() - t0, 2)
        meta = {
            "variant": "baseline",
            "run_id": run_id,
            "trace": str(trace_root / f"{run_id}.jsonl"),
            "model": llm.model,
            "provider": resp.provider,
            "status": status,
            "llm_calls": 1,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "would_be_cost_usd": round(resp.would_be_cost_usd, 5),
            "wall_s": wall,
            "probes_run": 0,
            "verified": False,
            "actions_executed": [],
            "harm_done": [],
        }
        tw.run_end(
            status=status,
            final_output=json.dumps(verdict.__dict__)[:2000],
            total_tokens=resp.input_tokens + resp.output_tokens,
            cost_usd=0.0,
            would_be_cost_usd=meta["would_be_cost_usd"],
        )
    write_case_result(run_dir, case_id, verdict, meta)
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", nargs="*", default=list(SCENARIOS))
    ap.add_argument("--model", default=None)
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--scope", default="alert", choices=["alert", "full"],
                    help="alert = realistic paste (alerting service logs); full = everything")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()
    run_dir = RESULTS_DIR / a.tag
    llm = LLM(model=a.model, use_cache=not a.no_cache)
    for cid in a.cases:
        meta = run_case(cid, llm, run_dir, Path("traces"), scope=a.scope)
        v = json.loads((run_dir / f"{cid}.json").read_text(encoding="utf-8"))["verdict"]
        print(
            f"{cid:32s} {meta['status']:8s} rc={v['root_cause']:28s} action={v['action']}:{v['target']}  "
            f"{meta['wall_s']}s tok={meta['input_tokens']}+{meta['output_tokens']}"
        )
    print("llm stats:", llm.stats())


if __name__ == "__main__":
    main()
