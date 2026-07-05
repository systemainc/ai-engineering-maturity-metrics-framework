"""
Metric formulas for the five maturity dimensions.

Every function has the same signature:

    fn(store: Store, division_id: Optional[str], start: datetime, end: datetime) -> Optional[float]

`division_id=None` means "org-wide." Returning None means "insufficient
data" — the engine excludes that metric from level aggregation rather than
silently treating missing data as zero. This mirrors the dashboard's own
"coverage note" convention: a gap in the data is surfaced, not hidden.

These formulas encode real (documented) simplifications, e.g. lead time is
approximated as PR-merge-to-next-repo-deploy, not a full commit-level trace.
See README.md "Metric formulas & their limits" for the full list.
"""
from __future__ import annotations

from statistics import median
from typing import Optional

from ..store import Store


def _in_period(dt, start, end) -> bool:
    return dt is not None and start <= dt <= end


def _division_matches(rec_division_id, division_id) -> bool:
    return division_id is None or rec_division_id == division_id


def _pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator == 0:
        return None
    return round(100 * numerator / denominator, 1)


# ---------------------------------------------------------------- adoption

def weekly_active_usage(store: Store, division_id, start, end) -> Optional[float]:
    people = store.people(division_id)
    if not people:
        return None
    active_ids = {
        e.person_id for e in store.get("ai_usage_event")
        if _in_period(e.occurred_at, start, end)
        and _division_matches(store.division_of_person(e.person_id), division_id)
    }
    return _pct(len(active_ids), len(people))


def ai_pr_share(store: Store, division_id, start, end) -> Optional[float]:
    prs = [
        pr for pr in store.get("pull_request")
        if _in_period(pr.merged_at, start, end)
        and _division_matches(store.division_of_repo(pr.repo_id), division_id)
    ]
    if not prs:
        return None
    return _pct(sum(1 for pr in prs if pr.ai_assisted), len(prs))


def training_pct(store: Store, division_id, start, end) -> Optional[float]:
    people = store.people(division_id)
    if not people:
        return None
    trained_ids = {
        t.person_id for t in store.get("training_record")
        if t.completed_at is not None and t.completed_at <= end
        and _division_matches(store.division_of_person(t.person_id), division_id)
    }
    return _pct(len(trained_ids), len(people))


# -------------------------------------------------------------------- flow

def deploy_frequency_per_week(store: Store, division_id, start, end) -> Optional[float]:
    deploys = [
        d for d in store.get("deploy")
        if d.is_prod and _in_period(d.deployed_at, start, end)
        and _division_matches(store.division_of_repo(d.repo_id), division_id)
    ]
    weeks = max((end - start).days / 7.0, 1e-6)
    if not deploys:
        return 0.0
    return round(len(deploys) / weeks, 2)


def lead_time_hours(store: Store, division_id, start, end) -> Optional[float]:
    deploys_by_repo: dict[str, list] = {}
    for d in store.get("deploy"):
        if d.is_prod:
            deploys_by_repo.setdefault(d.repo_id, []).append(d)
    for repo_deploys in deploys_by_repo.values():
        repo_deploys.sort(key=lambda d: d.deployed_at)

    deltas = []
    for pr in store.get("pull_request"):
        if not _in_period(pr.merged_at, start, end):
            continue
        if not _division_matches(store.division_of_repo(pr.repo_id), division_id):
            continue
        for d in deploys_by_repo.get(pr.repo_id, []):
            if d.deployed_at >= pr.merged_at:
                deltas.append((d.deployed_at - pr.merged_at).total_seconds() / 3600.0)
                break
    if not deltas:
        return None
    return round(median(deltas), 1)


def change_failure_rate_pct(store: Store, division_id, start, end) -> Optional[float]:
    deploys = [
        d for d in store.get("deploy")
        if d.is_prod and _in_period(d.deployed_at, start, end)
        and _division_matches(store.division_of_repo(d.repo_id), division_id)
    ]
    if not deploys:
        return None
    failed = sum(1 for d in deploys if d.status in ("failed", "rolled_back"))
    return _pct(failed, len(deploys))


def mttr_hours(store: Store, division_id, start, end) -> Optional[float]:
    incidents = [
        i for i in store.get("incident")
        if i.severity in ("P1", "P2") and i.resolved_at is not None
        and _in_period(i.opened_at, start, end)
        and _division_matches(i.division_id or store.division_of_repo(i.repo_id), division_id)
    ]
    if not incidents:
        return None
    deltas = [(i.resolved_at - i.opened_at).total_seconds() / 3600.0 for i in incidents]
    return round(median(deltas), 1)


# ------------------------------------------------------------------ spend

def credit_utilization_pct(store: Store, division_id, start, end) -> Optional[float]:
    seats = [
        s for s in store.get("ai_seat")
        if s.provisioned and _division_matches(store.division_of_person(s.person_id), division_id)
    ]
    if not seats:
        return None
    return _pct(sum(1 for s in seats if s.active_last_30d), len(seats))


def spend_per_active_user_usd(store: Store, division_id, start, end, period_label: Optional[str] = None) -> Optional[float]:
    """Billing records carry their own `period` label (e.g. "2026-Q2") rather than a
    timestamp, since spend is naturally reported per billing cycle. `period_label` is
    passed in by the engine so this stays consistent with whichever period the caller
    is computing (current vs. prior)."""
    records = [
        b for b in store.get("billing_record")
        if _division_matches(b.division_id, division_id)
        and (period_label is None or b.period == period_label)
    ]
    if not records:
        return None
    total_spend = sum(b.amount_usd for b in records)
    total_users = sum(b.active_users for b in records)
    if total_users == 0:
        return None
    return round(total_spend / total_users, 2)


# ---------------------------------------------------------------- quality

def ai_test_pr_pct(store: Store, division_id, start, end) -> Optional[float]:
    prs = [
        pr for pr in store.get("pull_request")
        if _in_period(pr.merged_at, start, end)
        and _division_matches(store.division_of_repo(pr.repo_id), division_id)
    ]
    if not prs:
        return None
    return _pct(sum(1 for pr in prs if pr.ai_test_generated), len(prs))


def ai_review_gate_pct(store: Store, division_id, start, end) -> Optional[float]:
    prs = [
        pr for pr in store.get("pull_request")
        if _in_period(pr.merged_at, start, end)
        and pr.ai_review_passed is not None
        and _division_matches(store.division_of_repo(pr.repo_id), division_id)
    ]
    if not prs:
        return None
    return _pct(sum(1 for pr in prs if pr.ai_review_passed), len(prs))


def vulns_escaped_per_quarter(store: Store, division_id, start, end) -> Optional[float]:
    vulns = [
        v for v in store.get("vulnerability")
        if v.severity in ("critical", "high") and v.ai_generated_code and v.reached_prod
        and _in_period(v.detected_at, start, end)
        and _division_matches(store.division_of_repo(v.repo_id), division_id)
    ]
    return float(len(vulns))


# ----------------------------------------------------------------- health

def composite_score(store: Store, division_id, start, end, weights: Optional[dict] = None) -> Optional[float]:
    weights = weights or {
        "test_coverage": 0.30, "complexity_coupling": 0.25, "dead_code": 0.15,
        "dependency_freshness": 0.15, "doc_coverage": 0.15,
    }
    latest_by_repo: dict[str, object] = {}
    for snap in store.get("code_health_snapshot"):
        if not _in_period_date(snap.snapshot_at, start, end):
            continue
        if not _division_matches(store.division_of_repo(snap.repo_id), division_id):
            continue
        prev = latest_by_repo.get(snap.repo_id)
        if prev is None or snap.snapshot_at > prev.snapshot_at:
            latest_by_repo[snap.repo_id] = snap
    if not latest_by_repo:
        return None

    scores = []
    for snap in latest_by_repo.values():
        parts, total_w = 0.0, 0.0
        fields = {
            "test_coverage": snap.test_coverage_pct,
            "complexity_coupling": snap.complexity_score,
            "dead_code": (100 - snap.dead_code_pct) if snap.dead_code_pct is not None else None,
            "dependency_freshness": snap.dependency_freshness_pct,
            "doc_coverage": snap.doc_coverage_pct,
        }
        for key, val in fields.items():
            if val is None:
                continue
            parts += val * weights.get(key, 0)
            total_w += weights.get(key, 0)
        if total_w > 0:
            scores.append(parts / total_w)
    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def _in_period_date(d, start, end) -> bool:
    if d is None:
        return False
    return start.date() <= d <= end.date()


REGISTRY = {
    "weekly_active_usage": weekly_active_usage,
    "ai_pr_share": ai_pr_share,
    "training_pct": training_pct,
    "deploy_frequency_per_week": deploy_frequency_per_week,
    "lead_time_hours": lead_time_hours,
    "change_failure_rate_pct": change_failure_rate_pct,
    "mttr_hours": mttr_hours,
    "credit_utilization_pct": credit_utilization_pct,
    "spend_per_active_user_usd": spend_per_active_user_usd,
    "ai_test_pr_pct": ai_test_pr_pct,
    "ai_review_gate_pct": ai_review_gate_pct,
    "vulns_escaped_per_quarter": vulns_escaped_per_quarter,
    "composite_score": composite_score,
}
