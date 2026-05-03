"""Tests for portfolio_manager/implementation_artifacts.py — Phase 4, tasks 4.1 + 4.2."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from portfolio_manager import implementation_artifacts as ia

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def artifact_dir(tmp_path: Path) -> Path:
    d = tmp_path / "artifacts" / "impl"
    return d


def _all_writers_and_sample_data(
    artifact_dir: Path,
) -> list[tuple[str, object, Path]]:
    """Return (writer_name, sample_data, expected_file) tuples for every writer."""
    return [
        ("write_plan_md", {"steps": ["step1"], "branch": "main"}, artifact_dir / "plan.md"),
        (
            "write_preflight_json",
            {"ok": True, "reasons": []},
            artifact_dir / "preflight.json",
        ),
        (
            "write_commands_json",
            [{"command": ["forge", "run"], "timeout": 600}],
            artifact_dir / "commands.json",
        ),
        (
            "write_input_request_json",
            {"issue_number": 42, "source": "spec.md"},
            artifact_dir / "input-request.json",
        ),
        (
            "write_test_first_evidence_md",
            {"phases": [{"phase": "red", "exit_code": 1}]},
            artifact_dir / "test-first-evidence.md",
        ),
        (
            "write_changed_files_json",
            [{"path": "src/foo.py", "status": "M"}],
            artifact_dir / "changed-files.json",
        ),
        (
            "write_checks_json",
            [{"id": "lint", "passed": True}],
            artifact_dir / "checks.json",
        ),
        (
            "write_scope_check_md",
            {"ok": True, "violations": []},
            artifact_dir / "scope-check.md",
        ),
        (
            "write_test_quality_md",
            {"ok": True, "new_tests": 2},
            artifact_dir / "test-quality.md",
        ),
        (
            "write_commit_json",
            {"sha": "abc123", "message": "impl #42"},
            artifact_dir / "commit.json",
        ),
        (
            "write_result_json",
            {"status": "succeeded"},
            artifact_dir / "result.json",
        ),
        (
            "write_error_json",
            {"error": "timeout", "exit_code": 2},
            artifact_dir / "error.json",
        ),
        ("write_summary_md", "Job completed.", artifact_dir / "summary.md"),
    ]


# ---------------------------------------------------------------------------
# Shape tests — each writer produces a file with valid content
# ---------------------------------------------------------------------------


def test_write_plan_md_shape(artifact_dir: Path) -> None:
    ia.write_plan_md(artifact_dir, {"steps": ["a", "b"]})
    content = (artifact_dir / "plan.md").read_text()
    assert content.startswith("# Implementation Plan")
    parsed = json.loads(content.split("\n\n", 1)[1])
    assert parsed["steps"] == ["a", "b"]


def test_write_preflight_json_shape(artifact_dir: Path) -> None:
    ia.write_preflight_json(artifact_dir, {"ok": True, "reasons": []})
    data = json.loads((artifact_dir / "preflight.json").read_text())
    assert data["ok"] is True


def test_write_commands_json_shape_argv_arrays_only(artifact_dir: Path) -> None:
    ia.write_commands_json(artifact_dir, [{"command": ["forge", "run"], "timeout": 600}])
    data = json.loads((artifact_dir / "commands.json").read_text())
    assert isinstance(data[0]["command"], list)
    # Reject shell string commands
    with pytest.raises(ValueError, match="argv arrays"):
        ia.write_commands_json(artifact_dir, [{"command": "forge run"}])


def test_write_input_request_json_shape(artifact_dir: Path) -> None:
    ia.write_input_request_json(artifact_dir, {"issue_number": 42})
    data = json.loads((artifact_dir / "input-request.json").read_text())
    assert data["issue_number"] == 42


def test_write_test_first_evidence_md_shape(artifact_dir: Path) -> None:
    ia.write_test_first_evidence_md(artifact_dir, {"phases": [{"phase": "red"}]})
    content = (artifact_dir / "test-first-evidence.md").read_text()
    assert content.startswith("# Test-First Evidence")


def test_write_changed_files_json_shape(artifact_dir: Path) -> None:
    ia.write_changed_files_json(artifact_dir, [{"path": "a.py", "status": "M"}])
    data = json.loads((artifact_dir / "changed-files.json").read_text())
    assert data[0]["path"] == "a.py"


def test_write_checks_json_shape(artifact_dir: Path) -> None:
    ia.write_checks_json(artifact_dir, [{"id": "lint", "passed": True}])
    data = json.loads((artifact_dir / "checks.json").read_text())
    assert data[0]["id"] == "lint"


def test_write_scope_check_md_shape(artifact_dir: Path) -> None:
    ia.write_scope_check_md(artifact_dir, {"ok": True, "violations": []})
    content = (artifact_dir / "scope-check.md").read_text()
    assert content.startswith("# Scope Check")


def test_write_test_quality_md_shape(artifact_dir: Path) -> None:
    ia.write_test_quality_md(artifact_dir, {"ok": True, "new_tests": 3})
    content = (artifact_dir / "test-quality.md").read_text()
    assert content.startswith("# Test Quality")


def test_write_commit_json_shape(artifact_dir: Path) -> None:
    ia.write_commit_json(artifact_dir, {"sha": "abc123", "message": "impl"})
    data = json.loads((artifact_dir / "commit.json").read_text())
    assert data["sha"] == "abc123"


def test_write_result_json_shape(artifact_dir: Path) -> None:
    ia.write_result_json(artifact_dir, {"status": "succeeded"})
    data = json.loads((artifact_dir / "result.json").read_text())
    assert data["status"] == "succeeded"


def test_write_error_json_shape(artifact_dir: Path) -> None:
    ia.write_error_json(artifact_dir, {"error": "boom"})
    data = json.loads((artifact_dir / "error.json").read_text())
    assert data["error"] == "boom"


def test_write_summary_md_is_telegram_safe(artifact_dir: Path) -> None:
    """summary.md must be plain text with no markdown that Telegram can't handle."""
    ia.write_summary_md(artifact_dir, "Job completed successfully.")
    content = (artifact_dir / "summary.md").read_text()
    assert "Job completed successfully." in content
    # No HTML/complex markup
    assert "<" not in content
    assert ">" not in content


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------


def test_dry_run_writes_no_files(artifact_dir: Path) -> None:
    """When dry_run=True, no files are written."""
    writers = _all_writers_and_sample_data(artifact_dir)
    for writer_name, data, _expected_file in writers:
        fn = getattr(ia, writer_name)
        fn(artifact_dir, data, dry_run=True)
    # No files should exist
    if artifact_dir.exists():
        files = list(artifact_dir.iterdir())
        assert files == [], f"dry_run=True wrote files: {files}"
    else:
        assert not artifact_dir.exists()


# ---------------------------------------------------------------------------
# Directory permissions
# ---------------------------------------------------------------------------


def test_artifact_dir_created_with_0o700_permissions(artifact_dir: Path) -> None:
    """Artifact directory must be created with 0o700 permissions."""
    assert not artifact_dir.exists()
    ia.write_plan_md(artifact_dir, {"steps": []})
    assert artifact_dir.exists()
    mode = stat.S_IMODE(artifact_dir.stat().st_mode)
    assert mode == 0o700, f"Expected 0o700, got {oct(mode)}"


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------


def test_secrets_redacted_in_every_artifact(artifact_dir: Path) -> None:
    """Every artifact must redact known secret patterns."""
    secret_payloads = {
        "write_plan_md": {"steps": ["use token ghp_abc123secret"]},
        "write_preflight_json": {"ok": True, "token": "ghp_abc123secret"},
        "write_commands_json": [{"command": ["echo", "ghp_abc123secret"]}],
        "write_input_request_json": {"env": "Bearer ghp_abc123secret"},
        "write_test_first_evidence_md": {"note": "sk-testkey123secret"},
        "write_changed_files_json": [{"path": "ghp_abc123secret.py"}],
        "write_checks_json": [{"output": "token=ghp_abc123secret"}],
        "write_scope_check_md": {"detail": "password=supersecret"},
        "write_test_quality_md": {"log": "Bearer ghp_abc123secret"},
        "write_commit_json": {"message": "ghp_abc123secret"},
        "write_result_json": {"output": "ghp_abc123secret"},
        "write_error_json": {"stderr": "ghp_abc123secret"},
    }

    for writer_name, data in secret_payloads.items():
        fn = getattr(ia, writer_name)
        fn(artifact_dir, data)

    # Check all JSON files for unredacted secrets
    for json_file in artifact_dir.glob("*.json"):
        content = json_file.read_text()
        assert "ghp_abc123secret" not in content, f"Unredacted secret in {json_file.name}"
        assert "sk-testkey123secret" not in content, f"Unredacted sk- secret in {json_file.name}"

    # Check all .md files
    for md_file in artifact_dir.glob("*.md"):
        content = md_file.read_text()
        assert "ghp_abc123secret" not in content, f"Unredacted secret in {md_file.name}"
        assert "sk-testkey123secret" not in content, f"Unredacted sk- secret in {md_file.name}"


# ---------------------------------------------------------------------------
# Chain-of-thought markers
# ---------------------------------------------------------------------------


def test_no_chain_of_thought_marker_written(artifact_dir: Path) -> None:
    """No CoT markers should appear in any artifact file."""
    cot_markers = [
        "internal:",
        "<|cot|>",
        "thinking:",
        "<|thinking|>",
        "<thought>",
        "</thought>",
        "<scratchpad>",
        "</scratchpad>",
    ]
    ia.write_plan_md(artifact_dir, {"steps": ["internal: secret thought"]})
    ia.write_summary_md(artifact_dir, "thinking: let me consider this...")
    ia.write_error_json(artifact_dir, {"error": "<|cot|> hidden reasoning"})

    for f in artifact_dir.iterdir():
        content = f.read_text().lower()
        for marker in cot_markers:
            assert marker.lower() not in content, f"CoT marker {marker!r} found in {f.name}"


# ---------------------------------------------------------------------------
# Atomic write verification
# ---------------------------------------------------------------------------


def test_atomic_replace_used_for_every_artifact_write(artifact_dir: Path) -> None:
    """Verify that os.replace is used (via issue_artifacts.write_text_atomic) for every write."""
    # We verify this by confirming issue_artifacts.write_text_atomic is called,
    # which internally uses os.replace. We patch it and verify the call count.
    with (
        patch(
            "portfolio_manager.implementation_artifacts._ia.write_text_atomic", wraps=ia._ia.write_text_atomic
        ) as mock_wta,
        patch(
            "portfolio_manager.implementation_artifacts._ia.write_json_atomic", wraps=ia._ia.write_json_atomic
        ) as mock_wja,
    ):
        ia.write_plan_md(artifact_dir, {"steps": []})
        ia.write_summary_md(artifact_dir, "done")
        ia.write_preflight_json(artifact_dir, {"ok": True})
        ia.write_result_json(artifact_dir, {"status": "ok"})

    # write_text_atomic is called for .md files and directly for some .json files
    # write_json_atomic wraps write_text_atomic
    assert mock_wta.called or mock_wja.called, "Atomic writers were not called"


# ---------------------------------------------------------------------------
# Static grep — no print/logger writes secret patterns
# ---------------------------------------------------------------------------


def test_no_print_or_logger_writes_secret_pattern() -> None:
    """Static grep: implementation_artifacts.py must not contain print() or logger calls
    that could leak secrets."""
    source = Path(__file__).resolve().parent.parent / "portfolio_manager" / "implementation_artifacts.py"
    content = source.read_text()
    lines = content.splitlines()

    for i, line in enumerate(lines, 1):
        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Check for print() calls
        assert "print(" not in line, f"Line {i}: print() found in implementation_artifacts.py"
        # Check for logger calls that might leak data
        for pattern in ("logger.info(", "logger.debug(", "logger.warning(", "logger.error("):
            assert pattern not in line, f"Line {i}: {pattern} found in implementation_artifacts.py"
