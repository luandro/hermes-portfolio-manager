"""State helpers for MVP 4 maintenance runs."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3


RUN_STATUSES = frozenset({"planned", "running", "success", "skipped", "blocked", "failed"})
FINDING_STATUSES = frozenset({"open", "resolved", "draft_created", "ignored"})


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row, strict=False))


def _rows_to_dicts(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]


def _validate_run_status(status: str) -> None:
    if status not in RUN_STATUSES:
        raise ValueError(f"Invalid maintenance run status: {status!r}. Valid: {sorted(RUN_STATUSES)}")


def _validate_finding_status(status: str) -> None:
    if status not in FINDING_STATUSES:
        raise ValueError(f"Invalid maintenance finding status: {status!r}. Valid: {sorted(FINDING_STATUSES)}")


def _metadata_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value or {}, sort_keys=True)


def start_maintenance_run(conn: sqlite3.Connection, run: dict[str, Any]) -> str:
    """Insert a new maintenance run. Returns the run id."""
    run_id = run.get("id") or uuid.uuid4().hex[:12]
    status = run.get("status", "running")
    _validate_run_status(status)

    now = _utcnow()
    started_at = run.get("started_at") or now
    created_at = run.get("created_at") or started_at
    conn.execute(
        """INSERT INTO maintenance_runs
           (id, skill_id, project_id, status, started_at, finished_at, due, dry_run,
            refresh_github, finding_count, draft_count, report_path, summary, error, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            run["skill_id"],
            run.get("project_id"),
            status,
            started_at,
            run.get("finished_at"),
            int(run.get("due", 1)),
            int(run.get("dry_run", 0)),
            int(run.get("refresh_github", 1)),
            int(run.get("finding_count", 0)),
            int(run.get("draft_count", 0)),
            run.get("report_path"),
            run.get("summary"),
            run.get("error"),
            created_at,
        ),
    )
    conn.commit()
    return str(run_id)


def finish_maintenance_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    summary: str | None,
    error: str | None,
) -> None:
    """Update run status, finished_at, summary, error. Validates status."""
    _validate_run_status(status)
    conn.execute(
        "UPDATE maintenance_runs SET status=?, finished_at=?, summary=?, error=? WHERE id=?",
        (status, _utcnow(), summary, error, run_id),
    )
    conn.commit()


def get_maintenance_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """Get a single run by id."""
    cur = conn.execute("SELECT * FROM maintenance_runs WHERE id=?", (run_id,))
    return _row_to_dict(cur, cur.fetchone())


def list_maintenance_runs(conn: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """List runs with optional filters: project_id, skill_id, status, limit."""
    conditions: list[str] = []
    params: list[Any] = []

    for key in ("project_id", "skill_id"):
        value = filters.get(key)
        if value is not None:
            conditions.append(f"{key}=?")
            params.append(value)

    status = filters.get("status")
    if status is not None:
        _validate_run_status(status)
        conditions.append("status=?")
        params.append(status)

    limit = int(filters.get("limit", 100))
    if limit < 1:
        limit = 100

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    cur = conn.execute(
        f"SELECT * FROM maintenance_runs{where} ORDER BY started_at DESC LIMIT ?",  # nosec B608
        [*params, limit],
    )
    return _rows_to_dicts(cur)


def upsert_maintenance_finding(conn: sqlite3.Connection, finding: dict[str, Any]) -> None:
    """Insert or update a finding by fingerprint."""
    requested_status = finding.get("status")
    if requested_status is not None:
        _validate_finding_status(requested_status)

    now = _utcnow()
    fingerprint = finding["fingerprint"]
    metadata_json = _metadata_json(finding.get("metadata_json", finding.get("metadata")))
    existing = get_maintenance_finding(conn, fingerprint)

    if existing is None:
        conn.execute(
            """INSERT INTO maintenance_findings
               (fingerprint, project_id, skill_id, severity, status, title, body, source_type,
                source_id, source_url, metadata_json, first_seen_at, last_seen_at, resolved_at,
                run_id, issue_draft_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)""",
            (
                fingerprint,
                finding["project_id"],
                finding["skill_id"],
                finding["severity"],
                finding["title"],
                finding.get("body") or "",
                finding.get("source_type"),
                finding.get("source_id"),
                finding.get("source_url"),
                metadata_json,
                finding.get("first_seen_at") or now,
                finding.get("last_seen_at") or now,
                finding.get("run_id"),
                finding.get("issue_draft_id"),
                finding.get("created_at") or now,
                finding.get("updated_at") or now,
            ),
        )
    elif existing["status"] in {"open", "draft_created"}:
        conn.execute(
            """UPDATE maintenance_findings
               SET severity=?, title=?, body=?, source_type=?, source_id=?, source_url=?,
                   metadata_json=?, last_seen_at=?, run_id=?, updated_at=?
               WHERE fingerprint=?""",
            (
                finding["severity"],
                finding["title"],
                finding.get("body") or "",
                finding.get("source_type"),
                finding.get("source_id"),
                finding.get("source_url"),
                metadata_json,
                finding.get("last_seen_at") or now,
                finding.get("run_id"),
                finding.get("updated_at") or now,
                fingerprint,
            ),
        )
    elif existing["status"] == "resolved":
        conn.execute(
            """UPDATE maintenance_findings
               SET severity=?, status='open', title=?, body=?, source_type=?, source_id=?, source_url=?,
                   metadata_json=?, last_seen_at=?, resolved_at=NULL, run_id=?, updated_at=?
               WHERE fingerprint=?""",
            (
                finding["severity"],
                finding["title"],
                finding.get("body") or "",
                finding.get("source_type"),
                finding.get("source_id"),
                finding.get("source_url"),
                metadata_json,
                finding.get("last_seen_at") or now,
                finding.get("run_id"),
                finding.get("updated_at") or now,
                fingerprint,
            ),
        )
    conn.commit()


def get_maintenance_finding(conn: sqlite3.Connection, fingerprint: str) -> dict[str, Any] | None:
    """Get a single finding by fingerprint."""
    cur = conn.execute("SELECT * FROM maintenance_findings WHERE fingerprint=?", (fingerprint,))
    return _row_to_dict(cur, cur.fetchone())


def list_maintenance_findings(conn: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """List findings with optional filters."""
    conditions: list[str] = []
    params: list[Any] = []

    for key in ("project_id", "skill_id", "severity"):
        value = filters.get(key)
        if value is not None:
            conditions.append(f"{key}=?")
            params.append(value)

    status = filters.get("status")
    if status is not None:
        _validate_finding_status(status)
        conditions.append("status=?")
        params.append(status)
    elif not filters.get("include_resolved", False):
        conditions.append("status != 'resolved'")

    limit = int(filters.get("limit", 100))
    if limit < 1:
        limit = 100

    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    cur = conn.execute(
        f"SELECT * FROM maintenance_findings{where} ORDER BY last_seen_at DESC LIMIT ?",  # nosec B608
        [*params, limit],
    )
    return _rows_to_dicts(cur)


def mark_resolved_missing_findings(
    conn: sqlite3.Connection,
    project_id: str,
    skill_id: str,
    seen_fingerprints: set[str],
    resolved_at: str,
) -> int:
    """Resolve findings not seen in the latest run for a project/skill."""
    params: list[Any] = [resolved_at, resolved_at, project_id, skill_id]
    condition = ""
    if seen_fingerprints:
        placeholders = ",".join("?" for _ in seen_fingerprints)
        condition = f" AND fingerprint NOT IN ({placeholders})"  # nosec B608
        params.extend(sorted(seen_fingerprints))

    query = (  # nosec B608 - condition only adds ? placeholders; all values are parameterized
        """UPDATE maintenance_findings
           SET status='resolved', resolved_at=?, updated_at=?
           WHERE project_id=? AND skill_id=? AND status IN ('open', 'draft_created')"""  # nosec B608
        + condition
    )
    cur = conn.execute(query, params)  # nosec B608
    conn.commit()
    return cur.rowcount


def start_run(
    conn: sqlite3.Connection,
    project_id: str,
    skill_id: str,
    now: datetime | None = None,
) -> str:
    """Compatibility wrapper for creating a running maintenance run."""
    ts = (now or datetime.now(UTC)).isoformat()
    return start_maintenance_run(
        conn,
        {
            "project_id": project_id,
            "skill_id": skill_id,
            "status": "running",
            "started_at": ts,
            "created_at": ts,
        },
    )


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    status: str,
    summary: str = "",
    reason: str | None = None,
) -> None:
    """Compatibility wrapper for finishing a maintenance run."""
    finish_maintenance_run(conn, run_id, status, summary, reason)


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
    """Compatibility wrapper for inserting/upserting a maintenance finding."""
    run = get_maintenance_run(conn, run_id)
    if run is None:
        raise ValueError(f"Unknown maintenance run id: {run_id!r}")
    upsert_maintenance_finding(
        conn,
        {
            "fingerprint": fingerprint,
            "project_id": run["project_id"],
            "skill_id": run["skill_id"],
            "severity": severity,
            "title": title,
            "body": body,
            "source_type": source_type,
            "source_id": source_id,
            "source_url": source_url,
            "metadata": metadata or {},
            "run_id": run_id,
            "status": "open",
        },
    )
    return 1 if draftable else 0


def get_findings_by_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Get all findings last seen in a run."""
    cur = conn.execute("SELECT * FROM maintenance_findings WHERE run_id=?", (run_id,))
    return _rows_to_dicts(cur)


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
    return _row_to_dict(cur, cur.fetchone())


def recover_stale_runs(
    conn: sqlite3.Connection,
    max_age_hours: int = 2,
) -> list[str]:
    """Mark stale 'running' runs as 'failed'. Returns recovered run ids."""
    cutoff_str = (datetime.now(UTC) - timedelta(hours=max_age_hours)).isoformat()
    cur = conn.execute(
        "SELECT id FROM maintenance_runs WHERE status='running' AND started_at < ?",
        (cutoff_str,),
    )
    stale_ids = [row[0] for row in cur.fetchall()]
    now_iso = _utcnow()
    for run_id in stale_ids:
        conn.execute(
            "UPDATE maintenance_runs SET status='failed', finished_at=?, error='stale recovery' WHERE id=?",
            (now_iso, run_id),
        )
    conn.commit()
    return stale_ids
