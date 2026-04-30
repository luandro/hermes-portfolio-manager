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
)
from portfolio_manager.errors import redact_secrets
from portfolio_manager.state import init_state, open_state, upsert_project
from portfolio_manager.worktree_artifacts import (
    base_artifact_dir,
    ensure_artifact_dir,
    write_commands,
    write_error,
    write_plan,
    write_preflight,
    write_result,
)
from portfolio_manager.worktree_locks import WorktreeLockBusy, with_project_lock
from portfolio_manager.worktree_planner import build_plan, plan_to_dict
from portfolio_manager.worktree_prepare import clone_base_repo, refresh_base_branch
from portfolio_manager.worktree_state import upsert_base_worktree

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
    _ensure_dirs(root)
    try:
        config = load_projects_config(root)
    except ConfigError as exc:
        return _blocked(tool, str(exc), reason="config_error")

    # Build a minimal plan using issue 1 as a placeholder so we can validate the
    # project + base path + branch up-front without needing a real issue.
    plan = build_plan(
        config,
        project_ref=project_ref,
        issue_number=1,
        base_branch=args.get("base_branch"),
        refresh_base=_coerce_bool(args.get("refresh_base"), default=True),
        root=root,
    )
    if plan.is_blocked and not (plan.would_clone_base or plan.would_refresh_base):
        return _blocked(tool, "; ".join(plan.blocked_reasons), reason="blocked", data={"plan": plan_to_dict(plan)})

    artifact_dir = ensure_artifact_dir(base_artifact_dir(root, plan.project_id))
    write_plan(artifact_dir, plan_to_dict(plan))
    write_commands(artifact_dir, plan.commands)
    if dry_run:
        write_preflight(artifact_dir, {"dry_run": True})
        return _result(
            status="success",
            tool=tool,
            message=f"[dry-run] {plan.project_id}: would clone={plan.would_clone_base} refresh={plan.would_refresh_base}",
            data={"plan": plan_to_dict(plan), "artifact_dir": str(artifact_dir)},
            summary=f"dry-run plan written to {artifact_dir}",
        )
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
