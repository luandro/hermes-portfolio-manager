"""Tests for portfolio_manager/implementation_planner.py.

Verifies that the planner:
  - Returns proposed commands and workspace path.
  - Resolves source artifact paths.
  - Blocks when harness is unknown.
  - Blocks when preflight fails.
  - Returns required_checks from harness config.
  - Does not run harness (zero subprocess calls).
  - Writes no SQLite and no artifacts.
  - Handles review_fix with approved_comment_ids.
  - Blocks review_fix when review_iteration <= 0.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from portfolio_manager.harness_config import HarnessCheckConfig, HarnessConfig
from portfolio_manager.implementation_planner import (
    ImplementationPlan,
    build_initial_plan,
    build_review_fix_plan,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HARNESS = HarnessConfig(
    id="forge",
    command=["forge", "run"],
    env_passthrough=["OPENAI_API_KEY"],
    timeout_seconds=1800,
    max_files_changed=20,
    required_checks=["unit_tests", "lint"],
    checks={
        "unit_tests": HarnessCheckConfig(
            id="unit_tests",
            command=["uv", "run", "pytest"],
            timeout_seconds=600,
        ),
        "lint": HarnessCheckConfig(
            id="lint",
            command=["uv", "run", "ruff", "check", "."],
            timeout_seconds=300,
        ),
    },
    workspace_subpath=None,
)


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    """Create a minimal root directory structure with config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects.yaml").write_text(
        "version: 1\n"
        "projects:\n"
        "  - id: my-project\n"
        "    name: My Project\n"
        "    repo: https://github.com/example/repo\n"
        "    priority: high\n"
        "    status: active\n"
        "    github:\n"
        "      owner: example\n"
        "      repo: repo\n"
    )
    return tmp_path


@pytest.fixture()
def conn(tmp_root: Path) -> sqlite3.Connection:
    """Create an in-memory SQLite connection with schema initialized."""
    c = sqlite3.connect(":memory:")
    from portfolio_manager.state import init_state

    init_state(c)
    # Insert the project row so foreign keys pass
    c.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES ('my-project', 'My Project', 'https://github.com/example/repo', 'high', 'active', "
        "'2024-01-01T00:00:00', '2024-01-01T00:00:00')"
    )
    c.commit()
    return c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_worktree(
    conn: sqlite3.Connection,
    tmp_root: Path,
    *,
    project_id: str = "my-project",
    issue_number: int = 42,
    branch_name: str = "agent/my-project/issue-42",
    head_sha: str = "abc123",
    state: str = "clean",
) -> Path:
    """Insert a worktree row and create the directory on disk."""
    from portfolio_manager.worktree_state import upsert_issue_worktree

    wt_path = tmp_root / "worktrees" / f"{project_id}-issue-{issue_number}"
    wt_path.mkdir(parents=True, exist_ok=True)

    upsert_issue_worktree(
        conn,
        project_id=project_id,
        issue_number=issue_number,
        path=str(wt_path),
        state=state,
        branch_name=branch_name,
        head_sha=head_sha,
    )
    return wt_path


def _setup_source_artifact(
    tmp_root: Path,
    conn: sqlite3.Connection,
    *,
    project_id: str = "my-project",
    issue_number: int = 42,
) -> Path:
    """Create a source artifact and link it in the issues table."""
    artifacts_dir = tmp_root / "artifacts" / "issues" / project_id / "draft-1"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    spec_path = artifacts_dir / "spec.md"
    spec_path.write_text("# Test spec\n")

    conn.execute(
        "INSERT INTO issues (project_id, issue_number, title, state, last_seen_at, created_at, updated_at, spec_artifact_path) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            project_id,
            issue_number,
            "Test issue",
            "open",
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            "2024-01-01T00:00:00",
            str(artifacts_dir),
        ),
    )
    conn.commit()
    return spec_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlanReturnsProposedCommandsAndWorkspace:
    """test_plan_returns_proposed_commands_and_workspace"""

    def test_plan_returns_proposed_commands_and_workspace(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        wt_path = _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        assert isinstance(plan, ImplementationPlan)
        assert plan.proposed_command == ["forge", "run"]
        assert plan.workspace_path == wt_path
        assert plan.job_type == "initial_implementation"
        assert plan.blocked_reasons == []


class TestPlanResolvesSourceArtifactPath:
    """test_plan_resolves_source_artifact_path"""

    def test_plan_resolves_source_artifact_path(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        spec_path = _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        assert plan.source_artifact_path is not None
        assert plan.source_artifact_path == spec_path


class TestPlanBlocksWhenHarnessUnknown:
    """test_plan_blocks_when_harness_unknown"""

    def test_plan_blocks_when_harness_unknown(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=None),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="nonexistent",
            )

        assert len(plan.blocked_reasons) > 0
        assert any("Unknown harness_id" in r for r in plan.blocked_reasons)
        assert plan.proposed_command == []
        assert plan.required_checks == []


class TestPlanBlocksWhenPreflightFails:
    """test_plan_blocks_when_preflight_fails"""

    def test_plan_blocks_when_preflight_fails(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        # No worktree row — preflight will fail
        with patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS):
            plan = build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        assert len(plan.blocked_reasons) > 0
        assert any("not found in SQLite" in r for r in plan.blocked_reasons)


class TestPlanReturnsRequiredChecksFromHarnessConfig:
    """test_plan_returns_required_checks_from_harness_config"""

    def test_plan_returns_required_checks_from_harness_config(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        assert plan.required_checks == ["unit_tests", "lint"]


class TestPlanDoesNotRunHarness:
    """test_plan_does_not_run_harness (zero subprocess calls)"""

    def test_plan_does_not_run_harness(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        # The planner itself never calls subprocess directly. Preflight's git probes
        # go through worktree_git.run_git which calls subprocess.run, but we mock
        # get_clean_state to prevent that. We also mock the preflight-internal helpers.
        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
            patch(
                "portfolio_manager.implementation_preflight._get_branch_name", return_value="agent/my-project/issue-42"
            ),
            patch("portfolio_manager.implementation_preflight._get_head_sha", return_value="abc123"),
            patch("subprocess.run") as mock_run,
            patch("subprocess.Popen") as mock_popen,
        ):
            build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        # The planner module itself must not spawn any subprocess.
        mock_run.assert_not_called()
        mock_popen.assert_not_called()


class TestPlanWritesNoSqliteNoArtifacts:
    """test_plan_writes_no_sqlite_no_artifacts"""

    def test_plan_writes_no_sqlite_no_artifacts(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        # Snapshot the DB state before
        tables_before = set(
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        )

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            build_initial_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                harness_id="forge",
            )

        # No new tables created
        tables_after = set(
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        )
        assert tables_before == tables_after

        # No implementation artifacts written
        impl_dir = tmp_root / "artifacts" / "implementations"
        assert not impl_dir.exists() or not any(impl_dir.rglob("*"))


class TestPlanForReviewFixIncludesApprovedCommentIds:
    """test_plan_for_review_fix_includes_approved_comment_ids"""

    def test_plan_for_review_fix_includes_approved_comment_ids(self, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_review_fix_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                pr_number=10,
                harness_id="forge",
                review_stage_id="stage1",
                review_iteration=1,
                approved_comment_ids=["c1", "c2"],
                fix_scope=["file:src/foo.py"],
            )

        assert plan.job_type == "review_fix"
        assert plan.blocked_reasons == []
        assert plan.proposed_command == ["forge", "run"]


class TestPlanForReviewFixBlocksWhenReviewIterationZeroOrNegative:
    """test_plan_for_review_fix_blocks_when_review_iteration_zero_or_negative"""

    @pytest.mark.parametrize("iteration", [0, -1])
    def test_blocks_on_bad_iteration(self, iteration: int, conn: sqlite3.Connection, tmp_root: Path) -> None:
        _setup_worktree(conn, tmp_root)
        _setup_source_artifact(tmp_root, conn)

        with (
            patch("portfolio_manager.implementation_planner.get_harness", return_value=_HARNESS),
            patch("portfolio_manager.implementation_preflight.get_clean_state", return_value="clean"),
        ):
            plan = build_review_fix_plan(
                conn,
                tmp_root,
                project_ref="my-project",
                issue_number=42,
                pr_number=10,
                harness_id="forge",
                review_stage_id="stage1",
                review_iteration=iteration,
                approved_comment_ids=["c1"],
                fix_scope=["file:src/foo.py"],
            )

        assert len(plan.blocked_reasons) > 0
        assert any("review_iteration must be > 0" in r for r in plan.blocked_reasons)
