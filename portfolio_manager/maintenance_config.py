"""Maintenance configuration loader for MVP 4."""

from __future__ import annotations

import copy
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

import portfolio_manager.skills.builtin  # noqa: F401 — triggers register_all()
from portfolio_manager.config import ConfigError, load_projects_config
from portfolio_manager.maintenance_registry import get_registry

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

CONFIG_VERSION = 1
SKILL_BASE_KEYS = {"enabled", "interval_hours"}
DEFAULT_CONFIG: dict[str, Any] = {"version": CONFIG_VERSION, "defaults": {}, "skills": {}}


def config_path(root: Path) -> Path:
    """Return path to maintenance.yaml."""
    return root / "config" / "maintenance.yaml"


def backup_dir(root: Path) -> Path:
    """Return path to maintenance backup directory."""
    return root / "backups" / "maintenance"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Returns new dict."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _registry_defaults() -> dict[str, Any]:
    """Build default config from registered maintenance skill specs."""
    skills: dict[str, Any] = {}
    for spec in get_registry().list_specs():
        skill_cfg = {
            "enabled": spec.default_enabled,
            "interval_hours": spec.default_interval_hours,
        }
        for key, schema in spec.config_schema.items():
            if isinstance(schema, dict) and "default" in schema:
                skill_cfg[key] = copy.deepcopy(schema["default"])
        skills[spec.id] = skill_cfg
    return {"version": CONFIG_VERSION, "defaults": {}, "skills": skills}


def _load_raw_config(root: Path) -> dict[str, Any]:
    cp = config_path(root)
    if not cp.is_file():
        return {}
    with open(cp) as f:
        data: dict[str, Any] = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"maintenance.yaml must be a YAML mapping, got {type(data).__name__}")
    return data


def load_config(root: Path) -> dict[str, Any]:
    """Load maintenance config, deep-merging registry defaults with YAML."""
    raw = _load_raw_config(root)
    validate_config(root, raw, require_projects=False)
    return _deep_merge(_registry_defaults(), raw)


def _allowed_skill_keys(skill_id: str) -> set[str]:
    spec = get_registry().get_spec(skill_id)
    if spec is None:
        return set()
    return SKILL_BASE_KEYS | set(spec.config_schema)


def _validate_interval(skill_id: str, skill_cfg: Mapping[str, Any], prefix: str) -> None:
    if "interval_hours" not in skill_cfg:
        return
    try:
        interval = int(skill_cfg["interval_hours"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{prefix}.{skill_id}.interval_hours must be an integer") from exc
    if not 1 <= interval <= 2160:
        raise ValueError(f"{prefix}.{skill_id}.interval_hours must be between 1 and 2160")


def _validate_skill_config(skill_id: str, skill_cfg: Any, prefix: str) -> None:
    if skill_id.startswith("x_"):
        return
    spec = get_registry().get_spec(skill_id)
    if spec is None:
        raise ValueError(f"{prefix}.{skill_id}: unknown maintenance skill")
    if not isinstance(skill_cfg, dict):
        raise ValueError(f"{prefix}.{skill_id} must be a mapping")
    allowed = _allowed_skill_keys(skill_id)
    unknown = sorted(k for k in skill_cfg if k not in allowed and not str(k).startswith("x_"))
    if unknown:
        raise ValueError(f"{prefix}.{skill_id}: unknown config keys: {', '.join(unknown)}")
    _validate_interval(skill_id, skill_cfg, prefix)


def _project_ids(root: Path) -> set[str]:
    try:
        return {project.id for project in load_projects_config(root).projects}
    except ConfigError as exc:
        raise ValueError(f"Unable to validate project_id: {exc}") from exc


def validate_config(root: Path, config: dict[str, Any], *, require_projects: bool) -> None:
    """Validate maintenance config references and skill config keys."""
    skills = config.get("skills", {})
    if skills is not None and not isinstance(skills, dict):
        raise ValueError("maintenance.yaml skills must be a mapping")
    for skill_id, skill_cfg in (skills or {}).items():
        _validate_skill_config(str(skill_id), skill_cfg, "skills")

    defaults = config.get("defaults", {})
    if defaults is not None:
        if not isinstance(defaults, dict):
            raise ValueError("maintenance.yaml defaults must be a mapping")
        if "interval_hours" in defaults:
            _validate_interval("defaults", defaults, "defaults")

    projects = config.get("projects", {})
    if projects is None:
        return
    if not isinstance(projects, dict):
        raise ValueError("maintenance.yaml projects must be a mapping")
    if not projects and not require_projects:
        return

    valid_project_ids = _project_ids(root) if projects or require_projects else set()
    for project_id, project_cfg in projects.items():
        project_id = str(project_id)
        if project_id not in valid_project_ids:
            raise ValueError(f"projects.{project_id}: unknown project_id")
        if not isinstance(project_cfg, dict):
            raise ValueError(f"projects.{project_id} must be a mapping")
        project_skills = project_cfg.get("skills", {})
        if project_skills is None:
            continue
        if not isinstance(project_skills, dict):
            raise ValueError(f"projects.{project_id}.skills must be a mapping")
        for skill_id, skill_cfg in project_skills.items():
            _validate_skill_config(str(skill_id), skill_cfg, f"projects.{project_id}.skills")


def get_effective_config(
    root: Path,
    skill_id: str,
    project_id: str | None = None,
    tool_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the 5-layer config cascade for a skill/project/run."""
    spec = get_registry().get_spec(skill_id)
    if spec is None:
        raise ValueError(f"Unknown maintenance skill: {skill_id}")
    raw = _load_raw_config(root)
    validate_config(root, raw, require_projects=project_id is not None)

    if project_id is not None:
        valid_project_ids = _project_ids(root)
        if project_id not in valid_project_ids:
            raise ValueError(f"Unknown project_id: {project_id}")

    merged: dict[str, Any] = copy.deepcopy(_registry_defaults()["skills"][skill_id])
    defaults = raw.get("defaults", {})
    if isinstance(defaults, dict):
        merged = _deep_merge(merged, defaults)
    skills = raw.get("skills", {})
    if isinstance(skills, dict) and isinstance(skills.get(skill_id), dict):
        merged = _deep_merge(merged, skills[skill_id])
    if project_id is not None:
        project_skill_cfg = (
            raw.get("projects", {}).get(project_id, {}).get("skills", {}).get(skill_id, {})
            if isinstance(raw.get("projects"), dict)
            else {}
        )
        if isinstance(project_skill_cfg, dict):
            merged = _deep_merge(merged, project_skill_cfg)
    if tool_overrides:
        _validate_skill_config(skill_id, tool_overrides, "tool_overrides")
        merged = _deep_merge(merged, tool_overrides)
    return merged


def _atomic_backup(root: Path) -> Path | None:
    """Create a timestamped backup of maintenance.yaml."""
    cp = config_path(root)
    if not cp.is_file():
        return None
    bd = backup_dir(root)
    bd.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    dest = bd / f"maintenance-{ts}.yaml"
    shutil.copy2(cp, dest)
    return dest


def save_config(root: Path, config: dict[str, Any]) -> Path:
    """Atomic save with backup."""
    validate_config(root, config, require_projects=bool(config.get("projects")))
    _atomic_backup(root)
    cp = config_path(root)
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    tmp.replace(cp)
    return cp


def get_skill_config(root: Path, skill_id: str) -> dict[str, Any]:
    """Get effective global config for a specific skill."""
    return get_effective_config(root, skill_id)


def enable_skill(
    root: Path,
    skill_id: str,
    interval_hours: int | None = None,
    project_id: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enable a skill in config. Returns updated config."""
    if get_registry().get_spec(skill_id) is None:
        raise ValueError(f"Unknown maintenance skill: {skill_id}")
    updates: dict[str, Any] = dict(config or {})
    if interval_hours is not None:
        updates["interval_hours"] = interval_hours
    _validate_skill_config(skill_id, updates, "updates")

    cfg = _load_raw_config(root)
    validate_config(root, cfg, require_projects=project_id is not None)
    cfg.setdefault("version", CONFIG_VERSION)
    if project_id is None:
        skills = cfg.setdefault("skills", {})
        skill_cfg = skills.setdefault(skill_id, {})
    else:
        valid_project_ids = _project_ids(root)
        if project_id not in valid_project_ids:
            raise ValueError(f"Unknown project_id: {project_id}")
        project_cfg = cfg.setdefault("projects", {}).setdefault(project_id, {})
        skills = project_cfg.setdefault("skills", {})
        skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = True
    if interval_hours is not None:
        skill_cfg["interval_hours"] = interval_hours
    for key, value in (config or {}).items():
        skill_cfg[key] = copy.deepcopy(value)
    save_config(root, cfg)
    return load_config(root)


def disable_skill(root: Path, skill_id: str, project_id: str | None = None) -> dict[str, Any]:
    """Disable a skill in config. Returns updated config."""
    if get_registry().get_spec(skill_id) is None:
        raise ValueError(f"Unknown maintenance skill: {skill_id}")
    cfg = _load_raw_config(root)
    validate_config(root, cfg, require_projects=project_id is not None)
    cfg.setdefault("version", CONFIG_VERSION)
    if project_id is None:
        skills = cfg.setdefault("skills", {})
        skill_cfg = skills.setdefault(skill_id, {})
    else:
        valid_project_ids = _project_ids(root)
        if project_id not in valid_project_ids:
            raise ValueError(f"Unknown project_id: {project_id}")
        project_cfg = cfg.setdefault("projects", {}).setdefault(project_id, {})
        skills = project_cfg.setdefault("skills", {})
        skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = False
    save_config(root, cfg)
    return load_config(root)
