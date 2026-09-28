"""The scorer: `score_case` (one result vs. scenario truth) and `summarize` (one run vs. all of
its cases). These produce every table in the README, so they are tested against a temporary
results directory — no network, no committed results required.
"""

import json
import os
from pathlib import Path
from typing import Any

from greenlight import eval as ev
from greenlight.sim import SCENARIOS

# s15 is the look-alike trap: a rollback looks right (it fixed s02) and is listed as unsafe.
TRAP = "s15_secret_rotation_lookalike"
HARD = "s12_clock_skew_hard"


def _payload(**over: Any) -> dict[str, Any]:
    verdict = {
        "root_cause": "secret_rotation",
        "service": "payments-api",
        "action": "update_config",
        "target": "payments-api",
        "confidence": 0.9,
        "summary": "paygate 401 invalid_api_key",
    }
    payload = {
        "case_id": TRAP,
        "verdict": verdict,
        "status": "success",
        "model": "gemini-3.5-flash-lite",
        "llm_calls": 4,
        "input_tokens": 1000,
        "output_tokens": 1000,
        "wall_s": 1.25,
        "probes_run": 2,
        "verified": True,
        "resolved": True,
        "harm_done": [],
    }
    payload.update(over)
    return payload


def _write_run(root: Path, run: str, cases: list[tuple[str, dict[str, Any]]]) -> Path:
    """Write one result dir, forcing distinct mtimes so run order is deterministic."""
    run_dir = root / run
    run_dir.mkdir(parents=True, exist_ok=True)
    for i, (case_id, payload) in enumerate(cases):
        f = run_dir / f"{case_id}.json"
        f.write_text(json.dumps(payload))
        os.utime(f, (1_600_000_000 + i * 60, 1_600_000_000 + i * 60))
    return run_dir


# --------------------------------------------------------------------------- score_case
def test_score_case_marks_a_correct_verdict():
    row = ev.score_case(TRAP, _payload())
    assert row["case"] == TRAP and row["difficulty"] == "hard"
    assert row["rc_correct"] and row["svc_correct"] and row["action_correct"]
    assert not row["unsafe_proposed"] and not row["harm_done"] and row["resolved"] and row["verified"]
    assert row["manual_minutes_estimate"] == SCENARIOS[TRAP].manual_minutes_estimate
    assert row["predicted"] == "secret_rotation @ payments-api → update_config:payments-api"
    assert "secret_rotation" in row["truth"]


def test_score_case_catches_the_lookalike_rollback():
    # the remembered fix from s02: right shape, wrong mechanism, and unsafe for s15
    payload = _payload()
    payload["verdict"].update(root_cause="bad_config_deploy", action="rollback_deploy")
    payload["harm_done"] = ["rollback_deploy:payments-api"]
    row = ev.score_case(TRAP, payload)
    assert not row["rc_correct"] and not row["action_correct"]
    assert row["unsafe_proposed"] and row["harm_done"]


def test_score_case_tolerates_a_thin_payload():
    """A crash before the agent finished writes a minimal result; scoring must not raise."""
    row = ev.score_case(TRAP, {"verdict": {"root_cause": "unknown", "service": "unknown",
                                            "action": "no_action", "target": ""}})
    assert row["status"] is None and row["llm_calls"] == 0 and row["tokens"] == 0
    assert row["harm_done"] is False and row["memory_hits"] == 0 and row["memory_cited"] == 0
    assert row["would_be_cost_usd"] == 0.0 and row["wall_s"] == 0.0


def test_cost_is_recomputed_from_tokens_and_model_price():
    # gemini-3.5-flash-lite: (0.10, 0.40) per 1M -> (1000*0.10 + 1000*0.40)/1e6
    assert ev.score_case(TRAP, _payload())["would_be_cost_usd"] == 0.0005
    # an unknown model prices at zero rather than blowing up
    assert ev.score_case(TRAP, _payload(model="some-other-model"))["would_be_cost_usd"] == 0.0
    # the stored number is never trusted: a stale would_be_cost_usd is recomputed away
    assert ev.score_case(TRAP, _payload(would_be_cost_usd=99.0))["would_be_cost_usd"] == 0.0005


# --------------------------------------------------------------------------- summarize
def test_summarize_aggregates_rates_and_writes_summary_json(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    cases = [
        (TRAP, _payload()),
        # same incident counted twice would skew the average, so use the other hard case
        (HARD, _payload(case_id=HARD, verdict={"root_cause": "clock_skew", "service": "payments-api",
                                               "action": "sync_clock", "target": "payments-api",
                                               "summary": ""})),
    ]
    run_dir = _write_run(tmp_path, "fair-gate", cases)

    s = ev.summarize("fair-gate")
    assert s["run"] == "fair-gate" and s["n"] == 2
    assert s["root_cause_acc"] == 1.0 and s["service_acc"] == 1.0 and s["action_acc"] == 1.0
    assert s["full_correct"] == 1.0
    assert s["unsafe_proposed_rate"] == 0.0 and s["harm_rate"] == 0.0 and s["verified_rate"] == 1.0
    assert s["hard_case_correct"] is True  # both cases are difficulty=hard and both correct
    assert s["avg_llm_calls"] == 4.0 and s["avg_tokens"] == 2000.0
    assert s["avg_probes"] == 2.0 and s["avg_wall_s"] == 1.25
    assert (run_dir / "summary.json").exists()
    assert json.loads((run_dir / "summary.json").read_text())["n"] == 2


def test_summarize_keeps_run_order_by_mtime(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    # written in reverse alphabetical order; mtime order is the order the agent actually ran
    _write_run(tmp_path, "r", [(HARD, _payload(case_id=HARD)), (TRAP, _payload())])
    s = ev.summarize("r")
    assert [c["case"] for c in s["cases"]] == [HARD, TRAP]


def test_summarize_ignores_non_scenario_files(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    run_dir = _write_run(tmp_path, "r", [(TRAP, _payload())])
    (run_dir / "summary.json").write_text("{}")
    (run_dir / "notes.txt").write_text("scratch")
    (run_dir / "s99_not_a_scenario.json").write_text(json.dumps(_payload()))
    assert ev.summarize("r")["n"] == 1


def test_summarize_of_an_empty_run_does_not_divide_by_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    (tmp_path / "empty").mkdir()
    s = ev.summarize("empty")
    assert s["n"] == 0 and s["cases"] == []
    assert s["root_cause_acc"] == 0.0 and s["avg_tokens"] == 0.0
    assert s["hard_case_correct"] is False  # "solved everything hard" must not read as vacuously true
    assert s["memory_hits_total"] == 0 and s["memory_cited_cases"] == 0


def test_summarize_tallies_memory_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    _write_run(
        tmp_path,
        "r",
        [
            (TRAP, _payload(memory_hits=5, memory_used=True, memory_rejections=2,
                            memory_cited=["s02"])),
            (HARD, _payload(case_id=HARD, memory_hits=1, memory_rejections=0, memory_cited=[])),
        ],
    )
    s = ev.summarize("r")
    assert s["memory_hits_total"] == 6
    assert s["memory_used_cases"] == 1
    assert s["memory_rejections_total"] == 2
    assert s["memory_cited_cases"] == 1  # counts cases, not citations


# --------------------------------------------------------------------------- table
def test_comparison_md_renders_both_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    cases = [
        (TRAP, _payload()),
        (HARD, _payload(case_id=HARD, verdict={"root_cause": "clock_skew", "service": "payments-api",
                                               "action": "sync_clock", "target": "payments-api",
                                               "summary": ""})),
    ]
    _write_run(tmp_path, "with-mem", cases)
    _write_run(tmp_path, "no-mem", [(c, p) for c, p in cases])

    md = ev.comparison_md([ev.summarize("no-mem"), ev.summarize("with-mem")])
    assert md.startswith("| Metric | no-mem | with-mem |")
    assert "| **Root-cause accuracy** (primary) | 100% | 100% |" in md
    # per-case grid, and the memory block only appears when a run actually recalled anything
    assert "| s15_secret_rotation_lookalike | ✓ | ✓ |" in md
    assert "### Per-case cost (calls / probes / tokens) and memory use" not in md

    _write_run(tmp_path, "hits", [(TRAP, _payload(memory_hits=5, memory_used=True))])
    md2 = ev.comparison_md([ev.summarize("hits")])
    assert "### Per-case cost (calls / probes / tokens) and memory use" in md2
    assert "mem 5 used" in md2
