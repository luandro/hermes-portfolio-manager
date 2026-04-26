"""Tests for Phase 4 — Atomic Config Writes and Backups."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

if TYPE_CHECKING:
    import pytest

import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = {"version": 1, "projects": [{"id": "proj-a", "name": "A"}]}


def _write_config(root: Path, config: dict[str, Any] | None = None) -> Path:
    """Write a projects.yaml under root/config/ and return the path."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "projects.yaml"
    config_path.write_text(
        yaml.dump(config or SAMPLE_CONFIG, default_flow_style=False),
        encoding="utf-8",
    )
    return config_path


# ---------------------------------------------------------------------------
# a) test_create_projects_config_backup
# ---------------------------------------------------------------------------


def test_create_projects_config_backup(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import create_projects_config_backup

    config_path = _write_config(tmp_path)
    original_content = config_path.read_text(encoding="utf-8")

    # Freeze _timestamp to a known value
    frozen_ts = "2026-04-26T12-00-00Z"
    with patch("portfolio_manager.admin_writes._timestamp", return_value=frozen_ts):
        result = create_projects_config_backup(tmp_path)

    assert result["backup_created"] is True
    assert result["backup_path"] is not None

    backup_path = Path(result["backup_path"])
    assert backup_path.exists()
    assert backup_path.parent == tmp_path / "backups"
    assert frozen_ts in backup_path.name
    assert backup_path.name == f"projects.yaml.{frozen_ts}.bak"

    # Content matches original
    assert backup_path.read_text(encoding="utf-8") == original_content


# ---------------------------------------------------------------------------
# b) test_missing_config_first_run_behavior
# ---------------------------------------------------------------------------


def test_missing_config_first_run_behavior(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import create_projects_config_backup

    # No projects.yaml exists — backup returns not-created
    result = create_projects_config_backup(tmp_path)
    assert result["backup_created"] is False
    assert result["backup_path"] is None


# ---------------------------------------------------------------------------
# c) test_atomic_config_write_uses_temp_file_and_replace
# ---------------------------------------------------------------------------


def test_atomic_config_write_uses_temp_file_and_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from portfolio_manager.admin_writes import write_projects_config_atomic

    config_dict = {"version": 1, "projects": []}

    # Track os.replace calls
    replace_calls: list[tuple[str, str]] = []
    original_replace = os.replace

    def tracking_replace(src: str, dst: str) -> None:
        replace_calls.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", tracking_replace)

    result = write_projects_config_atomic(tmp_path, config_dict)

    assert result["status"] == "success"

    # os.replace was called exactly once
    assert len(replace_calls) == 1
    src, dst = replace_calls[0]
    # Source was a temp file
    assert "projects.yaml.tmp." in src
    # Destination is the final config path
    assert dst.endswith("projects.yaml")
    assert not dst.endswith(".tmp")

    # Final file exists, temp file does not
    config_path = tmp_path / "config" / "projects.yaml"
    assert config_path.exists()
    # No temp files left
    for f in (tmp_path / "config").iterdir():
        assert ".tmp." not in f.name


# ---------------------------------------------------------------------------
# d) test_config_write_validates_before_and_after
# ---------------------------------------------------------------------------


def test_config_write_validates_before_and_after(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import write_projects_config_atomic

    # Valid config should succeed and be reloadable
    valid_config = {"version": 1, "projects": [{"id": "test-proj", "name": "Test"}]}
    result = write_projects_config_atomic(tmp_path, valid_config)
    assert result["status"] == "success"

    # Reload and verify
    config_path = tmp_path / "config" / "projects.yaml"
    reloaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert reloaded["version"] == 1
    assert reloaded["projects"][0]["id"] == "test-proj"

    # Object that can't serialize to valid YAML mapping should fail
    # (yaml.dump of a non-dict top-level produces non-mapping YAML)
    result_bad = write_projects_config_atomic(tmp_path, "not a dict")  # type: ignore[arg-type]
    assert result_bad["status"] == "failed"
    assert "validation failed" in result_bad["error"].lower()


# ---------------------------------------------------------------------------
# e) test_every_mutation_creates_backup_when_config_exists
# ---------------------------------------------------------------------------


def test_every_mutation_creates_backup_when_config_exists(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import create_projects_config_backup

    _write_config(tmp_path)
    backup_dir = tmp_path / "backups"

    # Each call should create a new backup
    call_count = 3
    for i in range(call_count):
        ts = f"2026-04-26T12-00-0{i}Z"
        with patch("portfolio_manager.admin_writes._timestamp", return_value=ts):
            result = create_projects_config_backup(tmp_path)
            assert result["backup_created"] is True

    # Verify backup count
    backups = list(backup_dir.glob("projects.yaml.*.bak"))
    assert len(backups) == call_count


# ---------------------------------------------------------------------------
# f) test_config_writes_cannot_escape_system_root
# ---------------------------------------------------------------------------


def test_config_writes_cannot_escape_system_root(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import (
        create_projects_config_backup,
        write_projects_config_atomic,
    )

    _write_config(tmp_path)

    # Backup writes stay under root
    result = create_projects_config_backup(tmp_path)
    assert result["backup_created"] is True
    backup_path = Path(result["backup_path"])
    assert str(backup_path).startswith(str(tmp_path))

    # Atomic write stays under root/config/
    config = {"version": 1, "projects": []}
    result = write_projects_config_atomic(tmp_path, config)
    assert result["status"] == "success"
    assert str(result["path"]).startswith(str(tmp_path))

    # All files under config/ and backups/ are within root
    for f in (tmp_path / "config").rglob("*"):
        resolved = f.resolve()
        assert str(resolved).startswith(str(tmp_path.resolve()))
    for f in (tmp_path / "backups").rglob("*"):
        resolved = f.resolve()
        assert str(resolved).startswith(str(tmp_path.resolve()))


# ---------------------------------------------------------------------------
# g) test_load_config_dict
# ---------------------------------------------------------------------------


def test_load_config_dict(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import load_config_dict

    # No config file → None
    assert load_config_dict(tmp_path) is None

    # Valid config → dict
    _write_config(tmp_path)
    result = load_config_dict(tmp_path)
    assert isinstance(result, dict)
    assert result["version"] == 1

    # Corrupt YAML → None
    config_path = tmp_path / "config" / "projects.yaml"
    config_path.write_text("{{{{invalid yaml: [", encoding="utf-8")
    assert load_config_dict(tmp_path) is None


# ---------------------------------------------------------------------------
# h) test_create_initial_config
# ---------------------------------------------------------------------------


def test_create_initial_config(tmp_path: Path) -> None:
    from portfolio_manager.admin_writes import create_initial_config, load_config_dict

    result = create_initial_config(tmp_path)
    assert result["status"] == "success"

    config = load_config_dict(tmp_path)
    assert config is not None
    assert config["version"] == 1
    assert config["projects"] == []
