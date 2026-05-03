"""Worktree discovery / reconciliation — MVP 5 Phase 9.

Walks ``$ROOT/worktrees`` and classifies each entry into base / issue /
unknown without mutating anything. Used by the list, inspect, and
explain handlers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from portfolio_manager.worktree_git import (
    get_clean_state,
    get_origin_url,
    is_git_repo,
)
from portfolio_manager.worktree_paths import normalize_remote_url, remotes_equal

if TYPE_CHECKING:
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


def _row_state(row: dict[str, object]) -> str:
    return str(row.get("state") or "unknown")


def worktree_reconcile(
    conn: object,
    project_id: str,
    issue_number: int | None,
    root: Path,
) -> dict[str, object]:
    """Compare SQLite row, filesystem and git probes; return verdict + diffs.

    Never mutates the repo and never auto-resolves drift. Callers may decide
    to update SQLite to filesystem truth based on the returned ``safe_to_sync``
    flag.
    """
    from portfolio_manager.worktree_state import (
        base_worktree_id,
        get_worktree,
        issue_worktree_id,
    )

    worktree_id = (
        issue_worktree_id(project_id, issue_number) if issue_number is not None else base_worktree_id(project_id)
    )
    row = get_worktree(conn, worktree_id) or {}  # type: ignore[arg-type]
    fs_path = Path(str(row.get("path") or "")) if row.get("path") else None

    # Path-derived expected location (not resolved against config here)
    fs_exists = bool(fs_path and fs_path.exists())
    diffs: list[str] = []
    if row and not fs_exists:
        diffs.append("sqlite has row but filesystem path missing")
    if fs_exists and fs_path and not is_git_repo(fs_path):
        diffs.append("filesystem path is not a git repo")
    branch = None
    state = "unknown"
    remote_url: str | None = None
    if fs_exists and fs_path is not None and is_git_repo(fs_path):
        from portfolio_manager.worktree_git import DEFAULT_TIMEOUTS, run_git

        b = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=fs_path, timeout=DEFAULT_TIMEOUTS["rev-parse"])
        branch = b.stdout.strip() if b.returncode == 0 else None
        state = get_clean_state(fs_path)
        origin = get_origin_url(fs_path)
        remote_url = normalize_remote_url(origin) if origin else None
        sql_branch = row.get("branch_name")
        sql_remote = row.get("remote_url")
        if branch and sql_branch and branch != sql_branch:
            diffs.append(f"branch drift: sqlite={sql_branch!r} fs={branch!r}")
        if remote_url and sql_remote and remote_url != sql_remote:
            diffs.append(f"remote drift: sqlite={sql_remote!r} fs={remote_url!r}")

    safe_to_sync = not diffs and (fs_exists or not row)
    return {
        "worktree_id": worktree_id,
        "sqlite_row": row,
        "fs_exists": fs_exists,
        "branch": branch,
        "state": state,
        "remote_url": remote_url,
        "diffs": diffs,
        "safe_to_sync": safe_to_sync,
    }


__all__ = [
    "DiscoveredWorktree",
    "discover_worktrees",
    "discovered_to_dict",
    "suggest_next_action",
    "worktree_reconcile",
]
