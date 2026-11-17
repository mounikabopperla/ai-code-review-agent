import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from backend.api import main
from backend.llm import generator
from backend.storage import answer_cache


@pytest.fixture(autouse=True)
def isolated_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(answer_cache, "DATABASE_PATH", tmp_path / "answers.db")


def fake_model(monkeypatch, stream):
    model = SimpleNamespace(generate_content_stream=stream)
    monkeypatch.setattr(generator, "get_client", lambda: SimpleNamespace(models=model))


def test_stream_delivers_first_fragment_before_generation_finishes(monkeypatch):
    steps = []
    def generate(**kwargs):
        steps.append("first")
        yield SimpleNamespace(text="Hello ")
        steps.append("second")
        yield SimpleNamespace(text="world")
    fake_model(monkeypatch, generate)
    stream = generator.stream_gemini("prompt", "repo:commit")
    assert next(stream) == "Hello "
    assert steps == ["first"]
    assert "".join(stream) == "world"
    assert steps == ["first", "second"]


def test_repeat_answer_skips_model_call(monkeypatch):
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return iter([SimpleNamespace(text="Cached answer")])
    fake_model(monkeypatch, generate)
    assert generator.ask_gemini("prompt", "repo:commit") == "Cached answer"
    assert generator.ask_gemini("prompt", "repo:commit") == "Cached answer"
    assert len(calls) == 1
    generator.ask_gemini("prompt", "repo:changed_commit")
    generator.ask_gemini("changed prompt", "repo:changed_commit")
    assert len(calls) == 3


def test_model_change_invalidates_cache(monkeypatch):
    assert answer_cache.cache_key("p", "model1", "r") != answer_cache.cache_key("p", "model2", "r")


def test_failed_partial_response_is_not_cached(monkeypatch):
    def generate(**kwargs):
        yield SimpleNamespace(text="Partial")
        raise RuntimeError("upstream failure")
    fake_model(monkeypatch, generate)
    with pytest.raises(RuntimeError):
        list(generator.stream_gemini("prompt"))
    key = answer_cache.cache_key("prompt", generator.settings.gemini_model)
    assert answer_cache.get_answer(key) is None


def test_expired_answers_are_not_returned(monkeypatch):
    monkeypatch.setattr(answer_cache.time, "time", lambda: 100)
    answer_cache.save_answer("key", "value")
    assert answer_cache.get_answer("key") == "value"
    monkeypatch.setattr(answer_cache.time, "time", lambda: 100 + answer_cache.TTL_SECONDS + 1)
    assert answer_cache.get_answer("key") is None


def test_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(answer_cache, "MAX_ENTRIES", 2)
    for i in range(3):
        monkeypatch.setattr(answer_cache.time, "time", lambda i=i: i)
        answer_cache.save_answer(str(i), str(i))
    assert answer_cache.get_answer("0") is None
    assert answer_cache.get_answer("2") == "2"


def test_cancelled_generator_does_not_save_partial_answer(monkeypatch):
    fake_model(monkeypatch, lambda **kwargs: iter([SimpleNamespace(text="one"), SimpleNamespace(text="two")]))
    stream = generator.stream_gemini("prompt")
    assert next(stream) == "one"
    stream.close()
    assert answer_cache.get_answer(answer_cache.cache_key("prompt", generator.settings.gemini_model)) is None


def test_stream_api_emits_text_then_completion(monkeypatch):
    monkeypatch.setattr(main, "stream_answer_question", lambda *args: iter(["Hello", " world"]))
    response = TestClient(main.app).post("/ask/stream", json={"question": "What?", "repo_path": "https://github.com/a/b"})
    frames = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert frames == [{"type": "delta", "text": "Hello"}, {"type": "delta", "text": " world"}, {"type": "done"}]
    assert response.headers["x-accel-buffering"] == "no"


def test_stream_error_is_explicit_and_redacted(monkeypatch):
    def fail(*args):
        yield "partial"
        raise RuntimeError("private upstream details")
    monkeypatch.setattr(main, "stream_answer_question", fail)
    response = TestClient(main.app).post("/ask/stream", json={"question": "What?", "repo_path": "https://github.com/a/b"})
    assert '"type":"error"' in response.text
    assert "private upstream details" not in response.text
    assert '"type":"done"' not in response.text
