---
name: project-admin
description: Administer portfolio projects — add, update, pause, resume, archive, remove, set priority, explain, manage auto-merge, create config backups.
hermes:
  tools:
    - portfolio_project_add
    - portfolio_project_update
    - portfolio_project_pause
    - portfolio_project_resume
    - portfolio_project_archive
    - portfolio_project_set_priority
    - portfolio_project_set_auto_merge
    - portfolio_project_remove
    - portfolio_project_explain
    - portfolio_project_config_backup
  safety:
    - tool_handlers_do_not_run_clarification_flows
    - prefer_archive_over_remove
    - never_enable_auto_merge_unless_explicitly_requested
    - auto_merge_policy_only_no_execution
    - no_issue_creation
    - no_branch_creation
    - no_repository_file_modification
---

# project-admin

Administer projects in the Hermes portfolio.

## Available Tools

| Tool | Purpose |
|------|---------|
| `portfolio_project_add` | Add a new project to the portfolio |
| `portfolio_project_update` | Update project fields (priority, status, name, etc.) |
| `portfolio_project_pause` | Pause a project (skipped by heartbeats) |
| `portfolio_project_resume` | Resume a paused project |
| `portfolio_project_archive` | Archive a project (safe alternative to removal) |
| `portfolio_project_set_priority` | Change project priority |
| `portfolio_project_set_auto_merge` | Configure auto-merge policy (storage only) |
| `portfolio_project_remove` | Remove a project from config (requires confirmation) |
| `portfolio_project_explain` | Show project configuration details |
| `portfolio_project_config_backup` | Create a timestamped config backup |

## Clarification Rules

- If the user request is ambiguous, ask follow-up questions before calling a mutating tool.
- Tool handlers themselves do not run multi-turn clarification flows.

## Safety Rules

- Prefer archive over remove. Remove requires explicit confirmation.
- Never enable auto-merge unless explicitly requested by the user.
- If enabling auto-merge and risk is unspecified, default to low risk.
- MVP 2 stores auto-merge policy but does not merge. It does not execute merges or create PRs.
- Do not create GitHub issues.
- Do not create branches.
- Do not create worktrees.
- Do not modify repository files.
- Do not create GitHub labels.
- Do not open or merge PRs.

## First-Run Behavior

- `portfolio_project_add` creates the initial config if `projects.yaml` is missing.
- Other tools return `config_missing` if there is no config.

## Tool Details

Each tool returns the shared Hermes result format:

```json
{
  "status": "success|blocked|failed",
  "tool": "portfolio_project_...",
  "message": "Human-readable result",
  "data": {},
  "summary": "Concise summary",
  "reason": null
}
```

For backup-creating tools, the `data` field includes `backup_created`, `backup_path`, and for the initial add `is_first_run`.
