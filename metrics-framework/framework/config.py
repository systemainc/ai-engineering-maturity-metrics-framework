"""
Config loading and validation for the AI Engineering Maturity Framework.

The config file (YAML) is the one place that changes when you point this
framework at a different org: which data sources exist, how their fields map
onto the semantic schema, and where the maturity-level thresholds sit for
each metric. Nothing in framework/adapters, framework/metrics, or
framework/pipeline.py should ever hardcode an org-specific value.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class SourceConfig:
    name: str
    type: str                      # csv | github | jira | sql
    entity: str                    # which semantic entity this source produces
    options: dict = field(default_factory=dict)   # adapter-specific: path, org, base_url, query, field_map, ...


@dataclass
class DimensionConfig:
    id: str
    name: str
    metrics: list
    level_strategy: str = "average"     # average | minimum
    weights: Optional[dict] = None       # for composite metrics like codebase health
    level_thresholds: Optional[dict] = None   # {metric_name: [L1_min, L2_min, L3_min, L4_min]}


@dataclass
class Config:
    org_name: str
    period_current: str
    period_prior: str
    divisions: list                # list of {id, name}
    sources: list                  # list[SourceConfig]
    dimensions: list               # list[DimensionConfig]
    levels: list                   # [{n, name}, ...]
    output: dict
    raw: dict = field(default_factory=dict)

    def division_ids(self):
        return [d["id"] for d in self.divisions]


def _expand_env(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders so secrets never live in the YAML file itself."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        var = value[2:-1]
        resolved = os.environ.get(var)
        if resolved is None:
            raise ConfigError(f"Config references ${{{var}}} but that environment variable is not set")
        return resolved
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


def load_config(path: str) -> Config:
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    raw = _expand_env(raw)

    try:
        org = raw["organization"]
        divisions = raw["divisions"]
        sources_raw = raw["sources"]
        metrics_raw = raw["metrics"]
        output = raw.get("output", {})
    except KeyError as e:
        raise ConfigError(f"Config is missing required top-level key: {e}") from e

    sources = []
    for s in sources_raw:
        for required in ("name", "type", "entity"):
            if required not in s:
                raise ConfigError(f"Source entry {s} is missing required key '{required}'")
        options = {k: v for k, v in s.items() if k not in ("name", "type", "entity")}
        sources.append(SourceConfig(name=s["name"], type=s["type"], entity=s["entity"], options=options))

    dimensions = []
    for dim_id, dim in metrics_raw.get("dimensions", {}).items():
        dimensions.append(DimensionConfig(
            id=dim_id,
            name=dim.get("name", dim_id),
            metrics=dim.get("metrics", []),
            level_strategy=dim.get("level_strategy", "average"),
            weights=dim.get("weights"),
            level_thresholds=dim.get("level_thresholds", {}),
        ))

    return Config(
        org_name=org["name"],
        period_current=org["period_current"],
        period_prior=org["period_prior"],
        divisions=divisions,
        sources=sources,
        dimensions=dimensions,
        levels=metrics_raw.get("levels", []),
        output=output,
        raw=raw,
    )
