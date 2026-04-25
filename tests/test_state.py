"""Tests for portfolio_manager.state - SQLite state layer (Phase 2.1-2.7)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.state import (
    acquire_lock,
    add_event,
    finish_heartbeat,
    init_state,
    open_state,
    release_lock,
    start_heartbeat,
    upsert_issue,
    upsert_project,
    upsert_pull_request,
    upsert_worktree,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _make_project(project_id: str = "test-proj") -> ProjectConfig:
    return ProjectConfig(
        id=project_id,
        name="Test Project",
        repo="git@github.com:test/test.git",
        github=GithubRef(owner="test", repo="test"),
        priority="high",
        status="active",
        default_branch="main",
        local=LocalPaths(base_path=Path("/tmp/test"), issue_worktree_pattern="/tmp/test-issue-{issue_number}"),
    )


def _open_and_init(tmp: str) -> object:
    """Open a state db in *tmp*, init, return the connection."""
    conn = open_state(Path(tmp))
    init_state(conn)
    return conn


# ---------------------------------------------------------------------------
# 2.1 Open and initialize SQLite database
# ---------------------------------------------------------------------------


class TestOpenState:
    def test_open_state_creates_file_and_directory(self, tmp_path: Path):
        root = tmp_path / "agent"
        conn = open_state(root)
        db_path = root / "state" / "state.sqlite"
        assert db_path.exists()
        conn.close()

    def test_open_state_creates_parent_dir(self, tmp_path: Path):
        root = tmp_path / "deep" / "nested" / "dir"
        conn = open_state(root)
        db_path = root / "state" / "state.sqlite"
        assert db_path.exists()
        assert (root / "state").is_dir()
        conn.close()

    def test_init_state_creates_tables(self, tmp_path: Path):
        conn = open_state(tmp_path)
        init_state(conn)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        expected = {"projects", "issues", "pull_requests", "worktrees", "heartbeats", "heartbeat_events", "locks"}
        assert expected.issubset(tables)
        conn.close()

    def test_init_state_idempotent(self, tmp_path: Path):
        conn = open_state(tmp_path)
        init_state(conn)
        init_state(conn)  # second call must not raise
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        count_before = cur.fetchone()[0]
        init_state(conn)
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        count_after = cur.fetchone()[0]
        assert count_before == count_after
        conn.close()

    def test_init_state_foreign_keys_enabled(self, tmp_path: Path):
        conn = open_state(tmp_path)
        init_state(conn)
        cur = conn.execute("PRAGMA foreign_keys")
        val = cur.fetchone()[0]
        assert val == 1
        conn.close()


# ---------------------------------------------------------------------------
# 2.2 Upsert projects
# ---------------------------------------------------------------------------


class TestUpsertProject:
    def test_upsert_project_insert(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        proj = _make_project("proj-a")
        upsert_project(conn, proj)
        cur = conn.execute("SELECT id, name, priority, status FROM projects WHERE id=?", ("proj-a",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "proj-a"
        assert row[1] == "Test Project"
        assert row[2] == "high"
        assert row[3] == "active"
        conn.close()

    def test_upsert_project_update(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        proj = _make_project("proj-a")
        upsert_project(conn, proj)
        updated = ProjectConfig(
            id="proj-a",
            name="Renamed",
            repo="git@github.com:test/test.git",
            github=GithubRef(owner="test", repo="test"),
            priority="low",
            status="paused",
            default_branch="main",
            local=LocalPaths(base_path=Path("/tmp/test"), issue_worktree_pattern="/tmp/test-issue-{issue_number}"),
        )
        upsert_project(conn, updated)
        cur = conn.execute("SELECT name, priority, status FROM projects WHERE id=?", ("proj-a",))
        row = cur.fetchone()
        assert row[0] == "Renamed"
        assert row[1] == "low"
        assert row[2] == "paused"
        conn.close()


# ---------------------------------------------------------------------------
# 2.3 Upsert issues
# ---------------------------------------------------------------------------


class TestUpsertIssue:
    def test_upsert_issue_insert_for_project(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        upsert_issue(
            conn,
            "p1",
            {
                "number": 42,
                "title": "Bug report",
                "state": "needs_triage",
                "labels_json": '["bug"]',
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT title, state FROM issues WHERE project_id=? AND issue_number=?", ("p1", 42))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Bug report"
        assert row[1] == "needs_triage"
        conn.close()

    def test_upsert_issue_update_title(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        upsert_issue(
            conn,
            "p1",
            {
                "number": 42,
                "title": "Old title",
                "state": "needs_triage",
                "labels_json": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )
        upsert_issue(
            conn,
            "p1",
            {
                "number": 42,
                "title": "New title",
                "state": "needs_triage",
                "labels_json": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT title FROM issues WHERE project_id=? AND issue_number=?", ("p1", 42))
        assert cur.fetchone()[0] == "New title"
        conn.close()

    def test_upsert_issue_preserves_existing_state(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        # Insert with explicit state
        upsert_issue(
            conn,
            "p1",
            {
                "number": 10,
                "title": "Issue ten",
                "state": "in_progress",
                "labels_json": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )
        # Upsert again with different state — should keep original "in_progress"
        upsert_issue(
            conn,
            "p1",
            {
                "number": 10,
                "title": "Issue ten updated",
                "state": "needs_triage",
                "labels_json": "[]",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT state FROM issues WHERE project_id=? AND issue_number=?", ("p1", 10))
        assert cur.fetchone()[0] == "in_progress"  # Should still be original
        conn.close()

    def test_upsert_issue_labels_json(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        labels = '["bug", "high-impact", "architecture"]'
        upsert_issue(
            conn,
            "p1",
            {
                "number": 7,
                "title": "Labeled issue",
                "state": "needs_triage",
                "labels_json": labels,
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT labels_json FROM issues WHERE project_id=? AND issue_number=?", ("p1", 7))
        assert cur.fetchone()[0] == labels
        conn.close()


# ---------------------------------------------------------------------------
# 2.4 Upsert PRs
# ---------------------------------------------------------------------------


class TestUpsertPullRequest:
    def test_upsert_pull_request_insert(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        upsert_pull_request(
            conn,
            "p1",
            {
                "number": 99,
                "title": "Fix the thing",
                "branch_name": "fix-thing",
                "base_branch": "main",
                "state": "open",
                "review_stage": "review_pending",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute(
            "SELECT title, branch_name, state FROM pull_requests WHERE project_id=? AND pr_number=?", ("p1", 99)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "Fix the thing"
        assert row[1] == "fix-thing"
        assert row[2] == "open"
        conn.close()

    def test_upsert_pull_request_update(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        upsert_pull_request(
            conn,
            "p1",
            {
                "number": 99,
                "title": "Fix the thing",
                "branch_name": "fix-thing",
                "base_branch": "main",
                "state": "open",
                "review_stage": "review_pending",
                "created_at": now,
                "updated_at": now,
            },
        )
        upsert_pull_request(
            conn,
            "p1",
            {
                "number": 99,
                "title": "Fix the thing v2",
                "branch_name": "fix-thing-v2",
                "base_branch": "main",
                "state": "checks_failed",
                "review_stage": "changes_requested",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute(
            "SELECT title, state, review_stage FROM pull_requests WHERE project_id=? AND pr_number=?", ("p1", 99)
        )
        row = cur.fetchone()
        assert row[0] == "Fix the thing v2"
        assert row[1] == "checks_failed"
        assert row[2] == "changes_requested"
        conn.close()

    def test_upsert_pull_request_auto_merge_default(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        upsert_pull_request(
            conn,
            "p1",
            {
                "number": 55,
                "title": "Auto merge test",
                "branch_name": "feature-x",
                "base_branch": "main",
                "state": "open",
                "review_stage": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute(
            "SELECT auto_merge_candidate FROM pull_requests WHERE project_id=? AND pr_number=?", ("p1", 55)
        )
        assert cur.fetchone()[0] == 0
        conn.close()


# ---------------------------------------------------------------------------
# 2.5 Upsert worktrees
# ---------------------------------------------------------------------------


class TestUpsertWorktree:
    def test_upsert_worktree_insert(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        wt_id = str(uuid4())
        upsert_worktree(
            conn,
            {
                "id": wt_id,
                "project_id": "p1",
                "issue_number": 12,
                "path": "/tmp/p1-issue-12",
                "branch_name": "agent/12-fix",
                "base_branch": "main",
                "state": "clean",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT path, state, branch_name FROM worktrees WHERE id=?", (wt_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "/tmp/p1-issue-12"
        assert row[1] == "clean"
        assert row[2] == "agent/12-fix"
        conn.close()

    def test_upsert_worktree_state_change(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        wt_id = str(uuid4())
        upsert_worktree(
            conn,
            {
                "id": wt_id,
                "project_id": "p1",
                "path": "/tmp/p1-base",
                "branch_name": "main",
                "base_branch": "main",
                "state": "clean",
                "created_at": now,
                "updated_at": now,
            },
        )
        upsert_worktree(
            conn,
            {
                "id": wt_id,
                "project_id": "p1",
                "path": "/tmp/p1-base",
                "branch_name": "main",
                "base_branch": "main",
                "state": "dirty_uncommitted",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT state FROM worktrees WHERE id=?", (wt_id,))
        assert cur.fetchone()[0] == "dirty_uncommitted"
        conn.close()

    def test_upsert_worktree_dirty_summary(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        now = _now()
        wt_id = str(uuid4())
        upsert_worktree(
            conn,
            {
                "id": wt_id,
                "project_id": "p1",
                "path": "/tmp/p1-base",
                "branch_name": "main",
                "base_branch": "main",
                "state": "dirty_uncommitted",
                "dirty_summary": "2 modified files, 1 untracked",
                "created_at": now,
                "updated_at": now,
            },
        )
        cur = conn.execute("SELECT dirty_summary FROM worktrees WHERE id=?", (wt_id,))
        assert cur.fetchone()[0] == "2 modified files, 1 untracked"
        conn.close()


# ---------------------------------------------------------------------------
# 2.6 Heartbeat records and events
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_start(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        hb_id = start_heartbeat(conn)
        assert isinstance(hb_id, str) and len(hb_id) > 0
        cur = conn.execute("SELECT status, active_window FROM heartbeats WHERE id=?", (hb_id,))
        row = cur.fetchone()
        assert row[0] == "running"
        assert row[1] == 1
        conn.close()

    def test_heartbeat_add_event(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        hb_id = start_heartbeat(conn)
        add_event(conn, hb_id, "info", "github.sync.project", "Synced project p1", project_id="p1")
        cur = conn.execute(
            "SELECT level, type, message, project_id FROM heartbeat_events WHERE heartbeat_id=?", (hb_id,)
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "info"
        assert row[1] == "github.sync.project"
        assert row[2] == "Synced project p1"
        assert row[3] == "p1"
        conn.close()

    def test_heartbeat_finish_success(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        hb_id = start_heartbeat(conn)
        finish_heartbeat(conn, hb_id, "success", summary="All good")
        cur = conn.execute("SELECT status, summary, finished_at FROM heartbeats WHERE id=?", (hb_id,))
        row = cur.fetchone()
        assert row[0] == "success"
        assert row[1] == "All good"
        assert row[2] is not None
        conn.close()

    def test_heartbeat_finish_warnings(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        hb_id = start_heartbeat(conn)
        finish_heartbeat(conn, hb_id, "success", summary="Completed with warnings")
        cur = conn.execute("SELECT status, summary FROM heartbeats WHERE id=?", (hb_id,))
        row = cur.fetchone()
        assert row[0] == "success"
        assert "warnings" in row[1]
        conn.close()

    def test_heartbeat_finish_failed(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        hb_id = start_heartbeat(conn)
        finish_heartbeat(conn, hb_id, "failed", error="SQLite corruption")
        cur = conn.execute("SELECT status, error FROM heartbeats WHERE id=?", (hb_id,))
        row = cur.fetchone()
        assert row[0] == "failed"
        assert row[1] == "SQLite corruption"
        conn.close()


# ---------------------------------------------------------------------------
# 2.7 Advisory heartbeat lock
# ---------------------------------------------------------------------------


class TestLock:
    def test_lock_acquire_new(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        result = acquire_lock(conn, "heartbeat:portfolio", "agent-1", 900)
        assert result.acquired is True
        assert result.reason == ""
        conn.close()

    def test_lock_second_acquire_blocked(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        r1 = acquire_lock(conn, "heartbeat:portfolio", "agent-1", 900)
        assert r1.acquired is True
        r2 = acquire_lock(conn, "heartbeat:portfolio", "agent-2", 900)
        assert r2.acquired is False
        assert "agent-1" in r2.reason
        conn.close()

    def test_lock_expired_replaced(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        # Acquire with a very short TTL
        r1 = acquire_lock(conn, "heartbeat:portfolio", "agent-1", 0)
        assert r1.acquired is True
        # TTL=0 means already expired, so second acquire should succeed
        r2 = acquire_lock(conn, "heartbeat:portfolio", "agent-2", 900)
        assert r2.acquired is True
        conn.close()

    def test_lock_release_owner(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        acquire_lock(conn, "heartbeat:portfolio", "agent-1", 900)
        result = release_lock(conn, "heartbeat:portfolio", "agent-1")
        assert result.acquired is True
        # After release, lock should be gone
        cur = conn.execute("SELECT count(*) FROM locks WHERE name=?", ("heartbeat:portfolio",))
        assert cur.fetchone()[0] == 0
        conn.close()

    def test_lock_wrong_owner_cannot_release(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        acquire_lock(conn, "heartbeat:portfolio", "agent-1", 900)
        result = release_lock(conn, "heartbeat:portfolio", "agent-2")
        assert result.acquired is False
        # Lock should still exist
        cur = conn.execute("SELECT owner FROM locks WHERE name=?", ("heartbeat:portfolio",))
        assert cur.fetchone()[0] == "agent-1"
        conn.close()
