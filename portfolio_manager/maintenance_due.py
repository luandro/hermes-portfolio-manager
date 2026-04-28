"""Due computation for maintenance checks — Phase 4."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3


def compute_due_checks(
    conn: sqlite3.Connection,
    config: dict[str, Any] | None = None,
    project_filter: list[str] | None = None,
    skill_filter: list[str] | None = None,
    include_paused: bool = False,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Compute which project+skill combinations are due for a maintenance run.

    Returns a list of dicts, each with:
        project_id, skill_id, is_due, reason, last_run_at
    """
    config = config or {}
    skills_cfg = config.get("skills", {})

    # 1. Gather projects
    conditions: list[str] = []
    params: list[Any] = []

    if not include_paused:
        conditions.append("status != 'paused'")
    if not include_archived:
        conditions.append("status != 'archived'")
    if project_filter is not None:
        if not project_filter:
            return []
        placeholders = ",".join("?" for _ in project_filter)
        conditions.append(f"id IN ({placeholders})")
        params.extend(project_filter)

    where = " AND ".join(conditions) if conditions else "1=1"
    cur = conn.execute(f"SELECT id, status FROM projects WHERE {where}", params)  # nosec B608
    projects = cur.fetchall()

    # 2. Determine which skills to check
    skill_ids = list(skills_cfg.keys())
    if skill_filter is not None:
        skill_ids = [s for s in skill_ids if s in skill_filter]

    now = datetime.now(UTC)
    results: list[dict[str, Any]] = []

    for project_id, _project_status in projects:
        for skill_id in skill_ids:
            skill_cfg = skills_cfg[skill_id]
            enabled = skill_cfg.get("enabled", True)

            if not enabled:
                results.append(
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "is_due": False,
                        "reason": "disabled",
                        "last_run_at": None,
                    }
                )
                continue

            # Check last successful run
            cur = conn.execute(
                "SELECT finished_at FROM maintenance_runs "
                "WHERE project_id=? AND skill_id=? AND status='success' "
                "ORDER BY finished_at DESC LIMIT 1",
                (project_id, skill_id),
            )
            row = cur.fetchone()

            if row is None:
                results.append(
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "is_due": True,
                        "reason": "never_run",
                        "last_run_at": None,
                    }
                )
                continue

            last_finished_str = row[0]
            last_run_at = last_finished_str
            try:
                last_finished = datetime.fromisoformat(last_finished_str)
                if last_finished.tzinfo is None:
                    last_finished = last_finished.replace(tzinfo=UTC)
            except (ValueError, TypeError):
                results.append(
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "is_due": True,
                        "reason": "never_run",
                        "last_run_at": last_run_at,
                    }
                )
                continue

            interval_hours = skill_cfg.get("interval_hours", 24)
            next_due = last_finished + timedelta(hours=interval_hours)

            if now >= next_due:
                results.append(
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "is_due": True,
                        "reason": "interval_elapsed",
                        "last_run_at": last_run_at,
                    }
                )
            else:
                results.append(
                    {
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "is_due": False,
                        "reason": "not_due_yet",
                        "last_run_at": last_run_at,
                    }
                )

    return results
