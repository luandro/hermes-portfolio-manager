"""Tool handlers for MVP 6 implementation tools.

Each handler extracts args, resolves root, opens state DB, calls the
appropriate helper, and returns a JSON string matching the shared result
format::

    {"status": ..., "tool": ..., "message": ..., "data": {},
     "summary": ..., "reason": null}
"""

from __future__ import annotations

import json
import logging
from typing import Any

from portfolio_manager.config import resolve_root
from portfolio_manager.implementation_jobs import run_initial_implementation, run_review_fix
from portfolio_manager.implementation_locks import ImplementationLockBusy
from portfolio_manager.implementation_planner import build_initial_plan
from portfolio_manager.implementation_state import list_jobs
from portfolio_manager.state import init_state, open_state

logger = logging.getLogger(__name__)


def _result(
    status: str,
    tool: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    summary: str | None = None,
    reason: str | None = None,
) -> str:
    return json.dumps(
        {
            "status": status,
            "tool": tool,
            "message": message,
            "data": data or {},
            "summary": summary or message,
            "reason": reason,
        }
    )


def _open_db(root: Any) -> Any:
    """Resolve root, open + init state DB, return (root_path, conn)."""
    root_path = resolve_root(root if isinstance(root, str) else None)
    conn = open_state(root_path)
    init_state(conn)
    return root_path, conn


# ---------------------------------------------------------------------------
# 13.1 — plan / status / list / explain
# ---------------------------------------------------------------------------


def _handle_portfolio_implementation_plan(args: dict[str, Any]) -> str:
    """Plan an implementation for an issue. Read-only — no state mutation."""
    tool = "portfolio_implementation_plan"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        plan = build_initial_plan(
            conn,
            root_path,
            project_ref=args["project_ref"],
            issue_number=args["issue_number"],
            harness_id=args["harness_id"],
            expected_branch=args.get("expected_branch"),
        )

        plan_dict = {
            "job_type": plan.job_type,
            "project_id": plan.project_id,
            "issue_number": plan.issue_number,
            "harness_id": plan.harness_id,
            "workspace_path": str(plan.workspace_path) if plan.workspace_path else None,
            "source_artifact_path": str(plan.source_artifact_path) if plan.source_artifact_path else None,
            "expected_branch": plan.expected_branch,
            "base_sha": plan.base_sha,
            "proposed_command": plan.proposed_command,
            "required_checks": plan.required_checks,
            "blocked_reasons": plan.blocked_reasons,
            "warnings": plan.warnings,
        }

        if plan.blocked_reasons:
            return _result(
                "blocked",
                tool,
                "Plan blocked: " + "; ".join(plan.blocked_reasons),
                data={"plan": plan_dict, "blocked_reasons": plan.blocked_reasons},
                summary="Implementation plan blocked: " + "; ".join(plan.blocked_reasons),
                reason="; ".join(plan.blocked_reasons),
            )

        return _result(
            "success",
            tool,
            "Implementation plan generated successfully.",
            data={"plan": plan_dict},
            summary="Implementation plan generated.",
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_plan failed")
        return _result("failed", tool, f"Plan failed: {exc}", reason=str(exc))


def _handle_portfolio_implementation_status(args: dict[str, Any]) -> str:
    """Get the status of an implementation run."""
    tool = "portfolio_implementation_status"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        project_ref = args.get("project_ref")
        issue_number = args.get("issue_number")

        if not project_ref or issue_number is None:
            return _result(
                "blocked",
                tool,
                "project_ref and issue_number are required.",
                reason="missing project_ref or issue_number",
            )

        # Resolve project_ref to project_id via planner helper
        from portfolio_manager.implementation_planner import _resolve_project_id

        project_id = _resolve_project_id(conn, root_path, project_ref)

        if project_id is None:
            return _result(
                "blocked",
                tool,
                f"Could not resolve project_ref: {project_ref!r}",
                reason=f"unknown project_ref: {project_ref!r}",
            )

        # Find the most recent job for this project+issue
        jobs = list_jobs(conn, project_id=project_id, issue_number=int(issue_number))
        if not jobs:
            return _result(
                "blocked",
                tool,
                f"No implementation job found for {project_id} issue #{issue_number}.",
                reason="no job found",
            )

        job = jobs[0]  # list_jobs returns newest first
        return _result(
            "success",
            tool,
            f"Job {job['job_id']} status: {job['status']}.",
            data={"job": job},
            summary=f"Job status: {job['status']}.",
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_status failed")
        return _result("failed", tool, f"Status lookup failed: {exc}", reason=str(exc))


def _handle_portfolio_implementation_list(args: dict[str, Any]) -> str:
    """List implementation runs, optionally filtered by project."""
    tool = "portfolio_implementation_list"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        project_ref = args.get("project_ref")
        project_id: str | None = None
        if project_ref:
            from portfolio_manager.implementation_planner import _resolve_project_id

            project_id = _resolve_project_id(conn, root_path, project_ref)

        jobs = list_jobs(conn, project_id=project_id)

        return _result(
            "success",
            tool,
            f"Found {len(jobs)} implementation job(s).",
            data={"jobs": jobs, "count": len(jobs)},
            summary=f"{len(jobs)} job(s) found.",
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_list failed")
        return _result("failed", tool, f"List failed: {exc}", reason=str(exc))


def _handle_portfolio_implementation_explain(args: dict[str, Any]) -> str:
    """Explain an implementation run state and suggest next actions."""
    tool = "portfolio_implementation_explain"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        project_ref = args.get("project_ref")
        issue_number = args.get("issue_number")

        if not project_ref or issue_number is None:
            return _result(
                "blocked",
                tool,
                "project_ref and issue_number are required.",
                reason="missing project_ref or issue_number",
            )

        from portfolio_manager.implementation_planner import _resolve_project_id

        project_id = _resolve_project_id(conn, root_path, project_ref)

        if project_id is None:
            return _result(
                "blocked",
                tool,
                f"Could not resolve project_ref: {project_ref!r}",
                reason=f"unknown project_ref: {project_ref!r}",
            )

        jobs = list_jobs(conn, project_id=project_id, issue_number=int(issue_number))
        if not jobs:
            return _result(
                "blocked",
                tool,
                f"No implementation job found for {project_id} issue #{issue_number}.",
                reason="no job found",
            )

        job = jobs[0]
        status = job["status"]
        failure_reason = job.get("failure_reason")

        explanation = f"Job {job['job_id']} is in state '{status}'."
        suggestion = ""

        if status == "blocked":
            explanation += f" Reason: {failure_reason or 'unknown'}."
            suggestion = "Review the failure reason and retry with a corrected plan."
        elif status == "needs_user":
            explanation += f" Question: {failure_reason or 'needs user input'}."
            suggestion = "Provide the requested input and re-run."
        elif status == "failed":
            explanation += f" Error: {failure_reason or 'unknown'}."
            suggestion = "Check artifacts for error details."
        elif status == "succeeded":
            explanation += " The implementation completed successfully."
            suggestion = "Proceed with review or merge."
        elif status in ("planned", "running"):
            explanation += " The job is still in progress."
            suggestion = "Wait for completion or check status again."

        return _result(
            "success",
            tool,
            explanation,
            data={"job": job, "suggestion": suggestion},
            summary=explanation,
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_explain failed")
        return _result("failed", tool, f"Explain failed: {exc}", reason=str(exc))


# ---------------------------------------------------------------------------
# 13.2 — start / apply_review_fixes
# ---------------------------------------------------------------------------


def _handle_portfolio_implementation_start(args: dict[str, Any]) -> str:
    """Start an implementation run for an issue."""
    tool = "portfolio_implementation_start"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        result = run_initial_implementation(
            conn,
            root_path,
            project_ref=args["project_ref"],
            issue_number=args["issue_number"],
            harness_id=args["harness_id"],
            expected_branch=args.get("expected_branch"),
            base_sha=args.get("base_sha"),
            instructions=args.get("instructions"),
            confirm=bool(args.get("confirm", False)),
        )
        return json.dumps(result)
    except ImplementationLockBusy as exc:
        return _result(
            "blocked",
            tool,
            f"Lock contention: {exc}",
            data={"lock_error": str(exc)},
            summary="Implementation blocked: lock busy.",
            reason=str(exc),
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_start failed")
        return _result("failed", tool, f"Start failed: {exc}", reason=str(exc))


def _handle_portfolio_implementation_apply_review_fixes(args: dict[str, Any]) -> str:
    """Apply approved review fixes to an in-progress implementation."""
    tool = "portfolio_implementation_apply_review_fixes"
    try:
        root_arg = args.get("root")
        root_path, conn = _open_db(root_arg)

        result = run_review_fix(
            conn,
            root_path,
            project_ref=args["project_ref"],
            issue_number=args["issue_number"],
            pr_number=args["pr_number"],
            review_stage_id=args["review_stage_id"],
            review_iteration=args["review_iteration"],
            approved_comment_ids=args["approved_comment_ids"],
            fix_scope=args["fix_scope"],
            harness_id=args["harness_id"],
            expected_branch=args.get("expected_branch"),
            confirm=bool(args.get("confirm", False)),
        )
        return json.dumps(result)
    except ImplementationLockBusy as exc:
        return _result(
            "blocked",
            tool,
            f"Lock contention: {exc}",
            data={"lock_error": str(exc)},
            summary="Review-fix blocked: lock busy.",
            reason=str(exc),
        )
    except Exception as exc:
        logger.exception("portfolio_implementation_apply_review_fixes failed")
        return _result("failed", tool, f"Review-fix failed: {exc}", reason=str(exc))
