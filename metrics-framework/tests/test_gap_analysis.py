"""
Gap analysis is pure arithmetic — no LLM, no network, no mocking needed.
This is the module every downstream LLM call is restricted to reading from,
so it earns thorough, synchronous, easy-to-audit tests.
"""
from framework.config import DimensionConfig
from framework.metrics.gap_analysis import dimension_lever, top_gap


def _dim(id_, metrics, thresholds, strategy="average"):
    return DimensionConfig(id=id_, name=id_.title(), metrics=metrics, level_strategy=strategy,
                            level_thresholds=thresholds)


def test_dimension_already_at_max_level_has_no_lever():
    dim = _dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}})
    assert dimension_lever(dim, level=4, raw_values={"a": 90}) is None


def test_dimension_with_no_level_has_no_lever():
    dim = _dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}})
    assert dimension_lever(dim, level=None, raw_values={"a": 90}) is None


def test_average_strategy_picks_closest_metric_to_next_bound():
    # both metrics currently at level 2 (bounds index 1). "a" needs +10 to hit L3's bound
    # of 50 (currently 40); "b" needs +30 to hit L3's bound of 60 (currently 30). "a" is
    # closer (smaller relative gap) so it should win even though "b"'s absolute value is
    # lower.
    thresholds = {
        "a": {"direction": "higher", "bounds": [0, 20, 50, 80]},
        "b": {"direction": "higher", "bounds": [0, 20, 60, 90]},
    }
    dim = _dim("adoption", ["a", "b"], thresholds, strategy="average")
    lever = dimension_lever(dim, level=2, raw_values={"a": 40, "b": 30})
    assert lever["metric"] == "a"
    assert lever["target"] == 50
    assert lever["distance"] == 10


def test_minimum_strategy_only_considers_the_gating_metric():
    # dimension level is 1 (minimum of levels [1, 3]). Even though "fast" (level 3, value
    # 95) is numerically closer to ITS next bound, it isn't the reason the dimension is at
    # L1 — "slow" is. The lever must be "slow".
    thresholds = {
        "slow": {"direction": "higher", "bounds": [0, 10, 40, 70]},   # value 5 -> level 1
        "fast": {"direction": "higher", "bounds": [0, 10, 40, 70]},   # value 95 -> level 4 (no gap, excluded)
    }
    dim = _dim("quality", ["slow", "fast"], thresholds, strategy="minimum")
    lever = dimension_lever(dim, level=1, raw_values={"slow": 5, "fast": 95})
    assert lever["metric"] == "slow"


def test_metric_with_no_data_is_skipped_not_treated_as_zero():
    thresholds = {
        "a": {"direction": "higher", "bounds": [0, 20, 50, 80]},
        "b": {"direction": "higher", "bounds": [0, 20, 50, 80]},
    }
    dim = _dim("adoption", ["a", "b"], thresholds)
    lever = dimension_lever(dim, level=2, raw_values={"a": None, "b": 35})
    assert lever["metric"] == "b"


def test_dimension_where_every_metric_lacks_data_has_no_lever():
    thresholds = {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}}
    dim = _dim("adoption", ["a"], thresholds)
    assert dimension_lever(dim, level=2, raw_values={"a": None}) is None


def test_lower_is_better_direction_computes_positive_distance():
    thresholds = {"lead_time": {"direction": "lower", "bounds": [9999, 72, 24, 6]}}
    dim = _dim("flow", ["lead_time"], thresholds)
    # level 2 band is (72, 24] i.e. bounds[1]=72; current value 50 needs to drop to 24
    lever = dimension_lever(dim, level=2, raw_values={"lead_time": 50})
    assert lever["metric"] == "lead_time"
    assert lever["target"] == 24
    assert lever["distance"] == 26   # 50 - 24


def test_top_gap_picks_the_lowest_level_dimension():
    dims = [
        _dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
        _dim("flow", ["b"], {"b": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
    ]
    dims_out = {
        "adoption": {"level": 3, "raw": {"a": 55}},
        "flow": {"level": 1, "raw": {"b": 5}},
    }
    result = top_gap(dims, dims_out)
    assert result["dimension_id"] == "flow"
    assert result["metric"] == "b"


def test_top_gap_ties_broken_by_progress_toward_next_level():
    dims = [
        _dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
        _dim("flow", ["b"], {"b": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
    ]
    # both dimensions at level 2; "adoption"'s metric is much closer to the L3 bound (48
    # vs. needing 50) than "flow"'s (22 vs. needing 50) -> adoption should win the tie.
    dims_out = {
        "adoption": {"level": 2, "raw": {"a": 48}},
        "flow": {"level": 2, "raw": {"b": 22}},
    }
    result = top_gap(dims, dims_out)
    assert result["dimension_id"] == "adoption"


def test_top_gap_skips_dimensions_with_insufficient_data():
    dims = [
        _dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
        _dim("flow", ["b"], {"b": {"direction": "higher", "bounds": [0, 20, 50, 80]}}),
    ]
    dims_out = {
        "adoption": {"level": None, "raw": {"a": None}},
        "flow": {"level": 2, "raw": {"b": 22}},
    }
    result = top_gap(dims, dims_out)
    assert result["dimension_id"] == "flow"


def test_top_gap_returns_none_when_every_dimension_is_maxed_or_missing():
    dims = [_dim("adoption", ["a"], {"a": {"direction": "higher", "bounds": [0, 20, 50, 80]}})]
    dims_out = {"adoption": {"level": 4, "raw": {"a": 95}}}
    assert top_gap(dims, dims_out) is None
