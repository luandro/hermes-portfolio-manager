"""Verify that all required plugin files exist in the repository."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "plugin.yaml",
    "portfolio_manager/__init__.py",
    "portfolio_manager/schemas.py",
    "portfolio_manager/tools.py",
    "portfolio_manager/config.py",
    "portfolio_manager/github_client.py",
    "portfolio_manager/worktree.py",
    "portfolio_manager/state.py",
    "portfolio_manager/summary.py",
    "portfolio_manager/errors.py",
    "dev_cli.py",
    "skills/portfolio-status/SKILL.md",
    "skills/portfolio-heartbeat/SKILL.md",
]

MVP3_FILES = [
    "portfolio_manager/issue_resolver.py",
    "portfolio_manager/issue_drafts.py",
    "portfolio_manager/issue_artifacts.py",
    "portfolio_manager/issue_github.py",
    "skills/issue-brainstorm/SKILL.md",
    "skills/issue-create/SKILL.md",
]


def test_all_required_files_exist() -> None:
    missing = [f for f in REQUIRED_FILES if not (ROOT / f).is_file()]
    assert not missing, f"Missing required files: {missing}"


def test_mvp3_files_exist() -> None:
    missing = [f for f in MVP3_FILES if not (ROOT / f).is_file()]
    assert not missing, f"Missing MVP 3 required files: {missing}"
