"""SQLite state persistence for the Portfolio Manager plugin.

Phase 2: open/init, upsert (projects, issues, PRs, worktrees),
heartbeat lifecycle, advisory locks.
"""

from __future__ import annotations

import json
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

CREATE TABLE IF NOT EXISTS issue_drafts (
  draft_id TEXT PRIMARY KEY,
  project_id TEXT,
  state TEXT NOT NULL,
  title TEXT,
  readiness REAL,
  artifact_path TEXT NOT NULL,
  github_issue_number INTEGER,
  github_issue_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_drafts_project_state ON issue_drafts(project_id, state);

CREATE TABLE IF NOT EXISTS dependency_issues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  summary TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dependency_issues_project ON dependency_issues(project_id);

CREATE TABLE IF NOT EXISTS dependency_licenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  license TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dependency_licenses_project ON dependency_licenses(project_id);

CREATE TABLE IF NOT EXISTS security_advisories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  cve_id TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium',
  summary TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_security_advisories_project ON security_advisories(project_id);

CREATE TABLE IF NOT EXISTS stale_branches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL,
  branch_name TEXT NOT NULL,
  last_activity TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stale_branches_project ON stale_branches(project_id);

CREATE TABLE IF NOT EXISTS maintenance_runs (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  project_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  due INTEGER NOT NULL DEFAULT 1,
  dry_run INTEGER NOT NULL DEFAULT 0,
  refresh_github INTEGER NOT NULL DEFAULT 1,
  finding_count INTEGER NOT NULL DEFAULT 0,
  draft_count INTEGER NOT NULL DEFAULT 0,
  report_path TEXT,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS maintenance_findings (
  fingerprint TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source_type TEXT,
  source_id TEXT,
  source_url TEXT,
  metadata_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  run_id TEXT,
  issue_draft_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (run_id) REFERENCES maintenance_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (issue_draft_id) REFERENCES issue_drafts(draft_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill
ON maintenance_runs(project_id, skill_id, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_status
ON maintenance_runs(status, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill_status_finished
ON maintenance_runs(project_id, skill_id, status, finished_at DESC);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_project_skill
ON maintenance_findings(project_id, skill_id, status);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_severity
ON maintenance_findings(severity, status);

CREATE TABLE IF NOT EXISTS implementation_jobs (
  job_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL CHECK(job_type IN ('initial_implementation','review_fix','qa_fix')),
  project_id TEXT NOT NULL,
  issue_number INTEGER,
  worktree_id TEXT,
  pr_number INTEGER,
  review_stage_id TEXT,
  source_artifact_path TEXT,
  status TEXT NOT NULL CHECK(status IN ('planned','blocked','running','failed','succeeded','needs_user')),
  harness_id TEXT,
  started_at TEXT,
  finished_at TEXT,
  commit_sha TEXT,
  artifact_path TEXT,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_impl_jobs_proj_issue ON implementation_jobs(project_id, issue_number);
CREATE INDEX IF NOT EXISTS idx_impl_jobs_status ON implementation_jobs(status);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Draft state validation
# ---------------------------------------------------------------------------

VALID_DRAFT_STATES = frozenset(
    {
        "draft",
        "needs_project_confirmation",
        "needs_user_questions",
        "ready_for_creation",
        "creating",
        "creating_failed",
        "created",
        "discarded",
        "blocked",
    }
)


def validate_draft_state(state: str) -> None:
    """Raise ValueError if *state* is not a recognised draft state."""
    if state not in VALID_DRAFT_STATES:
        raise ValueError(f"Invalid draft state: {state!r}. Valid: {sorted(VALID_DRAFT_STATES)}")


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


_MAINTENANCE_DDL = """\
CREATE TABLE IF NOT EXISTS maintenance_runs (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  project_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  due INTEGER NOT NULL DEFAULT 1,
  dry_run INTEGER NOT NULL DEFAULT 0,
  refresh_github INTEGER NOT NULL DEFAULT 1,
  finding_count INTEGER NOT NULL DEFAULT 0,
  draft_count INTEGER NOT NULL DEFAULT 0,
  report_path TEXT,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS maintenance_findings (
  fingerprint TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source_type TEXT,
  source_id TEXT,
  source_url TEXT,
  metadata_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  run_id TEXT,
  issue_draft_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (run_id) REFERENCES maintenance_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (issue_draft_id) REFERENCES issue_drafts(draft_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill
ON maintenance_runs(project_id, skill_id, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_status
ON maintenance_runs(status, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill_status_finished
ON maintenance_runs(project_id, skill_id, status, finished_at DESC);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_project_skill
ON maintenance_findings(project_id, skill_id, status);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_severity
ON maintenance_findings(severity, status);
"""


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}  # nosec B608


def _exec_ddl(conn: sqlite3.Connection, ddl: str) -> None:
    """Execute multiple semicolon-separated DDL statements within the current transaction.

    Unlike ``conn.executescript()``, this does **not** commit the current transaction,
    keeping DDL and subsequent DML in the same atomic unit.
    """
    for stmt in ddl.split(";"):
        stripped = stmt.strip()
        if stripped:
            conn.execute(stripped)


def _rebuild_legacy_maintenance_schema(conn: sqlite3.Connection) -> None:
    """Replace the pre-spec maintenance schema before running current DDL."""
    run_cols = _table_columns(conn, "maintenance_runs")
    finding_cols = _table_columns(conn, "maintenance_findings")
    legacy_runs = bool(run_cols) and "id" not in run_cols and "run_id" in run_cols
    legacy_findings = bool(finding_cols) and "project_id" not in finding_cols and "fingerprint" in finding_cols
    if not legacy_runs and not legacy_findings:
        return

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP TABLE IF EXISTS maintenance_findings_legacy")
        conn.execute("DROP TABLE IF EXISTS maintenance_runs_legacy")
        if legacy_findings:
            conn.execute("ALTER TABLE maintenance_findings RENAME TO maintenance_findings_legacy")
        if legacy_runs:
            conn.execute("ALTER TABLE maintenance_runs RENAME TO maintenance_runs_legacy")

        _exec_ddl(conn, _MAINTENANCE_DDL)

        if legacy_runs:
            conn.execute(
                """INSERT OR IGNORE INTO maintenance_runs
                   (id, project_id, skill_id, status, started_at, finished_at, due, dry_run,
                    refresh_github, finding_count, draft_count, summary, error, created_at)
                   SELECT run_id, project_id, skill_id,
                          CASE status WHEN 'error' THEN 'failed' ELSE status END,
                          started_at, finished_at, 1, 0, 1, 0, 0, summary, reason, started_at
                   FROM maintenance_runs_legacy"""
            )

        if legacy_findings:
            conn.execute(
                """INSERT OR IGNORE INTO maintenance_findings
                   (fingerprint, project_id, skill_id, severity, status, title, body, source_type,
                    source_id, source_url, metadata_json, first_seen_at, last_seen_at, resolved_at,
                    run_id, issue_draft_id, created_at, updated_at)
                   SELECT f.fingerprint, r.project_id, r.skill_id, f.severity, 'open', f.title,
                          COALESCE(f.body, ''), f.source_type, f.source_id, f.source_url,
                          COALESCE(f.metadata_json, '{}'), f.created_at, f.created_at, NULL,
                          f.run_id, f.issue_draft_id, f.created_at, f.created_at
                   FROM maintenance_findings_legacy f
                   JOIN maintenance_runs r ON r.id = f.run_id"""
            )
            conn.execute(
                """UPDATE maintenance_runs
                   SET finding_count = (
                     SELECT count(*) FROM maintenance_findings
                     WHERE maintenance_findings.run_id = maintenance_runs.id
                   )"""
            )

        conn.execute("DROP TABLE IF EXISTS maintenance_findings_legacy")
        conn.execute("DROP TABLE IF EXISTS maintenance_runs_legacy")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def init_state(conn: sqlite3.Connection) -> None:
    """Execute the MVP schema. Idempotent (IF NOT EXISTS)."""
    _rebuild_legacy_maintenance_schema(conn)
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
    """Insert or update an issue record.

    On conflict (same project_id + issue_number), only title, labels_json,
    last_seen_at, and updated_at are updated. The existing ``state`` is
    intentionally preserved so that manually-set states (e.g. "in_progress")
    are not overwritten by the default "needs_triage" from GitHub sync.
    """
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


@dataclass
class ReleaseResult:
    success: bool
    reason: str = ""


def acquire_lock(conn: sqlite3.Connection, name: str, owner: str, ttl_seconds: int) -> LockResult:
    now = datetime.now(UTC)
    now_iso = now.isoformat()
    expires_iso = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=UTC).isoformat()

    # Optimistic INSERT — atomic at the SQLite level; handles the common case
    # (no existing lock) without a SELECT/INSERT race.
    try:
        conn.execute(
            "INSERT INTO locks (name, owner, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
            (name, owner, now_iso, expires_iso),
        )
        conn.commit()
        return LockResult(acquired=True)
    except sqlite3.IntegrityError:
        conn.rollback()

    # Lock exists — check whether it has expired
    row = conn.execute("SELECT owner, expires_at FROM locks WHERE name=?", (name,)).fetchone()
    if row is None:
        return LockResult(acquired=False, reason="lock contention")

    existing_owner, expires_at_str = row
    expires_at = datetime.fromisoformat(expires_at_str)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at >= now:
        return LockResult(acquired=False, reason=f"held by {existing_owner}")

    # Expired — conditional UPDATE guards against a concurrent steal (CAS pattern)
    cur = conn.execute(
        "UPDATE locks SET owner=?, acquired_at=?, expires_at=? WHERE name=? AND expires_at=?",
        (owner, now_iso, expires_iso, name, expires_at_str),
    )
    conn.commit()
    if cur.rowcount > 0:
        return LockResult(acquired=True)

    return LockResult(acquired=False, reason="lock contention on expiry")


# ---------------------------------------------------------------------------
# Issue drafts CRUD
# ---------------------------------------------------------------------------


def upsert_issue_draft(conn: sqlite3.Connection, draft: dict[str, Any]) -> None:
    """Insert or update an issue draft row."""
    validate_draft_state(draft["state"])
    readiness = draft.get("readiness")
    if readiness is not None and not (0.0 <= readiness <= 1.0):
        raise ValueError(f"readiness must be between 0 and 1, got {readiness}")
    now = _utcnow()
    conn.execute(
        """INSERT INTO issue_drafts
           (draft_id, project_id, state, title, readiness, artifact_path,
            github_issue_number, github_issue_url, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(draft_id) DO UPDATE SET
             project_id=excluded.project_id,
             state=excluded.state,
             title=excluded.title,
             readiness=excluded.readiness,
             artifact_path=excluded.artifact_path,
             github_issue_number=excluded.github_issue_number,
             github_issue_url=excluded.github_issue_url,
             updated_at=excluded.updated_at""",
        (
            draft["draft_id"],
            draft.get("project_id"),
            draft["state"],
            draft.get("title"),
            readiness,
            draft["artifact_path"],
            draft.get("github_issue_number"),
            draft.get("github_issue_url"),
            draft.get("created_at", now),
            now,
        ),
    )
    conn.commit()


def get_issue_draft(conn: sqlite3.Connection, draft_id: str) -> dict[str, Any] | None:
    """Return a single draft as a dict, or None if not found."""
    row = conn.execute("SELECT * FROM issue_drafts WHERE draft_id=?", (draft_id,)).fetchone()
    if row is None:
        return None
    cols = [d[1] for d in conn.execute("PRAGMA table_info('issue_drafts')").fetchall()]
    return dict(zip(cols, row, strict=False))


def list_issue_drafts(
    conn: sqlite3.Connection,
    project_id: str | None = None,
    state: str | None = None,
    include_created: bool = False,
) -> list[dict[str, Any]]:
    """Return drafts matching the given filters, newest-updated first."""
    conditions: list[str] = []
    params: list[Any] = []
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    if state is not None:
        conditions.append("state = ?")
        params.append(state)
    if not include_created and state is None:
        conditions.append("state != 'created'")
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT * FROM issue_drafts WHERE {where_clause} ORDER BY updated_at DESC"  # nosec B608
    rows = conn.execute(query, params).fetchall()
    cols = [d[1] for d in conn.execute("PRAGMA table_info('issue_drafts')").fetchall()]
    return [dict(zip(cols, row, strict=False)) for row in rows]


def release_lock(conn: sqlite3.Connection, name: str, owner: str) -> ReleaseResult:
    cur = conn.execute("SELECT owner FROM locks WHERE name=?", (name,))
    row = cur.fetchone()
    if row is None:
        return ReleaseResult(success=True, reason="lock not found")

    if row[0] != owner:
        return ReleaseResult(success=False, reason=f"held by {row[0]}")

    conn.execute("DELETE FROM locks WHERE name=? AND owner=?", (name, owner))
    conn.commit()
    return ReleaseResult(success=True)
