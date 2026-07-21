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
class InsightsConfig:
    """Opt-in, off by default. When disabled, nothing in framework/insights/ is ever
    imported-and-called, no network call happens, and no API key is required — the
    pipeline behaves exactly as it did before this feature existed.

    `suggestions` is optional, config-authored, per-metric hint text (e.g.
    {"credit_utilization_pct": "Push provisioned-but-idle seats toward active use before
    adding more seats"}) folded into the prompt alongside the computed gap. It's advisory
    context for the model, not a template it's required to follow verbatim.
    """
    enabled: bool = False
    provider: str = "anthropic"    # anthropic | openai — see framework/insights/PROVIDER_REGISTRY
    model: str = ""
    api_key_env: str = ""
    max_tokens: int = 200
    suggestions: dict = field(default_factory=dict)


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
    min_team_size: int = 3         # teams smaller than this are suppressed in team-level output,
                                    # not computed — a 1-2 person "team average" is de facto per-person
                                    # data, which this framework's governance stance rules out.
    insights: InsightsConfig = field(default_factory=InsightsConfig)
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

    insights_raw = raw.get("insights") or {}
    insights = InsightsConfig(
        enabled=bool(insights_raw.get("enabled", False)),
        provider=insights_raw.get("provider", "anthropic"),
        model=insights_raw.get("model", ""),
        api_key_env=insights_raw.get("api_key_env", ""),
        max_tokens=insights_raw.get("max_tokens", 200),
        suggestions=insights_raw.get("suggestions", {}),
    )
    if insights.enabled:
        for required in ("model", "api_key_env"):
            if not getattr(insights, required):
                raise ConfigError(f"insights.enabled is true but insights.{required} is missing")

    return Config(
        org_name=org["name"],
        period_current=org["period_current"],
        period_prior=org["period_prior"],
        divisions=divisions,
        sources=sources,
        dimensions=dimensions,
        levels=metrics_raw.get("levels", []),
        output=output,
        min_team_size=metrics_raw.get("min_team_size", 3),
        insights=insights,
        raw=raw,
    )
