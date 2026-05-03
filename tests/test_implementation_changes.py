"""Tests for portfolio_manager.implementation_changes — Phase 8.2."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from portfolio_manager.implementation_changes import ChangedFiles, collect_changed_files

if TYPE_CHECKING:
    from pathlib import Path


def _git(*args: str, cwd: Path) -> None:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True)


def _make_workspace(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "root"
    root.mkdir()
    wt_root = root / "worktrees"
    wt_root.mkdir()
    workspace = wt_root / "proj-issue-1"
    workspace.mkdir()
    return root, workspace


def _init_repo(workspace: Path) -> None:
    _git("init", "-b", "main", cwd=workspace)
    (workspace / "README.md").write_text("init\n", encoding="utf-8")
    _git("add", "README.md", cwd=workspace)
    _git("commit", "-m", "init", cwd=workspace)


def test_collect_changed_files_uses_git_status_porcelain(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    # Modify a tracked file
    (workspace / "README.md").write_text("changed\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    assert any("README.md" in f for f in result.files)


def test_collect_changed_files_includes_untracked_files(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    (workspace / "new_file.py").write_text("print('hello')\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    assert "new_file.py" in result.files
    # Untracked files should have status starting with ??
    status_entry = next(s for s in result.statuses if s["path"] == "new_file.py")
    assert "??" in status_entry["status"]


def test_collect_changed_files_detects_renames(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    # Create a file, commit it, then rename
    (workspace / "old_name.py").write_text("content\n", encoding="utf-8")
    _git("add", "old_name.py", cwd=workspace)
    _git("commit", "-m", "add old", cwd=workspace)
    _git("mv", "old_name.py", "new_name.py", cwd=workspace)

    result = collect_changed_files(workspace, root=root)
    assert "new_name.py" in result.files
    # Should have an old_path reference
    rename_entries = [s for s in result.statuses if "old_path" in s]
    assert len(rename_entries) > 0


def test_collect_changed_files_normalizes_to_posix_relative_paths(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    # Create a file in a subdirectory
    subdir = workspace / "src"
    subdir.mkdir()
    (subdir / "main.py").write_text("code\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    assert "src/main.py" in result.files
    # No backslashes
    for f in result.files:
        assert "\\" not in f


def test_collect_changed_files_blocks_absolute_or_dotdot_paths(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    # Normal changes
    (workspace / "safe.py").write_text("ok\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    for f in result.files:
        assert not os.path.isabs(f), f"absolute path leaked: {f}"
        assert ".." not in f, f"dotdot path leaked: {f}"


def test_collect_changed_files_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    (workspace / "inside.py").write_text("ok\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    # All paths should be relative (no leading /)
    for f in result.files:
        assert not f.startswith("/")


def test_collect_changed_files_requires_workspace_under_worktrees_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()

    with pytest.raises(ValueError, match="escapes worktrees root"):
        collect_changed_files(outside, root=root)


def test_collect_changed_files_allows_dirty_workspace_after_harness_for_scope_gate(tmp_path: Path) -> None:
    """After a harness runs, the workspace is dirty. collect_changed_files must work on dirty workspaces."""
    root, workspace = _make_workspace(tmp_path)
    _init_repo(workspace)
    # Simulate harness output: modified + untracked files
    (workspace / "README.md").write_text("changed by harness\n", encoding="utf-8")
    (workspace / "new_feature.py").write_text("def feature(): pass\n", encoding="utf-8")
    subdir = workspace / "tests"
    subdir.mkdir()
    (subdir / "test_feature.py").write_text("def test_feature(): pass\n", encoding="utf-8")

    result = collect_changed_files(workspace, root=root)
    assert "README.md" in result.files
    assert "new_feature.py" in result.files
    assert "tests/test_feature.py" in result.files
    assert isinstance(result, ChangedFiles)
    assert isinstance(result.files, list)
    assert isinstance(result.statuses, list)
