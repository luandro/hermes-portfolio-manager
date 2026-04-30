"""Tests for MVP 4 maintenance tool handlers (Phase 6)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from portfolio_manager.maintenance_config import save_config
from portfolio_manager.maintenance_models import MaintenanceSkillSpec
from portfolio_manager.maintenance_registry import get_registry
from portfolio_manager.state import acquire_lock, init_state, open_state, release_lock

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """Provide a temp root with required directories."""
    for d in ("state", "artifacts", "backups", "config", "worktrees", "logs"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture()
def conn(root: Path):
    """Provide an initialized state DB connection."""
    c = open_state(root)
    init_state(c)
    yield c
    c.close()


@pytest.fixture()
def _register_test_skill() -> None:
    """Register a test skill in the registry (idempotent)."""
    registry = get_registry()
    if registry.get_spec("test_skill") is None:
        spec = MaintenanceSkillSpec(
            id="test_skill",
            name="Test Skill",
            description="A test maintenance skill",
            default_interval_hours=24,
            default_enabled=True,
            supports_issue_drafts=True,
            required_state=[],
            allowed_commands=[],
            config_schema={},
        )
        from portfolio_manager.maintenance_models import MaintenanceSkillResult

        def _execute(ctx):
            return MaintenanceSkillResult(
                skill_id="test_skill",
                project_id=ctx.project.id,
                status="success",
                findings=[],
                summary="Test skill ran successfully.",
            )

        registry.register(spec, _execute)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestSchemaDefaults:
    def test_maintenance_skill_list_schema_defaults(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA

        s = PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA
        assert s["name"] == "portfolio_maintenance_skill_list"
        assert s["parameters"]["required"] == []

    def test_maintenance_skill_explain_requires_skill_id(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA

        s = PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA
        assert "skill_id" in s["parameters"]["required"]

    def test_maintenance_skill_enable_validates_interval_bounds(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA

        s = PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA
        assert "skill_id" in s["parameters"]["required"]
        # interval_hours is optional (not in required)
        assert "interval_hours" not in s["parameters"]["required"]
        assert s["parameters"]["properties"]["interval_hours"]["type"] == "integer"

    def test_maintenance_run_schema_defaults(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_MAINTENANCE_RUN_SCHEMA

        s = PORTFOLIO_MAINTENANCE_RUN_SCHEMA
        assert s["parameters"]["required"] == []
        assert "dry_run" in s["parameters"]["properties"]
        assert "create_issue_drafts" in s["parameters"]["properties"]
        assert "refresh_github" in s["parameters"]["properties"]

    def test_maintenance_report_schema_defaults(self) -> None:
        from portfolio_manager.schemas import PORTFOLIO_MAINTENANCE_REPORT_SCHEMA

        s = PORTFOLIO_MAINTENANCE_REPORT_SCHEMA
        assert s["parameters"]["required"] == []
        assert "run_id" in s["parameters"]["properties"]
        assert "severity" in s["parameters"]["properties"]


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestSkillList:
    def test_skill_list_works_with_missing_config(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_list

        result_str = _handle_portfolio_maintenance_skill_list({"root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["tool"] == "portfolio_maintenance_skill_list"
        skills = result["data"]["skills"]
        # At least our test skill should be there
        skill_ids = [s["id"] for s in skills]
        assert "test_skill" in skill_ids

    def test_skill_list_can_hide_disabled_skills(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_list

        # Disable test_skill in config
        save_config(root, {"skills": {"test_skill": {"enabled": False}}})

        result_str = _handle_portfolio_maintenance_skill_list({"root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        test_skill = next(s for s in result["data"]["skills"] if s["id"] == "test_skill")
        assert test_skill["enabled"] is False


class TestSkillExplain:
    def test_skill_explain_returns_registry_and_effective_config(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_explain

        result_str = _handle_portfolio_maintenance_skill_explain({"skill_id": "test_skill", "root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["data"]["spec"]["id"] == "test_skill"
        assert "effective_config" in result["data"]

    def test_skill_explain_blocks_unknown_skill(self, root: Path) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_explain

        result_str = _handle_portfolio_maintenance_skill_explain({"skill_id": "nonexistent_skill", "root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "blocked"
        assert "Unknown skill" in result["message"]


class TestSkillEnableDisable:
    def test_skill_enable_writes_config(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_enable

        result_str = _handle_portfolio_maintenance_skill_enable({"skill_id": "test_skill", "root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["data"]["enabled"] is True

        # Verify persisted
        from portfolio_manager.maintenance_config import load_config

        cfg = load_config(root)
        assert cfg["skills"]["test_skill"]["enabled"] is True

    def test_skill_disable_writes_config(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_disable

        result_str = _handle_portfolio_maintenance_skill_disable({"skill_id": "test_skill", "root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["data"]["enabled"] is False

        # Verify persisted
        from portfolio_manager.maintenance_config import load_config

        cfg = load_config(root)
        assert cfg["skills"]["test_skill"]["enabled"] is False

    def test_skill_enable_blocks_when_config_lock_held(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_enable

        conn = open_state(root)
        init_state(conn)
        try:
            lock = acquire_lock(conn, "maintenance:config", "other-owner", 60)
            assert lock.acquired is True

            result_str = _handle_portfolio_maintenance_skill_enable({"skill_id": "test_skill", "root": str(root)})
            result = json.loads(result_str)

            assert result["status"] == "blocked"
            assert result["reason"] == "lock_held"
        finally:
            release_lock(conn, "maintenance:config", "other-owner")
            conn.close()

    def test_skill_disable_blocks_when_config_lock_held(self, root: Path, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_skill_disable

        conn = open_state(root)
        init_state(conn)
        try:
            lock = acquire_lock(conn, "maintenance:config", "other-owner", 60)
            assert lock.acquired is True

            result_str = _handle_portfolio_maintenance_skill_disable({"skill_id": "test_skill", "root": str(root)})
            result = json.loads(result_str)

            assert result["status"] == "blocked"
            assert result["reason"] == "lock_held"
        finally:
            release_lock(conn, "maintenance:config", "other-owner")
            conn.close()


class TestMaintenanceDue:
    def test_maintenance_due_tool_returns_counts(self, root: Path, conn: Any, _register_test_skill: None) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_due

        # Need at least one project in DB for due checks to work
        conn.execute(
            "INSERT INTO projects (id, name, repo_url, priority, status, default_branch, created_at, updated_at) "
            "VALUES (?, ?, '', 'medium', 'active', 'main', datetime('now'), datetime('now'))",
            ("test-project", "Test Project"),
        )
        conn.commit()

        # Save config with test_skill enabled
        save_config(root, {"skills": {"test_skill": {"enabled": True, "interval_hours": 24}}})

        result_str = _handle_portfolio_maintenance_due({"root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert "due_count" in result["data"]
        assert "not_due_count" in result["data"]
        assert "total" in result["data"]


class TestMaintenanceRun:
    def test_maintenance_run_dry_run_has_no_side_effects(
        self, root: Path, conn: Any, _register_test_skill: None
    ) -> None:
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_run

        # Add project to DB
        conn.execute(
            "INSERT INTO projects (id, name, repo_url, priority, status, default_branch, created_at, updated_at) "
            "VALUES (?, ?, '', 'medium', 'active', 'main', datetime('now'), datetime('now'))",
            ("test-project", "Test Project"),
        )
        conn.commit()

        save_config(root, {"skills": {"test_skill": {"enabled": True, "interval_hours": 24}}})

        # Count runs before
        runs_before = conn.execute("SELECT COUNT(*) FROM maintenance_runs").fetchone()[0]

        result_str = _handle_portfolio_maintenance_run({"root": str(root), "dry_run": True})
        result = json.loads(result_str)
        assert result["status"] == "success"

        # Count runs after — should be same (dry run)
        runs_after = conn.execute("SELECT COUNT(*) FROM maintenance_runs").fetchone()[0]
        assert runs_after == runs_before


class TestMaintenanceReport:
    def test_maintenance_report_returns_latest_run(self, root: Path) -> None:
        from portfolio_manager.maintenance_reports import (
            write_findings_json,
            write_maintenance_report,
            write_metadata_json,
        )
        from portfolio_manager.maintenance_tools import _handle_portfolio_maintenance_report

        # Create a fake report
        run_id = "test-run-001"
        findings = [{"severity": "high", "title": "Test finding", "body": "body"}]
        metadata = {"run_id": run_id, "project_id": "test-project", "skill_id": "test_skill", "status": "success"}

        write_maintenance_report(root, run_id, findings, metadata)
        write_findings_json(root, run_id, findings)
        write_metadata_json(root, run_id, metadata)

        result_str = _handle_portfolio_maintenance_report({"root": str(root)})
        result = json.loads(result_str)
        assert result["status"] == "success"
        assert result["data"]["run_id"] == run_id
        assert len(result["data"]["findings"]) == 1
