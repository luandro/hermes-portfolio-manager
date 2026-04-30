"""Tests for maintenance_planner.plan_maintenance_run — Task 4.2."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from portfolio_manager.state import init_state, open_state

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


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


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def config() -> dict[str, Any]:
    return {
        "skills": {
            "untriaged_issue_digest": {"enabled": True, "interval_hours": 24},
        },
    }


class TestPlanMaintenanceRun:
    """Tests for plan_maintenance_run (dry-run planning)."""

    def test_dry_run_returns_planned_checks(
        self,
        root: Path,
        conn: sqlite3.Connection,
        config: dict[str, Any],
    ) -> None:
        """Dry run returns planned_checks with due items."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_planner import plan_maintenance_run

        result = plan_maintenance_run(conn, config, root=root)
        assert "planned_checks" in result
        assert "skipped" in result
        assert "summary" in result
        planned = result["planned_checks"]
        assert len(planned) >= 1
        assert any(p["project_id"] == "proj-1" and p["skill_id"] == "untriaged_issue_digest" for p in planned)

    def test_dry_run_does_not_insert_runs(
        self,
        root: Path,
        conn: sqlite3.Connection,
        config: dict[str, Any],
    ) -> None:
        """Dry run does not insert any rows into maintenance_runs."""
        _insert_project(conn, "proj-1")

        cur = conn.execute("SELECT count(*) FROM maintenance_runs")
        count_before = cur.fetchone()[0]

        from portfolio_manager.maintenance_planner import plan_maintenance_run

        plan_maintenance_run(conn, config, root=root)

        cur = conn.execute("SELECT count(*) FROM maintenance_runs")
        count_after = cur.fetchone()[0]
        assert count_after == count_before

    def test_dry_run_does_not_write_artifacts(
        self,
        root: Path,
        conn: sqlite3.Connection,
        config: dict[str, Any],
    ) -> None:
        """Dry run does not write any artifact files."""
        _insert_project(conn, "proj-1")

        from portfolio_manager.maintenance_planner import plan_maintenance_run

        plan_maintenance_run(conn, config, root=root)

        artifact_dir = root / "artifacts" / "maintenance"
        assert not artifact_dir.exists() or not any(artifact_dir.iterdir())

    def test_dry_run_does_not_run_github_commands(
        self,
        root: Path,
        conn: sqlite3.Connection,
        config: dict[str, Any],
    ) -> None:
        """Dry run does not invoke subprocess or GitHub commands."""
        _insert_project(conn, "proj-1")

        from unittest.mock import patch

        from portfolio_manager.maintenance_planner import plan_maintenance_run

        with patch("subprocess.run") as mock_run:
            plan_maintenance_run(conn, config, root=root)
            mock_run.assert_not_called()

    def test_dry_run_reports_would_create_issue_drafts(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Dry run reports would_create_issue_drafts based on config."""
        _insert_project(conn, "proj-1")
        config: dict[str, Any] = {
            "skills": {
                "untriaged_issue_digest": {
                    "enabled": True,
                    "interval_hours": 24,
                    "create_issue_drafts": True,
                },
            },
        }

        from portfolio_manager.maintenance_planner import plan_maintenance_run

        result = plan_maintenance_run(conn, config, root=root)
        assert "would_create_issue_drafts" in result
        assert result["would_create_issue_drafts"] is True
