"""Telegram-friendly summary generation for the Portfolio Manager plugin.

Functions produce concise, action-oriented text suitable for direct
delivery through Telegram.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from portfolio_manager.config import PRIORITY_ORDER

if TYPE_CHECKING:
    from portfolio_manager.config import ProjectConfig
    from portfolio_manager.worktree import WorktreeInspection

# ---------------------------------------------------------------------------
# Priority helpers
# ---------------------------------------------------------------------------

_PRIORITY_LABELS: dict[str, str] = {
    "critical": "Critical",
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "paused": "Paused",
}

# States that need user attention
_NEEDS_USER_WORKTREE_STATES = {
    "dirty_uncommitted",
    "dirty_untracked",
    "merge_conflict",
    "rebase_conflict",
    "missing",
}

_NEEDS_USER_ISSUE_STATES = {"needs_triage", "needs_user_questions"}

_NEEDS_USER_PR_STATES = {"ready_for_human", "qa_required"}

# Ordering for worktree severity in summaries
_WT_SEVERITY: dict[str, int] = {
    "merge_conflict": 0,
    "rebase_conflict": 1,
    "dirty_uncommitted": 2,
    "dirty_untracked": 3,
    "missing": 4,
    "blocked": 5,
    "clean": 6,
    "unknown": 7,
}


# ---------------------------------------------------------------------------
# 4.1 summarize_project_list
# ---------------------------------------------------------------------------


def summarize_project_list(projects: list[ProjectConfig], counts: dict[str, int]) -> str:
    """Summarize configured projects grouped by priority.

    Excludes archived projects. Groups by priority label in order:
    critical > high > medium > low > paused.
    """
    active_projects = [p for p in projects if p.status != "archived"]
    sorted_projects = sorted(active_projects, key=lambda p: PRIORITY_ORDER.get(p.priority, 99))

    total = counts.get("active", 0)
    lines: list[str] = [f"I am managing {total} project{'s' if total != 1 else ''}."]

    # Group by priority
    groups: dict[str, list[ProjectConfig]] = {}
    for p in sorted_projects:
        groups.setdefault(p.priority, []).append(p)

    for priority in ("critical", "high", "medium", "low", "paused"):
        group = groups.get(priority)
        if not group:
            continue
        label = _PRIORITY_LABELS.get(priority, priority.capitalize())
        lines.append("")
        lines.append(f"{label} priority:")
        for p in group:
            lines.append(f"- {p.name}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4.2 summarize_github_sync
# ---------------------------------------------------------------------------


def summarize_github_sync(sync_results: list[dict[str, Any]]) -> str:
    """Summarize GitHub sync across projects.

    Shows aggregate counts (projects synced, total issues, total PRs)
    and any warnings. Does not list individual issues.
    """
    if not sync_results:
        return "No projects synced."

    total_issues = sum(r.get("issues_count", 0) for r in sync_results)
    total_prs = sum(r.get("prs_count", 0) for r in sync_results)
    projects_synced = len(sync_results)

    all_warnings: list[str] = []
    for r in sync_results:
        all_warnings.extend(r.get("warnings", []))

    lines: list[str] = [
        "GitHub sync complete.",
        "",
        f"{projects_synced} project{'s' if projects_synced != 1 else ''} synced.",
        f"{total_issues} open issue{'s' if total_issues != 1 else ''} seen.",
        f"{total_prs} open PR{'s' if total_prs != 1 else ''} seen.",
    ]

    if all_warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in all_warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4.3 summarize_worktrees
# ---------------------------------------------------------------------------


def summarize_worktrees(worktree_results: list[WorktreeInspection]) -> str:
    """Summarize worktree inspection results.

    Dirty/conflicted/missing worktrees are listed first with affected files.
    Clean worktrees are summarized concisely.
    """
    if not worktree_results:
        return "No worktrees inspected."

    # Sort by severity (worst first)
    sorted_wts = sorted(worktree_results, key=lambda w: _WT_SEVERITY.get(w.state, 99))

    problem_wts = [w for w in sorted_wts if w.state in _NEEDS_USER_WORKTREE_STATES or w.state == "blocked"]
    clean_wts = [w for w in sorted_wts if w.state == "clean"]

    lines: list[str] = ["Worktree inspection complete.", ""]

    if problem_wts:
        n = len(problem_wts)
        lines.append(f"{n} worktree{'s' if n != 1 else ''} {'need' if n != 1 else 'needs'} attention:")
        for w in problem_wts:
            detail = ""
            if w.dirty_summary:
                detail = f": {w.dirty_summary}"
            state_label = w.state.replace("_", " ")
            lines.append(f"- {w.path} [{state_label}]{detail}")
        lines.append("")

    if clean_wts:
        lines.append(f"{len(clean_wts)} clean worktree{'s' if len(clean_wts) != 1 else ''}.")

    has_conflicts = any(w.state in ("merge_conflict", "rebase_conflict") for w in worktree_results)
    if not has_conflicts:
        lines.append("No merge or rebase conflicts found.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4.4 summarize_portfolio_status
# ---------------------------------------------------------------------------


def summarize_portfolio_status(state_snapshot: dict[str, Any], status_filter: str = "all") -> str:
    """Summarize portfolio status from a state snapshot.

    status_filter='all': show everything.
    status_filter='needs_user': only items needing human attention.
    """
    issues = state_snapshot.get("issues", [])
    pull_requests = state_snapshot.get("pull_requests", [])
    worktrees = state_snapshot.get("worktrees", [])

    lines: list[str] = []

    if status_filter == "needs_user":
        needs_lines: list[str] = []

        # Issues needing attention
        for issue in issues:
            if issue.get("state") in _NEEDS_USER_ISSUE_STATES:
                proj = issue.get("project_id", "unknown")
                num = issue.get("number", "?")
                title = issue.get("title", "")
                needs_lines.append(f"- {proj} issue #{num}: {title} (needs triage)")

        # PRs needing attention
        for pr in pull_requests:
            if pr.get("state") in _NEEDS_USER_PR_STATES:
                proj = pr.get("project_id", "unknown")
                num = pr.get("number", "?")
                title = pr.get("title", "")
                needs_lines.append(f"- {proj} PR #{num}: {title} (ready for review)")

        # Worktrees needing attention
        for wt in worktrees:
            wt_state = wt.get("state", "")
            if wt_state in _NEEDS_USER_WORKTREE_STATES:
                path = wt.get("path", "unknown")
                detail = ""
                if wt.get("dirty_summary"):
                    detail = f": {wt['dirty_summary']}"
                state_label = wt_state.replace("_", " ")
                needs_lines.append(f"- {path} [{state_label}]{detail}")

        if needs_lines:
            lines.append("Needs you:")
            for i, item in enumerate(needs_lines[:10], 1):
                lines.append(f"{i}. {item}")
            if len(needs_lines) > 10:
                lines.append(f"...and {len(needs_lines) - 10} more.")
        else:
            lines.append("Nothing needs your attention right now.")

        return "\n".join(lines)

    # status_filter == 'all'
    lines.append("Portfolio status:")
    lines.append("")

    if issues:
        lines.append(f"{len(issues)} issue{'s' if len(issues) != 1 else ''}:")
        for issue in issues[:10]:
            proj = issue.get("project_id", "unknown")
            num = issue.get("number", "?")
            title = issue.get("title", "")
            state = issue.get("state", "")
            lines.append(f"- {proj} #{num}: {title} ({state})")
        if len(issues) > 10:
            lines.append(f"...and {len(issues) - 10} more.")
        lines.append("")

    if pull_requests:
        lines.append(f"{len(pull_requests)} PR{'s' if len(pull_requests) != 1 else ''}:")
        for pr in pull_requests[:10]:
            proj = pr.get("project_id", "unknown")
            num = pr.get("number", "?")
            title = pr.get("title", "")
            state = pr.get("state", "")
            lines.append(f"- {proj} PR #{num}: {title} ({state})")
        if len(pull_requests) > 10:
            lines.append(f"...and {len(pull_requests) - 10} more.")
        lines.append("")

    if worktrees:
        dirty_count = sum(1 for w in worktrees if w.get("state") in _NEEDS_USER_WORKTREE_STATES)
        clean_count = sum(1 for w in worktrees if w.get("state") == "clean")
        lines.append(
            f"{dirty_count} worktree{'s' if dirty_count != 1 else ''} "
            f"{'need' if dirty_count != 1 else 'needs'} attention, {clean_count} clean."
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4.5 summarize_heartbeat
# ---------------------------------------------------------------------------


def summarize_heartbeat(result: dict[str, Any]) -> str:
    """Summarize a heartbeat run as a concise, action-oriented digest.

    Suitable for direct Telegram delivery.
    """
    projects_checked = result.get("projects_checked", 0)
    issues_seen = result.get("issues_seen", 0)
    prs_seen = result.get("prs_seen", 0)
    dirty_worktrees = result.get("dirty_worktrees", 0)
    warnings = result.get("warnings", [])

    lines: list[str] = ["Portfolio heartbeat complete.", ""]
    lines.append(f"{projects_checked} project{'s' if projects_checked != 1 else ''} checked.")
    lines.append(f"{issues_seen} open issue{'s' if issues_seen != 1 else ''} seen.")
    lines.append(f"{prs_seen} open PR{'s' if prs_seen != 1 else ''} seen.")

    if dirty_worktrees > 0:
        lines.append(f"{dirty_worktrees} dirty worktree{'s' if dirty_worktrees != 1 else ''} found.")

    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"- {w}")

    return "\n".join(lines)
