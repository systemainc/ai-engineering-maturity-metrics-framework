# AI Engineering Maturity Framework

A configurable pipeline that turns raw engineering-org data (GitHub, Jira, CI/CD,
AI tool telemetry, billing, a warehouse) into the five-dimension maturity
scorecard used by `ai-engineering-maturity-dashboard.html`.

One YAML file (`config.yaml`) is the only thing you change to point this at a
different org. Nothing in `framework/` should ever hardcode an org-specific
value — division names, thresholds, and source connections all live in config.

```
config.yaml ─▶ adapters (fetch + normalize) ─▶ Store (semantic entities)
                                                      │
                                                      ▼
                                          metrics engine (formulas + levels)
                                                      │
                                                      ▼
                                     out/metrics.json + out/dashboard_data.js
                                                      │
                                                      ▼
                              ai-engineering-maturity-dashboard.html (drop the
                              generated dashboard_data.js next to it)
```

## Quick start

```bash
pip install -r requirements.txt
python -m framework.cli validate --config config.example.yaml
python -m framework.cli run --config config.example.yaml
# writes out/metrics.json and out/dashboard_data.js
```

Copy `out/dashboard_data.js` next to `ai-engineering-maturity-dashboard.html`
and reopen it — the Scorecard tab now reflects your data instead of the
built-in sample. The Definitions and Blueprint tabs stay static; they explain
the model, which doesn't change when you plug in a new data source.

Run the test suite (no credentials needed — it's entirely CSV-fixture driven):

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## The semantic schema

Every adapter normalizes into one of the dataclasses in `framework/schema.py`:
`Person`, `Division`, `Repo`, `PullRequest`, `Deploy`, `Incident`,
`Vulnerability`, `Defect`, `AIUsageEvent`, `AISeat`, `BillingRecord`,
`TrainingRecord`, `CodeHealthSnapshot`. This is the common vocabulary — nothing
downstream of normalization (the store, the metrics engine) knows anything
about GitHub, Jira, or any other source system.

## Adding a data source

A `sources:` entry in the config declares a `type` (which adapter handles it),
an `entity` (which semantic type it produces), and adapter-specific options.
Four adapters ship today:

| type     | Needs                                   | Good for |
|----------|------------------------------------------|----------|
| `csv`    | a file path + `field_map`                | exports, backfills, anything you can dump to a spreadsheet — the reference adapter, always runnable, no credentials |
| `github` | an org, a `GITHUB_TOKEN`, a repo→division map | merged PRs + AI-authorship signal (commit trailers, bot accounts) |
| `jira`   | a base URL, email + API token, a JQL query | training records or any ticket-shaped entity, via dotted-path field mapping |
| `sql`    | a SQLAlchemy connection string + query    | a warehouse/semantic layer (Postgres, Snowflake via `snowflake-sqlalchemy`, etc.) |

Secrets are never written into the YAML — every credential is
`token_env: SOME_ENV_VAR`, resolved from the environment at load time.

To add a fifth source system (e.g. Linear, PagerDuty, a different CI system),
write one `Adapter` subclass implementing `fetch()` → raw records and
`normalize()` → semantic dataclass instances, and register it in
`framework/adapters/__init__.py`'s `ADAPTER_REGISTRY`. Nothing else changes.

One broken source does not abort the run — `pipeline.py` collects failures
per-source and keeps going, so a team with 8 sources and one expired token
still gets a dashboard for the other 7 (see `meta.sourceErrors` in the output).

## The five dimensions and their metrics

Defined in `framework/metrics/definitions.py`, configured in `config.yaml`'s
`metrics.dimensions`. Each metric function has the signature
`fn(store, division_id, start, end) -> float | None`, where `None` means
"insufficient data" — a real data gap is surfaced (`insufficientData: true`
in the output, a coverage note in the dashboard), never silently treated as
zero.

| Dimension | Metrics | Real simplifications worth knowing |
|---|---|---|
| AI Adoption & Fluency | weekly active usage, AI-assisted PR share, training completion | AI-authorship via commit metadata undercounts inline/autocomplete use with no trailer — treat as a trend |
| Delivery Flow | deploy frequency, lead time, change failure rate, MTTR | lead time is approximated as PR-merge → next same-repo deploy, not a full commit-level trace |
| AI Spend Efficiency | credit/seat utilization, spend per active user | billing is matched by period label (e.g. "2026-Q2"), not a date range, since spend is naturally reported per billing cycle |
| Quality & Risk Automation | AI test coverage, AI review gate coverage, critical/high vulns escaped | uses `minimum` level-aggregation, not average — one badly-lagging metric here should not be masked by two good ones |
| Codebase Health | weighted composite (coverage, complexity, dead code, dependency freshness, docs) | needs a static-analysis pipeline feeding `code_health_snapshot`; weights need explicit sign-off before cross-team comparison |

Maturity levels (1 Exploring / 2 Piloting / 3 Scaling / 4 Optimizing) are
assigned per metric from `level_thresholds` in the config — each threshold
has a `direction` (`higher` or `lower` is better) and 4 ascending/descending
`bounds`. A dimension's level is the average (or, for Quality, the minimum)
of its metrics' levels. Trend compares the current period's level against
the prior period's.

## Governance principles this framework enforces in code, not just docs

- **Per-person data never appears in the output.** The engine only computes
  org- and division-level aggregates — there is no per-IC code path at all,
  so per-IC leaderboards can't leak in by omission.
- **A metric with no data is flagged, never faked.** See `insufficientData`
  above.
- **One broken source doesn't take down the dashboard.** See `sourceErrors`
  above.

## Layout

```
framework/
  schema.py           semantic entity dataclasses
  config.py            YAML config loading + ${ENV_VAR} secret resolution
  store.py              in-memory normalized store + repo/person → division joins
  adapters/
    base.py              Adapter interface (fetch → normalize)
    coerce.py             shared type coercion (CSV strings/API JSON → dataclass fields)
    csv_adapter.py         reference adapter, no credentials needed
    github_adapter.py      live: merged PRs + AI-authorship signal
    jira_adapter.py         live: JQL search, dotted-path field mapping
    sql_adapter.py           live: any SQLAlchemy-reachable warehouse
  metrics/
    definitions.py       metric formulas (one function per metric)
    engine.py             level assignment, aggregation, trend, dashboard-shaped output
  pipeline.py           config -> adapters -> store -> engine -> output
  cli.py                `run` / `validate` commands
tests/
  fixtures/             small CSV dataset + config.test.yaml (2 divisions, 5 people) —
                          the whole suite runs offline against this, no credentials
  test_*.py
config.example.yaml    a fully worked example config for a 5-division org
requirements.txt
```
