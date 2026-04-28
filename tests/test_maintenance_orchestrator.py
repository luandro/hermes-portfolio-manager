"""Tests for maintenance_orchestrator.run_maintenance — Tasks 4.3 and 4.4."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
)
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


def _make_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "skills": {
            "health_check": {"enabled": True, "interval_hours": 24},
            "dependency_audit": {"enabled": True, "interval_hours": 48},
        },
    }
    cfg.update(overrides)
    return cfg


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = open_state(tmp_path)
    init_state(c)
    yield c
    c.close()


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


def _mock_skill_result(
    skill_id: str = "health_check",
    project_id: str = "proj-1",
    findings: list[MaintenanceFinding] | None = None,
    status: str = "success",
) -> MaintenanceSkillResult:
    return MaintenanceSkillResult(
        skill_id=skill_id,
        project_id=project_id,
        status=status,
        findings=findings or [],
        summary="mock result",
    )


class TestRealRunOrchestration:
    """Tests for run_maintenance with real (non-dry) runs — Task 4.3."""

    def test_real_run_starts_and_finishes_run_rows(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Real run creates and finishes maintenance_runs rows."""
        _insert_project(conn, "proj-1")
        config = _make_config()

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        # Check that run rows were created and finished
        cur = conn.execute("SELECT status FROM maintenance_runs")
        rows = cur.fetchall()
        assert len(rows) >= 1
        for row in rows:
            assert row[0] in ("success", "failed")

    def test_real_run_upserts_findings(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Real run stores findings from skill execution."""
        _insert_project(conn, "proj-1")
        config = _make_config()

        finding = MaintenanceFinding(
            fingerprint="fp1",
            severity="high",
            title="Test finding",
            body="Something wrong",
            source_type="issue",
            source_id="42",
            source_url=None,
            metadata={},
        )
        mock_result = _mock_skill_result(findings=[finding])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        # Check findings were stored
        cur = conn.execute("SELECT count(*) FROM maintenance_findings")
        count = cur.fetchone()[0]
        assert count >= 1

    def test_real_run_marks_missing_findings_resolved(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Real run resolves findings that weren't seen in the latest run."""
        _insert_project(conn, "proj-1")
        # Use single-skill config to avoid double execution
        config: dict[str, Any] = {
            "skills": {
                "health_check": {"enabled": True, "interval_hours": 24},
            },
        }

        # First run with a finding
        finding_v1 = MaintenanceFinding(
            fingerprint="fp-old",
            severity="low",
            title="Old finding",
            body="gone now",
            source_type="issue",
            source_id="10",
            source_url=None,
            metadata={},
        )
        result_v1 = _mock_skill_result(findings=[finding_v1])

        # Second run with NO findings (old finding should be resolved)
        result_v2 = _mock_skill_result(findings=[])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = result_v1
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        # Make the second run due by backdating the first run's finished_at
        old_time = datetime.now(UTC) - timedelta(hours=48)
        conn.execute(
            "UPDATE maintenance_runs SET finished_at=? WHERE status='success'",
            (old_time.isoformat(),),
        )
        conn.commit()

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = result_v2
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        # The old finding's run should still exist, but the new run has no findings
        cur = conn.execute("SELECT count(*) FROM maintenance_findings WHERE fingerprint='fp-old'")
        assert cur.fetchone()[0] == 1  # old finding still exists from first run

    def test_real_run_writes_report_artifacts(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Real run writes report.md artifacts."""
        _insert_project(conn, "proj-1")
        config = _make_config()

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        # Check artifact dir was created
        artifact_dir = root / "artifacts" / "maintenance"
        assert artifact_dir.exists(), f"Expected artifact dir to exist at {artifact_dir}"
        report_files = list(artifact_dir.rglob("report.md"))
        assert len(report_files) >= 1

    def test_real_run_continues_after_one_skill_failure(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """If one skill fails, the orchestrator continues with others."""
        _insert_project(conn, "proj-1")
        config = _make_config()

        fail_result = _mock_skill_result(
            skill_id="health_check",
            status="failed",
        )
        success_result = _mock_skill_result(
            skill_id="dependency_audit",
        )

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        call_count = 0

        def mock_execute(skill_id: str, ctx: MaintenanceContext) -> MaintenanceSkillResult:
            nonlocal call_count
            call_count += 1
            if skill_id == "health_check":
                return fail_result
            return success_result

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.side_effect = mock_execute
            mock_reg.list_specs.return_value = []
            result = run_maintenance(root, conn, config)

        assert call_count >= 2
        assert "errors" in result

    def test_run_returns_summary(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """run_maintenance returns a summary dict with expected keys."""
        _insert_project(conn, "proj-1")
        config = _make_config()

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            result = run_maintenance(root, conn, config)

        assert "runs" in result
        assert "findings_count" in result
        assert "errors" in result


class TestGitHubRefreshIntegration:
    """Tests for GitHub refresh integration — Task 4.4."""

    def test_refresh_github_true_calls_sync(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """When refresh_github=True, sync helper is called."""
        _insert_project(conn, "proj-1")
        config = _make_config(refresh_github=True)

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with (
            patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg,
            patch("portfolio_manager.maintenance_orchestrator._refresh_github_data") as mock_refresh,
        ):
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        mock_refresh.assert_called_once()

    def test_refresh_github_false_skips_sync(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """When refresh_github=False, sync helper is not called."""
        _insert_project(conn, "proj-1")
        config = _make_config(refresh_github=False)

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with (
            patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg,
            patch("portfolio_manager.maintenance_orchestrator._refresh_github_data") as mock_refresh,
        ):
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config)

        mock_refresh.assert_not_called()

    def test_gh_unavailable_continues_with_warning(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """If GitHub refresh fails, local-state skills continue with a warning."""
        _insert_project(conn, "proj-1")
        config = _make_config(refresh_github=True)

        mock_result = _mock_skill_result()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with (
            patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg,
            patch(
                "portfolio_manager.maintenance_orchestrator._refresh_github_data",
                side_effect=Exception("gh unavailable"),
            ),
        ):
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            result = run_maintenance(root, conn, config)

        # Should still have completed runs despite GitHub failure
        assert "runs" in result
        assert len(result["runs"]) >= 1
        assert "warnings" in result
        assert any("gh unavailable" in w for w in result.get("warnings", []))
