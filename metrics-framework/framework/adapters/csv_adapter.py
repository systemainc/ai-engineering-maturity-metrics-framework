"""
CSVAdapter — reads a local CSV/JSON-lines export and normalizes it into a
semantic entity. This is the reference adapter: it needs no credentials, no
network, and is what the test suite runs against, so it's guaranteed to
always work as documentation for "what does a working adapter look like."

Config options (under a `sources[].` entry with type: csv):
    path:       required, path to the CSV file (relative to the config file's
                working directory, or absolute)
    field_map:  required, {semantic_field: csv_column_name}
    delimiter:  optional, default ","
"""
from __future__ import annotations

import csv
from typing import Iterable, Iterator

from .base import Adapter
from .coerce import build_entity


class CSVAdapter(Adapter):
    type_key = "csv"

    def __init__(self, name: str, entity: str, options: dict):
        super().__init__(name, entity, options)
        if "path" not in options:
            raise ValueError(f"CSV source '{name}' is missing required option 'path'")
        if "field_map" not in options:
            raise ValueError(f"CSV source '{name}' is missing required option 'field_map'")
        self.path = options["path"]
        self.field_map = options["field_map"]
        self.delimiter = options.get("delimiter", ",")

    def fetch(self) -> Iterable[dict]:
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            for row in reader:
                yield dict(row)

    def normalize(self, raw_records: Iterable[dict]) -> Iterator[object]:
        for row in raw_records:
            yield build_entity(self.entity_cls, self.field_map, row)
