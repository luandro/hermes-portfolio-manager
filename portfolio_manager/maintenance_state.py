"""State helpers for MVP 4 maintenance runs."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3


def start_run(
    conn: sqlite3.Connection,
    project_id: str,
    skill_id: str,
    now: datetime | None = None,
) -> str:
    """Create a new maintenance run row. Returns run_id."""
    run_id = uuid.uuid4().hex[:12]
    ts = (now or datetime.now(UTC)).isoformat()
    conn.execute(
        "INSERT INTO maintenance_runs (run_id, project_id, skill_id, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (run_id, project_id, skill_id, ts),
    )
    conn.commit()
    return run_id


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    summary: str = "",
    reason: str | None = None,
) -> None:
    """Mark a maintenance run as finished."""
    ts = datetime.now(UTC).isoformat()
    conn.execute(
        "UPDATE maintenance_runs SET status=?, finished_at=?, summary=?, reason=? WHERE run_id=?",
        (status, ts, summary, reason, run_id),
    )
    conn.commit()


def insert_finding(
    conn: sqlite3.Connection,
    run_id: str,
    fingerprint: str,
    severity: str,
    title: str,
    body: str = "",
    source_type: str = "",
    source_id: str | None = None,
    source_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    draftable: bool = True,
) -> int:
    """Insert a maintenance finding. Returns finding_id."""
    meta_json = json.dumps(metadata or {})
    cur = conn.execute(
        "INSERT INTO maintenance_findings (run_id, fingerprint, severity, title, body, source_type, source_id, source_url, metadata_json, draftable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, fingerprint, severity, title, body, source_type, source_id, source_url, meta_json, int(draftable)),
    )
    conn.commit()
    return cur.lastrowid or 0


def get_findings_by_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Get all findings for a run."""
    cur = conn.execute("SELECT * FROM maintenance_findings WHERE run_id=?", (run_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]


def get_latest_successful_run(
    conn: sqlite3.Connection,
    project_id: str,
    skill_id: str,
) -> dict[str, Any] | None:
    """Get the latest successful run for a project+skill combo."""
    cur = conn.execute(
        "SELECT * FROM maintenance_runs WHERE project_id=? AND skill_id=? AND status='success' ORDER BY finished_at DESC LIMIT 1",
        (project_id, skill_id),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row, strict=False)) if row else None


def recover_stale_runs(
    conn: sqlite3.Connection,
    max_age_hours: int = 2,
) -> list[str]:
    """Mark stale 'running' runs as 'failed'. Returns recovered run_ids."""
    cutoff_dt = datetime.now(UTC) - timedelta(hours=max_age_hours)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")
    cur = conn.execute(
        "SELECT run_id FROM maintenance_runs WHERE status='running' AND started_at < ?",
        (cutoff_str,),
    )
    stale_ids = [row[0] for row in cur.fetchall()]
    now_iso = datetime.now(UTC).isoformat()
    for rid in stale_ids:
        conn.execute(
            "UPDATE maintenance_runs SET status='failed', finished_at=?, reason='stale recovery' WHERE run_id=?",
            (now_iso, rid),
        )
    conn.commit()
    return stale_ids
