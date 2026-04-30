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
from portfolio_manager.worktree_planner import build_plan, plan_to_dict

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
