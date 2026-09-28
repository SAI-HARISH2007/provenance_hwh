"""Produce a scripted, offline demonstration of the provenance gate for the demo page.

The live model did not fall for the look-alike trap in our recorded runs, so this replays the
scripted agent from tests/test_memory_offline.py (fake LLM, fake memory, no network) against
s15 and writes a normal result + trace under eval/results/gate-demo/. The demo page labels it
"scripted (offline test)". Nothing here is presented as a live run.

Usage: python scripts/gate_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from test_agent_offline import FakeLLM, _tc  # noqa: E402
from test_memory_offline import ROLLBACK, TRUTH, FakeMemory  # noqa: E402

from greenlight.agent import VARIANTS, Investigator  # noqa: E402
from greenlight.common import RESULTS_DIR, write_case_result  # noqa: E402
from greenlight.sim import SCENARIOS  # noqa: E402


def main() -> None:
    script = [
        ("", [_tc(1, "get_alert")]),
        ("", [_tc(2, "recent_changes", last_hours=24)]),
        ("", [_tc(3, "run_probe", kind="http", target="api.paygate.example")]),
        ("", [_tc(4, "submit_verdict", **ROLLBACK)]),  # remembered fix -> gate rejects
        ("", [_tc(5, "run_probe", kind="http", target="payments-api")]),
        ("", [_tc(6, "submit_verdict", **TRUTH)]),
    ]
    llm = FakeLLM(script)
    inv = Investigator(VARIANTS["mem_gate"], llm, Path("traces"), memory=FakeMemory())
    out = inv.run(SCENARIOS["s15_secret_rotation_lookalike"])
    out.meta["input_tokens"] = llm.input_tokens
    out.meta["output_tokens"] = llm.output_tokens
    out.meta["scripted"] = True
    write_case_result(RESULTS_DIR / "gate-demo", "s15_secret_rotation_lookalike", out.verdict, out.meta)
    print(
        f"gate-demo: verdict={out.verdict.root_cause} memory_rejections={out.meta['memory_rejections']} "
        f"trace={out.meta['trace']}"
    )


if __name__ == "__main__":
    main()
