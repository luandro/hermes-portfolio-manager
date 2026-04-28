"""Dry-run maintenance planning — Phase 4, Task 4.2."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from portfolio_manager.maintenance_due import compute_due_checks

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


def plan_maintenance_run(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    root: Path | None = None,
    project_filter: list[str] | None = None,
    skill_filter: list[str] | None = None,
) -> dict[str, Any]:
    """Compute what a maintenance run WOULD do, without side effects.

    Does NOT insert rows, write files, or run commands.
    Returns {planned_checks, skipped, summary, would_create_issue_drafts}.
    """
    due_checks = compute_due_checks(
        conn,
        config=config,
        project_filter=project_filter,
        skill_filter=skill_filter,
    )

    planned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for check in due_checks:
        if check["is_due"]:
            planned.append(check)
        else:
            skipped.append(check)

    # Determine if any skill has create_issue_drafts enabled
    skills_cfg = config.get("skills", {})
    would_create = any(skills_cfg.get(sid, {}).get("create_issue_drafts", False) for sid in skills_cfg)

    return {
        "planned_checks": planned,
        "skipped": skipped,
        "summary": {
            "total_checks": len(due_checks),
            "planned": len(planned),
            "skipped": len(skipped),
        },
        "would_create_issue_drafts": would_create,
    }
