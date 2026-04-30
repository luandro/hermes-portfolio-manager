"""Hermes Portfolio Manager plugin — MVP 1 + MVP 2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from portfolio_manager.maintenance_tools import (
    _handle_portfolio_maintenance_due,
    _handle_portfolio_maintenance_report,
    _handle_portfolio_maintenance_run,
    _handle_portfolio_maintenance_run_project,
    _handle_portfolio_maintenance_skill_disable,
    _handle_portfolio_maintenance_skill_enable,
    _handle_portfolio_maintenance_skill_explain,
    _handle_portfolio_maintenance_skill_list,
)
from portfolio_manager.schemas import (
    PORTFOLIO_CONFIG_VALIDATE_SCHEMA,
    PORTFOLIO_GITHUB_SYNC_SCHEMA,
    PORTFOLIO_HEARTBEAT_SCHEMA,
    PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_CREATE_SCHEMA,
    PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA,
    PORTFOLIO_ISSUE_QUESTIONS_SCHEMA,
    PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA,
    # MVP 4 maintenance schemas
    PORTFOLIO_MAINTENANCE_DUE_SCHEMA,
    PORTFOLIO_MAINTENANCE_REPORT_SCHEMA,
    PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA,
    PORTFOLIO_MAINTENANCE_RUN_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA,
    PORTFOLIO_PING_SCHEMA,
    PORTFOLIO_PROJECT_ADD_SCHEMA,
    PORTFOLIO_PROJECT_ARCHIVE_SCHEMA,
    PORTFOLIO_PROJECT_CONFIG_BACKUP_SCHEMA,
    PORTFOLIO_PROJECT_EXPLAIN_SCHEMA,
    PORTFOLIO_PROJECT_LIST_SCHEMA,
    PORTFOLIO_PROJECT_PAUSE_SCHEMA,
    PORTFOLIO_PROJECT_REMOVE_SCHEMA,
    PORTFOLIO_PROJECT_RESOLVE_SCHEMA,
    PORTFOLIO_PROJECT_RESUME_SCHEMA,
    PORTFOLIO_PROJECT_SET_AUTO_MERGE_SCHEMA,
    PORTFOLIO_PROJECT_SET_PRIORITY_SCHEMA,
    PORTFOLIO_PROJECT_UPDATE_SCHEMA,
    PORTFOLIO_STATUS_SCHEMA,
    PORTFOLIO_WORKTREE_INSPECT_SCHEMA,
)
from portfolio_manager.tools import (
    _handle_portfolio_config_validate,
    _handle_portfolio_github_sync,
    _handle_portfolio_heartbeat,
    _handle_portfolio_issue_create,
    _handle_portfolio_issue_create_from_draft,
    _handle_portfolio_issue_discard_draft,
    _handle_portfolio_issue_draft,
    _handle_portfolio_issue_explain_draft,
    _handle_portfolio_issue_list_drafts,
    _handle_portfolio_issue_questions,
    _handle_portfolio_issue_update_draft,
    _handle_portfolio_ping,
    _handle_portfolio_project_add,
    _handle_portfolio_project_archive,
    _handle_portfolio_project_config_backup,
    _handle_portfolio_project_explain,
    _handle_portfolio_project_list,
    _handle_portfolio_project_pause,
    _handle_portfolio_project_remove,
    _handle_portfolio_project_resolve,
    _handle_portfolio_project_resume,
    _handle_portfolio_project_set_auto_merge,
    _handle_portfolio_project_set_priority,
    _handle_portfolio_project_update,
    _handle_portfolio_status,
    _handle_portfolio_worktree_inspect,
)

# Tool name -> (schema, handler) mapping
_TOOL_REGISTRY: list[tuple[str, dict[str, Any], Any]] = [
    # MVP 1 tools
    ("portfolio_ping", PORTFOLIO_PING_SCHEMA, _handle_portfolio_ping),
    ("portfolio_config_validate", PORTFOLIO_CONFIG_VALIDATE_SCHEMA, _handle_portfolio_config_validate),
    ("portfolio_project_list", PORTFOLIO_PROJECT_LIST_SCHEMA, _handle_portfolio_project_list),
    ("portfolio_github_sync", PORTFOLIO_GITHUB_SYNC_SCHEMA, _handle_portfolio_github_sync),
    ("portfolio_worktree_inspect", PORTFOLIO_WORKTREE_INSPECT_SCHEMA, _handle_portfolio_worktree_inspect),
    ("portfolio_status", PORTFOLIO_STATUS_SCHEMA, _handle_portfolio_status),
    ("portfolio_heartbeat", PORTFOLIO_HEARTBEAT_SCHEMA, _handle_portfolio_heartbeat),
    # MVP 2 tools
    ("portfolio_project_add", PORTFOLIO_PROJECT_ADD_SCHEMA, _handle_portfolio_project_add),
    ("portfolio_project_update", PORTFOLIO_PROJECT_UPDATE_SCHEMA, _handle_portfolio_project_update),
    ("portfolio_project_pause", PORTFOLIO_PROJECT_PAUSE_SCHEMA, _handle_portfolio_project_pause),
    ("portfolio_project_resume", PORTFOLIO_PROJECT_RESUME_SCHEMA, _handle_portfolio_project_resume),
    ("portfolio_project_archive", PORTFOLIO_PROJECT_ARCHIVE_SCHEMA, _handle_portfolio_project_archive),
    ("portfolio_project_set_priority", PORTFOLIO_PROJECT_SET_PRIORITY_SCHEMA, _handle_portfolio_project_set_priority),
    (
        "portfolio_project_set_auto_merge",
        PORTFOLIO_PROJECT_SET_AUTO_MERGE_SCHEMA,
        _handle_portfolio_project_set_auto_merge,
    ),
    ("portfolio_project_remove", PORTFOLIO_PROJECT_REMOVE_SCHEMA, _handle_portfolio_project_remove),
    ("portfolio_project_explain", PORTFOLIO_PROJECT_EXPLAIN_SCHEMA, _handle_portfolio_project_explain),
    (
        "portfolio_project_config_backup",
        PORTFOLIO_PROJECT_CONFIG_BACKUP_SCHEMA,
        _handle_portfolio_project_config_backup,
    ),
    # MVP 3 tools
    ("portfolio_project_resolve", PORTFOLIO_PROJECT_RESOLVE_SCHEMA, _handle_portfolio_project_resolve),
    ("portfolio_issue_draft", PORTFOLIO_ISSUE_DRAFT_SCHEMA, _handle_portfolio_issue_draft),
    ("portfolio_issue_questions", PORTFOLIO_ISSUE_QUESTIONS_SCHEMA, _handle_portfolio_issue_questions),
    ("portfolio_issue_update_draft", PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA, _handle_portfolio_issue_update_draft),
    ("portfolio_issue_create", PORTFOLIO_ISSUE_CREATE_SCHEMA, _handle_portfolio_issue_create),
    (
        "portfolio_issue_create_from_draft",
        PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA,
        _handle_portfolio_issue_create_from_draft,
    ),
    ("portfolio_issue_explain_draft", PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA, _handle_portfolio_issue_explain_draft),
    ("portfolio_issue_list_drafts", PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA, _handle_portfolio_issue_list_drafts),
    ("portfolio_issue_discard_draft", PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA, _handle_portfolio_issue_discard_draft),
    # MVP 4 tools
    (
        "portfolio_maintenance_skill_list",
        PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA,
        _handle_portfolio_maintenance_skill_list,
    ),
    (
        "portfolio_maintenance_skill_explain",
        PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA,
        _handle_portfolio_maintenance_skill_explain,
    ),
    (
        "portfolio_maintenance_skill_enable",
        PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA,
        _handle_portfolio_maintenance_skill_enable,
    ),
    (
        "portfolio_maintenance_skill_disable",
        PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA,
        _handle_portfolio_maintenance_skill_disable,
    ),
    ("portfolio_maintenance_due", PORTFOLIO_MAINTENANCE_DUE_SCHEMA, _handle_portfolio_maintenance_due),
    ("portfolio_maintenance_run", PORTFOLIO_MAINTENANCE_RUN_SCHEMA, _handle_portfolio_maintenance_run),
    (
        "portfolio_maintenance_run_project",
        PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA,
        _handle_portfolio_maintenance_run_project,
    ),
    ("portfolio_maintenance_report", PORTFOLIO_MAINTENANCE_REPORT_SCHEMA, _handle_portfolio_maintenance_report),
]

# Skills directory: check repo-root skills/ first, fall back to plugin-local
_PLUGIN_DIR = Path(__file__).parent
_SKILLS_DIR = _PLUGIN_DIR.parent / "skills" if (_PLUGIN_DIR.parent / "skills").exists() else _PLUGIN_DIR / "skills"

_SKILL_DESCRIPTIONS: dict[str, str] = {
    "portfolio-status": "View portfolio status — projects, issues, PRs, worktrees.",
    "portfolio-heartbeat": "Periodic health check across all portfolio projects.",
    "project-admin": "Administer portfolio projects — add, update, pause, resume, archive, remove, set priority, explain, manage auto-merge, create config backups.",
    "issue-brainstorm": "Brainstorm and refine an issue draft from a rough description.",
    "issue-create": "Create a GitHub issue from a refined draft (with confirmation).",
    "portfolio-maintenance": "Run safe maintenance checks and generate reports.",
}


def register(ctx: Any) -> None:
    """Register all portfolio tools and skills with the Hermes plugin context."""
    for name, schema, handler in _TOOL_REGISTRY:
        ctx.register_tool(
            name=name,
            toolset="portfolio-manager",
            schema=schema,
            handler=handler,
            check_fn=None,
            emoji="",
        )
    for name, description in _SKILL_DESCRIPTIONS.items():
        skill_path = _SKILLS_DIR / name / "SKILL.md"
        if skill_path.exists():
            ctx.register_skill(
                name=name,
                path=skill_path,
                description=description,
            )
