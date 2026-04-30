"""Pure planner shared by plan / prepare / create tools — MVP 5 Phase 6.

Builds a fully-typed :class:`WorktreePlan` describing what *would* happen.
Never mutates SQLite, never writes artifacts, never runs allowlisted git
commands beyond read-only probes against an *already-cloned* base repo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from portfolio_manager.issue_resolver import resolve_project
from portfolio_manager.worktree_git import (
    branch_exists,
    get_clean_state,
    get_origin_url,
    is_git_repo,
)
from portfolio_manager.worktree_paths import (
    default_branch_name,
    normalize_remote_url,
    remotes_equal,
    render_issue_worktree_path,
    validate_branch_name,
)

if TYPE_CHECKING:
    from pathlib import Path

    from portfolio_manager.config import PortfolioConfig, ProjectConfig


@dataclass
class WorktreePlan:
    """Description of what a worktree-prep tool would do, with no side effects."""

    project_id: str
    issue_number: int
    base_path: Path
    issue_worktree_path: Path
    base_branch: str
    branch_name: str
    remote_url: str  # canonical normalized form (for comparison + display)
    remote_url_raw: str  # original from project config (for actual clone/fetch)
    would_clone_base: bool
    would_refresh_base: bool
    would_create_worktree: bool
    warnings: list[str] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    skipped_reason: str | None = None  # set when an exact clean match exists

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_reasons)

    @property
    def is_skipped(self) -> bool:
        return self.skipped_reason is not None


def _resolve_project_config(config: PortfolioConfig, project_ref: str) -> ProjectConfig | None:
    """Use the existing fuzzy resolver, then map back to ProjectConfig."""
    res = resolve_project(config, project_ref=project_ref)
    if res.state != "resolved" or res.project_id is None:
        return None
    for p in config.projects:
        if p.id == res.project_id:
            return p
    return None


def _resolve_base_branch(project: ProjectConfig, base_branch: str | None) -> tuple[str | None, str | None]:
    """Return (resolved_branch, error). 'auto' is unresolvable here without a remote."""
    if base_branch is not None:
        return base_branch, None
    if project.default_branch and project.default_branch != "auto":
        return project.default_branch, None
    return None, "default_branch is 'auto' but no explicit base_branch was supplied"


def build_plan(
    config: PortfolioConfig,
    *,
    project_ref: str,
    issue_number: int | None = None,
    base_branch: str | None = None,
    branch_name: str | None = None,
    refresh_base: bool = True,
    root: Path,
) -> WorktreePlan:
    """Construct a :class:`WorktreePlan` from inputs + the current filesystem state.

    Pure with respect to mutations: only read-only probes (``rev-parse``,
    ``status``, ``remote get-url``, ``for-each-ref``) are issued, and only
    against an *already-existing* base clone.
    """
    # ---- Resolve project ----
    project = _resolve_project_config(config, project_ref)
    if project is None:
        return WorktreePlan(
            project_id="",
            issue_number=issue_number or 0,
            base_path=root / "worktrees",
            issue_worktree_path=root / "worktrees",
            base_branch="",
            branch_name="",
            remote_url="",
            remote_url_raw="",
            would_clone_base=False,
            would_refresh_base=False,
            would_create_worktree=False,
            blocked_reasons=[f"project not resolved: {project_ref!r}"],
        )

    # ---- Validate issue ----
    blocked: list[str] = []
    warnings: list[str] = []
    if issue_number is not None and (not isinstance(issue_number, int) or issue_number <= 0):
        blocked.append(f"issue_number must be positive int, got {issue_number!r}")

    # ---- Resolve branches ----
    resolved_base, base_err = _resolve_base_branch(project, base_branch)
    if base_err:
        blocked.append(base_err)
    final_base_branch = resolved_base or ""

    effective_issue = max(issue_number, 1) if issue_number is not None else 1
    try:
        final_branch_name = (
            validate_branch_name(branch_name) if branch_name else default_branch_name(project.id, effective_issue)
        )
    except ValueError as exc:
        blocked.append(f"invalid branch name: {exc}")
        final_branch_name = ""

    # ---- Resolve paths ----
    base_path = project.local.base_path
    if issue_number is not None:
        try:
            issue_path = render_issue_worktree_path(
                project.local.issue_worktree_pattern, project.id, effective_issue, root
            )
        except (TypeError, ValueError) as exc:
            blocked.append(f"invalid issue worktree path: {exc}")
            issue_path = base_path  # placeholder; not used when blocked
    else:
        issue_path = base_path  # no issue worktree for base-only plans

    remote_url = project.repo
    norm_remote = normalize_remote_url(remote_url) if remote_url else ""

    if blocked:
        return WorktreePlan(
            project_id=project.id,
            issue_number=issue_number or 0,
            base_path=base_path,
            issue_worktree_path=issue_path,
            base_branch=final_base_branch,
            branch_name=final_branch_name,
            remote_url=norm_remote,
            remote_url_raw=remote_url,
            would_clone_base=False,
            would_refresh_base=False,
            would_create_worktree=False,
            warnings=warnings,
            blocked_reasons=blocked,
        )

    # ---- Inspect base clone if it already exists ----
    base_exists = base_path.exists()
    would_clone = not base_exists
    would_refresh = bool(refresh_base) and base_exists

    if base_exists:
        if not is_git_repo(base_path):
            blocked.append(f"base path exists but is not a git repo: {base_path}")
        else:
            origin = get_origin_url(base_path)
            if origin and not remotes_equal(origin, remote_url):
                blocked.append(
                    f"base remote {normalize_remote_url(origin)!r} does not match config "
                    f"{normalize_remote_url(remote_url)!r}"
                )
            state = get_clean_state(base_path)
            if state in ("merge_conflict", "rebase_conflict"):
                blocked.append(f"base repo in {state}; refresh blocked")
            elif state in ("dirty_uncommitted", "dirty_untracked"):
                blocked.append(f"base repo has {state}; refresh blocked")
            elif state == "probe_failed":
                blocked.append("base repo state could not be probed; refresh blocked")

    # ---- Inspect existing issue worktree (idempotency / conflict detection) ----
    skipped_reason: str | None = None
    would_create = True
    if issue_number is not None and issue_path.exists():
        if not is_git_repo(issue_path):
            blocked.append(f"issue path exists but is not a git repo: {issue_path}")
            would_create = False
        else:
            wt_origin = get_origin_url(issue_path)
            if wt_origin and not remotes_equal(wt_origin, remote_url):
                blocked.append(f"existing issue worktree has wrong remote {normalize_remote_url(wt_origin)!r}")
                would_create = False
            else:
                wt_state = get_clean_state(issue_path)
                if wt_state in (
                    "merge_conflict",
                    "rebase_conflict",
                    "dirty_uncommitted",
                    "dirty_untracked",
                    "probe_failed",
                ):
                    blocked.append(f"existing issue worktree is {wt_state}")
                    would_create = False
                else:
                    # Branch must match too
                    if final_branch_name and not branch_exists(issue_path, final_branch_name, remote=False):
                        blocked.append(f"existing issue worktree does not have branch {final_branch_name!r}")
                        would_create = False
                    else:
                        # Verify HEAD is actually on the expected branch
                        from portfolio_manager.worktree_git import DEFAULT_TIMEOUTS as _DT
                        from portfolio_manager.worktree_git import run_git as _run_git

                        head = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=issue_path, timeout=_DT["rev-parse"])
                        current = head.stdout.strip() if head.returncode == 0 else ""
                        if final_branch_name and current != final_branch_name:
                            blocked.append(
                                f"existing issue worktree is on branch {current!r}, expected {final_branch_name!r}"
                            )
                            would_create = False
                        else:
                            skipped_reason = "exact matching clean worktree already exists"
                            would_create = False

    # ---- If branch already exists in base repo without matching worktree → block ----
    if (
        not blocked
        and not skipped_reason
        and issue_number is not None
        and base_exists
        and is_git_repo(base_path)
        and final_branch_name
        and branch_exists(base_path, final_branch_name, remote=False)
    ):
        blocked.append(f"branch {final_branch_name!r} already exists in base repo without a matching worktree")
        would_create = False

    # ---- Build commands list (descriptive, not executed by planner) ----
    commands: list[list[str]] = []
    if would_clone:
        commands.append(["git", "clone", remote_url, str(base_path)])
    if would_refresh and not blocked:
        commands.append(["git", "switch", final_base_branch])
        commands.append(["git", "fetch", "origin", final_base_branch, "--prune"])
        commands.append(["git", "merge", "--ff-only", f"origin/{final_base_branch}"])
    if would_create and not blocked:
        commands.append(
            [
                "git",
                "worktree",
                "add",
                str(issue_path),
                "-b",
                final_branch_name,
                f"origin/{final_base_branch}",
            ]
        )

    # ---- Warning: issue not found in local SQLite ----
    # (Caller may pass a conn for this; planner stays read-only-pure here.)

    return WorktreePlan(
        project_id=project.id,
        issue_number=issue_number or 0,
        base_path=base_path,
        issue_worktree_path=issue_path,
        base_branch=final_base_branch,
        branch_name=final_branch_name,
        remote_url=norm_remote,
        remote_url_raw=remote_url,
        would_clone_base=would_clone,
        would_refresh_base=would_refresh and not blocked,
        would_create_worktree=would_create and not blocked,
        warnings=warnings,
        commands=commands,
        blocked_reasons=blocked,
        skipped_reason=skipped_reason,
    )


def plan_to_dict(plan: WorktreePlan) -> dict[str, object]:
    """Convert a WorktreePlan into a JSON-friendly dict for the result envelope."""
    return {
        "project_id": plan.project_id,
        "issue_number": plan.issue_number,
        "base_path": str(plan.base_path),
        "issue_worktree_path": str(plan.issue_worktree_path),
        "base_branch": plan.base_branch,
        "branch_name": plan.branch_name,
        "remote_url": plan.remote_url,
        "would_clone_base": plan.would_clone_base,
        "would_refresh_base": plan.would_refresh_base,
        "would_create_worktree": plan.would_create_worktree,
        "warnings": list(plan.warnings),
        "commands": [list(c) for c in plan.commands],
        "blocked_reasons": list(plan.blocked_reasons),
        "skipped_reason": plan.skipped_reason,
    }


__all__ = ["WorktreePlan", "build_plan", "plan_to_dict"]
