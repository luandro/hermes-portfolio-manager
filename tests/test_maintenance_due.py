"""Tests for maintenance_due.compute_due_checks — Task 4.1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from portfolio_manager.maintenance_state import finish_run, start_run
from portfolio_manager.state import init_state, open_state

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _insert_project(
    conn: sqlite3.Connection,
    project_id: str,
    status: str = "active",
) -> None:
    now = _now()
    conn.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', ?, ?, ?)",
        (project_id, project_id, f"https://github.com/test/{project_id}", status, now, now),
    )
    conn.commit()


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = open_state(tmp_path)
    init_state(c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestComputeDueChecks:
    """Tests for compute_due_checks."""

    def test_never_run_skill_is_due(self, conn: sqlite3.Connection) -> None:
        """A project+skill with no previous run is due."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config)
        due = [r for r in results if r["skill_id"] == "untriaged_issue_digest" and r["project_id"] == "proj-1"]
        assert len(due) == 1
        assert due[0]["is_due"] is True
        assert due[0]["reason"] == "never_run"

    def test_recent_successful_run_is_not_due(self, conn: sqlite3.Connection) -> None:
        """A project+skill with a recent successful run is not due."""
        _insert_project(conn, "proj-1")
        run_id = start_run(conn, "proj-1", "untriaged_issue_digest")
        finish_run(conn, run_id, "success", summary="ok")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config)
        due = [r for r in results if r["skill_id"] == "untriaged_issue_digest" and r["project_id"] == "proj-1"]
        assert len(due) == 1
        assert due[0]["is_due"] is False
        assert due[0]["reason"] == "not_due_yet"

    def test_old_successful_run_is_due(self, conn: sqlite3.Connection) -> None:
        """A project+skill with an old successful run is due."""
        _insert_project(conn, "proj-1")
        old_time = datetime.now(UTC) - timedelta(hours=48)
        old_time_str = old_time.isoformat()
        # Start and finish with an old finished_at by direct insert
        run_id = start_run(conn, "proj-1", "untriaged_issue_digest", now=old_time)
        conn.execute(
            "UPDATE maintenance_runs SET status='success', finished_at=?, summary='ok' WHERE id=?",
            (old_time_str, run_id),
        )
        conn.commit()

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config)
        due = [r for r in results if r["skill_id"] == "untriaged_issue_digest" and r["project_id"] == "proj-1"]
        assert len(due) == 1
        assert due[0]["is_due"] is True
        assert due[0]["reason"] == "interval_elapsed"

    def test_disabled_skill_is_not_due(self, conn: sqlite3.Connection) -> None:
        """A disabled skill is never due."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": False, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config)
        due = [r for r in results if r["skill_id"] == "untriaged_issue_digest" and r["project_id"] == "proj-1"]
        assert len(due) == 1
        assert due[0]["is_due"] is False
        assert due[0]["reason"] == "disabled"

    def test_paused_and_archived_projects_excluded_by_default(self, conn: sqlite3.Connection) -> None:
        """Paused and archived projects are excluded unless flags are set."""
        _insert_project(conn, "proj-active", status="active")
        _insert_project(conn, "proj-paused", status="paused")
        _insert_project(conn, "proj-archived", status="archived")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config)
        project_ids = {r["project_id"] for r in results}
        assert "proj-active" in project_ids
        assert "proj-paused" not in project_ids
        assert "proj-archived" not in project_ids

    def test_include_paused_and_include_archived_flags_work(self, conn: sqlite3.Connection) -> None:
        """include_paused and include_archived flags include those projects."""
        _insert_project(conn, "proj-paused", status="paused")
        _insert_project(conn, "proj-archived", status="archived")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        # Include paused
        results = compute_due_checks(conn, config=config, include_paused=True)
        project_ids = {r["project_id"] for r in results}
        assert "proj-paused" in project_ids
        assert "proj-archived" not in project_ids

        # Include archived
        results = compute_due_checks(conn, config=config, include_archived=True)
        project_ids = {r["project_id"] for r in results}
        assert "proj-archived" in project_ids

    def test_project_filter_works(self, conn: sqlite3.Connection) -> None:
        """project_filter limits results to specified project."""
        _insert_project(conn, "proj-1")
        _insert_project(conn, "proj-2")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
        }
        results = compute_due_checks(conn, config=config, project_filter=["proj-1"])
        project_ids = {r["project_id"] for r in results}
        assert project_ids == {"proj-1"}

    def test_skill_filter_works(self, conn: sqlite3.Connection) -> None:
        """skill_filter limits results to specified skills."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
                "stale_issue_digest": {"enabled": True, "interval_hours": 48},
            },
        }
        results = compute_due_checks(conn, config=config, skill_filter=["untriaged_issue_digest"])
        skill_ids = {r["skill_id"] for r in results}
        assert skill_ids == {"untriaged_issue_digest"}

    def test_project_override_disable_makes_skill_not_due(self, conn: sqlite3.Connection) -> None:
        """Project-scoped overrides are applied during due computation."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_due import compute_due_checks

        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
            },
            "projects": {
                "proj-1": {
                    "skills": {
                        "untriaged_issue_digest": {"enabled": False},
                    }
                }
            },
        }

        results = compute_due_checks(conn, config=config)

        due = [r for r in results if r["skill_id"] == "untriaged_issue_digest" and r["project_id"] == "proj-1"]
        assert len(due) == 1
        assert due[0]["is_due"] is False
        assert due[0]["reason"] == "disabled"
