"""Tool handlers for MVP 4 maintenance tools.

Each handler delegates to existing maintenance modules and returns a JSON string
via the shared _result/_blocked/_failed helpers from tools.py.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import portfolio_manager.skills.builtin  # noqa: F401 — triggers register_all()
from portfolio_manager.config import resolve_root
from portfolio_manager.maintenance_config import (
    disable_skill,
    enable_skill,
    get_effective_config,
    get_skill_config,
    load_config,
)
from portfolio_manager.maintenance_due import compute_due_checks
from portfolio_manager.maintenance_orchestrator import run_maintenance
from portfolio_manager.maintenance_registry import get_registry
from portfolio_manager.maintenance_reports import load_latest_report, load_report
from portfolio_manager.state import acquire_lock, init_state, open_state, release_lock
from portfolio_manager.tools import _blocked, _failed, _result

logger = logging.getLogger(__name__)
CONFIG_LOCK_NAME = "maintenance:config"
CONFIG_LOCK_OWNER = "maintenance-tool"
CONFIG_LOCK_TTL_SECONDS = 60


def _parse_csv_filter(value: str | None) -> list[str] | None:
    """Parse a comma-separated filter string into a list, or None if empty."""
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()] or None


def _parse_bool(value: Any, default: bool = False) -> bool:
    """Parse boolean-like CLI inputs."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return bool(value)


def _ensure_dirs(root: Any) -> None:
    """Create state/, artifacts/ dirs if missing."""
    from pathlib import Path

    root = Path(root)
    for d in ("state", "worktrees", "logs", "artifacts", "backups"):
        (root / d).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# portfolio_maintenance_skill_list
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_skill_list(args: dict[str, Any], **kwargs: Any) -> str:
    """List all registered maintenance skills with enabled/disabled status."""
    tool = "portfolio_maintenance_skill_list"
    root = resolve_root(args.get("root"))

    registry = get_registry()
    specs = registry.list_specs()
    config = load_config(root)
    skills_cfg = config.get("skills", {})

    skills = []
    for spec in specs:
        skill_cfg = skills_cfg.get(spec.id, {})
        effective_enabled = skill_cfg.get("enabled", spec.default_enabled)
        skills.append(
            {
                "id": spec.id,
                "name": spec.name,
                "description": spec.description,
                "default_interval_hours": spec.default_interval_hours,
                "default_enabled": spec.default_enabled,
                "enabled": effective_enabled,
                "interval_hours": skill_cfg.get("interval_hours", spec.default_interval_hours),
            }
        )

    return _result(
        status="success",
        tool=tool,
        message=f"Found {len(skills)} maintenance skills.",
        data={"skills": skills, "count": len(skills)},
        summary=f"{len(skills)} maintenance skills registered.",
    )


# ---------------------------------------------------------------------------
# portfolio_maintenance_skill_explain
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_skill_explain(args: dict[str, Any], **kwargs: Any) -> str:
    """Show skill spec and effective config for a specific skill."""
    tool = "portfolio_maintenance_skill_explain"
    root = resolve_root(args.get("root"))

    skill_id = args.get("skill_id", "")
    if not skill_id:
        return _blocked(tool, "skill_id is required")

    registry = get_registry()
    spec = registry.get_spec(skill_id)
    if spec is None:
        return _blocked(tool, f"Unknown skill: {skill_id}", reason="skill_not_found")

    project_id = args.get("project_id")
    try:
        effective_config = (
            get_effective_config(root, skill_id, project_id=project_id)
            if project_id
            else get_skill_config(root, skill_id)
        )
    except ValueError as exc:
        return _blocked(tool, str(exc))

    return _result(
        status="success",
        tool=tool,
        message=f"Skill explanation for {skill_id}",
        data={
            "spec": {
                "id": spec.id,
                "name": spec.name,
                "description": spec.description,
                "default_interval_hours": spec.default_interval_hours,
                "default_enabled": spec.default_enabled,
                "supports_issue_drafts": spec.supports_issue_drafts,
                "required_state": spec.required_state,
                "config_schema": spec.config_schema,
            },
            "effective_config": effective_config,
        },
        summary=f"Skill: {spec.name} ({spec.id}). Enabled: {effective_config.get('enabled', spec.default_enabled)}.",
    )


# ---------------------------------------------------------------------------
# portfolio_maintenance_skill_enable
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_skill_enable(args: dict[str, Any], **kwargs: Any) -> str:
    """Enable a maintenance skill in config."""
    tool = "portfolio_maintenance_skill_enable"
    root = resolve_root(args.get("root"))

    skill_id = args.get("skill_id", "")
    if not skill_id:
        return _blocked(tool, "skill_id is required")
    if not re.match(r"^[a-z][a-z0-9_]{2,63}$", skill_id):
        return _blocked(tool, "invalid skill_id: must match ^[a-z][a-z0-9_]{2,63}$")

    interval_hours = args.get("interval_hours")
    if interval_hours is not None:
        try:
            interval_hours = int(interval_hours)
        except (TypeError, ValueError):
            return _blocked(tool, "interval_hours must be an integer >= 1")
        if not 1 <= interval_hours <= 2160:
            return _blocked(tool, "interval_hours must be between 1 and 2160")

    config_json_str = args.get("config_json")
    extra_config = {}
    if config_json_str:
        try:
            extra_config = json.loads(config_json_str)
        except (json.JSONDecodeError, TypeError) as exc:
            return _blocked(tool, f"Invalid config_json: {exc}")
        if not isinstance(extra_config, dict):
            return _blocked(tool, "config_json must decode to an object")
    if "create_issue_drafts" in args:
        extra_config["create_issue_drafts"] = _parse_bool(args.get("create_issue_drafts"), default=False)

    conn = open_state(root)
    init_state(conn)
    try:
        lock = acquire_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER, CONFIG_LOCK_TTL_SECONDS)
        if not lock.acquired:
            return _blocked(tool, "Config is locked by another operation", reason="lock_held")

        project_id = args.get("project_id")
        try:
            updated = enable_skill(
                root,
                skill_id,
                interval_hours=interval_hours,
                project_id=project_id,
                config=extra_config,
            )
            skill_cfg = (
                get_effective_config(root, skill_id, project_id=project_id)
                if project_id
                else updated["skills"][skill_id]
            )
        finally:
            release_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER)

        return _result(
            status="success",
            tool=tool,
            message=f"Enabled skill {skill_id}",
            data={"skill_id": skill_id, "enabled": True, "config": skill_cfg},
            summary=f"Skill {skill_id} enabled.",
        )
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to enable skill %s", skill_id)
        return _failed(tool, str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_maintenance_skill_disable
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_skill_disable(args: dict[str, Any], **kwargs: Any) -> str:
    """Disable a maintenance skill in config."""
    tool = "portfolio_maintenance_skill_disable"
    root = resolve_root(args.get("root"))

    skill_id = args.get("skill_id", "")
    if not skill_id:
        return _blocked(tool, "skill_id is required")
    if not re.match(r"^[a-z][a-z0-9_]{2,63}$", skill_id):
        return _blocked(tool, "invalid skill_id: must match ^[a-z][a-z0-9_]{2,63}$")

    conn = open_state(root)
    init_state(conn)
    try:
        lock = acquire_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER, CONFIG_LOCK_TTL_SECONDS)
        if not lock.acquired:
            return _blocked(tool, "Config is locked by another operation", reason="lock_held")

        project_id = args.get("project_id")
        try:
            updated = disable_skill(root, skill_id, project_id=project_id)
            skill_cfg = (
                get_effective_config(root, skill_id, project_id=project_id)
                if project_id
                else updated["skills"][skill_id]
            )
        finally:
            release_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER)

        return _result(
            status="success",
            tool=tool,
            message=f"Disabled skill {skill_id}",
            data={"skill_id": skill_id, "enabled": False, "config": skill_cfg},
            summary=f"Skill {skill_id} disabled.",
        )
    except ValueError as exc:
        return _blocked(tool, str(exc))
    except Exception as exc:
        logger.exception("Failed to disable skill %s", skill_id)
        return _failed(tool, str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_maintenance_due
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_due(args: dict[str, Any], **kwargs: Any) -> str:
    """Check which maintenance skills are due to run."""
    tool = "portfolio_maintenance_due"
    root = resolve_root(args.get("root"))

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        config = load_config(root)
        project_filter = _parse_csv_filter(args.get("project_id") or args.get("project_filter"))
        skill_filter = _parse_csv_filter(args.get("skill_id") or args.get("skill_filter"))

        checks = compute_due_checks(
            conn,
            config=config,
            project_filter=project_filter,
            skill_filter=skill_filter,
            include_paused=_parse_bool(args.get("include_paused"), default=False),
            include_archived=_parse_bool(args.get("include_archived"), default=False),
        )

        due_count = sum(1 for c in checks if c["is_due"])
        not_due_count = len(checks) - due_count

        return _result(
            status="success",
            tool=tool,
            message=f"{due_count} checks due, {not_due_count} not due.",
            data={
                "checks": checks,
                "due_count": due_count,
                "not_due_count": not_due_count,
                "total": len(checks),
            },
            summary=f"{due_count} due, {not_due_count} not due out of {len(checks)} checks.",
        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_maintenance_run
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_run(args: dict[str, Any], **kwargs: Any) -> str:
    """Execute or dry-run a maintenance cycle."""
    tool = "portfolio_maintenance_run"
    root = resolve_root(args.get("root"))

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        config = load_config(root)

        # Apply runtime overrides
        dry_run = _parse_bool(args.get("dry_run"), default=True)

        defaults = config.get("defaults", {})
        config["refresh_github"] = _parse_bool(
            args.get("refresh_github"),
            default=bool(defaults.get("refresh_github", config.get("refresh_github", False)))
            if isinstance(defaults, dict)
            else bool(config.get("refresh_github", False)),
        )
        config["create_issue_drafts"] = _parse_bool(
            args.get("create_issue_drafts"),
            default=bool(defaults.get("create_issue_drafts", config.get("create_issue_drafts", False)))
            if isinstance(defaults, dict)
            else bool(config.get("create_issue_drafts", False)),
        )

        project_filter = _parse_csv_filter(args.get("project_id") or args.get("project_filter"))
        skill_filter = _parse_csv_filter(args.get("skill_id") or args.get("skill_filter"))

        result = run_maintenance(
            root,
            conn,
            config,
            project_filter=project_filter,
            skill_filter=skill_filter,
            dry_run=bool(dry_run),
        )
        if result.get("status") == "blocked":
            return _blocked(tool, result.get("message", "Maintenance run is blocked"), reason=result.get("reason"))

        if dry_run:
            summary_data = result.get("summary", {})
            return _result(
                status="success",
                tool=tool,
                message="Dry run completed.",
                data=result,
                summary=(
                    f"Dry run: {summary_data.get('planned', 0)} planned, {summary_data.get('skipped', 0)} skipped."
                ),
            )

        runs = result.get("runs", [])
        errors = result.get("errors", [])
        findings_count = result.get("findings_count", 0)

        return _result(
            status="success",
            tool=tool,
            message=f"Ran {len(runs)} checks. {findings_count} findings.",
            data=result,
            summary=f"{len(runs)} runs, {findings_count} findings, {len(errors)} errors.",
        )
    except Exception as exc:
        logger.exception("Maintenance run failed")
        return _failed(tool, str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_maintenance_run_project
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_run_project(args: dict[str, Any], **kwargs: Any) -> str:
    """Run maintenance for a single project."""
    tool = "portfolio_maintenance_run_project"
    root = resolve_root(args.get("root"))

    project_ref = args.get("project_ref", "")
    if not project_ref:
        return _blocked(tool, "project_ref is required")

    _ensure_dirs(root)
    conn = open_state(root)
    init_state(conn)

    try:
        # Resolve project_ref to a project_id
        from portfolio_manager.config import load_projects_config
        from portfolio_manager.issue_resolver import resolve_project

        try:
            project_config = load_projects_config(root)
        except Exception as exc:
            return _blocked(tool, f"Config error: {exc}")

        resolution = resolve_project(project_config, project_ref=project_ref)
        if resolution.state != "resolved":
            return _blocked(
                tool,
                resolution.message,
                reason="project_not_found" if resolution.state == "not_found" else "ambiguous",
            )

        project_id = resolution.project_id or ""

        config = load_config(root)
        dry_run = _parse_bool(args.get("dry_run"), default=True)

        defaults = config.get("defaults", {})
        config["refresh_github"] = _parse_bool(
            args.get("refresh_github"),
            default=bool(defaults.get("refresh_github", config.get("refresh_github", False)))
            if isinstance(defaults, dict)
            else bool(config.get("refresh_github", False)),
        )
        config["create_issue_drafts"] = _parse_bool(
            args.get("create_issue_drafts"),
            default=bool(defaults.get("create_issue_drafts", config.get("create_issue_drafts", False)))
            if isinstance(defaults, dict)
            else bool(config.get("create_issue_drafts", False)),
        )

        skill_filter_arg = _parse_csv_filter(args.get("skill_id"))

        result = run_maintenance(
            root,
            conn,
            config,
            project_filter=[project_id],
            skill_filter=skill_filter_arg,
            dry_run=bool(dry_run),
        )
        if result.get("status") == "blocked":
            return _blocked(tool, result.get("message", "Maintenance run is blocked"), reason=result.get("reason"))

        if dry_run:
            summary_data = result.get("summary", {})
            return _result(
                status="success",
                tool=tool,
                message=f"Dry run for project {project_id}.",
                data=result,
                summary=(
                    f"Dry run {project_id}: {summary_data.get('planned', 0)} planned, "
                    f"{summary_data.get('skipped', 0)} skipped."
                ),
            )

        runs = result.get("runs", [])
        findings_count = result.get("findings_count", 0)

        return _result(
            status="success",
            tool=tool,
            message=f"Ran maintenance for {project_id}. {findings_count} findings.",
            data=result,
            summary=f"Project {project_id}: {len(runs)} runs, {findings_count} findings.",
        )
    except Exception as exc:
        logger.exception("Maintenance run_project failed")
        return _failed(tool, str(exc))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_maintenance_report
# ---------------------------------------------------------------------------


def _handle_portfolio_maintenance_report(args: dict[str, Any], **kwargs: Any) -> str:
    """Load a maintenance report."""
    tool = "portfolio_maintenance_report"
    root = resolve_root(args.get("root"))

    run_id = args.get("run_id")

    try:
        report = load_report(root, run_id) if run_id else load_latest_report(root)

        if report is None:
            return _blocked(
                tool,
                f"Report not found: {run_id}" if run_id else "No reports found.",
                reason="not_found",
            )

        # Apply optional filters to findings
        severity_filter = args.get("severity") or args.get("severity_filter")
        if severity_filter and "findings" in report:
            report["findings"] = [f for f in report["findings"] if f.get("severity") == severity_filter]

        return _result(
            status="success",
            tool=tool,
            message=f"Report for run {report.get('run_id', run_id or 'latest')}",
            data=report,
            summary=f"Report loaded: {len(report.get('findings', []))} findings.",
        )
    except Exception as exc:
        logger.exception("Failed to load report")
        return _failed(tool, str(exc))
