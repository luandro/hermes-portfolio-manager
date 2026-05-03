"""Tests for implementation_jobs table and CRUD helpers (MVP 6 Phase 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.implementation_state import (
    finish_job,
    get_job,
    insert_job,
    list_jobs,
    update_job_status,
)
from portfolio_manager.state import init_state, open_state, upsert_project

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _open_and_init(tmp: str) -> sqlite3.Connection:
    conn = open_state(Path(tmp))
    init_state(conn)
    return conn


def _make_job(job_id: str = "job-1", **overrides) -> dict:
    job = {
        "job_id": job_id,
        "job_type": "initial_implementation",
        "project_id": "test-proj",
        "issue_number": 42,
        "status": "planned",
        "harness_id": "harness-1",
    }
    job.update(overrides)
    return job


# ---------------------------------------------------------------------------
# Schema / DDL tests
# ---------------------------------------------------------------------------


class TestImplementationJobsSchema:
    def test_init_state_creates_implementation_jobs_table_idempotent(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='implementation_jobs'")
        assert cur.fetchone()[0] == 1
        # Second init must not raise
        init_state(conn)
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='implementation_jobs'")
        assert cur.fetchone()[0] == 1
        conn.close()

    def test_implementation_jobs_columns_match_spec(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        cols = {row[1] for row in conn.execute("PRAGMA table_info(implementation_jobs)").fetchall()}
        expected = {
            "job_id",
            "job_type",
            "project_id",
            "issue_number",
            "worktree_id",
            "pr_number",
            "review_stage_id",
            "source_artifact_path",
            "status",
            "harness_id",
            "started_at",
            "finished_at",
            "commit_sha",
            "artifact_path",
            "failure_reason",
            "created_at",
            "updated_at",
        }
        assert cols == expected
        conn.close()

    def test_status_check_constraint_rejects_unknown_value(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO implementation_jobs
                   (job_id, job_type, project_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                ("j1", "initial_implementation", "test-proj", "bogus_status"),
            )
        conn.close()

    def test_job_type_check_constraint_rejects_unknown_value(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """INSERT INTO implementation_jobs
                   (job_id, job_type, project_id, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))""",
                ("j1", "bogus_type", "test-proj", "planned"),
            )
        conn.close()

    def test_existing_state_db_can_be_migrated_in_place(self, tmp_path: Path):
        # Create and init with pre-MVP6 schema (no implementation_jobs)
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        # Simulate a pre-existing DB by dropping the table
        conn.execute("DROP TABLE IF EXISTS implementation_jobs")
        conn.commit()
        # Re-init should recreate it
        init_state(conn)
        cur = conn.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='implementation_jobs'")
        assert cur.fetchone()[0] == 1
        conn.close()

    def test_migration_does_not_break_mvp1_to_mvp5_state_tests(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        # Verify existing tables still work
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        }
        expected = {
            "projects",
            "issues",
            "pull_requests",
            "worktrees",
            "heartbeats",
            "heartbeat_events",
            "locks",
            "issue_drafts",
            "dependency_issues",
            "dependency_licenses",
            "security_advisories",
            "stale_branches",
            "maintenance_runs",
            "maintenance_findings",
            "implementation_jobs",
        }
        assert expected.issubset(tables)
        conn.close()


# ---------------------------------------------------------------------------
# CRUD helper tests
# ---------------------------------------------------------------------------


class TestInsertJob:
    def test_insert_job_planned_returns_row(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job())
        row = get_job(conn, "job-1")
        assert row is not None
        assert row["job_id"] == "job-1"
        assert row["job_type"] == "initial_implementation"
        assert row["status"] == "planned"
        assert row["project_id"] == "test-proj"
        assert row["issue_number"] == 42
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        conn.close()


class TestUpdateJobStatus:
    def test_update_job_status_transitions_planned_to_running(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job())
        update_job_status(conn, "job-1", status="running", started_at="2025-01-01T00:00:00")
        row = get_job(conn, "job-1")
        assert row["status"] == "running"
        assert row["started_at"] == "2025-01-01T00:00:00"
        conn.close()

    def test_invalid_status_transition_rejected(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job())
        # succeeded -> running is not allowed (succeeded is terminal)
        update_job_status(conn, "job-1", status="running")
        with pytest.raises(ValueError, match="Invalid transition"):
            update_job_status(conn, "job-1", status="planned")
        conn.close()


class TestFinishJob:
    def test_finish_job_sets_finished_at_and_commit_sha(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job())
        update_job_status(conn, "job-1", status="running")
        finish_job(
            conn,
            "job-1",
            status="succeeded",
            commit_sha="abc123",
            artifact_path="/artifacts/job-1.tar.gz",
            failure_reason=None,
        )
        row = get_job(conn, "job-1")
        assert row["status"] == "succeeded"
        assert row["finished_at"] is not None
        assert row["commit_sha"] == "abc123"
        assert row["artifact_path"] == "/artifacts/job-1.tar.gz"
        assert row["failure_reason"] is None
        conn.close()


class TestGetJob:
    def test_get_job_by_id(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job("j1"))
        insert_job(conn, _make_job("j2", issue_number=99))
        row = get_job(conn, "j1")
        assert row is not None
        assert row["job_id"] == "j1"
        assert row["issue_number"] == 42
        assert get_job(conn, "nonexistent") is None
        conn.close()


class TestListJobs:
    def test_list_jobs_for_project_filters_by_status(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        upsert_project(conn, _make_project("p2"))
        insert_job(conn, _make_job("j1", project_id="p1", status="planned"))
        insert_job(conn, _make_job("j2", project_id="p1", status="running"))
        insert_job(conn, _make_job("j3", project_id="p2", status="planned"))
        rows = list_jobs(conn, project_id="p1", status="planned")
        assert len(rows) == 1
        assert rows[0]["job_id"] == "j1"
        conn.close()

    def test_list_jobs_for_issue_filters_by_issue_number(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project("p1"))
        insert_job(conn, _make_job("j1", project_id="p1", issue_number=10))
        insert_job(conn, _make_job("j2", project_id="p1", issue_number=20))
        insert_job(conn, _make_job("j3", project_id="p1", issue_number=10))
        rows = list_jobs(conn, project_id="p1", issue_number=10)
        assert len(rows) == 2
        assert {r["job_id"] for r in rows} == {"j1", "j3"}
        conn.close()


class TestConcurrentInsert:
    def test_concurrent_insert_with_same_job_id_rejected(self, tmp_path: Path):
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())
        insert_job(conn, _make_job("j-dup"))
        with pytest.raises(sqlite3.IntegrityError):
            insert_job(conn, _make_job("j-dup"))
        conn.close()
