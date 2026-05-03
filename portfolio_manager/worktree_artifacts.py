"""Artifact writers for MVP 5 — Phase 4.

All paths are pinned under ``$ROOT/artifacts/worktrees/<project_id>/`` and
all written content passes through redaction for secrets and credential URLs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from portfolio_manager.maintenance_artifacts import redact_secrets
from portfolio_manager.worktree_paths import redact_remote_url

_ARTIFACT_BASE = Path("artifacts") / "worktrees"
_PROJECT_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


def _validate_project_id(project_id: str) -> None:
    if not _PROJECT_ID_RE.match(project_id):
        raise ValueError(f"invalid project_id for artifact path: {project_id!r}")


def _validate_issue_number(issue_number: int) -> None:
    if not isinstance(issue_number, int) or isinstance(issue_number, bool):
        raise ValueError(f"issue_number must be int, got {type(issue_number).__name__}")
    if issue_number <= 0:
        raise ValueError(f"issue_number must be positive, got {issue_number}")


def _safe_join(root: Path, *parts: str) -> Path:
    root = Path(root)
    if not root.is_absolute():
        raise ValueError(f"root must be an absolute path, got {root!r}")
    base = (root / _ARTIFACT_BASE).resolve()
    target = (base.joinpath(*parts)).resolve()
    if not target.is_relative_to(base):
        raise ValueError(f"path escapes artifacts root: {target} not under {base}")
    return target


# ---------------------------------------------------------------------------
# 4.1 Path helpers
# ---------------------------------------------------------------------------


def base_artifact_dir(root: Path, project_id: str) -> Path:
    """Return ``$ROOT/artifacts/worktrees/<project_id>/base`` (not created)."""
    _validate_project_id(project_id)
    return _safe_join(root, project_id, "base")


def issue_artifact_dir(root: Path, project_id: str, issue_number: int) -> Path:
    """Return ``$ROOT/artifacts/worktrees/<project_id>/issue-<n>`` (not created)."""
    _validate_project_id(project_id)
    _validate_issue_number(issue_number)
    return _safe_join(root, project_id, f"issue-{issue_number}")


# ---------------------------------------------------------------------------
# 4.2 Redaction
# ---------------------------------------------------------------------------


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        out = redact_secrets(value)
        out = re.sub(r"(https?|ssh|git)://[^/@\s]+@", lambda m: f"{m.group(1)}://***@", out)
        return out
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = _redact_value(payload)
    # Special handling: remote_url field gets explicit credential strip
    if "remote_url" in redacted and isinstance(redacted["remote_url"], str):
        redacted["remote_url"] = redact_remote_url(redacted["remote_url"])
    return redacted


def _write_json(target_dir: Path, filename: str, payload: dict[str, Any]) -> Path:
    if not target_dir.exists():
        raise FileNotFoundError(f"artifact dir does not exist: {target_dir}")
    out = target_dir / filename
    safe = _redact_payload(payload)
    out.write_text(json.dumps(safe, indent=2, sort_keys=True), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# 4.2 Writers
# ---------------------------------------------------------------------------


def write_plan(target_dir: Path, plan: dict[str, Any]) -> Path:
    """Write redacted plan.json into *target_dir*."""
    return _write_json(target_dir, "plan.json", plan)


def write_commands(target_dir: Path, commands: list[list[str]]) -> Path:
    """Write commands.json (list of argv arrays)."""
    if not target_dir.exists():
        raise FileNotFoundError(f"artifact dir does not exist: {target_dir}")
    out = target_dir / "commands.json"
    safe = _redact_value({"commands": commands})
    out.write_text(json.dumps(safe, indent=2), encoding="utf-8")
    return out


def write_preflight(target_dir: Path, preflight: dict[str, Any]) -> Path:
    return _write_json(target_dir, "preflight.json", preflight)


def write_result(target_dir: Path, result: dict[str, Any]) -> Path:
    return _write_json(target_dir, "result.json", result)


def write_inspection(target_dir: Path, inspection: dict[str, Any]) -> Path:
    return _write_json(target_dir, "inspection.json", inspection)


def write_error(target_dir: Path, error: dict[str, Any]) -> Path:
    return _write_json(target_dir, "error.json", error)


def write_summary_md(target_dir: Path, summary_md: str) -> Path:
    """Write redacted summary.md (plain markdown, public-safe)."""
    if not target_dir.exists():
        raise FileNotFoundError(f"artifact dir does not exist: {target_dir}")
    out = target_dir / "summary.md"
    safe = redact_secrets(summary_md)
    safe = re.sub(r"(https?|ssh|git)://[^/@\s]+@", lambda m: f"{m.group(1)}://***@", safe)
    out.write_text(safe, encoding="utf-8")
    return out


def ensure_artifact_dir(target_dir: Path) -> Path:
    """Create *target_dir* (and any missing parents) and return it."""
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


__all__ = [
    "base_artifact_dir",
    "ensure_artifact_dir",
    "issue_artifact_dir",
    "write_commands",
    "write_error",
    "write_inspection",
    "write_plan",
    "write_preflight",
    "write_result",
    "write_summary_md",
]
