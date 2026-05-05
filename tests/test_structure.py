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


# ---------------------------------------------------------------------------
# MVP 5 — Worktree Preparation
# ---------------------------------------------------------------------------

MVP5_MODULES = [
    "portfolio_manager.worktree_paths",
    "portfolio_manager.worktree_git",
    "portfolio_manager.worktree_state",
    "portfolio_manager.worktree_artifacts",
    "portfolio_manager.worktree_locks",
    "portfolio_manager.worktree_planner",
    "portfolio_manager.worktree_prepare",
    "portfolio_manager.worktree_create",
    "portfolio_manager.worktree_reconcile",
    "portfolio_manager.worktree_tools",
]

MVP5_TOOLS = [
    "portfolio_worktree_plan",
    "portfolio_worktree_prepare_base",
    "portfolio_worktree_create_issue",
    "portfolio_worktree_list",
    "portfolio_worktree_inspect",
    "portfolio_worktree_explain",
]

MVP5_CLI_COMMANDS = [
    "worktree-plan",
    "worktree-prepare-base",
    "worktree-create-issue",
    "worktree-list",
    "worktree-inspect",
    "worktree-explain",
]


def test_worktree_modules_exist() -> None:
    """All ten new MVP 5 worktree_* modules must be importable."""
    import importlib

    missing: list[str] = []
    for mod in MVP5_MODULES:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    assert not missing, f"Missing MVP 5 modules: {missing}"


def test_worktree_prepare_skill_folder_exists() -> None:
    skill_md = ROOT / "skills" / "worktree-prepare" / "SKILL.md"
    assert skill_md.is_file(), f"Missing skill: {skill_md}"


def test_worktree_tools_registered() -> None:
    """All MVP 5 worktree tools must appear in the __init__ tool registry."""
    from portfolio_manager import _TOOL_REGISTRY

    registered = {name for name, _, _ in _TOOL_REGISTRY}
    missing = [t for t in MVP5_TOOLS if t not in registered]
    assert not missing, f"Missing tool registrations: {missing}"


def test_dev_cli_worktree_commands_registered() -> None:
    """All MVP 5 CLI subcommands must be registered in dev_cli."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("dev_cli", ROOT / "dev_cli.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dev_cli"] = module
    spec.loader.exec_module(module)
    missing = [c for c in MVP5_CLI_COMMANDS if c not in module.TOOL_HANDLERS]
    assert not missing, f"Missing CLI commands: {missing}"


def test_no_duplicate_tool_names() -> None:
    """No tool name may appear twice in the registry."""
    from portfolio_manager import _TOOL_REGISTRY

    names = [name for name, _, _ in _TOOL_REGISTRY]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate tool names: {duplicates}"


def test_existing_portfolio_worktree_inspect_still_callable() -> None:
    """MVP 1 inspect handler must remain importable and callable (back-compat)."""
    from portfolio_manager.tools import _handle_portfolio_worktree_inspect

    assert callable(_handle_portfolio_worktree_inspect)


# ---------------------------------------------------------------------------
# MVP 6 — Implementation Runner
# ---------------------------------------------------------------------------

MVP6_MODULES = [
    "portfolio_manager.implementation_paths",
    "portfolio_manager.implementation_state",
    "portfolio_manager.harness_config",
    "portfolio_manager.implementation_locks",
    "portfolio_manager.implementation_artifacts",
    "portfolio_manager.implementation_preflight",
    "portfolio_manager.implementation_planner",
    "portfolio_manager.harness_runner",
    "portfolio_manager.implementation_changes",
    "portfolio_manager.implementation_scope_guard",
    "portfolio_manager.implementation_test_quality",
    "portfolio_manager.implementation_commit",
    "portfolio_manager.implementation_jobs",
    "portfolio_manager.implementation_tools",
]

MVP6_TOOLS = [
    "portfolio_implementation_plan",
    "portfolio_implementation_start",
    "portfolio_implementation_apply_review_fixes",
    "portfolio_implementation_status",
    "portfolio_implementation_list",
    "portfolio_implementation_explain",
]

MVP6_CLI_COMMANDS = [
    "implementation-plan",
    "implementation-start",
    "implementation-apply-review-fixes",
    "implementation-status",
    "implementation-list",
    "implementation-explain",
]


def test_implementation_modules_exist() -> None:
    """All fourteen MVP 6 implementation_* modules must be importable."""
    import importlib

    missing: list[str] = []
    for mod in MVP6_MODULES:
        try:
            importlib.import_module(mod)
        except ImportError:
            missing.append(mod)
    assert not missing, f"Missing MVP 6 modules: {missing}"


def test_implementation_run_skill_folder_exists() -> None:
    skill_md = ROOT / "skills" / "implementation-run" / "SKILL.md"
    assert skill_md.is_file(), f"Missing skill: {skill_md}"


def test_implementation_tools_registered() -> None:
    """All MVP 6 implementation tools must appear in the __init__ tool registry."""
    from portfolio_manager import _TOOL_REGISTRY

    registered = {name for name, _, _ in _TOOL_REGISTRY}
    missing = [t for t in MVP6_TOOLS if t not in registered]
    assert not missing, f"Missing tool registrations: {missing}"


def test_dev_cli_implementation_commands_registered() -> None:
    """All MVP 6 CLI subcommands must be registered in dev_cli."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("dev_cli", ROOT / "dev_cli.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["dev_cli"] = module
    spec.loader.exec_module(module)
    missing = [c for c in MVP6_CLI_COMMANDS if c not in module.TOOL_HANDLERS]
    assert not missing, f"Missing CLI commands: {missing}"


def test_existing_worktree_tools_still_callable() -> None:
    """MVP 5 worktree tool handlers must remain importable and callable (back-compat)."""
    from portfolio_manager.worktree_tools import (
        _handle_portfolio_worktree_create_issue,
        _handle_portfolio_worktree_explain,
        _handle_portfolio_worktree_list,
        _handle_portfolio_worktree_plan,
        _handle_portfolio_worktree_prepare_base,
    )

    handlers = [
        _handle_portfolio_worktree_create_issue,
        _handle_portfolio_worktree_explain,
        _handle_portfolio_worktree_list,
        _handle_portfolio_worktree_plan,
        _handle_portfolio_worktree_prepare_base,
    ]
    for h in handlers:
        assert callable(h), f"{h.__name__} is not callable"
