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
]
