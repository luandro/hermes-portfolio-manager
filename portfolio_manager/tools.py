"""Tool handlers for the Portfolio Manager plugin.

Each handler imports from config, state, worktree, github_client, summary.
Each returns JSON with shared result shape:
    {"status", "tool", "message", "data", "summary", "reason"}
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.config import ConfigError, load_projects_config, resolve_root, select_projects
from portfolio_manager.errors import redact_secrets
from portfolio_manager.github_client import (
    ProjectGitHubSyncResult,
    check_gh_auth,
    check_gh_available,
    sync_project_github,
)
from portfolio_manager.state import (
    acquire_lock,
    add_event,
    finish_heartbeat,
    init_state,
    open_state,
    release_lock,
    start_heartbeat,
    upsert_issue,
    upsert_project,
    upsert_pull_request,
    upsert_worktree,
)
from portfolio_manager.summary import (
    summarize_github_sync,
    summarize_heartbeat,
    summarize_portfolio_status,
    summarize_project_list,
    summarize_worktrees,
)
from portfolio_manager.worktree import inspect_project_worktrees

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared result builder
# ---------------------------------------------------------------------------


def _result(
    *,
    status: str,
    tool: str,
    message: str,
    data: dict[str, Any] | None = None,
    summary: str = "",
    reason: str | None = None,
) -> str:
    res = json.dumps(
        {
            "status": status,
            "tool": tool,
            "message": message,
            "data": data if data is not None else {},
            "summary": summary,
            "reason": reason,
        },
        ensure_ascii=False,
    )
    return redact_secrets(res)


def _blocked(tool: str, message: str, reason: str | None = None, data: dict[str, Any] | None = None) -> str:
    return _result(status="blocked", tool=tool, message=message, data=data, summary=message, reason=reason)


def _ensure_dirs(root: Path) -> None:
    """Create state/, worktrees/, logs/, artifacts/ if missing."""
    for d in ("state", "worktrees", "logs", "artifacts"):
        (root / d).mkdir(parents=True, exist_ok=True)


def _persist_github_sync(conn: Any, project_id: str, sync: ProjectGitHubSyncResult) -> None:
    """Persist fetched issues and PRs into the state database."""
    for issue in sync.issues:
        upsert_issue(
            conn,
            project_id,
            {
                "number": issue.number,
                "title": issue.title,
                "state": "needs_triage",
                "labels_json": json.dumps(issue.labels),
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
            },
        )
    for pr in sync.prs:
        upsert_pull_request(
            conn,
            project_id,
            {
                "number": pr.number,
                "title": pr.title,
                "branch_name": pr.head_branch,
                "base_branch": pr.base_branch,
                "state": pr.review_stage,
                "review_stage": pr.review_stage,
                "created_at": pr.created_at,
                "updated_at": pr.updated_at,
            },
        )


# ---------------------------------------------------------------------------
# portfolio_ping
# ---------------------------------------------------------------------------


def _handle_portfolio_ping(args: dict[str, Any], **kwargs: Any) -> str:
    """Smoke test handler — confirms the plugin is loaded."""
    return _result(
        status="success",
        tool="portfolio_ping",
        message="Portfolio plugin is loaded",
        data={},
        summary="Portfolio plugin is loaded.",
    )


# ---------------------------------------------------------------------------
# portfolio_config_validate
# ---------------------------------------------------------------------------


def _handle_portfolio_config_validate(args: dict[str, Any], **kwargs: Any) -> str:
    """Validate server-side config without contacting GitHub."""
    tool = "portfolio_config_validate"
    root = resolve_root(args.get("root"))

    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), data={"valid": False, "errors": [str(exc)]})

    # Create required directories
    _ensure_dirs(root)

    # Count by status
    counts: dict[str, int] = {}
    for p in config.projects:
        counts[p.status] = counts.get(p.status, 0) + 1

    summary = summarize_project_list(
        config.projects,
        counts,
    )

    return _result(
        status="success",
        tool=tool,
        message=f"Config valid. {len(config.projects)} projects found.",
        data={
            "root": str(root),
            "config_path": str(root / "config" / "projects.yaml"),
            "valid": True,
            "project_count": len(config.projects),
            "warnings": [],
            "errors": [],
        },
        summary=summary,
    )


# ---------------------------------------------------------------------------
# portfolio_project_list
# ---------------------------------------------------------------------------


def _handle_portfolio_project_list(args: dict[str, Any], **kwargs: Any) -> str:
    """List configured projects from the server manifest."""
    tool = "portfolio_project_list"
    root = resolve_root(args.get("root"))

    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc))

    status_filter = args.get("status")
    include_archived = args.get("include_archived", False)

    projects = select_projects(config, status=status_filter, include_archived=include_archived)

    # Build counts
    all_counts: dict[str, int] = {}
    for p in config.projects:
        all_counts[p.status] = all_counts.get(p.status, 0) + 1

    project_dicts = [
        {
            "id": p.id,
            "name": p.name,
            "repo": p.repo,
            "github": {"owner": p.github.owner, "repo": p.github.repo},
            "priority": p.priority,
            "status": p.status,
        }
        for p in projects
    ]

    summary = summarize_project_list(projects, all_counts)

    return _result(
        status="success",
        tool=tool,
        message=f"Found {len(projects)} projects.",
        data={"projects": project_dicts, "counts": all_counts},
        summary=summary,
    )


# ---------------------------------------------------------------------------
# portfolio_github_sync
# ---------------------------------------------------------------------------


def _handle_portfolio_github_sync(args: dict[str, Any], **kwargs: Any) -> str:
    """Read open GitHub issues and PRs and update local state."""
    tool = "portfolio_github_sync"
    root = resolve_root(args.get("root"))

    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc))

    # Check gh availability
    gh_check = check_gh_available()
    if not gh_check.available:
        return _blocked(tool, gh_check.message)

    auth_check = check_gh_auth()
    if not auth_check.available:
        return _blocked(tool, auth_check.message)

    # Select projects
    project_id = args.get("project_id")
    include_paused = args.get("include_paused", False)
    max_items = args.get("max_items_per_project", 50)

    if project_id:
        projects = [p for p in config.projects if p.id == project_id]
        if not projects:
            return _blocked(tool, f"Project '{project_id}' not found in config.")
    else:
        projects = select_projects(config, include_paused=include_paused)

    # Open state
    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        sync_results: list[dict[str, Any]] = []
        total_issues = 0
        total_prs = 0
        all_warnings: list[str] = []

        for project in projects:
            upsert_project(conn, project)
            sync = sync_project_github(project, max_items=max_items)
            _persist_github_sync(conn, project.id, sync)
            sync_results.append(
                {
                    "id": sync.project_id,
                    "issues_count": sync.issues_count,
                    "prs_count": sync.prs_count,
                    "warnings": sync.warnings,
                }
            )
            total_issues += sync.issues_count
            total_prs += sync.prs_count
            all_warnings.extend(sync.warnings)

        summary = summarize_github_sync(sync_results)

        return _result(
            status="success",
            tool=tool,
            message=f"Synced {len(projects)} projects: {total_issues} issues, {total_prs} PRs.",
            data={
                "projects_synced": len(projects),
                "issues_seen": total_issues,
                "prs_seen": total_prs,
                "projects": sync_results,
            },
            summary=summary,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_worktree_inspect
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_inspect(args: dict[str, Any], **kwargs: Any) -> str:
    """Inspect local worktree folders for configured projects."""
    tool = "portfolio_worktree_inspect"
    root = resolve_root(args.get("root"))

    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc))

    project_id = args.get("project_id")
    include_paused = args.get("include_paused", False)
    if project_id:
        projects = [p for p in config.projects if p.id == project_id]
        if not projects:
            return _blocked(tool, f"Project '{project_id}' not found in config.")
    else:
        projects = select_projects(config, include_paused=include_paused)

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        all_inspections = []
        for project in projects:
            upsert_project(conn, project)
            inspections = inspect_project_worktrees(project)
            all_inspections.extend(inspections)

            # Upsert each worktree into state
            for insp in inspections:
                wt_id = f"{insp.project_id}"
                if insp.issue_number is not None:
                    wt_id += f"-issue-{insp.issue_number}"
                upsert_worktree(
                    conn,
                    {
                        "id": wt_id,
                        "project_id": insp.project_id,
                        "issue_number": insp.issue_number,
                        "path": insp.path,
                        "branch_name": insp.branch_name,
                        "state": insp.state,
                        "dirty_summary": insp.dirty_summary,
                    },
                )

        # Build counts
        state_counts: dict[str, int] = {}
        for insp in all_inspections:
            state_counts[insp.state] = state_counts.get(insp.state, 0) + 1

        summary = summarize_worktrees(all_inspections)

        return _result(
            status="success",
            tool=tool,
            message=f"Inspected {len(projects)} projects, {len(all_inspections)} worktrees.",
            data={
                "projects_inspected": len(projects),
                "worktrees": [
                    {
                        "project_id": w.project_id,
                        "issue_number": w.issue_number,
                        "path": w.path,
                        "state": w.state,
                        "branch_name": w.branch_name,
                        "dirty_summary": w.dirty_summary,
                    }
                    for w in all_inspections
                ],
                "counts": state_counts,
            },
            summary=summary,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_status
# ---------------------------------------------------------------------------


def _handle_portfolio_status(args: dict[str, Any], **kwargs: Any) -> str:
    """Return concise high-level status across all projects."""
    tool = "portfolio_status"
    root = resolve_root(args.get("root"))

    refresh = args.get("refresh", False)
    filter_val = args.get("filter", "all")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        if refresh:
            # Run github sync + worktree inspect for all active projects
            try:
                config = load_projects_config(root)
                projects = select_projects(config)

                gh_ok = check_gh_available().available and check_gh_auth().available

                for project in projects:
                    upsert_project(conn, project)
                    if gh_ok:
                        sync = sync_project_github(project)
                        _persist_github_sync(conn, project.id, sync)
                    # Upsert worktrees
                    inspections = inspect_project_worktrees(project)
                    for insp in inspections:
                        wt_id = f"{insp.project_id}"
                        if insp.issue_number is not None:
                            wt_id += f"-issue-{insp.issue_number}"
                        upsert_worktree(
                            conn,
                            {
                                "id": wt_id,
                                "project_id": insp.project_id,
                                "issue_number": insp.issue_number,
                                "path": insp.path,
                                "branch_name": insp.branch_name,
                                "state": insp.state,
                                "dirty_summary": insp.dirty_summary,
                            },
                        )
            except ConfigError as exc:
                logger.warning("Status refresh skipped: %s", exc)  # No config — still query whatever state exists

        # Query state for snapshot
        issues_rows = conn.execute("SELECT project_id, issue_number, title, state FROM issues").fetchall()
        pr_rows = conn.execute("SELECT project_id, pr_number, title, state, branch_name FROM pull_requests").fetchall()
        wt_rows = conn.execute(
            "SELECT project_id, issue_number, path, state, dirty_summary, branch_name FROM worktrees"
        ).fetchall()

        state_snapshot = {
            "issues": [{"project_id": r[0], "number": r[1], "title": r[2], "state": r[3]} for r in issues_rows],
            "pull_requests": [
                {"project_id": r[0], "number": r[1], "title": r[2], "state": r[3], "branch_name": r[4]} for r in pr_rows
            ],
            "worktrees": [
                {
                    "project_id": r[0],
                    "issue_number": r[1],
                    "path": r[2],
                    "state": r[3],
                    "dirty_summary": r[4],
                    "branch_name": r[5],
                }
                for r in wt_rows
            ],
        }

        summary = summarize_portfolio_status(state_snapshot, filter=filter_val)

        return _result(
            status="success",
            tool=tool,
            message="Portfolio status retrieved.",
            data=state_snapshot,
            summary=summary,
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_heartbeat
# ---------------------------------------------------------------------------

_LOCK_NAME = "heartbeat:portfolio"
_LOCK_TTL = 900
_LOCK_OWNER = "portfolio-manager"


def _handle_portfolio_heartbeat(args: dict[str, Any], **kwargs: Any) -> str:
    """Run the read-only portfolio heartbeat across all configured projects."""
    tool = "portfolio_heartbeat"
    root = resolve_root(args.get("root"))

    # Validate config first
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc))

    # Open state + init
    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        hb_id: str | None = None
        # Acquire lock
        lock = acquire_lock(conn, _LOCK_NAME, _LOCK_OWNER, _LOCK_TTL)
        if not lock.acquired:
            return _result(
                status="blocked",
                tool=tool,
                message="Heartbeat lock already held.",
                data={},
                summary="Heartbeat is already running.",
                reason="heartbeat_lock_already_held",
            )

        # Check gh
        gh_check = check_gh_available()
        if not gh_check.available:
            release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
            return _blocked(tool, gh_check.message)

        auth_check = check_gh_auth()
        if not auth_check.available:
            release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
            return _blocked(tool, auth_check.message)

        # Start heartbeat
        hb_id = start_heartbeat(conn)

        projects = select_projects(config)
        total_issues = 0
        total_prs = 0
        all_warnings: list[str] = []
        all_worktree_inspections = []

        for project in projects:
            upsert_project(conn, project)

            # GitHub sync
            sync = sync_project_github(project)
            _persist_github_sync(conn, project.id, sync)
            total_issues += sync.issues_count
            total_prs += sync.prs_count
            if sync.warnings:
                all_warnings.extend(sync.warnings)
                add_event(
                    conn,
                    hb_id,
                    "warning",
                    "github.sync.warning",
                    f"Sync warnings for {project.id}",
                    project_id=project.id,
                    data={"warnings": sync.warnings},
                )
            else:
                add_event(
                    conn,
                    hb_id,
                    "info",
                    "github.sync.project",
                    f"GitHub sync completed for {project.id}",
                    project_id=project.id,
                    data={"issues_seen": sync.issues_count, "prs_seen": sync.prs_count},
                )

            # Worktree inspect
            inspections = inspect_project_worktrees(project)
            all_worktree_inspections.extend(inspections)
            for insp in inspections:
                wt_id = f"{insp.project_id}"
                if insp.issue_number is not None:
                    wt_id += f"-issue-{insp.issue_number}"
                upsert_worktree(
                    conn,
                    {
                        "id": wt_id,
                        "project_id": insp.project_id,
                        "issue_number": insp.issue_number,
                        "path": insp.path,
                        "branch_name": insp.branch_name,
                        "state": insp.state,
                        "dirty_summary": insp.dirty_summary,
                    },
                )

        dirty_count = sum(
            1
            for w in all_worktree_inspections
            if w.state in ("dirty_uncommitted", "dirty_untracked", "merge_conflict", "rebase_conflict")
        )

        hb_summary = summarize_heartbeat(
            {
                "projects_checked": len(projects),
                "issues_seen": total_issues,
                "prs_seen": total_prs,
                "dirty_worktrees": dirty_count,
                "warnings": all_warnings,
            }
        )

        finish_heartbeat(conn, hb_id, "success", summary=hb_summary)
        release_lock(conn, _LOCK_NAME, _LOCK_OWNER)

        return _result(
            status="success",
            tool=tool,
            message=f"Heartbeat complete. {len(projects)} projects checked.",
            data={
                "projects_checked": len(projects),
                "issues_seen": total_issues,
                "prs_seen": total_prs,
                "dirty_worktrees": dirty_count,
                "warnings": all_warnings,
            },
            summary=hb_summary,
        )
    except Exception as e:
        with contextlib.suppress(Exception):
            if hb_id is not None:
                finish_heartbeat(conn, hb_id, "failed", error=str(e))
        with contextlib.suppress(Exception):
            release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
        raise
    finally:
        conn.close()
