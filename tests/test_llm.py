import json

from greenlight import llm as llm_mod
from greenlight.llm import LLM, LLMResponse


def test_cache_roundtrip_and_replay_only(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_mod, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    client = LLM(provider="gemini", model="gemini-3.7-flash", fallback=None)
    msgs = [{"role": "user", "content": "hi"}]
    key = LLM._cache_key(client.model, msgs, None, 0.0, 4096)
    d = {
        "text": "hello",
        "tool_calls": [{"id": "c1", "name": "f", "arguments": {"a": 1}}],
        "stop_reason": "tool_calls",
        "input_tokens": 3,
        "output_tokens": 2,
        "latency_ms": 5,
        "model": "gemini-3.7-flash",
        "provider": "gemini",
        "raw_message": {"role": "assistant", "content": "hello"},
    }
    (tmp_path / f"{key}.json").write_text(json.dumps(d))
    r = client.chat(msgs)
    assert isinstance(r, LLMResponse) and r.cached and r.text == "hello"
    assert r.tool_calls[0].name == "f" and r.tool_calls[0].arguments == {"a": 1}
    assert client.stats()["cache_hits"] == 1 and client.stats()["input_tokens"] == 3
    assert r.would_be_cost_usd > 0 and client.stats()["actual_cost_usd"] == 0.0

    replay = LLM(provider="gemini", model="gemini-3.7-flash", fallback=None, replay_only=True)
    try:
        replay.chat([{"role": "user", "content": "not cached"}])
        raise AssertionError("expected replay-only error")
    except RuntimeError as e:
        assert "replay-only" in str(e)


def test_cache_key_is_order_insensitive_for_dict_keys():
    a = LLM._cache_key("m", [{"role": "user", "content": "x"}], [{"b": 1, "a": 2}], 0)
    b = LLM._cache_key("m", [{"content": "x", "role": "user"}], [{"a": 2, "b": 1}], 0)
    assert a == b
