"""Tests for the LLM adapter (no network calls are made)."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from countergap.adapters.llm import DeepSeekClient, LLMError, extract_json_object


def test_deepseek_client_requires_key(monkeypatch):
    # Simulate "no key anywhere": block the .env loader too.
    monkeypatch.setattr("countergap.adapters.llm.get_env", lambda key, default=None: default)
    with pytest.raises(LLMError, match="DEEPSEEK_API_KEY"):
        DeepSeekClient(api_key="")


def test_deepseek_client_uses_explicit_key():
    client = DeepSeekClient(api_key="sk-test", model="deepseek-chat", base_url="https://example.test/v1/chat/completions")
    assert client.api_key == "sk-test"
    assert client.model == "deepseek-chat"


def test_extract_json_object_plain():
    assert extract_json_object('{"gap": "x"}') == {"gap": "x"}


def test_extract_json_object_fenced():
    assert extract_json_object('```json\n{"gap": "x"}\n```') == {"gap": "x"}


def test_extract_json_object_with_prose():
    assert extract_json_object('Sure! Here is the JSON: {"gap": "x", "n": 2} hope it helps') == {
        "gap": "x", "n": 2,
    }


def test_extract_json_object_rejects_garbage():
    with pytest.raises(LLMError):
        extract_json_object("no json here")


def test_deepseek_complete_builds_request_and_parses():
    client = DeepSeekClient(
        api_key="sk-test",
        model="deepseek-chat",
        base_url="https://example.test/v1/chat/completions",
    )
    fake_response = mock.Mock()
    fake_response.read.return_value = json.dumps({
        "choices": [{"message": {"content": "{\"gap\": \"hello\"}"}}],
    }).encode("utf-8")
    fake_context = mock.MagicMock()
    fake_context.__enter__.return_value = fake_response

    with mock.patch("urllib.request.urlopen", return_value=fake_context) as urlopen:
        result = client.complete("sys", "usr", temperature=0.5, max_tokens=64)

    assert result == '{"gap": "hello"}'
    request = urlopen.call_args.args[0]
    assert request.method == "POST"
    sent = json.loads(request.data.decode("utf-8"))
    assert sent["model"] == "deepseek-chat"
    assert sent["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]
    assert sent["temperature"] == 0.5
    assert request.headers["Authorization"] == "Bearer sk-test"
