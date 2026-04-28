"""Tests for maintenance CLI commands in dev_cli.py."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import portfolio_manager.skills.builtin  # noqa: F401 — triggers self-registration
from dev_cli import TOOL_HANDLERS

if TYPE_CHECKING:
    from pathlib import Path

MAINTENANCE_COMMANDS = [
    "maintenance-skill-list",
    "maintenance-skill-explain",
    "maintenance-skill-enable",
    "maintenance-skill-disable",
    "maintenance-due",
    "maintenance-run",
    "maintenance-run-project",
    "maintenance-report",
]


def _setup_root(tmp_path: Path) -> Path:
    """Create a minimal portfolio root with config dirs."""
    root = tmp_path / "portfolio"
    for d in ("config", "state", "worktrees", "logs", "artifacts", "backups"):
        (root / d).mkdir(parents=True, exist_ok=True)
    # Write an empty projects.yaml so config loading doesn't fail
    config_dir = root / "config"
    (config_dir / "projects.yaml").write_text("version: 1\nprojects: []\n", encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


def test_all_maintenance_commands_registered() -> None:
    """All 8 maintenance CLI commands must be present in TOOL_HANDLERS."""
    missing = [cmd for cmd in MAINTENANCE_COMMANDS if cmd not in TOOL_HANDLERS]
    assert not missing, f"Missing CLI registrations: {missing}"


def test_maintenance_handlers_are_callable() -> None:
    """Every maintenance handler must be callable."""
    for cmd in MAINTENANCE_COMMANDS:
        handler = TOOL_HANDLERS[cmd]
        assert callable(handler), f"Handler for {cmd!r} is not callable"


# ---------------------------------------------------------------------------
# Handler callability tests — invoke each handler directly
# ---------------------------------------------------------------------------


def test_maintenance_skill_list_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-skill-list"]
    result = handler({"root": str(root)})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_list"


def test_maintenance_skill_explain_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-skill-explain"]
    result = handler({"root": str(root), "skill_id": "health_check"})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_explain"


def test_maintenance_skill_enable_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-skill-enable"]
    result = handler({"root": str(root), "skill_id": "health_check"})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_enable"


def test_maintenance_skill_disable_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    # Enable first so disable has something to disable
    TOOL_HANDLERS["maintenance-skill-enable"]({"root": str(root), "skill_id": "health_check"})
    handler = TOOL_HANDLERS["maintenance-skill-disable"]
    result = handler({"root": str(root), "skill_id": "health_check"})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_disable"


def test_maintenance_due_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-due"]
    result = handler({"root": str(root)})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_due"


def test_maintenance_run_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-run"]
    result = handler({"root": str(root), "dry_run": True})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_run"


def test_maintenance_run_project_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-run-project"]
    result = handler({"root": str(root), "project_ref": "nonexistent", "dry_run": True})
    data = json.loads(result)
    # project_ref "nonexistent" won't resolve → blocked, but still callable
    assert data["tool"] == "portfolio_maintenance_run_project"
    assert data["status"] in ("success", "blocked")


def test_maintenance_report_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-report"]
    result = handler({"root": str(root)})
    data = json.loads(result)
    # No reports exist → blocked, but still callable
    assert data["tool"] == "portfolio_maintenance_report"
    assert data["status"] in ("success", "blocked")
