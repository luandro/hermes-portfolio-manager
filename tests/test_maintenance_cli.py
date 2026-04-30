"""Tests for maintenance CLI commands in dev_cli.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# dev_cli.py lives in the project root, not in a package — add it to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import portfolio_manager.skills.builtin  # noqa: F401 — triggers self-registration
from dev_cli import TOOL_HANDLERS, main

MAINTENANCE_COMMANDS = [
    "portfolio_maintenance_skill_list",
    "portfolio_maintenance_skill_explain",
    "portfolio_maintenance_skill_enable",
    "portfolio_maintenance_skill_disable",
    "portfolio_maintenance_due",
    "portfolio_maintenance_run",
    "portfolio_maintenance_run_project",
    "portfolio_maintenance_report",
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


def test_maintenance_cli_wires_new_args(monkeypatch, capsys) -> None:
    """Maintenance CLI args are parsed and forwarded to handlers."""

    def fake_handler(args: dict[str, object]) -> str:
        return json.dumps(args, sort_keys=True)

    monkeypatch.setitem(TOOL_HANDLERS, "portfolio_maintenance_run", fake_handler)

    main(
        [
            "portfolio_maintenance_run",
            "--skill-id",
            "stale_issue_digest",
            "--interval-hours",
            "168",
            "--config-json",
            '{"create_issue_drafts": true}',
            "--include-disabled",
            "true",
            "--include-project-overrides",
            "false",
            "--include-paused",
            "true",
            "--include-archived",
            "false",
            "--include-not-due",
            "true",
            "--refresh-github",
            "false",
            "--create-issue-drafts",
            "true",
            "--max-projects",
            "7",
            "--run-id",
            "run_001",
            "--severity",
            "high",
            "--limit",
            "3",
            "--include-resolved",
            "false",
        ]
    )

    parsed = json.loads(capsys.readouterr().out)
    assert parsed["skill_id"] == "stale_issue_digest"
    assert parsed["interval_hours"] == 168
    assert parsed["config_json"] == '{"create_issue_drafts": true}'
    assert parsed["include_disabled"] is True
    assert parsed["include_project_overrides"] is False
    assert parsed["include_paused"] is True
    assert parsed["include_archived"] is False
    assert parsed["include_not_due"] is True
    assert parsed["refresh_github"] is False
    assert parsed["create_issue_drafts"] is True
    assert parsed["max_projects"] == 7
    assert parsed["run_id"] == "run_001"
    assert parsed["severity"] == "high"
    assert parsed["limit"] == 3
    assert parsed["include_resolved"] is False


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
    result = handler({"root": str(root), "skill_id": "untriaged_issue_digest"})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_explain"


def test_maintenance_skill_enable_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    handler = TOOL_HANDLERS["maintenance-skill-enable"]
    result = handler({"root": str(root), "skill_id": "untriaged_issue_digest"})
    data = json.loads(result)
    assert data["status"] == "success"
    assert data["tool"] == "portfolio_maintenance_skill_enable"


def test_maintenance_skill_disable_callable(tmp_path: Path) -> None:
    root = _setup_root(tmp_path)
    # Enable first so disable has something to disable
    TOOL_HANDLERS["maintenance-skill-enable"]({"root": str(root), "skill_id": "untriaged_issue_digest"})
    handler = TOOL_HANDLERS["maintenance-skill-disable"]
    result = handler({"root": str(root), "skill_id": "untriaged_issue_digest"})
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
