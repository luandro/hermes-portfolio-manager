"""Tests for portfolio_manager.worktree_git allowlist extensions (Phase 10.1)
and portfolio_manager.implementation_commit helper (Phase 10.2)."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from portfolio_manager.implementation_commit import make_local_commit
from portfolio_manager.worktree_git import (
    DEFAULT_TIMEOUTS,
    GitCommandError,
    get_clean_state,
    run_git,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers — bare repo + clone for real-git tests
# ---------------------------------------------------------------------------

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True, text=True)


@pytest.fixture
def commit_repo(tmp_path: Path) -> Path:
    """Bare remote + clone ready for commit tests."""
    seed = tmp_path / "_seed"
    seed.mkdir()
    _git("init", "-b", "main", str(seed), cwd=tmp_path)
    (seed / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md", cwd=seed)
    _git("commit", "-m", "initial", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "--bare", str(seed), str(bare), cwd=tmp_path)
    clone = tmp_path / "worktree"
    _git("clone", str(bare), str(clone), cwd=tmp_path)
    return clone


# ===================================================================
# Phase 10.1 — worktree_git allowlist extension tests
# ===================================================================


class TestWorktreeGitAllowlist:
    """Verify add/commit/rev-parse are properly allowlisted with validation."""

    def test_worktree_git_allows_add_A_for_implementation_commit(self, tmp_path: Path) -> None:
        """git add -A passes the allowlist check."""
        captured: dict = {}

        def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured["args"] = args
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
            result = run_git(["add", "-A"], cwd=tmp_path, timeout=30)
        assert result.returncode == 0
        assert captured["args"] == ["git", "add", "-A"]

    def test_worktree_git_allows_commit_with_per_command_user_config_and_m_message(self, tmp_path: Path) -> None:
        """git -c user.name=X -c user.email=Y commit -m msg passes validation."""
        captured: dict = {}

        def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured["args"] = args
            return subprocess.CompletedProcess(args, 0, "", "")

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
            result = run_git(
                ["-c", "user.name=Bot", "-c", "user.email=bot@t", "commit", "-m", "msg"],
                cwd=tmp_path,
                timeout=30,
            )
        assert result.returncode == 0

    def test_worktree_git_allows_rev_parse_head(self, tmp_path: Path) -> None:
        """git rev-parse HEAD is allowlisted (pre-existing)."""
        captured: dict = {}

        def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured["args"] = args
            return subprocess.CompletedProcess(args, 0, "abc123\n", "")

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
            result = run_git(["rev-parse", "HEAD"], cwd=tmp_path, timeout=30)
        assert result.returncode == 0

    def test_worktree_git_rejects_commit_amend(self, tmp_path: Path) -> None:
        """git commit --amend is rejected."""
        with pytest.raises(GitCommandError, match="forbidden"):
            run_git(["commit", "-m", "x", "--amend"], cwd=tmp_path, timeout=30)

    def test_worktree_git_rejects_commit_without_message(self, tmp_path: Path) -> None:
        """git commit without -m is rejected."""
        with pytest.raises(GitCommandError, match="-m"):
            run_git(["commit"], cwd=tmp_path, timeout=30)

    def test_worktree_git_rejects_commit_with_global_config(self, tmp_path: Path) -> None:
        """git -c core.xxx commit -m msg (not user.name/user.email) is rejected."""
        with pytest.raises(GitCommandError, match=r"user.name/user.email"):
            run_git(
                ["-c", "core.bare=true", "commit", "-m", "msg"],
                cwd=tmp_path,
                timeout=30,
            )

    def test_worktree_git_still_rejects_push_rebase_reset_clean_stash(self, tmp_path: Path) -> None:
        """Destructive commands remain forbidden."""
        for args in [
            ["push", "origin", "main"],
            ["rebase", "main"],
            ["reset", "--hard"],
            ["clean", "-fd"],
            ["stash"],
        ]:
            with pytest.raises(GitCommandError):
                run_git(args, cwd=tmp_path, timeout=30)

    def test_add_rejects_non_A_flag(self, tmp_path: Path) -> None:
        """git add with flags other than -A is rejected."""
        with pytest.raises(GitCommandError, match="add -A"):
            run_git(["add", "somefile.txt"], cwd=tmp_path, timeout=30)

    def test_add_rejects_extra_args(self, tmp_path: Path) -> None:
        """git add -A with extra args is rejected."""
        with pytest.raises(GitCommandError, match="add -A"):
            run_git(["add", "-A", "extra"], cwd=tmp_path, timeout=30)

    def test_commit_rejects_no_verify(self, tmp_path: Path) -> None:
        """git commit --no-verify is rejected."""
        with pytest.raises(GitCommandError, match="forbidden"):
            run_git(["commit", "-m", "msg", "--no-verify"], cwd=tmp_path, timeout=30)

    def test_commit_rejects_allow_empty(self, tmp_path: Path) -> None:
        """git commit --allow-empty is rejected."""
        with pytest.raises(GitCommandError, match="forbidden"):
            run_git(["commit", "-m", "msg", "--allow-empty"], cwd=tmp_path, timeout=30)

    def test_commit_rejects_signoff(self, tmp_path: Path) -> None:
        """git commit --signoff is rejected."""
        with pytest.raises(GitCommandError, match="forbidden"):
            run_git(["commit", "-m", "msg", "--signoff"], cwd=tmp_path, timeout=30)

    def test_commit_rejects_file_flag(self, tmp_path: Path) -> None:
        """git commit -F is rejected."""
        with pytest.raises(GitCommandError, match="forbidden"):
            run_git(["commit", "-F", "/tmp/msg"], cwd=tmp_path, timeout=30)

    def test_commit_rejects_extra_message_args(self, tmp_path: Path) -> None:
        """git commit -m a b (extra positional) is rejected."""
        with pytest.raises(GitCommandError, match="exactly one message"):
            run_git(["commit", "-m", "a", "b"], cwd=tmp_path, timeout=30)

    def test_timeouts_for_add_and_commit(self) -> None:
        """DEFAULT_TIMEOUTS has entries for add and commit."""
        assert DEFAULT_TIMEOUTS["add"] == 30
        assert DEFAULT_TIMEOUTS["commit"] == 30


# ===================================================================
# Phase 10.2 — implementation_commit helper tests
# ===================================================================


class TestCommitHelper:
    """Tests for make_local_commit using real git repos."""

    def test_commit_runs_only_after_checks_pass(self, commit_repo: Path) -> None:
        """make_local_commit succeeds when there are changes to commit."""
        (commit_repo / "new_file.txt").write_text("content", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-1",
            issue_number=42,
            message="Add new file",
        )
        assert sha is not None
        assert len(sha) == 40

    def test_commit_uses_argument_array_no_shell(self, commit_repo: Path) -> None:
        """All subprocess calls use argument arrays, never shell."""
        (commit_repo / "file.txt").write_text("x", encoding="utf-8")
        captured_calls: list[dict] = []
        original_run = subprocess.run

        def tracking_run(*args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured_calls.append({"args": args[0] if args else kwargs.get("args"), "kwargs": kwargs})
            return original_run(*args, **kwargs)

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=tracking_run):
            make_local_commit(
                commit_repo,
                job_id="job-2",
                issue_number=7,
                message="Test file",
            )

        for call in captured_calls:
            assert isinstance(call["args"], list), f"Expected list, got {type(call['args'])}"
            assert not call["kwargs"].get("shell", False), "shell=True found"

    def test_commit_uses_minus_m_with_safe_message(self, commit_repo: Path) -> None:
        """The commit uses -m flag with the provided message."""
        (commit_repo / "safe.txt").write_text("y", encoding="utf-8")
        captured_cmds: list[list[str]] = []
        original_run = subprocess.run

        def tracking_run(args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured_cmds.append(list(args))
            return original_run(args, **kwargs)

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=tracking_run):
            make_local_commit(
                commit_repo,
                job_id="job-3",
                issue_number=10,
                message="Safe message here",
            )

        # Find the commit command (has '-m' in it)
        commit_cmd = None
        for cmd in captured_cmds:
            if "-m" in cmd:
                commit_cmd = cmd
                break
        assert commit_cmd is not None, "No commit command found"
        m_idx = commit_cmd.index("-m")
        msg = commit_cmd[m_idx + 1]
        assert "Safe message here" in msg

    def test_commit_message_includes_job_id_and_issue_number(self, commit_repo: Path) -> None:
        """The commit message body includes job_id and issue_number."""
        (commit_repo / "msg.txt").write_text("z", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-abc",
            issue_number=99,
            message="My change",
        )
        assert sha is not None
        # Read the commit message via git log
        log = _git("log", "-1", "--format=%B", cwd=commit_repo)
        body = log.stdout
        assert "job-abc" in body
        assert "#99" in body

    def test_commit_message_omits_provider_credentials_or_paths_under_user_home(self, commit_repo: Path) -> None:
        """Commit message must not leak home directory paths or credentials."""
        (commit_repo / "cred.txt").write_text("w", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-safe",
            issue_number=1,
            message="Normal change",
        )
        assert sha is not None
        log = _git("log", "-1", "--format=%B", cwd=commit_repo)
        body = log.stdout
        # Must not contain home dir patterns
        assert "/home/" not in body
        assert "~/" not in body
        # Must not contain credential patterns
        assert "ghp_" not in body
        assert "token=" not in body
        assert "password=" not in body

    def test_commit_blocks_when_worktree_dirty_with_unstaged_after_harness(self, commit_repo: Path) -> None:
        """Dirty worktree (modified tracked file) is committed successfully."""
        (commit_repo / "README.md").write_text("modified\n", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-dirty",
            issue_number=5,
            message="Modify tracked",
        )
        assert sha is not None
        # Verify the tree is now clean
        assert get_clean_state(commit_repo) == "clean"

    def test_commit_blocks_when_worktree_clean_no_changes_to_commit(self, commit_repo: Path) -> None:
        """Clean worktree returns None (no commit attempted)."""
        result = make_local_commit(
            commit_repo,
            job_id="job-clean",
            issue_number=3,
            message="Nothing to do",
        )
        assert result is None

    def test_commit_returns_sha_after_success(self, commit_repo: Path) -> None:
        """Returned SHA matches actual HEAD."""
        (commit_repo / "sha_test.txt").write_text("sha", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-sha",
            issue_number=8,
            message="SHA test",
        )
        assert sha is not None
        # Verify it matches HEAD
        head = _git("rev-parse", "HEAD", cwd=commit_repo)
        assert sha == head.stdout.strip()

    def test_commit_does_NOT_call_git_push_amend_rebase_reset_clean_stash(self, commit_repo: Path) -> None:
        """No destructive git commands are called during commit."""
        (commit_repo / "safe2.txt").write_text("s", encoding="utf-8")
        captured_cmds: list[list[str]] = []
        original_run = subprocess.run

        def tracking_run(args, **kwargs):  # type: ignore[no-untyped-def]  # mock matches subprocess.run
            captured_cmds.append(list(args))
            return original_run(args, **kwargs)

        with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=tracking_run):
            make_local_commit(
                commit_repo,
                job_id="job-no-destruct",
                issue_number=11,
                message="Safe",
            )

        banned_leaders = {"push", "amend", "rebase", "reset", "clean", "stash"}
        for cmd in captured_cmds:
            # cmd[0] is 'git', cmd[1] is the leader or first flag
            for token in cmd[1:]:
                assert token not in banned_leaders, f"Banned command {token} in {cmd}"

    def test_commit_does_NOT_set_user_email_or_user_name_globally(self, commit_repo: Path) -> None:
        """Global gitconfig is not modified — author is set per-command only."""
        (commit_repo / "global_test.txt").write_text("g", encoding="utf-8")
        # Capture global config before
        before_name = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
        )
        before_email = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True,
        )

        make_local_commit(
            commit_repo,
            job_id="job-global",
            issue_number=12,
            message="Global test",
        )

        after_name = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
        )
        after_email = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True,
        )

        assert before_name.stdout == after_name.stdout
        assert before_email.stdout == after_email.stdout

    def test_commit_with_untracked_files(self, commit_repo: Path) -> None:
        """Untracked files are staged and committed."""
        (commit_repo / "untracked_new.py").write_text("print('hi')", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-untracked",
            issue_number=15,
            message="Add untracked",
        )
        assert sha is not None
        assert get_clean_state(commit_repo) == "clean"

    def test_commit_author_is_per_command(self, commit_repo: Path) -> None:
        """The commit author matches the per-command config, not global."""
        (commit_repo / "author.txt").write_text("a", encoding="utf-8")
        sha = make_local_commit(
            commit_repo,
            job_id="job-author",
            issue_number=20,
            message="Author test",
            author_name="Custom Bot",
            author_email="custom@bot.local",
        )
        assert sha is not None
        # Verify author
        author = _git("log", "-1", "--format=%an", cwd=commit_repo)
        email = _git("log", "-1", "--format=%ae", cwd=commit_repo)
        assert author.stdout.strip() == "Custom Bot"
        assert email.stdout.strip() == "custom@bot.local"
