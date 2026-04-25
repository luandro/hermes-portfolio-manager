"""SQLite state persistence for the Portfolio Manager plugin.

Phase 2: open/init, upsert (projects, issues, PRs, worktrees),
heartbeat lifecycle, advisory locks.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path

    from portfolio_manager.config import ProjectConfig

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  repo_url TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'medium',
  default_branch TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
  project_id TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  github_node_id TEXT,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  risk TEXT,
  confidence REAL,
  labels_json TEXT,
  spec_artifact_path TEXT,
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, issue_number),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pull_requests (
  project_id TEXT NOT NULL,
  pr_number INTEGER NOT NULL,
  github_node_id TEXT,
  title TEXT NOT NULL,
  branch_name TEXT,
  base_branch TEXT,
  state TEXT NOT NULL,
  risk TEXT,
  review_stage TEXT,
  auto_merge_candidate INTEGER NOT NULL DEFAULT 0,
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, pr_number),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worktrees (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  issue_number INTEGER,
  path TEXT NOT NULL,
  branch_name TEXT,
  base_branch TEXT,
  state TEXT NOT NULL,
  dirty_summary TEXT,
  last_inspected_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS heartbeats (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  active_window INTEGER NOT NULL DEFAULT 1,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS heartbeat_events (
  id TEXT PRIMARY KEY,
  heartbeat_id TEXT,
  project_id TEXT,
  level TEXT NOT NULL,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  data_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (heartbeat_id) REFERENCES heartbeats(id) ON DELETE SET NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS locks (
  name TEXT PRIMARY KEY,
  owner TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_project_state ON issues(project_id, state);
CREATE INDEX IF NOT EXISTS idx_prs_project_state ON pull_requests(project_id, state);
CREATE INDEX IF NOT EXISTS idx_worktrees_project_state ON worktrees(project_id, state);
CREATE INDEX IF NOT EXISTS idx_events_heartbeat ON heartbeat_events(heartbeat_id);
CREATE INDEX IF NOT EXISTS idx_locks_expires_at ON locks(expires_at);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# 2.1 Open / Init
# ---------------------------------------------------------------------------


def open_state(root: Path) -> sqlite3.Connection:
    """Create/open the SQLite database at ``{root}/state/state.sqlite``.

    Creates parent directories, enables WAL mode and foreign keys.
    """
    state_dir = root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    db_path = state_dir / "state.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_state(conn: sqlite3.Connection) -> None:
    """Execute the MVP schema. Idempotent (IF NOT EXISTS + version check)."""
    # Guard: skip if already initialized
    try:
        row = conn.execute("SELECT value FROM _schema_meta WHERE key='schema_version'").fetchone()
        if row:
            return
    except Exception:
        pass
    conn.executescript(SCHEMA_SQL)
    conn.execute("CREATE TABLE IF NOT EXISTS _schema_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT OR IGNORE INTO _schema_meta (key, value) VALUES ('schema_version', '1')")
    conn.commit()


# ---------------------------------------------------------------------------
# 2.2 Upsert project
# ---------------------------------------------------------------------------


def upsert_project(conn: sqlite3.Connection, project: ProjectConfig) -> None:
    now = _utcnow()
    conn.execute(
        """INSERT INTO projects
           (id, name, repo_url, priority, default_branch, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             name=excluded.name,
             repo_url=excluded.repo_url,
             priority=excluded.priority,
             default_branch=excluded.default_branch,
             status=excluded.status,
             updated_at=excluded.updated_at""",
        (
            project.id,
            project.name,
            project.repo,
            project.priority,
            project.default_branch,
            project.status,
            now,
            now,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 2.3 Upsert issue
# ---------------------------------------------------------------------------


def upsert_issue(conn: sqlite3.Connection, project_id: str, issue_record: dict[str, Any]) -> None:
    now = _utcnow()
    conn.execute(
        """INSERT INTO issues
           (project_id, issue_number, title, state, labels_json, last_seen_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id, issue_number) DO UPDATE SET
             title=excluded.title,
             labels_json=excluded.labels_json,
             last_seen_at=excluded.last_seen_at,
             updated_at=excluded.updated_at""",
        (
            project_id,
            issue_record["number"],
            issue_record["title"],
            issue_record.get("state", "needs_triage"),
            issue_record.get("labels_json"),
            now,
            issue_record.get("created_at", now),
            issue_record.get("updated_at", now),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 2.4 Upsert PR
# ---------------------------------------------------------------------------


def upsert_pull_request(conn: sqlite3.Connection, project_id: str, pr_record: dict[str, Any]) -> None:
    now = _utcnow()
    conn.execute(
        """INSERT INTO pull_requests
           (project_id, pr_number, title, branch_name, base_branch, state,
            review_stage, last_seen_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(project_id, pr_number) DO UPDATE SET
             title=excluded.title,
             branch_name=excluded.branch_name,
             base_branch=excluded.base_branch,
             state=excluded.state,
             review_stage=excluded.review_stage,
             last_seen_at=excluded.last_seen_at,
             updated_at=excluded.updated_at""",
        (
            project_id,
            pr_record["number"],
            pr_record["title"],
            pr_record.get("branch_name"),
            pr_record.get("base_branch"),
            pr_record["state"],
            pr_record.get("review_stage"),
            now,
            pr_record.get("created_at", now),
            pr_record.get("updated_at", now),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 2.5 Upsert worktree
# ---------------------------------------------------------------------------


def upsert_worktree(conn: sqlite3.Connection, worktree_record: dict[str, Any]) -> None:
    now = _utcnow()
    conn.execute(
        """INSERT INTO worktrees
           (id, project_id, issue_number, path, branch_name, base_branch,
            state, dirty_summary, last_inspected_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             project_id=excluded.project_id,
             issue_number=excluded.issue_number,
             path=excluded.path,
             branch_name=excluded.branch_name,
             base_branch=excluded.base_branch,
             state=excluded.state,
             dirty_summary=excluded.dirty_summary,
             last_inspected_at=excluded.last_inspected_at,
             updated_at=excluded.updated_at""",
        (
            worktree_record["id"],
            worktree_record["project_id"],
            worktree_record.get("issue_number"),
            worktree_record["path"],
            worktree_record.get("branch_name"),
            worktree_record.get("base_branch"),
            worktree_record["state"],
            worktree_record.get("dirty_summary"),
            now,
            worktree_record.get("created_at", now),
            worktree_record.get("updated_at", now),
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 2.6 Heartbeat lifecycle
# ---------------------------------------------------------------------------


def start_heartbeat(conn: sqlite3.Connection) -> str:
    hb_id = str(uuid4())
    now = _utcnow()
    conn.execute(
        """INSERT INTO heartbeats (id, started_at, status, active_window, created_at)
           VALUES (?, ?, 'running', 1, ?)""",
        (hb_id, now, now),
    )
    conn.commit()
    return hb_id


def add_event(
    conn: sqlite3.Connection,
    heartbeat_id: str,
    level: str,
    event_type: str,
    message: str,
    project_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    import json

    event_id = str(uuid4())
    now = _utcnow()
    conn.execute(
        """INSERT INTO heartbeat_events
           (id, heartbeat_id, project_id, level, type, message, data_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event_id,
            heartbeat_id,
            project_id,
            level,
            event_type,
            message,
            json.dumps(data) if data else None,
            now,
        ),
    )
    conn.commit()


def finish_heartbeat(
    conn: sqlite3.Connection,
    heartbeat_id: str,
    status: str,
    summary: str | None = None,
    error: str | None = None,
) -> None:
    now = _utcnow()
    conn.execute(
        """UPDATE heartbeats
           SET finished_at=?, status=?, summary=?, error=?
           WHERE id=?""",
        (now, status, summary, error, heartbeat_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 2.7 Advisory locks
# ---------------------------------------------------------------------------


@dataclass
class LockResult:
    acquired: bool
    reason: str = ""


def acquire_lock(conn: sqlite3.Connection, name: str, owner: str, ttl_seconds: int) -> LockResult:
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    expires_iso = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=UTC).isoformat()

    cur = conn.execute("SELECT owner, expires_at FROM locks WHERE name=?", (name,))
    row = cur.fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO locks (name, owner, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
            (name, owner, now_iso, expires_iso),
        )
        conn.commit()
        return LockResult(acquired=True)

    existing_owner, expires_at_str = row
    expires_at = datetime.fromisoformat(expires_at_str)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at < now:
        # Expired — replace
        conn.execute(
            "UPDATE locks SET owner=?, acquired_at=?, expires_at=? WHERE name=?",
            (owner, now_iso, expires_iso, name),
        )
        conn.commit()
        return LockResult(acquired=True)

    return LockResult(acquired=False, reason=f"held by {existing_owner}")


def release_lock(conn: sqlite3.Connection, name: str, owner: str) -> LockResult:
    cur = conn.execute("SELECT owner FROM locks WHERE name=?", (name,))
    row = cur.fetchone()
    if row is None:
        return LockResult(acquired=True, reason="lock not found")

    if row[0] != owner:
        return LockResult(acquired=False, reason=f"held by {row[0]}")

    conn.execute("DELETE FROM locks WHERE name=? AND owner=?", (name, owner))
    conn.commit()
    return LockResult(acquired=True)
