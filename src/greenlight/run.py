"""Run the advanced agent on eval cases.
Usage: python -m greenlight.run --variant final [--cases ...] [--tag name] [--approve auto|deny|ask]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import VARIANTS, Investigator
from .agent.investigator import default_eval_approver
from .common import RESULTS_DIR, write_case_result
from .llm import LLM
from .memory import HindsightMemory
from .sim import SCENARIOS


def make_approver(mode: str):
    if mode == "auto":
        return default_eval_approver
    if mode == "deny":
        return lambda v, report, ctx: ("denied", "auto-deny policy (dry run)")

    def ask(v, report, ctx):
        print("\n" + "=" * 78 + "\nINCIDENT REPORT (for approval)\n" + "=" * 78)
        print(report[:6000])
        print("-" * 78)
        print(f"Proposed remediation: {v.action} on {v.target}  (confidence {v.confidence})")
        print(f"Reviewer approved: {ctx.get('reviewer_approved')}   verified by probe: {ctx.get('verified')}   "
              f"gate rejections: {ctx.get('gate_rejections')}")
        ans = input("Approve? [y/N] ").strip().lower()
        return (
            ("approved", "human approved at terminal")
            if ans == "y"
            else ("denied", "human denied at terminal")
        )

    return ask


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="final", choices=list(VARIANTS))
    ap.add_argument("--cases", nargs="*", default=list(SCENARIOS))
    ap.add_argument("--tag", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--approve", default="auto", choices=["auto", "deny", "ask"])
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--bank", default=None, help="Hindsight bank id (default: provenance-<tag>)")
    ap.add_argument("--reset-bank", action="store_true", help="start from an empty memory bank")
    a = ap.parse_args()
    cfg = VARIANTS[a.variant]
    tag = a.tag or a.variant
    run_dir = RESULTS_DIR / tag
    llm = LLM(model=a.model, use_cache=not a.no_cache)
    memory = None
    if cfg.memory:
        memory = HindsightMemory(bank_id=a.bank or f"provenance-{tag}")
        if a.reset_bank:
            memory.reset()
        else:
            memory.ensure_bank()
        print(f"memory: bank={memory.bank_id} (order of --cases matters: the bank accumulates)")
    inv = Investigator(cfg, llm, Path("traces"), approver=make_approver(a.approve), memory=memory)
    for cid in a.cases:
        before = (llm.input_tokens, llm.output_tokens)
        out = inv.run(SCENARIOS[cid])
        out.meta["input_tokens"] = llm.input_tokens - before[0]
        out.meta["output_tokens"] = llm.output_tokens - before[1]
        pin, pout = __import__("greenlight.llm", fromlist=["PRICE_PER_M"]).PRICE_PER_M.get(
            llm.model, (0, 0)
        )
        out.meta["would_be_cost_usd"] = round(
            (out.meta["input_tokens"] * pin + out.meta["output_tokens"] * pout) / 1e6, 5
        )
        write_case_result(run_dir, cid, out.verdict, out.meta)
        v = out.verdict
        m = out.meta
        print(
            f"{cid:32s} {m['status']:8s} rc={v.root_cause:28s} action={v.action}:{v.target:14s} "
            f"calls={m['llm_calls']:2d} probes={m['probes_run']} verified={m['verified']} "
            f"rej={m['gate_rejections']} harm={bool(m['harm_done'])} resolved={m['resolved']} {m['wall_s']}s"
            + (
                f"\n{'':32s} memory: hits={m['memory_hits']} used={m['memory_used']} "
                f"gate_rejections={m['memory_rejections']} retained={bool(m.get('memory_retained'))}"
                if memory is not None
                else ""
            )
        )
    print("llm stats:", json.dumps(llm.stats()))
    if memory is not None:
        memory.close()


if __name__ == "__main__":
    main()
