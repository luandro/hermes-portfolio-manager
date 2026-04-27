"""Pure project mutation functions for MVP 2.

All functions operate on in-memory dicts only — no file I/O, no SQLite.
Each returns a new dict (deep copy); the original is never mutated.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from portfolio_manager.admin_models import AdminProjectConfig

from portfolio_manager.admin_models import (
    VALID_PRIORITIES,
    validate_auto_merge,
    validate_priority,
    validate_status,
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


def add_project_to_config(
    config: dict[str, Any],
    project: AdminProjectConfig,
) -> dict[str, Any]:
    """Add a project to the in-memory config dict. Pure function — no I/O."""

    cfg = copy.deepcopy(config)
    projects: list[dict[str, Any]] = cfg.setdefault("projects", [])

    # Validate uniqueness
    for existing in projects:
        if existing.get("id") == project.id:
            raise ValueError(f"duplicate_project_id: {project.id}")
        # Check nested github: {owner, repo} shape
        existing_github = existing.get("github", {}) if isinstance(existing.get("github"), dict) else {}
        e_owner = existing_github.get("owner") or existing.get("github_owner")
        e_repo = existing_github.get("repo") or existing.get("github_repo")
        if e_owner == project.github_owner and e_repo == project.github_repo:
            raise ValueError(f"duplicate_github_repo: {project.github_owner}/{project.github_repo}")

    # Build project dict
    now = _utcnow()
    proj_dict: dict[str, Any] = {
        "id": project.id,
        "name": project.name,
        "repo": project.repo,
        "github": {
            "owner": project.github_owner,
            "repo": project.github_repo,
        },
        "priority": project.priority,
        "status": project.status,
        "default_branch": project.default_branch,
        "auto_merge": {
            "enabled": project.auto_merge.enabled,
            "max_risk": project.auto_merge.max_risk,
        },
        "protected_paths": list(project.protected_paths),
        "labels": list(project.labels) if project.labels else [],
        "created_at": now,
        "updated_at": now,
    }
    if project.notes:
        proj_dict["notes"] = project.notes
    if project.created_by:
        proj_dict["created_by"] = project.created_by

    # Preserve extra fields from the Pydantic model
    extra = project.model_extra or {}
    for k, v in extra.items():
        if k not in proj_dict and k not in ("github_owner", "github_repo"):
            proj_dict[k] = v

    projects.append(proj_dict)
    return cfg


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_project_in_config(
    config: dict[str, Any],
    project_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Update fields on an existing project. Pure function — no I/O."""
    if not updates:
        raise ValueError("no_update_fields")

    cfg = copy.deepcopy(config)
    projects: list[dict[str, Any]] = cfg.get("projects", [])

    target = None
    for existing in projects:
        if existing.get("id") == project_id:
            target = existing
            break
    if target is None:
        raise ValueError(f"Project not found: {project_id}")

    now = _utcnow()

    for key in ("name", "default_branch"):
        if key in updates:
            target[key] = updates[key]
    if "priority" in updates:
        validate_priority(updates["priority"])
        target["priority"] = updates["priority"]
        if updates["priority"] == "paused":
            target["status"] = "paused"
    if "status" in updates:
        validate_status(updates["status"])
        target["status"] = updates["status"]

    # protected_paths
    if "protected_paths" in updates:
        target["protected_paths"] = list(updates["protected_paths"])

    # auto_merge — validate through validate_auto_merge for consistent warnings
    if "auto_merge" in updates:
        am = updates["auto_merge"]
        if am is not None:
            validated = validate_auto_merge(enabled=am.get("enabled", False), max_risk=am.get("max_risk"))
            target["auto_merge"] = {"enabled": validated.enabled, "max_risk": validated.max_risk}

    # notes
    if "notes" in updates:
        target["notes"] = updates["notes"]

    target["updated_at"] = now
    return cfg


# ---------------------------------------------------------------------------
# Pause / Resume / Archive
# ---------------------------------------------------------------------------


def _find_project(config: dict[str, Any], project_id: str) -> dict[str, Any] | None:
    """Find a project dict by ID in the config."""
    projects: list[dict[str, Any]] = config.get("projects", [])
    for p in projects:
        if p.get("id") == project_id:
            return p
    return None


def pause_project_in_config(
    config: dict[str, Any],
    project_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Set project status to 'paused' with optional reason appended to notes."""
    existing = _find_project(config, project_id)
    if existing is None:
        raise ValueError(f"Project not found: {project_id}")
    existing_notes = existing.get("notes", "") or ""
    pause_note = f"Paused: {reason}" if reason else "Paused"
    new_notes = (existing_notes + "\n" + pause_note).strip() if existing_notes else pause_note
    return update_project_in_config(
        config,
        project_id,
        {
            "status": "paused",
            "notes": new_notes,
        },
    )


def resume_project_in_config(
    config: dict[str, Any],
    project_id: str,
) -> dict[str, Any]:
    """Set project status back to 'active'."""
    existing = _find_project(config, project_id)
    if existing is None:
        raise ValueError(f"Project not found: {project_id}")
    existing_notes = existing.get("notes", "") or ""
    resume_note = f"Resumed at: {_utcnow()}"
    new_notes = (existing_notes + "\n" + resume_note).strip() if existing_notes else resume_note
    return update_project_in_config(
        config,
        project_id,
        {
            "status": "active",
            "notes": new_notes,
        },
    )


def archive_project_in_config(
    config: dict[str, Any],
    project_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Set project status to 'archived' with optional reason appended to notes."""
    existing = _find_project(config, project_id)
    if existing is None:
        raise ValueError(f"Project not found: {project_id}")
    updates: dict[str, Any] = {"status": "archived"}
    existing_notes = existing.get("notes", "") or ""
    archive_note = f"Archived: {reason}" if reason else "Archived"
    new_notes = (existing_notes + "\n" + archive_note).strip() if existing_notes else archive_note
    updates["notes"] = new_notes
    return update_project_in_config(config, project_id, updates)


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


def remove_project_from_config(
    config: dict[str, Any],
    project_id: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Remove a project entirely. Requires confirm=True."""
    if not confirm:
        raise ValueError("Cannot remove project without confirmation (confirm=True). Consider archiving instead.")
    cfg = copy.deepcopy(config)
    # Check if project exists before removal
    found = any(p.get("id") == project_id for p in cfg.get("projects", []))
    if not found:
        raise ValueError(f"Project not found: {project_id}")
    cfg["projects"] = [p for p in cfg.get("projects", []) if p.get("id") != project_id]
    return cfg


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


def set_project_priority_in_config(
    config: dict[str, Any],
    project_id: str,
    priority: str,
) -> dict[str, Any]:
    """Set project priority. If priority='paused', also sets status='paused'."""
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority!r}. Valid: {sorted(VALID_PRIORITIES)}")
    updates: dict[str, Any] = {"priority": priority}
    if priority == "paused":
        updates["status"] = "paused"
    return update_project_in_config(config, project_id, updates)


# ---------------------------------------------------------------------------
# Auto-merge
# ---------------------------------------------------------------------------


def set_project_auto_merge_in_config(
    config: dict[str, Any],
    project_id: str,
    enabled: bool,
    max_risk: str | None = None,
) -> dict[str, Any]:
    """Set auto-merge policy. Validates via AutoMergeConfig."""
    am = validate_auto_merge(enabled=enabled, max_risk=max_risk)
    return update_project_in_config(
        config,
        project_id,
        {"auto_merge": {"enabled": am.enabled, "max_risk": am.max_risk}},
    )
