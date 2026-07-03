"""
GitHubAdapter — pulls merged pull requests across every repo in a GitHub
org via the REST API, tags each with an AI-authorship signal (Co-Authored-By
trailer or a known bot login), and maps repo -> division via a small CSV.

Config options (type: github):
    org:                    required, GitHub org login
    token_env:               required, name of the env var holding a PAT
                              with repo read access (never the token itself)
    since:                   optional ISO date, only PRs merged after this
    repo_division_map_path:  required, CSV with columns repo,division
    ai_signal.co_authored_trailers: list of exact trailer strings to match
    ai_signal.bot_authors:          list of bot login names

Only entity: pull_request is currently supported; extending this adapter to
also emit `deploy` (via workflow runs) or `incident` follows the same
fetch/normalize shape.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Iterable, Iterator

import requests

from .base import Adapter
from ..schema import PullRequest

API_ROOT = "https://api.github.com"


class GitHubAdapter(Adapter):
    type_key = "github"

    def __init__(self, name: str, entity: str, options: dict):
        super().__init__(name, entity, options)
        if entity != "pull_request":
            raise ValueError("GitHubAdapter currently only supports entity: pull_request")
        for required in ("org", "token_env", "repo_division_map_path"):
            if required not in options:
                raise ValueError(f"GitHub source '{name}' is missing required option '{required}'")
        self.org = options["org"]
        token = os.environ.get(options["token_env"])
        if not token:
            raise ValueError(
                f"GitHub source '{name}': environment variable "
                f"{options['token_env']} is not set"
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.since = options.get("since")
        self.repo_division = self._load_repo_division_map(options["repo_division_map_path"])
        ai_signal = options.get("ai_signal", {})
        self.trailers = [t.lower() for t in ai_signal.get("co_authored_trailers", [])]
        self.bot_authors = set(ai_signal.get("bot_authors", []))

    @staticmethod
    def _load_repo_division_map(path: str) -> dict:
        mapping = {}
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                mapping[row["repo"]] = row["division"]
        return mapping

    def _list_repos(self):
        page = 1
        while True:
            resp = self.session.get(f"{API_ROOT}/orgs/{self.org}/repos", params={"per_page": 100, "page": page})
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                return
            for repo in batch:
                yield repo["name"]
            page += 1

    def _list_merged_prs(self, repo: str):
        page = 1
        while True:
            resp = self.session.get(
                f"{API_ROOT}/repos/{self.org}/{repo}/pulls",
                params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 100, "page": page},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                return
            stop = False
            for pr in batch:
                if not pr.get("merged_at"):
                    continue
                if self.since and pr["merged_at"] < self.since:
                    stop = True
                    continue
                yield repo, pr
            if stop:
                return
            page += 1

    def fetch(self) -> Iterable[dict]:
        for repo in self._list_repos():
            if repo not in self.repo_division:
                continue  # unmapped repos are out of scope, same convention as the rest of the framework
            for repo_name, pr in self._list_merged_prs(repo):
                pr["_repo"] = repo_name
                yield pr

    def _has_ai_signal(self, repo: str, pr_number: int) -> bool:
        author = None
        try:
            resp = self.session.get(f"{API_ROOT}/repos/{self.org}/{repo}/pulls/{pr_number}")
            resp.raise_for_status()
            author = (resp.json().get("user") or {}).get("login")
        except requests.RequestException:
            pass
        if author in self.bot_authors:
            return True
        try:
            resp = self.session.get(
                f"{API_ROOT}/repos/{self.org}/{repo}/pulls/{pr_number}/commits", params={"per_page": 100}
            )
            resp.raise_for_status()
            for commit in resp.json():
                msg = ((commit.get("commit") or {}).get("message") or "").lower()
                if any(t in msg for t in self.trailers):
                    return True
        except requests.RequestException:
            pass
        return False

    def normalize(self, raw_records: Iterable[dict]) -> Iterator[object]:
        for pr in raw_records:
            repo = pr["_repo"]
            yield PullRequest(
                id=str(pr["id"]),
                repo_id=repo,
                author_id=(pr.get("user") or {}).get("login"),
                opened_at=_parse_dt(pr.get("created_at")),
                merged_at=_parse_dt(pr.get("merged_at")),
                ai_assisted=self._has_ai_signal(repo, pr["number"]),
                lines_changed=(pr.get("additions", 0) or 0) + (pr.get("deletions", 0) or 0),
            )


def _parse_dt(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
