"""Stale-issue digest skill."""

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

OPEN_STATES = ("open", "needs_triage")

SPEC = MaintenanceSkillSpec(
    id="stale_issue_digest",
    name="Stale Issue Digest",
    description="Find open issues in local state that have not been updated recently",
    default_interval_hours=168,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=["issues"],
    allowed_commands=[],
    config_schema={
        "stale_after_days": {"type": "integer", "default": 30},
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


def _int_config(ctx: MaintenanceContext, key: str, default: int) -> int:
    try:
        value = int(ctx.skill_config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Find locally open issues older than the configured stale threshold."""
    stale_after_days = _int_config(ctx, "stale_after_days", 30)
    max_findings = _int_config(ctx, "max_findings", 20)
    now = ctx.now.astimezone(UTC)
    cutoff = now - timedelta(days=stale_after_days)
    medium_cutoff = now - timedelta(days=stale_after_days * 2)

    cur = ctx.conn.execute(
        "SELECT issue_number, title, state, last_seen_at, updated_at FROM issues "
        "WHERE project_id=? AND state IN (?, ?)",
        (ctx.project.id, *OPEN_STATES),
    )
    candidates = []
    for issue_number, title, state, last_seen_at, updated_at in cur.fetchall():
        activity_at = _parse_timestamp(updated_at) or _parse_timestamp(last_seen_at)
        if activity_at is not None and activity_at < cutoff:
            candidates.append((activity_at, issue_number, title, state, last_seen_at, updated_at))

    candidates.sort(key=lambda row: (row[0], row[1]))
    findings: list[MaintenanceFinding] = []
    for activity_at, issue_number, title, state, last_seen_at, updated_at in candidates[:max_findings]:
        source_id = str(issue_number)
        severity = "medium" if activity_at < medium_cutoff else "low"
        finding_title = f"Stale issue #{issue_number}: {title}"
        findings.append(
            MaintenanceFinding(
                fingerprint=_fingerprint(ctx.project.id, "issue", source_id, finding_title),
                severity=severity,
                title=finding_title,
                body=f"Issue #{issue_number} is open and has not been updated since {updated_at or last_seen_at}.",
                source_type="issue",
                source_id=source_id,
                source_url=f"https://github.com/{ctx.project.github.owner}/{ctx.project.github.repo}/issues/{issue_number}",
                metadata={
                    "issue_number": issue_number,
                    "state": state,
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
        summary=f"Stale issue digest complete: {len(findings)} issue(s) found",
    )


REGISTRY.register(SPEC, execute)
