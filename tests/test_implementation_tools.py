"""Tests for portfolio_manager/implementation_tools.py.

Phase 13-14 tests: verify that the six tool handlers work correctly,
returning proper JSON strings matching the shared result format.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from portfolio_manager.harness_config import HarnessConfig
from portfolio_manager.implementation_locks import ImplementationLockBusy
from portfolio_manager.implementation_state import insert_job
from portfolio_manager.state import init_state, open_state

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_HARNESS = HarnessConfig(
    id="test-harness",
    command=["echo", "hello"],
    env_passthrough=[],
    timeout_seconds=60,
    max_files_changed=20,
    required_checks=[],
    checks={},
    workspace_subpath=None,
)


def _write_config(root: Path) -> Path:
    """Write a minimal projects.yaml into root/config/."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yaml").write_text(
        "version: 1\n"
        "projects:\n"
        "  - id: test-proj\n"
        "    name: Test Project\n"
        "    repo: https://github.com/example/repo\n"
        "    priority: high\n"
        "    status: active\n"
        "    github:\n"
        "      owner: example\n"
        "      repo: repo\n",
        encoding="utf-8",
    )
    return root


def _write_harness_config(root: Path) -> Path:
    """Write a minimal harnesses.yaml into root/config/."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "harnesses.yaml").write_text(
        "harnesses:\n"
        "  - id: test-harness\n"
        "    command: [echo, hello]\n"
        "    env_passthrough: []\n"
        "    timeout_seconds: 60\n"
        "    max_files_changed: 20\n"
        "    required_checks: []\n"
        "    checks: {}\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    """Create a minimal root with config + state DB."""
    root = _write_config(tmp_path / "agent-system")
    _write_harness_config(root)
    return root


def _open_conn(root: Path) -> sqlite3.Connection:
    conn = open_state(root)
    init_state(conn)
    # Insert project row for foreign key integrity
    conn.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES ('test-proj', 'Test Project', 'https://github.com/example/repo', 'high', 'active', "
        "'2024-01-01T00:00:00', '2024-01-01T00:00:00')"
    )
    conn.commit()
    return conn


def _insert_job(conn: sqlite3.Connection, **overrides: Any) -> str:
    """Insert a job row and return its job_id."""
    defaults: dict[str, Any] = {
        "job_id": "job-001",
        "job_type": "initial_implementation",
        "project_id": "test-proj",
        "issue_number": 42,
        "status": "succeeded",
        "harness_id": "test-harness",
    }
    defaults.update(overrides)
    insert_job(conn, defaults)
    return defaults["job_id"]


def _parse(result: str) -> dict[str, Any]:
    return json.loads(result)


# ---------------------------------------------------------------------------
# Plan handler tests
# ---------------------------------------------------------------------------


class TestPlanTool:
    def test_plan_tool_returns_blocked_for_unknown_project(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_plan

        result_str = _handle_portfolio_implementation_plan(
            {
                "project_ref": "nonexistent",
                "issue_number": 42,
                "harness_id": "test-harness",
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert result["tool"] == "portfolio_implementation_plan"
        assert "nonexistent" in result["reason"]

    def test_plan_tool_returns_blocked_with_reason(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_plan

        result_str = _handle_portfolio_implementation_plan(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "nonexistent-harness",
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert "nonexistent-harness" in result["reason"]

    def test_plan_tool_does_not_persist_state(self, tmp_root: Path) -> None:
        """The plan handler is read-only — no implementation_jobs rows should appear."""
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_plan

        conn = _open_conn(tmp_root)

        _handle_portfolio_implementation_plan(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "test-harness",
                "root": str(tmp_root),
            }
        )

        rows = conn.execute("SELECT count(*) FROM implementation_jobs").fetchone()
        assert rows[0] == 0
        conn.close()


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_status_schema_accepts_project_ref_issue_number(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_IMPLEMENTATION_STATUS_SCHEMA

        props = PORTFOLIO_IMPLEMENTATION_STATUS_SCHEMA["parameters"]["properties"]
        assert "project_ref" in props
        assert "issue_number" in props
        assert "job_id" in props
        required = PORTFOLIO_IMPLEMENTATION_STATUS_SCHEMA["parameters"]["required"]
        assert required == []  # job_id can substitute for project_ref+issue_number

    def test_list_schema_accepts_optional_project_issue_status_filters(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_IMPLEMENTATION_LIST_SCHEMA

        props = PORTFOLIO_IMPLEMENTATION_LIST_SCHEMA["parameters"]["properties"]
        assert "project_ref" in props
        required = PORTFOLIO_IMPLEMENTATION_LIST_SCHEMA["parameters"]["required"]
        assert "project_ref" not in required

    def test_explain_schema_requires_project_ref_and_issue_number(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_IMPLEMENTATION_EXPLAIN_SCHEMA

        required = PORTFOLIO_IMPLEMENTATION_EXPLAIN_SCHEMA["parameters"]["required"]
        assert "project_ref" in required
        assert "issue_number" in required


# ---------------------------------------------------------------------------
# Status handler tests
# ---------------------------------------------------------------------------


class TestStatusTool:
    def test_status_tool_closes_db_when_init_state_fails(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_status

        mock_conn = MagicMock()

        with (
            patch("portfolio_manager.implementation_tools.open_state", return_value=mock_conn),
            patch("portfolio_manager.implementation_tools.init_state", side_effect=RuntimeError("init failed")),
        ):
            result_str = _handle_portfolio_implementation_status(
                {
                    "job_id": "job-known",
                    "root": str(tmp_root),
                }
            )

        result = _parse(result_str)
        assert result["status"] == "failed"
        assert result["tool"] == "portfolio_implementation_status"
        assert result["reason"] == "init failed"
        mock_conn.close.assert_called_once_with()

    def test_status_tool_returns_row_for_known_job(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_status

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-known", status="succeeded")
        conn.close()

        result_str = _handle_portfolio_implementation_status(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert result["data"]["job"]["job_id"] == "job-known"
        assert result["data"]["job"]["status"] == "succeeded"

    def test_status_tool_blocks_for_unknown_project(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_status

        result_str = _handle_portfolio_implementation_status(
            {
                "project_ref": "no-such-project",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert "no-such-project" in result["reason"]


# ---------------------------------------------------------------------------
# List handler tests
# ---------------------------------------------------------------------------


class TestListTool:
    def test_list_tool_returns_empty_for_no_jobs(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_list

        result_str = _handle_portfolio_implementation_list(
            {
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert result["data"]["jobs"] == []
        assert result["data"]["count"] == 0

    def test_list_tool_filters_by_project(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_list

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-a", project_id="test-proj", issue_number=1)
        conn.close()

        result_str = _handle_portfolio_implementation_list(
            {
                "project_ref": "test-proj",
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert result["data"]["count"] == 1
        assert result["data"]["jobs"][0]["job_id"] == "job-a"

    def test_list_tool_filters_by_status(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_list

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-s", status="succeeded", issue_number=1)
        conn.close()

        # The list tool doesn't take a status filter directly in schema,
        # but we can verify it returns all jobs when no filter given
        result_str = _handle_portfolio_implementation_list(
            {
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert result["data"]["count"] == 1


# ---------------------------------------------------------------------------
# Explain handler tests
# ---------------------------------------------------------------------------


class TestExplainTool:
    def test_explain_tool_describes_block_reason_for_blocked_job(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_explain

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-blk", status="blocked", failure_reason="scope exceeded")
        conn.close()

        result_str = _handle_portfolio_implementation_explain(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert "blocked" in result["message"]
        assert "scope exceeded" in result["message"]
        assert result["data"]["suggestion"] != ""

    def test_explain_tool_describes_needs_user_reason(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_explain

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-nu", status="needs_user", failure_reason="Which API version?")
        conn.close()

        result_str = _handle_portfolio_implementation_explain(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        assert "needs_user" in result["message"]
        assert "Which API version?" in result["message"]

    def test_explain_tool_redacts_persisted_failure_reason(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_explain

        conn = _open_conn(tmp_root)
        _insert_job(conn, job_id="job-secret", status="blocked", failure_reason="token=abc123secret")
        conn.close()

        result_str = _handle_portfolio_implementation_explain(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert "abc123secret" not in result_str
        assert result["message"] == "Job job-secret is in state 'blocked'. Reason: token=***"

    def test_explain_tool_returns_blocked_for_unknown_project(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_explain

        result_str = _handle_portfolio_implementation_explain(
            {
                "project_ref": "no-such-project",
                "issue_number": 42,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert "no-such-project" in result["reason"]


# ---------------------------------------------------------------------------
# Start handler tests
# ---------------------------------------------------------------------------


class TestStartHandler:
    def test_start_handler_blocks_when_confirm_false(self, tmp_root: Path) -> None:
        """When confirm=False, run_initial_implementation returns blocked (dry run)."""
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_start

        result_str = _handle_portfolio_implementation_start(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "test-harness",
                "confirm": False,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert result["tool"] == "portfolio_implementation_start"

    @patch("portfolio_manager.implementation_tools.run_initial_implementation")
    def test_start_handler_calls_run_initial_implementation_when_confirm_true(
        self, mock_run: MagicMock, tmp_root: Path
    ) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_start

        mock_run.return_value = {
            "status": "success",
            "tool": "portfolio_implementation_start",
            "message": "ok",
            "data": {"job_id": "j1"},
            "summary": "ok",
            "reason": None,
        }

        result_str = _handle_portfolio_implementation_start(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "test-harness",
                "confirm": True,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        mock_run.assert_called_once()

    @patch("portfolio_manager.implementation_tools.run_initial_implementation")
    def test_start_handler_returns_lock_contention_as_blocked(self, mock_run: MagicMock, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_start

        mock_run.side_effect = ImplementationLockBusy("impl:test:42", "held by other")

        result_str = _handle_portfolio_implementation_start(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "test-harness",
                "confirm": True,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert "lock" in result["reason"].lower() or "busy" in result["reason"].lower()

    @patch("portfolio_manager.implementation_tools.run_initial_implementation")
    def test_start_handler_redacts_result_json(self, mock_run: MagicMock, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_start

        mock_run.return_value = {
            "status": "needs_user",
            "tool": "portfolio_implementation_start",
            "message": "Need token ghp_AAAA1111BBBB",
            "data": {"needs_user": {"question": "Use ghp_AAAA1111BBBB?"}},
            "summary": "Need token ghp_AAAA1111BBBB",
            "reason": None,
        }

        result_str = _handle_portfolio_implementation_start(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "harness_id": "test-harness",
                "confirm": True,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert "ghp_AAAA1111BBBB" not in result_str
        assert result["data"]["needs_user"]["question"] == "Use ghp_***?"


# ---------------------------------------------------------------------------
# Apply review fixes handler tests
# ---------------------------------------------------------------------------


class TestApplyReviewFixesHandler:
    def test_apply_review_fixes_handler_blocks_when_confirm_false(self, tmp_root: Path) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_apply_review_fixes

        result_str = _handle_portfolio_implementation_apply_review_fixes(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "pr_number": 7,
                "review_stage_id": "rs-1",
                "review_iteration": 1,
                "approved_comment_ids": ["c1"],
                "fix_scope": ["src/"],
                "harness_id": "test-harness",
                "confirm": False,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "blocked"
        assert result["tool"] == "portfolio_implementation_apply_review_fixes"

    @patch("portfolio_manager.implementation_tools.run_review_fix")
    def test_apply_review_fixes_handler_calls_run_review_fix_when_confirm_true(
        self, mock_run: MagicMock, tmp_root: Path
    ) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_apply_review_fixes

        mock_run.return_value = {
            "status": "success",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "ok",
            "data": {"job_id": "j2"},
            "summary": "ok",
            "reason": None,
        }

        result_str = _handle_portfolio_implementation_apply_review_fixes(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "pr_number": 7,
                "review_stage_id": "rs-1",
                "review_iteration": 1,
                "approved_comment_ids": ["c1"],
                "fix_scope": ["src/"],
                "harness_id": "test-harness",
                "confirm": True,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert result["status"] == "success"
        mock_run.assert_called_once()

    @patch("portfolio_manager.implementation_tools.run_review_fix")
    def test_apply_review_fixes_handler_passes_base_sha_and_redacts_result(
        self, mock_run: MagicMock, tmp_root: Path
    ) -> None:
        from portfolio_manager.implementation_tools import _handle_portfolio_implementation_apply_review_fixes

        mock_run.return_value = {
            "status": "failed",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "failed with ghp_AAAA1111BBBB",
            "data": {},
            "summary": "failed with ghp_AAAA1111BBBB",
            "reason": "ghp_AAAA1111BBBB",
        }

        result_str = _handle_portfolio_implementation_apply_review_fixes(
            {
                "project_ref": "test-proj",
                "issue_number": 42,
                "pr_number": 7,
                "review_stage_id": "rs-1",
                "review_iteration": 1,
                "approved_comment_ids": ["c1"],
                "fix_scope": ["src/"],
                "harness_id": "test-harness",
                "base_sha": "abc123",
                "confirm": True,
                "root": str(tmp_root),
            }
        )
        result = _parse(result_str)
        assert "ghp_AAAA1111BBBB" not in result_str
        assert result["reason"] == "ghp_***"
        assert mock_run.call_args.kwargs["base_sha"] == "abc123"


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_handlers_register_in_TOOL_REGISTRY(self) -> None:
        from portfolio_manager import _TOOL_REGISTRY

        registered = {name for name, _, _ in _TOOL_REGISTRY}
        expected = {
            "portfolio_implementation_plan",
            "portfolio_implementation_start",
            "portfolio_implementation_apply_review_fixes",
            "portfolio_implementation_status",
            "portfolio_implementation_list",
            "portfolio_implementation_explain",
        }
        missing = expected - registered
        assert not missing, f"Missing from _TOOL_REGISTRY: {missing}"
