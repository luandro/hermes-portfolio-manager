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
                "description": ("Optional agent system root. Defaults to AGENT_SYSTEM_ROOT or /srv/agent-system."),
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
# All schemas in order
# ---------------------------------------------------------------------------

ALL_SCHEMAS = [
    PORTFOLIO_PING_SCHEMA,
    PORTFOLIO_CONFIG_VALIDATE_SCHEMA,
    PORTFOLIO_PROJECT_LIST_SCHEMA,
    PORTFOLIO_GITHUB_SYNC_SCHEMA,
    PORTFOLIO_WORKTREE_INSPECT_SCHEMA,
    PORTFOLIO_STATUS_SCHEMA,
    PORTFOLIO_HEARTBEAT_SCHEMA,
]
