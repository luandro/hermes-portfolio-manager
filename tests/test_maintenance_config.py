"""Tests for MVP 4 maintenance config (Tasks 1.4-1.5)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import yaml

from portfolio_manager.maintenance_config import (
    backup_dir,
    config_path,
    disable_skill,
    enable_skill,
    get_skill_config,
    load_config,
    save_config,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    """Provide a temp root directory."""
    return tmp_path


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, root: Path) -> None:
        cfg = load_config(root)
        assert "skills" in cfg
        assert "untriaged_issue_digest" in cfg["skills"]

    def test_loads_existing_file(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        custom = {"skills": {"my_skill": {"enabled": True, "interval_hours": 48}}}
        with open(cp, "w") as f:
            yaml.dump(custom, f)
        cfg = load_config(root)
        assert cfg["skills"]["my_skill"]["enabled"] is True

    def test_returns_defaults_for_empty_file(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("")
        cfg = load_config(root)
        assert "skills" in cfg


class TestSaveConfig:
    def test_creates_file(self, root: Path) -> None:
        cfg = {"skills": {"test_skill": {"enabled": True}}}
        result = save_config(root, cfg)
        assert result.is_file()
        loaded = load_config(root)
        assert loaded["skills"]["test_skill"]["enabled"] is True

    def test_creates_backup(self, root: Path) -> None:
        # Save once
        save_config(root, {"skills": {"s1": {"enabled": True}}})
        # Save again
        save_config(root, {"skills": {"s1": {"enabled": False}}})
        bd = backup_dir(root)
        backups = list(bd.glob("maintenance-*.yaml"))
        assert len(backups) >= 1


class TestGetSkillConfig:
    def test_returns_defaults_for_known_skill(self, root: Path) -> None:
        cfg = get_skill_config(root, "untriaged_issue_digest")
        assert cfg["enabled"] is True
        assert cfg["interval_hours"] == 24

    def test_merges_overrides(self, root: Path) -> None:
        # Save custom config with override
        custom = {"skills": {"untriaged_issue_digest": {"interval_hours": 48}}}
        save_config(root, custom)
        cfg = get_skill_config(root, "untriaged_issue_digest")
        assert cfg["interval_hours"] == 48
        assert cfg["enabled"] is True  # from defaults

    def test_empty_overrides_for_unknown_skill(self, root: Path) -> None:
        cfg = get_skill_config(root, "nonexistent_skill")
        assert cfg == {}


class TestEnableDisableSkill:
    def test_enable_skill(self, root: Path) -> None:
        cfg = enable_skill(root, "untriaged_issue_digest")
        assert cfg["skills"]["untriaged_issue_digest"]["enabled"] is True
        # Verify persisted
        loaded = load_config(root)
        assert loaded["skills"]["untriaged_issue_digest"]["enabled"] is True

    def test_enable_skill_with_interval(self, root: Path) -> None:
        cfg = enable_skill(root, "untriaged_issue_digest", interval_hours=48)
        assert cfg["skills"]["untriaged_issue_digest"]["interval_hours"] == 48

    def test_disable_skill(self, root: Path) -> None:
        cfg = disable_skill(root, "untriaged_issue_digest")
        assert cfg["skills"]["untriaged_issue_digest"]["enabled"] is False
        # Verify persisted
        loaded = load_config(root)
        assert loaded["skills"]["untriaged_issue_digest"]["enabled"] is False

    def test_enable_new_skill(self, root: Path) -> None:
        cfg = enable_skill(root, "custom_skill")
        assert cfg["skills"]["custom_skill"]["enabled"] is True
