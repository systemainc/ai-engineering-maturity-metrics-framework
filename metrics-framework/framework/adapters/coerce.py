"""
Shared type coercion: every adapter ends up building a dataclass instance
from loosely-typed source data (CSV strings, JSON from an API, DB rows).
This module is the one place that turns "2026-04-12T09:00:00Z" or "true"
or "" into the right Python value for the target dataclass field, so each
adapter's normalize() stays a short, readable field-by-field mapping.
"""
from __future__ import annotations

import re
import typing
from datetime import date, datetime


def _normalize_iso(s: str) -> str:
    """Make real-world ISO-ish timestamps parseable by datetime.fromisoformat, which
    (on Python < 3.11) rejects a bare 'Z' or an offset with no colon like '+0000' —
    both of which Jira and plenty of other APIs send by default."""
    s = s.strip().replace("Z", "+00:00")
    # "+0000" / "-0500" (no colon) -> "+00:00" / "-05:00"
    s = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', s)
    return s


def _unwrap_optional(tp):
    """Optional[X] is Union[X, None] — pull out X for coercion purposes."""
    origin = typing.get_origin(tp)
    if origin is typing.Union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def coerce_value(value, target_type):
    if value is None:
        return None
    if isinstance(value, str) and value.strip() in ("", "n/a", "N/A", "null", "None"):
        return None

    target_type = _unwrap_optional(target_type)

    if target_type is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "t", "yes", "y")

    if target_type is int:
        return int(float(value))

    if target_type is float:
        return float(value)

    if target_type is datetime:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        dt = datetime.fromisoformat(_normalize_iso(str(value)))
        return dt.replace(tzinfo=None)  # normalize to naive UTC-equivalent so all comparisons stay consistent

    if target_type is date:
        if isinstance(value, date):
            return value
        return datetime.fromisoformat(_normalize_iso(str(value))).date()

    return str(value) if not isinstance(value, str) else value


def build_entity(entity_cls, field_map: dict, source_record: dict, get=None):
    """
    field_map: {semantic_field_name: source_key}
    source_record: the raw dict (CSV row / API JSON / DB row-as-dict)
    get: optional custom getter(source_record, source_key) -> raw value,
         used by adapters like Jira where source_key is a dotted path
         into a nested JSON payload (e.g. "fields.assignee.emailAddress").
    """
    hints = typing.get_type_hints(entity_cls)
    getter = get or (lambda rec, key: rec.get(key))
    kwargs = {}
    for semantic_field, source_key in field_map.items():
        if semantic_field not in hints:
            raise ValueError(
                f"{entity_cls.__name__} has no field '{semantic_field}' "
                f"(check the field_map in your config)"
            )
        raw_value = getter(source_record, source_key)
        kwargs[semantic_field] = coerce_value(raw_value, hints[semantic_field])

    required = [
        f.name for f in __import__("dataclasses").fields(entity_cls)
        if f.default is __import__("dataclasses").MISSING
        and f.default_factory is __import__("dataclasses").MISSING  # type: ignore[misc]
    ]
    missing = [r for r in required if kwargs.get(r) is None]
    if missing:
        raise ValueError(f"{entity_cls.__name__} record is missing required field(s): {missing}")

    return entity_cls(**kwargs)


def get_dotted(record: dict, dotted_key: str):
    """Resolve 'fields.assignee.emailAddress' against a nested dict (used by JiraAdapter)."""
    cur = record
    for part in dotted_key.split("."):
        if cur is None:
            return None
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur
