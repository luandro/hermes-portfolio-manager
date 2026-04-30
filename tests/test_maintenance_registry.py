"""Tests for maintenance_registry._Registry and module-level helpers."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
)
from portfolio_manager.maintenance_registry import REGISTRY, _Registry, get_registry

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_spec(
    skill_id: str = "test_skill",
    name: str = "Test Skill",
    description: str = "A test skill",
    **overrides,
) -> MaintenanceSkillSpec:
    defaults = dict(
        id=skill_id,
        name=name,
        description=description,
        default_interval_hours=24,
        default_enabled=True,
        supports_issue_drafts=False,
        required_state=[],
        allowed_commands=[],
        config_schema={},
    )
    defaults.update(overrides)
    return MaintenanceSkillSpec(**defaults)


def _make_project(project_id: str = "proj-1") -> ProjectConfig:
    return ProjectConfig(
        id=project_id,
        name="Test Project",
        repo="org/test",
        github=GithubRef(owner="org", repo="test"),
        priority="medium",
        status="active",
        local=LocalPaths(base_path=Path("/tmp/test"), issue_worktree_pattern=""),
    )


def _make_ctx(project_id: str = "proj-1") -> MaintenanceContext:
    return MaintenanceContext(
        root=Path("/tmp"),
        conn=MagicMock(spec=sqlite3.Connection),
        project=_make_project(project_id),
        skill_config={},
        now=datetime(2025, 1, 1, tzinfo=UTC),
        refresh_github=False,
    )


def _noop_execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    return MaintenanceSkillResult(
        skill_id=ctx.project.id,  # placeholder; tests override via custom executor
        project_id=ctx.project.id,
        status="success",
        findings=[],
        summary="ran successfully",
    )


# ---------------------------------------------------------------------------
# _Registry.register()
# ---------------------------------------------------------------------------


class TestRegister:
    def test_valid_skill(self) -> None:
        reg = _Registry()
        spec = _make_spec("valid_skill")
        reg.register(spec, _noop_execute)
        assert reg.get_spec("valid_skill") is spec

    def test_duplicate_raises(self) -> None:
        reg = _Registry()
        spec = _make_spec("dup_skill")
        reg.register(spec, _noop_execute)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(spec, _noop_execute)

    @pytest.mark.parametrize(
        "bad_id",
        [
            "ab",  # too short (2 chars, needs 3-64)
            "UPPER",  # uppercase
            "123abc",  # starts with digit
            "has-dash",  # dash not allowed
            "has.dot",  # dot not allowed
            "",  # empty
            "a" * 65,  # too long
        ],
    )
    def test_invalid_id_raises(self, bad_id: str) -> None:
        reg = _Registry()
        spec = _make_spec(bad_id)
        with pytest.raises(ValueError, match="Invalid skill ID"):
            reg.register(spec, _noop_execute)

    def test_stores_executor(self) -> None:
        reg = _Registry()
        spec = _make_spec("exec_check")

        def exec_check_fn(ctx: MaintenanceContext) -> MaintenanceSkillResult:
            return MaintenanceSkillResult(
                skill_id="exec_check",
                project_id=ctx.project.id,
                status="success",
                findings=[],
                summary="ok",
            )

        reg.register(spec, exec_check_fn)
        ctx = _make_ctx()
        result = reg.execute("exec_check", ctx)
        assert result.status == "success"
        assert result.skill_id == "exec_check"


# ---------------------------------------------------------------------------
# _Registry.get_spec()
# ---------------------------------------------------------------------------


class TestGetSpec:
    def test_found(self) -> None:
        reg = _Registry()
        spec = _make_spec("find_me")
        reg.register(spec, _noop_execute)
        assert reg.get_spec("find_me") is spec

    def test_not_found_returns_none(self) -> None:
        reg = _Registry()
        assert reg.get_spec("nope") is None


# ---------------------------------------------------------------------------
# _Registry.list_specs()
# ---------------------------------------------------------------------------


class TestListSpecs:
    def test_empty(self) -> None:
        reg = _Registry()
        assert reg.list_specs() == []

    def test_multiple_sorted_by_id(self) -> None:
        reg = _Registry()
        for sid in ("zebra", "alpha", "middle"):
            reg.register(_make_spec(sid), _noop_execute)
        ids = [s.id for s in reg.list_specs()]
        assert ids == ["alpha", "middle", "zebra"]

    def test_returns_all_registered(self) -> None:
        reg = _Registry()
        specs = []
        for sid in ("aaa", "bbb", "ccc"):
            s = _make_spec(sid)
            reg.register(s, _noop_execute)
            specs.append(s)
        result_ids = {s.id for s in reg.list_specs()}
        expected_ids = {s.id for s in specs}
        assert result_ids == expected_ids


# ---------------------------------------------------------------------------
# _Registry.execute()
# ---------------------------------------------------------------------------


class TestExecute:
    def test_calls_executor(self) -> None:
        reg = _Registry()
        spec = _make_spec("run_me")

        def executor(ctx: MaintenanceContext) -> MaintenanceSkillResult:
            return MaintenanceSkillResult(
                skill_id="run_me",
                project_id=ctx.project.id,
                status="success",
                findings=[],
                summary="executed",
            )

        reg.register(spec, executor)
        ctx = _make_ctx()
        result = reg.execute("run_me", ctx)
        assert result.status == "success"
        assert result.summary == "executed"

    def test_unknown_skill_returns_blocked(self) -> None:
        reg = _Registry()
        ctx = _make_ctx()
        result = reg.execute("nonexistent", ctx)
        assert result.status == "blocked"
        assert result.reason == "skill_not_registered"
        assert "nonexistent" in result.summary
        assert result.project_id == "proj-1"

    def test_executor_receives_context(self) -> None:
        reg = _Registry()
        spec = _make_spec("ctx_check")
        received: list[MaintenanceContext] = []

        def capture(ctx: MaintenanceContext) -> MaintenanceSkillResult:
            received.append(ctx)
            return MaintenanceSkillResult(
                skill_id="ctx_check",
                project_id=ctx.project.id,
                status="success",
                findings=[],
                summary="ok",
            )

        reg.register(spec, capture)
        ctx = _make_ctx()
        reg.execute("ctx_check", ctx)
        assert len(received) == 1
        assert received[0] is ctx


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


class TestModuleHelpers:
    def test_get_registry_returns_global(self) -> None:
        assert get_registry() is REGISTRY

    def test_get_registry_returns_registry_instance(self) -> None:
        assert isinstance(get_registry(), _Registry)
