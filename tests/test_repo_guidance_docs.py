"""Tests for repo_guidance_docs skill — _gh_json 4-tuple return and execute logic."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.maintenance_models import MaintenanceContext
from portfolio_manager.skills.builtin.repo_guidance_docs import (
    _gh_json,
    execute,
)


def _make_ctx(**overrides: Any) -> MaintenanceContext:
    defaults: dict[str, Any] = dict(
        root=Path("/tmp"),
        conn=MagicMock(spec=sqlite3.Connection),
        project=ProjectConfig(
            id="proj-1",
            name="Test Project",
            repo="org/test",
            github=GithubRef(owner="org", repo="test"),
            priority="medium",
            status="active",
            local=LocalPaths(base_path=Path("/tmp/test"), issue_worktree_pattern=""),
            default_branch="main",
        ),
        skill_config={},
        now=datetime(2025, 6, 1, tzinfo=UTC),
        refresh_github=False,
    )
    defaults.update(overrides)
    return MaintenanceContext(**defaults)


# ---------------------------------------------------------------------------
# _gh_json 4-tuple return
# ---------------------------------------------------------------------------


class TestGhJsonReturn:
    """Verify _gh_json returns (bool, data, error, is_not_found) 4-tuple."""

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._run_gh")
    def test_success_returns_4_tuple(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"name": "README.md"}')
        result = _gh_json("org", "repo", "repos/org/repo/contents/README.md")
        assert len(result) == 4
        ok, data, error, is_not_found = result
        assert ok is True
        assert data == {"name": "README.md"}
        assert error is None
        assert is_not_found is False

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._run_gh")
    def test_404_returns_is_not_found_true(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="404 Not Found", stdout="")
        result = _gh_json("org", "repo", "repos/org/repo/contents/MISSING.md")
        ok, data, error, is_not_found = result
        assert ok is False
        assert data is None
        assert error is not None
        assert is_not_found is True

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._run_gh")
    def test_non_404_error_returns_is_not_found_false(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="500 Internal Server Error", stdout="")
        result = _gh_json("org", "repo", "repos/org/repo/contents/README.md")
        ok, data, error, is_not_found = result
        assert ok is False
        assert data is None
        assert error is not None
        assert is_not_found is False

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._run_gh")
    def test_timeout_returns_is_not_found_false(self, mock_run: MagicMock) -> None:
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=20)
        result = _gh_json("org", "repo", "repos/org/repo/contents/README.md")
        ok, data, error, is_not_found = result
        assert ok is False
        assert data is None
        assert error is not None
        assert is_not_found is False


# ---------------------------------------------------------------------------
# execute integration with mocked _gh_json
# ---------------------------------------------------------------------------


class TestExecuteWithMissingFiles:
    """Test execute() with mocked _gh_json returning 4-tuple."""

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._gh_json")
    def test_missing_required_file_creates_finding(self, mock_gh: MagicMock) -> None:
        """Missing required file (404) produces a finding."""
        # _gh_json is called for contents and then commits — return 404 for both
        mock_gh.return_value = (False, None, "404 Not Found", True)
        ctx = _make_ctx(skill_config={"required_files": ["AGENTS.md"], "optional_files": []})
        result = execute(ctx)
        assert result.status == "success"
        assert len(result.findings) == 1
        assert "Missing required" in result.findings[0].title

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._gh_json")
    def test_present_required_file_no_finding(self, mock_gh: MagicMock) -> None:
        """Present required file produces no missing-file finding."""
        # First call: contents check returns success
        # Second call: commit date returns success with recent date
        mock_gh.side_effect = [
            (True, {"name": "AGENTS.md"}, None, False),
            (True, [{"commit": {"committer": {"date": "2025-05-01T00:00:00Z"}}}], None, False),
        ]
        ctx = _make_ctx(skill_config={"required_files": ["AGENTS.md"], "optional_files": []})
        result = execute(ctx)
        assert result.status == "success"
        assert len(result.findings) == 0

    @patch("portfolio_manager.skills.builtin.repo_guidance_docs._gh_json")
    def test_api_error_no_finding_but_warning(self, mock_gh: MagicMock) -> None:
        """Non-404 API error does not produce a missing-file finding but adds a warning."""
        mock_gh.return_value = (False, None, "500 Internal Server Error", False)
        ctx = _make_ctx(skill_config={"required_files": ["AGENTS.md"], "optional_files": []})
        result = execute(ctx)
        assert result.status == "success"
        assert len(result.findings) == 0
        assert any("500" in w for w in result.warnings)
