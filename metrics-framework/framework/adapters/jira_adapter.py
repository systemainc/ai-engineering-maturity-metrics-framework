"""
JiraAdapter — runs a JQL search against Jira Cloud's REST API v3 and maps
issue fields onto a semantic entity using dotted-path field references
(e.g. "fields.assignee.emailAddress"), so it can feed training_record today
and any other ticket-shaped entity later without new code.

Config options (type: jira):
    base_url:    required, e.g. https://mycompany.atlassian.net
    email_env:   required, env var holding the Jira account email
    token_env:   required, env var holding the Jira API token
    jql:         required, the search query
    field_map:   required, {semantic_field: dotted.path.into.issue.json}
"""
from __future__ import annotations

import os
from typing import Iterable, Iterator

import requests

from .base import Adapter
from .coerce import build_entity, get_dotted

SEARCH_PATH = "/rest/api/3/search/jql"
PAGE_SIZE = 100


class JiraAdapter(Adapter):
    type_key = "jira"

    def __init__(self, name: str, entity: str, options: dict):
        super().__init__(name, entity, options)
        for required in ("base_url", "email_env", "token_env", "jql", "field_map"):
            if required not in options:
                raise ValueError(f"Jira source '{name}' is missing required option '{required}'")
        email = os.environ.get(options["email_env"])
        token = os.environ.get(options["token_env"])
        if not email or not token:
            raise ValueError(
                f"Jira source '{name}': environment variables "
                f"{options['email_env']} / {options['token_env']} are not both set"
            )
        self.base_url = options["base_url"].rstrip("/")
        self.jql = options["jql"]
        self.field_map = options["field_map"]
        self.session = requests.Session()
        self.session.auth = (email, token)
        self.session.headers.update({"Accept": "application/json"})

    def fetch(self) -> Iterable[dict]:
        next_page_token = None
        while True:
            body = {"jql": self.jql, "maxResults": PAGE_SIZE, "fields": ["*all"]}
            if next_page_token:
                body["nextPageToken"] = next_page_token
            resp = self.session.post(f"{self.base_url}{SEARCH_PATH}", json=body)
            resp.raise_for_status()
            data = resp.json()
            for issue in data.get("issues", []):
                yield issue
            next_page_token = data.get("nextPageToken")
            if not next_page_token or not data.get("issues"):
                return

    def normalize(self, raw_records: Iterable[dict]) -> Iterator[object]:
        for issue in raw_records:
            yield build_entity(self.entity_cls, self.field_map, issue, get=get_dotted)
