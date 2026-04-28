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


MVP4_FILES = [
    "portfolio_manager/maintenance_models.py",
    "portfolio_manager/maintenance_registry.py",
    "portfolio_manager/maintenance_config.py",
    "portfolio_manager/maintenance_state.py",
    "portfolio_manager/skills/builtin/__init__.py",
]

MAINTENANCE_TOOLS = [
    "portfolio_maintenance_skill_list",
    "portfolio_maintenance_skill_explain",
    "portfolio_maintenance_skill_enable",
    "portfolio_maintenance_skill_disable",
    "portfolio_maintenance_due",
    "portfolio_maintenance_run",
    "portfolio_maintenance_run_project",
    "portfolio_maintenance_report",
]


def test_mvp4_files_exist() -> None:
    missing = [f for f in MVP4_FILES if not (ROOT / f).is_file()]
    assert not missing, f"Missing MVP 4 required files: {missing}"


def test_portfolio_maintenance_skill_folder_exists() -> None:
    skill_md = ROOT / "skills" / "portfolio-maintenance" / "SKILL.md"
    assert skill_md.is_file(), f"Missing skill folder: {skill_md}"


def test_maintenance_tools_registered() -> None:
    """All MVP 4 maintenance tools must appear in the __init__ tool registry."""
    from portfolio_manager import _TOOL_REGISTRY

    registered_names = {name for name, _, _ in _TOOL_REGISTRY}
    missing = [t for t in MAINTENANCE_TOOLS if t not in registered_names]
    assert not missing, f"Missing tool registrations: {missing}"


def test_maintenance_tool_schemas_exist() -> None:
    """All MVP 4 tool schemas must be importable from schemas module."""
    from portfolio_manager import schemas

    for tool_name in MAINTENANCE_TOOLS:
        # Convert tool_name to SCREAMING_SNAKE: portfolio_maintenance_skill_list -> PORTFOLIO_MAINTENANCE_SKILL_LIST
        attr_name = tool_name.upper() + "_SCHEMA"
        assert hasattr(schemas, attr_name), f"Missing schema: schemas.{attr_name}"
