from greenlight.sim import ACTIONS, ROOT_CAUSES, SCENARIOS, World


def test_scenarios_consistent():
    assert len(SCENARIOS) == 15 and "update_config" in ACTIONS
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
