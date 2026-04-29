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
    get_effective_config,
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


def _write_projects_config(root: Path, project_id: str = "proj-1") -> None:
    cp = root / "config" / "projects.yaml"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(
        "version: 1\n"
        "projects:\n"
        f"  - id: {project_id}\n"
        f"    name: {project_id}\n"
        f"    repo: https://github.com/test/{project_id}\n"
        "    github:\n"
        "      owner: test\n"
        f"      repo: {project_id}\n"
        "    priority: medium\n"
        "    status: active\n",
        encoding="utf-8",
    )


class TestLoadConfig:
    def test_returns_defaults_when_no_file(self, root: Path) -> None:
        cfg = load_config(root)
        assert "skills" in cfg
        assert "untriaged_issue_digest" in cfg["skills"]

    def test_loads_existing_file(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        custom = {"skills": {"untriaged_issue_digest": {"enabled": True, "interval_hours": 48}}}
        with open(cp, "w") as f:
            yaml.dump(custom, f)
        cfg = load_config(root)
        assert cfg["skills"]["untriaged_issue_digest"]["enabled"] is True

    def test_returns_defaults_for_empty_file(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("")
        cfg = load_config(root)
        assert "skills" in cfg


class TestSaveConfig:
    def test_creates_file(self, root: Path) -> None:
        cfg = {"skills": {"untriaged_issue_digest": {"enabled": True}}}
        result = save_config(root, cfg)
        assert result.is_file()
        loaded = load_config(root)
        assert loaded["skills"]["untriaged_issue_digest"]["enabled"] is True

    def test_creates_backup(self, root: Path) -> None:
        # Save once
        save_config(root, {"skills": {"untriaged_issue_digest": {"enabled": True}}})
        # Save again
        save_config(root, {"skills": {"untriaged_issue_digest": {"enabled": False}}})
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
        with pytest.raises(ValueError, match="Unknown maintenance skill"):
            get_skill_config(root, "nonexistent_skill")

    def test_project_override_wins_over_global_skill_config(self, root: Path) -> None:
        _write_projects_config(root)
        save_config(
            root,
            {
                "defaults": {"create_issue_drafts": False},
                "skills": {
                    "stale_issue_digest": {
                        "enabled": True,
                        "interval_hours": 168,
                        "stale_after_days": 30,
                    }
                },
                "projects": {
                    "proj-1": {
                        "skills": {
                            "stale_issue_digest": {
                                "stale_after_days": 21,
                                "create_issue_drafts": True,
                            }
                        }
                    }
                },
            },
        )

        cfg = get_effective_config(root, "stale_issue_digest", project_id="proj-1")

        assert cfg["enabled"] is True
        assert cfg["interval_hours"] == 168
        assert cfg["stale_after_days"] == 21
        assert cfg["create_issue_drafts"] is True

    def test_tool_overrides_apply_only_to_effective_config(self, root: Path) -> None:
        save_config(root, {"skills": {"untriaged_issue_digest": {"max_findings": 10}}})

        effective = get_effective_config(
            root,
            "untriaged_issue_digest",
            tool_overrides={"max_findings": 2},
        )
        persisted = get_effective_config(root, "untriaged_issue_digest")

        assert effective["max_findings"] == 2
        assert persisted["max_findings"] == 10

    def test_unknown_skill_blocks_validation(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("skills:\n  unknown_skill:\n    enabled: true\n", encoding="utf-8")

        with pytest.raises(ValueError, match="unknown maintenance skill"):
            load_config(root)

    def test_x_extension_skill_is_allowed(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text("skills:\n  x_vendor_extension:\n    custom: true\n", encoding="utf-8")

        cfg = load_config(root)

        assert cfg["skills"]["x_vendor_extension"]["custom"] is True

    def test_unknown_project_blocks_validation(self, root: Path) -> None:
        _write_projects_config(root, "known-project")
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            "projects:\n  missing-project:\n    skills:\n      untriaged_issue_digest:\n        enabled: true\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="unknown project_id"):
            load_config(root)

    def test_invalid_interval_blocks_validation(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            "skills:\n  untriaged_issue_digest:\n    interval_hours: 2161\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="between 1 and 2160"):
            load_config(root)

    def test_unknown_config_key_blocks_validation(self, root: Path) -> None:
        cp = config_path(root)
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(
            "skills:\n  untriaged_issue_digest:\n    unsupported: true\n",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="unknown config keys"):
            load_config(root)


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

    def test_enable_unknown_skill_blocks(self, root: Path) -> None:
        with pytest.raises(ValueError, match="Unknown maintenance skill"):
            enable_skill(root, "custom_skill")

    def test_enable_project_override_preserves_unknown_fields(self, root: Path) -> None:
        _write_projects_config(root)
        save_config(
            root,
            {
                "x_top": {"keep": True},
                "projects": {
                    "proj-1": {
                        "notes": "preserve me",
                        "skills": {
                            "stale_issue_digest": {
                                "enabled": False,
                            }
                        },
                    }
                },
            },
        )

        enable_skill(root, "stale_issue_digest", project_id="proj-1", config={"stale_after_days": 14})
        raw = yaml.safe_load(config_path(root).read_text(encoding="utf-8"))

        assert raw["x_top"] == {"keep": True}
        assert raw["projects"]["proj-1"]["notes"] == "preserve me"
        assert raw["projects"]["proj-1"]["skills"]["stale_issue_digest"]["enabled"] is True
        assert raw["projects"]["proj-1"]["skills"]["stale_issue_digest"]["stale_after_days"] == 14

    def test_disable_project_override(self, root: Path) -> None:
        _write_projects_config(root)

        cfg = disable_skill(root, "untriaged_issue_digest", project_id="proj-1")

        assert cfg["projects"]["proj-1"]["skills"]["untriaged_issue_digest"]["enabled"] is False
        effective = get_effective_config(root, "untriaged_issue_digest", project_id="proj-1")
        assert effective["enabled"] is False
