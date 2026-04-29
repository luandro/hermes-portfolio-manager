"""Open-PR health skill."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
)
from portfolio_manager.maintenance_registry import REGISTRY

SPEC = MaintenanceSkillSpec(
    id="open_pr_health",
    name="Open PR Health",
    description="Summarize open pull requests needing attention",
    default_interval_hours=12,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=["pull_requests"],
    allowed_commands=[],
    config_schema={
        "stale_after_days": {"type": "integer", "default": 7},
        "include_review_pending": {"type": "boolean", "default": True},
        "include_checks_failed": {"type": "boolean", "default": True},
        "include_changes_requested": {"type": "boolean", "default": True},
        "max_findings": {"type": "integer", "default": 20},
        "create_issue_drafts": {"type": "boolean", "default": False},
    },
)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalized_title(title: str) -> str:
    return " ".join(title.lower().split())


def _fingerprint(project_id: str, source_type: str, source_id: str, title: str) -> str:
    raw = f"{project_id}{SPEC.id}{source_type}{source_id}{_normalized_title(title)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _bool_config(ctx: MaintenanceContext, key: str, default: bool) -> bool:
    value = ctx.skill_config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_config(ctx: MaintenanceContext, key: str, default: int) -> int:
    try:
        value = int(ctx.skill_config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Find open PRs with failed checks, requested changes, or stale review waits."""
    stale_after_days = _int_config(ctx, "stale_after_days", 7)
    max_findings = _int_config(ctx, "max_findings", 20)
    include_review_pending = _bool_config(ctx, "include_review_pending", True)
    include_checks_failed = _bool_config(ctx, "include_checks_failed", True)
    include_changes_requested = _bool_config(ctx, "include_changes_requested", True)
    cutoff = ctx.now.astimezone(UTC) - timedelta(days=stale_after_days)

    cur = ctx.conn.execute(
        "SELECT pr_number, title, review_stage, last_seen_at, updated_at FROM pull_requests "
        "WHERE project_id=? AND state='open'",
        (ctx.project.id,),
    )
    candidates = []
    for pr_number, title, review_stage, last_seen_at, updated_at in cur.fetchall():
        stage = review_stage or ""
        activity_at = _parse_timestamp(updated_at) or _parse_timestamp(last_seen_at)
        severity: str | None = None
        if stage == "checks_failed" and include_checks_failed:
            severity = "high"
        elif stage == "changes_requested" and include_changes_requested:
            severity = "medium"
        elif stage == "review_pending" and include_review_pending and activity_at is not None and activity_at < cutoff:
            severity = "low"

        if severity is not None:
            candidates.append(
                (activity_at or ctx.now.astimezone(UTC), pr_number, title, stage, severity, last_seen_at, updated_at)
            )

    candidates.sort(key=lambda row: (row[0], row[1]))
    findings: list[MaintenanceFinding] = []
    for _activity_at, pr_number, title, stage, severity, last_seen_at, updated_at in candidates[:max_findings]:
        source_id = str(pr_number)
        finding_title = f"Open PR #{pr_number} needs attention: {title}"
        findings.append(
            MaintenanceFinding(
                fingerprint=_fingerprint(ctx.project.id, "pull_request", source_id, finding_title),
                severity=severity,
                title=finding_title,
                body=f"PR #{pr_number} is open with review stage {stage}. Last updated at {updated_at or last_seen_at}.",
                source_type="pull_request",
                source_id=source_id,
                source_url=f"https://github.com/{ctx.project.github.owner}/{ctx.project.github.repo}/pull/{pr_number}",
                metadata={
                    "pr_number": pr_number,
                    "review_stage": stage,
                    "last_seen_at": last_seen_at,
                    "updated_at": updated_at,
                    "stale_after_days": stale_after_days,
                },
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Open PR health complete: {len(findings)} PR(s) found",
    )


REGISTRY.register(SPEC, execute)
