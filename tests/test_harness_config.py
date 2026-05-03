"""Tests for portfolio_manager/harness_config.py — Task 2.1."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
import yaml

from portfolio_manager.config import ConfigError
from portfolio_manager.harness_config import (
    MAX_TIMEOUT,
    HarnessCheckConfig,
    HarnessConfig,
    get_harness,
    load_harness_config,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_harnesses_yaml(root: Path, data: dict) -> Path:
    """Write data as YAML to ``$root/config/harnesses.yaml`` and return root."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "harnesses.yaml").write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return root


def _valid_harness_dict(**overrides) -> dict:
    """Return a minimal valid harness entry dict with optional overrides."""
    entry = {
        "id": "forge",
        "command": ["forge", "run"],
        "env_passthrough": ["OPENAI_API_KEY"],
        "timeout_seconds": 1800,
        "max_files_changed": 20,
        "required_checks": ["unit_tests", "lint"],
        "checks": {
            "unit_tests": {
                "command": ["uv", "run", "pytest"],
                "timeout_seconds": 600,
            },
            "lint": {
                "command": ["uv", "run", "ruff", "check", "."],
                "timeout_seconds": 300,
            },
        },
        "workspace_subpath": None,
    }
    entry.update(overrides)
    return entry


def _valid_config(**harness_overrides) -> dict:
    """Return a valid harnesses.yaml top-level dict."""
    return {"harnesses": [_valid_harness_dict(**harness_overrides)]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadHarnessesYaml:
    """test_load_harnesses_yaml_returns_validated_models"""

    def test_load_harnesses_yaml_returns_validated_models(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config())
        result = load_harness_config(root)

        assert "forge" in result
        harness = result["forge"]
        assert isinstance(harness, HarnessConfig)
        assert harness.id == "forge"
        assert harness.command == ["forge", "run"]
        assert harness.env_passthrough == ["OPENAI_API_KEY"]
        assert harness.timeout_seconds == 1800
        assert harness.max_files_changed == 20
        assert harness.required_checks == ["unit_tests", "lint"]
        assert isinstance(harness.checks["unit_tests"], HarnessCheckConfig)
        assert harness.checks["unit_tests"].command == ["uv", "run", "pytest"]
        assert harness.checks["unit_tests"].timeout_seconds == 600
        assert harness.workspace_subpath is None

    def test_missing_harnesses_yaml_returns_empty_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="portfolio_manager.harness_config"):
            result = load_harness_config(tmp_path)

        assert result == {}
        assert "not found" in caplog.text

    def test_invalid_yaml_raises_config_error(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True)
        (config_dir / "harnesses.yaml").write_text("{{{{invalid yaml", encoding="utf-8")

        with pytest.raises(ConfigError, match="Failed to parse"):
            load_harness_config(tmp_path)


class TestHarnessCommandValidation:
    """test_harness_must_define_command_array_no_shell_string"""

    def test_harness_must_define_command_array_no_shell_string(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(command="forge run --all"))
        with pytest.raises(ConfigError, match="command must be a list"):
            load_harness_config(root)

    def test_harness_command_path_must_be_absolute_or_basename_only_no_traversal(self, tmp_path: Path) -> None:
        # Relative path with slash is rejected
        root = _write_harnesses_yaml(tmp_path, _valid_config(command=["../bin/forge", "run"]))
        with pytest.raises(ConfigError, match="basename or absolute path"):
            load_harness_config(root)

    def test_harness_command_rejects_shell_metacharacters(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(command=["forge; rm -rf /"]))
        with pytest.raises(ConfigError, match="shell metacharacters"):
            load_harness_config(root)

    def test_harness_command_rejects_empty_element(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(command=["forge", ""]))
        with pytest.raises(ConfigError, match="must not be empty"):
            load_harness_config(root)

    def test_harness_command_rejects_empty_list(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(command=[]))
        with pytest.raises(ConfigError, match="must not be empty"):
            load_harness_config(root)

    def test_harness_command_accepts_absolute_path(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(command=["/usr/bin/forge", "run"]))
        result = load_harness_config(root)
        assert result["forge"].command == ["/usr/bin/forge", "run"]


class TestHarnessTimeoutSeconds:
    """test_harness_timeout_seconds_required_positive_int_under_max"""

    def test_harness_timeout_seconds_required_positive_int_under_max(self, tmp_path: Path) -> None:
        # Zero is rejected
        root = _write_harnesses_yaml(tmp_path, _valid_config(timeout_seconds=0))
        with pytest.raises(ConfigError, match=r"timeout_seconds.*positive"):
            load_harness_config(root)

    def test_harness_timeout_rejects_negative(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(timeout_seconds=-1))
        with pytest.raises(ConfigError, match=r"timeout_seconds.*positive"):
            load_harness_config(root)

    def test_harness_timeout_rejects_over_max(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(timeout_seconds=MAX_TIMEOUT + 1))
        with pytest.raises(ConfigError, match=f"must be <= {MAX_TIMEOUT}"):
            load_harness_config(root)

    def test_harness_timeout_accepts_max(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(timeout_seconds=MAX_TIMEOUT))
        result = load_harness_config(root)
        assert result["forge"].timeout_seconds == MAX_TIMEOUT


class TestHarnessMaxFilesChanged:
    """test_harness_max_files_changed_required"""

    def test_harness_max_files_changed_required(self, tmp_path: Path) -> None:
        entry = _valid_harness_dict()
        del entry["max_files_changed"]
        root = _write_harnesses_yaml(tmp_path, {"harnesses": [entry]})
        with pytest.raises(ConfigError, match=r"max_files_changed.*positive"):
            load_harness_config(root)

    def test_harness_max_files_changed_rejects_zero(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(max_files_changed=0))
        with pytest.raises(ConfigError, match=r"max_files_changed.*positive"):
            load_harness_config(root)


class TestHarnessRequiredChecks:
    """test_harness_required_checks_must_be_array_of_allowlisted_check_ids"""

    def test_harness_required_checks_must_be_array_of_allowlisted_check_ids(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(
            tmp_path,
            _valid_config(
                required_checks=["unit_tests", "dangerous_check"],
                checks={
                    "unit_tests": {
                        "command": ["uv", "run", "pytest"],
                        "timeout_seconds": 600,
                    },
                    "dangerous_check": {
                        "command": ["run-danger"],
                        "timeout_seconds": 60,
                    },
                },
            ),
        )
        with pytest.raises(ConfigError, match="must be one of"):
            load_harness_config(root)

    def test_harness_required_checks_accepts_valid_ids(self, tmp_path: Path) -> None:
        checks = {
            "unit_tests": {"command": ["pytest"], "timeout_seconds": 300},
            "lint": {"command": ["ruff", "check"], "timeout_seconds": 60},
        }
        root = _write_harnesses_yaml(tmp_path, _valid_config(required_checks=["unit_tests", "lint"], checks=checks))
        result = load_harness_config(root)
        assert result["forge"].required_checks == ["unit_tests", "lint"]


class TestHarnessChecksMapping:
    """test_harness_checks_must_be_mapping_of_check_ids_to_command_arrays"""

    def test_harness_checks_must_be_mapping_of_check_ids_to_command_arrays(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(checks="not a mapping"))
        with pytest.raises(ConfigError, match=r"checks.*must be a mapping"):
            load_harness_config(root)

    def test_harness_checks_entry_must_be_mapping(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(
            tmp_path,
            _valid_config(checks={"unit_tests": "not a mapping"}),
        )
        with pytest.raises(ConfigError, match="must be a mapping"):
            load_harness_config(root)


class TestRequiredChecksReferenceDefined:
    """test_required_checks_must_reference_defined_checks"""

    def test_required_checks_must_reference_defined_checks(self, tmp_path: Path) -> None:
        # "lint" is in ALLOWED_CHECK_IDS but not defined in checks mapping
        root = _write_harnesses_yaml(
            tmp_path,
            _valid_config(
                required_checks=["unit_tests", "lint"],
                checks={
                    "unit_tests": {
                        "command": ["pytest"],
                        "timeout_seconds": 300,
                    },
                    # "lint" is NOT in checks
                },
            ),
        )
        with pytest.raises(ConfigError, match="not defined in checks"):
            load_harness_config(root)


class TestCheckTimeoutSeconds:
    """test_check_timeout_seconds_required_positive_int_under_max"""

    def test_check_timeout_seconds_required_positive_int_under_max(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(
            tmp_path,
            _valid_config(
                checks={
                    "unit_tests": {
                        "command": ["pytest"],
                        "timeout_seconds": 0,
                    },
                },
                required_checks=["unit_tests"],
            ),
        )
        with pytest.raises(ConfigError, match=r"timeout_seconds.*positive"):
            load_harness_config(root)

    def test_check_timeout_rejects_over_max(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(
            tmp_path,
            _valid_config(
                checks={
                    "unit_tests": {
                        "command": ["pytest"],
                        "timeout_seconds": MAX_TIMEOUT + 1,
                    },
                },
                required_checks=["unit_tests"],
            ),
        )
        with pytest.raises(ConfigError, match=f"must be <= {MAX_TIMEOUT}"):
            load_harness_config(root)


class TestGetHarnessById:
    """test_get_harness_by_id_returns_typed_model"""

    def test_get_harness_by_id_returns_typed_model(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config())
        harness = get_harness(root, "forge")
        assert harness is not None
        assert isinstance(harness, HarnessConfig)
        assert harness.id == "forge"

    def test_get_harness_by_id_unknown_returns_none(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config())
        result = get_harness(root, "nonexistent")
        assert result is None


class TestHarnessIdField:
    """test_harness_id_field_must_match_HARNESS_ID_RE"""

    def test_harness_id_field_must_match_HARNESS_ID_RE(self, tmp_path: Path) -> None:
        # Uppercase is rejected by HARNESS_ID_RE
        root = _write_harnesses_yaml(tmp_path, _valid_config(id="FORGE"))
        with pytest.raises(ConfigError, match="invalid id"):
            load_harness_config(root)

    def test_harness_id_rejects_path_separator(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(id="forge/evil"))
        with pytest.raises(ConfigError, match="invalid id"):
            load_harness_config(root)

    def test_harness_id_rejects_shell_metachar(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(id="forge;rm"))
        with pytest.raises(ConfigError, match="invalid id"):
            load_harness_config(root)

    def test_harness_id_accepts_valid_alnum_dash_underscore(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(id="forge-v2_beta"))
        result = load_harness_config(root)
        assert "forge-v2_beta" in result


class TestWorkspaceSubpath:
    """Additional coverage for workspace_subpath validation."""

    def test_workspace_subpath_rejects_dotdot(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(workspace_subpath="../escape"))
        with pytest.raises(ConfigError, match="must not contain"):
            load_harness_config(root)

    def test_workspace_subpath_rejects_absolute(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(workspace_subpath="/tmp/evil"))
        with pytest.raises(ConfigError, match="must be a relative path"):
            load_harness_config(root)

    def test_workspace_subpath_accepts_relative(self, tmp_path: Path) -> None:
        root = _write_harnesses_yaml(tmp_path, _valid_config(workspace_subpath="src/subdir"))
        result = load_harness_config(root)
        assert result["forge"].workspace_subpath == "src/subdir"
