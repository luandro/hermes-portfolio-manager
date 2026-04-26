"""Git worktree discovery and inspection for the Portfolio Manager plugin.

Handles: discovering issue worktrees by naming convention, inspecting worktree
state (clean/dirty/conflict/missing/blocked), and reporting results.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portfolio_manager.config import ProjectConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WorktreeCandidate:
    path: Path
    issue_number: int


@dataclass
class WorktreeInspection:
    path: str
    project_id: str
    issue_number: int | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    state: str = "unknown"
    dirty_summary: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# 3.1 discover_issue_worktrees
# ---------------------------------------------------------------------------


def discover_issue_worktrees(root: Path, project: ProjectConfig) -> list[WorktreeCandidate]:
    """Find directories matching {project_id}-issue-{number} in root/worktrees/."""
    worktrees_dir = root / "worktrees"
    if not worktrees_dir.is_dir():
        return []

    prefix = f"{project.id}-issue-"
    candidates: list[WorktreeCandidate] = []

    for entry in worktrees_dir.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        if not suffix.isdigit():
            continue
        candidates.append(WorktreeCandidate(path=entry, issue_number=int(suffix)))

    return candidates


# ---------------------------------------------------------------------------
# Internal helpers for inspect_worktree
# ---------------------------------------------------------------------------


def _run_git(*args: str, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run a git command with argument arrays. Returns CompletedProcess."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git %s timed out after %ds in %s", args, timeout, cwd)
        return subprocess.CompletedProcess(args=["git", *args], returncode=124, stdout="", stderr="timeout")


def _is_git_repo(path: Path) -> bool:
    """Check if path is inside a git work tree."""
    result = _run_git("rev-parse", "--is-inside-work-tree", cwd=path)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _resolve_git_path(path: Path, git_path: str) -> Path:
    """Resolve a git internal path via ``git rev-parse --git-path``."""
    result = _run_git("rev-parse", "--git-path", git_path, cwd=path)
    if result.returncode != 0 or not result.stdout.strip():
        # Return a path that won't exist so the caller's .exists() check works correctly
        return path / f"__git_internal_{git_path}_not_found__"
    resolved = Path(result.stdout.strip())
    # git rev-parse may return a relative path; resolve against the repo root
    if not resolved.is_absolute():
        resolved = path / resolved
    return resolved


def _get_branch_name(path: Path) -> str | None:
    """Get current branch name via ``git branch --show-current``."""
    result = _run_git("branch", "--show-current", cwd=path)
    if result.returncode == 0:
        name = result.stdout.strip()
        return name if name else None
    return None


def _parse_porcelain(porcelain: str) -> tuple[list[str], list[str], list[str]]:
    """Parse git status --porcelain=v1 output.

    Returns (modified_tracked, untracked, conflict) file lists.
    """
    modified: list[str] = []
    untracked: list[str] = []
    conflict: list[str] = []

    for line in porcelain.splitlines():
        if not line:
            continue
        xy = line[:2]
        filepath = line[3:]
        # For rename/copy entries, extract the destination path
        if " -> " in filepath:
            filepath = filepath.split(" -> ", 1)[1]
        # Conflict indicators: UU, AA, DD, AU, UA, DU, UD
        if xy in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
            conflict.append(filepath)
        # Untracked
        elif xy == "??":
            untracked.append(filepath)
        # Modified: staged (index) OR unstaged (working tree) changes
        elif xy[0] not in (" ", "?") or xy[1] not in (" ", "?"):
            modified.append(filepath)

    return modified, untracked, conflict


# ---------------------------------------------------------------------------
# 3.2-3.7 inspect_worktree
# ---------------------------------------------------------------------------


def inspect_worktree(path: Path, project_id: str = "", issue_number: int | None = None) -> WorktreeInspection:
    """Inspect a single worktree path and return its state.

    State detection priority:
    1. missing  — path doesn't exist
    2. blocked  — exists but not a git repo
    3. rebase_conflict — rebase-merge or rebase-apply exists
    4. merge_conflict  — MERGE_HEAD exists or porcelain shows conflicts
    5. dirty_uncommitted — modified tracked files
    6. dirty_untracked  — untracked files only
    7. clean — none of the above
    """
    inspection = WorktreeInspection(
        path=str(path),
        project_id=project_id,
        issue_number=issue_number,
    )

    # 1. Missing
    if not path.exists():
        inspection.state = "missing"
        return inspection

    # 2. Not a git repo
    if not _is_git_repo(path):
        inspection.state = "blocked"
        return inspection

    # Capture branch name
    inspection.branch_name = _get_branch_name(path)

    # 3. Rebase in progress
    rebase_merge = _resolve_git_path(path, "rebase-merge")
    rebase_apply = _resolve_git_path(path, "rebase-apply")
    if rebase_merge.exists() or rebase_apply.exists():
        inspection.state = "rebase_conflict"
        return inspection

    # 4. Merge in progress — check MERGE_HEAD
    merge_head = _resolve_git_path(path, "MERGE_HEAD")
    merge_in_progress = merge_head.exists()

    # Get porcelain status
    porcelain_result = _run_git("status", "--porcelain=v1", cwd=path)
    porcelain_output = porcelain_result.stdout
    modified, untracked, conflict_files = _parse_porcelain(porcelain_output)

    if merge_in_progress or conflict_files:
        inspection.state = "merge_conflict"
        all_dirty = conflict_files + modified + untracked
        if all_dirty:
            inspection.dirty_summary = ", ".join(all_dirty)
        return inspection

    # 5. Dirty — modified tracked files
    if modified:
        inspection.state = "dirty_uncommitted"
        inspection.dirty_summary = ", ".join(modified)
        return inspection

    # 6. Dirty — untracked files
    if untracked:
        inspection.state = "dirty_untracked"
        inspection.dirty_summary = ", ".join(untracked)
        return inspection

    # 7. Clean
    inspection.state = "clean"
    return inspection


# ---------------------------------------------------------------------------
# 3.8 inspect_project_worktrees
# ---------------------------------------------------------------------------


def inspect_project_worktrees(project: ProjectConfig, root: Path | None = None) -> list[WorktreeInspection]:
    """Inspect the base worktree and all issue worktrees for a project.

    Pass ``root`` explicitly (the agent-system root) so that issue-worktree
    discovery works correctly when ``local.base_path`` is configured to a
    non-default location.  When omitted, root is derived from base_path as a
    fallback (only reliable for the default path layout).

    Returns a combined list of WorktreeInspection for every discovered worktree.
    """
    results: list[WorktreeInspection] = []

    base_path = project.local.base_path
    if root is None:
        root = base_path.parent.parent

    # Inspect base worktree
    base_inspection = inspect_worktree(base_path, project_id=project.id)
    results.append(base_inspection)

    # Discover and inspect issue worktrees
    candidates = discover_issue_worktrees(root, project)
    for candidate in candidates:
        issue_inspection = inspect_worktree(
            candidate.path,
            project_id=project.id,
            issue_number=candidate.issue_number,
        )
        results.append(issue_inspection)

    return results
