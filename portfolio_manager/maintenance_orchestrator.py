"""Maintenance run orchestration — Phase 4, Tasks 4.3 and 4.4."""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.maintenance_due import compute_due_checks
from portfolio_manager.maintenance_models import MaintenanceContext
from portfolio_manager.maintenance_planner import plan_maintenance_run
from portfolio_manager.maintenance_registry import REGISTRY
from portfolio_manager.maintenance_reports import (
    write_findings_json,
    write_maintenance_report,
    write_metadata_json,
)
from portfolio_manager.maintenance_state import (
    finish_run,
    insert_finding,
    start_run,
)

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


def _build_project_config(root: Path, conn: sqlite3.Connection, project_id: str) -> ProjectConfig | None:
    """Build a ProjectConfig from the projects table row."""
    cur = conn.execute(
        "SELECT id, name, repo_url, priority, status, default_branch FROM projects WHERE id=?", (project_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    pid, name, repo_url, priority, status, default_branch = row
    # Parse owner/repo from repo_url
    parts = repo_url.rstrip("/").split("/")
    repo_name = parts[-1].replace(".git", "") if parts else pid
    owner = parts[-2] if len(parts) >= 2 else "unknown"
    return ProjectConfig(
        id=pid,
        name=name,
        repo=repo_url,
        github=GithubRef(owner=owner, repo=repo_name),
        priority=priority,
        status=status,
        default_branch=default_branch or "main",
        local=LocalPaths(base_path=root / "worktrees" / pid, issue_worktree_pattern=""),
    )


def _refresh_github_data(
    root: Path, conn: sqlite3.Connection, config: dict[str, Any], project_filter: list[str] | None = None
) -> None:
    """Attempt GitHub sync using existing helpers. Raises on failure."""
    from portfolio_manager.github_client import check_gh_auth, check_gh_available, sync_project_github
    from portfolio_manager.state import upsert_issue, upsert_project, upsert_pull_request

    if not check_gh_available().available or not check_gh_auth().available:
        raise RuntimeError("GitHub CLI not available or not authenticated")

    # Sync all active projects
    if project_filter:
        placeholders = ",".join("?" for _ in project_filter)
        cur = conn.execute(
            f"SELECT id FROM projects WHERE status IN ('active', 'paused') AND id IN ({placeholders})", project_filter
        )
    else:
        cur = conn.execute("SELECT id FROM projects WHERE status IN ('active', 'paused')")
    project_ids = [row[0] for row in cur.fetchall()]

    for pid in project_ids:
        project = _build_project_config(root, conn, pid)
        if project is None:
            continue
        upsert_project(conn, project)
        result = sync_project_github(project)
        for issue in result.issues:
            upsert_issue(
                conn,
                pid,
                {
                    "number": issue.number,
                    "title": issue.title,
                    "state": "needs_triage",  # default for new rows; upsert_issue preserves existing state
                    "labels_json": json.dumps(list(issue.labels), ensure_ascii=False),
                },
            )
        for pr in result.prs:
            upsert_pull_request(
                conn,
                pid,
                {
                    "number": pr.number,
                    "title": pr.title,
                    "branch_name": pr.head_branch,
                    "base_branch": pr.base_branch,
                    "state": "open",
                    "review_stage": pr.review_stage,
                },
            )


def run_maintenance(
    root: Path,
    conn: sqlite3.Connection,
    config: dict[str, Any],
    project_filter: list[str] | None = None,
    skill_filter: list[str] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute or dry-run a maintenance cycle.

    Steps:
      1. If dry_run, delegate to planner and return.
      2. Recover stale runs.
      3. Optionally refresh GitHub data.
      4. Compute due checks.
      5. For each due check: start_run, execute skill, store findings, finish_run, write report.
      6. Return summary.
    """
    if dry_run:
        return plan_maintenance_run(conn, config, root=root, project_filter=project_filter, skill_filter=skill_filter)

    # Step 2: Recover stale runs
    from portfolio_manager.maintenance_state import recover_stale_runs

    recover_stale_runs(conn)

    # Step 3: Optional GitHub refresh
    warnings: list[str] = []
    refresh_github = config.get("refresh_github", False)
    if refresh_github:
        try:
            _refresh_github_data(root, conn, config, project_filter=project_filter)
        except Exception as exc:
            msg = f"GitHub refresh failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)

    # Step 4: Compute due checks
    due_checks = compute_due_checks(
        conn,
        config=config,
        project_filter=project_filter,
        skill_filter=skill_filter,
    )
    due_items = [c for c in due_checks if c["is_due"]]

    # Step 5: Execute each due check
    runs: list[dict[str, Any]] = []
    errors: list[str] = []
    total_findings = 0

    for check in due_items:
        project_id = check["project_id"]
        skill_id = check["skill_id"]

        project = _build_project_config(root, conn, project_id)
        if project is None:
            errors.append(f"Project {project_id} not found in DB")
            continue

        skills_cfg = config.get("skills", {})
        skill_cfg = skills_cfg.get(skill_id, {})

        ctx = MaintenanceContext(
            root=root,
            conn=conn,
            project=project,
            skill_config=skill_cfg,
            now=datetime.now(UTC),
            refresh_github=refresh_github,
        )

        run_id = start_run(conn, project_id, skill_id)

        try:
            result = REGISTRY.execute(skill_id, ctx)

            # Store findings
            for finding in result.findings:
                insert_finding(
                    conn,
                    run_id,
                    fingerprint=finding.fingerprint,
                    severity=finding.severity,
                    title=finding.title,
                    body=finding.body,
                    source_type=finding.source_type,
                    source_id=finding.source_id,
                    source_url=finding.source_url,
                    metadata=finding.metadata,
                    draftable=finding.draftable,
                )

            total_findings += len(result.findings)

            # Finish run
            run_status = result.status if result.status in ("success", "skipped", "blocked", "failed") else "error"
            finish_run(conn, run_id, run_status, summary=result.summary, reason=result.reason)

            # Write report artifacts
            findings_dicts = [
                {
                    "fingerprint": f.fingerprint,
                    "severity": f.severity,
                    "title": f.title,
                    "body": f.body,
                    "source_type": f.source_type,
                    "source_id": f.source_id,
                    "source_url": f.source_url,
                    "metadata": f.metadata,
                }
                for f in result.findings
            ]
            metadata = {
                "run_id": run_id,
                "project_id": project_id,
                "skill_id": skill_id,
                "status": run_status,
                "summary": result.summary,
            }
            write_maintenance_report(root, run_id, findings_dicts, metadata)
            write_findings_json(root, run_id, findings_dicts)
            write_metadata_json(root, run_id, metadata)

            runs.append(
                {
                    "run_id": run_id,
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": run_status,
                    "findings_count": len(result.findings),
                }
            )

            if result.warnings:
                warnings.extend(result.warnings)

        except Exception as exc:
            error_msg = f"Skill {skill_id} failed for {project_id}: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            with contextlib.suppress(Exception):
                finish_run(conn, run_id, "failed", summary=str(exc), reason="execution_error")
            runs.append(
                {
                    "run_id": run_id,
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": "failed",
                    "findings_count": 0,
                }
            )

    return {
        "runs": runs,
        "findings_count": total_findings,
        "errors": errors,
        "warnings": warnings,
    }
