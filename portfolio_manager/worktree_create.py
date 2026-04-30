"""Issue worktree creation logic — MVP 5 Phase 8.

Idempotent: an exact-match clean worktree is left untouched. Anything
ambiguous returns blocked instead of overwriting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from portfolio_manager.worktree_git import (
    DEFAULT_TIMEOUTS,
    branch_exists,
    get_clean_state,
    get_origin_url,
    is_git_repo,
    run_git,
)
from portfolio_manager.worktree_paths import (
    assert_under_worktrees_root,
    normalize_remote_url,
    remotes_equal,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class CreateIssueOutcome:
    """Result of an issue worktree creation attempt."""

    created: bool = False
    skipped: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    final_state: str = "unknown"

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_reasons) and not self.failures

    @property
    def is_failed(self) -> bool:
        return bool(self.failures)


def create_issue_worktree(
    *,
    base_path: Path,
    issue_path: Path,
    branch_name: str,
    base_branch: str,
    remote_url: str,
    root: Path,
) -> CreateIssueOutcome:
    """Create an issue worktree at *issue_path* tracking *branch_name*.

    Pre-conditions verified up front:
      * base_path is a git repo with matching remote and clean working tree
      * issue_path is under $ROOT/worktrees and either missing or already an
        exact-match clean worktree on the requested branch
      * the requested branch does not already exist in base_path

    On success: ``git worktree add <issue_path> -b <branch_name>
    origin/<base_branch>``.
    """
    outcome = CreateIssueOutcome()
    try:
        issue_resolved = assert_under_worktrees_root(issue_path, root)
    except ValueError as exc:
        outcome.blocked_reasons.append(f"issue path escapes worktrees root: {exc}")
        return outcome

    if not is_git_repo(base_path):
        outcome.blocked_reasons.append(f"base path is not a git repo: {base_path}")
        return outcome

    actual_remote = get_origin_url(base_path)
    if actual_remote and not remotes_equal(actual_remote, remote_url):
        outcome.blocked_reasons.append(f"base remote {normalize_remote_url(actual_remote)!r} does not match config")
        return outcome

    base_state = get_clean_state(base_path)
    if base_state in ("merge_conflict", "rebase_conflict", "dirty_uncommitted"):
        outcome.blocked_reasons.append(f"base repo is {base_state}; create blocked")
        return outcome

    # Idempotency: an exact-match worktree means nothing to do.
    if issue_resolved.exists():
        if not is_git_repo(issue_resolved):
            outcome.blocked_reasons.append(f"issue path exists but is not a git repo: {issue_resolved}")
            return outcome
        wt_remote = get_origin_url(issue_resolved)
        if wt_remote and not remotes_equal(wt_remote, remote_url):
            outcome.blocked_reasons.append(
                f"existing issue worktree has wrong remote {normalize_remote_url(wt_remote)!r}"
            )
            return outcome
        wt_state = get_clean_state(issue_resolved)
        if wt_state in (
            "merge_conflict",
            "rebase_conflict",
            "dirty_uncommitted",
            "dirty_untracked",
        ):
            outcome.blocked_reasons.append(f"existing issue worktree is {wt_state}; refuse to overwrite")
            return outcome
        if not branch_exists(issue_resolved, branch_name, remote=False):
            outcome.blocked_reasons.append(f"existing issue worktree does not have branch {branch_name!r}")
            return outcome
        # Verify HEAD is actually on the expected branch
        head = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=issue_resolved, timeout=DEFAULT_TIMEOUTS["rev-parse"])
        current = head.stdout.strip() if head.returncode == 0 else ""
        if current != branch_name:
            outcome.blocked_reasons.append(
                f"existing issue worktree is on branch {current!r}, expected {branch_name!r}"
            )
            return outcome
        outcome.skipped = True
        outcome.final_state = "clean"
        return outcome

    # If the branch exists in the base repo without a corresponding worktree
    # for our path, refuse to clobber it.
    if branch_exists(base_path, branch_name, remote=False):
        outcome.blocked_reasons.append(f"branch {branch_name!r} already exists in base repo with no matching worktree")
        return outcome

    if not branch_exists(base_path, base_branch, remote=True):
        outcome.blocked_reasons.append(f"origin/{base_branch} not found in base repo (run prepare-base first)")
        return outcome

    issue_resolved.parent.mkdir(parents=True, exist_ok=True)
    res = run_git(
        ["worktree", "add", str(issue_resolved), "-b", branch_name, f"origin/{base_branch}"],
        cwd=base_path,
        timeout=DEFAULT_TIMEOUTS["worktree"],
    )
    if res.returncode != 0:
        outcome.failures.append(f"git worktree add exited {res.returncode}: {res.stderr.strip() or 'no stderr'}")
        return outcome

    outcome.created = True
    outcome.final_state = "clean"
    return outcome


__all__ = ["CreateIssueOutcome", "create_issue_worktree"]
