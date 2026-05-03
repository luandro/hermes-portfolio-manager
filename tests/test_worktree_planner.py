"""Tests for portfolio_manager.worktree_planner — Phase 6.2."""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from portfolio_manager.config import load_projects_config
from portfolio_manager.worktree_planner import build_plan

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


def _config(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path):
    """Load PortfolioConfig from the agent_root/config/projects.yaml."""
    return load_projects_config(agent_root)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_plan_returns_expected_paths_and_branch(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=42, root=agent_root)
    assert plan.project_id == "testproj"
    assert plan.branch_name == "agent/testproj/issue-42"
    assert plan.base_branch == "main"
    assert str(plan.issue_worktree_path).endswith("testproj-issue-42")
    assert plan.would_clone_base  # base not yet cloned


def test_plan_resolves_explicit_base_branch(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=1, base_branch="feature-x", root=agent_root)
    assert plan.base_branch == "feature-x"


def test_plan_writes_no_sqlite_no_artifacts(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    before = sorted((agent_root / "state").iterdir())
    build_plan(cfg, project_ref="testproj", issue_number=1, root=agent_root)
    after = sorted((agent_root / "state").iterdir())
    assert before == after
    assert not (agent_root / "artifacts" / "worktrees").exists()


# ---------------------------------------------------------------------------
# Blocked paths
# ---------------------------------------------------------------------------


def test_plan_blocks_invalid_issue_number(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=0, root=agent_root)
    assert plan.is_blocked


def test_plan_blocks_invalid_branch_name(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=1, branch_name="bad..name", root=agent_root)
    assert plan.is_blocked


def test_plan_blocks_default_branch_auto_unresolvable(agent_root: Path, bare_remote: Path) -> None:
    cfg_path = agent_root / "config" / "projects.yaml"
    cfg_path.write_text(
        f"version: 1\nprojects:\n  - id: p\n    name: P\n    repo: file://{bare_remote}\n"
        "    priority: high\n    status: active\n    default_branch: auto\n"
        "    github:\n      owner: o\n      repo: r\n",
        encoding="utf-8",
    )
    cfg = load_projects_config(agent_root)
    plan = build_plan(cfg, project_ref="p", issue_number=1, root=agent_root)
    assert plan.is_blocked
    assert any("auto" in r for r in plan.blocked_reasons)


def test_plan_unknown_project_blocks(agent_root: Path, projects_yaml_pointing_to_bare_remote: Path) -> None:
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="nope-xyz", issue_number=1, root=agent_root)
    assert plan.is_blocked


# ---------------------------------------------------------------------------
# Probing existing base/issue clones
# ---------------------------------------------------------------------------


def test_plan_detects_existing_clean_matching_worktree_as_skipped(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path, bare_remote: Path
) -> None:
    base = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    issue_path = agent_root / "worktrees" / "testproj-issue-7"
    _git("worktree", "add", str(issue_path), "-b", "agent/testproj/issue-7", "main", cwd=base)
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=7, root=agent_root)
    assert plan.is_skipped, plan.blocked_reasons


def test_plan_detects_existing_dirty_worktree_as_blocked(
    agent_root: Path, projects_yaml_pointing_to_bare_remote: Path, bare_remote: Path
) -> None:
    base = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    issue_path = agent_root / "worktrees" / "testproj-issue-7"
    _git("worktree", "add", str(issue_path), "-b", "agent/testproj/issue-7", "main", cwd=base)
    (issue_path / "README.md").write_text("dirty\n", encoding="utf-8")
    cfg = _config(agent_root, projects_yaml_pointing_to_bare_remote)
    plan = build_plan(cfg, project_ref="testproj", issue_number=7, root=agent_root)
    assert plan.is_blocked
