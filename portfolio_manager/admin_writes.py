"""Config file I/O layer for MVP 2.

Atomic writes, backup creation, and reload validation.
All functions operate on a *root* directory containing config/ and backups/.
"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import yaml

BACKUP_PATTERN = "projects.yaml.{timestamp}.bak"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S.%fZ")


def load_config_dict(root: Path) -> dict[str, Any] | None:
    """Load config/projects.yaml as a dict. Returns None if missing or corrupt."""
    config_path = root / "config" / "projects.yaml"
    if not config_path.exists():
        return None
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        return None  # Not a dict (list, scalar, etc.) is corrupt/missing config
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        return None


def create_projects_config_backup(root: Path) -> dict[str, Any]:
    """Copy config/projects.yaml to backups/ with a timestamp suffix.

    Returns {"backup_created": bool, "backup_path": str | None}.
    """
    config_path = root / "config" / "projects.yaml"
    if not config_path.exists():
        return {"backup_created": False, "backup_path": None}

    backup_dir = root / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    backup_path = backup_dir / BACKUP_PATTERN.format(timestamp=ts)
    shutil.copy2(config_path, backup_path)

    return {"backup_created": True, "backup_path": str(backup_path)}


def write_projects_config_atomic(root: Path, config_dict: dict[str, Any]) -> dict[str, Any]:
    """Write config_dict to config/projects.yaml atomically (temp + os.replace).

    Validates both before and after writing. Returns {"status": ..., "path": ...}.
    """
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "projects.yaml"

    # Validate before write: serialize and re-parse
    try:
        yaml_output = yaml.dump(config_dict, default_flow_style=False, allow_unicode=True)
        parsed_back = yaml.safe_load(yaml_output)
        if not isinstance(parsed_back, dict):
            raise ValueError("Config produces invalid YAML (not a mapping)")
    except (yaml.YAMLError, ValueError) as exc:
        return {"status": "failed", "error": f"Config validation failed before write: {exc}", "path": str(config_path)}

    # Atomic write: temp file then replace
    tmp_name = f"projects.yaml.tmp.{uuid.uuid4().hex}"
    tmp_path = config_dir / tmp_name
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(yaml_output)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(config_path))
        try:
            dir_fd = os.open(str(config_dir), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except OSError as exc:
        if tmp_path.exists():
            tmp_path.unlink()
        return {"status": "failed", "error": f"Write failed: {exc}", "path": str(config_path)}

    # Validate after write: reload and compare with original
    try:
        reloaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(reloaded, dict):
            return {"status": "failed", "error": "Written config failed reload validation", "path": str(config_path)}
        # Check that reloaded data matches what we tried to write
        if reloaded != parsed_back:
            return {"status": "failed", "error": "Written config data mismatch after reload", "path": str(config_path)}
    except yaml.YAMLError as exc:
        return {"status": "failed", "error": f"Written config failed reload: {exc}", "path": str(config_path)}

    return {"status": "success", "path": str(config_path)}


def create_initial_config(root: Path) -> dict[str, Any]:
    """Create a fresh config/projects.yaml with version 1 and empty projects list."""
    initial: dict[str, Any] = {"version": 1, "projects": []}
    return write_projects_config_atomic(root, initial)
