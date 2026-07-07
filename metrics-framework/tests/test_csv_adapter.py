import os

from framework.adapters.csv_adapter import CSVAdapter

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_csv_adapter_normalizes_people():
    adapter = CSVAdapter("roster", "person", {
        "path": os.path.join(FIXTURES, "people.csv"),
        "field_map": {"id": "person_id", "email": "email", "division_id": "division",
                      "team": "team", "role": "role", "name": "name"},
    })
    people = adapter.run()
    assert len(people) == 5
    alice = next(p for p in people if p.id == "p1")
    assert alice.email == "p1@x.com"
    assert alice.division_id == "payments"
    assert alice.team == "teamA"


def test_csv_adapter_coerces_booleans_and_dates():
    adapter = CSVAdapter("prs", "pull_request", {
        "path": os.path.join(FIXTURES, "pull_requests.csv"),
        "field_map": {
            "id": "pr_id", "repo_id": "repo_id", "author_id": "author_id",
            "opened_at": "opened_at", "merged_at": "merged_at",
            "ai_assisted": "ai_assisted", "ai_test_generated": "ai_test_generated",
            "ai_review_passed": "ai_review_passed", "lines_changed": "lines_changed",
        },
    })
    prs = {pr.id: pr for pr in adapter.run()}
    assert prs["pr1"].ai_assisted is True
    assert prs["pr2"].ai_assisted is False
    assert prs["pr3"].ai_review_passed is None   # blank cell -> None, not False
    assert prs["pr1"].merged_at.year == 2026
    assert prs["pr1"].lines_changed == 120


def test_csv_adapter_missing_required_field_raises():
    adapter = CSVAdapter("bad", "person", {
        "path": os.path.join(FIXTURES, "people.csv"),
        "field_map": {"email": "email"},  # missing required 'id'
    })
    import pytest
    with pytest.raises(Exception):
        adapter.run()
