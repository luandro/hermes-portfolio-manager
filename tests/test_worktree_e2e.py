"""End-to-end tests for MVP 5 worktree handlers using local bare repos.

These tests call the tool handlers directly (not the CLI) against the
``bare_remote`` / ``agent_root`` / ``projects_yaml_pointing_to_bare_remote``
fixtures from ``tests/fixtures/worktree_fixtures.py``. No network access.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.tools import _handle_portfolio_worktree_inspect
from portfolio_manager.worktree_tools import (
    _handle_portfolio_worktree_create_issue,
    _handle_portfolio_worktree_prepare_base,
)

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_GIT_ENV,
        check=True,
        capture_output=True,
    )


def _call_prepare(args: dict[str, object]) -> dict[str, object]:
    return json.loads(_handle_portfolio_worktree_prepare_base(args))


def _call_create(args: dict[str, object]) -> dict[str, object]:
    return json.loads(_handle_portfolio_worktree_create_issue(args))


# ---------------------------------------------------------------------------
# 14.2 — prepare_base end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_prepare_base_dry_run_no_side_effects(agent_root: Path) -> None:
    result = _call_prepare(
        {
            "project_ref": "testproj",
            "dry_run": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] in ("success", "skipped"), result
    base_path = agent_root / "worktrees" / "testproj"
    assert not base_path.exists()
    state_db = agent_root / "state" / "state.sqlite"
    assert not state_db.exists() or state_db.stat().st_size <= 4096


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_prepare_base_clones_when_missing_with_confirm(agent_root: Path) -> None:
    result = _call_prepare(
        {
            "project_ref": "testproj",
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "success", result
    base_path = agent_root / "worktrees" / "testproj"
    assert (base_path / ".git").exists()
    assert (base_path / "README.md").exists()


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_prepare_base_ff_refresh_when_remote_advanced(agent_root: Path, bare_remote: Path) -> None:
    base_path = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base_path), cwd=agent_root)

    seed = agent_root / "_advance"
    _git("clone", str(bare_remote), str(seed), cwd=agent_root)
    (seed / "NEW.md").write_text("advanced\n", encoding="utf-8")
    _git("add", "NEW.md", cwd=seed)
    _git("commit", "-m", "advance", cwd=seed)
    _git("push", "origin", "main", cwd=seed)

    result = _call_prepare(
        {
            "project_ref": "testproj",
            "dry_run": "false",
            "confirm": "true",
            "refresh_base": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "success", result
    assert (base_path / "NEW.md").exists()


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_prepare_base_blocks_when_local_base_dirty(agent_root: Path, bare_remote: Path) -> None:
    base_path = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base_path), cwd=agent_root)
    (base_path / "README.md").write_text("dirty\n", encoding="utf-8")

    result = _call_prepare(
        {
            "project_ref": "testproj",
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "blocked", result


# ---------------------------------------------------------------------------
# 14.3 — create_issue worktree + idempotency
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_create_issue_worktree_creates_branch_and_path(agent_root: Path) -> None:
    result = _call_create(
        {
            "project_ref": "testproj",
            "issue_number": 42,
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "success", result
    issue_path = agent_root / "worktrees" / "testproj-issue-42"
    assert issue_path.exists()
    assert (issue_path / ".git").exists()


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_create_issue_worktree_writes_sqlite_row(agent_root: Path) -> None:
    _call_create(
        {
            "project_ref": "testproj",
            "issue_number": 43,
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    import sqlite3

    db = agent_root / "state" / "state.sqlite"
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT id, issue_number, branch_name FROM worktrees WHERE project_id=?",
            ("testproj",),
        ).fetchall()
    finally:
        conn.close()
    issue_rows = [r for r in rows if r[1] == 43]
    assert issue_rows, f"No SQLite row for issue 43: {rows}"


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_create_issue_worktree_writes_artifacts(agent_root: Path) -> None:
    _call_create(
        {
            "project_ref": "testproj",
            "issue_number": 44,
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    artifact_dir = agent_root / "artifacts" / "worktrees" / "testproj" / "issue-44"
    assert artifact_dir.exists()
    files = {p.name for p in artifact_dir.iterdir()}
    assert "plan.json" in files
    assert "commands.json" in files
    assert "result.json" in files


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_repeat_create_returns_skipped_success(agent_root: Path) -> None:
    args: dict[str, object] = {
        "project_ref": "testproj",
        "issue_number": 45,
        "dry_run": "false",
        "confirm": "true",
        "root": str(agent_root),
    }
    first = _call_create(args)
    assert first["status"] == "success", first
    second = _call_create(args)
    assert second["status"] in ("skipped", "success"), second
    if second["status"] == "success":
        outcome = second.get("data", {}).get("outcome", {})
        assert outcome.get("skipped") is True, second


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_create_blocks_when_target_branch_exists_without_matching_worktree(
    agent_root: Path, bare_remote: Path
) -> None:
    base_path = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base_path), cwd=agent_root)
    _git("branch", "agent/testproj/issue-99", cwd=base_path)

    result = _call_create(
        {
            "project_ref": "testproj",
            "issue_number": 99,
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "blocked", result


# ---------------------------------------------------------------------------
# 14.4 — dirty / conflict / divergence block paths
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_create_blocks_when_existing_issue_worktree_dirty(
    agent_root: Path,
) -> None:
    create_args: dict[str, object] = {
        "project_ref": "testproj",
        "issue_number": 50,
        "dry_run": "false",
        "confirm": "true",
        "root": str(agent_root),
    }
    first = _call_create(create_args)
    assert first["status"] == "success", first
    issue_path = agent_root / "worktrees" / "testproj-issue-50"
    (issue_path / "README.md").write_text("dirty in issue tree\n", encoding="utf-8")

    second = _call_create(create_args)
    assert second["status"] == "blocked", second


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_prepare_base_blocks_when_local_branch_diverges_from_origin(agent_root: Path, bare_remote: Path) -> None:
    base_path = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base_path), cwd=agent_root)
    (base_path / "LOCAL.md").write_text("local-only\n", encoding="utf-8")
    _git("add", "LOCAL.md", cwd=base_path)
    _git("commit", "-m", "local-only commit", cwd=base_path)

    result = _call_prepare(
        {
            "project_ref": "testproj",
            "dry_run": "false",
            "confirm": "true",
            "refresh_base": "true",
            "root": str(agent_root),
        }
    )
    assert result["status"] == "blocked", result


@pytest.mark.usefixtures("projects_yaml_pointing_to_bare_remote")
def test_e2e_inspect_round_trip_after_create(agent_root: Path) -> None:
    _call_create(
        {
            "project_ref": "testproj",
            "issue_number": 60,
            "dry_run": "false",
            "confirm": "true",
            "root": str(agent_root),
        }
    )
    result = json.loads(_handle_portfolio_worktree_inspect({"root": str(agent_root)}))
    assert result["status"] == "success", result
