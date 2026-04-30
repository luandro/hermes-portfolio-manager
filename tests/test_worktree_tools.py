"""Tests for portfolio_manager.worktree_tools — Phases 6.3, 7.4, 8.4, 9."""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

from portfolio_manager.schemas import (
    PORTFOLIO_WORKTREE_CREATE_ISSUE_SCHEMA,
    PORTFOLIO_WORKTREE_EXPLAIN_SCHEMA,
    PORTFOLIO_WORKTREE_LIST_SCHEMA,
    PORTFOLIO_WORKTREE_PLAN_SCHEMA,
    PORTFOLIO_WORKTREE_PREPARE_BASE_SCHEMA,
)
from portfolio_manager.worktree_tools import _handle_portfolio_worktree_plan

if TYPE_CHECKING:
    from pathlib import Path

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@e",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@e",
}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# 6.1 Plan schema
# ---------------------------------------------------------------------------


def test_plan_schema_requires_project_ref_and_issue_number() -> None:
    req = PORTFOLIO_WORKTREE_PLAN_SCHEMA["parameters"]["required"]
    assert "project_ref" in req
    assert "issue_number" in req


def test_plan_schema_has_optional_branch_name() -> None:
    props = PORTFOLIO_WORKTREE_PLAN_SCHEMA["parameters"]["properties"]
    assert "branch_name" in props
    assert "base_branch" in props
    assert "refresh_base" in props


def test_prepare_base_schema_has_dry_run_and_confirm() -> None:
    props = PORTFOLIO_WORKTREE_PREPARE_BASE_SCHEMA["parameters"]["properties"]
    assert "dry_run" in props and "confirm" in props


def test_create_issue_schema_validates_issue_number_positive() -> None:
    props = PORTFOLIO_WORKTREE_CREATE_ISSUE_SCHEMA["parameters"]["properties"]
    assert props["issue_number"]["type"] == "integer"


def test_list_schema_no_required() -> None:
    assert PORTFOLIO_WORKTREE_LIST_SCHEMA["parameters"]["required"] == []


def test_explain_schema_requires_project_ref() -> None:
    assert "project_ref" in PORTFOLIO_WORKTREE_EXPLAIN_SCHEMA["parameters"]["required"]


# ---------------------------------------------------------------------------
# 6.3 Plan handler
# ---------------------------------------------------------------------------


def test_plan_tool_returns_success_for_clean_path(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    out = _handle_portfolio_worktree_plan({"project_ref": "testproj", "issue_number": 1, "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "success"
    assert res["data"]["plan"]["branch_name"] == "agent/testproj/issue-1"


def test_plan_tool_returns_blocked_with_reason(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    out = _handle_portfolio_worktree_plan(
        {"project_ref": "testproj", "issue_number": 1, "branch_name": "bad..name", "root": str(agent_root)}
    )
    res = json.loads(out)
    assert res["status"] == "blocked"


def test_plan_tool_returns_skipped_for_existing_clean_match(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path, bare_remote: Path
) -> None:
    base = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    issue_path = agent_root / "worktrees" / "testproj-issue-9"
    _git("worktree", "add", str(issue_path), "-b", "agent/testproj/issue-9", "main", cwd=base)
    out = _handle_portfolio_worktree_plan({"project_ref": "testproj", "issue_number": 9, "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "skipped"


def test_plan_tool_does_not_persist_state(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    state_dir = agent_root / "state"
    before = sorted(state_dir.iterdir())
    _handle_portfolio_worktree_plan({"project_ref": "testproj", "issue_number": 5, "root": str(agent_root)})
    after = sorted(state_dir.iterdir())
    assert before == after


def test_plan_tool_blocks_unknown_project(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    out = _handle_portfolio_worktree_plan({"project_ref": "nope-zz", "issue_number": 1, "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "blocked"


def test_plan_tool_blocks_missing_project_ref(agent_root: Path) -> None:
    out = _handle_portfolio_worktree_plan({"issue_number": 1, "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "blocked"


def test_plan_tool_blocks_missing_issue_number(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    out = _handle_portfolio_worktree_plan({"project_ref": "testproj", "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "blocked"


# ---------------------------------------------------------------------------
# 7.4 Prepare-base handler
# ---------------------------------------------------------------------------

from portfolio_manager.worktree_tools import _handle_portfolio_worktree_prepare_base  # noqa: E402


def test_prepare_base_dry_run_writes_plan_artifacts_no_clone(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    out = _handle_portfolio_worktree_prepare_base({"project_ref": "testproj", "dry_run": True, "root": str(agent_root)})
    res = json.loads(out)
    assert res["status"] == "success"
    assert "[dry-run]" in res["message"]
    base_dir = agent_root / "worktrees" / "testproj"
    assert not base_dir.exists()
    artifact_dir = agent_root / "artifacts" / "worktrees" / "testproj" / "base"
    assert (artifact_dir / "plan.json").exists()
    assert (artifact_dir / "commands.json").exists()


def test_prepare_base_requires_confirm_when_dry_run_false(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    out = _handle_portfolio_worktree_prepare_base(
        {"project_ref": "testproj", "dry_run": False, "root": str(agent_root)}
    )
    res = json.loads(out)
    assert res["status"] == "blocked"
    assert res["reason"] == "confirm_required"


def test_prepare_base_executes_clone_and_records_state(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    out = _handle_portfolio_worktree_prepare_base(
        {"project_ref": "testproj", "dry_run": False, "confirm": True, "root": str(agent_root)}
    )
    res = json.loads(out)
    assert res["status"] == "success", res
    assert (agent_root / "worktrees" / "testproj" / ".git").exists()
    artifact_dir = agent_root / "artifacts" / "worktrees" / "testproj" / "base"
    assert (artifact_dir / "result.json").exists()


def test_prepare_base_idempotent_second_call_refreshes(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    args = {"project_ref": "testproj", "dry_run": False, "confirm": True, "root": str(agent_root)}
    _handle_portfolio_worktree_prepare_base(args)
    out = _handle_portfolio_worktree_prepare_base(args)
    res = json.loads(out)
    assert res["status"] == "success"


def test_prepare_base_blocks_dirty_repo(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    args = {"project_ref": "testproj", "dry_run": False, "confirm": True, "root": str(agent_root)}
    _handle_portfolio_worktree_prepare_base(args)
    base = agent_root / "worktrees" / "testproj"
    (base / "README.md").write_text("dirty\n", encoding="utf-8")
    out = _handle_portfolio_worktree_prepare_base(args)
    res = json.loads(out)
    assert res["status"] == "blocked"


# ---------------------------------------------------------------------------
# 8.4 Create-issue handler
# ---------------------------------------------------------------------------

from portfolio_manager.worktree_tools import _handle_portfolio_worktree_create_issue  # noqa: E402


def test_create_issue_dry_run_blocks_no_mutation(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    out = _handle_portfolio_worktree_create_issue(
        {"project_ref": "testproj", "issue_number": 5, "dry_run": True, "root": str(agent_root)}
    )
    res = json.loads(out)
    assert res["status"] in ("success", "skipped")
    assert not (agent_root / "worktrees" / "testproj-issue-5").exists()


def test_create_issue_requires_confirm_when_dry_run_false(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    out = _handle_portfolio_worktree_create_issue(
        {"project_ref": "testproj", "issue_number": 5, "dry_run": False, "root": str(agent_root)}
    )
    res = json.loads(out)
    assert res["status"] == "blocked" and res["reason"] == "confirm_required"


def test_create_issue_executes_and_records_state(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    out = _handle_portfolio_worktree_create_issue(
        {
            "project_ref": "testproj",
            "issue_number": 11,
            "dry_run": False,
            "confirm": True,
            "root": str(agent_root),
        }
    )
    res = json.loads(out)
    assert res["status"] == "success", res
    issue_path = agent_root / "worktrees" / "testproj-issue-11"
    assert issue_path.is_dir() and (issue_path / ".git").exists()
    assert (agent_root / "artifacts" / "worktrees" / "testproj" / "issue-11" / "result.json").exists()


def test_create_issue_idempotent_second_call_skipped(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path
) -> None:
    args = {
        "project_ref": "testproj",
        "issue_number": 12,
        "dry_run": False,
        "confirm": True,
        "root": str(agent_root),
    }
    _handle_portfolio_worktree_create_issue(args)
    out = _handle_portfolio_worktree_create_issue(args)
    res = json.loads(out)
    assert res["status"] == "skipped"


def test_create_issue_blocks_when_branch_exists_in_base_only(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path, bare_remote: Path
) -> None:
    base = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    _git("branch", "agent/testproj/issue-13", "main", cwd=base)
    out = _handle_portfolio_worktree_create_issue(
        {
            "project_ref": "testproj",
            "issue_number": 13,
            "dry_run": False,
            "confirm": True,
            "root": str(agent_root),
        }
    )
    res = json.loads(out)
    assert res["status"] == "blocked"
