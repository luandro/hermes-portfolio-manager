"""Harness configuration loader for MVP 6 implementation runner.

Loads and validates ``$ROOT/config/harnesses.yaml`` — server-side policy that
defines which coding harnesses are available, their commands, timeouts, and
required checks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from portfolio_manager.config import ConfigError
from portfolio_manager.implementation_paths import validate_harness_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HarnessCheckConfig:
    id: str
    command: list[str]  # argv form, no shell string
    timeout_seconds: int


@dataclass(frozen=True)
class HarnessConfig:
    id: str
    command: list[str]  # argv form, no shell string
    env_passthrough: list[str]  # env var names allowed
    timeout_seconds: int
    max_files_changed: int
    required_checks: list[str]  # ids referencing checks
    checks: dict[str, HarnessCheckConfig]
    workspace_subpath: str | None  # optional sub-dir under issue_worktree_path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_CHECK_IDS = {"lint", "typecheck", "unit_tests", "format_check"}
MAX_TIMEOUT = 7200  # 2 hours max

_SHELL_METACHAR_RE = re.compile(r"[;|&$`<>]")


# ---------------------------------------------------------------------------
# Internal validators
# ---------------------------------------------------------------------------


def _validate_command(cmd: Any, context: str) -> list[str]:
    """Validate a command is an argv array with no shell metacharacters or path traversal.

    Each element must be a non-empty string. The first element (binary) must be
    a basename only (no ``/``) or an absolute path. No element may contain
    shell metacharacters.
    """
    if not isinstance(cmd, list):
        raise ConfigError(f"{context}: command must be a list, got {type(cmd).__name__}")
    if not cmd:
        raise ConfigError(f"{context}: command must not be empty")

    result: list[str] = []
    for i, elem in enumerate(cmd):
        if not isinstance(elem, str):
            raise ConfigError(f"{context}: command[{i}] must be a string, got {type(elem).__name__}")
        if not elem:
            raise ConfigError(f"{context}: command[{i}] must not be empty")

        if _SHELL_METACHAR_RE.search(elem):
            raise ConfigError(f"{context}: command[{i}] contains shell metacharacters: {elem!r}")

        if i == 0:
            # First element: basename only or absolute path, no path traversal
            if "/" in elem and not elem.startswith("/"):
                raise ConfigError(f"{context}: command[0] must be a basename or absolute path, got {elem!r}")
            if ".." in elem:
                raise ConfigError(f"{context}: command[0] must not contain '..': {elem!r}")
        else:
            if ".." in elem:
                raise ConfigError(f"{context}: command[{i}] must not contain '..': {elem!r}")

        result.append(elem)
    return result


def _validate_env_passthrough(env: Any, context: str) -> list[str]:
    """Validate env_passthrough is a list of env var names."""
    if not isinstance(env, list):
        raise ConfigError(f"{context}: env_passthrough must be a list, got {type(env).__name__}")
    result: list[str] = []
    for i, name in enumerate(env):
        if not isinstance(name, str) or not name:
            raise ConfigError(f"{context}: env_passthrough[{i}] must be a non-empty string")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ConfigError(f"{context}: env_passthrough[{i}] invalid env var name: {name!r}")
        result.append(name)
    return result


def _validate_harness_entry(raw: dict[str, Any], idx: int) -> HarnessConfig:
    """Validate all fields of a harness entry and return a HarnessConfig."""
    prefix = f"harnesses[{idx}]"
    errors: list[str] = []

    # --- id ---
    raw_id = raw.get("id")
    if not isinstance(raw_id, str) or not raw_id:
        errors.append(f"{prefix}: 'id' must be a non-empty string")
    else:
        try:
            validate_harness_id(raw_id)
        except ValueError as exc:
            errors.append(f"{prefix}: invalid id: {exc}")

    # --- command ---
    raw_cmd = raw.get("command")
    cmd: list[str] | None = None
    try:
        cmd = _validate_command(raw_cmd, prefix)
    except ConfigError as exc:
        errors.append(str(exc))

    # --- env_passthrough ---
    raw_env = raw.get("env_passthrough", [])
    env: list[str] | None = None
    try:
        env = _validate_env_passthrough(raw_env, prefix)
    except ConfigError as exc:
        errors.append(str(exc))

    # --- timeout_seconds ---
    raw_timeout = raw.get("timeout_seconds")
    if not isinstance(raw_timeout, int) or isinstance(raw_timeout, bool) or raw_timeout <= 0:
        errors.append(f"{prefix}: 'timeout_seconds' must be a positive integer")
    elif raw_timeout > MAX_TIMEOUT:
        errors.append(f"{prefix}: 'timeout_seconds' must be <= {MAX_TIMEOUT}, got {raw_timeout}")

    # --- max_files_changed ---
    raw_max_files = raw.get("max_files_changed")
    if not isinstance(raw_max_files, int) or isinstance(raw_max_files, bool) or raw_max_files <= 0:
        errors.append(f"{prefix}: 'max_files_changed' must be a positive integer")

    # --- required_checks ---
    raw_required = raw.get("required_checks", [])
    if not isinstance(raw_required, list):
        errors.append(f"{prefix}: 'required_checks' must be a list")
    else:
        for i, check_id in enumerate(raw_required):
            if not isinstance(check_id, str) or check_id not in ALLOWED_CHECK_IDS:
                errors.append(
                    f"{prefix}: required_checks[{i}] must be one of {sorted(ALLOWED_CHECK_IDS)}, got {check_id!r}"
                )

    # --- checks ---
    raw_checks = raw.get("checks")
    checks: dict[str, HarnessCheckConfig] = {}
    if not isinstance(raw_checks, dict):
        errors.append(f"{prefix}: 'checks' must be a mapping")
    else:
        for check_id, check_val in raw_checks.items():
            check_prefix = f"{prefix}.checks[{check_id!r}]"
            if not isinstance(check_val, dict):
                errors.append(f"{check_prefix}: must be a mapping")
                continue

            check_cmd: list[str] | None = None
            try:
                check_cmd = _validate_command(check_val.get("command"), check_prefix)
            except ConfigError as exc:
                errors.append(str(exc))

            check_timeout = check_val.get("timeout_seconds")
            if not isinstance(check_timeout, int) or isinstance(check_timeout, bool) or check_timeout <= 0:
                errors.append(f"{check_prefix}: 'timeout_seconds' must be a positive integer")
            elif check_timeout > MAX_TIMEOUT:
                errors.append(f"{check_prefix}: 'timeout_seconds' must be <= {MAX_TIMEOUT}, got {check_timeout}")

            if check_cmd is not None and isinstance(check_timeout, int) and check_timeout > 0:
                checks[check_id] = HarnessCheckConfig(
                    id=check_id,
                    command=check_cmd,
                    timeout_seconds=check_timeout,
                )

    # --- required_checks must reference defined checks ---
    if isinstance(raw_required, list) and isinstance(raw_checks, dict):
        for check_id in raw_required:
            if isinstance(check_id, str) and check_id not in raw_checks:
                errors.append(f"{prefix}: required_checks references '{check_id}' which is not defined in checks")

    # --- workspace_subpath ---
    raw_subpath = raw.get("workspace_subpath")
    if raw_subpath is not None:
        if not isinstance(raw_subpath, str):
            errors.append(f"{prefix}: 'workspace_subpath' must be a string or null")
        elif ".." in Path(raw_subpath).parts:
            errors.append(f"{prefix}: 'workspace_subpath' must not contain '..'")
        elif Path(raw_subpath).is_absolute():
            errors.append(f"{prefix}: 'workspace_subpath' must be a relative path")

    if errors:
        raise ConfigError("; ".join(errors))

    assert cmd is not None
    assert env is not None
    assert isinstance(raw_timeout, int)
    assert isinstance(raw_max_files, int)
    assert isinstance(raw_required, list)
    assert isinstance(raw_id, str)

    return HarnessConfig(
        id=raw_id,
        command=cmd,
        env_passthrough=env,
        timeout_seconds=raw_timeout,
        max_files_changed=raw_max_files,
        required_checks=list(raw_required),
        checks=checks,
        workspace_subpath=raw_subpath,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_harness_config(root: Path) -> dict[str, HarnessConfig]:
    """Load and validate ``{root}/config/harnesses.yaml``.

    Returns a dict mapping harness_id -> HarnessConfig.
    If the file does not exist, returns an empty dict with a warning log.
    Raises ConfigError on invalid YAML or validation errors.
    """
    config_path = root / "config" / "harnesses.yaml"

    if not config_path.exists():
        logger.warning("Harness config not found: %s — no harnesses available", config_path)
        return {}

    try:
        text = config_path.read_text(encoding="utf-8")
        raw = yaml.safe_load(text)
    except OSError as exc:
        raise ConfigError(f"Failed to read harnesses.yaml: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse harnesses.yaml: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("harnesses.yaml must be a YAML mapping at the top level.")

    raw_harnesses = raw.get("harnesses")
    if raw_harnesses is None:
        return {}

    if not isinstance(raw_harnesses, list):
        raise ConfigError("'harnesses' must be a list.")

    errors: list[str] = []
    result: dict[str, HarnessConfig] = {}
    seen_ids: set[str] = set()

    for idx, entry in enumerate(raw_harnesses):
        if not isinstance(entry, dict):
            errors.append(f"harnesses[{idx}]: must be a mapping, got {type(entry).__name__}")
            continue
        try:
            harness = _validate_harness_entry(entry, idx)
        except ConfigError as exc:
            errors.append(str(exc))
            continue

        if harness.id in seen_ids:
            errors.append(f"harnesses[{idx}]: duplicate harness id '{harness.id}'")
            continue
        seen_ids.add(harness.id)
        result[harness.id] = harness

    if errors:
        raise ConfigError("; ".join(errors))

    return result


def get_harness(root: Path, harness_id: str) -> HarnessConfig | None:
    """Load config and return the matching harness, or None if not found."""
    configs = load_harness_config(root)
    return configs.get(harness_id)
