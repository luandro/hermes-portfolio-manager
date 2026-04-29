"""Maintenance run orchestration — Phase 4, Tasks 4.3 and 4.4."""

from __future__ import annotations

import contextlib
import copy
import json
import logging
import re
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
    finish_maintenance_run,
    mark_resolved_missing_findings,
    start_maintenance_run,
    upsert_maintenance_finding,
)
from portfolio_manager.state import acquire_lock, release_lock

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)
RUN_LOCK_NAME = "maintenance:run"
RUN_LOCK_OWNER = "maintenance-run"
RUN_LOCK_TTL_SECONDS = 30 * 60
PROJECT_SKILL_LOCK_OWNER = "maintenance-project-skill"
PROJECT_SKILL_LOCK_TTL_SECONDS = 10 * 60


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _effective_skill_config(config: dict[str, Any], project_id: str, skill_id: str) -> dict[str, Any]:
    skill_cfg: dict[str, Any] = {}
    defaults = config.get("defaults", {})
    if isinstance(defaults, dict):
        skill_cfg = _deep_merge(skill_cfg, defaults)
    skills_cfg = config.get("skills", {})
    if isinstance(skills_cfg, dict) and isinstance(skills_cfg.get(skill_id), dict):
        skill_cfg = _deep_merge(skill_cfg, skills_cfg[skill_id])
    project_skill_cfg = (
        config.get("projects", {}).get(project_id, {}).get("skills", {}).get(skill_id, {})
        if isinstance(config.get("projects"), dict)
        else {}
    )
    if isinstance(project_skill_cfg, dict):
        skill_cfg = _deep_merge(skill_cfg, project_skill_cfg)
    return skill_cfg


def _project_skill_lock_name(project_id: str, skill_id: str) -> str:
    return f"maintenance:project:{project_id}:skill:{skill_id}"


def _build_project_config(root: Path, conn: sqlite3.Connection, project_id: str) -> ProjectConfig | None:
    """Build a ProjectConfig from the projects table row."""
    cur = conn.execute(
        "SELECT id, name, repo_url, priority, status, default_branch FROM projects WHERE id=?", (project_id,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    pid, name, repo_url, priority, status, default_branch = row
    # Parse owner/repo from repo_url (handles both HTTPS and SSH URLs)
    cleaned = repo_url.rstrip("/")
    m = re.search(r"(?:github\.com[:/])(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$", cleaned)
    if m:
        owner = m.group("owner")
        repo_name = m.group("repo")
    else:
        parts = cleaned.split("/")
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
    if project_filter is not None:
        if not project_filter:
            return  # empty filter = no projects to refresh
        placeholders = ",".join("?" for _ in project_filter)
        cur = conn.execute(
            f"SELECT id FROM projects WHERE status IN ('active', 'paused') AND id IN ({placeholders})",  # nosec B608
            project_filter,
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
    """Execute or dry-run a maintenance cycle with the required run lock."""
    if dry_run:
        return _run_maintenance_unlocked(
            root,
            conn,
            config,
            project_filter=project_filter,
            skill_filter=skill_filter,
            dry_run=dry_run,
        )

    lock = acquire_lock(conn, RUN_LOCK_NAME, RUN_LOCK_OWNER, RUN_LOCK_TTL_SECONDS)
    if not lock.acquired:
        return {
            "status": "blocked",
            "reason": "lock_held",
            "message": "Maintenance run is locked by another operation",
            "runs": [],
            "findings_count": 0,
            "errors": [],
            "warnings": [lock.reason] if lock.reason else [],
        }

    try:
        return _run_maintenance_unlocked(
            root,
            conn,
            config,
            project_filter=project_filter,
            skill_filter=skill_filter,
            dry_run=dry_run,
        )
    finally:
        release_lock(conn, RUN_LOCK_NAME, RUN_LOCK_OWNER)


def _run_maintenance_unlocked(
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

    # Step 2b: Repair draft references from crash recovery
    from portfolio_manager.maintenance_drafts import repair_draft_references

    try:
        repairs = repair_draft_references(root, conn)
        if repairs:
            logger.info("Repaired %d draft reference(s) from crash recovery", repairs)
    except Exception as exc:
        logger.warning("Draft repair failed (non-fatal): %s", exc)

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

        lock_name = _project_skill_lock_name(project_id, skill_id)
        project_lock = acquire_lock(conn, lock_name, PROJECT_SKILL_LOCK_OWNER, PROJECT_SKILL_LOCK_TTL_SECONDS)
        if not project_lock.acquired:
            _skip_run_id = start_maintenance_run(
                conn,
                {
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": "running",
                    "due": check.get("is_due", True),
                    "dry_run": dry_run,
                    "refresh_github": refresh_github,
                },
            )
            finish_maintenance_run(
                conn,
                _skip_run_id,
                "skipped",
                summary="Skipped because maintenance lock is held",
                error="lock_held",
            )
            runs.append(
                {
                    "run_id": _skip_run_id,
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": "skipped",
                    "findings_count": 0,
                }
            )
            continue

        run_id = None
        try:
            skill_cfg = _effective_skill_config(config, project_id, skill_id)

            ctx = MaintenanceContext(
                root=root,
                conn=conn,
                project=project,
                skill_config=skill_cfg,
                now=datetime.now(UTC),
                refresh_github=refresh_github,
            )

            run_id = start_maintenance_run(
                conn,
                {
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": "running",
                    "due": check.get("is_due", True),
                    "dry_run": dry_run,
                    "refresh_github": refresh_github,
                },
            )
            result = REGISTRY.execute(skill_id, ctx)

            # Store findings
            for finding in result.findings:
                upsert_maintenance_finding(
                    conn,
                    {
                        "fingerprint": finding.fingerprint,
                        "project_id": project_id,
                        "skill_id": skill_id,
                        "severity": finding.severity,
                        "title": finding.title,
                        "body": finding.body,
                        "source_type": finding.source_type,
                        "source_id": finding.source_id,
                        "source_url": finding.source_url,
                        "metadata": {**finding.metadata, "draftable": finding.draftable},
                        "run_id": run_id,
                    },
                )
            total_findings += len(result.findings)

            # Finish run
            run_status = result.status if result.status in ("success", "skipped", "blocked", "failed") else "failed"
            if run_status == "success":
                mark_resolved_missing_findings(
                    conn,
                    project_id,
                    skill_id,
                    {finding.fingerprint for finding in result.findings},
                    datetime.now(UTC).isoformat(),
                )
            finish_maintenance_run(conn, run_id, run_status, summary=result.summary, error=result.reason)

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
            conn.execute(
                "UPDATE maintenance_runs SET finding_count=?, report_path=? WHERE id=?",
                (len(result.findings), str(root / "artifacts" / "maintenance" / run_id / "report.md"), run_id),
            )
            conn.commit()

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
                if run_id is not None:
                    finish_maintenance_run(conn, run_id, "failed", summary=str(exc), error="execution_error")
            runs.append(
                {
                    "run_id": run_id,
                    "project_id": project_id,
                    "skill_id": skill_id,
                    "status": "failed",
                    "findings_count": 0,
                }
            )
        finally:
            release_lock(conn, lock_name, PROJECT_SKILL_LOCK_OWNER)

    # Step 5b: Create issue drafts if configured
    if config.get("create_issue_drafts", False) and runs:
        try:
            from portfolio_manager.maintenance_drafts import (
                create_maintenance_drafts,
                plan_maintenance_issue_drafts,
            )

            # Collect findings by (project_id, skill_id, run_id) for draft planning
            findings_map: dict[tuple[str, str, str], Any] = {}
            for run_info in runs:
                if run_info.get("status") != "success" or run_info.get("findings_count", 0) == 0:
                    continue
                skill_cfg = _effective_skill_config(config, run_info["project_id"], run_info["skill_id"])
                if not skill_cfg.get("create_issue_drafts", config.get("create_issue_drafts", False)):
                    continue
                # Fetch findings for this run
                cur = conn.execute(
                    "SELECT fingerprint, severity, title, body, source_type, source_id, source_url, metadata_json "
                    "FROM maintenance_findings WHERE run_id=?",
                    (run_info["run_id"],),
                )
                from portfolio_manager.maintenance_models import MaintenanceFinding, MaintenanceSkillResult

                run_findings = []
                for frow in cur.fetchall():
                    meta = frow[7]
                    if isinstance(meta, str):
                        try:
                            import json as _json

                            meta = _json.loads(meta)
                        except (ValueError, TypeError):
                            meta = {}
                    run_findings.append(
                        MaintenanceFinding(
                            fingerprint=frow[0],
                            severity=frow[1],
                            title=frow[2],
                            body=frow[3] or "",
                            source_type=frow[4] or "",
                            source_id=frow[5] or "",
                            source_url=frow[6] or "",
                            metadata=meta or {},
                            draftable=meta.get("draftable", True),
                        )
                    )
                if run_findings:
                    key = (run_info["project_id"], run_info["skill_id"], run_info["run_id"])
                    findings_map[key] = MaintenanceSkillResult(
                        skill_id=run_info["skill_id"],
                        project_id=run_info["project_id"],
                        status="success",
                        findings=run_findings,
                        summary="",
                    )

            if findings_map:
                draft_plans = plan_maintenance_issue_drafts(findings_map, config, conn=conn)
                if draft_plans:
                    draft_results = create_maintenance_drafts(root, conn, draft_plans, config)
                    for dr in draft_results:
                        if "warning" in dr:
                            warnings.append(dr["warning"])
                    draft_counts: dict[str, int] = {}
                    for dr in draft_results:
                        if dr.get("draft_id") and dr.get("run_id"):
                            draft_counts[dr["run_id"]] = draft_counts.get(dr["run_id"], 0) + 1
                    if draft_counts:
                        for run_id, draft_count in draft_counts.items():
                            conn.execute(
                                "UPDATE maintenance_runs SET draft_count=draft_count + ? WHERE id=?",
                                (draft_count, run_id),
                            )
                        conn.commit()
        except Exception as exc:
            msg = f"Draft creation failed: {exc}"
            logger.warning(msg)
            warnings.append(msg)

    return {
        "runs": runs,
        "findings_count": total_findings,
        "errors": errors,
        "warnings": warnings,
    }
