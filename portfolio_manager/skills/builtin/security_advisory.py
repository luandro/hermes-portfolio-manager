"""Security-advisory skill — checks for known CVEs."""

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
    id="security_advisory",
    name="Security Advisory",
    description="Check for security advisories",
    default_interval_hours=24,
    default_enabled=True,
    supports_issue_drafts=True,
    required_state=[],
    allowed_commands=[],
    config_schema={},
)


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Check for security advisories recorded in the state DB."""
    findings: list[MaintenanceFinding] = []

    try:
        cur = ctx.conn.execute(
            "SELECT cve_id, severity, summary FROM security_advisories WHERE project_id=?",
            (ctx.project.id,),
        )
        rows = cur.fetchall()
    except Exception:
        rows = []

    for row in rows:
        cve_id, severity, summary = row[0], row[1], row[2]
        safe_summary = summary or "No advisory summary provided."
        fp = make_finding_fingerprint(
            skill_id=SPEC.id,
            project_id=ctx.project.id,
            source_type="cve",
            source_id=cve_id,
            key=cve_id,
        )
        findings.append(
            MaintenanceFinding(
                fingerprint=fp,
                severity=severity,
                title=f"Security advisory: {cve_id}",
                body=safe_summary,
                source_type="cve",
                source_id=cve_id,
                source_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                metadata={"cve_id": cve_id},
            )
        )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Security advisory check complete: {len(findings)} advisory(ies) found",
    )


REGISTRY.register(SPEC, execute)
