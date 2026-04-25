"""Tests for Hermes SKILL.md files in skills/."""

from __future__ import annotations

from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "skills"


class TestPortfolioStatusSkill:
    """Verify skills/portfolio-status/SKILL.md content."""

    SKILL_PATH = SKILLS_DIR / "portfolio-status" / "SKILL.md"

    def test_frontmatter_has_name(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "name: portfolio-status" in content

    def test_instructs_to_call_portfolio_status(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "portfolio_status" in content

    def test_highlights_user_decisions(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "decision" in content.lower() or "triage" in content.lower()

    def test_highlights_prs(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "PR" in content

    def test_highlights_worktree_blockers(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "worktree" in content.lower()

    def test_highlights_warnings(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "Warning" in content


class TestPortfolioHeartbeatSkill:
    """Verify skills/portfolio-heartbeat/SKILL.md content."""

    SKILL_PATH = SKILLS_DIR / "portfolio-heartbeat" / "SKILL.md"

    def test_frontmatter_has_name(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "name: portfolio-heartbeat" in content

    def test_instructs_to_call_portfolio_heartbeat(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "portfolio_heartbeat" in content

    def test_has_read_only_restrictions(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "read-only" in content.lower() or "read only" in content.lower()

    def test_returns_blockers(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "Block" in content

    def test_returns_user_decisions(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "decision" in content.lower() or "triage" in content.lower()

    def test_returns_prs_ready_for_review(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "PR" in content

    def test_returns_dirty_worktrees(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "dirty" in content.lower() or "worktree" in content.lower()

    def test_returns_conflicted_worktrees(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "conflict" in content.lower()

    def test_returns_warnings(self) -> None:
        content = self.SKILL_PATH.read_text()
        assert "Warning" in content
