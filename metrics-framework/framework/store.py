"""
Normalized in-memory store.

Every adapter's normalize() output lands here, keyed by semantic entity
type. The store also owns the joins almost every metric needs — repo ->
division, person -> division, and (one level finer) repo -> team,
person -> team — so metric formulas never have to know how a division or
team was derived, only which scope they're asking about.

Team is a plain string label (like division_id), not a separate registered
entity with its own source of truth — it comes along for the ride on
Person and Repo records. That's deliberate: a team is a grouping within a
division, not a new top-level thing adapters need to fetch separately.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional


class Store:
    def __init__(self):
        self._data: dict[str, list] = defaultdict(list)
        self._repo_division: dict[str, str] = {}
        self._person_division: dict[str, str] = {}
        self._repo_team: dict[str, str] = {}
        self._person_team: dict[str, str] = {}

    def add(self, entity_type: str, records: list):
        self._data[entity_type].extend(records)
        if entity_type == "repo":
            for r in records:
                if r.division_id:
                    self._repo_division[r.id] = r.division_id
                if getattr(r, "team", None):
                    self._repo_team[r.id] = r.team
        if entity_type == "person":
            for p in records:
                if p.division_id:
                    self._person_division[p.id] = p.division_id
                if p.team:
                    self._person_team[p.id] = p.team

    def get(self, entity_type: str) -> list:
        return self._data.get(entity_type, [])

    def division_of_repo(self, repo_id: Optional[str]) -> Optional[str]:
        return self._repo_division.get(repo_id) if repo_id else None

    def division_of_person(self, person_id: Optional[str]) -> Optional[str]:
        return self._person_division.get(person_id) if person_id else None

    def team_of_repo(self, repo_id: Optional[str]) -> Optional[str]:
        return self._repo_team.get(repo_id) if repo_id else None

    def team_of_person(self, person_id: Optional[str]) -> Optional[str]:
        return self._person_team.get(person_id) if person_id else None

    def people(self, division_id: Optional[str] = None, team: Optional[str] = None):
        rows = self.get("person")
        if division_id is not None:
            rows = [p for p in rows if p.division_id == division_id]
        if team is not None:
            rows = [p for p in rows if p.team == team]
        return rows

    def teams_in_division(self, division_id: str) -> list[str]:
        """Distinct team labels for people in this division, sorted for stable output order.

        Anchored on people (not repos) — a "team" for drilldown purposes means a group of
        engineers. A repo's team label (if present) is used only to resolve repo-keyed
        records (PRs, deploys, vulns, code health) to the right team; it never introduces a
        team that has no people in it.
        """
        return sorted({p.team for p in self.people(division_id) if p.team})

    def counts(self) -> dict:
        return {k: len(v) for k, v in self._data.items()}
