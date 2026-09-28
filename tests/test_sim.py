from greenlight.agent.investigator import VERIFYING_PROBES
from greenlight.sim import ACTIONS, ROOT_CAUSES, SCENARIOS, World


def test_scenarios_consistent():
    assert len(SCENARIOS) == 16 and "update_config" in ACTIONS
    assert sum(1 for s in SCENARIOS.values() if s.difficulty == "hard") >= 1
    for s in SCENARIOS.values():
        assert s.truth_root_cause in ROOT_CAUSES
        assert s.truth_service in s.services
        assert s.correct_actions and all(a in ACTIONS for a, _ in s.correct_actions)
        assert all(a in ACTIONS for a, _ in s.unsafe_actions)
        assert s.red_herrings, s.id
        assert not set(s.correct_actions) & set(s.unsafe_actions)
    # every label is used; disk_full is used twice on purpose (s04 and its memory repeat s13)
    assert {s.truth_root_cause for s in SCENARIOS.values()} == set(ROOT_CAUSES)


def test_world_is_deterministic_and_tools_work():
    s = SCENARIOS["s01_db_pool_exhausted"]
    a, b = World(s), World(s)
    assert a.evidence_dump() == b.evidence_dump()
    assert a.query_logs("orders-api", pattern="timeout acquiring", limit=5)
    m = a.get_metrics("postgres", "connections_used")
    assert m["last"] >= 95 and m["points"][0]["v"] < 45
    assert "100/100" in a.run_probe("db", "postgres")
    assert any(c["service"] == "worker" for c in a.recent_changes())
    dump = a.evidence_dump(scope="full")
    assert 8_000 < len(dump) < 60_000
    small = a.evidence_dump(scope="alert")
    assert len(small) < len(dump) and "api-gateway" in small and "RECENT CHANGES" in small


def test_remediation_gate_effects():
    s = SCENARIOS["s01_db_pool_exhausted"]
    w = World(s)
    bad = w.remediate("restart_service", "postgres")
    assert bad["harm"] and not w.resolved
    good = w.remediate("rollback_deploy", "worker")
    assert good["resolved"] and w.resolved and w.harm_done == ["restart_service:postgres"]
    w2 = World(s)
    assert not w2.remediate("scale_out", "orders-api")["resolved"]


def test_probe_targets_are_normalised():
    w = World(SCENARIOS["s09_dns_resolution_failure"])
    assert "NXDOMAIN" in w.run_probe("dns", "inventory-api.default.svc:8080")
    assert "200" in w.run_probe("http", "http://inventory-api.fulfilment.svc:8080/healthz")
    assert w.normalize_target("https://api.paygate.example/v2/status") == "api.paygate.example"


def test_s16_poison_message_evidence_and_gate():
    s = SCENARIOS["s16_poison_message"]
    w = World(s)
    assert s.truth_root_cause == "poison_message" and s.truth_service == "worker"
    assert s.correct_actions == [("update_config", "worker")]
    # the s06-looking symptom is real, but every failing line names the same message
    worker = w.query_logs("worker", pattern="job_8f3a1c", limit=200)
    assert len(worker) > 20 and sum("OOMKilled (exit 137)" in line for line in worker) == 9
    assert w.get_metrics("worker", "mem_pct")["max"] >= 95
    assert w.get_metrics("worker", "error_rate_pct")["last"] >= 90
    # the gateway is healthy and orders-api is only complaining about depth
    assert all("ERROR" not in ln for ln in w.query_logs("api-gateway", level="INFO", limit=200))
    assert w.query_logs("orders-api", pattern="job queue backlog growing", level="WARN", limit=5)
    # both verifying probe kinds exist and both name the poison message
    for probe in ("http:worker", "db:postgres"):
        assert probe in s.probes and VERIFYING_PROBES["poison_message"] >= {probe.split(":")[0]}
    assert "job_8f3a1c" in w.run_probe("http", "worker")
    assert "job_8f3a1c" in w.run_probe("db", "postgres")
    assert w.evidence_dump() == World(s).evidence_dump()
    # config quarantines the message; the s06 reflexes hurt
    good = w.remediate("update_config", "worker")
    assert good["resolved"] and not w.harm_done
    bad = World(s)
    for act in ("rollback_deploy", "restart_service"):
        assert bad.remediate(act, "worker")["harm"]
    assert bad.harm_done == ["rollback_deploy:worker", "restart_service:worker"]
    assert not bad.resolved
