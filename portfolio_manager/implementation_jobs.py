"""Job orchestration for MVP 6 implementation runner.

Provides ``run_initial_implementation`` and ``run_review_fix`` — the two
orchestrators that execute harness jobs inside prepared issue worktrees.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from portfolio_manager.harness_config import get_harness
from portfolio_manager.harness_runner import run_harness, run_required_check
from portfolio_manager.implementation_artifacts import (
    write_changed_files_json,
    write_checks_json,
    write_commands_json,
    write_commit_json,
    write_error_json,
    write_input_request_json,
    write_plan_md,
    write_preflight_json,
    write_result_json,
    write_scope_check_md,
    write_summary_md,
    write_test_first_evidence_md,
    write_test_quality_md,
)
from portfolio_manager.implementation_changes import collect_changed_files
from portfolio_manager.implementation_commit import make_local_commit
from portfolio_manager.implementation_locks import (
    ImplementationLockBusy,
    with_implementation_lock,
    with_implementation_review_lock,
)
from portfolio_manager.implementation_paths import (
    generate_job_id,
    implementation_artifact_dir,
)
from portfolio_manager.implementation_planner import build_initial_plan, build_review_fix_plan
from portfolio_manager.implementation_scope_guard import check_scope
from portfolio_manager.implementation_state import (
    finish_job,
    insert_job,
    update_job_status,
)
from portfolio_manager.implementation_test_quality import check_test_quality, collect_test_first_evidence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared result helpers
# ---------------------------------------------------------------------------


def _shared_result(
    status: str,
    tool: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
    summary: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "tool": tool,
        "message": message,
        "data": data or {},
        "summary": summary or message,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# 11.2 — initial_implementation orchestrator
# ---------------------------------------------------------------------------


def run_initial_implementation(
    conn: object,
    root: Path | str,
    *,
    project_ref: str,
    issue_number: int,
    harness_id: str,
    expected_branch: str | None = None,
    base_sha: str | None = None,
    instructions: dict[str, Any] | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Run an initial_implementation job in a prepared issue worktree.

    Sequence:
      build_initial_plan -> confirm gate -> insert_job(planned) ->
      with_implementation_lock -> update_job_status(running) ->
      write plan/preflight/commands/input-request ->
      run_harness -> collect_changed_files -> run required_checks ->
      write changed-files.json + checks.json ->
      collect_test_first_evidence -> check_scope -> check_test_quality ->
      if any gate fails: blocked + finish_job
      make_local_commit -> write commit.json + result.json + summary.md ->
      finish_job(succeeded)

    Returns a tool-result dict with status in
    ``{"success", "blocked", "failed", "needs_user"}``.
    """
    import sqlite3

    tool = "portfolio_implementation_start"

    if not isinstance(conn, sqlite3.Connection):
        return _shared_result("failed", tool, "Invalid connection object", reason="Invalid connection object")

    root = Path(root)

    # --- Build plan (read-only, no side effects) ---
    plan = build_initial_plan(
        conn,
        root,
        project_ref=project_ref,
        issue_number=issue_number,
        harness_id=harness_id,
        expected_branch=expected_branch,
    )

    # --- Dry-run gate: if confirm is False, return the plan without mutating ---
    if not confirm:
        return _shared_result(
            "blocked",
            tool,
            "Dry run — no mutations performed. Set confirm=true to execute.",
            data={"plan": _plan_to_dict(plan), "dry_run": True},
            summary="Initial-implementation plan returned (dry run).",
            reason="confirm is false",
        )

    # --- Pre-flight block check ---
    if plan.blocked_reasons:
        return _shared_result(
            "blocked",
            tool,
            "Plan blocked: " + "; ".join(plan.blocked_reasons),
            data={"plan": _plan_to_dict(plan), "blocked_reasons": plan.blocked_reasons},
            summary="Initial-implementation blocked: " + "; ".join(plan.blocked_reasons),
            reason="; ".join(plan.blocked_reasons),
        )

    # --- Real run: generate IDs, acquire lock, then insert job row and execute ---
    job_id = generate_job_id()
    artifact_dir = implementation_artifact_dir(root, plan.project_id, issue_number, job_id)

    try:
        with with_implementation_lock(conn, plan.project_id, issue_number):
            insert_job(
                conn,
                {
                    "job_id": job_id,
                    "job_type": "initial_implementation",
                    "project_id": plan.project_id,
                    "issue_number": issue_number,
                    "source_artifact_path": str(plan.source_artifact_path) if plan.source_artifact_path else None,
                    "status": "planned",
                    "harness_id": harness_id,
                    "artifact_path": str(artifact_dir),
                },
            )
            return _run_initial_impl_inner(
                conn=conn,
                root=root,
                job_id=job_id,
                artifact_dir=artifact_dir,
                plan=plan,
                instructions=instructions,
            )
    except ImplementationLockBusy as exc:
        return _shared_result(
            "blocked",
            tool,
            f"Lock contention: {exc}",
            data={"job_id": job_id, "lock_error": str(exc)},
            summary="Initial-implementation blocked: lock busy.",
            reason=str(exc),
        )
    except Exception as exc:
        logger.exception("initial_implementation job %s failed", job_id)
        try:
            write_error_json(artifact_dir, {"error": str(exc), "job_id": job_id})
            finish_job(
                conn, job_id, status="failed", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=str(exc)
            )
        except Exception:
            logger.exception("failed to write error artifact for job %s", job_id)
        return _shared_result(
            "failed",
            tool,
            f"Initial-implementation failed: {exc}",
            data={"job_id": job_id},
            summary=f"Initial-implementation failed unexpectedly: {exc}",
            reason=str(exc),
        )


def _run_initial_impl_inner(
    *,
    conn: object,
    root: Path,
    job_id: str,
    artifact_dir: Path,
    plan: Any,
    instructions: dict[str, Any] | None,
) -> dict[str, Any]:
    """Inner execution of an initial_implementation job, already holding the lock."""
    import sqlite3

    assert isinstance(conn, sqlite3.Connection)
    tool = "portfolio_implementation_start"

    # Transition to running
    update_job_status(conn, job_id, status="running", started_at=_utcnow())

    # Write plan artifact
    write_plan_md(artifact_dir, _plan_to_dict(plan))

    # Write preflight artifact
    write_preflight_json(
        artifact_dir,
        {
            "ok": not bool(plan.blocked_reasons),
            "reasons": plan.blocked_reasons,
            "workspace_path": str(plan.workspace_path) if plan.workspace_path else None,
            "branch_name": plan.expected_branch,
            "base_sha": plan.base_sha,
        },
    )

    # Write commands artifact
    write_commands_json(artifact_dir, [{"command": plan.proposed_command, "type": "harness"}])

    # Write input-request.json
    input_request = {
        "job_type": "initial_implementation",
        "project_id": plan.project_id,
        "issue_number": plan.issue_number,
        "harness_id": plan.harness_id,
        "source_artifact_path": str(plan.source_artifact_path) if plan.source_artifact_path else None,
    }
    if instructions:
        input_request["instructions"] = instructions
    write_input_request_json(artifact_dir, input_request)

    # Resolve harness config
    harness = get_harness(root, plan.harness_id)
    if harness is None:
        _finish_blocked_impl(conn, job_id, artifact_dir, f"Unknown harness_id: {plan.harness_id!r}")
        return _blocked_impl_result(job_id, f"Unknown harness_id: {plan.harness_id!r}")

    workspace = plan.workspace_path
    if workspace is None:
        _finish_blocked_impl(conn, job_id, artifact_dir, "No workspace path resolved")
        return _blocked_impl_result(job_id, "No workspace path resolved")

    source_artifact = plan.source_artifact_path
    if source_artifact is None:
        _finish_blocked_impl(conn, job_id, artifact_dir, "No source artifact resolved")
        return _blocked_impl_result(job_id, "No source artifact resolved")

    input_request_path = artifact_dir / "input-request.json"

    # --- Run harness ---
    harness_result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=source_artifact,
        instructions=input_request,
        artifact_dir=artifact_dir,
        input_request_path=input_request_path,
        extra_env={"PORTFOLIO_IMPLEMENTATION_JOB_ID": job_id},
    )

    # Gate: non-zero exit or timeout always means failure
    if harness_result.timed_out or harness_result.returncode != 0:
        write_error_json(
            artifact_dir,
            {
                "error": "harness failed",
                "returncode": harness_result.returncode,
                "timed_out": harness_result.timed_out,
                "stderr": harness_result.stderr[:2000],
                "job_id": job_id,
            },
        )
        finish_job(
            conn,
            job_id,
            status="failed",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=(
                "harness timed out" if harness_result.timed_out else f"harness exit code {harness_result.returncode}"
            ),
        )
        return _shared_result(
            "failed",
            tool,
            "Harness failed.",
            data={"job_id": job_id, "returncode": harness_result.returncode},
            reason=(
                "harness timed out" if harness_result.timed_out else f"harness exit code {harness_result.returncode}"
            ),
        )

    # Check harness status — needs_user shortcut
    if harness_result.harness_status == "needs_user":
        needs_user_data = _read_needs_user_from_harness_result(artifact_dir)
        finish_job(
            conn,
            job_id,
            status="needs_user",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=needs_user_data.get("question", "harness returned needs_user"),
        )
        write_result_json(
            artifact_dir,
            {
                "status": "needs_user",
                "job_id": job_id,
                "needs_user": needs_user_data,
            },
        )
        write_summary_md(
            artifact_dir, f"Initial-implementation needs user input: {needs_user_data.get('question', '')}"
        )
        return _shared_result(
            "needs_user",
            tool,
            "Harness requires product judgment.",
            data={"job_id": job_id, "needs_user": needs_user_data},
            summary=f"Initial-implementation needs user: {needs_user_data.get('question', '')}",
        )

    if harness_result.harness_status == "failed":
        write_error_json(
            artifact_dir,
            {
                "error": "harness failed",
                "returncode": harness_result.returncode,
                "stderr": harness_result.stderr[:2000],
                "job_id": job_id,
            },
        )
        finish_job(
            conn,
            job_id,
            status="failed",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=f"harness exit code {harness_result.returncode}",
        )
        return _shared_result(
            "failed",
            tool,
            f"Harness failed with exit code {harness_result.returncode}",
            data={"job_id": job_id, "returncode": harness_result.returncode},
            summary=f"Initial-implementation harness failed (exit {harness_result.returncode}).",
            reason=f"harness exit code {harness_result.returncode}",
        )

    # --- Collect changed files ---
    changed = collect_changed_files(workspace, root=root)
    write_changed_files_json(artifact_dir, changed.statuses)

    # --- Run required checks ---
    check_results: list[dict[str, Any]] = []
    for check_id in plan.required_checks:
        check_config = harness.checks.get(check_id)
        if check_config is None:
            write_error_json(
                artifact_dir,
                {"error": f"required check {check_id!r} not found in harness config", "job_id": job_id},
            )
            finish_job(
                conn,
                job_id,
                status="failed",
                commit_sha=None,
                artifact_path=str(artifact_dir),
                failure_reason=f"required check {check_id!r} not configured",
            )
            return _shared_result(
                "failed",
                tool,
                f"Required check {check_id!r} is not configured in harness.",
                data={"job_id": job_id},
                reason=f"missing required check: {check_id}",
            )
        cr = run_required_check(
            check=check_config,
            workspace=workspace,
            root=root,
            artifact_dir=artifact_dir,
        )
        check_results.append(
            {
                "check_id": check_id,
                "exit_code": cr.returncode,
                "stdout": cr.stdout[:2000],
                "stderr": cr.stderr[:2000],
                "timed_out": cr.timed_out,
                "harness_status": cr.harness_status,
            }
        )
    write_checks_json(artifact_dir, check_results)

    # Check if any required check failed
    failed_checks = [c for c in check_results if c["exit_code"] != 0]
    if failed_checks:
        reasons = [f"check {c['check_id']} failed (exit {c['exit_code']})" for c in failed_checks]
        _finish_blocked_impl(conn, job_id, artifact_dir, "; ".join(reasons))
        return _blocked_impl_result(job_id, "; ".join(reasons))

    # --- Collect test-first evidence ---
    import json as _json

    harness_result_data: dict[str, Any] | None = None
    result_path = artifact_dir / "harness-result.json"
    if result_path.is_file():
        with contextlib.suppress(_json.JSONDecodeError, OSError):
            harness_result_data = _json.loads(result_path.read_text(encoding="utf-8"))

    evidence = collect_test_first_evidence(harness_result_data, check_results)
    write_test_first_evidence_md(
        artifact_dir,
        {
            "job_type": "initial_implementation",
            "has_failing_phase": evidence.has_failing_phase,
            "has_passing_phase": evidence.has_passing_phase,
            "waiver": evidence.waiver,
            "blocked_reason": evidence.blocked_reason,
        },
    )

    # --- Scope guard ---
    scope_check = check_scope(
        changed_files=changed.files,
        spec_scope=[],
        protected_paths=[],
        max_files_changed=harness.max_files_changed,
    )
    write_scope_check_md(
        artifact_dir,
        {
            "ok": scope_check.ok,
            "reasons": scope_check.reasons,
            "changed_files": scope_check.changed_files,
            "protected_violations": scope_check.protected_violations,
            "out_of_scope_files": scope_check.out_of_scope_files,
        },
    )

    if not scope_check.ok:
        _finish_blocked_impl(conn, job_id, artifact_dir, "; ".join(scope_check.reasons))
        return _blocked_impl_result(job_id, "; ".join(scope_check.reasons))

    # --- Test quality ---
    new_test_files = [f for f in changed.files if "test" in f.lower() and f.endswith(".py")]
    test_bodies: dict[str, str] = {}
    for tf in new_test_files:
        tf_path = workspace / tf
        if tf_path.is_file():
            try:
                test_bodies[tf] = tf_path.read_text(encoding="utf-8")
            except OSError:
                test_bodies[tf] = ""
    spec_body = ""
    if source_artifact.is_file():
        try:
            spec_body = source_artifact.read_text(encoding="utf-8")
        except OSError:
            spec_body = ""
    test_quality = check_test_quality(
        changed_files=changed.files,
        new_test_files=new_test_files,
        test_bodies=test_bodies,
        spec_body=spec_body,
        job_type="initial_implementation",
    )
    write_test_quality_md(
        artifact_dir,
        {
            "ok": test_quality.ok,
            "reasons": test_quality.reasons,
            "mode": test_quality.mode,
        },
    )

    if not test_quality.ok:
        _finish_blocked_impl(conn, job_id, artifact_dir, "; ".join(test_quality.reasons))
        return _blocked_impl_result(job_id, "; ".join(test_quality.reasons))

    # --- Make local commit ---
    commit_message = f"feat: initial implementation for issue #{plan.issue_number} [project={plan.project_id}]"
    commit_sha = make_local_commit(
        workspace,
        job_id=job_id,
        issue_number=plan.issue_number,
        message=commit_message,
        author_name="portfolio-manager",
        author_email="portfolio-manager@hermes",
    )

    if commit_sha is None:
        # No changes to commit — treat as skipped, not failure
        finish_job(
            conn, job_id, status="succeeded", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=None
        )
        write_result_json(artifact_dir, {"status": "succeeded", "job_id": job_id, "commit_sha": None})
        write_summary_md(artifact_dir, "Initial-implementation completed with no changes to commit.")
        return _shared_result(
            "success",
            tool,
            "Initial-implementation completed (no changes to commit).",
            data={"job_id": job_id, "commit_sha": None},
            summary="Initial-implementation completed — no changes needed.",
        )

    # Write commit artifact
    write_commit_json(
        artifact_dir,
        {
            "sha": commit_sha,
            "message": commit_message,
            "job_id": job_id,
        },
    )

    # --- Finish succeeded ---
    finish_job(
        conn, job_id, status="succeeded", commit_sha=commit_sha, artifact_path=str(artifact_dir), failure_reason=None
    )
    write_result_json(
        artifact_dir,
        {
            "status": "succeeded",
            "job_id": job_id,
            "commit_sha": commit_sha,
        },
    )
    write_summary_md(
        artifact_dir,
        (
            f"Initial-implementation completed for issue #{plan.issue_number} "
            f"(project={plan.project_id}). Commit: {commit_sha[:12]}."
        ),
    )

    return _shared_result(
        "success",
        tool,
        "Initial-implementation completed successfully.",
        data={"job_id": job_id, "commit_sha": commit_sha},
        summary=f"Initial-implementation completed. Commit: {commit_sha[:12]}.",
    )


def _blocked_impl_result(job_id: str, reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "tool": "portfolio_implementation_start",
        "message": f"Initial-implementation blocked: {reason}",
        "data": {"job_id": job_id, "blocked_reason": reason},
        "summary": f"Initial-implementation blocked: {reason}",
        "reason": reason,
    }


def _finish_blocked_impl(conn: object, job_id: str, artifact_dir: Path, reason: str) -> None:
    import sqlite3

    assert isinstance(conn, sqlite3.Connection)
    write_result_json(artifact_dir, {"status": "blocked", "job_id": job_id, "reason": reason})
    finish_job(conn, job_id, status="blocked", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=reason)


# ---------------------------------------------------------------------------
# 12.2 — review_fix orchestrator
# ---------------------------------------------------------------------------


def run_review_fix(
    conn: object,
    root: Path | str,
    *,
    project_ref: str,
    issue_number: int,
    pr_number: int,
    review_stage_id: str,
    review_iteration: int,
    approved_comment_ids: list[str],
    fix_scope: list[str],
    harness_id: str,
    expected_branch: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Run a review-fix job for approved review comments.

    Differences from ``run_initial_implementation``:
    - Uses ``build_review_fix_plan`` instead of ``build_initial_plan``.
    - Uses ``with_implementation_review_lock`` scoped to ``pr_number``.
    - ``job_type='review_fix'``.
    - Scope check uses ``fix_scope`` instead of full spec scope.
    - Test quality may pass without new tests if ``fix_scope`` is doc-only.
    - Artifacts include ``input-request.json`` with approved comment IDs and
      review stage/iteration.
    - Commit message references comment IDs.
    - MVP 6 does NOT decide pass/fail for the review stage.

    Returns a tool-result dict with status in
    ``{"success", "blocked", "failed", "needs_user"}``.
    """
    import sqlite3

    if not isinstance(conn, sqlite3.Connection):
        return {
            "status": "failed",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Invalid connection object",
            "data": {},
            "summary": "Review-fix failed: invalid connection.",
            "reason": "Invalid connection object",
        }

    root = Path(root)

    # --- Build plan (read-only, no side effects) ---
    plan = build_review_fix_plan(
        conn,
        root,
        project_ref=project_ref,
        issue_number=issue_number,
        pr_number=pr_number,
        harness_id=harness_id,
        review_stage_id=review_stage_id,
        review_iteration=review_iteration,
        approved_comment_ids=approved_comment_ids,
        fix_scope=fix_scope,
        expected_branch=expected_branch,
    )

    # --- Dry-run gate: if confirm is False, return the plan without mutating ---
    if not confirm:
        return {
            "status": "blocked",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Dry run — no mutations performed. Set confirm=true to execute.",
            "data": {
                "plan": _plan_to_dict(plan),
                "dry_run": True,
            },
            "summary": "Review-fix plan returned (dry run).",
            "reason": "confirm is false",
        }

    # --- Pre-flight block check ---
    if plan.blocked_reasons:
        return {
            "status": "blocked",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Plan blocked: " + "; ".join(plan.blocked_reasons),
            "data": {
                "plan": _plan_to_dict(plan),
                "blocked_reasons": plan.blocked_reasons,
            },
            "summary": "Review-fix blocked: " + "; ".join(plan.blocked_reasons),
            "reason": "; ".join(plan.blocked_reasons),
        }

    # --- Real run: generate IDs, acquire lock, then insert job row and execute ---
    job_id = generate_job_id()
    artifact_dir = implementation_artifact_dir(root, plan.project_id, issue_number, job_id)

    try:
        with with_implementation_review_lock(conn, plan.project_id, pr_number):
            insert_job(
                conn,
                {
                    "job_id": job_id,
                    "job_type": "review_fix",
                    "project_id": plan.project_id,
                    "issue_number": issue_number,
                    "pr_number": pr_number,
                    "review_stage_id": review_stage_id,
                    "source_artifact_path": str(plan.source_artifact_path) if plan.source_artifact_path else None,
                    "status": "planned",
                    "harness_id": harness_id,
                    "artifact_path": str(artifact_dir),
                },
            )
            return _run_review_fix_inner(
                conn=conn,
                root=root,
                job_id=job_id,
                artifact_dir=artifact_dir,
                plan=plan,
                pr_number=pr_number,
                review_stage_id=review_stage_id,
                review_iteration=review_iteration,
                approved_comment_ids=approved_comment_ids,
                fix_scope=fix_scope,
            )
    except ImplementationLockBusy as exc:
        return {
            "status": "blocked",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": f"Lock contention: {exc}",
            "data": {"job_id": job_id, "lock_error": str(exc)},
            "summary": "Review-fix blocked: lock busy.",
            "reason": str(exc),
        }
    except Exception as exc:
        logger.exception("review_fix job %s failed", job_id)
        try:
            write_error_json(artifact_dir, {"error": str(exc), "job_id": job_id})
            finish_job(
                conn, job_id, status="failed", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=str(exc)
            )
        except Exception:
            logger.exception("failed to write error artifact for job %s", job_id)
        return {
            "status": "failed",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": f"Review-fix failed: {exc}",
            "data": {"job_id": job_id},
            "summary": f"Review-fix failed unexpectedly: {exc}",
            "reason": str(exc),
        }


def _run_review_fix_inner(
    *,
    conn: object,
    root: Path,
    job_id: str,
    artifact_dir: Path,
    plan: Any,
    pr_number: int,
    review_stage_id: str,
    review_iteration: int,
    approved_comment_ids: list[str],
    fix_scope: list[str],
) -> dict[str, Any]:
    """Inner execution of a review-fix job, already holding the lock."""
    import sqlite3

    assert isinstance(conn, sqlite3.Connection)

    # Transition to running
    update_job_status(conn, job_id, status="running", started_at=_utcnow())

    # Write plan artifact
    write_plan_md(artifact_dir, _plan_to_dict(plan))

    # Write preflight artifact
    write_preflight_json(
        artifact_dir,
        {
            "ok": not bool(plan.blocked_reasons),
            "reasons": plan.blocked_reasons,
            "workspace_path": str(plan.workspace_path) if plan.workspace_path else None,
            "branch_name": plan.expected_branch,
            "base_sha": plan.base_sha,
        },
    )

    # Write commands artifact
    write_commands_json(artifact_dir, [{"command": plan.proposed_command, "type": "harness"}])

    # Write input-request.json with review context
    input_request = {
        "job_type": "review_fix",
        "project_id": plan.project_id,
        "issue_number": plan.issue_number,
        "pr_number": pr_number,
        "review_stage_id": review_stage_id,
        "review_iteration": review_iteration,
        "approved_comment_ids": approved_comment_ids,
        "fix_scope": fix_scope,
        "source_artifact_path": str(plan.source_artifact_path) if plan.source_artifact_path else None,
    }
    write_input_request_json(artifact_dir, input_request)

    # Resolve harness config
    harness = get_harness(root, plan.harness_id)
    if harness is None:
        _finish_blocked(conn, job_id, artifact_dir, f"Unknown harness_id: {plan.harness_id!r}")
        return _blocked_result(job_id, f"Unknown harness_id: {plan.harness_id!r}")

    workspace = plan.workspace_path
    if workspace is None:
        _finish_blocked(conn, job_id, artifact_dir, "No workspace path resolved")
        return _blocked_result(job_id, "No workspace path resolved")

    source_artifact = plan.source_artifact_path
    if source_artifact is None:
        _finish_blocked(conn, job_id, artifact_dir, "No source artifact resolved")
        return _blocked_result(job_id, "No source artifact resolved")

    input_request_path = artifact_dir / "input-request.json"

    # --- Run harness ---
    harness_result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=source_artifact,
        instructions=input_request,
        artifact_dir=artifact_dir,
        input_request_path=input_request_path,
        extra_env={"PORTFOLIO_IMPLEMENTATION_JOB_ID": job_id},
    )

    # Gate: non-zero exit or timeout always means failure
    if harness_result.timed_out or harness_result.returncode != 0:
        write_error_json(
            artifact_dir,
            {
                "error": "harness failed",
                "returncode": harness_result.returncode,
                "timed_out": harness_result.timed_out,
                "stderr": harness_result.stderr[:2000],
                "job_id": job_id,
            },
        )
        finish_job(
            conn,
            job_id,
            status="failed",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=(
                "harness timed out" if harness_result.timed_out else f"harness exit code {harness_result.returncode}"
            ),
        )
        return {
            "status": "failed",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Harness failed.",
            "data": {"job_id": job_id, "returncode": harness_result.returncode},
            "summary": (
                "harness timed out"
                if harness_result.timed_out
                else f"Review-fix harness failed (exit {harness_result.returncode})."
            ),
            "reason": (
                "harness timed out" if harness_result.timed_out else f"harness exit code {harness_result.returncode}"
            ),
        }

    # Check harness status — needs_user shortcut
    if harness_result.harness_status == "needs_user":
        needs_user_data = _read_needs_user_from_harness_result(artifact_dir)
        finish_job(
            conn,
            job_id,
            status="needs_user",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=needs_user_data.get("question", "harness returned needs_user"),
        )
        write_result_json(
            artifact_dir,
            {
                "status": "needs_user",
                "job_id": job_id,
                "needs_user": needs_user_data,
            },
        )
        write_summary_md(artifact_dir, f"Review-fix needs user input: {needs_user_data.get('question', '')}")
        return {
            "status": "needs_user",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Harness requires product judgment.",
            "data": {"job_id": job_id, "needs_user": needs_user_data},
            "summary": f"Review-fix needs user: {needs_user_data.get('question', '')}",
            "reason": None,
        }

    if harness_result.harness_status == "failed":
        write_error_json(
            artifact_dir,
            {
                "error": "harness failed",
                "returncode": harness_result.returncode,
                "stderr": harness_result.stderr[:2000],
                "job_id": job_id,
            },
        )
        finish_job(
            conn,
            job_id,
            status="failed",
            commit_sha=None,
            artifact_path=str(artifact_dir),
            failure_reason=f"harness exit code {harness_result.returncode}",
        )
        return {
            "status": "failed",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": f"Harness failed with exit code {harness_result.returncode}",
            "data": {"job_id": job_id, "returncode": harness_result.returncode},
            "summary": f"Review-fix harness failed (exit {harness_result.returncode}).",
            "reason": f"harness exit code {harness_result.returncode}",
        }

    # --- Collect changed files ---
    changed = collect_changed_files(workspace, root=root)
    write_changed_files_json(artifact_dir, changed.statuses)

    # --- Run required checks ---
    check_results: list[dict[str, Any]] = []
    for check_id in plan.required_checks:
        check_config = harness.checks.get(check_id)
        if check_config is None:
            write_error_json(
                artifact_dir,
                {"error": f"required check {check_id!r} not found in harness config", "job_id": job_id},
            )
            finish_job(
                conn,
                job_id,
                status="failed",
                commit_sha=None,
                artifact_path=str(artifact_dir),
                failure_reason=f"required check {check_id!r} not configured",
            )
            return {
                "status": "failed",
                "tool": "portfolio_implementation_apply_review_fixes",
                "message": f"Required check {check_id!r} is not configured in harness.",
                "data": {"job_id": job_id},
                "summary": f"Missing required check: {check_id}",
                "reason": f"missing required check: {check_id}",
            }
        cr = run_required_check(
            check=check_config,
            workspace=workspace,
            root=root,
            artifact_dir=artifact_dir,
        )
        check_results.append(
            {
                "check_id": check_id,
                "exit_code": cr.returncode,
                "stdout": cr.stdout[:2000],
                "stderr": cr.stderr[:2000],
                "timed_out": cr.timed_out,
                "harness_status": cr.harness_status,
            }
        )
    write_checks_json(artifact_dir, check_results)

    # Check if any required check failed
    failed_checks = [c for c in check_results if c["exit_code"] != 0]
    if failed_checks:
        reasons = [f"check {c['check_id']} failed (exit {c['exit_code']})" for c in failed_checks]
        _finish_blocked(conn, job_id, artifact_dir, "; ".join(reasons))
        return _blocked_result(job_id, "; ".join(reasons))

    # --- Scope guard: use fix_scope instead of full spec scope ---
    scope_check = check_scope(
        changed_files=changed.files,
        spec_scope=[],  # review_fix uses fix_scope, not spec scope
        protected_paths=[],
        max_files_changed=harness.max_files_changed,
        fix_scope=fix_scope,
    )
    write_scope_check_md(
        artifact_dir,
        {
            "ok": scope_check.ok,
            "reasons": scope_check.reasons,
            "changed_files": scope_check.changed_files,
            "out_of_scope_files": scope_check.out_of_scope_files,
            "fix_scope": fix_scope,
        },
    )

    if not scope_check.ok:
        _finish_blocked(conn, job_id, artifact_dir, "; ".join(scope_check.reasons))
        return _blocked_result(job_id, "; ".join(scope_check.reasons))

    # --- Test quality: may pass without new tests for doc-only fix_scope ---
    new_test_files = [f for f in changed.files if "test" in f.lower() and f.endswith(".py")]
    test_bodies: dict[str, str] = {}
    for tf in new_test_files:
        tf_path = workspace / tf
        if tf_path.is_file():
            try:
                test_bodies[tf] = tf_path.read_text(encoding="utf-8")
            except OSError:
                test_bodies[tf] = ""
    spec_body = ""
    if source_artifact.is_file():
        try:
            spec_body = source_artifact.read_text(encoding="utf-8")
        except OSError:
            spec_body = ""
    test_quality = check_test_quality(
        changed_files=changed.files,
        new_test_files=new_test_files,
        test_bodies=test_bodies,
        spec_body=spec_body,
        job_type="review_fix",
        fix_scope=fix_scope,
    )
    write_test_quality_md(
        artifact_dir,
        {
            "ok": test_quality.ok,
            "reasons": test_quality.reasons,
            "mode": test_quality.mode,
        },
    )

    if not test_quality.ok:
        _finish_blocked(conn, job_id, artifact_dir, "; ".join(test_quality.reasons))
        return _blocked_result(job_id, "; ".join(test_quality.reasons))

    # --- Write test-first evidence ---
    write_test_first_evidence_md(
        artifact_dir,
        {
            "job_type": "review_fix",
            "mode": test_quality.mode,
            "test_quality_ok": test_quality.ok,
        },
    )

    # --- Make local commit ---
    comment_ids_str = ",".join(approved_comment_ids)
    commit_message = (
        f"fix(review): address review feedback for PR #{pr_number} "
        f"[stage={review_stage_id}, iter={review_iteration}, "
        f"comments={comment_ids_str}]"
    )
    commit_sha = make_local_commit(
        workspace,
        job_id=job_id,
        issue_number=plan.issue_number,
        message=commit_message,
        author_name="portfolio-manager",
        author_email="portfolio-manager@hermes",
    )

    if commit_sha is None:
        # No changes to commit — treat as skipped, not failure
        finish_job(
            conn, job_id, status="succeeded", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=None
        )
        write_result_json(artifact_dir, {"status": "succeeded", "job_id": job_id, "commit_sha": None})
        write_summary_md(artifact_dir, "Review-fix completed with no changes to commit.")
        return {
            "status": "success",
            "tool": "portfolio_implementation_apply_review_fixes",
            "message": "Review-fix completed (no changes to commit).",
            "data": {"job_id": job_id, "commit_sha": None},
            "summary": "Review-fix completed — no changes needed.",
            "reason": None,
        }

    # Write commit artifact
    write_commit_json(
        artifact_dir,
        {
            "sha": commit_sha,
            "message": commit_message,
            "job_id": job_id,
        },
    )

    # --- Finish succeeded ---
    finish_job(
        conn, job_id, status="succeeded", commit_sha=commit_sha, artifact_path=str(artifact_dir), failure_reason=None
    )
    write_result_json(
        artifact_dir,
        {
            "status": "succeeded",
            "job_id": job_id,
            "commit_sha": commit_sha,
        },
    )
    write_summary_md(
        artifact_dir,
        (
            f"Review-fix applied for PR #{pr_number} "
            f"(stage={review_stage_id}, iter={review_iteration}, "
            f"{len(approved_comment_ids)} comments). "
            f"Commit: {commit_sha[:12]}."
        ),
    )

    return {
        "status": "success",
        "tool": "portfolio_implementation_apply_review_fixes",
        "message": "Review-fix completed successfully.",
        "data": {
            "job_id": job_id,
            "commit_sha": commit_sha,
        },
        "summary": (f"Review-fix applied for PR #{pr_number}. Commit: {commit_sha[:12]}."),
        "reason": None,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _plan_to_dict(plan: Any) -> dict[str, Any]:
    return {
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


def _blocked_result(job_id: str, reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "tool": "portfolio_implementation_apply_review_fixes",
        "message": f"Review-fix blocked: {reason}",
        "data": {"job_id": job_id, "blocked_reason": reason},
        "summary": f"Review-fix blocked: {reason}",
        "reason": reason,
    }


def _finish_blocked(conn: object, job_id: str, artifact_dir: Path, reason: str) -> None:
    import sqlite3

    assert isinstance(conn, sqlite3.Connection)
    write_result_json(artifact_dir, {"status": "blocked", "job_id": job_id, "reason": reason})
    finish_job(conn, job_id, status="blocked", commit_sha=None, artifact_path=str(artifact_dir), failure_reason=reason)


def _read_needs_user_from_harness_result(artifact_dir: Path) -> dict[str, Any]:
    """Read the needs_user field from harness-result.json if present."""
    import json

    result_path = artifact_dir / "harness-result.json"
    if result_path.is_file():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            needs_user = data.get("needs_user", {})
            if isinstance(needs_user, dict):
                return dict(needs_user)
        except (json.JSONDecodeError, OSError):
            pass
    return {}
