"""License-compliance skill — checks for problematic licenses."""

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
    id="license_compliance",
    name="License Compliance",
    description="Check license compliance",
    default_interval_hours=168,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=[],
    allowed_commands=[],
    config_schema={},
)


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Check for license issues recorded in the state DB."""
    findings: list[MaintenanceFinding] = []

    try:
        cur = ctx.conn.execute(
            "SELECT name, version, license FROM dependency_licenses WHERE project_id=?",
            (ctx.project.id,),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []

    for row in rows:
        name, version, license_id = row[0], row[1], row[2]
        fp = make_finding_fingerprint(
            skill_id=SPEC.id,
            project_id=ctx.project.id,
            source_type="license",
            source_id=f"{name}@{version}",
            key=license_id,
        )
        findings.append(
            MaintenanceFinding(
                fingerprint=fp,
                severity="low",
                title=f"License issue: {name}@{version} uses {license_id}",
                body=f"Package {name} at version {version} is licensed under {license_id}.",
                source_type="license",
                source_id=f"{name}@{version}",
                source_url=None,
                metadata={"package": name, "version": version, "license": license_id},
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"License compliance check complete: {len(findings)} issue(s) found",
    )


REGISTRY.register(SPEC, execute)
