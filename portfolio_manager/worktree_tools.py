"""Tool handlers for MVP 5 worktree-prep tools — Phases 6.3, 7.4, 8.4, 9.

Thin wrappers: validate inputs → resolve root → open conn → call helpers →
return shared result envelope. Mutating tools enforce dry_run/confirm gates
and acquire locks before any side effect.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from portfolio_manager.config import (
    ConfigError,
    load_projects_config,
    resolve_root,
    select_projects,
)
from portfolio_manager.errors import redact_secrets
from portfolio_manager.state import init_state, open_state, upsert_project
from portfolio_manager.worktree_artifacts import (
    base_artifact_dir,
    ensure_artifact_dir,
    issue_artifact_dir,
    write_commands,
    write_error,
    write_plan,
    write_result,
)
from portfolio_manager.worktree_create import create_issue_worktree
from portfolio_manager.worktree_locks import (
    WorktreeLockBusy,
    with_project_and_issue_locks,
    with_project_lock,
)
from portfolio_manager.worktree_planner import build_plan, plan_to_dict
from portfolio_manager.worktree_prepare import clone_base_repo, refresh_base_branch
from portfolio_manager.worktree_reconcile import (
    discover_worktrees,
    discovered_to_dict,
    suggest_next_action,
)
from portfolio_manager.worktree_state import (
    upsert_base_worktree,
    upsert_issue_worktree,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Local result helpers (mirror tools.py shape)
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


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return default


def _ensure_dirs(root: Path) -> None:
    for d in ("state", "worktrees", "logs", "artifacts"):
        (root / d).mkdir(parents=True, exist_ok=True)


def _validate_issue_number(args: dict[str, Any]) -> tuple[int | None, str | None]:
    raw = args.get("issue_number")
    if raw is None:
        return None, "issue_number is required"
    if isinstance(raw, bool):
        return None, f"issue_number must be int, got {raw!r}"
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None, f"issue_number must be int, got {raw!r}"
    if n <= 0:
        return None, f"issue_number must be positive, got {n}"
    return n, None


# ---------------------------------------------------------------------------
# 6.3 portfolio_worktree_plan handler (read-only)
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_plan(args: dict[str, Any], **kwargs: Any) -> str:
    """Plan a worktree creation. Read-only — never writes SQLite or artifacts."""
    tool = "portfolio_worktree_plan"
    project_ref = args.get("project_ref", "")
    if not project_ref:
        return _blocked(tool, "project_ref is required", reason="invalid_input")

    issue_number, err = _validate_issue_number(args)
    if err is not None:
        return _blocked(tool, err, reason="invalid_input")
    assert issue_number is not None  # narrow for type-checker

    root = resolve_root(args.get("root"))
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    plan = build_plan(
        config,
        project_ref=project_ref,
        issue_number=issue_number,
        base_branch=args.get("base_branch"),
        branch_name=args.get("branch_name"),
        refresh_base=_coerce_bool(args.get("refresh_base"), default=True),
        root=root,
    )
    plan_dict = plan_to_dict(plan)

    if plan.is_blocked:
        reason = ", ".join(plan.blocked_reasons)
        return _result(
            status="blocked",
            tool=tool,
            message=f"Worktree plan blocked: {reason}",
            data={"plan": plan_dict},
            summary=f"Blocked: {reason}",
            reason="blocked",
        )
    if plan.is_skipped:
        return _result(
            status="skipped",
            tool=tool,
            message=plan.skipped_reason or "exact match exists",
            data={"plan": plan_dict},
            summary=plan.skipped_reason or "skipped",
            reason="exact_match",
        )

    summary_parts = [f"plan {plan.project_id}#{plan.issue_number} → {plan.branch_name}"]
    if plan.would_clone_base:
        summary_parts.append("clone base")
    if plan.would_refresh_base:
        summary_parts.append("ff-only refresh")
    if plan.would_create_worktree:
        summary_parts.append("create worktree")

    return _result(
        status="success",
        tool=tool,
        message=f"Plan ready for {plan.project_id}#{plan.issue_number}",
        data={"plan": plan_dict},
        summary="; ".join(summary_parts),
    )


# ---------------------------------------------------------------------------
# 7.4 portfolio_worktree_prepare_base handler
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_prepare_base(args: dict[str, Any], **kwargs: Any) -> str:
    """Clone (if missing) and ff-only refresh the project base repo."""
    tool = "portfolio_worktree_prepare_base"
    project_ref = args.get("project_ref", "")
    if not project_ref:
        return _blocked(tool, "project_ref is required", reason="invalid_input")

    dry_run = _coerce_bool(args.get("dry_run"), default=True)
    confirm = _coerce_bool(args.get("confirm"), default=False)
    if not dry_run and not confirm:
        return _blocked(tool, "confirm=true required when dry_run=false", reason="confirm_required")

    root = resolve_root(args.get("root"))
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    # Build a minimal plan without an issue number so we only validate the
    # project + base path + branch up-front without needing a real issue.
    plan = build_plan(
        config,
        project_ref=project_ref,
        issue_number=None,
        base_branch=args.get("base_branch"),
        refresh_base=_coerce_bool(args.get("refresh_base"), default=True),
        root=root,
    )
    if plan.is_blocked:
        return _blocked(tool, "; ".join(plan.blocked_reasons), reason="blocked", data={"plan": plan_to_dict(plan)})

    if dry_run:
        return _result(
            status="success",
            tool=tool,
            message=f"[dry-run] {plan.project_id}: would clone={plan.would_clone_base} refresh={plan.would_refresh_base}",
            data={"plan": plan_to_dict(plan)},
            summary="dry-run only; no artifacts written",
        )

    _ensure_dirs(root)
    artifact_dir = ensure_artifact_dir(base_artifact_dir(root, plan.project_id))
    write_plan(artifact_dir, plan_to_dict(plan))
    write_commands(artifact_dir, plan.commands)
    return _execute_prepare_base(tool, plan, config, root, artifact_dir)


def _persist_failed_base(conn: Any, plan: Any, state: str) -> None:
    upsert_base_worktree(
        conn,
        project_id=plan.project_id,
        path=str(plan.base_path),
        state=state,
        branch_name=plan.base_branch,
        base_branch=plan.base_branch,
        remote_url=plan.remote_url,
    )


def _ensure_project_row(conn: Any, config: Any, project_id: str) -> None:
    """Make sure a row exists in the ``projects`` table for FK satisfaction."""
    for project in config.projects:
        if project.id == project_id:
            upsert_project(conn, project)
            return


def _execute_prepare_base(tool: str, plan: Any, config: Any, root: Path, artifact_dir: Path) -> str:
    """Run clone + refresh under the project lock with full artifact logging."""
    conn = open_state(root)
    init_state(conn)
    try:
        _ensure_project_row(conn, config, plan.project_id)
        with with_project_lock(conn, plan.project_id):
            if plan.would_clone_base:
                outcome = clone_base_repo(remote_url=plan.remote_url_raw, target_path=plan.base_path, root=root)
                if outcome.is_blocked or outcome.is_failed:
                    payload = {
                        "stage": "clone",
                        "blocked_reasons": outcome.blocked_reasons,
                        "failures": outcome.failures,
                    }
                    write_error(artifact_dir, payload)
                    _persist_failed_base(conn, plan, "failed" if outcome.is_failed else "blocked")
                    return _blocked(
                        tool,
                        "; ".join(outcome.blocked_reasons or outcome.failures),
                        reason="failed" if outcome.is_failed else "blocked",
                        data={"outcome": payload},
                    )
            refreshed = False
            if plan.would_refresh_base:
                outcome = refresh_base_branch(
                    base_path=plan.base_path,
                    base_branch=plan.base_branch,
                    remote_url=plan.remote_url_raw,
                )
                if outcome.is_blocked or outcome.is_failed:
                    payload = {
                        "stage": "refresh",
                        "blocked_reasons": outcome.blocked_reasons,
                        "failures": outcome.failures,
                    }
                    write_error(artifact_dir, payload)
                    fallback_state = (
                        outcome.final_state
                        if outcome.final_state in {"merge_conflict", "rebase_conflict", "dirty_uncommitted", "diverged"}
                        else ("failed" if outcome.is_failed else "blocked")
                    )
                    persist_state = fallback_state if fallback_state != "diverged" else "blocked"
                    _persist_failed_base(conn, plan, persist_state)
                    return _blocked(
                        tool,
                        "; ".join(outcome.blocked_reasons or outcome.failures),
                        reason="failed" if outcome.is_failed else "blocked",
                        data={"outcome": payload},
                    )
                refreshed = outcome.refreshed
            upsert_base_worktree(
                conn,
                project_id=plan.project_id,
                path=str(plan.base_path),
                state="ready",
                branch_name=plan.base_branch,
                base_branch=plan.base_branch,
                remote_url=plan.remote_url,
            )
            result_payload = {
                "status": "success",
                "cloned": plan.would_clone_base,
                "refreshed": refreshed,
            }
            write_result(artifact_dir, result_payload)
            return _result(
                status="success",
                tool=tool,
                message=f"Base repo ready for {plan.project_id}",
                data={"outcome": result_payload, "artifact_dir": str(artifact_dir)},
                summary=f"prepared base for {plan.project_id}",
            )
    except WorktreeLockBusy as exc:
        return _blocked(tool, str(exc), reason="lock_busy")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 8.4 portfolio_worktree_create_issue handler
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_create_issue(args: dict[str, Any], **kwargs: Any) -> str:
    """Create an issue worktree (idempotent on exact-match clean state)."""
    tool = "portfolio_worktree_create_issue"
    project_ref = args.get("project_ref", "")
    if not project_ref:
        return _blocked(tool, "project_ref is required", reason="invalid_input")

    issue_number, err = _validate_issue_number(args)
    if err is not None:
        return _blocked(tool, err, reason="invalid_input")
    assert issue_number is not None

    dry_run = _coerce_bool(args.get("dry_run"), default=True)
    confirm = _coerce_bool(args.get("confirm"), default=False)
    if not dry_run and not confirm:
        return _blocked(tool, "confirm=true required when dry_run=false", reason="confirm_required")

    root = resolve_root(args.get("root"))
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    plan = build_plan(
        config,
        project_ref=project_ref,
        issue_number=issue_number,
        base_branch=args.get("base_branch"),
        branch_name=args.get("branch_name"),
        refresh_base=_coerce_bool(args.get("refresh_base"), default=True),
        root=root,
    )
    if plan.is_blocked:
        return _blocked(tool, "; ".join(plan.blocked_reasons), reason="blocked", data={"plan": plan_to_dict(plan)})

    if dry_run:
        message = f"[dry-run] {plan.project_id}#{issue_number}: would_create={plan.would_create_worktree}"
        return _result(
            status="success" if not plan.is_skipped else "skipped",
            tool=tool,
            message=message,
            data={"plan": plan_to_dict(plan)},
            summary="dry-run only; no artifacts written",
        )

    _ensure_dirs(root)
    artifact_dir = ensure_artifact_dir(issue_artifact_dir(root, plan.project_id, issue_number))
    write_plan(artifact_dir, plan_to_dict(plan))
    write_commands(artifact_dir, plan.commands)
    return _execute_create_issue(tool, plan, config, root, artifact_dir, issue_number)


def _execute_create_issue(
    tool: str,
    plan: Any,
    config: Any,
    root: Path,
    artifact_dir: Path,
    issue_number: int,
) -> str:
    conn = open_state(root)
    init_state(conn)
    try:
        _ensure_project_row(conn, config, plan.project_id)
        with with_project_and_issue_locks(conn, plan.project_id, issue_number):
            # Auto-prepare the base if needed (clone/refresh) — same gates apply.
            if plan.would_clone_base:
                outcome = clone_base_repo(remote_url=plan.remote_url_raw, target_path=plan.base_path, root=root)
                if outcome.is_blocked or outcome.is_failed:
                    payload = {
                        "stage": "auto_clone",
                        "blocked_reasons": outcome.blocked_reasons,
                        "failures": outcome.failures,
                    }
                    write_error(artifact_dir, payload)
                    return _blocked(
                        tool,
                        "; ".join(outcome.blocked_reasons or outcome.failures),
                        reason="failed" if outcome.is_failed else "blocked",
                        data={"outcome": payload},
                    )
            if plan.would_refresh_base:
                outcome = refresh_base_branch(
                    base_path=plan.base_path,
                    base_branch=plan.base_branch,
                    remote_url=plan.remote_url_raw,
                )
                if outcome.is_blocked or outcome.is_failed:
                    payload = {
                        "stage": "auto_refresh",
                        "blocked_reasons": outcome.blocked_reasons,
                        "failures": outcome.failures,
                    }
                    write_error(artifact_dir, payload)
                    return _blocked(
                        tool,
                        "; ".join(outcome.blocked_reasons or outcome.failures),
                        reason="failed" if outcome.is_failed else "blocked",
                        data={"outcome": payload},
                    )
            # Now create the issue worktree.
            create_outcome = create_issue_worktree(
                base_path=plan.base_path,
                issue_path=plan.issue_worktree_path,
                branch_name=plan.branch_name,
                base_branch=plan.base_branch,
                remote_url=plan.remote_url_raw,
                root=root,
            )
            if create_outcome.is_blocked or create_outcome.is_failed:
                payload = {
                    "stage": "worktree_add",
                    "blocked_reasons": create_outcome.blocked_reasons,
                    "failures": create_outcome.failures,
                }
                write_error(artifact_dir, payload)
                return _blocked(
                    tool,
                    "; ".join(create_outcome.blocked_reasons or create_outcome.failures),
                    reason="failed" if create_outcome.is_failed else "blocked",
                    data={"outcome": payload},
                )
            upsert_issue_worktree(
                conn,
                project_id=plan.project_id,
                issue_number=issue_number,
                path=str(plan.issue_worktree_path),
                state="clean",
                branch_name=plan.branch_name,
                base_branch=plan.base_branch,
                remote_url=plan.remote_url,
            )
            result_payload = {
                "status": "success",
                "created": create_outcome.created,
                "skipped": create_outcome.skipped,
            }
            write_result(artifact_dir, result_payload)
            return _result(
                status="skipped" if create_outcome.skipped else "success",
                tool=tool,
                message=(
                    f"Issue worktree {'matched' if create_outcome.skipped else 'created'} "
                    f"for {plan.project_id}#{issue_number}"
                ),
                data={"outcome": result_payload, "artifact_dir": str(artifact_dir)},
                summary=f"{plan.project_id}#{issue_number} → {plan.branch_name}",
            )
    except WorktreeLockBusy as exc:
        return _blocked(tool, str(exc), reason="lock_busy")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 9.1 portfolio_worktree_list handler (read-only by default)
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_list(args: dict[str, Any], **kwargs: Any) -> str:
    """List discovered worktrees. Optionally inspect each (which writes SQLite)."""
    tool = "portfolio_worktree_list"
    root = resolve_root(args.get("root"))
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    project_ref = args.get("project_ref")
    include_archived = _coerce_bool(args.get("include_archived"), default=False)
    include_paused = _coerce_bool(args.get("include_paused"), default=False)
    inspect = _coerce_bool(args.get("inspect"), default=False)

    if project_ref:
        projects = [p for p in config.projects if p.id == project_ref]
        if not projects:
            return _blocked(tool, f"project not found: {project_ref!r}", reason="not_found")
    else:
        projects = select_projects(config, include_archived=include_archived, include_paused=include_paused)

    discovered = discover_worktrees(root, projects, inspect=inspect)

    if inspect:
        _ensure_dirs(root)
        conn = open_state(root)
        init_state(conn)
        try:
            for project in projects:
                _ensure_project_row(conn, config, project.id)
            for wt in discovered:
                if not wt.project_id:
                    continue
                if wt.kind == "issue" and wt.issue_number is not None:
                    upsert_issue_worktree(
                        conn,
                        project_id=wt.project_id,
                        issue_number=wt.issue_number,
                        path=wt.path,
                        state=wt.state if wt.state != "unknown" else "missing",
                        branch_name=wt.branch_name,
                        remote_url=wt.remote_url,
                    )
                elif wt.kind == "base":
                    upsert_base_worktree(
                        conn,
                        project_id=wt.project_id,
                        path=wt.path,
                        state=wt.state if wt.state != "unknown" else "missing",
                        branch_name=wt.branch_name,
                        remote_url=wt.remote_url,
                    )
        finally:
            conn.close()

    payload = [discovered_to_dict(w) for w in discovered]
    return _result(
        status="success",
        tool=tool,
        message=f"Found {len(payload)} worktrees ({'inspected' if inspect else 'not inspected'})",
        data={"worktrees": payload, "count": len(payload), "inspected": inspect},
        summary=f"{len(payload)} worktrees" + (" (inspected)" if inspect else ""),
    )


# ---------------------------------------------------------------------------
# 9.3 portfolio_worktree_explain handler (read-only)
# ---------------------------------------------------------------------------


def _handle_portfolio_worktree_explain(args: dict[str, Any], **kwargs: Any) -> str:
    """Explain a worktree state and suggest the next safe action."""
    tool = "portfolio_worktree_explain"
    project_ref = args.get("project_ref", "")
    if not project_ref:
        return _blocked(tool, "project_ref is required", reason="invalid_input")

    root = resolve_root(args.get("root"))
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    projects = [p for p in config.projects if p.id == project_ref]
    if not projects:
        return _blocked(tool, f"project not found: {project_ref!r}", reason="not_found")

    discovered = discover_worktrees(root, projects, inspect=True)
    issue_number = args.get("issue_number")
    if issue_number is not None:
        try:
            n = int(issue_number)
        except (TypeError, ValueError):
            return _blocked(tool, f"issue_number must be int, got {issue_number!r}", reason="invalid_input")
        target = next((w for w in discovered if w.kind == "issue" and w.issue_number == n), None)
    else:
        target = next((w for w in discovered if w.kind == "base"), None)

    if target is None:
        return _result(
            status="success",
            tool=tool,
            message="No matching worktree found on disk.",
            data={"target": None, "suggestion": "Run portfolio_worktree_prepare_base / create_issue first."},
            summary="not found",
        )

    suggestion = suggest_next_action(target.state, target.kind)
    return _result(
        status="success",
        tool=tool,
        message=f"{target.kind} worktree for {target.project_id} is {target.state}",
        data={"target": discovered_to_dict(target), "suggestion": suggestion},
        summary=suggestion,
    )
