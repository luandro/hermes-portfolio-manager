"""Tests for MVP 4 maintenance state helpers (Tasks 1.1-1.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from portfolio_manager.maintenance_state import (
    finish_run,
    get_findings_by_run,
    get_latest_successful_run,
    insert_finding,
    recover_stale_runs,
    start_run,
)
from portfolio_manager.state import init_state, open_state

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    """In-memory DB with schema initialized and a dummy project."""
    c = open_state(tmp_path)
    init_state(c)
    # Insert a dummy project so FK constraints on maintenance_runs.project_id pass
    from datetime import datetime

    now = datetime.now(UTC).isoformat()
    c.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("proj-1", "Test Project", "https://github.com/test/repo", "medium", "active", now, now),
    )
    c.commit()
    yield c
    c.close()


# ---- Task 1.1: Schema exists ----


class TestSchema:
    def test_maintenance_runs_table_exists(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_runs'")
        assert cur.fetchone() is not None

    def test_maintenance_findings_table_exists(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='maintenance_findings'")
        assert cur.fetchone() is not None

    def test_maintenance_runs_indexes(self, conn: sqlite3.Connection) -> None:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_maintenance_%'")
        indexes = {row[0] for row in cur.fetchall()}
        assert "idx_maintenance_runs_project" in indexes
        assert "idx_maintenance_runs_skill" in indexes
        assert "idx_maintenance_findings_run" in indexes
        assert "idx_maintenance_findings_fingerprint" in indexes


# ---- Task 1.2: Helper functions ----


class TestStartRun:
    def test_creates_running_row(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "untriaged_issue_digest")
        assert run_id
        cur = conn.execute("SELECT status, project_id, skill_id FROM maintenance_runs WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == "proj-1"
        assert row[2] == "untriaged_issue_digest"

    def test_with_explicit_now(self, conn: sqlite3.Connection) -> None:
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC)
        run_id = start_run(conn, "proj-1", "skill-1", now=now)
        cur = conn.execute("SELECT started_at FROM maintenance_runs WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        assert row is not None
        assert "2025-01-15" in row[0]


class TestFinishRun:
    def test_updates_status_and_finished_at(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "skill-1")
        finish_run(conn, run_id, "success", summary="All good")
        cur = conn.execute("SELECT status, finished_at, summary FROM maintenance_runs WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "success"
        assert row[1] is not None
        assert row[2] == "All good"

    def test_with_reason(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "skill-1")
        finish_run(conn, run_id, "failed", reason="timeout")
        cur = conn.execute("SELECT reason FROM maintenance_runs WHERE run_id=?", (run_id,))
        assert cur.fetchone()[0] == "timeout"


class TestInsertFinding:
    def test_basic_insert(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "skill-1")
        fid = insert_finding(
            conn,
            run_id,
            fingerprint="abc123",
            severity="high",
            title="Stale issue found",
            body="Issue #42 has been open for 90 days",
            source_type="issue",
            source_id="42",
        )
        assert fid > 0
        findings = get_findings_by_run(conn, run_id)
        assert len(findings) == 1
        f = findings[0]
        assert f["fingerprint"] == "abc123"
        assert f["severity"] == "high"
        assert f["title"] == "Stale issue found"
        assert f["draftable"] == 1

    def test_multiple_findings(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "skill-1")
        insert_finding(conn, run_id, fingerprint="f1", severity="low", title="Finding 1")
        insert_finding(conn, run_id, fingerprint="f2", severity="medium", title="Finding 2")
        findings = get_findings_by_run(conn, run_id)
        assert len(findings) == 2


class TestGetLatestSuccessfulRun:
    def test_returns_none_when_no_runs(self, conn: sqlite3.Connection) -> None:
        result = get_latest_successful_run(conn, "proj-1", "skill-1")
        assert result is None

    def test_returns_latest_after_success(self, conn: sqlite3.Connection) -> None:
        r1 = start_run(conn, "proj-1", "skill-1")
        finish_run(conn, r1, "success", summary="First")
        r2 = start_run(conn, "proj-1", "skill-1")
        finish_run(conn, r2, "success", summary="Second")
        result = get_latest_successful_run(conn, "proj-1", "skill-1")
        assert result is not None
        assert result["summary"] == "Second"

    def test_ignores_failed_runs(self, conn: sqlite3.Connection) -> None:
        r1 = start_run(conn, "proj-1", "skill-1")
        finish_run(conn, r1, "failed")
        result = get_latest_successful_run(conn, "proj-1", "skill-1")
        assert result is None


# ---- Task 1.3: Stale run recovery ----


class TestRecoverStaleRuns:
    def test_marks_old_running_as_failed(self, conn: sqlite3.Connection) -> None:
        now = datetime.now(UTC)
        old_time = now - timedelta(hours=5)
        run_id = start_run(conn, "proj-1", "skill-1", now=old_time)
        recovered = recover_stale_runs(conn, max_age_hours=2)
        assert run_id in recovered
        cur = conn.execute("SELECT status, reason FROM maintenance_runs WHERE run_id=?", (run_id,))
        row = cur.fetchone()
        assert row[0] == "failed"
        assert row[1] == "stale recovery"

    def test_skips_recent_runs(self, conn: sqlite3.Connection) -> None:
        run_id = start_run(conn, "proj-1", "skill-1")
        recovered = recover_stale_runs(conn, max_age_hours=2)
        assert run_id not in recovered

    def test_skips_already_finished(self, conn: sqlite3.Connection) -> None:
        now = datetime.now(UTC)
        old_time = now - timedelta(hours=5)
        run_id = start_run(conn, "proj-1", "skill-1", now=old_time)
        finish_run(conn, run_id, "success")
        recovered = recover_stale_runs(conn, max_age_hours=2)
        assert run_id not in recovered
