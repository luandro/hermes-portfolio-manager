"""Local CLI for running portfolio-manager tools outside Hermes."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

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

TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "portfolio_ping": _handle_portfolio_ping,
    "portfolio_config_validate": _handle_portfolio_config_validate,
    "portfolio_project_list": _handle_portfolio_project_list,
    "portfolio_github_sync": _handle_portfolio_github_sync,
    "portfolio_worktree_inspect": _handle_portfolio_worktree_inspect,
    "portfolio_status": _handle_portfolio_status,
    "portfolio_heartbeat": _handle_portfolio_heartbeat,
    "portfolio_project_add": _handle_portfolio_project_add,
    "portfolio_project_update": _handle_portfolio_project_update,
    "portfolio_project_pause": _handle_portfolio_project_pause,
    "portfolio_project_resume": _handle_portfolio_project_resume,
    "portfolio_project_archive": _handle_portfolio_project_archive,
    "portfolio_project_set_priority": _handle_portfolio_project_set_priority,
    "portfolio_project_set_auto_merge": _handle_portfolio_project_set_auto_merge,
    "portfolio_project_remove": _handle_portfolio_project_remove,
    "portfolio_project_explain": _handle_portfolio_project_explain,
    "portfolio_project_config_backup": _handle_portfolio_project_config_backup,
    # MVP 3
    "portfolio_project_resolve": _handle_portfolio_project_resolve,
    "portfolio_issue_draft": _handle_portfolio_issue_draft,
    "portfolio_issue_questions": _handle_portfolio_issue_questions,
    "portfolio_issue_update_draft": _handle_portfolio_issue_update_draft,
    "portfolio_issue_create": _handle_portfolio_issue_create,
    "portfolio_issue_create_from_draft": _handle_portfolio_issue_create_from_draft,
    "portfolio_issue_explain_draft": _handle_portfolio_issue_explain_draft,
    "portfolio_issue_list_drafts": _handle_portfolio_issue_list_drafts,
    "portfolio_issue_discard_draft": _handle_portfolio_issue_discard_draft,
}


def _to_bool(val: str | None) -> bool | str | None:
    """Normalize 'true'/'false' strings to bool, pass through otherwise."""
    if val is None:
        return None
    lower = val.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    return val


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-manager tools locally")
    parser.add_argument("tool", choices=list(TOOL_HANDLERS), help="Tool to run")
    parser.add_argument("--project-id", help="Project ID for admin operations")
    parser.add_argument("--repo", help="GitHub repo reference (owner/repo, URL)")
    parser.add_argument("--name", help="Human-readable project name")
    parser.add_argument("--priority", help="Priority level")
    parser.add_argument("--status", help="Project status")
    parser.add_argument("--default-branch", help="Default branch")
    parser.add_argument("--auto-merge-enabled", type=str, help="Enable auto-merge (true/false)")
    parser.add_argument("--auto-merge-max-risk", help="Max risk for auto-merge (low/medium)")
    parser.add_argument("--validate-github", type=str, help="Validate GitHub repo (true/false)")
    parser.add_argument("--confirm", type=str, help="Confirm destructive operation (true/false)")
    parser.add_argument("--reason", help="Reason for pause/archive/remove")
    parser.add_argument("--text", help="Text for issue draft creation")
    parser.add_argument("--project-ref", help="Project reference for resolution/draft")
    parser.add_argument("--draft-id", help="Draft ID for issue operations")
    parser.add_argument("--answers", help="Answers to clarifying questions")
    parser.add_argument("--body", help="Issue body text")
    parser.add_argument("--force-ready", type=str, help="Force draft ready (true/false)")
    parser.add_argument("--force-rough-issue", type=str, help="Force rough issue (true/false)")
    parser.add_argument("--dry-run", type=str, help="Dry run mode (true/false)")
    parser.add_argument("--allow-open-questions", type=str, help="Allow open questions (true/false)")
    parser.add_argument("--allow-possible-duplicate", type=str, help="Allow possible duplicate (true/false)")
    parser.add_argument("--include-created", type=str, help="Include created drafts (true/false)")
    parser.add_argument("--root", help="System root path override")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args(argv)

    # Build args dict — only include non-None values
    handler_args: dict[str, object] = {}

    if args.root is not None:
        handler_args["root"] = args.root
    if args.project_id is not None:
        handler_args["project_id"] = args.project_id
    if args.repo is not None:
        handler_args["repo"] = args.repo
    if args.name is not None:
        handler_args["name"] = args.name
    if args.priority is not None:
        handler_args["priority"] = args.priority
    if args.status is not None:
        handler_args["status"] = args.status
    if args.default_branch is not None:
        handler_args["default_branch"] = args.default_branch
    if args.auto_merge_enabled is not None:
        handler_args["enabled"] = _to_bool(args.auto_merge_enabled)
    if args.auto_merge_max_risk is not None:
        handler_args["max_risk"] = args.auto_merge_max_risk
    if args.validate_github is not None:
        handler_args["validate_github"] = _to_bool(args.validate_github)
    if args.confirm is not None:
        handler_args["confirm"] = _to_bool(args.confirm)
    if args.reason is not None:
        handler_args["reason"] = args.reason
    if args.text is not None:
        handler_args["text"] = args.text
    if args.project_ref is not None:
        handler_args["project_ref"] = args.project_ref
    if args.draft_id is not None:
        handler_args["draft_id"] = args.draft_id
    if args.answers is not None:
        handler_args["answers"] = args.answers
    if args.body is not None:
        handler_args["body"] = args.body
    if args.force_ready is not None:
        handler_args["force_ready"] = _to_bool(args.force_ready)
    if args.force_rough_issue is not None:
        handler_args["force_rough_issue"] = _to_bool(args.force_rough_issue)
    if args.dry_run is not None:
        handler_args["dry_run"] = _to_bool(args.dry_run)
    if args.allow_open_questions is not None:
        handler_args["allow_open_questions"] = _to_bool(args.allow_open_questions)
    if args.allow_possible_duplicate is not None:
        handler_args["allow_possible_duplicate"] = _to_bool(args.allow_possible_duplicate)
    if args.include_created is not None:
        handler_args["include_created"] = _to_bool(args.include_created)

    handler = TOOL_HANDLERS[args.tool]
    result = handler(handler_args)

    print(result)


if __name__ == "__main__":
    main()
