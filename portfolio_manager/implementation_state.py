"""SQLite state management for MVP 6 implementation jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

ALLOWED_STATUS = {"planned", "blocked", "running", "failed", "succeeded", "needs_user"}
_TERMINAL_STATUS = {"succeeded", "failed", "needs_user", "blocked"}
ALLOWED_JOB_TYPES = {"initial_implementation", "review_fix", "qa_fix"}

_ALLOWED_UPDATE_FIELDS = frozenset(
    {
        "started_at",
        "worktree_id",
        "pr_number",
        "review_stage_id",
        "source_artifact_path",
    }
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"running", "blocked", "failed", "needs_user"},
    "running": {"succeeded", "failed", "needs_user", "blocked"},
    "blocked": {"planned"},
    "needs_user": {"planned", "blocked"},
    "succeeded": set(),
    "failed": set(),
}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(conn: sqlite3.Connection, row: tuple[Any, ...]) -> dict[str, Any]:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(implementation_jobs)").fetchall()]
    return dict(zip(cols, row, strict=False))


def insert_job(conn: sqlite3.Connection, job: dict[str, Any]) -> None:
    """Insert a new job row.

    *job* must include at least: job_id, job_type, project_id, issue_number,
    status, harness_id.  Sets created_at and updated_at automatically.
    """
    if job.get("job_type") not in ALLOWED_JOB_TYPES:
        raise ValueError(f"Invalid job_type: {job.get('job_type')!r}")
    if job.get("status") not in ALLOWED_STATUS:
        raise ValueError(f"Invalid status: {job.get('status')!r}")

    now = _utcnow()
    conn.execute(
        """INSERT INTO implementation_jobs
           (job_id, job_type, project_id, issue_number, worktree_id, pr_number,
            review_stage_id, source_artifact_path, status, harness_id,
            started_at, finished_at, commit_sha, artifact_path, failure_reason,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job["job_id"],
            job["job_type"],
            job["project_id"],
            job.get("issue_number"),
            job.get("worktree_id"),
            job.get("pr_number"),
            job.get("review_stage_id"),
            job.get("source_artifact_path"),
            job["status"],
            job.get("harness_id"),
            job.get("started_at"),
            job.get("finished_at"),
            job.get("commit_sha"),
            job.get("artifact_path"),
            job.get("failure_reason"),
            job.get("created_at", now),
            now,
        ),
    )
    conn.commit()


def update_job_status(conn: sqlite3.Connection, job_id: str, *, status: str, **fields: Any) -> None:
    """Validate the transition is allowed, then update status and extra fields."""
    if status not in ALLOWED_STATUS:
        raise ValueError(f"Invalid status: {status!r}")

    row = conn.execute("SELECT status FROM implementation_jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"No job found: {job_id!r}")

    current = row[0]
    if status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current!r} -> {status!r}")

    now = _utcnow()
    sets = ["status=?", "updated_at=?"]
    params: list[Any] = [status, now]
    for key, value in fields.items():
        if key not in _ALLOWED_UPDATE_FIELDS:
            raise ValueError(f"Unknown update field: {key!r}")
        sets.append(f"{key}=?")
        params.append(value)
    params.append(job_id)

    conn.execute(
        f"UPDATE implementation_jobs SET {', '.join(sets)} WHERE job_id=?",  # nosec B608 — fields from _ALLOWED_UPDATE_FIELDS allowlist; values parameterized
        params,
    )
    conn.commit()


def finish_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    commit_sha: str | None,
    artifact_path: str,
    failure_reason: str | None,
) -> None:
    """Set status, finished_at, commit_sha, artifact_path, failure_reason.

    Validates the transition is allowed before writing. Terminal states
    (succeeded, failed) cannot be overwritten.
    """
    if status not in _TERMINAL_STATUS:
        raise ValueError(f"finish_job requires terminal status, got: {status!r}")

    row = conn.execute("SELECT status FROM implementation_jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        raise ValueError(f"No job found: {job_id!r}")

    current = row[0]
    if status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current!r} -> {status!r}")

    now = _utcnow()
    conn.execute(
        """UPDATE implementation_jobs
           SET status=?, finished_at=?, commit_sha=?, artifact_path=?,
               failure_reason=?, updated_at=?
           WHERE job_id=?""",
        (status, now, commit_sha, artifact_path, failure_reason, now, job_id),
    )
    conn.commit()


def get_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any] | None:
    """Return a job row as dict, or None."""
    row = conn.execute("SELECT * FROM implementation_jobs WHERE job_id=?", (job_id,)).fetchone()
    if row is None:
        return None
    return _row_to_dict(conn, row)


def list_jobs(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    issue_number: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Filter jobs by optional criteria."""
    conditions: list[str] = []
    params: list[Any] = []
    if project_id is not None:
        conditions.append("project_id=?")
        params.append(project_id)
    if issue_number is not None:
        conditions.append("issue_number=?")
        params.append(issue_number)
    if status is not None:
        conditions.append("status=?")
        params.append(status)

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = conn.execute(
        f"SELECT * FROM implementation_jobs WHERE {where} ORDER BY created_at DESC",  # nosec B608 — WHERE clause built from fixed condition strings; values parameterized
        params,
    ).fetchall()
    return [_row_to_dict(conn, r) for r in rows]
