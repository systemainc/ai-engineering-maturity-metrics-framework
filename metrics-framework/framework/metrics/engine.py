"""
The metrics engine: turns a populated Store + Config into the exact JSON
shape the dashboard consumes — org-level dimension scores, per-division
dimension scores, per-team dimension scores (nested inside each division),
levels 1-4, and quarter-over-quarter trend at every level.

This is the only place that knows about maturity *levels*; framework/metrics/
definitions.py only knows how to compute a raw metric value for a given
scope (org / division / team).

Team is the finest granularity this engine ever computes. There is
deliberately no per-person code path — see `min_team_size` below and the
framework README's governance section.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from typing import Optional

from .definitions import REGISTRY
from ..config import Config, DimensionConfig
from ..store import Store

METRIC_META = {
    "weekly_active_usage":       {"label": "Weekly active usage",            "suffix": "%"},
    "ai_pr_share":                {"label": "AI-assisted PR share",           "suffix": "%"},
    "training_pct":               {"label": "Agentic workflow training",      "suffix": "%"},
    "deploy_frequency_per_week":  {"label": "Deploys / week (median)",        "suffix": ""},
    "lead_time_hours":            {"label": "Lead time",                      "suffix": " hrs"},
    "change_failure_rate_pct":    {"label": "Change failure rate",            "suffix": "%"},
    "mttr_hours":                 {"label": "MTTR",                           "suffix": " hrs"},
    "credit_utilization_pct":     {"label": "Credit utilization",             "suffix": "%"},
    "spend_per_active_user_usd":  {"label": "Spend / active user",            "prefix": "$", "suffix": "/mo"},
    "ai_test_pr_pct":             {"label": "AI-generated test coverage",     "suffix": "%"},
    "ai_review_gate_pct":         {"label": "AI review gate coverage",        "suffix": "%"},
    "vulns_escaped_per_quarter":  {"label": "Critical/high vulns escaped",    "suffix": ""},
    "composite_score":            {"label": "Composite score",                "suffix": "/100"},
}


def parse_period(label: str) -> tuple[datetime, datetime]:
    """'2026-Q2' -> (2026-04-01T00:00:00, 2026-06-30T23:59:59). Calendar quarters."""
    year_s, q_s = label.split("-Q")
    year, q = int(year_s), int(q_s)
    if q not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarter in period '{label}'")
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    start = datetime(year, start_month, 1)
    last_day = monthrange(year, end_month)[1]
    end = datetime(year, end_month, last_day, 23, 59, 59)
    return start, end


def format_value(metric_name: str, value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    meta = METRIC_META.get(metric_name, {})
    if float(value).is_integer():
        num = str(int(value))
    else:
        num = f"{value:.1f}"
    return f"{meta.get('prefix', '')}{num}{meta.get('suffix', '')}"


def assign_level(value: Optional[float], threshold_cfg: Optional[dict]) -> Optional[int]:
    if value is None or not threshold_cfg:
        return None
    bounds = threshold_cfg["bounds"]
    direction = threshold_cfg.get("direction", "higher")
    for level in (4, 3, 2, 1):
        bound = bounds[level - 1]
        if direction == "higher" and value >= bound:
            return level
        if direction == "lower" and value <= bound:
            return level
    return 1


def _aggregate(levels: list[int], strategy: str) -> Optional[int]:
    available = [l for l in levels if l is not None]
    if not available:
        return None
    if strategy == "minimum":
        return min(available)
    return round(sum(available) / len(available))


def _compute_dimension_for_scope(dim: DimensionConfig, store: Store, division_id, start, end, period_label=None, team=None):
    """Returns (level, {metric_name: value}) for one dimension, scoped to org / division / team."""
    values = {}
    levels = []
    for metric_name in dim.metrics:
        fn = REGISTRY.get(metric_name)
        if fn is None:
            raise ValueError(f"Dimension '{dim.id}' references unknown metric '{metric_name}'")
        kwargs = {}
        if metric_name == "composite_score":
            kwargs["weights"] = dim.weights
        if metric_name == "spend_per_active_user_usd":
            kwargs["period_label"] = period_label
        value = fn(store, division_id, start, end, team=team, **kwargs)
        values[metric_name] = value
        levels.append(assign_level(value, (dim.level_thresholds or {}).get(metric_name)))
    level = _aggregate(levels, dim.level_strategy)
    return level, values


def _trend(current: Optional[int], prior: Optional[int]) -> int:
    if current is None or prior is None:
        return 0
    if current > prior:
        return 1
    if current < prior:
        return -1
    return 0


def _highlight(dim: DimensionConfig, values: dict) -> str:
    parts = []
    for metric_name in dim.metrics[:2]:
        meta = METRIC_META.get(metric_name, {"label": metric_name})
        parts.append(f"{format_value(metric_name, values.get(metric_name))} {meta['label'].lower()}")
    return " · ".join(parts)


def _compute_scope_dims(config: Config, store: Store, division_id, team, cur_start, cur_end, prior_start, prior_end) -> dict:
    """{dim_id: {level, trend, m, insufficientData}} for one division- or team-scoped row.

    Shared by division-level and team-level output so the two nesting levels can't drift
    apart — a team row is computed exactly the same way a division row is, just with an
    extra `team` filter applied.
    """
    out = {}
    for dim in config.dimensions:
        level_cur, values_cur = _compute_dimension_for_scope(
            dim, store, division_id, cur_start, cur_end, config.period_current, team=team)
        level_prior, values_prior = _compute_dimension_for_scope(
            dim, store, division_id, prior_start, prior_end, config.period_prior, team=team)
        rows = []
        for metric_name in dim.metrics:
            cur_v = values_cur.get(metric_name)
            prior_v = values_prior.get(metric_name)
            delta = "n/a"
            if cur_v is not None and prior_v is not None:
                diff = round(cur_v - prior_v, 1)
                sign = "+" if diff >= 0 else ""
                delta = f"{sign}{diff}"
            rows.append([METRIC_META.get(metric_name, {}).get("label", metric_name),
                         format_value(metric_name, cur_v), delta])
        out[dim.id] = {
            "level": level_cur if level_cur is not None else 1,
            "trend": _trend(level_cur, level_prior),
            "m": rows,
            "insufficientData": level_cur is None,
        }
    return out


def _team_breakdown_for_division(config: Config, store: Store, division_id, cur_start, cur_end, prior_start, prior_end) -> list:
    """Per-team rows for one division. Teams below `config.min_team_size` are suppressed —
    metrics are not computed for them at all, only a name/size/reason — because a team that
    small makes its "team average" de facto per-person data. See README governance section.
    """
    rows = []
    for team_name in store.teams_in_division(division_id):
        team_people = store.people(division_id, team_name)
        if len(team_people) < config.min_team_size:
            n = len(team_people)
            rows.append({
                "name": team_name,
                "engineers": n,
                "suppressed": True,
                "reason": (
                    f"{n} engineer{'s' if n != 1 else ''} — below the {config.min_team_size}-person "
                    "minimum for team-level reporting. A team this small would make individual "
                    "contribution identifiable from the aggregate, which this framework's governance "
                    "model rules out (see 'Per-person data never appears in the output')."
                ),
            })
            continue
        rows.append({
            "name": team_name,
            "engineers": len(team_people),
            "suppressed": False,
            "dims": _compute_scope_dims(config, store, division_id, team_name, cur_start, cur_end, prior_start, prior_end),
        })
    return rows


def compute(config: Config, store: Store) -> dict:
    cur_start, cur_end = parse_period(config.period_current)
    prior_start, prior_end = parse_period(config.period_prior)

    dimensions_out = []
    for dim in config.dimensions:
        org_level_cur, org_values_cur = _compute_dimension_for_scope(dim, store, None, cur_start, cur_end, config.period_current)
        org_level_prior, _ = _compute_dimension_for_scope(dim, store, None, prior_start, prior_end, config.period_prior)

        dimensions_out.append({
            "id": dim.id,
            "name": dim.name,
            "orgLevel": org_level_cur if org_level_cur is not None else 1,
            "orgTrend": _trend(org_level_cur, org_level_prior),
            "orgHi": _highlight(dim, org_values_cur),
            "insufficientData": org_level_cur is None,
        })

    divisions_out = []
    for division in config.divisions:
        did = division["id"]
        people = store.people(did)
        division_dims = _compute_scope_dims(config, store, did, None, cur_start, cur_end, prior_start, prior_end)
        team_breakdown = _team_breakdown_for_division(config, store, did, cur_start, cur_end, prior_start, prior_end)

        divisions_out.append({
            "name": division["name"],
            "teams": len(store.teams_in_division(did)),
            "engineers": len(people),
            "dims": division_dims,
            "teamBreakdown": team_breakdown,
        })

    return {
        "meta": {
            "org": config.org_name,
            "engineers": len(store.get("person")),
            "teams": len({p.team for p in store.get("person") if p.team}),
            "divisions": len(config.divisions),
            "periodCurrent": config.period_current,
            "periodPrior": config.period_prior,
            "minTeamSize": config.min_team_size,
        },
        "LEVELS": [
            {"n": l["n"], "key": f"l{l['n']}", "name": l["name"]}
            for l in config.levels
        ],
        "DIMENSIONS": dimensions_out,
        "DIVISIONS": divisions_out,
    }
