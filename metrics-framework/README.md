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

`Person` and `Repo` both carry an optional `team` field — a plain string label,
not a separately-fetched entity. That's what drives the dashboard's org →
division → team drilldown: person-keyed metrics (Adoption, Spend) resolve
team via the person, repo-keyed metrics (Flow, Quality, Codebase Health) via
the repo. Leave `team` unset and everything still works at the division
level; you just won't get a team breakdown.

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
`fn(store, division_id, start, end, team=None) -> float | None`, where
`division_id=None` means org-wide, `team=None` means "whole division," and
`None` return value means "insufficient data" — a real data gap is surfaced
(`insufficientData: true` in the output, a coverage note in the dashboard),
never silently treated as zero.

| Dimension | Metrics | Real simplifications worth knowing |
|---|---|---|
| AI Adoption & Fluency | weekly active usage, AI-assisted PR share, training completion | AI-authorship via commit metadata undercounts inline/autocomplete use with no trailer — treat as a trend |
| Delivery Flow | deploy frequency, lead time, change failure rate, MTTR | lead time is approximated as PR-merge → next same-repo deploy, not a full commit-level trace |
| AI Spend Efficiency | credit/seat utilization, spend per active user | billing is matched by period label (e.g. "2026-Q2"), not a date range, since spend is naturally reported per billing cycle. **Team scope not supported** — billing exports report per division, never per team, so `spend_per_active_user_usd` always returns `None` (insufficient data) when a `team` is passed, rather than attributing a division's total to one team |
| Quality & Risk Automation | AI test coverage, AI review gate coverage, critical/high vulns escaped | uses `minimum` level-aggregation, not average — one badly-lagging metric here should not be masked by two good ones |
| Codebase Health | weighted composite (coverage, complexity, dead code, dependency freshness, docs) | needs a static-analysis pipeline feeding `code_health_snapshot`; weights need explicit sign-off before cross-team comparison |

Maturity levels (1 Exploring / 2 Piloting / 3 Scaling / 4 Optimizing) are
assigned per metric from `level_thresholds` in the config — each threshold
has a `direction` (`higher` or `lower` is better) and 4 ascending/descending
`bounds`. A dimension's level is the average (or, for Quality, the minimum)
of its metrics' levels. Trend compares the current period's level against
the prior period's. The same assignment/aggregation code runs at org,
division, and team scope — a team's level isn't computed by some separate,
looser path.

## Team-level drilldown

Every division's output includes a `teamBreakdown`: one entry per distinct
`team` value found among that division's people, each scored exactly like a
division (same five dimensions, same level/trend logic), via
`store.teams_in_division()` and `engine._team_breakdown_for_division()`.

Teams below `metrics.min_team_size` in the config (default 3) are
**suppressed, not computed**: the output includes the team's name and
headcount and a `suppressed: true` flag, but no `dims` at all. This isn't a
display-layer filter — the engine never calls the metric formulas for that
team in the first place. The reasoning: a 2-person team's "average" is
functionally per-person data once you know who's on the team, which this
framework's per-person exclusion is meant to rule out. Raise
`min_team_size` for orgs with larger teams; don't lower it just to make more
teams "light up" in the dashboard.

## Governance principles this framework enforces in code, not just docs

- **Per-person data never appears in the output.** The engine only computes
  org-, division-, and team-level aggregates — there is no per-IC code path
  at all, so per-IC leaderboards can't leak in by omission.
- **A team below the size floor is suppressed, not computed.** See
  "Team-level drilldown" above — this is the same principle applied one
  level finer than division.
- **A metric with no data is flagged, never faked.** See `insufficientData`
  above.
- **One broken source doesn't take down the dashboard.** See `sourceErrors`
  above.

## Layout

```
framework/
  schema.py           semantic entity dataclasses
  config.py            YAML config loading + ${ENV_VAR} secret resolution + min_team_size
  store.py              in-memory normalized store + repo/person → division/team joins
  adapters/
    base.py              Adapter interface (fetch → normalize)
    coerce.py             shared type coercion (CSV strings/API JSON → dataclass fields)
    csv_adapter.py         reference adapter, no credentials needed
    github_adapter.py      live: merged PRs + AI-authorship signal
    jira_adapter.py         live: JQL search, dotted-path field mapping
    sql_adapter.py           live: any SQLAlchemy-reachable warehouse
  metrics/
    definitions.py       metric formulas (one function per metric, org/division/team scope)
    engine.py             level assignment, aggregation, trend, team-size suppression, dashboard-shaped output
  pipeline.py           config -> adapters -> store -> engine -> output
  cli.py                `run` / `validate` commands
tests/
  fixtures/             small CSV dataset + config.test.yaml (2 divisions, 3 teams, 5 people) —
                          the whole suite runs offline against this, no credentials
  test_*.py             includes test_team_scope.py (full-metrics vs. suppressed team paths)
config.example.yaml    a fully worked example config for a 5-division org
requirements.txt
```
