"""
Pipeline orchestrator: config -> adapters -> store -> metrics engine ->
(optional) insights -> output.

Design choice: one broken source should not take down the whole dashboard.
Each source runs independently; failures are collected and reported (both to
stderr and inside the output JSON's meta.sourceErrors) rather than aborting
the run. A team with 8 data sources and one expired API token should still
get a dashboard for the other 7. The same posture applies to insight
generation below: one failed LLM call skips that scope's insight, it never
aborts the run or blanks out the (already-correct) computed metrics.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .adapters import build_adapter
from .config import Config, load_config
from .insights import build_provider
from .insights.prompt import build_prompt
from .metrics.engine import compute
from .metrics.gap_analysis import top_gap
from .store import Store


def run_pipeline(config_path: str, base_dir: str | None = None) -> dict:
    config = load_config(config_path)
    base = Path(base_dir) if base_dir else Path(config_path).resolve().parent

    store = Store()
    source_errors = []
    for source in config.sources:
        opts = dict(source.options)
        for path_key in ("path", "repo_division_map_path"):
            if path_key in opts and not os.path.isabs(opts[path_key]):
                opts[path_key] = str(base / opts[path_key])
        try:
            adapter = build_adapter(_with_options(source, opts))
            records = adapter.run()
            store.add(source.entity, records)
        except Exception as e:  # noqa: BLE001 - deliberately broad: one bad source shouldn't kill the run
            msg = f"{source.name} ({source.type}): {e}"
            source_errors.append(msg)
            print(f"[warn] source failed, continuing without it — {msg}", file=sys.stderr)

    result = compute(config, store)
    result["meta"]["sourceErrors"] = source_errors
    result["meta"]["sourcesRun"] = len(config.sources)
    result["meta"]["sourcesFailed"] = len(source_errors)

    if config.insights.enabled:
        _apply_insights(config, result)
    else:
        result["meta"]["insightsEnabled"] = False

    return result


def _apply_insights(config: Config, result: dict) -> None:
    """Mutates `result` in place, attaching an `insight` (or `orgInsight`) field
    wherever framework/metrics/gap_analysis.py finds a highest-leverage next move.

    Every insight is generated once here, in the pipeline, and baked into the JSON —
    never called live from the dashboard. The dashboard is a static file; it has no API
    key and makes no outbound calls. See config.example.yaml's `insights:` block.
    """
    try:
        provider = build_provider(config.insights.provider, {
            "model": config.insights.model,
            "api_key_env": config.insights.api_key_env,
            "max_tokens": config.insights.max_tokens,
        })
    except Exception as e:  # noqa: BLE001 - provider construction (e.g. missing API key) shouldn't kill the run
        result["meta"]["insightsEnabled"] = True
        result["meta"]["insightErrors"] = [f"provider setup: {e}"]
        result["meta"]["insightsRequested"] = 0
        result["meta"]["insightsFailed"] = 0
        print(f"[warn] insights provider setup failed, skipping insights — {e}", file=sys.stderr)
        return

    errors: list[str] = []
    requested = 0

    def _generate(scope_label: str, gap: dict):
        nonlocal requested
        if gap is None:
            return None
        requested += 1
        hint = config.insights.suggestions.get(gap["metric"])
        prompt = build_prompt(scope_label, gap, suggestion_hint=hint)
        try:
            text = provider.generate(prompt)
        except Exception as e:  # noqa: BLE001 - one failed call shouldn't drop the others
            errors.append(f"{scope_label}: {e}")
            print(f"[warn] insight generation failed for '{scope_label}' — {e}", file=sys.stderr)
            return None
        return {"text": text, "gap": gap}

    org_dims_out = {d["id"]: {"level": d["orgLevel"], "raw": d.get("raw", {})} for d in result["DIMENSIONS"]}
    org_gap = top_gap(config.dimensions, org_dims_out)
    org_insight = _generate(f"{config.org_name} (org-wide)", org_gap)
    if org_insight:
        result["orgInsight"] = org_insight

    for division in result["DIVISIONS"]:
        div_gap = top_gap(config.dimensions, division["dims"])
        div_insight = _generate(division["name"], div_gap)
        if div_insight:
            division["insight"] = div_insight

        for team in division.get("teamBreakdown", []):
            if team.get("suppressed"):
                continue
            team_gap = top_gap(config.dimensions, team["dims"])
            team_insight = _generate(f"{division['name']} / {team['name']}", team_gap)
            if team_insight:
                team["insight"] = team_insight

    result["meta"]["insightsEnabled"] = True
    result["meta"]["insightsRequested"] = requested
    result["meta"]["insightsFailed"] = len(errors)
    result["meta"]["insightErrors"] = errors


def _with_options(source, opts):
    from dataclasses import replace
    return replace(source, options=opts)


def write_outputs(result: dict, config: Config, base_dir: str | None = None) -> None:
    base = Path(base_dir) if base_dir else Path(".")
    json_path = base / config.output.get("json", "out/metrics.json")
    js_path = base / config.output.get("dashboard_data_js", "out/dashboard_data.js")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(json.dumps(result, indent=2))
    js_path.write_text("window.DASHBOARD_DATA = " + json.dumps(result, indent=2) + ";\n")

    print(f"wrote {json_path}")
    print(f"wrote {js_path}")
