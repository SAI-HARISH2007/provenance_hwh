"""The memory primitives, without a memory server: how a recalled hit is read (`MemoryHit` tags,
which the provenance gate depends on) and how it is aged out (`filter_by_age`). The gate itself
is exercised end to end in `test_memory_offline.py`.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from greenlight.common import Verdict
from greenlight.memory import (
    HindsightMemory,
    MemoryHit,
    _env_int,
    _with_retries,
    filter_by_age,
    hits_to_json,
    incident_time,
)
from greenlight.sim import SCENARIOS

NOW = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

S02_TAGS = [
    "incident:s02_bad_config_deploy",
    "root_cause:bad_config_deploy",
    "service:payments-api",
    "action:rollback_deploy",
    "verified:yes",
    "resolved:yes",
    "harm:no",
]


def _hit(when: str, **kw) -> MemoryHit:
    return MemoryHit(text=kw.pop("text", f"incident {when}"), type="world", when=when,
                     score=kw.pop("score", 1.0), **kw)


# --------------------------------------------------------------------------- tag parsing
def test_tags_are_read_by_key_not_by_text():
    """The provenance gate trusts `root_cause:`/`action:`/`incident:` tags, not the prose.

    The text here claims a totally different root cause than the tags. The tags win, because a
    retained record's provenance is written by code and a memory server's paraphrase is not
    evidence.
    """
    hit = MemoryHit(
        text="payments-api was down and I think it was the vendor key",
        type="world",
        when="2026-07-24T09:10:00+00:00",
        score=0.9,
        tags=S02_TAGS,
    )
    assert hit.incident_id == "s02_bad_config_deploy"
    assert hit.root_cause == "bad_config_deploy"
    assert hit.action == "rollback_deploy"
    assert hit.verified is True


def test_missing_and_malformed_tags_read_as_absent_not_as_guesses():
    bare = _hit("2026-08-01T00:00:00+00:00")
    assert bare.tags == []
    assert bare.incident_id is None and bare.root_cause is None and bare.action is None
    assert bare.verified is False

    # only `verified:no` is present, so nothing else is known and it is explicitly unverified
    partial = _hit("2026-08-01T00:00:00+00:00", tags=["verified:no", "harm:yes"])
    assert partial.verified is False and partial.root_cause is None

    # a value containing a colon is split once, not on every colon
    colony = _hit("2026-08-01T00:00:00+00:00", tags=["incident:s15:hard"])
    assert colony.incident_id == "s15:hard"

    # a key with no value is not a value of ""
    empty = _hit("2026-08-01T00:00:00+00:00", tags=["root_cause:"])
    assert empty.root_cause == ""

    # verified is a yes/no flag; anything else is not a claim of verification
    assert _hit("", tags=["verified:maybe"]).verified is False


def test_line_labels_the_source_the_date_and_the_verification():
    hit = MemoryHit(
        text="rollback fixed it", type="world", when="2026-07-24T09:10:00+00:00", score=0.9,
        tags=S02_TAGS,
    )
    assert hit.line() == "- [s02_bad_config_deploy · 2026-07-24 · verified] rollback fixed it"

    unverified = _hit("2026-08-01T09:10:00+00:00", text="probably the deploy", tags=["incident:s17"])
    assert unverified.line() == "- [s17 · 2026-08-01 · UNVERIFIED] probably the deploy"

    # an undated or unlabelled hit is shown as such rather than dropped
    assert "unknown incident" in _hit("", text="vague").line()
    assert "undated" in _hit("", text="vague", tags=["verified:yes"]).line()


# --------------------------------------------------------------------------- age
def test_age_days_reads_dated_undated_and_offset_hits():
    # a plain ISO timestamp, and the same instant written without an offset
    assert _hit("2026-08-01T12:00:00+00:00").age_days(NOW) == 9.0
    assert _hit("2026-08-01T12:00:00").age_days(NOW) == 9.0

    # a bare date is midnight, so it is a day and a half old at noon
    assert _hit("2026-08-09").age_days(NOW) == 1.5

    # +02:00 local time, resolved to the same instant before differencing
    assert round(_hit("2026-08-09T13:30:00+02:00").age_days(NOW), 6) == 1.020833

    # nothing to parse means no age, not an age of zero
    assert _hit("").age_days(NOW) is None
    assert _hit("   ").age_days(NOW) is None
    assert _hit("sometime last tuesday").age_days(NOW) is None


def test_age_days_accepts_a_naive_reference_clock():
    naive_now = datetime(2026, 8, 10, 12, 0)
    assert _hit("2026-08-01T12:00:00+00:00").age_days(naive_now) == 9.0


def test_filter_by_age_drops_stale_and_keeps_undated():
    fresh = _hit("2026-08-08T12:00:00+00:00")
    stale = _hit("2026-06-01T12:00:00+00:00")
    undated = _hit("")
    hits = [fresh, stale, undated]

    kept = filter_by_age(hits, 30, NOW)
    assert kept == [fresh, undated]
    assert [h.text for h in kept] == [fresh.text, undated.text]

    # a limit of 0 means no limit: even the stale hit survives, with or without an explicit now
    assert filter_by_age(hits, 0, NOW) == hits
    assert filter_by_age(hits, 0) == hits


def test_filter_by_age_boundary_and_negative_limits():
    exactly_30 = _hit("2026-07-11T12:00:00+00:00")
    just_over = _hit("2026-07-11T11:59:59+00:00")
    assert filter_by_age([exactly_30], 30, NOW) == [exactly_30]
    assert filter_by_age([just_over], 30, NOW) == []

    # a negative limit is not a limit either, rather than an error or an empty recall
    assert filter_by_age([just_over], -1, NOW) == [just_over]

    # the default reference is "now", so a hit from an hour ago survives a 1-day limit
    recent = _hit((datetime.now(UTC) - timedelta(hours=1)).isoformat())
    assert filter_by_age([recent], 1) == [recent]
    # ... and the input list is never mutated
    original = [exactly_30, just_over]
    kept = filter_by_age(original, 1, NOW)
    assert kept == [] and original == [exactly_30, just_over]


def test_incident_dates_are_days_apart_so_recall_spans_weeks():
    assert incident_time(0) == datetime(2026, 7, 6, 2, 10, tzinfo=UTC)
    assert incident_time(1) - incident_time(0) >= timedelta(days=9)
    assert incident_time(3) - incident_time(0) >= timedelta(days=27)  # "six weeks ago" is literal


# --------------------------------------------------------------------------- rendering
def _recall_hit(inc: str, score: float, **tags: str) -> MemoryHit:
    return MemoryHit(
        text=f"{inc}: something happened",
        type="world",
        when="2026-07-24T09:10:00+00:00",
        score=score,
        tags=[f"incident:{inc}", *[f"{k}:{v}" for k, v in tags.items()]],
    )


def test_format_hits_groups_by_incident_strongest_first():
    hits = [
        _recall_hit("s04", 0.9, root_cause="disk_full", action="free_disk_space", verified="yes"),
        _recall_hit("s02", 0.5, root_cause="bad_config_deploy", action="rollback_deploy",
                    verified="no"),
    ]
    out = HindsightMemory.format_hits(hits)
    assert out.index("s04") < out.index("s02")
    assert "claims about the PAST" in out and "unverified for THIS incident" in out
    assert "strong match" in out and "WEAK match" not in out

    # a mid-score incident reads as a plain "match", not a strong one
    mid = HindsightMemory.format_hits([_recall_hit("s02", 0.4)])
    assert "(match 0.40)" in mid
    assert "(WEAK match" in HindsightMemory.format_hits([_recall_hit("s02", 0.2)])

    # and an untagged recall is still shown, with its unknowns spelled out
    unknown = HindsightMemory.format_hits([MemoryHit(text="mystery", type="world", when="", score=0.3)])
    assert "cause ?" in unknown and "fix ?" in unknown and "undated" in unknown


def test_format_hits_says_so_when_memory_is_empty():
    out = HindsightMemory.format_hits([])
    assert "no similar incident in memory" in out and "first time you see this" in out


def test_format_hits_respects_the_max_incidents_knob(monkeypatch):
    hits = [
        _recall_hit("s04", 0.9, root_cause="disk_full", action="free_disk_space", verified="yes"),
        _recall_hit("s02", 0.8, root_cause="bad_config_deploy", action="rollback_deploy",
                    verified="yes"),
        _recall_hit("s12", 0.7, root_cause="clock_skew", action="sync_clock", verified="yes"),
    ]
    assert all(inc in HindsightMemory.format_hits(hits) for inc in ("s04", "s02", "s12"))

    monkeypatch.setenv("HINDSIGHT_MAX_INCIDENTS", "2")
    out = HindsightMemory.format_hits(hits)  # default limit follows the environment
    assert "s04" in out and "s02" in out and "s12" not in out

    # an explicit argument still wins, and junk in the env falls back to the default of 3
    assert "s12" in HindsightMemory.format_hits(hits, limit=3)
    monkeypatch.setenv("HINDSIGHT_MAX_INCIDENTS", "not-a-number")
    assert all(inc in HindsightMemory.format_hits(hits) for inc in ("s04", "s02", "s12"))


def test_group_by_incident_orders_incidents_and_facts_by_strength():
    hits = [
        _recall_hit("s04", 0.31),
        _recall_hit("s02", 0.9),
        _recall_hit("s04", 0.8),
    ]
    groups = HindsightMemory.group_by_incident(hits)
    assert [inc for inc, _ in groups] == ["s02", "s04"]
    assert [h.score for h in groups[1][1]] == [0.8, 0.31]

    # hits with no incident tag are bucketed, never dropped
    unlabelled = HindsightMemory.group_by_incident([_hit("")])
    assert [inc for inc, _ in unlabelled] == ["unknown"]


def test_hits_to_json_caps_the_trace_payload():
    hits = [_hit("2026-08-01T00:00:00+00:00", text="x" * 900) for _ in range(20)]
    rows = json.loads(hits_to_json(hits, limit=3))
    assert len(rows) == 3
    assert all(len(r["text"]) == 300 for r in rows)
    assert rows[0]["score"] == 1.0 and rows[0]["type"] == "world"  # asdict fields survive


# --------------------------------------------------------------------------- the server calls
# A stand-in for hindsight_client.Hindsight. Same method surface, no server, no network.
class FakeClient:
    def __init__(self, results=(), create_bank_error=None):
        self.results = list(results)
        self.create_bank_error = create_bank_error
        self.calls = []

    def create_bank(self, **kw):
        self.calls.append(("create_bank", kw))
        if self.create_bank_error:
            raise self.create_bank_error

    def delete_bank(self, **kw):
        self.calls.append(("delete_bank", kw))

    def recall(self, **kw):
        self.calls.append(("recall", kw))
        return type("Res", (), {"results": self.results})()

    def retain(self, **kw):
        self.calls.append(("retain", kw))
        return {}

    def close(self):
        self.calls.append(("close", {}))


def _result(text, score, when="2026-07-24T09:10:00+00:00", tags=(), type_="world"):
    """A memory-server recall result, as the client hands it over."""
    return type(
        "R",
        (),
        {
            "text": text,
            "type": type_,
            "occurred_start": when,
            "scores": type("S", (), {"final": score})(),
            "tags": list(tags),
        },
    )()


def _memory(client, **kw):
    """A HindsightMemory wired to `client`, skipping __init__ so no client is even constructed."""
    mem = HindsightMemory.__new__(HindsightMemory)
    mem.client = client
    mem.bank_id = "test-bank"
    mem.min_score = kw.get("min_score", 0.3)
    mem.max_incidents = kw.get("max_incidents", 3)
    mem.max_age_days = kw.get("max_age_days", 0)
    mem.ordinal = 0
    mem.retained = []
    return mem


def test_with_retries_backs_off_only_on_transient_failures(monkeypatch):
    slept = []
    monkeypatch.setattr("greenlight.memory.time.sleep", slept.append)

    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("503 Service Unavailable")
        return "ok"

    assert _with_retries(flaky) == "ok"
    assert len(calls) == 3 and slept == [2.0, 4.0]  # exponential, starting at 2s

    # a permanent failure is not retried at all
    def broken():
        raise RuntimeError("bank_id must be a string")

    try:
        _with_retries(broken)
    except RuntimeError as e:
        assert "must be a string" in str(e)
    else:
        raise AssertionError("a permanent failure must propagate")
    assert slept == [2.0, 4.0]

    # a transient failure that never clears still raises, after the attempt budget
    monkeypatch.setattr("greenlight.memory.time.sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="429"):
        _with_retries(lambda: (_ for _ in ()).throw(RuntimeError("429 rate limited")))


def test_recall_filters_on_score_sorts_and_carries_tags():
    client = FakeClient(
        results=[
            _result("weak look-alike", 0.11, tags=["incident:s04"]),
            _result("the disk filled up", 0.95, tags=["incident:s04", "root_cause:disk_full",
                                                      "action:free_disk_space", "verified:yes"]),
            _result("also relevant", 0.62, tags=["incident:s13"]),
        ]
    )
    mem = _memory(client)
    hits = mem.recall("disk full on postgres")

    assert [h.text for h in hits] == ["the disk filled up", "also relevant"]  # sorted, 0.11 dropped
    assert hits[0].incident_id == "s04" and hits[0].root_cause == "disk_full"
    assert hits[0].verified and hits[0].when.startswith("2026-07-24")

    # the recall call itself asks for the memory types and the bank we were given
    call = next(c for c in client.calls if c[0] == "recall")[1]
    assert call["bank_id"] == "test-bank"
    assert call["types"] == ["world", "experience", "observation"]
    assert "disk full" in call["query"]

    # an explicit min_score and an explicit age limit both narrow the same result set
    assert len(mem.recall("q", min_score=0.9)) == 1
    assert mem.recall("q", min_score=0.99) == []

    recent = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    stale = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    aged = _memory(FakeClient(results=[_result("recent", 0.9, when=recent),
                                      _result("stale", 0.9, when=stale),
                                      _result("undated", 0.9, when="")]),
                   max_age_days=30)
    assert [h.text for h in aged.recall("q")] == ["recent", "undated"]  # undated is kept
    assert _memory(FakeClient(results=[_result("stale", 0.9, when=stale)])).recall("q")


def test_recall_survives_a_server_that_returns_nothing():
    assert _memory(FakeClient(results=[])).recall("q") == []
    # a result with no usable score reads as 0.0 rather than raising on a missing attribute
    bare = _memory(FakeClient(results=[_result("no score", None)]))
    assert bare.recall("q") == []
    assert bare.recall("q", min_score=0.0)[0].text == "no score"


def test_brief_asks_two_phrasings_and_keeps_the_best_score_per_fact():
    strong = _result("payments down after a deploy", 0.9, tags=["incident:s02"])
    weak = _result("payments down after a deploy", 0.3, tags=["incident:s02"])
    client = FakeClient(results=[weak, strong, _result("unrelated", 0.2)])
    mem = _memory(client)

    alert = {"service": "payments-api", "severity": "P1", "message": "charge_failed 100%"}
    changes = [{"kind": "deploy", "service": "payments-api", "summary": "rollout 2.16.0"}]
    hits = mem.brief(alert, changes, error_lines=["paygate 401 invalid_api_key"])

    queries = [c[1]["query"] for c in client.calls if c[0] == "recall"]
    assert len(queries) == 2
    assert "charge_failed 100%" in queries[0] and "rollout 2.16.0" in queries[0]  # alert + changes
    assert "invalid_api_key" in queries[1]  # ... and the alerting service's own error lines

    # the same fact recalled twice is merged on its best score, not shown twice
    assert [h.text for h in hits] == ["payments down after a deploy"]
    assert hits[0].score == 0.9

    # with no error lines there is only the one phrasing
    client2 = FakeClient(results=[])
    assert _memory(client2).brief(alert, []) == []
    assert len([c for c in client2.calls if c[0] == "recall"]) == 1


def test_ensure_bank_tolerates_an_existing_bank_but_not_a_real_failure():
    ok = _memory(FakeClient())
    ok.ensure_bank()
    bank_kw = ok.client.calls[0][1]
    assert bank_kw["bank_id"] == "test-bank"
    assert bank_kw["disposition"]["skepticism"] == 5  # doubt memory by default
    assert "on-call incident investigator" in bank_kw["mission"]

    for already in (RuntimeError("409 bank already exists"), RuntimeError("Bank Already Exists")):
        _memory(FakeClient(create_bank_error=already)).ensure_bank()  # must not raise

    try:
        _memory(FakeClient(create_bank_error=RuntimeError("401 unauthorized"))).ensure_bank()
    except RuntimeError as e:
        assert "unauthorized" in str(e)
    else:
        raise AssertionError("an auth failure must not be swallowed")


def test_remember_writes_one_record_with_provenance_tags():
    s = SCENARIOS["s15_secret_rotation_lookalike"]
    v_ok = Verdict(root_cause="secret_rotation", service="payments-api", action="update_config",
                   target="payments-api", summary="revoked key v7")
    v_bad = Verdict(root_cause="bad_config_deploy", service="payments-api",
                    action="rollback_deploy", target="payments-api", summary="")

    # a verified incident whose fix resolved it
    client = FakeClient()
    mem = _memory(client)
    rec = mem.remember(s, v_ok, ["http payments-api: 401 invalid_api_key"], {
        "verified": True, "resolved": True, "harm_done": False,
        "actions_executed": [["update_config", "payments-api"]],
        "approval": {"decision": "approved"},
        "remediation_effect": {"effect": "charges succeed again"}})
    kw = client.calls[-1][1]
    assert kw["bank_id"] == "test-bank" and kw["context"].startswith("on-call incident record")
    assert "invalid_api_key" in kw["content"] and "RESOLVED the incident" in kw["content"]
    assert "Verified root cause: secret_rotation" in kw["content"]
    assert kw["metadata"] == {t.split(":", 1)[0]: t.split(":", 1)[1] for t in kw["tags"]}
    assert kw["timestamp"] == incident_time(0)

    # the tags are the provenance the gate and the recall panel read back
    for tag in ("incident:s15_secret_rotation_lookalike", "root_cause:secret_rotation",
                "service:payments-api", "action:update_config", "verified:yes", "resolved:yes",
                "harm:no"):
        assert tag in kw["tags"]
    assert rec["incident"] == "s15_secret_rotation_lookalike" and rec["chars"] == len(kw["content"])
    assert mem.ordinal == 1  # the next incident gets a later date

    # an executed fix that did not help is retained as negative evidence, not as a success
    for effect, harm, resolved, expected in (
        ("duplicate charges", True, False, "CAUSED HARM"),
        ("error rate unchanged", False, False, "did NOT resolve"),
    ):
        c = FakeClient()
        m = _memory(c)
        r = m.remember(s, v_bad, [], {"verified": False, "harm_done": harm, "resolved": resolved,
                                      "actions_executed": [["rollback_deploy", "payments-api"]],
                                      "approval": {"decision": "approved"},
                                      "remediation_effect": {"effect": effect}})
        k = c.calls[-1][1]
        assert expected in k["content"] and effect in k["content"]
        assert "UNVERIFIED root cause" in k["content"]
        assert "no probes were run" in k["content"]
        # only a harmful fix carries the "do not repeat" instruction
        assert ("Do not repeat it" in k["content"]) is harm
        assert "verified:no" in k["tags"] and "resolved:no" in k["tags"]
        assert ("harm:yes" in k["tags"]) is harm
        assert r["chars"] == len(k["content"])

    # an unapproved, unexecuted remediation says so rather than claiming an outcome
    c3 = FakeClient()
    _memory(c3).remember(s, v_ok, ["http payments-api: 401"], {"verified": True})
    k3 = c3.calls[-1][1]
    assert "not executed" in k3["content"] and "approval: skipped" in k3["content"]

    # each retained record is dated weeks after the last, which is what makes recall span weeks
    assert mem.remember(s, v_ok, [], {})["when"] == incident_time(1).strftime("%Y-%m-%d %H:%M UTC")


def test_reset_clears_the_bank_and_survives_a_delete_failure():
    client = FakeClient()
    mem = _memory(client)
    mem.ordinal = 5
    mem.retained = [{"incident": "s01"}]
    mem.reset()
    assert mem.ordinal == 0 and mem.retained == []
    assert [c[0] for c in client.calls] == ["delete_bank", "create_bank"]

    class NoDelete(FakeClient):
        delete_bank = None  # older client builds: reset must skip straight to create_bank

    mem2 = _memory(NoDelete())
    mem2.reset()
    assert [c[0] for c in mem2.client.calls] == ["create_bank"]


def test_close_is_best_effort():
    client = FakeClient()
    _memory(client).close()
    assert client.calls == [("close", {})]

    class BadClose(FakeClient):
        def close(self):
            raise RuntimeError("already closed")

    _memory(BadClose()).close()  # must not raise


def test_env_knobs_are_read_with_a_safe_fallback(monkeypatch):
    monkeypatch.delenv("HINDSIGHT_MAX_INCIDENTS", raising=False)
    assert _env_int("HINDSIGHT_MAX_INCIDENTS", 3) == 3
    monkeypatch.setenv("HINDSIGHT_MAX_INCIDENTS", "7")
    assert _env_int("HINDSIGHT_MAX_INCIDENTS", 3) == 7
    for junk in ("", "three", "3.5", " "):
        monkeypatch.setenv("HINDSIGHT_MAX_INCIDENTS", junk)
        assert _env_int("HINDSIGHT_MAX_INCIDENTS", 3) == 3
