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
