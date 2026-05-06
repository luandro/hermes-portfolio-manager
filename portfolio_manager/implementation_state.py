"""SQLite state management for MVP 6 implementation jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

ALLOWED_STATUS = {"planned", "blocked", "running", "failed", "succeeded", "needs_user"}
_TERMINAL_STATUS = {"succeeded", "failed", "needs_user", "blocked"}
ALLOWED_JOB_TYPES = {"initial_implementation", "review_fix", "qa_fix"}

_ALLOWED_UPDATE_FIELDS = ("started_at", "worktree_id", "pr_number", "review_stage_id", "source_artifact_path")

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


def _row_to_dict(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    cols = [d[0] for d in cursor.description]
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

    row = conn.execute(
        """SELECT status, started_at, worktree_id, pr_number, review_stage_id, source_artifact_path
           FROM implementation_jobs
           WHERE job_id=?""",
        (job_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"No job found: {job_id!r}")

    current = row[0]
    if status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current!r} -> {status!r}")

    now = _utcnow()
    update_values = dict(zip(_ALLOWED_UPDATE_FIELDS, row[1:], strict=True))
    for key, value in fields.items():
        if key not in update_values:
            raise ValueError(f"Unknown update field: {key!r}")
        update_values[key] = value

    clear_completion = current in {"blocked", "needs_user"} and status == "planned"
    conn.execute(
        """UPDATE implementation_jobs
           SET status=?,
               updated_at=?,
               finished_at=CASE WHEN ? THEN NULL ELSE finished_at END,
               commit_sha=CASE WHEN ? THEN NULL ELSE commit_sha END,
               artifact_path=CASE WHEN ? THEN NULL ELSE artifact_path END,
               failure_reason=CASE WHEN ? THEN NULL ELSE failure_reason END,
               started_at=?,
               worktree_id=?,
               pr_number=?,
               review_stage_id=?,
               source_artifact_path=?
           WHERE job_id=?""",
        (
            status,
            now,
            clear_completion,
            clear_completion,
            clear_completion,
            clear_completion,
            update_values["started_at"],
            update_values["worktree_id"],
            update_values["pr_number"],
            update_values["review_stage_id"],
            update_values["source_artifact_path"],
            job_id,
        ),
    )
    conn.commit()


def finish_job(
    conn: sqlite3.Connection,
    job_id: str,
    *,
    status: str,
    commit_sha: str | None,
    artifact_path: str | None,
    failure_reason: str | None,
) -> None:
    """Set status, finished_at, commit_sha, artifact_path, failure_reason.

    Validates the transition is allowed before writing. Allowed finish statuses
    are succeeded, failed, needs_user, and blocked; succeeded and failed cannot
    be overwritten. artifact_path may be None for terminal jobs without artifacts.
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
    cur = conn.execute("SELECT * FROM implementation_jobs WHERE job_id=?", (job_id,))
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(cur, row)


def list_jobs(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    issue_number: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Filter jobs by optional criteria."""
    cur = conn.execute(
        """SELECT * FROM implementation_jobs
           WHERE (? IS NULL OR project_id=?)
             AND (? IS NULL OR issue_number=?)
             AND (? IS NULL OR status=?)
           ORDER BY created_at DESC""",
        (project_id, project_id, issue_number, issue_number, status, status),
    )
    rows = cur.fetchall()
    return [_row_to_dict(cur, r) for r in rows]
