"""Tests for portfolio_manager.worktree_git — runner + read-only probes (Phase 2)."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.worktree_git import (
    GitCommandError,
    branch_exists,
    get_clean_state,
    get_origin_url,
    is_git_repo,
    list_worktrees,
    local_branch_diverges_from_origin,
    run_gh,
    run_git,
)

# ---------------------------------------------------------------------------
# 2.1 Allowlisted runner
# ---------------------------------------------------------------------------


def test_run_git_uses_argument_array(tmp_path: Path) -> None:
    captured: dict = {}

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["args"] = args
        captured["shell"] = kwargs.get("shell", False)
        return subprocess.CompletedProcess(args, 0, "git version 2.0\n", "")

    with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
        run_git(["--version"], cwd=tmp_path, timeout=5)
    assert captured["args"][0] == "git"
    assert captured["shell"] is False


def test_run_git_sets_GIT_TERMINAL_PROMPT_zero(tmp_path: Path) -> None:
    captured: dict = {}

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(args, 0, "", "")

    with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
        run_git(["--version"], cwd=tmp_path, timeout=5)
    assert captured["env"]["GIT_TERMINAL_PROMPT"] == "0"


def test_run_git_applies_timeout_per_command(tmp_path: Path) -> None:
    captured: dict = {}

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        captured["timeout"] = kwargs["timeout"]
        return subprocess.CompletedProcess(args, 0, "", "")

    with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
        run_git(["status", "--porcelain=v1"], cwd=tmp_path, timeout=30)
    assert captured["timeout"] == 30


def test_run_git_rejects_non_allowlisted_subcommand(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError):
        run_git(["push", "origin", "main"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_git(["commit", "-m", "x"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_git(["reset", "--hard"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_git(["clean", "-fd"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_git(["stash"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_git(["rebase", "main"], cwd=tmp_path, timeout=5)


def test_run_git_redacts_credentials_in_stderr_capture(tmp_path: Path) -> None:
    leaked = "fatal: cannot access https://user:ghp_AAAA1111@github.com/o/r.git\n"

    def fake_run(args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args, 128, "", leaked)

    with patch("portfolio_manager.worktree_git.subprocess.run", side_effect=fake_run):
        result = run_git(["--version"], cwd=tmp_path, timeout=5)
    assert "ghp_AAAA1111" not in result.stderr
    assert "ghp_***" in result.stderr or "***" in result.stderr


def test_run_gh_only_allows_get_methods(tmp_path: Path) -> None:
    with pytest.raises(GitCommandError):
        run_gh(["api", "--method", "POST", "repos/o/r"], cwd=tmp_path, timeout=5)
    with pytest.raises(GitCommandError):
        run_gh(["issue", "create", "--title", "x"], cwd=tmp_path, timeout=5)


# ---------------------------------------------------------------------------
# 2.2 Read-only probes (use bare repo fixture)
# ---------------------------------------------------------------------------


def test_is_git_repo_true_for_clone(cloned_repo: Path) -> None:
    assert is_git_repo(cloned_repo)


def test_is_git_repo_false_for_plain_dir(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    assert not is_git_repo(plain)


def test_get_remote_url_returns_origin(cloned_repo: Path, bare_remote: Path) -> None:
    url = get_origin_url(cloned_repo)
    assert url is not None
    assert str(bare_remote) in url


def test_clean_state_for_fresh_clone(cloned_repo: Path) -> None:
    assert get_clean_state(cloned_repo) == "clean"


def test_dirty_uncommitted_for_modified_tracked_file(cloned_repo: Path) -> None:
    (cloned_repo / "README.md").write_text("changed\n", encoding="utf-8")
    assert get_clean_state(cloned_repo) == "dirty_uncommitted"


def test_dirty_untracked_for_new_file(cloned_repo: Path) -> None:
    (cloned_repo / "new.txt").write_text("x", encoding="utf-8")
    assert get_clean_state(cloned_repo) == "dirty_untracked"


def test_branch_exists_local(cloned_repo: Path) -> None:
    assert branch_exists(cloned_repo, "main", remote=False)
    assert not branch_exists(cloned_repo, "nonexistent", remote=False)


def test_branch_exists_origin(cloned_repo: Path) -> None:
    assert branch_exists(cloned_repo, "main", remote=True)
    assert not branch_exists(cloned_repo, "nonexistent", remote=True)


def test_local_branch_has_commits_not_in_origin(cloned_repo: Path) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    (cloned_repo / "extra.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "extra.txt"], cwd=cloned_repo, check=True, env=env)
    subprocess.run(["git", "commit", "-m", "extra"], cwd=cloned_repo, check=True, env=env, capture_output=True)
    assert local_branch_diverges_from_origin(cloned_repo, "main")


def test_local_branch_in_sync_with_origin(cloned_repo: Path) -> None:
    assert not local_branch_diverges_from_origin(cloned_repo, "main")


def test_worktree_list_porcelain_parsed(cloned_repo: Path) -> None:
    entries = list_worktrees(cloned_repo)
    paths = {e.get("worktree") for e in entries}
    assert str(cloned_repo) in paths or str(cloned_repo.resolve()) in paths


def test_merge_conflict_state_detected(cloned_repo: Path) -> None:
    """Force a merge conflict by hand-writing MERGE_HEAD; we don't execute git merge."""
    (cloned_repo / ".git" / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")
    assert get_clean_state(cloned_repo) == "merge_conflict"


def test_rebase_conflict_state_detected(cloned_repo: Path) -> None:
    rb = cloned_repo / ".git" / "rebase-apply"
    rb.mkdir()
    assert get_clean_state(cloned_repo) == "rebase_conflict"
