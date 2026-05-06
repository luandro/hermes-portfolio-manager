"""Artifact persistence for MVP 6 implementation runner — Phase 4.

Writers for the thirteen implementation artifacts. Every writer:
- accepts ``dry_run`` (no-op when True)
- redacts secrets via the shared helpers
- strips chain-of-thought markers and user-home paths
- writes atomically via ``issue_artifacts.write_text_atomic`` / ``write_json_atomic``
- creates the artifact directory with 0o700 permissions
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from portfolio_manager import errors as _errors_mod
from portfolio_manager import issue_artifacts as _ia
from portfolio_manager import maintenance_artifacts as _ma

# ---------------------------------------------------------------------------
# Chain-of-thought markers to strip
# ---------------------------------------------------------------------------

_COT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"internal:\s*", re.IGNORECASE),
    re.compile(r"<\|cot\|>\s*", re.IGNORECASE),
    re.compile(r"thinking:\s*", re.IGNORECASE),
    re.compile(r"<\|thinking\|>\s*", re.IGNORECASE),
    re.compile(r"<thought>\s*", re.IGNORECASE),
    re.compile(r"</thought>\s*", re.IGNORECASE),
    re.compile(r"<scratchpad>\s*", re.IGNORECASE),
    re.compile(r"</scratchpad>\s*", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize(text: str) -> str:
    """Apply all redaction patterns, strip home paths, and strip CoT markers."""
    # Redact secrets using both redaction helpers
    result = _errors_mod.redact_secrets(text)
    result = _ma.redact_secrets(result)

    # Strip user home paths
    home = str(Path.home())
    if home:
        result = result.replace(home, "$HOME")

    # Strip chain-of-thought markers
    for pat in _COT_PATTERNS:
        result = pat.sub("", result)

    return result


def _sanitize_value(value: Any) -> Any:
    """Recursively sanitize all strings in a JSON-serialisable structure."""
    if isinstance(value, str):
        return _sanitize(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


def _ensure_dir(artifact_dir: Path) -> None:
    """Create *artifact_dir* (with parents) and set permissions to 0o700."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.chmod(0o700)


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------


def write_plan_md(artifact_dir: Path, plan: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``plan.md`` — the implementation plan as markdown."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(plan)
    md = f"# Implementation Plan\n\n{json.dumps(safe, indent=2)}\n"
    _ia.write_text_atomic(artifact_dir / "plan.md", md)


def write_preflight_json(artifact_dir: Path, preflight: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``preflight.json`` — preflight check results."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(preflight)
    _ia.write_json_atomic(artifact_dir / "preflight.json", safe)


def write_commands_json(artifact_dir: Path, commands: list[dict[str, Any]], *, dry_run: bool = False) -> None:
    """Write ``commands.json`` — argv arrays only."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(commands)
    # Validate that every entry has a command key with a list value
    for entry in safe:
        cmd = entry.get("command")
        if cmd is not None and not isinstance(cmd, list):
            raise ValueError(f"commands.json entries must use argv arrays, got: {type(cmd)}")
    _ia.write_text_atomic(artifact_dir / "commands.json", json.dumps(safe, indent=2))


def write_input_request_json(artifact_dir: Path, request: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``input-request.json`` — harness input specification."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(request)
    _ia.write_json_atomic(artifact_dir / "input-request.json", safe)


def write_test_first_evidence_md(artifact_dir: Path, evidence: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``test-first-evidence.md`` — TDD red/green evidence."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(evidence)
    md = f"# Test-First Evidence\n\n{json.dumps(safe, indent=2)}\n"
    _ia.write_text_atomic(artifact_dir / "test-first-evidence.md", md)


def write_changed_files_json(artifact_dir: Path, files: list[dict[str, Any]], *, dry_run: bool = False) -> None:
    """Write ``changed-files.json`` — list of changed files with statuses."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(files)
    _ia.write_text_atomic(artifact_dir / "changed-files.json", json.dumps(safe, indent=2))


def write_checks_json(artifact_dir: Path, checks: list[dict[str, Any]], *, dry_run: bool = False) -> None:
    """Write ``checks.json`` — results of required checks (lint, tests, etc)."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(checks)
    _ia.write_text_atomic(artifact_dir / "checks.json", json.dumps(safe, indent=2))


def write_scope_check_md(artifact_dir: Path, scope_check: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``scope-check.md`` — scope guard results."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(scope_check)
    md = f"# Scope Check\n\n{json.dumps(safe, indent=2)}\n"
    _ia.write_text_atomic(artifact_dir / "scope-check.md", md)


def write_test_quality_md(artifact_dir: Path, quality: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``test-quality.md`` — test quality heuristic results."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(quality)
    md = f"# Test Quality\n\n{json.dumps(safe, indent=2)}\n"
    _ia.write_text_atomic(artifact_dir / "test-quality.md", md)


def write_commit_json(artifact_dir: Path, commit_info: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``commit.json`` — local commit metadata."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(commit_info)
    _ia.write_json_atomic(artifact_dir / "commit.json", safe)


def write_result_json(artifact_dir: Path, result: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``result.json`` — final job result."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(result)
    _ia.write_json_atomic(artifact_dir / "result.json", safe)


def write_error_json(artifact_dir: Path, error: dict[str, Any], *, dry_run: bool = False) -> None:
    """Write ``error.json`` — error details for failed jobs."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize_value(error)
    _ia.write_json_atomic(artifact_dir / "error.json", safe)


def write_summary_md(artifact_dir: Path, summary: str, *, dry_run: bool = False) -> None:
    """Write ``summary.md`` — Telegram-safe human-readable summary."""
    if dry_run:
        return
    _ensure_dir(artifact_dir)
    safe = _sanitize(summary)
    _ia.write_text_atomic(artifact_dir / "summary.md", safe)
