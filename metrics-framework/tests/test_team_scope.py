"""
Team is the finest granularity this framework computes (never per-person).
These tests cover both paths: a team at/above `min_team_size` gets full
metrics, and a team below it is suppressed rather than computed.

Fixture roster (people.csv): payments division has teamA (p1, p2) and
teamB (p3, solo) — config.test.yaml sets min_team_size: 2, so teamA clears
the bar and teamB doesn't. platform division has teamC (p4, p5).
"""
import os

from framework.config import Config, load_config
from framework.pipeline import run_pipeline

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
CONFIG_PATH = os.path.join(FIXTURES, "config.test.yaml")


def _division(result, name):
    return next(d for d in result["DIVISIONS"] if d["name"] == name)


def _team(division, name):
    return next(t for t in division["teamBreakdown"] if t["name"] == name)


def test_division_lists_its_teams():
    result = run_pipeline(CONFIG_PATH)
    payments = _division(result, "Payments & Billing")
    platform = _division(result, "Core Platform & Infra")
    assert payments["teams"] == 2   # teamA, teamB
    assert platform["teams"] == 1   # teamC
    assert {t["name"] for t in payments["teamBreakdown"]} == {"teamA", "teamB"}
    assert {t["name"] for t in platform["teamBreakdown"]} == {"teamC"}


def test_small_team_is_suppressed_not_computed():
    result = run_pipeline(CONFIG_PATH)
    payments = _division(result, "Payments & Billing")
    team_b = _team(payments, "teamB")   # solo — below min_team_size: 2
    assert team_b["suppressed"] is True
    assert team_b["engineers"] == 1
    assert "dims" not in team_b
    assert "below the 2-person minimum" in team_b["reason"]


def test_team_at_minimum_size_gets_full_metrics():
    result = run_pipeline(CONFIG_PATH)
    payments = _division(result, "Payments & Billing")
    team_a = _team(payments, "teamA")   # p1, p2 — exactly at min_team_size: 2
    assert team_a["suppressed"] is False
    assert team_a["engineers"] == 2
    for dim_id in ("adoption", "flow", "spend", "quality", "health"):
        assert dim_id in team_a["dims"]
        assert 1 <= team_a["dims"][dim_id]["level"] <= 4


def test_team_adoption_metrics_match_hand_calculation():
    # Q2 ai_usage events: u1(p1), u2(p2) -> both teamA active -> 2/2 = 100%
    # Q2 ai_usage events: u3(p4) -> teamC 1/2 active = 50%
    result = run_pipeline(CONFIG_PATH)
    payments = _division(result, "Payments & Billing")
    platform = _division(result, "Core Platform & Infra")
    team_a = _team(payments, "teamA")
    team_c = _team(platform, "teamC")
    adoption_a = {row[0]: row[1] for row in team_a["dims"]["adoption"]["m"]}
    adoption_c = {row[0]: row[1] for row in team_c["dims"]["adoption"]["m"]}
    assert adoption_a["Weekly active usage"] == "100%"
    assert adoption_c["Weekly active usage"] == "50%"
    # Q2 merged PRs: r1 (teamA) has pr1 (ai) + pr2 (not) -> 50%; r3 (teamC) has pr4 (ai) only -> 100%
    assert adoption_a["AI-assisted PR share"] == "50%"
    assert adoption_c["AI-assisted PR share"] == "100%"


def test_spend_metric_is_not_computed_at_team_scope():
    # Billing is reported per division in every real export we've seen — never per team.
    # Team-scoped spend must stay "n/a", not silently inherit or split the division total.
    result = run_pipeline(CONFIG_PATH)
    payments = _division(result, "Payments & Billing")
    team_a = _team(payments, "teamA")
    spend_rows = {row[0]: row[1] for row in team_a["dims"]["spend"]["m"]}
    assert spend_rows["Spend / active user"] == "n/a"
    # credit utilization DOES resolve at team scope (it's seat-level, joined via person)
    assert spend_rows["Credit utilization"] == "100%"


def test_default_min_team_size_is_three():
    # The fixture config overrides this to 2 to exercise both code paths with a tiny
    # roster; the framework's own default (used when a real org's config is silent on
    # it) should be the more conservative 3.
    config = load_config(CONFIG_PATH)
    assert config.min_team_size == 2  # overridden by config.test.yaml
    default_config = Config(
        org_name="x", period_current="2026-Q1", period_prior="2025-Q4",
        divisions=[], sources=[], dimensions=[], levels=[], output={},
    )
    assert default_config.min_team_size == 3


def test_meta_reports_min_team_size():
    result = run_pipeline(CONFIG_PATH)
    assert result["meta"]["minTeamSize"] == 2
