"""Maintenance configuration loader for MVP 4."""

from __future__ import annotations

import copy
import shutil
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_CONFIG: dict[str, Any] = {
    "skills": {
        "untriaged_issue_digest": {
            "enabled": True,
            "interval_hours": 24,
            "min_age_hours": 24,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "stale_issue_digest": {
            "enabled": True,
            "interval_hours": 168,
            "stale_after_days": 30,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "open_pr_health": {
            "enabled": True,
            "interval_hours": 12,
            "stale_after_days": 7,
            "include_review_pending": True,
            "include_checks_failed": True,
            "include_changes_requested": True,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "repo_guidance_docs": {
            "enabled": True,
            "interval_hours": 168,
            "doc_paths": ["CONTRIBUTING.md", "DEVELOPMENT.md", "ARCHITECTURE.md", "DESIGN.md"],
            "max_findings": 20,
            "create_issue_drafts": False,
        },
    },
}


def config_path(root: Path) -> Path:
    """Return path to maintenance.yaml."""
    return root / "config" / "maintenance.yaml"


def backup_dir(root: Path) -> Path:
    """Return path to maintenance backup directory."""
    return root / "backups" / "maintenance"


def load_config(root: Path) -> dict[str, Any]:
    """Load maintenance config. Returns defaults if file doesn't exist."""
    cp = config_path(root)
    if cp.is_file():
        with open(cp) as f:
            data: dict[str, Any] = yaml.safe_load(f)
        if data and isinstance(data, dict):
            return data
    return copy.deepcopy(DEFAULT_CONFIG)


def _atomic_backup(root: Path) -> Path | None:
    """Create a timestamped backup of maintenance.yaml."""
    cp = config_path(root)
    if not cp.is_file():
        return None
    bd = backup_dir(root)
    bd.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = bd / f"maintenance-{ts}.yaml"
    shutil.copy2(cp, dest)
    return dest


def save_config(root: Path, config: dict[str, Any]) -> Path:
    """Atomic save with backup."""
    _atomic_backup(root)
    cp = config_path(root)
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    tmp.replace(cp)
    return cp


def get_skill_config(root: Path, skill_id: str) -> dict[str, Any]:
    """Get merged config for a specific skill (defaults + overrides)."""
    cfg = load_config(root)
    defaults = DEFAULT_CONFIG.get("skills", {}).get(skill_id, {})
    overrides = cfg.get("skills", {}).get(skill_id, {})
    return {**defaults, **overrides}


def enable_skill(root: Path, skill_id: str, interval_hours: int | None = None) -> dict[str, Any]:
    """Enable a skill in config. Returns updated config."""
    cfg = load_config(root)
    skills = cfg.setdefault("skills", {})
    skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = True
    if interval_hours is not None:
        skill_cfg["interval_hours"] = interval_hours
    save_config(root, cfg)
    return cfg


def disable_skill(root: Path, skill_id: str) -> dict[str, Any]:
    """Disable a skill in config. Returns updated config."""
    cfg = load_config(root)
    skills = cfg.setdefault("skills", {})
    skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = False
    save_config(root, cfg)
    return cfg
