"""Tests for the worktree-prepare Hermes skill."""

from __future__ import annotations

from pathlib import Path

SKILL_PATH = Path(__file__).parent.parent / "skills" / "worktree-prepare" / "SKILL.md"

EXPECTED_TOOLS = (
    "portfolio_worktree_plan",
    "portfolio_worktree_prepare_base",
    "portfolio_worktree_create_issue",
    "portfolio_worktree_list",
    "portfolio_worktree_inspect",
    "portfolio_worktree_explain",
)


def _read() -> str:
    assert SKILL_PATH.is_file(), f"Missing skill: {SKILL_PATH}"
    return SKILL_PATH.read_text(encoding="utf-8").lower()


def test_worktree_prepare_skill_md_exists() -> None:
    assert SKILL_PATH.is_file()


def test_skill_mentions_plan_first() -> None:
    text = _read()
    assert "plan first" in text


def test_skill_mentions_dry_run_then_confirm() -> None:
    text = _read()
    assert "dry-run" in text or "dry_run" in text
    assert "confirm" in text


def test_skill_mentions_blocked_over_guessing() -> None:
    text = _read()
    assert "blocked" in text
    assert "guess" in text


def test_skill_lists_six_expected_tools() -> None:
    text = _read()
    for tool in EXPECTED_TOOLS:
        assert tool in text, f"Missing tool reference: {tool}"


def test_skill_warns_no_implementation_agents_in_mvp5() -> None:
    text = _read()
    assert "no implementation agents" in text


def test_skill_warns_no_github_remote_mutation() -> None:
    text = _read()
    assert "no github remote mutation" in text
