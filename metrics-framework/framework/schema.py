"""
Semantic entity schema for the AI Engineering Maturity Framework.

This is the common vocabulary every adapter normalizes *into*. Adapters know
about GitHub/Jira/CSV/warehouse-specific shapes; nothing downstream of
normalization (the store, the metrics engine) knows about any source system.

Every entity is a plain dataclass with a small, fixed set of required fields.
Optional fields default to None and metrics that need them degrade gracefully
(a metric with missing inputs is reported as "insufficient_data", not zero).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass
class Person:
    id: str
    email: str
    division_id: Optional[str] = None
    team: Optional[str] = None
    role: Optional[str] = None
    name: Optional[str] = None


@dataclass
class Division:
    id: str
    name: str


@dataclass
class Repo:
    id: str
    name: str
    division_id: Optional[str] = None


@dataclass
class PullRequest:
    id: str
    repo_id: str
    author_id: Optional[str] = None
    opened_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    ai_assisted: bool = False          # AI co-authorship signal present
    ai_test_generated: bool = False    # includes AI-authored test coverage
    ai_review_passed: Optional[bool] = None  # passed an automated AI review gate pre-merge
    lines_changed: Optional[int] = None


@dataclass
class Deploy:
    id: str
    repo_id: str
    deployed_at: datetime
    environment: str = "production"
    is_prod: bool = True
    status: str = "success"            # success | failed | rolled_back


@dataclass
class Incident:
    id: str
    opened_at: datetime
    resolved_at: Optional[datetime] = None
    severity: Optional[str] = None     # P1 | P2 | P3 | P4
    repo_id: Optional[str] = None
    division_id: Optional[str] = None
    caused_by_deploy_id: Optional[str] = None


@dataclass
class Vulnerability:
    id: str
    detected_at: datetime
    severity: str                      # critical | high | medium | low
    repo_id: Optional[str] = None
    ai_generated_code: bool = False
    reached_prod: bool = False


@dataclass
class Defect:
    """A post-release bug, used to compute the AI-touched vs human-only escaped defect ratio."""
    id: str
    opened_at: datetime
    repo_id: Optional[str] = None
    ai_touched: bool = False


@dataclass
class AIUsageEvent:
    """One AI-assisted coding session (IDE/CLI telemetry)."""
    id: str
    person_id: str
    tool: str                          # e.g. claude-code, copilot, cursor
    occurred_at: datetime
    accepted_output: bool = True


@dataclass
class AISeat:
    """A provisioned AI tool license/seat, and whether it saw activity in the trailing window."""
    person_id: str
    tool: str
    provisioned: bool = True
    active_last_30d: bool = False


@dataclass
class BillingRecord:
    period: str                        # e.g. "2026-Q2"
    tool: str
    division_id: Optional[str]
    amount_usd: float
    active_users: int = 0


@dataclass
class TrainingRecord:
    person_id: str
    program: str
    completed_at: datetime


@dataclass
class CodeHealthSnapshot:
    repo_id: str
    snapshot_at: date
    test_coverage_pct: Optional[float] = None
    complexity_score: Optional[float] = None      # 0-100, higher = healthier (already inverted)
    dead_code_pct: Optional[float] = None          # lower is better; converted at scoring time
    dependency_freshness_pct: Optional[float] = None
    doc_coverage_pct: Optional[float] = None


ENTITY_TYPES = {
    "person": Person,
    "division": Division,
    "repo": Repo,
    "pull_request": PullRequest,
    "deploy": Deploy,
    "incident": Incident,
    "vulnerability": Vulnerability,
    "defect": Defect,
    "ai_usage_event": AIUsageEvent,
    "ai_seat": AISeat,
    "billing_record": BillingRecord,
    "training_record": TrainingRecord,
    "code_health_snapshot": CodeHealthSnapshot,
}
