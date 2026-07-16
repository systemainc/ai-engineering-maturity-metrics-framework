# AI Engineering Maturity Metrics Framework

A blueprint for measuring AI-native engineering across teams that are
starting from very different places: how deeply engineers actually use AI
tools, whether AI spend is going anywhere, whether AI is being used to catch
problems (not just ship more code faster), and whether the codebase can
still be maintained as AI-generated volume grows.

Two pieces:

- **[`ai-engineering-maturity-dashboard.html`](./ai-engineering-maturity-dashboard.html)**
  — a single-file, no-build dashboard. Open it directly in a browser. Ships
  with illustrative sample data (a fictional org, "Beacon Digital") so the
  shape of the model is visible immediately.
- **[`metrics-framework/`](./metrics-framework)** — a configurable Python
  pipeline that turns real data (GitHub, Jira, CI/CD, AI tool telemetry,
  billing, a warehouse) into the exact JSON the dashboard consumes. One
  YAML config file per org; no code changes required to point it at a
  different company.

## Why this exists

Most early "AI OKRs" reach for metrics that don't hold up: individual
story-points-per-developer (gameable, discouraged by both the DORA and
SPACE research programs), AI suggestion acceptance rate as a standalone
number (ambiguous — high acceptance can mean "AI is great" or "engineers
are rubber-stamping"), lines of code (a vanity metric AI inflates for
free). See the dashboard's **Metric Definitions** tab, "What we
deliberately left out," for the full reasoning.

Instead, this uses a five-dimension maturity model — AI Adoption &
Fluency, Delivery Flow (DORA's four keys), AI Spend Efficiency, Quality &
Risk Automation, and Codebase Health — scored 1–4 (Exploring → Piloting →
Scaling → Optimizing), drilling down org → division → team. Team is the
floor: there is no per-individual code path anywhere in the engine, and a
team below a configurable size (default 3) is shown by name and headcount
only — metrics withheld, not computed anyway — because a 2-person "team
average" is de facto per-person data.

## Quick start

Just want to see it? Open `ai-engineering-maturity-dashboard.html` in a
browser — no server, no build step.

Want it running on your own org's data? See
[`metrics-framework/README.md`](./metrics-framework/README.md).

## License

MIT — see [LICENSE](./LICENSE).
