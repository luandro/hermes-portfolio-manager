"""Tests for Phase 1 — Project Admin Data Models and Validation."""

from __future__ import annotations

import tomllib
import warnings
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# a) Dependency declaration
# ---------------------------------------------------------------------------


def test_mvp2_dependency_choices_are_declared() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    deps = data["project"]["dependencies"]
    assert "pyyaml>=6" in deps
    assert "pydantic>=2" in deps


# ---------------------------------------------------------------------------
# b) Model preserves optional and unknown fields
# ---------------------------------------------------------------------------


def test_project_model_preserves_optional_and_unknown_fields() -> None:
    from portfolio_manager.admin_models import AdminPortfolioConfig, AdminProjectConfig

    project = AdminProjectConfig(
        id="edt-next",
        name="EDT Next",
        repo="git@github.com:awana-digital/edt-next.git",
        github_owner="awana-digital",
        github_repo="edt-next",
        priority="medium",
        status="active",
        default_branch="auto",
        auto_merge={"enabled": True, "max_risk": "low"},
        notes="Some notes",
        created_by="luandro",
        labels=["frontend", "urgent"],
        protected_paths=[".github/workflows/**"],
    )

    assert project.id == "edt-next"
    assert project.name == "EDT Next"
    assert project.auto_merge.enabled is True
    assert project.auto_merge.max_risk == "low"
    assert project.notes == "Some notes"
    assert project.labels == ["frontend", "urgent"]

    # Unknown fields retained via extra="allow"
    project_extra = AdminProjectConfig(
        id="edt-next",
        name="EDT Next",
        repo="git@github.com:awana-digital/edt-next.git",
        github_owner="awana-digital",
        github_repo="edt-next",
        custom_field="value",  # type: ignore[call-arg]
    )
    assert project_extra.model_extra is not None
    assert project_extra.model_extra.get("custom_field") == "value"

    # Top-level config also retains unknown fields
    portfolio = AdminPortfolioConfig(
        version=1,
        projects=[],
        some_top_level="yes",  # type: ignore[call-arg]
    )
    assert portfolio.model_extra is not None
    assert portfolio.model_extra.get("some_top_level") == "yes"


# ---------------------------------------------------------------------------
# c) Project ID validation
# ---------------------------------------------------------------------------


def test_project_id_validation() -> None:
    from portfolio_manager.admin_models import validate_project_id

    valid_ids = ["comapeo-cloud-app", "edt-next", "docs2"]
    for vid in valid_ids:
        validate_project_id(vid)  # should not raise

    invalid_ids = ["../escape", ".project", "ProjectName", "project_name", "project/", "-project", "project-", ""]
    for iid in invalid_ids:
        with pytest.raises(ValueError, match="Invalid project ID"):
            validate_project_id(iid)


# ---------------------------------------------------------------------------
# d) Auto-merge policy validation
# ---------------------------------------------------------------------------


def test_auto_merge_policy_validation() -> None:
    from portfolio_manager.admin_models import validate_auto_merge

    # 1. None/missing → enabled=False
    cfg1 = validate_auto_merge(enabled=False)
    assert cfg1.enabled is False
    assert cfg1.max_risk is None

    # 2. enabled=False → valid
    cfg2 = validate_auto_merge(enabled=False)
    assert cfg2.enabled is False

    # 3. enabled=True, max_risk=low → valid
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        cfg3 = validate_auto_merge(enabled=True, max_risk="low")
    assert cfg3.max_risk == "low"

    # 4. enabled=True, max_risk=medium → valid
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        cfg4 = validate_auto_merge(enabled=True, max_risk="medium")
    assert cfg4.max_risk == "medium"

    # 5. enabled=True, max_risk=high → ValueError
    with pytest.raises(ValueError), warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        validate_auto_merge(enabled=True, max_risk="high")

    # 6. enabled=True, max_risk=critical → ValueError
    with pytest.raises(ValueError), warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        validate_auto_merge(enabled=True, max_risk="critical")

    # 7. enabled=True, no max_risk → defaults to low
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        cfg7 = validate_auto_merge(enabled=True)
    assert cfg7.max_risk == "low"

    # Warning about MVP 2 storing policy only
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", UserWarning)
        validate_auto_merge(enabled=True)
    assert any("MVP 2" in str(warning.message) for warning in w)


# ---------------------------------------------------------------------------
# e) Priority and status mutation validation
# ---------------------------------------------------------------------------


def test_priority_and_status_mutation_validation() -> None:
    from portfolio_manager.admin_models import validate_priority, validate_status

    valid_priorities = ["critical", "high", "medium", "low", "paused"]
    for p in valid_priorities:
        validate_priority(p)

    invalid_priorities = ["very-high", ""]
    for p in invalid_priorities:
        with pytest.raises(ValueError):
            validate_priority(p)

    valid_statuses = ["active", "paused", "archived", "blocked", "missing"]
    for s in valid_statuses:
        validate_status(s)

    invalid_statuses = ["deleted", ""]
    for s in invalid_statuses:
        with pytest.raises(ValueError):
            validate_status(s)


# ---------------------------------------------------------------------------
# f) Project local path normalization
# ---------------------------------------------------------------------------


def test_project_local_path_normalization() -> None:
    from portfolio_manager.admin_models import (
        expand_user_path,
        project_base_path,
        serialize_path_for_config,
    )

    home = Path.home()

    # Paths under home serialize as ~/...
    result = serialize_path_for_config(home / ".agent-system" / "worktrees")
    assert result.startswith("~/")
    assert ".agent-system" in result

    # expand_user_path expands ~ correctly
    expanded = expand_user_path("~/.agent-system")
    assert expanded == home / ".agent-system"
    assert not str(expanded).startswith("~")

    # Project ID cannot influence paths outside root
    root = Path("/tmp/fake-root")
    base = project_base_path(root, "my-project")
    assert base.startswith(str(root))

    with pytest.raises(ValueError):
        project_base_path(root, "../escape")


# ---------------------------------------------------------------------------
# g) Default protected paths
# ---------------------------------------------------------------------------


def test_default_protected_paths() -> None:
    from portfolio_manager.admin_models import get_default_protected_paths

    defaults = get_default_protected_paths()
    assert defaults == [
        ".github/workflows/**",
        "infra/**",
        "auth/**",
        "security/**",
        "migrations/**",
    ]

    # User-provided override replaces defaults
    from portfolio_manager.admin_models import AdminProjectConfig

    custom = AdminProjectConfig(
        id="test-proj",
        name="Test",
        repo="git@github.com:test/test.git",
        github_owner="test",
        github_repo="test",
        protected_paths=["custom/**"],
    )
    assert custom.protected_paths == ["custom/**"]


# ===========================================================================
# Phase 3 — Pure Project Mutation Functions
# ===========================================================================


# ---------------------------------------------------------------------------
# h) add_project_to_config — empty config
# ---------------------------------------------------------------------------


def test_add_project_to_empty_config() -> None:
    from portfolio_manager.admin_functions import add_project_to_config
    from portfolio_manager.admin_models import AdminProjectConfig

    empty_config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )

    result = add_project_to_config(empty_config, project)

    # Original unchanged (pure function)
    assert empty_config["projects"] == []

    assert len(result["projects"]) == 1
    p = result["projects"][0]
    assert p["id"] == "edt-next"
    assert p["name"] == "EDT"
    assert p["repo"] == "git@github.com:a/b.git"
    assert p["github"] == {"owner": "a", "repo": "b"}
    # Defaults
    assert p["priority"] == "medium"
    assert p["status"] == "active"
    assert p["default_branch"] == "auto"
    assert p["auto_merge"]["enabled"] is False
    # Default protected paths applied
    assert ".github/workflows/**" in p["protected_paths"]
    assert "migrations/**" in p["protected_paths"]
    # Timestamps set
    assert p["created_at"] is not None
    assert p["updated_at"] is not None


# ---------------------------------------------------------------------------
# i) add_project_to_config — existing config
# ---------------------------------------------------------------------------


def test_add_project_to_existing_config() -> None:
    from portfolio_manager.admin_functions import add_project_to_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {
        "version": 1,
        "projects": [
            {"id": "proj-a", "name": "A", "github": {"owner": "x", "repo": "a"}},
            {"id": "proj-b", "name": "B", "github": {"owner": "x", "repo": "b"}},
        ],
    }

    new_project = AdminProjectConfig(
        id="proj-c",
        name="C",
        repo="git@github.com:x/c.git",
        github_owner="x",
        github_repo="c",
    )
    result = add_project_to_config(config, new_project)

    # Existing preserved
    assert len(result["projects"]) == 3
    assert result["projects"][0]["id"] == "proj-a"
    assert result["projects"][1]["id"] == "proj-b"
    assert result["projects"][2]["id"] == "proj-c"

    # Extra fields preserved via extra="allow"
    project_with_extra = AdminProjectConfig(
        id="proj-d",
        name="D",
        repo="git@github.com:x/d.git",
        github_owner="x",
        github_repo="d",
        custom_field="hello",  # type: ignore[call-arg]
    )
    result2 = add_project_to_config(result, project_with_extra)
    proj_d = result2["projects"][3]
    assert proj_d["custom_field"] == "hello"


# ---------------------------------------------------------------------------
# j) add_project_to_config — rejects duplicate ID
# ---------------------------------------------------------------------------


def test_add_rejects_duplicate_project_id() -> None:
    from portfolio_manager.admin_functions import add_project_to_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {
        "version": 1,
        "projects": [
            {"id": "edt-next", "name": "EDT", "github": {"owner": "a", "repo": "b"}},
        ],
    }
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT Duplicate",
        repo="git@github.com:a/b2.git",
        github_owner="a",
        github_repo="b2",
    )

    with pytest.raises(ValueError, match="duplicate_project_id"):
        add_project_to_config(config, project)


# ---------------------------------------------------------------------------
# k) add_project_to_config — rejects duplicate github repo
# ---------------------------------------------------------------------------


def test_add_rejects_duplicate_github_repo() -> None:
    from portfolio_manager.admin_functions import add_project_to_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {
        "version": 1,
        "projects": [
            {"id": "proj-a", "name": "A", "github": {"owner": "x", "repo": "y"}},
        ],
    }
    project = AdminProjectConfig(
        id="proj-b",
        name="B",
        repo="git@github.com:x/y.git",
        github_owner="x",
        github_repo="y",
    )

    with pytest.raises(ValueError, match="duplicate_github_repo"):
        add_project_to_config(config, project)


# ---------------------------------------------------------------------------
# l) update_project_in_config — field updates
# ---------------------------------------------------------------------------


def test_update_project_fields() -> None:
    import time

    from portfolio_manager.admin_functions import add_project_to_config, update_project_in_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)
    original_updated = cfg["projects"][0]["updated_at"]

    # Small delay so updated_at changes
    time.sleep(0.01)

    updated = update_project_in_config(
        cfg,
        "edt-next",
        {
            "priority": "high",
            "status": "blocked",
            "name": "EDT Next",
            "default_branch": "main",
            "auto_merge": {"enabled": True, "max_risk": "low"},
        },
    )

    p = updated["projects"][0]
    assert p["priority"] == "high"
    assert p["status"] == "blocked"
    assert p["name"] == "EDT Next"
    assert p["default_branch"] == "main"
    assert p["auto_merge"]["enabled"] is True
    assert p["auto_merge"]["max_risk"] == "low"
    # updated_at changed
    assert p["updated_at"] != original_updated
    # Original config untouched
    assert cfg["projects"][0]["name"] == "EDT"

    # Unknown fields preserved: inject one, then update a known field
    cfg["projects"][0]["custom_stuff"] = "keep me"
    updated2 = update_project_in_config(cfg, "edt-next", {"priority": "low"})
    assert updated2["projects"][0]["custom_stuff"] == "keep me"


# ---------------------------------------------------------------------------
# m) update_project_in_config — rejects no fields
# ---------------------------------------------------------------------------


def test_update_rejects_no_fields() -> None:
    from portfolio_manager.admin_functions import update_project_in_config

    config: dict = {
        "version": 1,
        "projects": [{"id": "edt-next", "name": "EDT"}],
    }

    with pytest.raises(ValueError, match="no_update_fields"):
        update_project_in_config(config, "edt-next", {})


# ---------------------------------------------------------------------------
# n) pause_project_in_config
# ---------------------------------------------------------------------------


def test_pause_project() -> None:
    from portfolio_manager.admin_functions import add_project_to_config, pause_project_in_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)
    original_updated = cfg["projects"][0]["updated_at"]

    result = pause_project_in_config(cfg, "edt-next", reason="travel")
    p = result["projects"][0]
    assert p["status"] == "paused"
    assert "travel" in p["notes"]
    assert p["updated_at"] != original_updated


# ---------------------------------------------------------------------------
# o) resume_project_in_config
# ---------------------------------------------------------------------------


def test_resume_project() -> None:
    from portfolio_manager.admin_functions import (
        add_project_to_config,
        pause_project_in_config,
        resume_project_in_config,
    )
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)
    paused = pause_project_in_config(cfg, "edt-next", reason="travel")
    assert paused["projects"][0]["status"] == "paused"

    resumed = resume_project_in_config(paused, "edt-next")
    p = resumed["projects"][0]
    assert p["status"] == "active"
    assert p["updated_at"] != paused["projects"][0]["updated_at"]


# ---------------------------------------------------------------------------
# p) archive_project_in_config
# ---------------------------------------------------------------------------


def test_archive_project() -> None:
    from portfolio_manager.admin_functions import add_project_to_config, archive_project_in_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)

    result = archive_project_in_config(cfg, "edt-next", reason="end of life")
    p = result["projects"][0]
    assert p["status"] == "archived"
    assert "end of life" in p["notes"]
    assert p["updated_at"] != cfg["projects"][0]["updated_at"]


# ---------------------------------------------------------------------------
# q) remove_project_from_config — requires confirmation
# ---------------------------------------------------------------------------


def test_remove_project_requires_confirmation() -> None:
    from portfolio_manager.admin_functions import add_project_to_config, remove_project_from_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)

    # Without confirm — raises
    with pytest.raises(ValueError, match="confirm"):
        remove_project_from_config(cfg, "edt-next", confirm=False)

    # Project still there
    assert len(cfg["projects"]) == 1

    # With confirm — removes
    result = remove_project_from_config(cfg, "edt-next", confirm=True)
    assert len(result["projects"]) == 0
    # Original untouched
    assert len(cfg["projects"]) == 1


# ---------------------------------------------------------------------------
# r) set_project_priority_in_config
# ---------------------------------------------------------------------------


def test_set_project_priority() -> None:
    from portfolio_manager.admin_functions import add_project_to_config, set_project_priority_in_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)

    # Valid priorities
    for prio in ("critical", "high", "medium", "low"):
        result = set_project_priority_in_config(cfg, "edt-next", prio)
        assert result["projects"][0]["priority"] == prio

    # priority="paused" also sets status="paused"
    result = set_project_priority_in_config(cfg, "edt-next", "paused")
    assert result["projects"][0]["priority"] == "paused"
    assert result["projects"][0]["status"] == "paused"

    # Invalid priority fails
    with pytest.raises(ValueError, match="Invalid priority"):
        set_project_priority_in_config(cfg, "edt-next", "ultra-high")


# ---------------------------------------------------------------------------
# s) set_project_auto_merge_in_config
# ---------------------------------------------------------------------------


def test_set_project_auto_merge() -> None:
    import warnings

    from portfolio_manager.admin_functions import add_project_to_config, set_project_auto_merge_in_config
    from portfolio_manager.admin_models import AdminProjectConfig

    config: dict = {"version": 1, "projects": []}
    project = AdminProjectConfig(
        id="edt-next",
        name="EDT",
        repo="git@github.com:a/b.git",
        github_owner="a",
        github_repo="b",
    )
    cfg = add_project_to_config(config, project)

    # Disable auto-merge
    result = set_project_auto_merge_in_config(cfg, "edt-next", enabled=False)
    assert result["projects"][0]["auto_merge"]["enabled"] is False

    # Enable with default (max_risk defaults to "low")
    result = set_project_auto_merge_in_config(cfg, "edt-next", enabled=True)
    assert result["projects"][0]["auto_merge"]["enabled"] is True
    assert result["projects"][0]["auto_merge"]["max_risk"] == "low"

    # Enable with max_risk=medium
    result = set_project_auto_merge_in_config(cfg, "edt-next", enabled=True, max_risk="medium")
    assert result["projects"][0]["auto_merge"]["max_risk"] == "medium"

    # Reject high/critical
    with pytest.raises(ValueError):
        set_project_auto_merge_in_config(cfg, "edt-next", enabled=True, max_risk="high")
    with pytest.raises(ValueError):
        set_project_auto_merge_in_config(cfg, "edt-next", enabled=True, max_risk="critical")

    # Warning about MVP 2 policy-only
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", UserWarning)
        set_project_auto_merge_in_config(cfg, "edt-next", enabled=True)
    assert any("MVP 2" in str(warning.message) for warning in w)
