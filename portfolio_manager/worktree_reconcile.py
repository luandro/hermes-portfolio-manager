"""Worktree discovery / reconciliation — MVP 5 Phase 9.

Walks ``$ROOT/worktrees`` and classifies each entry into base / issue /
unknown without mutating anything. Used by the list, inspect, and
explain handlers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from portfolio_manager.worktree_git import (
    get_clean_state,
    get_origin_url,
    is_git_repo,
)
from portfolio_manager.worktree_paths import normalize_remote_url, remotes_equal

if TYPE_CHECKING:
    from pathlib import Path

    from portfolio_manager.config import ProjectConfig


@dataclass
class DiscoveredWorktree:
    """A worktree directory found on disk."""

    project_id: str
    path: str
    kind: str  # "base" | "issue" | "unknown"
    issue_number: int | None = None
    branch_name: str | None = None
    state: str = "unknown"
    remote_url: str | None = None
    remote_matches_config: bool | None = None
    notes: list[str] = field(default_factory=list)


_ISSUE_DIR_RE = re.compile(r"^(?P<project>[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63})-issue-(?P<n>[1-9][0-9]{0,9})$")


def _classify_directory(path: Path, projects: list[ProjectConfig]) -> tuple[str, str | None, int | None]:
    """Classify *path* as base/issue/unknown and identify the project + issue."""
    name = path.name
    m = _ISSUE_DIR_RE.match(name)
    if m:
        project_id = m.group("project")
        return ("issue", project_id, int(m.group("n")))
    for p in projects:
        if name == p.id:
            return ("base", p.id, None)
    return ("unknown", None, None)


def _branch_name(path: Path) -> str | None:
    """Return the current HEAD branch name, or ``None`` for detached/non-repo."""
    from portfolio_manager.worktree_git import DEFAULT_TIMEOUTS, run_git

    res = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path, timeout=DEFAULT_TIMEOUTS["rev-parse"])
    if res.returncode != 0:
        return None
    val = res.stdout.strip()
    return None if val in ("", "HEAD") else val


def discover_worktrees(
    root: Path,
    projects: list[ProjectConfig],
    *,
    inspect: bool = False,
) -> list[DiscoveredWorktree]:
    """Walk ``$ROOT/worktrees``, classify and (optionally) probe each entry."""
    worktrees_dir = root / "worktrees"
    if not worktrees_dir.exists():
        return []
    project_by_id = {p.id: p for p in projects}
    out: list[DiscoveredWorktree] = []
    for entry in sorted(worktrees_dir.iterdir()):
        if not entry.is_dir():
            continue
        kind, project_id, issue_number = _classify_directory(entry, projects)
        wt = DiscoveredWorktree(
            project_id=project_id or "",
            path=str(entry),
            kind=kind,
            issue_number=issue_number,
        )
        if not inspect:
            out.append(wt)
            continue
        if not is_git_repo(entry):
            wt.notes.append("not a git repo")
            wt.state = "missing"
            out.append(wt)
            continue
        wt.branch_name = _branch_name(entry)
        wt.state = get_clean_state(entry)
        origin = get_origin_url(entry)
        wt.remote_url = normalize_remote_url(origin) if origin else None
        if project_id and project_id in project_by_id:
            cfg_remote = project_by_id[project_id].repo
            wt.remote_matches_config = bool(origin) and remotes_equal(origin or "", cfg_remote)
        out.append(wt)
    return out


def discovered_to_dict(wt: DiscoveredWorktree) -> dict[str, object]:
    return {
        "project_id": wt.project_id,
        "path": wt.path,
        "kind": wt.kind,
        "issue_number": wt.issue_number,
        "branch_name": wt.branch_name,
        "state": wt.state,
        "remote_url": wt.remote_url,
        "remote_matches_config": wt.remote_matches_config,
        "notes": list(wt.notes),
    }


def suggest_next_action(state: str, kind: str) -> str:
    """Return a public-safe one-line suggestion for *state*."""
    if state == "clean":
        return "Worktree is clean. Ready for work."
    if state == "dirty_untracked":
        return "Untracked files present. Review or `git add` before refresh."
    if state == "dirty_uncommitted":
        return "Uncommitted changes. Commit or stash before refresh."
    if state == "merge_conflict":
        return "Merge in progress with conflicts. Resolve manually; refuse to auto-resolve."
    if state == "rebase_conflict":
        return "Rebase in progress. Resolve manually; refuse to auto-resolve."
    if state == "missing":
        return f"{'Base' if kind == 'base' else 'Issue'} worktree missing. Run prepare_base / create_issue."
    return "State unknown. Re-run inspect to refresh."


__all__ = [
    "DiscoveredWorktree",
    "discover_worktrees",
    "discovered_to_dict",
    "suggest_next_action",
]
