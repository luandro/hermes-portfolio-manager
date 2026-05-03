"""Tests for skills/implementation-run/SKILL.md content.

Phase 15, Task 15.1: verify the implementation-run skill document covers
all required topics.
"""

from pathlib import Path

SKILL_PATH = Path(__file__).resolve().parent.parent / "skills" / "implementation-run" / "SKILL.md"

SIX_TOOLS = [
    "portfolio_implementation_plan",
    "portfolio_implementation_start",
    "portfolio_implementation_apply_review_fixes",
    "portfolio_implementation_status",
    "portfolio_implementation_list",
    "portfolio_implementation_explain",
]


def test_implementation_run_skill_md_exists() -> None:
    assert SKILL_PATH.is_file(), f"Skill file missing: {SKILL_PATH}"


def test_skill_mentions_plan_first() -> None:
    text = SKILL_PATH.read_text()
    assert "plan" in text.lower() and "first" in text.lower(), "Skill must mention plan-first workflow"
    assert "portfolio_implementation_plan" in text
    assert "portfolio_implementation_start" in text


def test_skill_mentions_confirm_required() -> None:
    text = SKILL_PATH.read_text()
    assert "confirm=true" in text or "confirm = true" in text
    assert "confirm" in text.lower() and "required" in text.lower()


def test_skill_mentions_blocked_over_guessing() -> None:
    text = SKILL_PATH.read_text()
    assert "blocked" in text.lower() and "guess" in text.lower(), "Skill must mention blocked-over-guessing principle"


def test_skill_lists_six_expected_tools() -> None:
    text = SKILL_PATH.read_text()
    for tool in SIX_TOOLS:
        assert tool in text, f"Skill must mention tool: {tool}"


def test_skill_warns_no_push_no_pr_no_review_decision() -> None:
    text = SKILL_PATH.read_text().lower()
    assert "push" in text, "Skill must warn against pushing"
    assert "pull request" in text or "pr" in text, "Skill must warn against PR creation"
    assert "review" in text and ("pass" in text or "fail" in text or "decision" in text), (
        "Skill must warn against making review decisions"
    )


def test_skill_warns_no_worktree_mutation_outside_harness() -> None:
    text = SKILL_PATH.read_text().lower()
    assert "worktree" in text
    assert "harness" in text
    # Must mention that worktree mutation is limited to harness subprocess changes
    assert "mvp 5" in text or "mvp5" in text, "Skill must reference MVP 5 as worktree owner"


def test_skill_describes_review_fix_callable_only_after_mvp7() -> None:
    text = SKILL_PATH.read_text().lower()
    assert "mvp 7" in text or "mvp7" in text, "Skill must mention MVP 7 as prerequisite for review-fix"
    assert "apply_review_fixes" in text.lower() or "review_fix" in text.lower(), "Skill must describe review-fix tool"


def test_skill_states_operator_exports_provider_env_vars() -> None:
    text = SKILL_PATH.read_text()
    # Must mention the specific env vars for each harness
    assert "FORGE_SESSION__PROVIDER_ID" in text
    assert "FORGE_SESSION__MODEL_ID" in text
    assert "OPENAI_API_KEY" in text
    assert "ANTHROPIC_API_KEY" in text
    # Must mention that MVP 6 does not pick provider/model
    assert "does not pick a provider" in text.lower() or "does not" in text.lower()
