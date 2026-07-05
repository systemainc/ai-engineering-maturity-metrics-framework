"""
Pipeline orchestrator: config -> adapters -> store -> metrics engine -> output.

Design choice: one broken source should not take down the whole dashboard.
Each source runs independently; failures are collected and reported (both to
stderr and inside the output JSON's meta.sourceErrors) rather than aborting
the run. A team with 8 data sources and one expired API token should still
get a dashboard for the other 7.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .adapters import build_adapter
from .config import Config, load_config
from .metrics.engine import compute
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
    return result


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
