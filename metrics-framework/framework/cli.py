"""
CLI entrypoint.

    python -m framework.cli run --config config.yaml
    python -m framework.cli validate --config config.yaml
"""
from __future__ import annotations

import argparse
import sys

from .adapters import ADAPTER_REGISTRY
from .config import ConfigError, load_config
from .pipeline import run_pipeline, write_outputs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="framework", description="AI Engineering Maturity Framework")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Fetch all configured sources, compute metrics, write outputs")
    p_run.add_argument("--config", required=True)

    p_val = sub.add_parser("validate", help="Load and sanity-check a config file without fetching any data")
    p_val.add_argument("--config", required=True)

    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            config = load_config(args.config)
        except ConfigError as e:
            print(f"INVALID: {e}", file=sys.stderr)
            return 1
        unknown = [s.type for s in config.sources if s.type not in ADAPTER_REGISTRY]
        if unknown:
            print(f"INVALID: unknown adapter type(s): {unknown}", file=sys.stderr)
            return 1
        print(f"OK — {config.org_name}: {len(config.sources)} sources, "
              f"{len(config.dimensions)} dimensions, {len(config.divisions)} divisions")
        return 0

    if args.command == "run":
        import os
        result = run_pipeline(args.config)
        config = load_config(args.config)
        write_outputs(result, config, base_dir=os.path.dirname(os.path.abspath(args.config)) or ".")
        if result["meta"]["sourcesFailed"]:
            print(f"[warn] {result['meta']['sourcesFailed']} of {result['meta']['sourcesRun']} sources failed "
                  f"— see meta.sourceErrors in the output", file=sys.stderr)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
