"""The provenance gate, exercised offline with a fake memory and a scripted LLM.

Scenario s15 looks like s02 (payments down right after a deploy). Memory says "last time it was a
bad config deploy and rollback fixed it". The scripted agent tries to reuse that fix after probing
only the vendor, is rejected by the provenance gate, probes the blamed service, finds the 401
invalid_api_key, and submits the real cause. No network.
"""

from pathlib import Path

from test_agent_offline import FakeLLM, _tc

from greenlight.agent import VARIANTS, Investigator
from greenlight.memory import HindsightMemory, MemoryHit
from greenlight.sim import SCENARIOS
from greenlight.tracing import load_trace

S02_TAGS = [
    "incident:s02_bad_config_deploy",
    "root_cause:bad_config_deploy",
    "service:payments-api",
    "action:rollback_deploy",
    "verified:yes",
    "resolved:yes",
    "harm:no",
]


class FakeMemory:
    """Same surface as HindsightMemory, no server."""

    bank_id = "fake-bank"

    def __init__(self):
        self.ordinal = 0
        self.retained = []
        self.queries = []

    def brief(self, alert, changes, error_lines=None):
        self.queries.append(("brief", alert["message"]))
        return [
            MemoryHit(
                text="Incident s02: payments-api charge_failed 100% right after a deploy; root cause "
                "bad_config_deploy; rollback_deploy on payments-api resolved it.",
                type="world",
                when="2026-07-24T09:10:00+00:00",
                score=1.1,
                tags=S02_TAGS,
            )
        ]

    def recall(self, query):
        self.queries.append(("recall", query))
        return self.brief({"message": query}, [])

    format_hits = staticmethod(HindsightMemory.format_hits)

    def remember(self, scenario, verdict, probes, meta, when=None):
        rec = {"incident": scenario.id, "verified": meta["verified"], "harm": bool(meta["harm_done"])}
        self.retained.append(rec)
        self.ordinal += 1
        return rec


ROLLBACK = dict(
    root_cause="bad_config_deploy",
    service="payments-api",
    action="rollback_deploy",
    target="payments-api",
    confidence=0.8,
    summary="same as last time, roll back 2.16.0",
    evidence=["memory: s02 was fixed by rollback"],
    report_markdown="# rollback",
)
TRUTH = dict(
    root_cause="secret_rotation",
    service="payments-api",
    action="update_config",
    target="payments-api",
    confidence=0.9,
    summary="paygate 401 invalid_api_key: process holds revoked key v7 after rotation",
    evidence=["http probe payments-api: paygate=FAIL 401 invalid_api_key key_version=v7"],
    report_markdown="# secret rotation",
)


def test_provenance_gate_blocks_remembered_fix_until_reprobed(tmp_path: Path):
    script = [
        ("", [_tc(1, "get_alert")]),
        ("", [_tc(2, "run_probe", kind="http", target="api.paygate.example")]),
        ("", [_tc(3, "submit_verdict", **ROLLBACK)]),  # verification gate: http ran -> ok
        #                                                provenance gate: wrong target -> REJECT
        ("", [_tc(4, "run_probe", kind="http", target="payments-api")]),
        ("", [_tc(5, "submit_verdict", **TRUTH)]),
    ]
    llm = FakeLLM(script)
    mem = FakeMemory()
    inv = Investigator(VARIANTS["v5_memory"], llm, tmp_path, memory=mem)
    out = inv.run(SCENARIOS["s15_secret_rotation_lookalike"])

    # the kickoff message carried the recalled incident, marked as unverified for this incident
    kickoff = llm.seen[0]["content"]
    assert "Recalled incidents" in kickoff and "s02_bad_config_deploy" in kickoff
    assert "UNVERIFIED" in kickoff or "unverified" in kickoff

    # the remembered fix was challenged exactly once, then the fresh verdict went through
    m = out.meta
    assert m["memory_hits"] == 1
    assert m["memory_rejections"] == 1
    assert m["memory_checks"][0]["accepted"] is False
    assert "RECALLED, NOT VERIFIED" in m["memory_checks"][0]["reason"]
    assert out.verdict.root_cause == "secret_rotation"
    assert out.verdict.action == "update_config"
    assert m["verified"] is True and m["resolved"] is True and not m["harm_done"]

    # the LLM saw the rejection as a tool result, so the loop closed on the model side
    rejection = llm.seen[3]
    assert rejection["role"] == "tool" and "RECALLED, NOT VERIFIED" in rejection["content"]

    # the closed incident was retained, with its provenance
    assert mem.retained == [{"incident": "s15_secret_rotation_lookalike", "verified": True, "harm": False}]

    # and all of it is in the trace
    ev = list(load_trace(Path(m["trace"])))
    signals = [(e.get("source"), e.get("signal")) for e in ev if e["type"] == "feedback"]
    assert ("hindsight_memory", "recall") in signals
    assert ("provenance_gate", "rejected") in signals
    assert ("hindsight_memory", "retain") in signals


def test_memory_variant_requires_memory():
    import pytest

    with pytest.raises(ValueError):
        Investigator(VARIANTS["final_memory"], FakeLLM([]), Path("/tmp"))
