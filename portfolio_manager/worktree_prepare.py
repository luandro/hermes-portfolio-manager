"""Clone + safe ff-only refresh for the base repo — MVP 5 Phase 7.

Every command goes through ``worktree_git.run_git`` which enforces the
allowlist + redaction. Refusal cases never auto-resolve: dirty/conflict/
diverged states return an :class:`OutcomeBlocked` rather than rewriting
local state.
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
    local_branch_diverges_from_origin,
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
class PrepareBaseOutcome:
    """Result of clone + refresh attempts."""

    cloned: bool = False
    refreshed: bool = False
    blocked_reasons: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    final_state: str = "unknown"

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_reasons) and not self.failures

    @property
    def is_failed(self) -> bool:
        return bool(self.failures)


def clone_base_repo(
    *,
    remote_url: str,
    target_path: Path,
    root: Path,
) -> PrepareBaseOutcome:
    """Clone *remote_url* into *target_path*. Refuses if path exists non-empty
    or escapes the worktrees root, and verifies the post-clone remote matches.
    """
    outcome = PrepareBaseOutcome()
    try:
        target_resolved = assert_under_worktrees_root(target_path, root)
    except ValueError as exc:
        outcome.blocked_reasons.append(f"clone target escapes root: {exc}")
        return outcome
    if target_resolved.exists():
        if not target_resolved.is_dir():
            outcome.blocked_reasons.append(f"clone target exists and is not a directory: {target_resolved}")
            return outcome
        if any(target_resolved.iterdir()):
            outcome.blocked_reasons.append(f"clone target exists and is non-empty: {target_resolved}")
            return outcome

    target_resolved.parent.mkdir(parents=True, exist_ok=True)
    if not remote_url or remote_url.startswith("-"):
        outcome.failures.append(f"invalid remote_url: {remote_url!r}")
        return outcome
    res = run_git(
        ["clone", "--", remote_url, str(target_resolved)],
        cwd=target_resolved.parent,
        timeout=DEFAULT_TIMEOUTS["clone"],
    )
    if res.returncode != 0:
        outcome.failures.append(f"git clone exited {res.returncode}: {res.stderr.strip() or 'no stderr'}")
        # Best-effort cleanup of an empty directory only
        if target_resolved.exists() and not any(target_resolved.iterdir()):
            target_resolved.rmdir()
        return outcome

    actual_remote = get_origin_url(target_resolved)
    if actual_remote and not remotes_equal(actual_remote, remote_url):
        outcome.blocked_reasons.append(
            f"post-clone remote {normalize_remote_url(actual_remote)!r} does not match "
            f"{normalize_remote_url(remote_url)!r}"
        )
        return outcome

    outcome.cloned = True
    outcome.final_state = "ready"
    return outcome


def refresh_base_branch(
    *,
    base_path: Path,
    base_branch: str,
    remote_url: str,
) -> PrepareBaseOutcome:
    """Safely ff-only refresh *base_branch* in *base_path*.

    Sequence: clean check → state guard (merge/rebase) → remote match →
    branch existence → switch → fetch → ff-only merge. Divergence blocks.
    """
    outcome = PrepareBaseOutcome()
    if not is_git_repo(base_path):
        outcome.blocked_reasons.append(f"refresh target is not a git repo: {base_path}")
        return outcome

    state = get_clean_state(base_path)
    if state in ("merge_conflict", "rebase_conflict"):
        outcome.blocked_reasons.append(f"base repo in {state}; refresh blocked")
        outcome.final_state = state
        return outcome
    if state == "dirty_uncommitted":
        outcome.blocked_reasons.append("base repo has uncommitted changes; refresh blocked")
        outcome.final_state = state
        return outcome
    if state == "dirty_untracked":
        outcome.blocked_reasons.append("base repo has untracked files; refresh blocked")
        outcome.final_state = state
        return outcome
    if state == "probe_failed":
        outcome.blocked_reasons.append("base repo state could not be probed; refresh blocked")
        outcome.final_state = state
        return outcome

    actual_remote = get_origin_url(base_path)
    if actual_remote and not remotes_equal(actual_remote, remote_url):
        outcome.blocked_reasons.append(f"base remote {normalize_remote_url(actual_remote)!r} does not match config")
        return outcome

    if not branch_exists(base_path, base_branch, remote=False):
        outcome.blocked_reasons.append(
            f"local branch {base_branch!r} does not exist in base repo (no implicit creation)"
        )
        return outcome

    sw = run_git(["switch", base_branch], cwd=base_path, timeout=DEFAULT_TIMEOUTS["switch"])
    if sw.returncode != 0:
        outcome.failures.append(f"git switch failed: {sw.stderr.strip() or 'no stderr'}")
        return outcome

    fetch = run_git(
        ["fetch", "origin", base_branch, "--prune"],
        cwd=base_path,
        timeout=DEFAULT_TIMEOUTS["fetch"],
    )
    if fetch.returncode != 0:
        outcome.failures.append(f"git fetch failed: {fetch.stderr.strip() or 'no stderr'}")
        return outcome

    if local_branch_diverges_from_origin(base_path, base_branch):
        outcome.blocked_reasons.append(
            f"local {base_branch!r} has commits not in origin/{base_branch}; refresh blocked"
        )
        outcome.final_state = "diverged"
        return outcome

    merge = run_git(
        ["merge", "--ff-only", f"origin/{base_branch}"],
        cwd=base_path,
        timeout=DEFAULT_TIMEOUTS["merge"],
    )
    if merge.returncode != 0:
        outcome.failures.append(f"git merge --ff-only failed: {merge.stderr.strip() or 'no stderr'}")
        return outcome

    outcome.refreshed = True
    outcome.final_state = "clean"
    return outcome


__all__ = ["PrepareBaseOutcome", "clone_base_repo", "refresh_base_branch"]
