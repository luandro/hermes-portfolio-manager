"""Maintenance issue draft planning, creation, and repair — Phase 5.

Provides pure planning logic for deciding which maintenance findings should
produce local issue drafts, creation via MVP 3 helpers, and crash-recovery
repair for partial draft creation.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from portfolio_manager.maintenance_models import MaintenanceFinding, MaintenanceSkillResult

from portfolio_manager.issue_drafts import create_issue_draft
from portfolio_manager.maintenance_artifacts import redact_secrets, write_artifact

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 5.1 DraftPlan dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DraftPlan:
    """Plan for creating one local issue draft from maintenance findings."""

    project_id: str
    skill_id: str
    run_id: str
    findings: list[Any]  # list[MaintenanceFinding]
    should_create: bool


# ---------------------------------------------------------------------------
# 5.1 plan_maintenance_issue_drafts — pure logic, no side effects
# ---------------------------------------------------------------------------


def plan_maintenance_issue_drafts(
    findings_by_project_skill_run: dict[tuple[str, str, str], MaintenanceSkillResult],
    config: dict[str, Any],
    *,
    conn: sqlite3.Connection | None = None,
) -> list[DraftPlan]:
    """Decide which project/skill/run combos should produce issue drafts.

    Rules:
      - config ``create_issue_drafts`` must be True
      - At least one finding must have ``draftable=True``
      - Findings with ``issue_draft_id`` already set in DB are skipped
      - One draft per (project_id, skill_id, run_id) combination

    Pure logic — no side effects, no MVP 3 calls.
    """
    if not config.get("create_issue_drafts", False):
        return []

    plans: list[DraftPlan] = []

    for (project_id, skill_id, run_id), result in findings_by_project_skill_run.items():
        draftable_findings: list[MaintenanceFinding] = []

        for finding in result.findings:
            if not finding.draftable:
                continue

            # Check if finding already has an issue_draft_id in DB
            if conn is not None:
                row = conn.execute(
                    "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint=? AND issue_draft_id IS NOT NULL LIMIT 1",
                    (finding.fingerprint,),
                ).fetchone()
                if row and row[0]:
                    continue

            draftable_findings.append(finding)

        if draftable_findings:
            plans.append(
                DraftPlan(
                    project_id=project_id,
                    skill_id=skill_id,
                    run_id=run_id,
                    findings=draftable_findings,
                    should_create=True,
                )
            )

    return plans


# ---------------------------------------------------------------------------
# 5.2 create_maintenance_drafts — local drafts via MVP 3 helpers
# ---------------------------------------------------------------------------

# Keys to strip from finding metadata when building draft body
_PRIVATE_META_KEYS = frozenset(
    {
        "internal_notes",
        "chain_of_thought",
        "private_metadata",
        "cot",
    }
)


def _build_draft_body(plan: DraftPlan) -> str:
    """Build a clean draft body from findings, excluding private metadata."""
    parts: list[str] = []

    parts.append("## Goal")
    parts.append(f"Summarize maintenance findings for {plan.skill_id} on {plan.project_id}.")
    parts.append("")

    parts.append("## Why This Matters")
    parts.append("Automated maintenance checks detected items that may need attention.")
    parts.append("")

    parts.append("## Findings")
    for f in plan.findings:
        parts.append(f"### {f.title}")
        parts.append(f"- **Severity**: {f.severity}")
        if f.body:
            # Exclude private metadata and chain-of-thought from body
            safe_body = f.body
            for key in _PRIVATE_META_KEYS:
                # Redact full "key: value" pairs to prevent leaking values after key removal
                safe_body = re.sub(rf"^.*\b{re.escape(key)}\b.*$", "", safe_body, flags=re.MULTILINE)
            safe_body = "\n".join(line for line in safe_body.split("\n") if line.strip())
            parts.append(safe_body)
        if f.source_url:
            parts.append(f"- **Source**: {f.source_url}")
        parts.append("")

    parts.append("## Suggested Manual Next Step")
    parts.append("Review findings and decide whether to create a GitHub issue or resolve locally.")
    parts.append("")

    parts.append("## Acceptance Criteria")
    parts.append("- All findings reviewed")
    parts.append("- Action taken (issue created, dismissed, or resolved)")
    parts.append("")

    parts.append("## Source Maintenance Run ID")
    parts.append(plan.run_id)

    return redact_secrets("\n".join(parts))


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Strip private keys from metadata dict."""
    return {k: v for k, v in metadata.items() if k not in _PRIVATE_META_KEYS}


def create_maintenance_drafts(
    root: Path,
    conn: sqlite3.Connection,
    draft_plans: list[DraftPlan],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create local issue drafts for each DraftPlan using MVP 3 helpers.

    For each plan:
      - Build draft body (goal, findings, acceptance criteria, run_id)
      - Exclude private metadata and chain-of-thought
      - Call MVP 3 ``create_issue_draft`` helper
      - On success: update finding.issue_draft_id in DB, write draft-created.json
      - On failure: record warning, don't lose findings

    NEVER publishes to GitHub. Only creates local drafts via MVP 3 helpers.
    """
    results: list[dict[str, Any]] = []

    for plan in draft_plans:
        if not plan.should_create:
            continue

        body = _build_draft_body(plan)
        title = f"Maintenance: {plan.skill_id} findings for {plan.project_id}"

        try:
            draft_result = create_issue_draft(
                root,
                conn,
                body,
                project_ref=plan.project_id,
                title=title,
            )
        except Exception as exc:
            logger.warning("Draft creation failed for %s/%s: %s", plan.project_id, plan.skill_id, exc)
            results.append(
                {
                    "project_id": plan.project_id,
                    "skill_id": plan.skill_id,
                    "run_id": plan.run_id,
                    "warning": f"Draft creation failed: {exc}",
                }
            )
            continue

        if draft_result.get("blocked"):
            reason = draft_result.get("reason", "unknown")
            logger.warning(
                "Draft creation blocked for %s/%s: %s",
                plan.project_id,
                plan.skill_id,
                reason,
            )
            results.append(
                {
                    "project_id": plan.project_id,
                    "skill_id": plan.skill_id,
                    "run_id": plan.run_id,
                    "warning": f"Draft blocked: {reason}",
                }
            )
            continue

        draft_id = draft_result.get("draft_id")
        if not draft_id:
            results.append(
                {
                    "project_id": plan.project_id,
                    "skill_id": plan.skill_id,
                    "run_id": plan.run_id,
                    "warning": "Draft creation failed: missing draft_id",
                }
            )
            continue

        # Update findings in DB with issue_draft_id
        for finding in plan.findings:
            conn.execute(
                "UPDATE maintenance_findings SET issue_draft_id=? WHERE fingerprint=? AND (issue_draft_id IS NULL OR issue_draft_id = '')",
                (draft_id, finding.fingerprint),
            )
        conn.commit()

        # Write draft-created.json artifact
        first_fingerprint = plan.findings[0].fingerprint if plan.findings else ""
        draft_created_data = {
            "finding_fingerprint": first_fingerprint,
            "project_id": plan.project_id,
            "skill_id": plan.skill_id,
            "draft_id": draft_id,
            "draft_artifact_path": draft_result.get("artifact_path", ""),
        }
        write_artifact(root, plan.run_id, "draft-created.json", json.dumps(draft_created_data, indent=2))

        results.append(
            {
                "project_id": plan.project_id,
                "skill_id": plan.skill_id,
                "run_id": plan.run_id,
                "draft_id": draft_id,
            }
        )

    return results


# ---------------------------------------------------------------------------
# 5.3 repair_draft_references — crash recovery
# ---------------------------------------------------------------------------


def repair_draft_references(root: Path, conn: sqlite3.Connection) -> int:
    """Scan draft-created.json artifacts and repair missing SQLite references.

    For each maintenance run artifact dir that has a draft-created.json:
      - If the referenced finding is missing issue_draft_id in SQLite, update it.
      - If the finding already has an issue_draft_id, skip (no duplicate).
      - If the artifact is missing or invalid, skip silently.

    Returns count of repairs made.
    """
    base_dir = root / "artifacts" / "maintenance"
    if not base_dir.is_dir():
        return 0

    repairs = 0

    for run_dir in base_dir.iterdir():
        if not run_dir.is_dir():
            continue

        draft_created_path = run_dir / "draft-created.json"
        if not draft_created_path.is_file():
            continue

        try:
            data = json.loads(draft_created_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        fingerprint = data.get("finding_fingerprint")
        draft_id = data.get("draft_id")
        if not fingerprint or not draft_id:
            continue

        # Check if finding already has issue_draft_id
        row = conn.execute(
            "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint=?",
            (fingerprint,),
        ).fetchone()
        if row is None:
            continue

        existing_draft_id = row[0]
        if existing_draft_id:
            # Already has a reference — don't duplicate
            continue

        conn.execute(
            "UPDATE maintenance_findings SET issue_draft_id=? WHERE fingerprint=?",
            (draft_id, fingerprint),
        )
        conn.commit()
        repairs += 1

    return repairs
