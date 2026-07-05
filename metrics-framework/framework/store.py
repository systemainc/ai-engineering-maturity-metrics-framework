"""
Normalized in-memory store.

Every adapter's normalize() output lands here, keyed by semantic entity
type. The store also owns the two joins almost every metric needs —
repo -> division and person -> division — so metric formulas never have to
know how a division was derived, only which division they're asking about.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional


class Store:
    def __init__(self):
        self._data: dict[str, list] = defaultdict(list)
        self._repo_division: dict[str, str] = {}
        self._person_division: dict[str, str] = {}

    def add(self, entity_type: str, records: list):
        self._data[entity_type].extend(records)
        if entity_type == "repo":
            for r in records:
                if r.division_id:
                    self._repo_division[r.id] = r.division_id
        if entity_type == "person":
            for p in records:
                if p.division_id:
                    self._person_division[p.id] = p.division_id

    def get(self, entity_type: str) -> list:
        return self._data.get(entity_type, [])

    def division_of_repo(self, repo_id: Optional[str]) -> Optional[str]:
        return self._repo_division.get(repo_id) if repo_id else None

    def division_of_person(self, person_id: Optional[str]) -> Optional[str]:
        return self._person_division.get(person_id) if person_id else None

    def people(self, division_id: Optional[str] = None):
        rows = self.get("person")
        if division_id is None:
            return rows
        return [p for p in rows if p.division_id == division_id]

    def counts(self) -> dict:
        return {k: len(v) for k, v in self._data.items()}
