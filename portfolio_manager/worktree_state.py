"""SQLite helpers for MVP 5 worktree rows — Phase 3.

ID conventions:
  * base worktree   → ``base:<project_id>``
  * issue worktree  → ``issue:<project_id>:<issue_number>``

Adds four optional columns to the existing ``worktrees`` table via idempotent
ALTERs (guarded by ``PRAGMA table_info``). Provides typed upsert/read helpers
that validate the ``state`` enum.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3

# ---------------------------------------------------------------------------
# Allowed worktree state values (spec § Phase 3.2)
# ---------------------------------------------------------------------------

ALLOWED_WORKTREE_STATES = frozenset(
    {
        "missing",
        "planned",
        "cloning",
        "ready",
        "clean",
        "dirty_untracked",
        "dirty_uncommitted",
        "merge_conflict",
        "rebase_conflict",
        "probe_failed",
        "blocked",
        "failed",
    }
)

#: Additive columns introduced by MVP 5.
_MVP5_COLUMNS: dict[str, str] = {
    "remote_url": "TEXT",
    "head_sha": "TEXT",
    "base_sha": "TEXT",
    "preparation_artifact_path": "TEXT",
}


# ---------------------------------------------------------------------------
# 3.1 ID keys + idempotent schema migration
# ---------------------------------------------------------------------------


def base_worktree_id(project_id: str) -> str:
    """Return the canonical ID for a project's base worktree row."""
    return f"base:{project_id}"


def issue_worktree_id(project_id: str, issue_number: int) -> str:
    """Return the canonical ID for an issue worktree row."""
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number < 1:
        raise ValueError(f"issue_number must be positive int, got {issue_number!r}")
    return f"issue:{project_id}:{issue_number}"


def init_worktree_schema(conn: sqlite3.Connection) -> None:
    """Add MVP 5 worktree columns idempotently. Safe on every startup."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(worktrees)").fetchall()}
    changed = False
    for col, sqltype in _MVP5_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE worktrees ADD COLUMN {col} {sqltype}")
            changed = True
    if changed:
        conn.commit()


# ---------------------------------------------------------------------------
# 3.2 Upsert + read helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _validate_state(state: str) -> None:
    if state not in ALLOWED_WORKTREE_STATES:
        raise ValueError(f"invalid worktree state {state!r}; allowed={sorted(ALLOWED_WORKTREE_STATES)}")


def _row_to_dict(conn: sqlite3.Connection, row: tuple[Any, ...]) -> dict[str, Any]:
    cols = [c[1] for c in conn.execute("PRAGMA table_info(worktrees)").fetchall()]
    return dict(zip(cols, row, strict=False))


def _upsert(
    conn: sqlite3.Connection,
    *,
    worktree_id: str,
    project_id: str,
    issue_number: int | None,
    path: str,
    branch_name: str | None,
    base_branch: str | None,
    state: str,
    dirty_summary: str | None,
    remote_url: str | None,
    head_sha: str | None,
    base_sha: str | None,
    preparation_artifact_path: str | None,
) -> None:
    _validate_state(state)
    init_worktree_schema(conn)
    now = _utcnow()
    conn.execute(
        """INSERT INTO worktrees
           (id, project_id, issue_number, path, branch_name, base_branch,
            state, dirty_summary, last_inspected_at, created_at, updated_at,
            remote_url, head_sha, base_sha, preparation_artifact_path)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             project_id=excluded.project_id,
             issue_number=excluded.issue_number,
             path=excluded.path,
             branch_name=excluded.branch_name,
             base_branch=excluded.base_branch,
             state=excluded.state,
             dirty_summary=excluded.dirty_summary,
             last_inspected_at=excluded.last_inspected_at,
             updated_at=excluded.updated_at,
             remote_url=COALESCE(excluded.remote_url, worktrees.remote_url),
             head_sha=COALESCE(excluded.head_sha, worktrees.head_sha),
             base_sha=COALESCE(excluded.base_sha, worktrees.base_sha),
             preparation_artifact_path=COALESCE(excluded.preparation_artifact_path,
                                                worktrees.preparation_artifact_path)""",
        (
            worktree_id,
            project_id,
            issue_number,
            path,
            branch_name,
            base_branch,
            state,
            dirty_summary,
            now,
            now,
            now,
            remote_url,
            head_sha,
            base_sha,
            preparation_artifact_path,
        ),
    )
    conn.commit()


def upsert_base_worktree(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    path: str,
    state: str,
    branch_name: str | None = None,
    base_branch: str | None = None,
    dirty_summary: str | None = None,
    remote_url: str | None = None,
    head_sha: str | None = None,
    base_sha: str | None = None,
    preparation_artifact_path: str | None = None,
) -> None:
    """Upsert a base-worktree row keyed by ``base:<project_id>``."""
    _upsert(
        conn,
        worktree_id=base_worktree_id(project_id),
        project_id=project_id,
        issue_number=None,
        path=path,
        branch_name=branch_name,
        base_branch=base_branch,
        state=state,
        dirty_summary=dirty_summary,
        remote_url=remote_url,
        head_sha=head_sha,
        base_sha=base_sha,
        preparation_artifact_path=preparation_artifact_path,
    )


def upsert_issue_worktree(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    issue_number: int,
    path: str,
    state: str,
    branch_name: str | None = None,
    base_branch: str | None = None,
    dirty_summary: str | None = None,
    remote_url: str | None = None,
    head_sha: str | None = None,
    base_sha: str | None = None,
    preparation_artifact_path: str | None = None,
) -> None:
    """Upsert an issue-worktree row keyed by ``issue:<project_id>:<n>``."""
    _upsert(
        conn,
        worktree_id=issue_worktree_id(project_id, issue_number),
        project_id=project_id,
        issue_number=issue_number,
        path=path,
        branch_name=branch_name,
        base_branch=base_branch,
        state=state,
        dirty_summary=dirty_summary,
        remote_url=remote_url,
        head_sha=head_sha,
        base_sha=base_sha,
        preparation_artifact_path=preparation_artifact_path,
    )


def get_worktree(conn: sqlite3.Connection, worktree_id: str) -> dict[str, Any] | None:
    """Return the worktree row dict for *worktree_id* or ``None``."""
    init_worktree_schema(conn)
    row = conn.execute("SELECT * FROM worktrees WHERE id=?", (worktree_id,)).fetchone()
    return None if row is None else _row_to_dict(conn, row)


def list_worktrees_for_project(conn: sqlite3.Connection, project_id: str) -> list[dict[str, Any]]:
    """Return all worktree rows for *project_id*, ordered by id."""
    init_worktree_schema(conn)
    rows = conn.execute(
        "SELECT * FROM worktrees WHERE project_id=? ORDER BY id",
        (project_id,),
    ).fetchall()
    return [_row_to_dict(conn, r) for r in rows]


__all__ = [
    "ALLOWED_WORKTREE_STATES",
    "base_worktree_id",
    "get_worktree",
    "init_worktree_schema",
    "issue_worktree_id",
    "list_worktrees_for_project",
    "upsert_base_worktree",
    "upsert_issue_worktree",
]
