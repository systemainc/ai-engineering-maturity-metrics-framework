import csv
import os
from unittest.mock import MagicMock, patch

import pytest

from framework.adapters.github_adapter import GitHubAdapter


@pytest.fixture
def repo_map_path(tmp_path):
    path = tmp_path / "repo_division_map.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["repo", "division"])
        w.writerow(["payments-api", "payments"])
    return str(path)


def _resp(json_body, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body
    m.raise_for_status = MagicMock()
    if status >= 400:
        m.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return m


def test_github_adapter_requires_token_env(repo_map_path, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        GitHubAdapter("gh", "pull_request", {
            "org": "acme", "token_env": "GITHUB_TOKEN", "repo_division_map_path": repo_map_path,
        })


def test_github_adapter_fetches_and_flags_ai_signal(repo_map_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    adapter = GitHubAdapter("gh", "pull_request", {
        "org": "acme", "token_env": "GITHUB_TOKEN", "repo_division_map_path": repo_map_path,
        "ai_signal": {"co_authored_trailers": ["co-authored-by: claude"], "bot_authors": []},
    })

    repos_page1 = _resp([{"name": "payments-api"}])
    repos_page2 = _resp([])
    prs_page1 = _resp([
        {"id": 1, "number": 101, "merged_at": "2026-04-02T09:00:00Z", "created_at": "2026-04-01T09:00:00Z",
         "user": {"login": "alice"}, "additions": 10, "deletions": 2},
    ])
    prs_page2 = _resp([])
    pr_detail = _resp({"user": {"login": "alice"}})
    pr_commits = _resp([{"commit": {"message": "fix thing\n\nCo-Authored-By: Claude <noreply@anthropic.com>"}}])

    def fake_get(url, params=None):
        if url.endswith("/orgs/acme/repos"):
            return repos_page1 if params["page"] == 1 else repos_page2
        if url.endswith("/repos/acme/payments-api/pulls") and "state" in (params or {}):
            return prs_page1 if params["page"] == 1 else prs_page2
        if url.endswith("/pulls/101"):
            return pr_detail
        if url.endswith("/pulls/101/commits"):
            return pr_commits
        raise AssertionError(f"unexpected URL {url}")

    with patch.object(adapter.session, "get", side_effect=fake_get):
        records = adapter.run()

    assert len(records) == 1
    pr = records[0]
    assert pr.repo_id == "payments-api"
    assert pr.ai_assisted is True
    assert pr.lines_changed == 12


def test_github_adapter_skips_unmapped_repos(repo_map_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    adapter = GitHubAdapter("gh", "pull_request", {
        "org": "acme", "token_env": "GITHUB_TOKEN", "repo_division_map_path": repo_map_path,
    })

    def fake_get(url, params=None):
        if url.endswith("/orgs/acme/repos"):
            return _resp([{"name": "some-unmapped-repo"}]) if params["page"] == 1 else _resp([])
        raise AssertionError(f"should not fetch PRs for an unmapped repo, got {url}")

    with patch.object(adapter.session, "get", side_effect=fake_get):
        records = adapter.run()

    assert records == []
