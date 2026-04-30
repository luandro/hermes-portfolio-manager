"""Tests for maintenance skills — Phase 8: SKILL.md documentation."""

from __future__ import annotations

from pathlib import Path

SKILL_MD = Path(__file__).parent.parent / "skills" / "portfolio-maintenance" / "SKILL.md"

# The eight expected tool names
EXPECTED_TOOLS = [
    "portfolio_maintenance_skill_list",
    "skill_explain",
    "skill_enable",
    "skill_disable",
    "maintenance_due",
    "maintenance_run",
    "maintenance_run_project",
    "maintenance_report",
]

EXAMPLE_PHRASES = [
    "List maintenance skills.",
    "Explain stale issue checks.",
    "Show checks due now.",
    "Dry-run maintenance.",
    "Run maintenance and report findings.",
    "Show latest maintenance report.",
]


def test_portfolio_maintenance_skill_md_exists() -> None:
    """SKILL.md exists at the expected path."""
    assert SKILL_MD.is_file(), f"SKILL.md not found at {SKILL_MD}"


def test_portfolio_maintenance_skill_mentions_report_only_default() -> None:
    """SKILL.md states that checks are report-only by default."""
    content = SKILL_MD.read_text()
    assert "report-only" in content, "Missing 'report-only' mention in SKILL.md"


def test_portfolio_maintenance_skill_warns_no_auto_fixes() -> None:
    """SKILL.md warns that there are no auto-fixes."""
    content = SKILL_MD.read_text()
    assert "no auto-fixes" in content.lower() or "No auto-fixes" in content, (
        "Missing 'no auto-fixes' warning in SKILL.md"
    )


def test_portfolio_maintenance_skill_lists_expected_tools() -> None:
    """SKILL.md lists all 8 expected maintenance tools."""
    content = SKILL_MD.read_text()
    for tool in EXPECTED_TOOLS:
        assert tool in content, f"Tool '{tool}' not mentioned in SKILL.md"


def test_skill_contains_example_phrases() -> None:
    """SKILL.md contains all expected example user phrases."""
    content = SKILL_MD.read_text()
    for phrase in EXAMPLE_PHRASES:
        assert phrase in content, f"Example phrase '{phrase}' not found in SKILL.md"
