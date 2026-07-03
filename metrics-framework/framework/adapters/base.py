"""
Adapter interface.

Every data source — a CSV export, a live GitHub org, a Jira project, a
warehouse table — implements the same two-step contract:

    fetch()     -> yields raw records (dicts), source-shape, unmodified
    normalize() -> turns raw records into semantic dataclass instances

Splitting the two matters: fetch() is where network/IO calls and retries
live; normalize() is pure data transformation and is unit-testable without
any network at all (see tests/test_csv_adapter.py for the pattern).

Adding a new source system means writing one new Adapter subclass. Nothing
else in the framework changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Iterator

from ..schema import ENTITY_TYPES


class Adapter(ABC):
    #: adapter type key, matched against `type:` in the config source entry
    type_key: str = "base"

    def __init__(self, name: str, entity: str, options: dict):
        if entity not in ENTITY_TYPES:
            raise ValueError(
                f"Source '{name}' declares unknown entity '{entity}'. "
                f"Known entities: {sorted(ENTITY_TYPES)}"
            )
        self.name = name
        self.entity = entity
        self.entity_cls = ENTITY_TYPES[entity]
        self.options = options

    @abstractmethod
    def fetch(self) -> Iterable[dict]:
        """Yield raw records exactly as the source system returns them."""
        raise NotImplementedError

    @abstractmethod
    def normalize(self, raw_records: Iterable[dict]) -> Iterator[object]:
        """Turn raw records into instances of self.entity_cls."""
        raise NotImplementedError

    def run(self) -> list:
        """fetch -> normalize, with a source-tagged error if either step fails."""
        try:
            raw = list(self.fetch())
        except Exception as e:
            raise RuntimeError(f"[{self.name}] fetch() failed: {e}") from e
        try:
            return list(self.normalize(raw))
        except Exception as e:
            raise RuntimeError(f"[{self.name}] normalize() failed: {e}") from e


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "t", "yes", "y")


def _coerce_optional(value):
    """Treat common 'empty' spreadsheet/API values as None."""
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "n/a", "null", "none"):
        return None
    return value
