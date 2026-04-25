"""Tests for portfolio_manager.worktree — git worktree discovery and inspection."""

from __future__ import annotations

import subprocess
from pathlib import Path

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.worktree import (
    discover_issue_worktrees,
    inspect_project_worktrees,
    inspect_worktree,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    """Run a git command using argument arrays (no shell=True)."""
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> Path:
    """Create a minimal git repo with one initial commit. Returns the path."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    (path / "README.md").write_text("hello")
    _git("add", "README.md", cwd=path)
    _git("commit", "-m", "init", cwd=path)
    return path


def _make_project(
    project_id: str = "comapeo-cloud-app",
    base_path: Path | None = None,
    root: Path | None = None,
) -> ProjectConfig:
    """Build a ProjectConfig for testing."""
    if base_path is None:
        base_path = root / "worktrees" / project_id if root else Path("/tmp/dummy")
    if root is not None:
        issue_pattern = str(root / "worktrees" / f"{project_id}-issue-{{issue_number}}")
    else:
        issue_pattern = f"/tmp/{project_id}-issue-{{issue_number}}"
    return ProjectConfig(
        id=project_id,
        name="Test Project",
        repo="test/repo",
        github=GithubRef(owner="test", repo="repo"),
        priority="medium",
        status="active",
        local=LocalPaths(base_path=base_path, issue_worktree_pattern=issue_pattern),
    )


# ---------------------------------------------------------------------------
# 3.1 discover_issue_worktrees
# ---------------------------------------------------------------------------


class TestDiscoverIssueWorktrees:
    def test_finds_issue_dirs_and_extracts_numbers(self, tmp_path: Path) -> None:
        root = tmp_path
        worktrees = root / "worktrees"
        worktrees.mkdir()
        (worktrees / "comapeo-cloud-app-issue-123").mkdir()
        (worktrees / "comapeo-cloud-app-issue-47").mkdir()
        (worktrees / "unrelated-folder").mkdir()

        project = _make_project("comapeo-cloud-app", root=root)
        result = discover_issue_worktrees(root, project)

        numbers = {c.issue_number for c in result}
        assert numbers == {123, 47}
        assert all(c.path.parent == worktrees for c in result)

    def test_ignores_unrelated_dirs(self, tmp_path: Path) -> None:
        root = tmp_path
        worktrees = root / "worktrees"
        worktrees.mkdir()
        (worktrees / "unrelated-folder").mkdir()
        (worktrees / "other-project-issue-99").mkdir()

        project = _make_project("comapeo-cloud-app", root=root)
        result = discover_issue_worktrees(root, project)

        assert result == []

    def test_no_worktrees_dir(self, tmp_path: Path) -> None:
        project = _make_project("comapeo-cloud-app", root=tmp_path)
        result = discover_issue_worktrees(tmp_path, project)
        assert result == []


# ---------------------------------------------------------------------------
# 3.2-3.7 inspect_worktree
# ---------------------------------------------------------------------------


class TestInspectWorktree:
    def test_missing_path(self, tmp_path: Path) -> None:
        gone = tmp_path / "does-not-exist"
        result = inspect_worktree(gone)
        assert result.state == "missing"

    def test_non_git_path(self, tmp_path: Path) -> None:
        not_a_repo = tmp_path / "plain-dir"
        not_a_repo.mkdir()
        result = inspect_worktree(not_a_repo)
        assert result.state == "blocked"

    def test_clean_worktree(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        result = inspect_worktree(repo)
        assert result.state == "clean"
        assert result.branch_name is not None

    def test_dirty_tracked_file(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "README.md").write_text("modified content")
        result = inspect_worktree(repo)
        assert result.state == "dirty_uncommitted"
        assert result.dirty_summary is not None
        assert "README.md" in result.dirty_summary

    def test_dirty_untracked_file(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        (repo / "new_file.txt").write_text("I am untracked")
        result = inspect_worktree(repo)
        assert result.state == "dirty_untracked"
        assert result.dirty_summary is not None
        assert "new_file.txt" in result.dirty_summary

    def test_merge_conflict_state(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        # Simulate a merge in progress by creating MERGE_HEAD at the resolved git path
        _git("commit", "--allow-empty", "-m", "second", cwd=repo)
        result_merge_head = subprocess.run(
            ["git", "rev-parse", "--git-path", "MERGE_HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        merge_head_path = Path(result_merge_head.stdout.strip())
        if not merge_head_path.is_absolute():
            merge_head_path = repo / merge_head_path
        merge_head_path.write_text("abc123\n")
        result = inspect_worktree(repo)
        assert result.state == "merge_conflict"

    def test_rebase_conflict_state(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        # Simulate a rebase in progress by creating rebase-merge directory
        result_git_dir = subprocess.run(
            ["git", "rev-parse", "--git-path", "rebase-merge"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        rebase_merge_path = Path(result_git_dir.stdout.strip())
        if not rebase_merge_path.is_absolute():
            rebase_merge_path = repo / rebase_merge_path
        rebase_merge_path.mkdir(parents=True, exist_ok=True)
        result = inspect_worktree(repo)
        assert result.state == "rebase_conflict"


# ---------------------------------------------------------------------------
# 3.8 inspect_project_worktrees
# ---------------------------------------------------------------------------


class TestInspectProjectWorktrees:
    def test_combined_base_and_issue_worktrees(self, tmp_path: Path) -> None:
        root = tmp_path
        worktrees_dir = root / "worktrees"
        worktrees_dir.mkdir()

        # Base worktree — clean git repo
        base_repo = _init_repo(worktrees_dir / "comapeo-cloud-app")

        # Issue worktree 1 — clean
        issue_repo_1 = _init_repo(worktrees_dir / "comapeo-cloud-app-issue-10")

        # Issue worktree 2 — dirty (untracked)
        issue_repo_2 = _init_repo(worktrees_dir / "comapeo-cloud-app-issue-20")
        (issue_repo_2 / "untracked.txt").write_text("new")

        # Unrelated folder — should be ignored by discovery
        (worktrees_dir / "unrelated-folder").mkdir()

        project = _make_project("comapeo-cloud-app", base_path=base_repo, root=root)
        results = inspect_project_worktrees(project)

        # Should have 3 inspections: base + 2 issue worktrees
        assert len(results) == 3

        states = {r.path: r.state for r in results}
        assert states[str(base_repo)] == "clean"
        assert states[str(issue_repo_1)] == "clean"
        assert states[str(issue_repo_2)] == "dirty_untracked"
