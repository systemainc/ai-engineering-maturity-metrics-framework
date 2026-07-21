"""
Deterministic "what's the single highest-leverage next move" analysis.

This is pure arithmetic over numbers the engine has already computed — no
LLM, no network, nothing probabilistic. It exists as its own module,
separate from framework/insights/, on purpose: everything an LLM is allowed
to say about a scope's data has to pass through here first. The model's job
(see framework/insights/) is to turn one of these fact sets into two
sentences of prose; it never gets raw numbers and never gets to decide what
matters. If you disable the insights feature entirely, this module still
runs for free and could just as well be rendered as a plain-text hint with
no LLM involved at all.

Given a scope's per-dimension output (level + raw metric values, both
already present on the engine's dashboard-shaped output), `top_gap()`
picks ONE fact set: the dimension holding the scope's overall score down
the most, and within it, the single metric worth focusing on next.
"""
from __future__ import annotations

from typing import Optional

from ..config import DimensionConfig
from .engine import assign_level


def _metric_gap(metric_name: str, value: Optional[float], threshold_cfg: Optional[dict], metric_level: Optional[int]) -> Optional[dict]:
    """Distance from `value` to the bound needed for the next level up, for one metric.

    None if there's nothing to compute: no value, no threshold config, or the metric is
    already at L4 (nowhere further up to go).
    """
    if value is None or not threshold_cfg or metric_level is None or metric_level >= 4:
        return None
    bounds = threshold_cfg["bounds"]
    direction = threshold_cfg.get("direction", "higher")
    metric_next_level = metric_level + 1
    target = bounds[metric_next_level - 1]
    distance = (target - value) if direction == "higher" else (value - target)

    # "progress": how far value already is across the band between this level's floor
    # and the next level's bound, as a 0-1 fraction. Lets metrics on completely
    # different scales (%, hours, $) be compared for "how close is this to leveling up"
    # within a single dimension, and across dimensions in top_gap() below.
    prev_bound = bounds[metric_level - 1]
    span = abs(target - prev_bound) or 1e-9
    progress = max(0.0, min(1.0, 1 - abs(distance) / span))

    return {
        "metric": metric_name,
        "value": value,
        "target": target,
        "distance": round(distance, 2),
        "direction": direction,
        # Deliberately namespaced "metric_*", not "current_level"/"next_level" — those
        # names are reserved for the DIMENSION's own level in top_gap()'s output, which
        # (for average-strategy dimensions especially) is often NOT the same number as
        # this one metric's level. Conflating the two produced a real bug during
        # development: a dimension at L2 whose lagging metric was individually at L1
        # rendered as "currently L2, needs to reach L2," which is nonsense.
        "metric_level": metric_level,
        "metric_next_level": metric_next_level,
        "progress": round(progress, 3),
    }


def dimension_lever(dim: DimensionConfig, level: Optional[int], raw_values: dict) -> Optional[dict]:
    """The single metric within this dimension worth focusing on next.

    None if the dimension has no level (insufficient data), is already at L4, or none of
    its metrics have both a value and threshold config to compute a gap from.

    `minimum`-strategy dimensions (e.g. Quality & Risk Automation) restrict candidates to
    whichever metric(s) are currently AT the dimension's level — by construction, that
    metric is the one holding the whole dimension back, so there's no ambiguity to
    resolve. `average`-strategy dimensions consider every metric and pick the lowest-level
    one, tie-broken by whichever is closest to its own next bound — the cheapest unlock.
    """
    if level is None or level >= 4:
        return None

    candidates = []
    for metric_name in dim.metrics:
        threshold_cfg = (dim.level_thresholds or {}).get(metric_name)
        value = raw_values.get(metric_name)
        metric_level = assign_level(value, threshold_cfg)
        gap = _metric_gap(metric_name, value, threshold_cfg, metric_level)
        if gap is None:
            continue
        candidates.append((metric_level, gap))

    if not candidates:
        return None

    if dim.level_strategy == "minimum":
        at_level = [c for c in candidates if c[0] == level]
        if at_level:
            candidates = at_level

    candidates.sort(key=lambda c: (c[0], -c[1]["progress"]))
    return candidates[0][1]


def top_gap(dim_configs: list[DimensionConfig], dims_out: dict) -> Optional[dict]:
    """Across every dimension in this scope, the single highest-leverage next move.

    `dims_out`: {dim_id: {"level": int|None, "raw": {metric_name: value|None}, ...}} —
    exactly the shape `engine._compute_scope_dims()` (division/team) produces, or the
    small transform of `dimensions_out` pipeline.py builds for the org scope.

    Picks the lowest-level dimension first — that's the one dragging the scope's overall
    picture down. Ties broken by whichever dimension's lever metric is closest to
    unlocking its next level. Returns a fully self-contained fact set: dimension, metric,
    current value, target, direction. Nothing downstream has to infer anything further.
    """
    best_key = None
    best = None
    for dim in dim_configs:
        row = dims_out.get(dim.id)
        if not row or row.get("level") is None:
            continue
        lever = dimension_lever(dim, row["level"], row.get("raw") or {})
        if lever is None:
            continue
        key = (row["level"], -lever["progress"])
        if best_key is None or key < best_key:
            best_key = key
            best = {
                "dimension_id": dim.id,
                "dimension_name": dim.name,
                "current_level": row["level"],
                **lever,
            }
    return best
