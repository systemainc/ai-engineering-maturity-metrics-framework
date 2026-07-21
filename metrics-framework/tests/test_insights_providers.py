"""
Provider tests are fully mocked — no real network calls, no real API keys.
Same convention as test_github_adapter.py: patch the session's HTTP method,
assert on what was sent and how the response gets parsed.
"""
from unittest.mock import MagicMock, patch

import pytest

from framework.insights import build_provider
from framework.insights.anthropic_provider import AnthropicProvider
from framework.insights.openai_provider import OpenAIProvider


def _resp(json_body, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body
    m.raise_for_status = MagicMock()
    if status >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return m


def test_anthropic_provider_requires_api_key_env(monkeypatch):
    monkeypatch.delenv("FAKE_ANTHROPIC_KEY", raising=False)
    with pytest.raises(ValueError, match="FAKE_ANTHROPIC_KEY"):
        AnthropicProvider({"model": "claude-x", "api_key_env": "FAKE_ANTHROPIC_KEY"})


def test_anthropic_provider_requires_model():
    with pytest.raises(ValueError, match="model"):
        AnthropicProvider({"api_key_env": "FAKE_ANTHROPIC_KEY"})


def test_anthropic_provider_sends_expected_payload_and_parses_text(monkeypatch):
    monkeypatch.setenv("FAKE_ANTHROPIC_KEY", "sk-fake")
    provider = AnthropicProvider({"model": "claude-x", "api_key_env": "FAKE_ANTHROPIC_KEY", "max_tokens": 50})

    fake_response = _resp({"content": [{"type": "text", "text": "Focus on adoption."}]})
    with patch.object(provider.session, "post", return_value=fake_response) as mock_post:
        text = provider.generate("some prompt")

    assert text == "Focus on adoption."
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "claude-x"
    assert kwargs["json"]["max_tokens"] == 50
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "some prompt"}]
    assert provider.session.headers["x-api-key"] == "sk-fake"


def test_openai_provider_requires_api_key_env(monkeypatch):
    monkeypatch.delenv("FAKE_OPENAI_KEY", raising=False)
    with pytest.raises(ValueError, match="FAKE_OPENAI_KEY"):
        OpenAIProvider({"model": "gpt-x", "api_key_env": "FAKE_OPENAI_KEY"})


def test_openai_provider_sends_expected_payload_and_parses_text(monkeypatch):
    monkeypatch.setenv("FAKE_OPENAI_KEY", "sk-fake")
    provider = OpenAIProvider({"model": "gpt-x", "api_key_env": "FAKE_OPENAI_KEY"})

    fake_response = _resp({"choices": [{"message": {"content": "Focus on quality."}}]})
    with patch.object(provider.session, "post", return_value=fake_response) as mock_post:
        text = provider.generate("some prompt")

    assert text == "Focus on quality."
    _, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "gpt-x"
    assert provider.session.headers["Authorization"] == "Bearer sk-fake"


def test_registry_builds_known_providers(monkeypatch):
    monkeypatch.setenv("FAKE_ANTHROPIC_KEY", "sk-fake")
    provider = build_provider("anthropic", {"model": "claude-x", "api_key_env": "FAKE_ANTHROPIC_KEY"})
    assert isinstance(provider, AnthropicProvider)


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown insights provider"):
        build_provider("not-a-real-provider", {})
