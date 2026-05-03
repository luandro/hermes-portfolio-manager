"""Pre-flight checks for MVP 6 implementation runner.

Validates that a worktree is in a safe state before starting an implementation
or review-fix job. All checks are read-only — no artifacts written, no SQLite
mutations."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

from portfolio_manager.implementation_paths import resolve_source_artifact
from portfolio_manager.worktree_git import DEFAULT_TIMEOUTS, get_clean_state, run_git
from portfolio_manager.worktree_state import get_worktree, issue_worktree_id


@dataclass
class PreflightResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    worktree_path: Path | None = None
    branch_name: str | None = None
    head_sha: str | None = None
    source_artifact_path: Path | None = None


def _get_head_sha(path: Path) -> str | None:
    """Return the current HEAD commit SHA, or None on failure."""
    r = run_git(["rev-parse", "HEAD"], cwd=path, timeout=DEFAULT_TIMEOUTS["rev-parse"])
    if r.returncode == 0:
        return r.stdout.strip() or None
    return None


def _get_branch_name(path: Path) -> str | None:
    """Return the current branch name, or None."""
    r = run_git(["branch", "--show-current"], cwd=path, timeout=DEFAULT_TIMEOUTS["branch"])
    if r.returncode == 0:
        name = r.stdout.strip()
        return name if name else None
    return None


def preflight_initial_implementation(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    issue_number: int,
    expected_branch: str | None = None,
    root: Path,
) -> PreflightResult:
    """Run pre-flight checks for an initial implementation job.

    Checks:
      1. Worktree row exists in SQLite.
      2. Worktree path exists on disk.
      3. Worktree is clean (no uncommitted changes, untracked files, or conflicts).
      4. Current branch matches *expected_branch* (if provided).
      5. Source artifact (spec) exists.

    Returns a ``PreflightResult`` with ``ok=True`` when all checks pass.
    """
    reasons: list[str] = []

    # 1. Worktree row in SQLite
    wt_id = issue_worktree_id(project_id, issue_number)
    row = get_worktree(conn, wt_id)
    if row is None:
        reasons.append(f"Worktree row {wt_id!r} not found in SQLite")
        return PreflightResult(ok=False, reasons=reasons)

    wt_path_str = row.get("path")
    if not wt_path_str:
        reasons.append(f"Worktree row {wt_id!r} has no path")
        return PreflightResult(ok=False, reasons=reasons)

    wt_path = Path(wt_path_str)

    # 2. Worktree path exists on disk
    if not wt_path.is_dir():
        reasons.append(f"Worktree path {wt_path} does not exist on disk")
        return PreflightResult(ok=False, reasons=reasons, worktree_path=wt_path)

    # 3. Worktree is clean
    clean_state = get_clean_state(wt_path)
    if clean_state != "clean":
        reasons.append(f"Worktree is not clean (state={clean_state!r})")

    # 4. Branch matches expected
    branch = _get_branch_name(wt_path)
    if expected_branch is not None and branch != expected_branch:
        reasons.append(f"Branch mismatch: expected {expected_branch!r}, got {branch!r}")

    # 5. Source artifact exists
    try:
        source = resolve_source_artifact(root, conn, project_id, issue_number)
    except ValueError:
        source = None
    if source is None:
        reasons.append("Source artifact (spec) not found")

    head_sha = _get_head_sha(wt_path)

    ok = len(reasons) == 0
    return PreflightResult(
        ok=ok,
        reasons=reasons,
        worktree_path=wt_path,
        branch_name=branch,
        head_sha=head_sha,
        source_artifact_path=source,
    )


def preflight_review_fix(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    issue_number: int,
    pr_number: int,
    expected_branch: str | None = None,
    approved_comment_ids: list[str],
    fix_scope: list[str],
    root: Path,
) -> PreflightResult:
    """Run pre-flight checks for a review-fix job.

    Same checks as :func:`preflight_initial_implementation` plus:
      6. *approved_comment_ids* is non-empty.
      7. *fix_scope* is non-empty.
    """
    # 6. Approved comment IDs
    reasons: list[str] = []
    if not approved_comment_ids:
        reasons.append("approved_comment_ids is empty")

    # 7. Fix scope
    if not fix_scope:
        reasons.append("fix_scope is empty")

    # Run the same checks as initial implementation
    base = preflight_initial_implementation(
        conn,
        project_id=project_id,
        issue_number=issue_number,
        expected_branch=expected_branch,
        root=root,
    )

    all_reasons = reasons + base.reasons
    ok = len(all_reasons) == 0
    return PreflightResult(
        ok=ok,
        reasons=all_reasons,
        worktree_path=base.worktree_path,
        branch_name=base.branch_name,
        head_sha=base.head_sha,
        source_artifact_path=base.source_artifact_path,
    )
