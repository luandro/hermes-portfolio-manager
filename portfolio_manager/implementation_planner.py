"""Plan generation for MVP 6 implementation runner.

Pure functions that build an ImplementationPlan without writing to SQLite,
creating artifacts, or running subprocesses. The planner resolves project
references, validates harness IDs, runs preflight checks, and assembles
the proposed command and required checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

from portfolio_manager.config import load_projects_config
from portfolio_manager.harness_config import get_harness
from portfolio_manager.implementation_paths import (
    resolve_source_artifact,
    validate_harness_id,
)
from portfolio_manager.implementation_preflight import (
    PreflightResult,
    preflight_initial_implementation,
    preflight_review_fix,
)
from portfolio_manager.issue_resolver import resolve_project


@dataclass
class ImplementationPlan:
    """Read-only plan for an implementation job."""

    job_type: str
    project_id: str
    issue_number: int
    harness_id: str
    workspace_path: Path | None
    source_artifact_path: Path | None
    expected_branch: str | None
    base_sha: str | None
    proposed_command: list[str]
    required_checks: list[str]
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _resolve_project_id(conn: object, root: Path, project_ref: str) -> str | None:
    """Resolve a project_ref string to a project_id.

    Uses issue_resolver.resolve_project for deterministic fuzzy matching.
    Returns None if unresolvable.
    """
    try:
        config = load_projects_config(root)
    except Exception:
        return None

    result = resolve_project(config, project_ref=project_ref)
    if result.state == "resolved" and result.project_id:
        return result.project_id
    return None


def build_initial_plan(
    conn: sqlite3.Connection,
    root: Path,
    *,
    project_ref: str,
    issue_number: int,
    harness_id: str,
    expected_branch: str | None = None,
) -> ImplementationPlan:
    """Build a read-only plan for an initial_implementation job.

    Steps:
      1. Resolve project_ref to project_id.
      2. Validate harness_id and look up harness config.
      3. Run preflight checks.
      4. Resolve source artifact.
      5. Build and return ImplementationPlan.

    Pure function -- no SQLite writes, no artifact writes, no subprocess.
    """
    root = Path(root)
    blocked_reasons: list[str] = []
    warnings: list[str] = []

    # 1. Resolve project_ref
    project_id = _resolve_project_id(conn, root, project_ref)
    if project_id is None:
        blocked_reasons.append(f"Could not resolve project_ref: {project_ref!r}")

    # 2. Validate harness_id
    harness = None
    try:
        validate_harness_id(harness_id)
    except ValueError as exc:
        blocked_reasons.append(f"Invalid harness_id: {exc}")

    # Look up harness config
    harness_id_valid = not any(r.startswith("Invalid harness_id:") for r in blocked_reasons)
    if harness_id_valid:
        harness = get_harness(root, harness_id)
        if harness is None:
            blocked_reasons.append(f"Unknown harness_id: {harness_id!r}")

    # 3. Run preflight checks (only if project resolved)
    preflight: PreflightResult | None = None
    if project_id is not None:
        preflight = preflight_initial_implementation(
            conn,
            project_id=project_id,
            issue_number=issue_number,
            expected_branch=expected_branch,
            root=root,
        )
        if not preflight.ok:
            blocked_reasons.extend(preflight.reasons)

    # 4. Resolve source artifact (only if project resolved and not already found by preflight)
    source_artifact_path: Path | None = None
    if project_id is not None:
        if preflight and preflight.source_artifact_path:
            source_artifact_path = preflight.source_artifact_path
        else:
            source_artifact_path = resolve_source_artifact(root, conn, project_id, issue_number)

    # Build proposed command from harness config
    proposed_command: list[str] = []
    required_checks: list[str] = []
    if harness is not None:
        proposed_command = list(harness.command)
        required_checks = list(harness.required_checks)

    workspace_path = preflight.worktree_path if preflight else None
    base_sha = preflight.head_sha if preflight else None
    branch = preflight.branch_name if preflight else expected_branch

    return ImplementationPlan(
        job_type="initial_implementation",
        project_id=project_id or "",
        issue_number=issue_number,
        harness_id=harness_id,
        workspace_path=workspace_path,
        source_artifact_path=source_artifact_path,
        expected_branch=branch,
        base_sha=base_sha,
        proposed_command=proposed_command,
        required_checks=required_checks,
        blocked_reasons=blocked_reasons,
        warnings=warnings,
    )


def build_review_fix_plan(
    conn: sqlite3.Connection,
    root: Path,
    *,
    project_ref: str,
    issue_number: int,
    pr_number: int,
    harness_id: str,
    review_stage_id: str,
    review_iteration: int,
    approved_comment_ids: list[str],
    fix_scope: list[str],
    expected_branch: str | None = None,
) -> ImplementationPlan:
    """Build a read-only plan for a review_fix job.

    Extends initial plan with:
      - review_iteration must be > 0.
      - approved_comment_ids must be non-empty.

    Pure function -- no SQLite writes, no artifact writes, no subprocess.
    """
    root = Path(root)
    blocked_reasons: list[str] = []
    warnings: list[str] = []

    # Validate review_iteration
    if review_iteration <= 0:
        blocked_reasons.append(f"review_iteration must be > 0, got {review_iteration}")

    # Validate approved_comment_ids
    if not approved_comment_ids:
        blocked_reasons.append("approved_comment_ids must be non-empty for review_fix")

    # 1. Resolve project_ref
    project_id = _resolve_project_id(conn, root, project_ref)
    if project_id is None:
        blocked_reasons.append(f"Could not resolve project_ref: {project_ref!r}")

    # 2. Validate harness_id
    harness = None
    try:
        validate_harness_id(harness_id)
    except ValueError as exc:
        blocked_reasons.append(f"Invalid harness_id: {exc}")

    # Look up harness config
    harness_id_valid = not any(r.startswith("Invalid harness_id:") for r in blocked_reasons)
    if harness_id_valid:
        harness = get_harness(root, harness_id)
        if harness is None:
            blocked_reasons.append(f"Unknown harness_id: {harness_id!r}")

    # 3. Run preflight checks (only if project resolved)
    preflight: PreflightResult | None = None
    if project_id is not None:
        preflight = preflight_review_fix(
            conn,
            project_id=project_id,
            issue_number=issue_number,
            pr_number=pr_number,
            expected_branch=expected_branch,
            approved_comment_ids=approved_comment_ids,
            fix_scope=fix_scope,
            root=root,
        )
        if not preflight.ok:
            blocked_reasons.extend(preflight.reasons)

    # 4. Resolve source artifact
    source_artifact_path: Path | None = None
    if project_id is not None:
        if preflight and preflight.source_artifact_path:
            source_artifact_path = preflight.source_artifact_path
        else:
            source_artifact_path = resolve_source_artifact(root, conn, project_id, issue_number)

    # Build proposed command from harness config
    proposed_command: list[str] = []
    required_checks: list[str] = []
    if harness is not None:
        proposed_command = list(harness.command)
        required_checks = list(harness.required_checks)

    workspace_path = preflight.worktree_path if preflight else None
    base_sha = preflight.head_sha if preflight else None
    branch = preflight.branch_name if preflight else expected_branch

    return ImplementationPlan(
        job_type="review_fix",
        project_id=project_id or "",
        issue_number=issue_number,
        harness_id=harness_id,
        workspace_path=workspace_path,
        source_artifact_path=source_artifact_path,
        expected_branch=branch,
        base_sha=base_sha,
        proposed_command=proposed_command,
        required_checks=required_checks,
        blocked_reasons=blocked_reasons,
        warnings=warnings,
    )
