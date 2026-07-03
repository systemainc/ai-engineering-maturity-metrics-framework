"""
SQLAdapter — runs a parameterized query against any SQLAlchemy-reachable
database (Postgres, MySQL, SQLite, Snowflake via `snowflake-sqlalchemy`,
etc.) and normalizes each row into a semantic entity.

This is the intended long-term adapter for a warehouse/semantic-layer setup
like the one described in the framework README: land raw source data in
Snowflake, build one clean view per semantic entity, point this adapter at
each view.

Config options (type: sql):
    connection_env:  required, env var holding a SQLAlchemy connection URL
                      (e.g. "snowflake://user:pass@account/db/schema" or
                      "postgresql://user:pass@host/db")
    query:            required, SQL text; supports :named params
    params:           optional, dict of bind parameters
    field_map:        optional, {semantic_field: column_name}; if omitted,
                       column names are assumed to already match the
                       semantic field names
"""
from __future__ import annotations

import os
from typing import Iterable, Iterator

from .base import Adapter
from .coerce import build_entity


class SQLAdapter(Adapter):
    type_key = "sql"

    def __init__(self, name: str, entity: str, options: dict):
        super().__init__(name, entity, options)
        for required in ("connection_env", "query"):
            if required not in options:
                raise ValueError(f"SQL source '{name}' is missing required option '{required}'")
        conn_str = os.environ.get(options["connection_env"])
        if not conn_str:
            raise ValueError(
                f"SQL source '{name}': environment variable "
                f"{options['connection_env']} is not set"
            )
        try:
            import sqlalchemy  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "SQLAdapter requires the 'sqlalchemy' package. Install it with: "
                "pip install sqlalchemy (plus a driver for your warehouse, e.g. "
                "snowflake-sqlalchemy or psycopg2-binary)."
            ) from e
        self._conn_str = conn_str
        self.query = options["query"]
        self.params = options.get("params", {})
        import typing as _t
        hints = _t.get_type_hints(self.entity_cls)
        self.field_map = options.get("field_map") or {f: f for f in hints}

    def fetch(self) -> Iterable[dict]:
        from sqlalchemy import create_engine, text

        engine = create_engine(self._conn_str)
        with engine.connect() as conn:
            result = conn.execute(text(self.query), self.params)
            columns = result.keys()
            for row in result:
                yield dict(zip(columns, row))

    def normalize(self, raw_records: Iterable[dict]) -> Iterator[object]:
        for row in raw_records:
            yield build_entity(self.entity_cls, self.field_map, row)
