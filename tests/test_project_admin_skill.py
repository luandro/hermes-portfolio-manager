"""Tests for skills/project-admin/SKILL.md."""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"
SKILL_PATH = SKILLS_DIR / "project-admin" / "SKILL.md"

MVP2_TOOLS = [
    "portfolio_project_add",
    "portfolio_project_update",
    "portfolio_project_pause",
    "portfolio_project_resume",
    "portfolio_project_archive",
    "portfolio_project_set_priority",
    "portfolio_project_set_auto_merge",
    "portfolio_project_remove",
    "portfolio_project_explain",
    "portfolio_project_config_backup",
]


class TestProjectAdminSkillExists:
    """Verify the skill file exists with correct frontmatter."""

    def test_project_admin_skill_exists(self) -> None:
        assert SKILL_PATH.is_file(), f"Skill file not found: {SKILL_PATH}"

    def test_frontmatter_has_name(self) -> None:
        content = SKILL_PATH.read_text()
        assert "name: project-admin" in content


class TestProjectAdminSkillMentionsTools:
    """Verify the skill references all 10 MVP 2 tools."""

    def test_mentions_all_mvp2_tools(self) -> None:
        content = SKILL_PATH.read_text()
        for tool in MVP2_TOOLS:
            assert tool in content, f"Missing tool reference: {tool}"


class TestProjectAdminSkillSafetyAndClarification:
    """Verify safety and clarification rules are present."""

    def test_has_clarification_rule(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "ask follow-up" in content or "clarification" in content or "ambiguous" in content

    def test_prefer_archive_over_remove(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "prefer archive over remove" in content or "prefer archive" in content

    def test_never_enable_auto_merge_unless(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "never enable auto-merge unless" in content or (
            "never" in content and "auto-merge" in content and "unless" in content
        )

    def test_auto_merge_policy_only(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert (
            "does not execute" in content
            or "does not merge" in content
            or ("stores auto-merge policy" in content and "does not" in content)
        )

    def test_tool_handlers_do_not_run_clarification_flows(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "tool handlers" in content and "do not run" in content and ("clarification" in content)

    def test_do_not_create_issues(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "do not create" in content and "issue" in content

    def test_do_not_create_branches(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "do not create" in content and "branch" in content

    def test_do_not_modify_repository_files(self) -> None:
        content = SKILL_PATH.read_text().lower()
        assert "do not modify" in content and "repository" in content
