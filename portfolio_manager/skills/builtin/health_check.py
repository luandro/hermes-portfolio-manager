"""Health-check skill — inspects project health from the state DB."""

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
    id="health_check",
    name="Health Check",
    description="Check project health status",
    default_interval_hours=24,
    default_enabled=True,
    supports_issue_drafts=False,
    required_state=[],
    allowed_commands=[],
    config_schema={},
)


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Query the state DB for project health and surface unhealthy projects."""
    findings: list[MaintenanceFinding] = []

    try:
        cur = ctx.conn.execute("SELECT id, status FROM projects WHERE status NOT IN ('active', 'paused')")
        rows = cur.fetchall()
    except Exception:
        rows = []

    for row in rows:
        project_id, status = row[0], row[1]
        fp = make_finding_fingerprint(
            skill_id=SPEC.id,
            project_id=ctx.project.id,
            source_type="project",
            source_id=project_id,
            key=f"status:{status}",
        )
        findings.append(
            MaintenanceFinding(
                fingerprint=fp,
                severity="medium",
                title=f"Project {project_id} has status: {status}",
                body=f"Project {project_id} is in '{status}' state, which may need attention.",
                source_type="project",
                source_id=project_id,
                source_url=None,
                metadata={"status": status},
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Checked project health: {len(findings)} issue(s) found",
    )


REGISTRY.register(SPEC, execute)
