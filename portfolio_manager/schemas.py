"""OpenAI function-calling schemas for the Portfolio Manager plugin.

Each schema is a dict with name, description, parameters.type=object,
properties, and required list.  These follow the OpenAI function-calling
convention used by Hermes for tool registration.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# portfolio_ping
# ---------------------------------------------------------------------------

PORTFOLIO_PING_SCHEMA = {
    "name": "portfolio_ping",
    "description": "Smoke test: confirm the Portfolio Manager plugin is loaded.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_config_validate
# ---------------------------------------------------------------------------

PORTFOLIO_CONFIG_VALIDATE_SCHEMA = {
    "name": "portfolio_config_validate",
    "description": (
        "Validate server-side project configuration without contacting GitHub "
        "or inspecting worktrees. Checks config/projects.yaml, validates fields, "
        "enums, duplicate IDs, and ensures required directories exist."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "root": {
                "type": "string",
                "description": ("Optional agent system root. Defaults to AGENT_SYSTEM_ROOT or ~/.agent-system."),
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_list
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_LIST_SCHEMA = {
    "name": "portfolio_project_list",
    "description": (
        "List configured projects from the server manifest. "
        "Filter by status, include/exclude archived projects, "
        "sorted by priority."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": ("Optional project status filter: active, paused, archived, blocked, missing."),
                "enum": ["active", "paused", "archived", "blocked", "missing"],
            },
            "include_archived": {
                "type": "boolean",
                "description": "Whether to include archived projects. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional agent system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_github_sync
# ---------------------------------------------------------------------------

PORTFOLIO_GITHUB_SYNC_SCHEMA = {
    "name": "portfolio_github_sync",
    "description": (
        "Read open GitHub issues and PRs for configured projects "
        "and update local SQLite state. Uses the gh CLI. Read-only against GitHub."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": ("Optional project ID. If omitted, sync all active projects."),
            },
            "include_paused": {
                "type": "boolean",
                "description": "Whether to include paused projects. Defaults to false.",
            },
            "max_items_per_project": {
                "type": "integer",
                "description": "Maximum issues and PRs to fetch per project. Defaults to 50.",
            },
            "root": {
                "type": "string",
                "description": "Optional agent system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_worktree_inspect
# ---------------------------------------------------------------------------

PORTFOLIO_WORKTREE_INSPECT_SCHEMA = {
    "name": "portfolio_worktree_inspect",
    "description": (
        "Inspect local worktree folders for configured projects. "
        "Detects clean, dirty, missing, blocked, and conflicted states. "
        "Read-only — does not modify any repository files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": ("Optional project ID. If omitted, inspect all active projects."),
            },
            "include_paused": {
                "type": "boolean",
                "description": "Whether to include paused projects. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional agent system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_status
# ---------------------------------------------------------------------------

PORTFOLIO_STATUS_SCHEMA = {
    "name": "portfolio_status",
    "description": (
        "Return a concise high-level status across all projects using the latest "
        "known state. Optionally refresh GitHub and worktree state first."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": ("Optional filter: all, needs_user. Defaults to all."),
                "enum": ["all", "needs_user"],
            },
            "refresh": {
                "type": "boolean",
                "description": (
                    "If true, run GitHub sync and worktree inspection before summarizing. Defaults to false."
                ),
            },
            "root": {
                "type": "string",
                "description": "Optional agent system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_heartbeat
# ---------------------------------------------------------------------------

PORTFOLIO_HEARTBEAT_SCHEMA = {
    "name": "portfolio_heartbeat",
    "description": (
        "Run the read-only portfolio heartbeat across all configured projects. "
        "This is the main tool called by the Hermes cron job. Validates config, "
        "syncs GitHub, inspects worktrees, updates state, returns concise digest."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_add
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_ADD_SCHEMA = {
    "name": "portfolio_project_add",
    "description": (
        "Add a new project to the portfolio. Creates config if missing. "
        "Pass validate_github=false to skip repo validation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "GitHub repo reference (owner/repo, HTTPS URL, or SSH URL)",
            },
            "name": {
                "type": "string",
                "description": "Human-readable project name (optional, defaults to repo name)",
            },
            "priority": {
                "type": "string",
                "description": "Priority: critical/high/medium/low/paused",
                "enum": ["critical", "high", "medium", "low", "paused"],
            },
            "status": {
                "type": "string",
                "description": "Status: active/paused/archived/blocked/missing",
                "enum": ["active", "paused", "archived", "blocked", "missing"],
            },
            "validate_github": {
                "type": "boolean",
                "description": "Whether to validate repo exists via gh CLI (default: true)",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["repo"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_update
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_UPDATE_SCHEMA = {
    "name": "portfolio_project_update",
    "description": "Update fields on an existing project (name, priority, status, notes, etc.).",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to update",
            },
            "name": {
                "type": "string",
                "description": "New human-readable project name",
            },
            "priority": {
                "type": "string",
                "description": "New priority: critical/high/medium/low/paused",
                "enum": ["critical", "high", "medium", "low", "paused"],
            },
            "status": {
                "type": "string",
                "description": "New status: active/paused/archived/blocked/missing",
                "enum": ["active", "paused", "archived", "blocked", "missing"],
            },
            "default_branch": {
                "type": "string",
                "description": "New default branch name",
            },
            "notes": {
                "type": "string",
                "description": "Project notes",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_pause
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_PAUSE_SCHEMA = {
    "name": "portfolio_project_pause",
    "description": "Pause a project. Sets status to 'paused' with optional reason.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to pause",
            },
            "reason": {
                "type": "string",
                "description": "Optional reason for pausing",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_resume
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_RESUME_SCHEMA = {
    "name": "portfolio_project_resume",
    "description": "Resume a paused project. Sets status back to 'active'.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to resume",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_archive
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_ARCHIVE_SCHEMA = {
    "name": "portfolio_project_archive",
    "description": "Archive a project. Sets status to 'archived' with optional reason. Preserves history.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to archive",
            },
            "reason": {
                "type": "string",
                "description": "Optional reason for archiving",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_set_priority
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_SET_PRIORITY_SCHEMA = {
    "name": "portfolio_project_set_priority",
    "description": "Set project priority. If priority is 'paused', also sets status to 'paused'.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to update",
            },
            "priority": {
                "type": "string",
                "description": "New priority: critical/high/medium/low/paused",
                "enum": ["critical", "high", "medium", "low", "paused"],
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id", "priority"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_set_auto_merge
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_SET_AUTO_MERGE_SCHEMA = {
    "name": "portfolio_project_set_auto_merge",
    "description": (
        "Set auto-merge policy for a project. MVP 2 stores policy only — it does not execute merges or create PRs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to update",
            },
            "enabled": {
                "type": "boolean",
                "description": "Whether auto-merge is enabled",
            },
            "max_risk": {
                "type": "string",
                "description": "Maximum risk level for auto-merge: low or medium",
                "enum": ["low", "medium"],
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id", "enabled"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_remove
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_REMOVE_SCHEMA = {
    "name": "portfolio_project_remove",
    "description": (
        "Remove a project from the portfolio entirely. Requires confirm=true. "
        "Consider archiving instead unless removal is necessary."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to remove",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to confirm removal",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id", "confirm"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_explain
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_EXPLAIN_SCHEMA = {
    "name": "portfolio_project_explain",
    "description": "Explain the current configuration of a project. Read-only — no mutations.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to explain",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": ["project_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_config_backup
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_CONFIG_BACKUP_SCHEMA = {
    "name": "portfolio_project_config_backup",
    "description": "Create a timestamped backup of the current projects.yaml config file.",
    "parameters": {
        "type": "object",
        "properties": {
            "root": {
                "type": "string",
                "description": "Optional system root override",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_project_resolve (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_PROJECT_RESOLVE_SCHEMA = {
    "name": "portfolio_project_resolve",
    "description": (
        "Resolve a project reference (name, ID, or owner/repo) to a project ID. "
        "Uses deterministic token scoring. Returns resolved, ambiguous, or not_found."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_ref": {
                "type": "string",
                "description": "Project reference: ID, name, or owner/repo string.",
            },
            "text": {
                "type": "string",
                "description": "Optional free-form text to help resolve the project.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_draft (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_DRAFT_SCHEMA = {
    "name": "portfolio_issue_draft",
    "description": (
        "Create an issue draft from user-supplied text. Resolves the project, "
        "generates a title, classifies the issue, computes readiness, and writes artifacts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Raw user text describing the issue or feature request.",
            },
            "project_ref": {
                "type": "string",
                "description": "Optional project reference to associate the draft with.",
            },
            "title": {
                "type": "string",
                "description": "Optional explicit title (auto-generated if omitted).",
            },
            "force_rough_issue": {
                "type": "boolean",
                "description": "If true, allow creation even with lower readiness. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["text"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_questions (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_QUESTIONS_SCHEMA = {
    "name": "portfolio_issue_questions",
    "description": "Read the clarifying questions for an existing issue draft.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID to read questions for.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["draft_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_update_draft (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA = {
    "name": "portfolio_issue_update_draft",
    "description": (
        "Update an existing issue draft with answers, project assignment, title change, "
        "or force readiness. Regenerates spec, questions, and readiness score."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID to update.",
            },
            "answers": {
                "type": "string",
                "description": "User answers to clarifying questions.",
            },
            "project_id": {
                "type": "string",
                "description": "Assign or reassign the draft to a project.",
            },
            "title": {
                "type": "string",
                "description": "New title for the draft.",
            },
            "force_ready": {
                "type": "boolean",
                "description": "Force the draft into ready_for_creation state. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["draft_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_create (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_CREATE_SCHEMA = {
    "name": "portfolio_issue_create",
    "description": (
        "Create a GitHub issue directly from text. Creates a local draft first, "
        "then creates the GitHub issue from that draft."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Project ID to create the issue in.",
            },
            "title": {
                "type": "string",
                "description": "Issue title.",
            },
            "body": {
                "type": "string",
                "description": "Issue body text.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to actually create the issue. Defaults to false.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, preview without creating. Defaults to false.",
            },
            "allow_possible_duplicate": {
                "type": "boolean",
                "description": "If true, allow creation even if a duplicate GitHub issue exists. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["project_id", "title", "body"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_create_from_draft (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA = {
    "name": "portfolio_issue_create_from_draft",
    "description": ("Create a GitHub issue from an existing draft. Requires confirm=true unless dry_run."),
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID to create the issue from.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to actually create the issue. Defaults to false.",
            },
            "allow_open_questions": {
                "type": "boolean",
                "description": "If true, allow creation even with open questions. Defaults to false.",
            },
            "allow_possible_duplicate": {
                "type": "boolean",
                "description": "If true, skip duplicate GitHub issue check. Defaults to false.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, preview without creating. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["draft_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_explain_draft (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA = {
    "name": "portfolio_issue_explain_draft",
    "description": "Explain the current state and content of an issue draft. Read-only.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID to explain.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["draft_id"],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_list_drafts (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA = {
    "name": "portfolio_issue_list_drafts",
    "description": "List issue drafts, optionally filtered by project and state.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "Optional project ID to filter drafts.",
            },
            "state": {
                "type": "string",
                "description": "Optional state filter.",
                "enum": [
                    "draft",
                    "needs_project_confirmation",
                    "needs_user_questions",
                    "ready_for_creation",
                    "creating",
                    "creating_failed",
                    "created",
                    "discarded",
                    "blocked",
                ],
            },
            "include_created": {
                "type": "boolean",
                "description": "Whether to include drafts already created as GitHub issues. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# portfolio_issue_discard_draft (MVP 3)
# ---------------------------------------------------------------------------

PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA = {
    "name": "portfolio_issue_discard_draft",
    "description": "Discard an issue draft. Requires confirm=true.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID to discard.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to confirm discard.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["draft_id", "confirm"],
    },
}

# ---------------------------------------------------------------------------
# MVP 4 — Maintenance tools
# ---------------------------------------------------------------------------

PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA = {
    "name": "portfolio_maintenance_skill_list",
    "description": (
        "List all registered maintenance skills with their enabled/disabled status from the maintenance config."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA = {
    "name": "portfolio_maintenance_skill_explain",
    "description": ("Show the skill spec and effective config for a specific maintenance skill."),
    "parameters": {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "Maintenance skill ID to explain.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project ID for project-specific config.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["skill_id"],
    },
}

PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA = {
    "name": "portfolio_maintenance_skill_enable",
    "description": "Enable a maintenance skill in the config.",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "Maintenance skill ID to enable.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project ID for project-scoped enable.",
            },
            "interval_hours": {
                "type": "integer",
                "description": "Optional check interval in hours.",
            },
            "config_json": {
                "type": "string",
                "description": "Optional JSON string with additional config overrides.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["skill_id"],
    },
}

PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA = {
    "name": "portfolio_maintenance_skill_disable",
    "description": "Disable a maintenance skill in the config.",
    "parameters": {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "Maintenance skill ID to disable.",
            },
            "project_id": {
                "type": "string",
                "description": "Optional project ID for project-scoped disable.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["skill_id"],
    },
}

PORTFOLIO_MAINTENANCE_DUE_SCHEMA = {
    "name": "portfolio_maintenance_due",
    "description": (
        "Check which maintenance skills are due to run across projects. Returns counts of due and not-due checks."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_filter": {
                "type": "string",
                "description": "Optional comma-separated project IDs to filter.",
            },
            "skill_filter": {
                "type": "string",
                "description": "Optional comma-separated skill IDs to filter.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

PORTFOLIO_MAINTENANCE_RUN_SCHEMA = {
    "name": "portfolio_maintenance_run",
    "description": (
        "Execute or dry-run a maintenance cycle across projects. "
        "In dry-run mode, returns planned checks without side effects."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "dry_run": {
                "type": "boolean",
                "description": "If true, plan only — no side effects. Defaults to true.",
            },
            "project_filter": {
                "type": "string",
                "description": "Optional comma-separated project IDs to filter.",
            },
            "skill_filter": {
                "type": "string",
                "description": "Optional comma-separated skill IDs to filter.",
            },
            "create_issue_drafts": {
                "type": "boolean",
                "description": "If true, create local issue drafts for draftable findings. Defaults to false.",
            },
            "refresh_github": {
                "type": "boolean",
                "description": "If true, refresh GitHub data before running. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA = {
    "name": "portfolio_maintenance_run_project",
    "description": (
        "Run maintenance for a single project. Resolves the project reference "
        "then delegates to the maintenance orchestrator."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project_ref": {
                "type": "string",
                "description": "Project reference: ID, name, or owner/repo string.",
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, plan only — no side effects. Defaults to true.",
            },
            "create_issue_drafts": {
                "type": "boolean",
                "description": "If true, create local issue drafts for draftable findings. Defaults to false.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": ["project_ref"],
    },
}

PORTFOLIO_MAINTENANCE_REPORT_SCHEMA = {
    "name": "portfolio_maintenance_report",
    "description": ("Load a maintenance report by run_id, or the latest report if no run_id given."),
    "parameters": {
        "type": "object",
        "properties": {
            "run_id": {
                "type": "string",
                "description": "Optional run ID. If omitted, returns the latest report.",
            },
            "project_filter": {
                "type": "string",
                "description": "Optional comma-separated project IDs to filter.",
            },
            "skill_filter": {
                "type": "string",
                "description": "Optional comma-separated skill IDs to filter.",
            },
            "severity_filter": {
                "type": "string",
                "description": "Optional severity filter: high, medium, low, info.",
            },
            "root": {
                "type": "string",
                "description": "Optional system root override.",
            },
        },
        "required": [],
    },
}

# ---------------------------------------------------------------------------
# All schemas in order
# ---------------------------------------------------------------------------

ALL_SCHEMAS = [
    # MVP 1
    PORTFOLIO_PING_SCHEMA,
    PORTFOLIO_CONFIG_VALIDATE_SCHEMA,
    PORTFOLIO_PROJECT_LIST_SCHEMA,
    PORTFOLIO_GITHUB_SYNC_SCHEMA,
    PORTFOLIO_WORKTREE_INSPECT_SCHEMA,
    PORTFOLIO_STATUS_SCHEMA,
    PORTFOLIO_HEARTBEAT_SCHEMA,
    # MVP 2
    PORTFOLIO_PROJECT_ADD_SCHEMA,
    PORTFOLIO_PROJECT_UPDATE_SCHEMA,
    PORTFOLIO_PROJECT_PAUSE_SCHEMA,
    PORTFOLIO_PROJECT_RESUME_SCHEMA,
    PORTFOLIO_PROJECT_ARCHIVE_SCHEMA,
    PORTFOLIO_PROJECT_SET_PRIORITY_SCHEMA,
    PORTFOLIO_PROJECT_SET_AUTO_MERGE_SCHEMA,
    PORTFOLIO_PROJECT_REMOVE_SCHEMA,
    PORTFOLIO_PROJECT_EXPLAIN_SCHEMA,
    PORTFOLIO_PROJECT_CONFIG_BACKUP_SCHEMA,
    # MVP 3
    PORTFOLIO_PROJECT_RESOLVE_SCHEMA,
    PORTFOLIO_ISSUE_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_QUESTIONS_SCHEMA,
    PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_CREATE_SCHEMA,
    PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA,
    PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA,
    # MVP 4
    PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA,
    PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA,
    PORTFOLIO_MAINTENANCE_DUE_SCHEMA,
    PORTFOLIO_MAINTENANCE_RUN_SCHEMA,
    PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA,
    PORTFOLIO_MAINTENANCE_REPORT_SCHEMA,
]
