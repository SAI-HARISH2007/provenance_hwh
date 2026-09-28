"""Exercise the investigator loop, verification gate, reviewer and approval checkpoint with a
scripted fake LLM — no network, deterministic. This is what `make test` runs in CI."""

import json
from pathlib import Path

from greenlight.agent import VARIANTS, Investigator
from greenlight.llm import LLMResponse, ToolCall
from greenlight.sim import SCENARIOS
from greenlight.tracing import load_trace


class FakeLLM:
    """Replays a script of responses; records every call. Mimics LLM's public surface."""

    def __init__(self, script):
        self.script = list(script)
        self.model, self.provider, self.temperature = "fake-model", "fake", 0.0
        self.calls = self.cache_hits = self.input_tokens = self.output_tokens = 0
        self.on_event = None
        self.seen = []

    def chat(self, messages, tools=None, max_tokens=4096, **_):
        self.calls += 1
        self.seen.append(messages[-1])
        text, tcs = self.script.pop(0)
        self.input_tokens += 100
        self.output_tokens += 20
        raw = {"role": "assistant", "content": text}
        if tcs:
            raw["tool_calls"] = [
                {
                    "id": t.id,
                    "type": "function",
                    "function": {"name": t.name, "arguments": json.dumps(t.arguments)},
                }
                for t in tcs
            ]
        return LLMResponse(
            text=text,
            tool_calls=tcs,
            stop_reason="tool_calls" if tcs else "stop",
            input_tokens=100,
            output_tokens=20,
            latency_ms=1,
            model=self.model,
            provider=self.provider,
            cached=False,
            raw_message=raw,
        )

    def stats(self):
        return {}


def _tc(i, name, **args):
    return ToolCall(id=f"c{i}", name=name, arguments=args)


VERDICT = dict(
    root_cause="db_connection_pool_exhausted",
    service="worker",
    action="rollback_deploy",
    target="worker",
    confidence=0.9,
    summary="worker holds the pool",
    evidence=["db probe 100/100 held by worker"],
    report_markdown="# Incident\nworker ate the pool",
)


def test_gate_rejects_unverified_then_accepts_and_executes(tmp_path: Path):
    script = [
        ("", [_tc(1, "get_alert"), _tc(2, "recent_changes")]),
        ("", [_tc(3, "query_logs", service="orders-api", pattern="QueuePool")]),
        ("", [_tc(4, "submit_verdict", **VERDICT)]),  # no probe yet -> rejected
        ("", [_tc(5, "run_probe", kind="db", target="postgres")]),
        ("", [_tc(6, "submit_verdict", **VERDICT)]),  # now verified -> accepted
    ]
    llm = FakeLLM(script)
    inv = Investigator(VARIANTS["v2_verify"], llm, trace_root=tmp_path)
    out = inv.run(SCENARIOS["s01_db_pool_exhausted"])
    assert out.verdict.root_cause == "db_connection_pool_exhausted"
    m = out.meta
    assert (
        m["status"] == "success"
        and m["gate_rejections"] == 1
        and m["verified"]
        and m["probes_run"] == 1
    )
    assert m["resolved"] and not m["harm_done"] and m["approval"]["decision"] == "approved"
    ev = list(load_trace(tmp_path / f"{m['run_id']}.jsonl"))
    types = [e["type"] for e in ev]
    assert "human_checkpoint" in types and types.count("feedback") >= 2
    rejected = [e for e in ev if e["type"] == "feedback" and e["source"] == "verification_gate"]
    assert rejected and "VERIFICATION REQUIRED" in rejected[0]["detail"]
    # the model was actually told to verify (feedback loop closed)
    assert any("VERIFICATION REQUIRED" in str(s.get("content")) for s in llm.seen)


def test_reviewer_rejection_feeds_back_and_denied_approval_blocks_execution(tmp_path: Path):
    script = [
        ("", [_tc(1, "run_probe", kind="db", target="postgres")]),
        ("", [_tc(2, "submit_verdict", **VERDICT)]),
        (
            '{"approve": false, "issues": ["no metric shown"], "suggested_checks": ["get_metrics postgres connections_used"], "note": "verify"}',
            [],
        ),
        ("", [_tc(3, "get_metrics", service="postgres", metric="connections_used")]),
        ("", [_tc(4, "submit_verdict", **VERDICT)]),
        ('{"approve": true, "issues": [], "suggested_checks": [], "note": "ok"}', []),
    ]
    llm = FakeLLM(script)
    inv = Investigator(
        VARIANTS["final"],
        llm,
        trace_root=tmp_path,
        approver=lambda v, r, ctx: ("denied", "human denied at terminal"),
    )
    out = inv.run(SCENARIOS["s01_db_pool_exhausted"])
    m = out.meta
    assert (
        m["status"] == "success" and m["gate_rejections"] == 1 and m["reviewer"]["approve"] is True
    )
    assert m["approval"] == {"decision": "denied", "by": "human"}
    assert m["actions_executed"] == [] and not m["resolved"]


def test_unsafe_action_is_recorded_as_harm(tmp_path: Path):
    bad = dict(VERDICT, action="restart_service", target="postgres")
    script = [
        ("", [_tc(1, "run_probe", kind="db", target="postgres")]),
        ("", [_tc(2, "submit_verdict", **bad)]),
    ]
    inv = Investigator(VARIANTS["v2_verify"], FakeLLM(script), trace_root=tmp_path)
    out = inv.run(SCENARIOS["s01_db_pool_exhausted"])
    assert out.meta["harm_done"] == ["restart_service:postgres"] and not out.meta["resolved"]


def test_step_budget_exhaustion_is_a_clean_failure(tmp_path: Path):
    cfg = VARIANTS["v1_tools"]
    script = [("", [_tc(i, "get_alert")]) for i in range(cfg.max_steps)]
    out = Investigator(cfg, FakeLLM(script), trace_root=tmp_path).run(
        SCENARIOS["s03_tls_cert_expired"]
    )
    assert out.meta["status"] == "fail" and out.verdict.root_cause == "unknown"


def test_gate_accepts_dns_probe_on_hostname_for_dns_verdict(tmp_path: Path):
    """Regression for gate v1: a DNS verdict verified by probing the *hostname* must pass."""
    dns_verdict = dict(VERDICT, root_cause="dns_resolution_failure", service="orders-api",
                       action="rollback_deploy", target="inventory-api")
    script = [("", [_tc(1, "run_probe", kind="dns", target="inventory-api.default.svc")]),
              ("", [_tc(2, "submit_verdict", **dns_verdict)])]
    out = Investigator(VARIANTS["v2_verify"], FakeLLM(script), trace_root=tmp_path).run(SCENARIOS["s09_dns_resolution_failure"])
    assert out.meta["gate_rejections"] == 0 and out.meta["verified"] and out.meta["resolved"]


def test_budget_warning_is_injected(tmp_path: Path):
    cfg = VARIANTS["v1_tools"]
    llm = FakeLLM([("", [_tc(i, "get_alert")]) for i in range(cfg.max_steps)])
    Investigator(cfg, llm, trace_root=tmp_path).run(SCENARIOS["s03_tls_cert_expired"])
    assert any("Budget:" in str(m.get("content")) for m in llm.seen)


def test_reviewer_rejection_on_final_attempt_blocks_autonomous_execution(tmp_path: Path):
    """The s09 lesson: when the reviewer still rejects after the retry budget, eval auto-approval
    must NOT execute the action — it is handed to a human instead."""
    bad = dict(VERDICT, root_cause="dns_resolution_failure", action="rollback_deploy", target="orders-api")
    reject = '{"approve": false, "issues": ["rollback does not fix DNS"], "suggested_checks": [], "note": "no"}'
    script = [("", [_tc(1, "run_probe", kind="dns", target="inventory-api.default.svc")]),
              ("", [_tc(2, "submit_verdict", **bad)]), (reject, []),
              ("", [_tc(3, "submit_verdict", **bad)]), (reject, []),
              ("", [_tc(4, "submit_verdict", **bad)]), (reject, [])]
    out = Investigator(VARIANTS["final"], FakeLLM(script), trace_root=tmp_path).run(SCENARIOS["s09_dns_resolution_failure"])
    m = out.meta
    assert m["reviewer_approved"] is False and m["approval"]["decision"] == "denied"
    assert m["actions_executed"] == [] and m["harm_done"] == []
