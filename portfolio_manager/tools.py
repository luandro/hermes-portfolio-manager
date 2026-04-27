"""Tool handlers for the Portfolio Manager plugin.

Each handler imports from config, state, worktree, github_client, summary.
Each returns JSON with shared result shape:
    {"status", "tool", "message", "data", "summary", "reason"}
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


from pydantic import ValidationError as PydanticValidationError

from portfolio_manager.admin_functions import (
    add_project_to_config,
    archive_project_in_config,
    pause_project_in_config,
    remove_project_from_config,
    resume_project_in_config,
    set_project_auto_merge_in_config,
    set_project_priority_in_config,
    update_project_in_config,
)
from portfolio_manager.admin_locks import with_config_lock
from portfolio_manager.admin_models import AdminProjectConfig
from portfolio_manager.admin_writes import (
    create_projects_config_backup,
    load_config_dict,
    write_projects_config_atomic,
)
from portfolio_manager.config import (
    ConfigError,
    GithubRef,
    ProjectConfig,
    load_projects_config,
    resolve_root,
    select_projects,
)
from portfolio_manager.errors import redact_secrets
from portfolio_manager.github_client import (
    ProjectGitHubSyncResult,
    check_gh_auth,
    check_gh_available,
    sync_project_github,
)
from portfolio_manager.issue_artifacts import read_issue_artifact
from portfolio_manager.issue_drafts import (
    create_issue,
    create_issue_draft,
    create_issue_from_draft,
    update_issue_draft,
)
from portfolio_manager.issue_resolver import resolve_project
from portfolio_manager.repo_parser import parse_github_repo_ref
from portfolio_manager.repo_validation import check_gh_available_for_project_add
from portfolio_manager.state import (
    acquire_lock,
    add_event,
    finish_heartbeat,
    get_issue_draft,
    init_state,
    list_issue_drafts,
    open_state,
    release_lock,
    start_heartbeat,
    upsert_issue,
    upsert_issue_draft,
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


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    """Coerce string/bool args to proper bool (handles JSON string 'true'/'false')."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return default


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


def _failed(tool: str, message: str, data: dict[str, Any] | None = None) -> str:
    return _result(status="error", tool=tool, message=message, data=data, summary=message, reason="error")


def _ensure_dirs(root: Path) -> None:
    """Create state/, worktrees/, logs/, artifacts/ if missing."""
    for d in ("state", "worktrees", "logs", "artifacts", "backups"):
        (root / d).mkdir(parents=True, exist_ok=True)


def _persist_github_sync(conn: sqlite3.Connection, project_id: str, sync: ProjectGitHubSyncResult) -> None:
    """Persist fetched issues and PRs into the state database."""
    for issue in sync.issues:
        # NOTE: state='needs_triage' is the default for new rows; upsert_issue
        # intentionally preserves existing state on conflict (see state.py).
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

    _lock_acquired = False
    try:
        lock = acquire_lock(conn, _LOCK_NAME, _LOCK_OWNER, _LOCK_TTL)
        if not lock.acquired:
            return _result(
                status="blocked",
                tool=tool,
                message="Worktree inspect blocked: heartbeat lock already held.",
                data={},
                summary="Worktree inspect blocked: another operation is running.",
                reason="heartbeat_lock_already_held",
            )
        _lock_acquired = True

        all_inspections = []
        for project in projects:
            upsert_project(conn, project)
            inspections = inspect_project_worktrees(project, root)
            all_inspections.extend(inspections)

            # Upsert each worktree into state
            for insp in inspections:
                wt_id = f"{insp.project_id}-{insp.path}"
                if insp.issue_number is not None:
                    wt_id = f"{insp.project_id}-issue-{insp.issue_number}"
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
        if _lock_acquired:
            with contextlib.suppress(Exception):
                release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
        conn.close()


# ---------------------------------------------------------------------------
# Heartbeat lock constants (shared by status, worktree_inspect, and heartbeat)
# ---------------------------------------------------------------------------

_LOCK_NAME = "heartbeat:portfolio"
_LOCK_TTL = 900
_LOCK_OWNER = "portfolio-manager"


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

    _lock_acquired = False
    try:
        if refresh:
            lock = acquire_lock(conn, _LOCK_NAME, _LOCK_OWNER, _LOCK_TTL)
            if not lock.acquired:
                return _result(
                    status="blocked",
                    tool=tool,
                    message="Status refresh blocked: heartbeat lock already held.",
                    data={},
                    summary="Status refresh blocked: another operation is running.",
                    reason="heartbeat_lock_already_held",
                )
            _lock_acquired = True
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
                    inspections = inspect_project_worktrees(project, root)
                    for insp in inspections:
                        wt_id = f"{insp.project_id}-{insp.path}"
                        if insp.issue_number is not None:
                            wt_id = f"{insp.project_id}-issue-{insp.issue_number}"
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
                logger.warning("Status refresh skipped: %s", exc)
            except Exception as exc:
                logger.exception("Status refresh failed: %s", exc)
                return _result(
                    status="error",
                    tool=tool,
                    message=f"Status refresh failed: {redact_secrets(str(exc))}",
                    data={},
                    summary="Status refresh encountered an error.",
                    reason="refresh_failed",
                )

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

        summary = summarize_portfolio_status(state_snapshot, status_filter=filter_val)

        return _result(
            status="success",
            tool=tool,
            message="Portfolio status retrieved.",
            data=state_snapshot,
            summary=summary,
        )
    finally:
        if _lock_acquired:
            with contextlib.suppress(Exception):
                release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_heartbeat
# ---------------------------------------------------------------------------


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
        lock_acquired = False
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
        lock_acquired = True

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
            try:
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
                inspections = inspect_project_worktrees(project, root)
                all_worktree_inspections.extend(inspections)
                for insp in inspections:
                    wt_id = f"{insp.project_id}-{insp.path}"
                    if insp.issue_number is not None:
                        wt_id = f"{insp.project_id}-issue-{insp.issue_number}"
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
            except Exception as project_exc:
                logger.exception("Heartbeat project %s failed: %s", project.id, project_exc)
                all_warnings.append(f"Project {project.id} failed: {redact_secrets(str(project_exc))}")
                add_event(
                    conn,
                    hb_id,
                    "error",
                    "heartbeat.project.error",
                    f"Project {project.id} failed: {redact_secrets(str(project_exc))}",
                    project_id=project.id,
                )
                continue

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
                finish_heartbeat(conn, hb_id, "failed", error=redact_secrets(str(e)))
        if lock_acquired:
            with contextlib.suppress(Exception):
                release_lock(conn, _LOCK_NAME, _LOCK_OWNER)
        logger.exception("Heartbeat failed: %s", e)
        return _result(
            status="error",
            tool=tool,
            message=f"Heartbeat failed: {redact_secrets(str(e))}",
            data={},
            summary="Heartbeat failed.",
            reason="heartbeat_failed",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helper: load config + state for mutation handlers
# ---------------------------------------------------------------------------


def _load_config_or_blocked(tool: str, root: Path) -> dict[str, Any] | str:
    """Load config dict; return blocked JSON string if missing."""
    config = load_config_dict(root)
    if config is None:
        return _blocked(tool, "Config file not found. Add a project first.", reason="config_missing")
    return config


def _mutation_write(
    tool: str,
    root: Path,
    conn: sqlite3.Connection,
    updated: dict[str, Any],
    is_first_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Backup (if needed), atomic-write, return (backup_result, write_result)."""
    if not is_first_run:
        backup_result = create_projects_config_backup(root)
    else:
        backup_result = {"backup_created": False, "backup_path": None}
    write_result = write_projects_config_atomic(root, updated)
    return backup_result, write_result


def _sync_project_to_state(
    conn: sqlite3.Connection,
    updated: dict[str, Any],
    project_id: str,
) -> None:
    """Find project dict in updated config and upsert into SQLite."""
    for p in updated.get("projects", []):
        if p.get("id") == project_id:
            gh = p.get("github", {})
            pc = ProjectConfig(
                id=p["id"],
                name=p.get("name", p["id"]),
                repo=p.get("repo", ""),
                github=GithubRef(owner=gh.get("owner", ""), repo=gh.get("repo", "")),
                priority=p.get("priority", "medium"),
                status=p.get("status", "active"),
                default_branch=p.get("default_branch", "auto"),
            )
            upsert_project(conn, pc)
            break


# ---------------------------------------------------------------------------
# portfolio_project_add
# ---------------------------------------------------------------------------


def _handle_portfolio_project_add(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_add"
    root = resolve_root(args.get("root"))

    try:
        repo_arg = args.get("repo", "")
        parsed = parse_github_repo_ref(repo_arg)

        project = AdminProjectConfig(
            id=parsed.project_id,
            name=args.get("name", parsed.project_id),
            repo=parsed.repo_url,
            github_owner=parsed.owner,
            github_repo=parsed.repo,
            priority=args.get("priority", "medium"),
            status=args.get("status", "active"),
        )

        validate = args.get("validate_github", True)
        if isinstance(validate, str):
            validate = validate.lower() == "true"

        if validate:
            validation = check_gh_available_for_project_add(True, parsed.owner, parsed.repo)
            if validation is not None and not validation.available:
                return _blocked(tool, validation.message)

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = load_config_dict(root)
                is_first_run = config is None
                if config is None:
                    config = {"version": 1, "projects": []}

                updated = add_project_to_config(config, project)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, is_first_run)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))

                pc = ProjectConfig(
                    id=parsed.project_id,
                    name=args.get("name", parsed.project_id),
                    repo=parsed.repo_url,
                    github=GithubRef(owner=parsed.owner, repo=parsed.repo),
                    priority=args.get("priority", "medium"),
                    status=args.get("status", "active"),
                )
                upsert_project(conn, pc)

            return _result(
                status="success",
                tool=tool,
                message=f"Added project {parsed.project_id}",
                data={
                    "project_id": parsed.project_id,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                    "is_first_run": is_first_run,
                },
                summary=f"Added {parsed.project_id}."
                + (
                    " Backup created."
                    if backup_result.get("backup_created")
                    else (" No backup (first config)." if is_first_run else "")
                ),
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except PydanticValidationError as exc:
        return _blocked(tool, f"Validation error: {exc}")
    except Exception as exc:
        logger.exception("Failed to add project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_update
# ---------------------------------------------------------------------------


def _handle_portfolio_project_update(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_update"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        updates: dict[str, Any] = {}
        for key in ("name", "priority", "status", "default_branch", "notes"):
            if key in args:
                updates[key] = args[key]

        if not updates:
            return _blocked(tool, "No update fields provided")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = update_project_in_config(config, project_id, updates)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

            return _result(
                status="success",
                tool=tool,
                message=f"Updated project {project_id}",
                data={
                    "project_id": project_id,
                    "updated_fields": list(updates.keys()),
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Updated {project_id}: {', '.join(updates.keys())}.",
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to update project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_pause
# ---------------------------------------------------------------------------


def _handle_portfolio_project_pause(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_pause"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        reason = args.get("reason")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = pause_project_in_config(config, project_id, reason=reason)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

            return _result(
                status="success",
                tool=tool,
                message=f"Paused project {project_id}",
                data={
                    "project_id": project_id,
                    "reason": reason,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Paused {project_id}." + (f" Reason: {reason}" if reason else ""),
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to pause project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_resume
# ---------------------------------------------------------------------------


def _handle_portfolio_project_resume(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_resume"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = resume_project_in_config(config, project_id)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

            return _result(
                status="success",
                tool=tool,
                message=f"Resumed project {project_id}",
                data={
                    "project_id": project_id,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Resumed {project_id}.",
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to resume project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_archive
# ---------------------------------------------------------------------------


def _handle_portfolio_project_archive(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_archive"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        reason = args.get("reason")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = archive_project_in_config(config, project_id, reason=reason)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

            return _result(
                status="success",
                tool=tool,
                message=f"Archived project {project_id}",
                data={
                    "project_id": project_id,
                    "reason": reason,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Archived {project_id}." + (f" Reason: {reason}" if reason else ""),
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to archive project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_set_priority
# ---------------------------------------------------------------------------


def _handle_portfolio_project_set_priority(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_set_priority"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        priority = args.get("priority", "")
        if not project_id:
            return _blocked(tool, "project_id is required")
        if not priority:
            return _blocked(tool, "priority is required")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = set_project_priority_in_config(config, project_id, priority)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

            return _result(
                status="success",
                tool=tool,
                message=f"Set priority of {project_id} to {priority}",
                data={
                    "project_id": project_id,
                    "priority": priority,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Set {project_id} priority to {priority}.",
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to set priority")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_set_auto_merge
# ---------------------------------------------------------------------------


def _handle_portfolio_project_set_auto_merge(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_set_auto_merge"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")
        if "enabled" not in args:
            return _blocked(tool, "enabled is required")

        enabled = args["enabled"]
        if isinstance(enabled, str):
            enabled = enabled.lower() == "true"

        max_risk = args.get("max_risk")

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = set_project_auto_merge_in_config(config, project_id, enabled, max_risk=max_risk)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))
                _sync_project_to_state(conn, updated, project_id)

                # Read back actual persisted auto_merge values (defaults applied)
                actual_am = None
                for p in updated.get("projects", []):
                    if p.get("id") == project_id:
                        actual_am = p.get("auto_merge", {})
                        break

            return _result(
                status="success",
                tool=tool,
                message=f"Set auto-merge for {project_id}: enabled={enabled}",
                data={
                    "project_id": project_id,
                    "enabled": actual_am.get("enabled", enabled) if actual_am else enabled,
                    "max_risk": actual_am.get("max_risk", max_risk) if actual_am else max_risk,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Auto-merge for {project_id}: {'enabled' if enabled else 'disabled'}.",
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to set auto-merge")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_remove
# ---------------------------------------------------------------------------


def _handle_portfolio_project_remove(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_remove"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        confirm = args.get("confirm", False)
        if isinstance(confirm, str):
            confirm = confirm.lower() == "true"

        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)

        try:
            with with_config_lock(conn):
                config = _load_config_or_blocked(tool, root)
                if isinstance(config, str):
                    return config

                updated = remove_project_from_config(config, project_id, confirm=confirm)
                backup_result, write_result = _mutation_write(tool, root, conn, updated, False)
                if write_result.get("status") == "failed":
                    return _failed(tool, write_result.get("error", "Write failed"))

                # Archive in SQLite (don't delete — preserve history).
                # Only UPDATE existing rows to avoid clobbering metadata; if no
                # row exists yet (project was never synced), INSERT a minimal one.
                now_iso = datetime.now(UTC).isoformat()
                cursor = conn.execute(
                    "UPDATE projects SET status='archived', updated_at=? WHERE id=?",
                    (now_iso, project_id),
                )
                if cursor.rowcount == 0:
                    conn.execute(
                        "INSERT INTO projects (id, name, repo_url, priority, default_branch, status, created_at, updated_at) "
                        "VALUES (?, ?, '', 'low', 'auto', 'archived', ?, ?)",
                        (project_id, project_id, now_iso, now_iso),
                    )
                conn.commit()

            return _result(
                status="success",
                tool=tool,
                message=f"Removed project {project_id} from config",
                data={
                    "project_id": project_id,
                    "backup_created": backup_result.get("backup_created", False),
                    "backup_path": backup_result.get("backup_path"),
                },
                summary=f"Removed {project_id}. Backup created."
                if backup_result.get("backup_created")
                else f"Removed {project_id}.",
            )
        finally:
            conn.close()
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to remove project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_explain
# ---------------------------------------------------------------------------


def _handle_portfolio_project_explain(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_explain"
    root = resolve_root(args.get("root"))

    try:
        project_id = args.get("project_id", "")
        if not project_id:
            return _blocked(tool, "project_id is required")

        config = _load_config_or_blocked(tool, root)
        if isinstance(config, str):
            return config

        target = None
        for p in config.get("projects", []):
            if p.get("id") == project_id:
                target = p
                break

        if target is None:
            return _blocked(tool, f"Project not found: {project_id}")

        return _result(
            status="success",
            tool=tool,
            message=f"Configuration for {project_id}",
            data={"project": target},
            summary=(
                f"Project: {target.get('name', project_id)}\n"
                f"  Repo: {target.get('repo', 'N/A')}\n"
                f"  Priority: {target.get('priority', 'N/A')}\n"
                f"  Status: {target.get('status', 'N/A')}\n"
                f"  Branch: {target.get('default_branch', 'auto')}\n"
                f"  Auto-merge: enabled={target.get('auto_merge', {}).get('enabled', False)}, max_risk={target.get('auto_merge', {}).get('max_risk') or 'n/a'}\n"
                f"  Protected paths: {', '.join(target.get('protected_paths', [])) or 'none'}"
            ),
        )
    except Exception as exc:
        logger.exception("Failed to explain project")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_config_backup
# ---------------------------------------------------------------------------


def _handle_portfolio_project_config_backup(args: dict[str, Any], **kwargs: Any) -> str:
    tool = "portfolio_project_config_backup"
    root = resolve_root(args.get("root"))

    try:
        config = _load_config_or_blocked(tool, root)
        if isinstance(config, str):
            return config

        _ensure_dirs(root)
        backup_result = create_projects_config_backup(root)

        if not backup_result.get("backup_created"):
            return _blocked(tool, "No config file to back up")

        return _result(
            status="success",
            tool=tool,
            message="Config backup created",
            data=backup_result,
            summary=f"Backup saved to {backup_result.get('backup_path')}.",
        )
    except Exception as exc:
        logger.exception("Failed to create config backup")
        return _failed(tool, str(exc))


# ---------------------------------------------------------------------------
# portfolio_project_resolve (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_project_resolve(args: dict[str, Any], **kwargs: Any) -> str:
    """Resolve a project reference to a project ID."""
    tool = "portfolio_project_resolve"
    root = resolve_root(args.get("root"))

    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc))

    resolution = resolve_project(
        config,
        project_ref=args.get("project_ref"),
        text=args.get("text"),
    )

    if resolution.state == "resolved":
        return _result(
            status="success",
            tool=tool,
            message=resolution.message,
            data={"state": "resolved", "project_id": resolution.project_id},
            summary=resolution.message,
        )
    if resolution.state == "ambiguous":
        return _result(
            status="success",
            tool=tool,
            message=resolution.message,
            data={"state": "ambiguous", "candidates": resolution.candidates},
            summary=resolution.message,
        )
    return _blocked(tool, resolution.message, reason="not_found")


# ---------------------------------------------------------------------------
# portfolio_issue_draft (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_draft(args: dict[str, Any], **kwargs: Any) -> str:
    """Create an issue draft from user-supplied text."""
    tool = "portfolio_issue_draft"
    root = resolve_root(args.get("root"))

    text = args.get("text", "")
    if not text:
        return _blocked(tool, "text is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        result = create_issue_draft(
            root,
            conn,
            text,
            project_ref=args.get("project_ref"),
            title=args.get("title"),
            force_rough_issue=_coerce_bool(args.get("force_rough_issue")),
        )

        if result.get("blocked"):
            return _blocked(
                tool,
                result.get("reason", "Draft creation blocked"),
                reason=result.get("reason"),
                data=result,
            )

        return _result(
            status="success",
            tool=tool,
            message=f"Draft created: {result.get('draft_id', '')}",
            data=result,
            summary=f"Draft created for {result.get('project_id', 'unknown')}. State: {result.get('state', '')}",
        )
    except ValueError as exc:
        return _blocked(tool, str(exc), reason="validation_error")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_questions (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_questions(args: dict[str, Any], **kwargs: Any) -> str:
    """Read clarifying questions for an existing draft."""
    tool = "portfolio_issue_questions"
    root = resolve_root(args.get("root"))

    draft_id = args.get("draft_id", "")
    if not draft_id:
        return _blocked(tool, "draft_id is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        row = get_issue_draft(conn, draft_id)
        if row is None:
            return _blocked(tool, f"Draft not found: {draft_id}", reason="not_found")

        project_id = row.get("project_id") or "unresolved"
        questions_text = read_issue_artifact(root, project_id, draft_id, "questions.md")
        questions = (
            [q.removeprefix("- ").strip() for q in (questions_text or "").splitlines() if q.strip()]
            if questions_text
            else []
        )

        return _result(
            status="success",
            tool=tool,
            message=f"Questions for draft {draft_id}",
            data={"draft_id": draft_id, "questions": questions},
            summary="\n".join(questions) if questions else "No questions found.",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_update_draft (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_update_draft(args: dict[str, Any], **kwargs: Any) -> str:
    """Update an existing issue draft."""
    tool = "portfolio_issue_update_draft"
    root = resolve_root(args.get("root"))

    draft_id = args.get("draft_id", "")
    if not draft_id:
        return _blocked(tool, "draft_id is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        result = update_issue_draft(
            root,
            conn,
            draft_id,
            answers=args.get("answers"),
            project_id=args.get("project_id"),
            title=args.get("title"),
            force_ready=_coerce_bool(args.get("force_ready")),
        )

        if result.get("blocked"):
            return _blocked(
                tool,
                result.get("reason", "Update blocked"),
                reason=result.get("reason"),
                data=result,
            )

        return _result(
            status="success",
            tool=tool,
            message=f"Draft updated: {draft_id}",
            data=result,
            summary=f"Draft {draft_id} updated. State: {result.get('state', '')}",
        )
    except ValueError as exc:
        return _blocked(tool, str(exc), reason="validation_error")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_create (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_create(args: dict[str, Any], **kwargs: Any) -> str:
    """Create a GitHub issue directly (draft + create)."""
    tool = "portfolio_issue_create"
    root = resolve_root(args.get("root"))

    project_id = args.get("project_id", "")
    title = args.get("title", "")
    body = args.get("body", "")

    if not project_id:
        return _blocked(tool, "project_id is required")
    if not title:
        return _blocked(tool, "title is required")
    if not body:
        return _blocked(tool, "body is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        result = create_issue(
            root,
            conn,
            text=body,
            title=title,
            body=body,
            project_ref=project_id,
            confirm=_coerce_bool(args.get("confirm")),
            dry_run=_coerce_bool(args.get("dry_run")),
            allow_possible_duplicate=_coerce_bool(args.get("allow_possible_duplicate")),
        )

        if result.get("blocked"):
            return _blocked(
                tool,
                result.get("reason", "Issue creation blocked"),
                reason=result.get("reason"),
                data=result,
            )

        if result.get("dry_run"):
            return _result(
                status="success",
                tool=tool,
                message="Dry run preview",
                data=result,
                summary="Dry run — no issue created.",
            )

        return _result(
            status="success",
            tool=tool,
            message=f"Issue created: #{result.get('issue_number', '')}",
            data=result,
            summary=f"Created issue #{result.get('issue_number', '')} — {result.get('issue_url', '')}",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_create_from_draft (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_create_from_draft(args: dict[str, Any], **kwargs: Any) -> str:
    """Create a GitHub issue from an existing draft."""
    tool = "portfolio_issue_create_from_draft"
    root = resolve_root(args.get("root"))

    draft_id = args.get("draft_id", "")
    if not draft_id:
        return _blocked(tool, "draft_id is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        result = create_issue_from_draft(
            root,
            conn,
            draft_id,
            confirm=_coerce_bool(args.get("confirm")),
            allow_open_questions=_coerce_bool(args.get("allow_open_questions")),
            allow_possible_duplicate=_coerce_bool(args.get("allow_possible_duplicate")),
            dry_run=_coerce_bool(args.get("dry_run")),
        )

        if result.get("blocked"):
            return _blocked(
                tool,
                result.get("reason", "Issue creation blocked"),
                reason=result.get("reason"),
                data=result,
            )

        if result.get("dry_run"):
            return _result(
                status="success",
                tool=tool,
                message="Dry run preview",
                data=result,
                summary="Dry run — no issue created.",
            )

        return _result(
            status="success",
            tool=tool,
            message=f"Issue created from draft: #{result.get('issue_number', '')}",
            data=result,
            summary=f"Created issue #{result.get('issue_number', '')} — {result.get('issue_url', '')}",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_explain_draft (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_explain_draft(args: dict[str, Any], **kwargs: Any) -> str:
    """Explain the current state and content of an issue draft."""
    tool = "portfolio_issue_explain_draft"
    root = resolve_root(args.get("root"))

    draft_id = args.get("draft_id", "")
    if not draft_id:
        return _blocked(tool, "draft_id is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        row = get_issue_draft(conn, draft_id)
        if row is None:
            return _blocked(tool, f"Draft not found: {draft_id}", reason="not_found")

        project_id = row.get("project_id") or "unresolved"
        spec = read_issue_artifact(root, project_id, draft_id, "spec.md")
        questions = read_issue_artifact(root, project_id, draft_id, "questions.md")

        summary_lines = [
            f"Draft: {draft_id}",
            f"State: {row.get('state', '')}",
            f"Title: {row.get('title', '')}",
            f"Project: {row.get('project_id', 'unresolved')}",
            f"Readiness: {row.get('readiness', 0.0)}",
        ]
        if row.get("github_issue_number"):
            summary_lines.append(f"GitHub Issue: #{row['github_issue_number']}")

        return _result(
            status="success",
            tool=tool,
            message=f"Explanation for draft {draft_id}",
            data={
                "draft": {k: row[k] for k in row},
                "spec": spec,
                "questions": questions,
            },
            summary="\n".join(summary_lines),
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_list_drafts (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_list_drafts(args: dict[str, Any], **kwargs: Any) -> str:
    """List issue drafts with optional filters."""
    tool = "portfolio_issue_list_drafts"
    root = resolve_root(args.get("root"))

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        drafts = list_issue_drafts(
            conn,
            project_id=args.get("project_id"),
            state=args.get("state"),
            include_created=_coerce_bool(args.get("include_created")),
        )

        draft_summaries = [
            {
                "draft_id": d.get("draft_id"),
                "project_id": d.get("project_id"),
                "state": d.get("state"),
                "title": d.get("title"),
                "readiness": d.get("readiness"),
            }
            for d in drafts
        ]

        return _result(
            status="success",
            tool=tool,
            message=f"Found {len(drafts)} drafts.",
            data={"drafts": draft_summaries, "count": len(drafts)},
            summary=f"{len(drafts)} drafts found.",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_issue_discard_draft (MVP 3)
# ---------------------------------------------------------------------------


def _handle_portfolio_issue_discard_draft(args: dict[str, Any], **kwargs: Any) -> str:
    """Discard an issue draft."""
    tool = "portfolio_issue_discard_draft"
    root = resolve_root(args.get("root"))

    draft_id = args.get("draft_id", "")
    if not draft_id:
        return _blocked(tool, "draft_id is required")

    confirm = args.get("confirm", False)
    if isinstance(confirm, str):
        confirm = confirm.lower() == "true"
    if not confirm:
        return _blocked(tool, "confirm=true is required to discard", reason="confirm_required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        row = get_issue_draft(conn, draft_id)
        if row is None:
            return _blocked(tool, f"Draft not found: {draft_id}", reason="not_found")

        current_state = row.get("state", "")
        if current_state == "created":
            return _blocked(tool, "Cannot discard a draft already created as a GitHub issue", reason="already_created")

        # Update state to discarded
        upsert_issue_draft(
            conn,
            {
                "draft_id": draft_id,
                "project_id": row.get("project_id"),
                "state": "discarded",
                "title": row.get("title"),
                "readiness": row.get("readiness"),
                "artifact_path": row.get("artifact_path", ""),
            },
        )

        return _result(
            status="success",
            tool=tool,
            message=f"Draft discarded: {draft_id}",
            data={"draft_id": draft_id, "state": "discarded"},
            summary=f"Draft {draft_id} discarded.",
        )
    finally:
        conn.close()
