from unittest.mock import MagicMock, patch

import pytest

from framework.adapters.jira_adapter import JiraAdapter


def test_jira_adapter_requires_credentials(monkeypatch):
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="JIRA_EMAIL"):
        JiraAdapter("training", "training_record", {
            "base_url": "https://x.atlassian.net", "email_env": "JIRA_EMAIL", "token_env": "JIRA_API_TOKEN",
            "jql": "project = ENG", "field_map": {"person_id": "fields.assignee.emailAddress"},
        })


def test_jira_adapter_paginates_and_maps_nested_fields(monkeypatch):
    monkeypatch.setenv("JIRA_EMAIL", "bot@x.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "secret")
    adapter = JiraAdapter("training", "training_record", {
        "base_url": "https://x.atlassian.net", "email_env": "JIRA_EMAIL", "token_env": "JIRA_API_TOKEN",
        "jql": "project = ENG",
        "field_map": {
            "person_id": "fields.assignee.emailAddress",
            "program": "fields.summary",
            "completed_at": "fields.resolutiondate",
        },
    })

    page1 = MagicMock()
    page1.raise_for_status = MagicMock()
    page1.json.return_value = {
        "issues": [{
            "fields": {
                "assignee": {"emailAddress": "alice@x.com"},
                "summary": "Agentic Delegation 101",
                "resolutiondate": "2026-02-01T00:00:00.000+0000",
            }
        }],
        "nextPageToken": "tok2",
    }
    page2 = MagicMock()
    page2.raise_for_status = MagicMock()
    page2.json.return_value = {"issues": [], "nextPageToken": None}

    with patch.object(adapter.session, "post", side_effect=[page1, page2]):
        records = adapter.run()

    assert len(records) == 1
    assert records[0].person_id == "alice@x.com"
    assert records[0].program == "Agentic Delegation 101"
    assert records[0].completed_at.year == 2026
