"""Stale-branches skill — finds branches with no recent activity."""

from __future__ import annotations

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
    make_finding_fingerprint,
)
from portfolio_manager.maintenance_registry import REGISTRY

SPEC = MaintenanceSkillSpec(
    id="stale_branches",
    name="Stale Branches",
    description="Find stale branches",
    default_interval_hours=168,
    default_enabled=True,
    supports_issue_drafts=False,
    required_state=[],
    allowed_commands=[],
    config_schema={},
)


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Find stale branches recorded in the state DB."""
    findings: list[MaintenanceFinding] = []

    try:
        cur = ctx.conn.execute(
            "SELECT branch_name, last_activity FROM stale_branches WHERE project_id=?",
            (ctx.project.id,),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []

    for row in rows:
        branch_name, last_activity = row[0], row[1]
        fp = make_finding_fingerprint(
            skill_id=SPEC.id,
            project_id=ctx.project.id,
            source_type="branch",
            source_id=branch_name,
            key="stale",
        )
        findings.append(
            MaintenanceFinding(
                fingerprint=fp,
                severity="info",
                title=f"Stale branch: {branch_name}",
                body=f"Branch {branch_name} last active at {last_activity}.",
                source_type="branch",
                source_id=branch_name,
                source_url=None,
                metadata={"branch": branch_name, "last_activity": last_activity},
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Stale branch scan complete: {len(findings)} branch(es) found",
    )


REGISTRY.register(SPEC, execute)
