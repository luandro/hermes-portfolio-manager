"""Tests for portfolio_manager/config.py — Phase 1: Configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from portfolio_manager.config import (
    ConfigError,
    PortfolioConfig,
    load_projects_config,
    resolve_root,
    select_projects,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# 1.1 resolve_root
# ---------------------------------------------------------------------------


def test_resolve_root_explicit() -> None:
    """Explicit root argument takes highest priority."""
    result = resolve_root("/custom/explicit")
    assert result == Path("/custom/explicit")


def test_resolve_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """AGENT_SYSTEM_ROOT env var is used when no explicit root."""
    monkeypatch.setenv("AGENT_SYSTEM_ROOT", "/from/env")
    result = resolve_root(None)
    assert result == Path("/from/env")


def test_resolve_root_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to /srv/agent-system when nothing else is provided."""
    monkeypatch.delenv("AGENT_SYSTEM_ROOT", raising=False)
    result = resolve_root(None)
    assert result == Path("/srv/agent-system")


# ---------------------------------------------------------------------------
# 1.3 load_projects_config — valid, missing, invalid
# ---------------------------------------------------------------------------


def test_load_valid_config(tmp_path: Path) -> None:
    """Loads a valid projects.yaml and returns a PortfolioConfig."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    valid = FIXTURES / "projects.valid.yaml"
    (config_dir / "projects.yaml").write_text(valid.read_text(), encoding="utf-8")

    cfg = load_projects_config(tmp_path)
    assert isinstance(cfg, PortfolioConfig)
    assert cfg.version == 1
    assert len(cfg.projects) == 4

    # Spot-check first project
    p = cfg.projects[0]
    assert p.id == "comapeo-cloud-app"
    assert p.name == "CoMapeo Cloud App"
    assert p.priority == "high"
    assert p.status == "active"
    assert p.github.owner == "awana-digital"
    assert p.github.repo == "comapeo-cloud-app"


def test_load_missing_config(tmp_path: Path) -> None:
    """Returns ConfigError when projects.yaml is missing."""
    with pytest.raises(ConfigError, match="missing"):
        load_projects_config(tmp_path)


def test_load_invalid_yaml(tmp_path: Path) -> None:
    """Returns ConfigError when YAML is syntactically broken."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects.yaml").write_text("version: 1\nprojects: [\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="parse"):
        load_projects_config(tmp_path)


# ---------------------------------------------------------------------------
# 1.4 Validate required project fields
# ---------------------------------------------------------------------------


def test_required_project_fields(tmp_path: Path) -> None:
    """Rejects a project missing a required field (id)."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    fixture = FIXTURES / "projects.invalid-missing-required.yaml"
    (config_dir / "projects.yaml").write_text(fixture.read_text(), encoding="utf-8")

    with pytest.raises(ConfigError, match="id"):
        load_projects_config(tmp_path)


# ---------------------------------------------------------------------------
# 1.5 Validate priority and status enums
# ---------------------------------------------------------------------------


def test_invalid_status_rejected(tmp_path: Path) -> None:
    """Rejects a project with an invalid status value."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    fixture = FIXTURES / "projects.invalid-status.yaml"
    (config_dir / "projects.yaml").write_text(fixture.read_text(), encoding="utf-8")

    with pytest.raises(ConfigError, match="status"):
        load_projects_config(tmp_path)


def test_invalid_priority_rejected(tmp_path: Path) -> None:
    """Rejects a project with an invalid priority value."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_content = {
        "version": 1,
        "projects": [
            {
                "id": "bad-prio",
                "name": "Bad Priority",
                "repo": "git@github.com:org/repo.git",
                "github": {"owner": "org", "repo": "repo"},
                "priority": "urgent",
                "status": "active",
            }
        ],
    }
    (config_dir / "projects.yaml").write_text(yaml.dump(yaml_content, default_flow_style=False), encoding="utf-8")

    with pytest.raises(ConfigError, match="priority"):
        load_projects_config(tmp_path)


# ---------------------------------------------------------------------------
# 1.6 Reject duplicate project IDs
# ---------------------------------------------------------------------------


def test_duplicate_project_ids_rejected(tmp_path: Path) -> None:
    """Rejects config with duplicate project IDs."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    fixture = FIXTURES / "projects.invalid-duplicate-id.yaml"
    (config_dir / "projects.yaml").write_text(fixture.read_text(), encoding="utf-8")

    with pytest.raises(ConfigError, match="duplicate"):
        load_projects_config(tmp_path)


# ---------------------------------------------------------------------------
# 1.7 Normalize local paths
# ---------------------------------------------------------------------------


def test_normalize_local_paths(tmp_path: Path) -> None:
    """Paths default correctly when not specified in config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yaml_content = {
        "version": 1,
        "projects": [
            {
                "id": "no-local",
                "name": "No Local Config",
                "repo": "git@github.com:org/repo.git",
                "github": {"owner": "org", "repo": "repo"},
                "priority": "medium",
                "status": "active",
            }
        ],
    }
    (config_dir / "projects.yaml").write_text(yaml.dump(yaml_content, default_flow_style=False), encoding="utf-8")

    cfg = load_projects_config(tmp_path)
    project = cfg.projects[0]

    # Defaults should be set
    assert project.local.base_path == tmp_path / "worktrees" / "no-local"
    assert "{issue_number}" in project.local.issue_worktree_pattern
    assert str(tmp_path) in project.local.issue_worktree_pattern

    # Explicit paths should be preserved (from valid fixture)
    valid = FIXTURES / "projects.valid.yaml"
    (config_dir / "projects.yaml").write_text(valid.read_text(), encoding="utf-8")
    cfg2 = load_projects_config(tmp_path)
    first = cfg2.projects[0]
    assert first.local.base_path == Path("/srv/agent-system/worktrees/comapeo-cloud-app")


# ---------------------------------------------------------------------------
# 1.8 Filter and sort projects
# ---------------------------------------------------------------------------


def test_project_filtering_and_sorting(tmp_path: Path) -> None:
    """select_projects filters by status and sorts by priority."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    valid = FIXTURES / "projects.valid.yaml"
    (config_dir / "projects.yaml").write_text(valid.read_text(), encoding="utf-8")

    cfg = load_projects_config(tmp_path)

    # Default: exclude archived
    active = select_projects(cfg)
    ids = [p.id for p in active]
    assert "old-archived-project" not in ids
    assert "comapeo-cloud-app" in ids
    assert "edt-next" in ids
    # paused is excluded by default too
    assert "docs-support-bot" not in ids

    # Include archived
    with_archived = select_projects(cfg, include_archived=True)
    assert "old-archived-project" in [p.id for p in with_archived]

    # Include paused
    with_paused = select_projects(cfg, include_paused=True)
    assert "docs-support-bot" in [p.id for p in with_paused]

    # Filter by status
    paused_only = select_projects(cfg, status="paused", include_paused=True)
    assert len(paused_only) == 1
    assert paused_only[0].id == "docs-support-bot"

    # Sort order: high > medium > low > paused (critical first if present)
    sorted_projects = select_projects(cfg, include_archived=True, include_paused=True)
    priorities = [p.priority for p in sorted_projects]
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "paused": 4}
    indices = [priority_order[p] for p in priorities]
    assert indices == sorted(indices), f"Priorities not sorted: {priorities}"
