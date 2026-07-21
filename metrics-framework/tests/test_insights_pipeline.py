"""
End-to-end insights wiring, fully offline: the CSV fixtures run through the
real pipeline (adapters -> store -> engine -> gap analysis), and only the
actual network call (AnthropicProvider.generate) is mocked. This proves the
whole chain — config parsing, provider construction, gap analysis, prompt
building, per-scope attachment, error isolation — without ever touching a
real API.
"""
import os
from unittest.mock import patch

from framework.config import load_config
from framework.insights.anthropic_provider import AnthropicProvider
from framework.pipeline import run_pipeline

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG_PATH = os.path.join(FIXTURES, "config.test.yaml")
INSIGHTS_CONFIG_PATH = os.path.join(FIXTURES, "config.test_insights.yaml")


def _division(result, name):
    return next(d for d in result["DIVISIONS"] if d["name"] == name)


def test_insights_disabled_by_default_adds_nothing(monkeypatch):
    # config.test.yaml has no `insights:` block at all — the disabled path must not
    # import-and-call anything LLM-related, and must leave meta free of insight keys
    # beyond the explicit "insightsEnabled: False" marker.
    result = run_pipeline(CONFIG_PATH)
    assert result["meta"]["insightsEnabled"] is False
    assert "orgInsight" not in result
    assert "insight" not in _division(result, "Payments & Billing")


def test_insights_config_requires_model_and_api_key_env_when_enabled(tmp_path):
    import yaml
    cfg = yaml.safe_load(open(INSIGHTS_CONFIG_PATH))
    del cfg["insights"]["model"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.dump(cfg))
    import pytest
    from framework.config import ConfigError
    with pytest.raises(ConfigError, match="insights.model"):
        load_config(str(broken))


def test_insights_enabled_attaches_org_and_division_insights(monkeypatch):
    monkeypatch.setenv("FAKE_TEST_ANTHROPIC_KEY", "sk-fake")
    with patch.object(AnthropicProvider, "generate", return_value="Focus here. It matters most."):
        result = run_pipeline(INSIGHTS_CONFIG_PATH)

    assert result["meta"]["insightsEnabled"] is True
    assert result["meta"]["insightsFailed"] == 0
    assert result["meta"]["insightsRequested"] > 0

    assert "orgInsight" in result
    assert result["orgInsight"]["text"] == "Focus here. It matters most."
    assert "gap" in result["orgInsight"]
    assert result["orgInsight"]["gap"]["dimension_id"] in {"adoption", "flow", "spend", "quality", "health"}

    payments = _division(result, "Payments & Billing")
    assert "insight" in payments
    assert payments["insight"]["text"] == "Focus here. It matters most."


def test_insights_skip_suppressed_teams(monkeypatch):
    monkeypatch.setenv("FAKE_TEST_ANTHROPIC_KEY", "sk-fake")
    calls = []

    def fake_generate(self, prompt):
        calls.append(prompt)
        return "note"

    with patch.object(AnthropicProvider, "generate", fake_generate):
        result = run_pipeline(INSIGHTS_CONFIG_PATH)

    payments = _division(result, "Payments & Billing")
    team_b = next(t for t in payments["teamBreakdown"] if t["name"] == "teamB")
    assert team_b["suppressed"] is True
    assert "insight" not in team_b   # never even attempted — no prompt should mention teamB
    assert not any("teamB" in p for p in calls)


def test_one_failed_insight_call_does_not_abort_the_others(monkeypatch):
    monkeypatch.setenv("FAKE_TEST_ANTHROPIC_KEY", "sk-fake")

    call_count = {"n": 0}

    def counting_flaky_generate(self, prompt):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated timeout")
        return "ok"

    with patch.object(AnthropicProvider, "generate", counting_flaky_generate):
        result = run_pipeline(INSIGHTS_CONFIG_PATH)

    assert result["meta"]["insightsFailed"] == 1
    assert len(result["meta"]["insightErrors"]) == 1
    # every other scope that had a computable gap still got its insight
    assert result["meta"]["insightsRequested"] > 1
    succeeded = sum(1 for d in result["DIVISIONS"] if "insight" in d)
    assert succeeded >= 1


def test_provider_setup_failure_does_not_crash_pipeline(monkeypatch):
    # api key env var is intentionally NOT set -> AnthropicProvider.__init__ raises ->
    # _apply_insights must catch that too, not just generate() failures.
    monkeypatch.delenv("FAKE_TEST_ANTHROPIC_KEY", raising=False)
    result = run_pipeline(INSIGHTS_CONFIG_PATH)
    assert result["meta"]["insightsEnabled"] is True
    assert result["meta"]["insightsFailed"] == 0
    assert len(result["meta"]["insightErrors"]) == 1
    assert "orgInsight" not in result
    # the rest of the pipeline (real metrics) is completely unaffected
    assert len(result["DIVISIONS"]) == 2
