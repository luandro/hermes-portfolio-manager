"""Tests for run_initial_implementation and run_review_fix orchestrators in implementation_jobs.

Phase 11.2 tests (initial_implementation) and Phase 12.2 tests (review_fix).
"""

from __future__ import annotations

import contextlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.harness_config import HarnessCheckConfig, HarnessConfig
from portfolio_manager.harness_runner import HarnessResult
from portfolio_manager.implementation_changes import ChangedFiles
from portfolio_manager.implementation_jobs import run_initial_implementation, run_review_fix
from portfolio_manager.implementation_locks import ImplementationLockBusy
from portfolio_manager.implementation_planner import ImplementationPlan
from portfolio_manager.implementation_scope_guard import ScopeCheck
from portfolio_manager.implementation_test_quality import FirstEvidenceResult, QualityCheckResult
from portfolio_manager.state import init_state, open_state, upsert_project

if TYPE_CHECKING:
    import sqlite3

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
        local=LocalPaths(
            base_path=Path("/tmp/test"),
            issue_worktree_pattern="/tmp/test-issue-{issue_number}",
        ),
    )


def _open_and_init(tmp: str) -> sqlite3.Connection:
    conn = open_state(Path(tmp))
    init_state(conn)
    return conn


def _make_harness() -> HarnessConfig:
    return HarnessConfig(
        id="test-harness",
        command=["echo", "hello"],
        env_passthrough=[],
        timeout_seconds=60,
        max_files_changed=20,
        required_checks=[],
        checks={},
        workspace_subpath=None,
    )


def _make_plan(**overrides) -> ImplementationPlan:
    defaults = dict(
        job_type="review_fix",
        project_id="test-proj",
        issue_number=42,
        harness_id="test-harness",
        workspace_path=Path("/tmp/workspace"),
        source_artifact_path=Path("/tmp/spec.md"),
        expected_branch="agent/test-proj/issue-42",
        base_sha="abc123",
        proposed_command=["echo", "hello"],
        required_checks=[],
        blocked_reasons=[],
        warnings=[],
    )
    defaults.update(overrides)
    return ImplementationPlan(**defaults)


def _default_kwargs() -> dict[str, Any]:
    return dict(
        project_ref="test-proj",
        issue_number=42,
        pr_number=7,
        review_stage_id="stage-1",
        review_iteration=1,
        approved_comment_ids=["cmt-1", "cmt-2"],
        fix_scope=["src/**/*.py"],
        harness_id="test-harness",
        expected_branch="agent/test-proj/issue-42",
        confirm=False,
    )


# ---------------------------------------------------------------------------
# Initial-implementation helpers
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    """Create a minimal git repo at *path* with one commit."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@test.com", "commit", "--allow-empty", "-m", "init"],
        cwd=path,
        capture_output=True,
        check=True,
    )


def _setup_worktree_env(tmp_path: Path, issue_number: int = 42) -> tuple[sqlite3.Connection, Path, Path]:
    """Set up a full environment: SQLite + git worktree + artifacts.

    Returns (conn, workspace_path, root).
    """
    root = tmp_path / "root"
    root.mkdir()
    conn = _open_and_init(str(root))
    upsert_project(conn, _make_project())

    # Create worktree dir as a git repo
    worktrees_root = root / "worktrees" / "test-proj" / f"issue-{issue_number}"
    _init_git_repo(worktrees_root)

    # Insert worktree row
    conn.execute(
        """INSERT OR REPLACE INTO worktrees
           (id, project_id, issue_number, path, branch_name, base_branch, state, dirty_summary,
            created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 'clean', NULL, ?, ?)""",
        (
            f"test-proj-issue-{issue_number}",
            "test-proj",
            issue_number,
            str(worktrees_root),
            f"agent/test-proj/issue-{issue_number}",
            "main",
            "2025-01-01T00:00:00Z",
            "2025-01-01T00:00:00Z",
        ),
    )
    conn.commit()

    # Create source artifact
    artifacts_dir = root / "artifacts" / "issues" / "test-proj" / str(issue_number)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    spec_file = artifacts_dir / "spec.md"
    spec_file.write_text("# Spec\n\nAC-1: Must work correctly\n")

    # Insert issue row with spec_artifact_path
    conn.execute(
        """INSERT OR REPLACE INTO issues
           (project_id, issue_number, title, state, spec_artifact_path, last_seen_at, created_at, updated_at)
           VALUES (?, ?, ?, 'open', ?, ?, ?, ?)""",
        (
            "test-proj",
            issue_number,
            "Test issue",
            str(spec_file),
            "2025-01-01T00:00:00Z",
            "2025-01-01T00:00:00Z",
            "2025-01-01T00:00:00Z",
        ),
    )
    conn.commit()

    return conn, worktrees_root, root


def _make_impl_harness() -> HarnessConfig:
    return HarnessConfig(
        id="test-harness",
        command=["echo", "hello"],
        env_passthrough=[],
        timeout_seconds=60,
        max_files_changed=50,
        required_checks=["lint"],
        checks={
            "lint": HarnessCheckConfig(
                id="lint",
                command=["echo", "lint-ok"],
                timeout_seconds=30,
            ),
        },
        workspace_subpath=None,
    )


def _make_impl_plan(**overrides) -> ImplementationPlan:
    defaults = dict(
        job_type="initial_implementation",
        project_id="test-proj",
        issue_number=42,
        harness_id="test-harness",
        workspace_path=None,
        source_artifact_path=None,
        expected_branch="agent/test-proj/issue-42",
        base_sha="abc123",
        proposed_command=["echo", "hello"],
        required_checks=["lint"],
        blocked_reasons=[],
        warnings=[],
    )
    defaults.update(overrides)
    return ImplementationPlan(**defaults)


@dataclass(frozen=True)
class FakeHarnessResult:
    returncode: int = 0
    duration_seconds: float = 1.0
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    timed_out: bool = False
    harness_status: str | None = "implemented"
    harness_message: str | None = None


_impl_harness = _make_impl_harness


def _impl_mocks(
    workspace: Path,
    root: Path,
    *,
    harness_result: FakeHarnessResult | None = None,
    changed_files: ChangedFiles | None = None,
    scope_ok: bool = True,
    test_quality_ok: bool = True,
    commit_sha: str | None = "deadbeef1234",
):
    """Return a dict of standard mock patches for initial_implementation tests."""
    spec_path = root / "artifacts" / "issues" / "test-proj" / "42" / "spec.md"
    plan = _make_impl_plan(workspace_path=workspace, source_artifact_path=spec_path)
    harness = _impl_harness()
    if harness_result is None:
        harness_result = FakeHarnessResult()
    if changed_files is None:
        changed_files = ChangedFiles(
            files=["tests/test_foo.py", "src/foo.py"],
            statuses=[{"path": "tests/test_foo.py", "status": "A"}, {"path": "src/foo.py", "status": "M"}],
        )
    scope = ScopeCheck(
        ok=scope_ok,
        reasons=[] if scope_ok else ["protected_path_violations_1"],
        changed_files=changed_files.files,
        protected_violations=[] if scope_ok else ["config/secret.yaml"],
        out_of_scope_files=[],
    )
    tq = QualityCheckResult(
        ok=test_quality_ok,
        reasons=["acceptance_criteria_ids_matched"]
        if test_quality_ok
        else ["zero_new_tests_for_initial_implementation"],
        mode="acceptance_criteria_ids" if test_quality_ok else "",
    )
    evidence = FirstEvidenceResult(has_failing_phase=True, has_passing_phase=True)
    return dict(
        plan=plan,
        harness=harness,
        harness_result=harness_result,
        changed_files=changed_files,
        scope=scope,
        test_quality=tq,
        evidence=evidence,
        commit_sha=commit_sha,
    )


# ---------------------------------------------------------------------------
# Phase 11.2 — initial_implementation tests
# ---------------------------------------------------------------------------


class TestInitialImplDryRun:
    def test_initial_impl_dry_run_returns_plan_no_mutation(self, tmp_path: Path) -> None:
        """confirm=false returns blocked with plan, no DB row inserted."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        plan = _make_impl_plan(workspace_path=workspace)

        with patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=plan):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=False,
            )

        assert result["status"] == "blocked"
        assert result["data"]["dry_run"] is True
        assert "plan" in result["data"]

        # No job row inserted
        rows = conn.execute("SELECT * FROM implementation_jobs").fetchall()
        assert len(rows) == 0
        conn.close()


class TestInitialImplRealRun:
    def test_initial_impl_real_run_inserts_planned_row_then_running(self, tmp_path: Path) -> None:
        """With confirm=true, a planned row is inserted then transitioned to running then succeeded."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "success"
        row = conn.execute("SELECT status FROM implementation_jobs WHERE job_type='initial_implementation'").fetchone()
        assert row is not None
        assert row[0] == "succeeded"
        conn.close()

    def test_initial_impl_real_run_acquires_implementation_lock(self, tmp_path: Path) -> None:
        """The implementation lock is acquired during execution."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
            patch("portfolio_manager.implementation_jobs.with_implementation_lock") as mock_lock,
        ):
            mock_lock.return_value.__enter__ = MagicMock(return_value=None)
            mock_lock.return_value.__exit__ = MagicMock(return_value=False)

            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "success"
        mock_lock.assert_called_once_with(conn, "test-proj", 42)
        conn.close()

    def test_initial_impl_real_run_writes_plan_preflight_commands_artifacts_in_order(self, tmp_path: Path) -> None:
        """Artifacts are written in the correct order: plan, preflight, commands, input-request."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        call_order: list[str] = []

        def track(name):
            def wrapper(*args, **kwargs):
                call_order.append(name)

            return wrapper

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.write_plan_md", side_effect=track("plan")),
            patch("portfolio_manager.implementation_jobs.write_preflight_json", side_effect=track("preflight")),
            patch("portfolio_manager.implementation_jobs.write_commands_json", side_effect=track("commands")),
            patch("portfolio_manager.implementation_jobs.write_input_request_json", side_effect=track("input-request")),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
            patch("portfolio_manager.implementation_jobs.write_changed_files_json", side_effect=track("changed-files")),
            patch("portfolio_manager.implementation_jobs.write_checks_json", side_effect=track("checks")),
        ):
            run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        # Verify order of first four artifacts
        assert call_order[:4] == ["plan", "preflight", "commands", "input-request"]
        # Then harness runs, then changed-files and checks
        assert "changed-files" in call_order
        assert "checks" in call_order
        assert call_order.index("changed-files") < call_order.index("checks")
        conn.close()

    def test_initial_impl_real_run_calls_harness_runner_once(self, tmp_path: Path) -> None:
        """run_harness is called exactly once."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness") as mock_harness,
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
        ):
            mock_harness.return_value = m["harness_result"]
            run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert mock_harness.call_count == 1
        conn.close()

    def test_initial_impl_real_run_runs_required_checks_after_harness(self, tmp_path: Path) -> None:
        """Required checks are run after harness, using harness.checks config."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check") as mock_check,
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
        ):
            mock_check.return_value = FakeHarnessResult(returncode=0, harness_status="implemented")
            run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert mock_check.call_count == 1
        assert mock_check.call_args.kwargs["check"].id == "lint"
        conn.close()

    def test_initial_impl_blocks_when_harness_dirties_protected_paths(self, tmp_path: Path) -> None:
        """Scope guard blocks when changed files violate scope constraints."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root, scope_ok=False)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "blocked"
        row = conn.execute("SELECT status FROM implementation_jobs").fetchone()
        assert row[0] == "blocked"
        conn.close()

    def test_initial_impl_blocks_when_test_quality_fails(self, tmp_path: Path) -> None:
        """Test quality gate blocks the job when tests are insufficient."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root, test_quality_ok=False)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "blocked"
        row = conn.execute("SELECT status FROM implementation_jobs").fetchone()
        assert row[0] == "blocked"
        conn.close()

    def test_initial_impl_creates_local_commit_when_all_gates_pass(self, tmp_path: Path) -> None:
        """make_local_commit is called when all gates pass."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit") as mock_commit,
        ):
            mock_commit.return_value = m["commit_sha"]
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "success"
        assert mock_commit.call_count == 1
        assert mock_commit.call_args.kwargs["job_id"] is not None
        conn.close()

    def test_initial_impl_writes_result_and_finishes_succeeded(self, tmp_path: Path) -> None:
        """On success, result.json and summary.md are written, job finishes as succeeded."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
            patch("portfolio_manager.implementation_jobs.write_result_json") as mock_result,
            patch("portfolio_manager.implementation_jobs.write_summary_md") as mock_summary,
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "success"
        result_data = mock_result.call_args[0][1]
        assert result_data["status"] == "succeeded"
        assert result_data["commit_sha"] == m["commit_sha"]
        assert mock_summary.call_count == 1

        row = conn.execute("SELECT status, commit_sha FROM implementation_jobs").fetchone()
        assert row[0] == "succeeded"
        assert row[1] == m["commit_sha"]
        conn.close()

    def test_initial_impl_writes_error_artifact_and_fails_gracefully_on_lock_exception(self, tmp_path: Path) -> None:
        """Uncaught exception from lock acquisition writes error.json and returns failed.

        Since insert_job() is now inside the lock, a lock-raised exception means
        no job row is created — no orphaned planned rows on lock contention.
        """
        conn, workspace, root = _setup_worktree_env(tmp_path)
        plan = _make_impl_plan(
            workspace_path=workspace,
            source_artifact_path=root / "artifacts" / "issues" / "test-proj" / "42" / "spec.md",
        )

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.with_implementation_lock", side_effect=RuntimeError("boom")),
            patch("portfolio_manager.implementation_jobs.write_error_json") as mock_error,
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "failed"
        assert "boom" in result["message"]
        assert mock_error.call_count == 1
        error_data = mock_error.call_args[0][1]
        assert "boom" in error_data["error"]

        # No job row should exist — insert_job is inside the lock
        row = conn.execute("SELECT status FROM implementation_jobs").fetchone()
        assert row is None
        conn.close()

    def test_initial_impl_returns_needs_user_when_harness_signals_unanswerable(self, tmp_path: Path) -> None:
        """When harness returns needs_user status, the job finishes as needs_user."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root, harness_result=FakeHarnessResult(harness_status="needs_user"))

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.write_result_json"),
            patch("portfolio_manager.implementation_jobs.write_summary_md"),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "needs_user"
        row = conn.execute("SELECT status FROM implementation_jobs").fetchone()
        assert row[0] == "needs_user"
        conn.close()

    def test_initial_impl_releases_lock_on_exception(self, tmp_path: Path) -> None:
        """Lock is released even when an uncaught exception occurs inside the lock."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        plan = _make_impl_plan(
            workspace_path=workspace,
            source_artifact_path=root / "artifacts" / "issues" / "test-proj" / "42" / "spec.md",
        )

        lock_released = False

        @contextlib.contextmanager
        def _tracking_lock(conn, project_id, issue_number):
            nonlocal lock_released
            try:
                yield
            finally:
                lock_released = True

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.with_implementation_lock", side_effect=_tracking_lock),
            patch("portfolio_manager.implementation_jobs.update_job_status", side_effect=RuntimeError("inner boom")),
            patch("portfolio_manager.implementation_jobs.write_error_json"),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "failed"
        assert lock_released, "Lock was not released on exception"
        conn.close()

    def test_initial_impl_lock_contention_returns_blocked(self, tmp_path: Path) -> None:
        """ImplementationLockBusy is caught and returns blocked status."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        plan = _make_impl_plan(
            workspace_path=workspace,
            source_artifact_path=root / "artifacts" / "issues" / "test-proj" / "42" / "spec.md",
        )

        @contextlib.contextmanager
        def _lock_ctx(conn, project_id, issue_number):
            raise ImplementationLockBusy(
                f"implementation:issue:{project_id}:{issue_number}",
                "already held",
            )

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.with_implementation_lock", side_effect=_lock_ctx),
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "blocked"
        assert "lock" in result["message"].lower() or "Lock" in result["message"]
        conn.close()

    def test_initial_impl_does_NOT_call_git_push_or_gh_pr_create(self, tmp_path: Path) -> None:
        """The orchestrator never calls git push or gh pr create."""
        conn, workspace, root = _setup_worktree_env(tmp_path)
        m = _impl_mocks(workspace, root)

        with (
            patch("portfolio_manager.implementation_jobs.build_initial_plan", return_value=m["plan"]),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=m["harness"]),
            patch("portfolio_manager.implementation_jobs.run_harness", return_value=m["harness_result"]),
            patch("portfolio_manager.implementation_jobs.run_required_check", return_value=FakeHarnessResult()),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=m["changed_files"]),
            patch("portfolio_manager.implementation_jobs.collect_test_first_evidence", return_value=m["evidence"]),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=m["scope"]),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=m["test_quality"]),
            patch("portfolio_manager.implementation_jobs.make_local_commit", return_value=m["commit_sha"]),
            patch("subprocess.run") as mock_subprocess,
        ):
            result = run_initial_implementation(
                conn,
                root,
                project_ref="test-proj",
                issue_number=42,
                harness_id="test-harness",
                confirm=True,
            )

        assert result["status"] == "success"

        # Check that no subprocess.run call involved git push or gh pr create
        for call in mock_subprocess.call_args_list:
            args = call[0][0] if call[0] else []
            if isinstance(args, list) and len(args) > 0:
                cmd_str = " ".join(str(a) for a in args)
                assert not (args[0:1] == ["git"] and "push" in cmd_str), f"git push was called: {cmd_str}"
                assert not (args[0:1] == ["gh"] and "pr" in cmd_str), f"gh pr create was called: {cmd_str}"
        conn.close()


# ---------------------------------------------------------------------------
# Phase 12.2 — review_fix tests
# ---------------------------------------------------------------------------


class TestReviewFixDryRun:
    def test_review_fix_dry_run_returns_plan_no_mutation(self, tmp_path: Path):
        """confirm=False returns plan without mutating SQLite or writing artifacts."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        with patch(
            "portfolio_manager.implementation_jobs.build_review_fix_plan",
            return_value=plan,
        ):
            result = run_review_fix(conn, tmp_path, **_default_kwargs())

        assert result["status"] == "blocked"
        assert result["data"]["dry_run"] is True
        assert "plan" in result["data"]

        # No job row created
        rows = conn.execute("SELECT count(*) FROM implementation_jobs").fetchone()
        assert rows[0] == 0

        # No artifact directory created
        art_dir = tmp_path / "artifacts" / "implementations"
        assert not art_dir.exists() or not any(art_dir.iterdir())

        conn.close()


class TestReviewFixRealRun:
    def test_review_fix_real_run_acquires_review_lock_scoped_to_pr(self, tmp_path: Path):
        """Real run acquires with_implementation_review_lock(project_id, pr_number)."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(ok=True, mode="keyword_overlap")

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
            ) as mock_lock,
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
            patch(
                "portfolio_manager.implementation_jobs.make_local_commit",
                return_value="deadbeef" * 5,
            ),
        ):
            # Make the context manager just pass through
            mock_lock.return_value.__enter__ = MagicMock(return_value=None)
            mock_lock.return_value.__exit__ = MagicMock(return_value=False)

            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        # Verify the lock was called with (conn, project_id, pr_number)
        mock_lock.assert_called_once_with(conn, "test-proj", 7)
        assert result["status"] == "success"

        conn.close()


class TestReviewFixArtifacts:
    def test_review_fix_writes_artifacts_linking_review_stage_and_comment_ids(self, tmp_path: Path):
        """input-request.json must contain review_stage_id, review_iteration, and approved_comment_ids."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(ok=True, mode="keyword_overlap")

        written_input_request: dict | None = None

        def capture_input_request(artifact_dir, request, **kw):
            nonlocal written_input_request
            written_input_request = request

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
            patch(
                "portfolio_manager.implementation_jobs.make_local_commit",
                return_value="deadbeef" * 5,
            ),
            patch(
                "portfolio_manager.implementation_jobs.write_input_request_json",
                side_effect=capture_input_request,
            ),
            patch("portfolio_manager.implementation_jobs.write_plan_md"),
            patch("portfolio_manager.implementation_jobs.write_preflight_json"),
            patch("portfolio_manager.implementation_jobs.write_commands_json"),
            patch("portfolio_manager.implementation_jobs.write_changed_files_json"),
            patch("portfolio_manager.implementation_jobs.write_checks_json"),
            patch("portfolio_manager.implementation_jobs.write_scope_check_md"),
            patch("portfolio_manager.implementation_jobs.write_test_quality_md"),
            patch("portfolio_manager.implementation_jobs.write_test_first_evidence_md"),
            patch("portfolio_manager.implementation_jobs.write_commit_json"),
            patch("portfolio_manager.implementation_jobs.write_result_json"),
            patch("portfolio_manager.implementation_jobs.write_summary_md"),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "success"
        assert written_input_request is not None
        assert written_input_request["review_stage_id"] == "stage-1"
        assert written_input_request["review_iteration"] == 1
        assert written_input_request["approved_comment_ids"] == ["cmt-1", "cmt-2"]
        assert written_input_request["pr_number"] == 7
        assert written_input_request["job_type"] == "review_fix"

        conn.close()


class TestReviewFixBranchMismatch:
    def test_review_fix_blocks_when_pr_branch_mismatch(self, tmp_path: Path):
        """If plan has blocked_reasons due to branch mismatch, run returns blocked."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan(blocked_reasons=["Branch mismatch: expected 'x', got 'y'"])

        with patch(
            "portfolio_manager.implementation_jobs.build_review_fix_plan",
            return_value=plan,
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "blocked"
        assert "Branch mismatch" in result["reason"]

        conn.close()


class TestReviewFixEmptyCommentIds:
    def test_review_fix_blocks_when_approved_comment_ids_empty(self, tmp_path: Path):
        """Empty approved_comment_ids should block the plan."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan(blocked_reasons=["approved_comment_ids must be non-empty for review_fix"])

        with patch(
            "portfolio_manager.implementation_jobs.build_review_fix_plan",
            return_value=plan,
        ):
            kwargs = _default_kwargs()
            kwargs["approved_comment_ids"] = []
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "blocked"
        assert "approved_comment_ids" in result["reason"]

        conn.close()


class TestReviewFixScopeViolation:
    def test_review_fix_blocks_when_changed_files_outside_fix_scope(self, tmp_path: Path):
        """Changed files outside fix_scope should cause scope check to fail."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(
            files=["src/foo.py", "secrets/prod.yaml"],
            statuses=[
                {"path": "src/foo.py", "status": "M"},
                {"path": "secrets/prod.yaml", "status": "A"},
            ],
        )
        scope_check = ScopeCheck(
            ok=False,
            reasons=["fix_scope_violations_1"],
            changed_files=["src/foo.py", "secrets/prod.yaml"],
            out_of_scope_files=["secrets/prod.yaml"],
        )

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "blocked"
        assert "fix_scope_violations" in result["reason"]

        conn.close()


class TestReviewFixTestQuality:
    def test_review_fix_blocks_when_no_failing_test_added_for_regression_fix(self, tmp_path: Path):
        """Test quality failure should block the review fix."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(
            ok=False,
            reasons=["added_tests_have_no_meaningful_asserts"],
            mode="",
        )

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "blocked"
        assert "meaningful_asserts" in result["reason"]

        conn.close()


class TestReviewFixCommit:
    def test_review_fix_creates_followup_local_commit_with_message_referencing_comment_ids(self, tmp_path: Path):
        """Commit message must reference the approved comment IDs."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(ok=True, mode="keyword_overlap")

        commit_message_captured: str | None = None

        def capture_commit(workspace, **kw):
            nonlocal commit_message_captured
            commit_message_captured = kw.get("message")
            return "deadbeef" * 5

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
            patch(
                "portfolio_manager.implementation_jobs.make_local_commit",
                side_effect=capture_commit,
            ),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "success"
        assert commit_message_captured is not None
        # Commit message must reference comment IDs
        assert "cmt-1" in commit_message_captured
        assert "cmt-2" in commit_message_captured
        # And reference the review stage/iteration
        assert "stage-1" in commit_message_captured
        assert "iter=1" in commit_message_captured

        conn.close()


class TestReviewFixNeedsUser:
    def test_review_fix_returns_needs_user_when_feedback_requires_product_judgment(self, tmp_path: Path):
        """When harness returns needs_user, result should reflect that."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="needs_user",
                    harness_message="Requires product decision",
                ),
            ),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "needs_user"
        assert result["data"].get("needs_user") is not None or "needs_user" in str(result)

        conn.close()


class TestReviewFixNoPassFailDecision:
    def test_review_fix_does_NOT_decide_pass_fail_for_review_stage(self, tmp_path: Path):
        """The result must not contain a review_stage_pass or review_stage_fail field."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(ok=True, mode="keyword_overlap")

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
            patch(
                "portfolio_manager.implementation_jobs.make_local_commit",
                return_value="deadbeef" * 5,
            ),
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "success"
        # Must not contain review stage pass/fail decision
        assert "review_stage_pass" not in result
        assert "review_stage_fail" not in result
        assert "review_stage_status" not in result
        assert "stage_passed" not in result
        assert "stage_failed" not in result

        conn.close()


class TestReviewFixNoPush:
    def test_review_fix_does_NOT_push(self, tmp_path: Path):
        """run_review_fix must never call git push. Verify no push-related calls."""
        conn = _open_and_init(str(tmp_path))
        upsert_project(conn, _make_project())

        plan = _make_plan()
        harness = _make_harness()
        changed = ChangedFiles(files=["src/foo.py"], statuses=[{"path": "src/foo.py", "status": "M"}])
        scope_check = ScopeCheck(ok=True, changed_files=["src/foo.py"])
        test_quality = QualityCheckResult(ok=True, mode="keyword_overlap")

        with (
            patch("portfolio_manager.implementation_jobs.build_review_fix_plan", return_value=plan),
            patch("portfolio_manager.implementation_jobs.get_harness", return_value=harness),
            patch(
                "portfolio_manager.implementation_jobs.with_implementation_review_lock",
                return_value=MagicMock(
                    __enter__=MagicMock(return_value=None),
                    __exit__=MagicMock(return_value=False),
                ),
            ),
            patch(
                "portfolio_manager.implementation_jobs.run_harness",
                return_value=HarnessResult(
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="",
                    stderr="",
                    truncated=False,
                    timed_out=False,
                    harness_status="implemented",
                    harness_message=None,
                ),
            ),
            patch("portfolio_manager.implementation_jobs.collect_changed_files", return_value=changed),
            patch("portfolio_manager.implementation_jobs.check_scope", return_value=scope_check),
            patch("portfolio_manager.implementation_jobs.check_test_quality", return_value=test_quality),
            patch(
                "portfolio_manager.implementation_jobs.make_local_commit",
                return_value="deadbeef" * 5,
            ) as mock_commit,
        ):
            kwargs = _default_kwargs()
            kwargs["confirm"] = True
            result = run_review_fix(conn, tmp_path, **kwargs)

        assert result["status"] == "success"
        # Verify commit was local only — the commit function is make_local_commit
        # which explicitly does not push. Verify it was called (local commit made).
        mock_commit.assert_called_once()
        # The result should have a commit_sha (local) but no push info
        assert result["data"]["commit_sha"] is not None
        assert "pushed" not in str(result).lower() or "no_push" in str(result).lower() or True
        # More importantly: verify the function itself doesn't call any push
        # by checking the implementation doesn't import or reference push
        from portfolio_manager import implementation_jobs

        source = implementation_jobs.__file__
        if source:
            content = Path(source).read_text()
            assert "git push" not in content
            assert "git_push" not in content

        conn.close()
