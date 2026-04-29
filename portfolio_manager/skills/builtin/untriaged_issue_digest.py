"""Untriaged-issue digest skill."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
    make_finding_fingerprint,
)
from portfolio_manager.maintenance_registry import REGISTRY

SPEC = MaintenanceSkillSpec(
    id="untriaged_issue_digest",
    name="Untriaged Issue Digest",
    description="Find open issues in local state that still need triage",
    default_interval_hours=24,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=["issues"],
    allowed_commands=[],
    config_schema={
        "min_age_hours": {"type": "integer", "default": 24},
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


def _int_config(ctx: MaintenanceContext, key: str, default: int) -> int:
    try:
        value = int(ctx.skill_config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Find needs-triage issues older than the configured age."""
    min_age_hours = _int_config(ctx, "min_age_hours", 24)
    max_findings = _int_config(ctx, "max_findings", 20)
    cutoff = ctx.now.astimezone(UTC) - timedelta(hours=min_age_hours)
    medium_cutoff = ctx.now.astimezone(UTC) - timedelta(days=14)

    cur = ctx.conn.execute(
        "SELECT issue_number, title, state, last_seen_at, updated_at FROM issues "
        "WHERE project_id=? AND state='needs_triage'",
        (ctx.project.id,),
    )
    candidates = []
    for issue_number, title, state, last_seen_at, updated_at in cur.fetchall():
        seen_at = _parse_timestamp(last_seen_at) or _parse_timestamp(updated_at)
        if seen_at is not None and seen_at < cutoff:
            candidates.append((seen_at, issue_number, title, state, last_seen_at, updated_at))

    candidates.sort(key=lambda row: (row[0], row[1]))
    findings: list[MaintenanceFinding] = []
    for seen_at, issue_number, title, state, last_seen_at, updated_at in candidates[:max_findings]:
        source_id = str(issue_number)
        severity: Literal["low", "medium"] = "medium" if seen_at < medium_cutoff else "low"
        finding_title = f"Untriaged issue #{issue_number}: {title}"
        findings.append(
            MaintenanceFinding(
                fingerprint=make_finding_fingerprint(SPEC.id, ctx.project.id, "issue", source_id, source_id),
                severity=severity,
                title=finding_title,
                body=(
                    f"Issue #{issue_number} is still marked needs_triage and was last seen at "
                    f"{last_seen_at or updated_at}."
                ),
                source_type="issue",
                source_id=source_id,
                source_url=f"https://github.com/{ctx.project.github.owner}/{ctx.project.github.repo}/issues/{issue_number}",
                metadata={
                    "issue_number": issue_number,
                    "state": state,
                    "last_seen_at": last_seen_at,
                    "updated_at": updated_at,
                    "min_age_hours": min_age_hours,
                },
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Untriaged issue digest complete: {len(findings)} issue(s) found",
    )


REGISTRY.register(SPEC, execute)
