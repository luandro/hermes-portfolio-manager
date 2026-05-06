"""Tests for dev_cli.py local tool runner."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "dev_cli.py", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_json(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    return json.loads(result.stdout)


def _write_config(root: Path, projects: list[dict[str, Any]] | None = None) -> Path:
    """Write a projects.yaml into root/config/ and return root."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config = {"version": 1, "projects": projects or []}
    (config_dir / "projects.yaml").write_text(
        _to_yaml(config),
        encoding="utf-8",
    )
    return root


def _to_yaml(data: dict[str, Any]) -> str:
    import yaml

    return yaml.safe_dump(data, sort_keys=False)


SAMPLE_PROJECT: dict[str, Any] = {
    "id": "test-project",
    "name": "Test Project",
    "repo": "https://github.com/example/test-project",
    "github": {"owner": "example", "repo": "test-project"},
    "priority": "medium",
    "status": "active",
    "default_branch": "auto",
}


# ---------------------------------------------------------------------------
# MVP 1 — existing test
# ---------------------------------------------------------------------------


def test_dev_cli_portfolio_ping() -> None:
    """dev_cli.py portfolio_ping returns valid JSON with success status."""
    result = _run_cli("portfolio_ping")
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_ping"


# ---------------------------------------------------------------------------
# MVP 2 — project_add
# ---------------------------------------------------------------------------


def test_dev_cli_project_add(tmp_path: Path) -> None:
    """portfolio_project_add with --repo, --priority, --root, --validate-github false."""
    root = tmp_path / "portfolio"
    result = _run_cli(
        "portfolio_project_add",
        "--repo",
        "example/test-project",
        "--priority",
        "high",
        "--root",
        str(root),
        "--validate-github",
        "false",
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_add"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_pause
# ---------------------------------------------------------------------------


def test_dev_cli_project_pause(tmp_path: Path) -> None:
    """portfolio_project_pause with --project-id, --reason, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_pause",
        "--project-id",
        "test-project",
        "--reason",
        "maintenance",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_pause"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_resume
# ---------------------------------------------------------------------------


def test_dev_cli_project_resume(tmp_path: Path) -> None:
    """portfolio_project_resume with --project-id, --root."""
    paused = {**SAMPLE_PROJECT, "status": "paused"}
    root = _write_config(tmp_path / "portfolio", [paused])
    result = _run_cli(
        "portfolio_project_resume",
        "--project-id",
        "test-project",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_resume"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_archive
# ---------------------------------------------------------------------------


def test_dev_cli_project_archive(tmp_path: Path) -> None:
    """portfolio_project_archive with --project-id, --reason, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_archive",
        "--project-id",
        "test-project",
        "--reason",
        "deprecated",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_archive"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_set_priority
# ---------------------------------------------------------------------------


def test_dev_cli_project_set_priority(tmp_path: Path) -> None:
    """portfolio_project_set_priority with --project-id, --priority, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_set_priority",
        "--project-id",
        "test-project",
        "--priority",
        "high",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_set_priority"
    assert "high" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_set_auto_merge
# ---------------------------------------------------------------------------


def test_dev_cli_project_set_auto_merge(tmp_path: Path) -> None:
    """portfolio_project_set_auto_merge with --project-id, --auto-merge-enabled, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_set_auto_merge",
        "--project-id",
        "test-project",
        "--auto-merge-enabled",
        "true",
        "--auto-merge-max-risk",
        "low",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_set_auto_merge"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_remove (no confirm → blocked)
# ---------------------------------------------------------------------------


def test_dev_cli_project_remove_no_confirm(tmp_path: Path) -> None:
    """portfolio_project_remove without --confirm returns blocked."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_remove",
        "--project-id",
        "test-project",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked"
    assert parsed["tool"] == "portfolio_project_remove"


# ---------------------------------------------------------------------------
# MVP 2 — project_remove (with confirm → success)
# ---------------------------------------------------------------------------


def test_dev_cli_project_remove_with_confirm(tmp_path: Path) -> None:
    """portfolio_project_remove with --confirm true succeeds."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_remove",
        "--project-id",
        "test-project",
        "--confirm",
        "true",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_remove"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 2 — project_explain
# ---------------------------------------------------------------------------


def test_dev_cli_project_explain(tmp_path: Path) -> None:
    """portfolio_project_explain with --project-id, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_explain",
        "--project-id",
        "test-project",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_explain"
    assert parsed["data"]["project"]["id"] == "test-project"


# ---------------------------------------------------------------------------
# MVP 2 — project_config_backup
# ---------------------------------------------------------------------------


def test_dev_cli_project_config_backup(tmp_path: Path) -> None:
    """portfolio_project_config_backup with --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_config_backup",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_config_backup"
    assert parsed["data"].get("backup_created") is True


# ---------------------------------------------------------------------------
# MVP 2 — project_update
# ---------------------------------------------------------------------------


def test_dev_cli_project_update(tmp_path: Path) -> None:
    """portfolio_project_update with --project-id, --priority, --status, --root."""
    root = _write_config(tmp_path / "portfolio", [SAMPLE_PROJECT])
    result = _run_cli(
        "portfolio_project_update",
        "--project-id",
        "test-project",
        "--priority",
        "low",
        "--status",
        "active",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_project_update"
    assert "test-project" in parsed["message"]


# ---------------------------------------------------------------------------
# MVP 3 — CLI tests
# ---------------------------------------------------------------------------


def _make_mvp3_config(tmp_path: Path) -> Path:
    """Set up a valid config with two projects for MVP 3 tests."""
    root = tmp_path / "agent-system"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "projects.yaml").write_text(
        "version: 1\nprojects:\n"
        "  - id: comapeo-cloud-app\n    name: CoMapeo Cloud App\n"
        "    repo: git@github.com:digidem/comapeo-cloud-app.git\n"
        "    github: {owner: digidem, repo: comapeo-cloud-app}\n"
        "    priority: medium\n    status: active\n"
        "  - id: comapeo-mobile\n    name: CoMapeo Mobile\n"
        "    repo: git@github.com:digidem/comapeo-mobile.git\n"
        "    github: {owner: digidem, repo: comapeo-mobile}\n"
        "    priority: medium\n    status: active\n"
    )
    return root


def test_dev_cli_issue_resolve_and_draft(tmp_path: Path) -> None:
    """portfolio_project_resolve + portfolio_issue_draft via CLI."""
    root = _make_mvp3_config(tmp_path)
    resolve_result = _run_cli(
        "portfolio_project_resolve",
        "--project-ref",
        "comapeo-cloud-app",
        "--root",
        str(root),
    )
    resolved = _parse_json(resolve_result)
    assert resolved["status"] == "success"

    draft_result = _run_cli(
        "portfolio_issue_draft",
        "--text",
        "Users should export selected layers as SMP",
        "--project-ref",
        "comapeo-cloud-app",
        "--root",
        str(root),
    )
    draft = _parse_json(draft_result)
    assert draft["status"] == "success"
    assert "draft_id" in draft["data"]


def test_dev_cli_issue_draft_management(tmp_path: Path) -> None:
    """Draft lifecycle via CLI: create → questions → update → explain → list → discard."""
    root = _make_mvp3_config(tmp_path)

    # Create draft
    result = _run_cli(
        "portfolio_issue_draft",
        "--text",
        "Make the stories better",
        "--project-ref",
        "comapeo-cloud-app",
        "--root",
        str(root),
    )
    draft = _parse_json(result)
    draft_id = draft["data"]["draft_id"]

    # Questions
    questions_result = _run_cli(
        "portfolio_issue_questions",
        "--draft-id",
        draft_id,
        "--root",
        str(root),
    )
    questions = _parse_json(questions_result)
    assert questions["status"] == "success"

    # Update
    update_result = _run_cli(
        "portfolio_issue_update_draft",
        "--draft-id",
        draft_id,
        "--answers",
        "Target CoMapeo Mobile first",
        "--root",
        str(root),
    )
    updated = _parse_json(update_result)
    assert updated["status"] == "success"

    # Explain
    explain_result = _run_cli(
        "portfolio_issue_explain_draft",
        "--draft-id",
        draft_id,
        "--root",
        str(root),
    )
    explained = _parse_json(explain_result)
    assert explained["status"] == "success"

    # List
    list_result = _run_cli(
        "portfolio_issue_list_drafts",
        "--root",
        str(root),
    )
    listed = _parse_json(list_result)
    assert listed["status"] == "success"

    # Discard
    discard_result = _run_cli(
        "portfolio_issue_discard_draft",
        "--draft-id",
        draft_id,
        "--confirm",
        "true",
        "--root",
        str(root),
    )
    discarded = _parse_json(discard_result)
    assert discarded["status"] == "success"


# ---------------------------------------------------------------------------
# MVP 5 — worktree CLI commands
# ---------------------------------------------------------------------------


def test_cli_registers_worktree_plan() -> None:
    import dev_cli

    assert "worktree-plan" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_plan" in dev_cli.TOOL_HANDLERS


def test_cli_registers_worktree_prepare_base() -> None:
    import dev_cli

    assert "worktree-prepare-base" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_prepare_base" in dev_cli.TOOL_HANDLERS


def test_cli_registers_worktree_create_issue() -> None:
    import dev_cli

    assert "worktree-create-issue" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_create_issue" in dev_cli.TOOL_HANDLERS


def test_cli_registers_worktree_list() -> None:
    import dev_cli

    assert "worktree-list" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_list" in dev_cli.TOOL_HANDLERS


def test_cli_registers_worktree_inspect() -> None:
    import dev_cli

    assert "worktree-inspect" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_inspect" in dev_cli.TOOL_HANDLERS


def test_cli_registers_worktree_explain() -> None:
    import dev_cli

    assert "worktree-explain" in dev_cli.TOOL_HANDLERS
    assert "portfolio_worktree_explain" in dev_cli.TOOL_HANDLERS


def test_cli_worktree_plan_returns_blocked_for_unknown_project(tmp_path: Path) -> None:
    root = _write_config(tmp_path, [])
    result = _run_cli(
        "worktree-plan",
        "--project-ref",
        "does-not-exist",
        "--issue-number",
        "42",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked", parsed
    assert parsed["tool"] == "portfolio_worktree_plan"


def test_cli_worktree_list_returns_empty_array_for_empty_root(tmp_path: Path) -> None:
    root = _write_config(tmp_path, [])
    result = _run_cli(
        "worktree-list",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success", parsed
    data = parsed.get("data", {})
    assert data.get("worktrees") == []


def test_cli_worktree_inspect_blocks_path_outside_root(tmp_path: Path) -> None:
    root = _write_config(tmp_path, [])
    escape = tmp_path / "escape" / "outside"
    escape.mkdir(parents=True, exist_ok=True)
    result = _run_cli(
        "worktree-inspect",
        "--path",
        str(escape),
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked", parsed
    assert "outside" in parsed.get("message", "").lower() or "escape" in parsed.get("message", "").lower()


# ---------------------------------------------------------------------------
# MVP 6 — implementation runner CLI tests
# ---------------------------------------------------------------------------


def _write_impl_config(root: Path) -> Path:
    """Write config with one project + harnesses.yaml."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "projects.yaml").write_text(
        "version: 1\n"
        "projects:\n"
        "  - id: impl-proj\n"
        "    name: Impl Project\n"
        "    repo: https://github.com/example/impl\n"
        "    priority: high\n"
        "    status: active\n"
        "    github:\n"
        "      owner: example\n"
        "      repo: impl\n",
        encoding="utf-8",
    )
    (config_dir / "harnesses.yaml").write_text(
        "harnesses:\n"
        "  - id: test-harness\n"
        "    command: [echo, hello]\n"
        "    env_passthrough: []\n"
        "    timeout_seconds: 60\n"
        "    max_files_changed: 20\n"
        "    required_checks: []\n"
        "    checks: {}\n",
        encoding="utf-8",
    )
    return root


def test_cli_implementation_plan_returns_blocked_for_unknown_project(tmp_path: Path) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-plan",
        "--project-ref",
        "does-not-exist",
        "--issue-number",
        "42",
        "--harness-id",
        "test-harness",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked", parsed
    assert parsed["tool"] == "portfolio_implementation_plan"


def test_cli_implementation_plan_returns_blocked_for_unknown_harness_id(tmp_path: Path) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-plan",
        "--project-ref",
        "impl-proj",
        "--issue-number",
        "42",
        "--harness-id",
        "no-such-harness",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked", parsed
    assert parsed["tool"] == "portfolio_implementation_plan"
    assert "harness" in parsed.get("reason", "").lower()


def test_cli_implementation_status_returns_blocked_for_unknown_job_id(tmp_path: Path) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-status",
        "--project-ref",
        "impl-proj",
        "--issue-number",
        "42",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "blocked", parsed
    assert parsed["tool"] == "portfolio_implementation_status"


def test_cli_implementation_list_returns_empty_array_for_empty_root(tmp_path: Path) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-list",
        "--root",
        str(root),
    )
    parsed = _parse_json(result)
    assert parsed["status"] == "success", parsed
    assert parsed["data"]["jobs"] == []
    assert parsed["data"]["count"] == 0


def test_cli_implementation_start_rejects_invalid_instructions_json(tmp_path: Path) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-start",
        "--project-ref",
        "impl-proj",
        "--issue-number",
        "42",
        "--harness-id",
        "test-harness",
        "--instructions",
        "{not-json",
        "--root",
        str(root),
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "--instructions" in result.stderr
    assert "valid JSON" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("instructions", ["[]", '"task"', "null"])
def test_cli_implementation_start_rejects_non_object_instructions_json(tmp_path: Path, instructions: str) -> None:
    root = _write_impl_config(tmp_path / "agent-system")
    result = _run_cli(
        "implementation-start",
        "--project-ref",
        "impl-proj",
        "--issue-number",
        "42",
        "--harness-id",
        "test-harness",
        "--instructions",
        instructions,
        "--root",
        str(root),
    )

    assert result.returncode != 0
    assert result.stdout == ""
    assert "--instructions" in result.stderr
    assert "JSON object" in result.stderr
    assert "Traceback" not in result.stderr
