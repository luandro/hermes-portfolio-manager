"""Changed-file collector for MVP 6 implementation runner.

Collects the list of files changed by a harness run using read-only git
commands (status + diff). Paths are normalized to POSIX-relative form and
validated to stay within the workspace.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from portfolio_manager.worktree_git import DEFAULT_TIMEOUTS, run_git
from portfolio_manager.worktree_paths import assert_under_worktrees_root


@dataclass(frozen=True)
class ChangedFiles:
    files: list[str]
    statuses: list[dict[str, str]]  # {path, status, old_path?}


def _is_safe_relative_path(p: str) -> bool:
    """Reject absolute paths, '..' components, and empty strings."""
    if not p:
        return False
    if os.path.isabs(p):
        return False
    parts = PurePosixPath(p).parts
    return ".." not in parts


def collect_changed_files(workspace: Path, *, root: Path) -> ChangedFiles:
    """Collect changed files from git status and diff.

    Uses ``git status --porcelain=v1 --untracked-files=all`` and
    ``git diff --name-status --find-renames HEAD``. Paths are normalized
    to POSIX relative and validated for safety.
    """
    assert_under_worktrees_root(workspace, root)

    # Collect from git status (includes untracked)
    status_result = run_git(
        ["status", "--porcelain=v1", "--untracked-files=all"],
        cwd=workspace,
        timeout=DEFAULT_TIMEOUTS["status"],
    )
    if status_result.returncode != 0:
        return ChangedFiles(files=[], statuses=[])

    seen_paths: set[str] = set()
    statuses: list[dict[str, str]] = []

    for line in status_result.stdout.splitlines():
        if not line or len(line) < 4:
            continue
        xy = line[:2]
        filepath = line[3:]
        if not _is_safe_relative_path(filepath):
            continue
        # Normalize to POSIX
        posix_path = PurePosixPath(filepath).as_posix()
        if posix_path in seen_paths:
            continue
        seen_paths.add(posix_path)
        statuses.append({"path": posix_path, "status": xy})

    # Collect renames from git diff
    diff_result = run_git(
        ["diff", "--name-status", "--find-renames", "HEAD"],
        cwd=workspace,
        timeout=DEFAULT_TIMEOUTS["diff"],
    )
    if diff_result.returncode == 0:
        for line in diff_result.stdout.splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].startswith("R"):
                # Rename: R100\told_path\tnew_path
                old_path = PurePosixPath(parts[1]).as_posix()
                new_path = PurePosixPath(parts[2]).as_posix()
                if _is_safe_relative_path(old_path) and _is_safe_relative_path(new_path):
                    # Add old_path if not already seen
                    if old_path not in seen_paths:
                        seen_paths.add(old_path)
                        statuses.append({"path": old_path, "status": "D", "old_path": old_path})
                    # Update/add new_path with rename info
                    if new_path not in seen_paths:
                        seen_paths.add(new_path)
                        statuses.append({"path": new_path, "status": "A", "old_path": old_path})
                    else:
                        # Update existing entry with old_path
                        for s in statuses:
                            if s["path"] == new_path:
                                s["old_path"] = old_path
                                break
            elif len(parts) >= 2:
                # Standard change: status\tpath
                status_code = parts[0]
                filepath = parts[1]
                if not _is_safe_relative_path(filepath):
                    continue
                posix_path = PurePosixPath(filepath).as_posix()
                if posix_path not in seen_paths:
                    seen_paths.add(posix_path)
                    statuses.append({"path": posix_path, "status": status_code})

    files = sorted(seen_paths)
    return ChangedFiles(files=files, statuses=statuses)
