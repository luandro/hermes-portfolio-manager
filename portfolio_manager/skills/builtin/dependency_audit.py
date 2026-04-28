"""Dependency-audit skill — scans for dependency vulnerabilities."""

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
    id="dependency_audit",
    name="Dependency Audit",
    description="Audit dependencies for vulnerabilities",
    default_interval_hours=168,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=[],
    allowed_commands=[],
    config_schema={},
)


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Scan for dependency issues recorded in the state DB."""
    findings: list[MaintenanceFinding] = []

    try:
        cur = ctx.conn.execute(
            "SELECT name, version, severity FROM dependency_issues WHERE project_id=?",
            (ctx.project.id,),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []

    for row in rows:
        name, version, severity = row[0], row[1], row[2]
        fp = make_finding_fingerprint(
            skill_id=SPEC.id,
            project_id=ctx.project.id,
            source_type="dependency",
            source_id=f"{name}@{version}",
            key=f"{name}@{version}",
        )
        findings.append(
            MaintenanceFinding(
                fingerprint=fp,
                severity=severity,
                title=f"Vulnerable dependency: {name}@{version}",
                body=f"Package {name} at version {version} has severity {severity}.",
                source_type="dependency",
                source_id=f"{name}@{version}",
                source_url=None,
                metadata={"package": name, "version": version},
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Dependency audit complete: {len(findings)} issue(s) found",
    )


REGISTRY.register(SPEC, execute)
