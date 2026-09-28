import json
from pathlib import Path

from greenlight.tracing import TraceWriter, load_trace, new_run_id, redact


def test_run_id_format():
    rid = new_run_id("Baseline Run #1")
    assert rid.endswith("_baseline-run-1")
    assert rid[8] == "T" and rid[15] == "Z"


def test_redaction():
    s = "key sk-ant-api03-abcdefghijklmnop and ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ and api_key=supersecret123"
    r = redact(s)
    assert "abcdefghijklmnop" not in r and "ABCDEFGHIJKLMNOPQRSTUVWXYZ" not in r
    assert "supersecret123" not in r and "[REDACTED]" in r


def test_round_trip_all_event_types(tmp_path: Path):
    rid = new_run_id("test")
    with TraceWriter(rid, root=tmp_path) as tw:
        tw.run_start(
            problem_id="case-01",
            agent_version="abc123",
            model="m",
            params={"temperature": 0},
            tools=["bash"],
            sandbox="docker",
            prompt_hashes={"system": "deadbeef"},
        )
        tw.instruction(role="system", name="system.md", content="You are helpful. token=hunter22")
        tw.llm_request(n_messages=2, tools_offered=["bash"], input_tokens=10)
        tw.llm_response(
            stop_reason="tool_use",
            text="calling",
            tool_calls=[{"id": "t1", "name": "bash", "input": {"cmd": "ls"}}],
            output_tokens=5,
            latency_ms=100,
        )
        tw.tool_call(tool_call_id="t1", name="bash", input={"cmd": "ls"})
        seq = tw.tool_result(
            tool_call_id="t1",
            ok=False,
            output="x" * 10_000,
            duration_ms=3,
            exit_code=1,
            stderr="boom",
        )
        tw.error(where="tool", kind="NonZeroExit", message="exit 1", recoverable=True)
        tw.retry(of=seq, attempt=2, strategy="reprompt", reason="exit 1")
        tw.feedback(source="test", signal="fail", detail="3 failed")
        tw.decision(summary="pick", options_considered=["a", "b"], chosen="a", rationale="cheaper")
        tw.human_checkpoint(question="apply patch?", decision="approved")
        tw.run_end(status="success", final_output="done", score=1.0, total_tokens=15)

    events = list(load_trace(tmp_path / f"{rid}.jsonl"))
    types = [e["type"] for e in events]
    assert types == [
        "run_start",
        "instruction",
        "llm_request",
        "llm_response",
        "tool_call",
        "tool_result",
        "error",
        "retry",
        "feedback",
        "decision",
        "human_checkpoint",
        "run_end",
    ]
    assert [e["seq"] for e in events] == list(range(1, 13))
    assert all(e["run_id"] == rid for e in events)
    # secret in instruction redacted
    assert "hunter22" not in json.dumps(events)
    # large output spilled to artifact with head kept
    tr = events[5]
    assert tr["output_ref"] and len(tr["output"]) == 500
    assert (tmp_path / tr["output_ref"]).read_text() == "x" * 10_000
    assert events[-1]["wall_ms"] >= 0
