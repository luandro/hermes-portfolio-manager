# SPEC.md — Hermes Portfolio Manager Plugin MVP 1

## Purpose

Build the first MVP of the Hermes Portfolio Manager plugin.

This plugin lets a single Hermes Agent manage many GitHub projects from one server-side configuration. MVP 1 is intentionally read-only and safe. It should let Hermes answer questions like:

* What projects am I managing?
* What needs my attention?
* Which projects have open issues or PRs?
* Which local worktrees are clean, dirty, missing, or conflicted?
* What happened in the latest portfolio heartbeat?

MVP 1 must not perform autonomous coding, create issues, create branches, modify files in repositories, open PRs, merge PRs, or change project configuration. It only reads configuration, inspects GitHub/project/worktree state, writes runtime state, and returns concise summaries to Hermes.

---

# Product Goal

The user installs Hermes on a VPS, connects Telegram and GitHub, and installs this plugin. After that, the user can ask Hermes through Telegram:

```txt
What needs me?
```

Hermes should call the plugin, inspect all configured projects, and reply with a concise status digest.

The plugin must support a single Hermes Agent managing multiple projects.

There must not be one Hermes Agent per repo.

---

# Scope of MVP 1

MVP 1 includes:

1. Hermes plugin skeleton.
2. Server-side config loading.
3. Project listing.
4. Read-only portfolio status.
5. Read-only GitHub sync.
6. Read-only worktree inspection.
7. Read-only portfolio heartbeat.
8. SQLite state integration through `agent-state` or direct local state module.
9. Structured tool results for Hermes.
10. Clear human-readable summaries for Telegram.

MVP 1 excludes:

* adding projects through Telegram
* editing manifests
* creating GitHub issues
* brainstorming issues
* creating worktrees
* modifying worktrees
* running maintenance skills
* autonomous implementation
* review ladder automation
* model/provider budget routing
* auto-merge

Those belong to later MVPs.

---

# Hermes Integration Assumptions

Hermes plugins are installed as directories under:

```txt
~/.hermes/plugins/<plugin-name>/
```

This plugin should use the standard Hermes plugin structure:

```txt
~/.hermes/plugins/portfolio-manager/
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
```

The plugin should register tools that Hermes can call from normal conversation, Telegram, Slack, cron jobs, or skills.

MVP 1 should also include Hermes skills, but those skills should only instruct Hermes when and how to call the plugin tools. Business logic must live in the plugin/tools, not in long prompts.

---

# Server-Side System Layout

The plugin must use server-side configuration and state.

Default root:

```txt
/srv/agent-system
```

Allow override with:

```bash
AGENT_SYSTEM_ROOT=/custom/path
```

Expected layout:

```txt
/srv/agent-system/
  config/
    projects.yaml
    user.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
```

MVP 1 only requires:

```txt
config/projects.yaml
state/state.sqlite
worktrees/
```

No repo-local automation YAML should be required.

Repos may contain normal guidance files such as:

```txt
README.md
AGENTS.md
CLAUDE.md
package.json
Makefile
justfile
```

But automation policy lives on the server.

---

# Server-Side Project Config

MVP 1 should read:

```txt
/srv/agent-system/config/projects.yaml
```

Example:

```yaml
version: 1
projects:
  - id: comapeo-cloud-app
    name: CoMapeo Cloud App
    repo: git@github.com:awana-digital/comapeo-cloud-app.git
    github:
      owner: awana-digital
      repo: comapeo-cloud-app
    priority: high
    status: active
    default_branch: auto
    local:
      base_path: /srv/agent-system/worktrees/comapeo-cloud-app
      issue_worktree_pattern: /srv/agent-system/worktrees/comapeo-cloud-app-issue-{issue_number}
    protected_paths:
      - .github/workflows/**
      - infra/**
      - auth/**
      - migrations/**
    labels:
      auto_develop_candidates:
        - agent-candidate
      high_impact:
        - architecture
        - security
        - migration

  - id: edt-next
    name: EDT Website Migration
    repo: git@github.com:awana-digital/edt-next.git
    github:
      owner: awana-digital
      repo: edt-next
    priority: medium
    status: active
    default_branch: auto
    local:
      base_path: /srv/agent-system/worktrees/edt-next
      issue_worktree_pattern: /srv/agent-system/worktrees/edt-next-issue-{issue_number}
```

Required fields:

```txt
id
name
repo
github.owner
github.repo
priority
status
```

Optional fields:

```txt
default_branch
local.base_path
local.issue_worktree_pattern
protected_paths
labels
```

Allowed priorities:

```txt
critical
high
medium
low
paused
```

Allowed project statuses:

```txt
active
paused
archived
blocked
missing
```

MVP 1 should ignore archived projects by default.

---

# Plugin Directory Structure

Create:

```txt
hermes-portfolio-manager/
  SPEC.md
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
  config.py
  github_client.py
  worktree.py
  state.py
  summary.py
  errors.py
  skills/
    portfolio-heartbeat/
      SKILL.md
    portfolio-status/
      SKILL.md
  tests/
    test_config.py
    test_worktree.py
    test_summary.py
    test_tools.py
```

When installed into Hermes:

```txt
~/.hermes/plugins/portfolio-manager/
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
  config.py
  github_client.py
  worktree.py
  state.py
  summary.py
  errors.py
  skills/
    portfolio-heartbeat/
      SKILL.md
    portfolio-status/
      SKILL.md
```

---

# `plugin.yaml`

Create plugin manifest:

```yaml
name: portfolio-manager
version: 0.1.0
description: Manage multiple GitHub projects from one server-side manifest. MVP 1 is read-only.
author: Awana Digital
license: MIT
```

If Hermes requires additional fields, add them, but keep the plugin name stable:

```txt
portfolio-manager
```

---

# Tool Naming

All plugin tools should use the prefix:

```txt
portfolio_
```

MVP 1 tools:

```txt
portfolio_config_validate
portfolio_project_list
portfolio_status
portfolio_github_sync
portfolio_worktree_inspect
portfolio_heartbeat
```

These tools must be read-only with respect to GitHub and local repos.

They may write to the system SQLite state and logs.

---

# Shared Tool Result Format

Every tool must return a dictionary with this shape:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "portfolio_status",
    "message": "Human-readable one-line result",
    "data": {...},
    "summary": "Concise Telegram-friendly summary"
}
```

Rules:

* `summary` must be readable directly by a user on Telegram.
* `data` must be structured and machine-readable.
* `status=blocked` means the tool intentionally could not proceed, such as missing config or missing GitHub CLI.
* `status=failed` means an unexpected error occurred.
* Do not expose secrets, tokens, env vars, private keys, or full stack traces.

---

# Tool 1: `portfolio_config_validate`

## Purpose

Validate server-side config without contacting GitHub or inspecting worktrees.

## Input schema

```python
{
    "root": {
        "type": "string",
        "description": "Optional agent system root. Defaults to AGENT_SYSTEM_ROOT or /srv/agent-system."
    }
}
```

All inputs optional.

## Behavior

1. Resolve root path.
2. Check that `config/projects.yaml` exists.
3. Parse YAML.
4. Validate top-level `version` and `projects` list.
5. Validate each project required field.
6. Validate priority/status enums.
7. Check for duplicate project IDs.
8. Check that `state/` and `worktrees/` directories exist or can be created.
9. Return structured validation result.

This tool may create these directories if missing:

```txt
state/
worktrees/
logs/
artifacts/
```

It must not create or modify `projects.yaml`.

## Output data

```python
{
    "root": "/srv/agent-system",
    "config_path": "/srv/agent-system/config/projects.yaml",
    "valid": True,
    "project_count": 3,
    "warnings": [],
    "errors": []
}
```

## Success summary example

```txt
Portfolio config is valid. I found 3 projects: 2 active, 1 paused.
```

## Blocked summary example

```txt
Portfolio config is missing: /srv/agent-system/config/projects.yaml. Create this file before running the portfolio heartbeat.
```

---

# Tool 2: `portfolio_project_list`

## Purpose

List configured projects from the server manifest.

## Input schema

```python
{
    "status": {
        "type": "string",
        "description": "Optional project status filter: active, paused, archived, blocked, missing."
    },
    "include_archived": {
        "type": "boolean",
        "description": "Whether to include archived projects. Defaults to false."
    },
    "root": {
        "type": "string",
        "description": "Optional system root override."
    }
}
```

## Behavior

1. Load and validate config.
2. Filter projects by status if provided.
3. Exclude archived projects unless `include_archived=true`.
4. Sort projects by priority:

   * critical
   * high
   * medium
   * low
   * paused
5. Return structured list and Telegram-friendly summary.

## Output data

```python
{
    "projects": [
        {
            "id": "comapeo-cloud-app",
            "name": "CoMapeo Cloud App",
            "repo": "git@github.com:awana-digital/comapeo-cloud-app.git",
            "github": {
                "owner": "awana-digital",
                "repo": "comapeo-cloud-app"
            },
            "priority": "high",
            "status": "active"
        }
    ],
    "counts": {
        "active": 1,
        "paused": 0,
        "archived": 0,
        "blocked": 0,
        "missing": 0
    }
}
```

## Summary example

```txt
I am managing 3 projects.

High priority:
- CoMapeo Cloud App

Medium priority:
- EDT Website Migration

Low priority:
- Docs Support Bot
```

---

# Tool 3: `portfolio_github_sync`

## Purpose

Read open GitHub issues and PRs for configured projects and update local SQLite state.

This tool is read-only against GitHub.

## Input schema

```python
{
    "project_id": {
        "type": "string",
        "description": "Optional project ID. If omitted, sync all active projects."
    },
    "include_paused": {
        "type": "boolean",
        "description": "Whether to include paused projects. Defaults to false."
    },
    "max_items_per_project": {
        "type": "integer",
        "description": "Maximum issues and PRs to fetch per project. Defaults to 50."
    },
    "root": {
        "type": "string",
        "description": "Optional system root override."
    }
}
```

## Implementation requirement

Use GitHub CLI `gh` for MVP 1.

Do not call GitHub API directly unless `gh` is unavailable and a clearly isolated fallback already exists.

Commands may use:

```bash
gh issue list --repo OWNER/REPO --state open --limit 50 --json number,title,labels,author,createdAt,updatedAt,url

gh pr list --repo OWNER/REPO --state open --limit 50 --json number,title,headRefName,baseRefName,labels,reviewDecision,statusCheckRollup,createdAt,updatedAt,url
```

## Behavior

1. Load projects.
2. Select target projects.
3. Check that `gh` is installed.
4. Check that GitHub auth is available by running:

```bash
gh auth status
```

5. For each target project:

   * fetch open issues
   * fetch open PRs
   * upsert issue records into SQLite
   * upsert PR records into SQLite
   * collect counts and warnings
6. Return summary.

## State mapping

For MVP 1, map GitHub issues conservatively:

```txt
open issue not seen before -> needs_triage
open issue already known -> keep existing local state unless it was closed/merged
```

For MVP 1, map PRs conservatively:

```txt
open PR not seen before -> open
open PR with failing checks -> checks_failed
open PR with changes requested -> changes_requested
open PR with no review decision -> review_pending
open PR with approved review and passing checks -> ready_for_human
```

If exact GitHub review/check fields are unavailable, store raw data and use `open` or `review_pending`.

## Output data

```python
{
    "projects_synced": 2,
    "issues_seen": 14,
    "prs_seen": 3,
    "projects": [
        {
            "id": "comapeo-cloud-app",
            "issues_seen": 8,
            "prs_seen": 2,
            "warnings": []
        }
    ]
}
```

## Summary example

```txt
GitHub sync complete.

2 projects synced.
14 open issues seen.
3 open PRs seen.

Needs attention:
- CoMapeo Cloud App has 1 PR with failing checks.
- EDT Website Migration has 2 issues needing triage.
```

---

# Tool 4: `portfolio_worktree_inspect`

## Purpose

Inspect local worktree folders for configured projects.

This tool is read-only. It must not run `git stash`, `git rebase`, `git pull`, `git clean`, `git reset`, or modify files.

## Input schema

```python
{
    "project_id": {
        "type": "string",
        "description": "Optional project ID. If omitted, inspect all active projects."
    },
    "include_paused": {
        "type": "boolean",
        "description": "Whether to include paused projects. Defaults to false."
    },
    "root": {
        "type": "string",
        "description": "Optional system root override."
    }
}
```

## Worktree naming convention

Base project worktree:

```txt
/srv/agent-system/worktrees/{project_id}
```

Issue worktree:

```txt
/srv/agent-system/worktrees/{project_id}-issue-{issue_number}
```

If a project config provides `local.base_path` or `local.issue_worktree_pattern`, use that instead.

## Behavior

1. Load projects.
2. For each selected project:

   * inspect base worktree path
   * discover issue worktrees matching pattern
   * run read-only Git commands in each existing worktree
3. Determine state:

   * `missing`
   * `clean`
   * `dirty_uncommitted`
   * `dirty_untracked`
   * `rebase_conflict`
   * `merge_conflict`
   * `blocked`
4. Upsert worktree state into SQLite.
5. Return structured result and concise summary.

## Allowed Git commands

Only use read-only commands:

```bash
git status --porcelain=v1
git branch --show-current
git rev-parse --is-inside-work-tree
git rev-parse --abbrev-ref HEAD
git rev-parse --show-toplevel
git rev-parse --git-path rebase-merge
git rev-parse --git-path rebase-apply
git rev-parse --git-path MERGE_HEAD
```

Do not run commands that modify repository state.

## State detection rules

### `missing`

Path does not exist.

### `blocked`

Path exists but is not a Git worktree.

### `rebase_conflict`

Either of these exists:

```txt
.git/rebase-merge
.git/rebase-apply
```

Use `git rev-parse --git-path` to resolve paths correctly.

### `merge_conflict`

`MERGE_HEAD` exists or `git status --porcelain` shows unmerged entries.

### `dirty_untracked`

`git status --porcelain` includes lines beginning with:

```txt
??
```

### `dirty_uncommitted`

`git status --porcelain` includes modified, added, deleted, renamed, copied, or unmerged tracked changes.

### `clean`

`git status --porcelain` is empty and no rebase/merge state exists.

## Output data

```python
{
    "projects_inspected": 2,
    "worktrees": [
        {
            "project_id": "comapeo-cloud-app",
            "path": "/srv/agent-system/worktrees/comapeo-cloud-app",
            "kind": "base",
            "state": "clean",
            "branch": "main"
        },
        {
            "project_id": "comapeo-cloud-app",
            "issue_number": 123,
            "path": "/srv/agent-system/worktrees/comapeo-cloud-app-issue-123",
            "kind": "issue",
            "state": "dirty_uncommitted",
            "branch": "agent/123-export-smp",
            "dirty_summary": "2 modified files"
        }
    ],
    "counts": {
        "clean": 1,
        "dirty_uncommitted": 1,
        "dirty_untracked": 0,
        "rebase_conflict": 0,
        "merge_conflict": 0,
        "missing": 0,
        "blocked": 0
    }
}
```

## Summary example

```txt
Worktree inspection complete.

2 projects inspected.
1 dirty worktree found:
- comapeo-cloud-app-issue-123: 2 modified files.

No merge or rebase conflicts found.
```

---

# Tool 5: `portfolio_status`

## Purpose

Return a concise high-level status across all projects using the latest known state.

This tool should be fast. It may optionally refresh GitHub/worktree state if requested.

## Input schema

```python
{
    "refresh": {
        "type": "boolean",
        "description": "If true, run GitHub sync and worktree inspection before summarizing. Defaults to false."
    },
    "filter": {
        "type": "string",
        "description": "Optional filter: all, needs_user, blocked, prs, issues. Defaults to all."
    },
    "root": {
        "type": "string",
        "description": "Optional system root override."
    }
}
```

Allowed filters:

```txt
all
needs_user
blocked
prs
issues
```

## Behavior

1. Load projects.
2. If `refresh=true`, run:

   * `portfolio_github_sync`
   * `portfolio_worktree_inspect`
3. Read SQLite state.
4. Compute portfolio summary:

   * active projects
   * paused projects
   * issues needing triage/spec/user input
   * PRs ready for human review
   * PRs with failing checks
   * dirty/conflicted/missing worktrees
5. Return Telegram-friendly summary.

## Needs-user classification

Items need the user if they are:

```txt
issue.state = needs_user_questions
issue.state = spec_ready and project policy requires approval before implementation
pr.state = ready_for_human
pr.state = qa_required
worktree.state = rebase_conflict
worktree.state = merge_conflict
worktree.state = dirty_uncommitted
worktree.state = dirty_untracked
```

MVP 1 does not implement project policy deeply, so `spec_ready requires approval` can be skipped unless state already exists.

## Summary example

```txt
Portfolio status:

3 active projects.

Needs you:
1. CoMapeo Cloud App PR #130 is ready for human review.
2. EDT Website Migration issue #47 needs clarification.
3. comapeo-cloud-app-issue-118 is dirty and blocked.

No provider budget warnings in MVP 1.
```

---

# Tool 6: `portfolio_heartbeat`

## Purpose

Run the read-only MVP portfolio heartbeat across all configured projects.

This is the main tool called by the Hermes cron job.

## Input schema

```python
{
    "root": {
        "type": "string",
        "description": "Optional system root override."
    },
    "include_paused": {
        "type": "boolean",
        "description": "Whether to include paused projects. Defaults to false."
    },
    "max_items_per_project": {
        "type": "integer",
        "description": "Maximum GitHub issues/PRs to fetch per project. Defaults to 50."
    }
}
```

## Behavior

1. Acquire global heartbeat lock in SQLite.
2. Start heartbeat row in SQLite.
3. Validate config.
4. List active projects.
5. Run GitHub sync for all active projects.
6. Run worktree inspection for all active projects.
7. Compute portfolio status.
8. Write heartbeat events to SQLite.
9. Finish heartbeat row.
10. Release lock.
11. Return concise summary.

If lock is already held, return:

```python
{
    "status": "blocked",
    "reason": "heartbeat_lock_already_held"
}
```

## Lock name

Use:

```txt
heartbeat:portfolio
```

Default TTL:

```txt
900 seconds
```

## Summary example

```txt
Portfolio heartbeat complete.

3 projects checked.
14 open issues seen.
3 open PRs seen.
1 dirty worktree found.

Needs you:
1. CoMapeo Cloud App PR #130 is ready for review.
2. EDT Website Migration issue #47 needs clarification.
3. Worktree comapeo-cloud-app-issue-118 is dirty.
```

## Failure behavior

If one project fails, do not fail the whole heartbeat unless config or state initialization fails.

Example:

```txt
GitHub sync failed for one project because the repo was inaccessible. Continue with other projects and report the warning.
```

---

# SQLite State Integration

MVP 1 may either:

1. call the `agent-state` CLI, or
2. import/use a small Python state helper that writes the same schema.

Preferred for MVP 1:

```txt
Use direct Python SQLite access inside the plugin, but keep schema compatible with agent-state SPEC.md.
```

Reason: Hermes plugins are Python-based, and shelling out to a TypeScript CLI for every upsert may be slower and more fragile.

Minimum tables required by MVP 1:

```txt
projects
issues
pull_requests
worktrees
heartbeats
heartbeat_events
locks
```

If tables do not exist, the plugin should either:

* initialize the minimum schema automatically, or
* return blocked with clear instructions to run `agent-state init`.

For MVP 1, prefer automatic initialization of the minimum schema.

---

# GitHub CLI Requirements

MVP 1 depends on `gh`.

Before GitHub sync, check:

```bash
gh --version
gh auth status
```

If `gh` is missing:

```txt
Return blocked: GitHub CLI is not installed.
```

If `gh` is unauthenticated:

```txt
Return blocked: GitHub CLI is not authenticated. Run `gh auth login` on the server.
```

Never print tokens or auth details.

---

# Hermes Skills

MVP 1 should include two skills.

## Skill: `portfolio-status`

Path:

```txt
skills/portfolio-status/SKILL.md
```

Content:

```md
---
name: portfolio-status
description: Check the status of all managed GitHub projects using the Portfolio Manager plugin.
---

Use this skill when the user asks:

- What needs me?
- What happened overnight?
- What is the status of my projects?
- Are there blocked worktrees?
- Which PRs need review?

Call the `portfolio_status` tool.

If the user asks for the freshest possible status, call `portfolio_status` with `refresh=true`.

Keep the response concise and action-oriented. Highlight only:

1. user decisions needed,
2. PRs ready for review or QA,
3. dirty/conflicted worktrees,
4. inaccessible projects,
5. major warnings.
```

## Skill: `portfolio-heartbeat`

Path:

```txt
skills/portfolio-heartbeat/SKILL.md
```

Content:

```md
---
name: portfolio-heartbeat
description: Run the read-only portfolio heartbeat across all configured projects.
---

Use this skill for scheduled portfolio checks.

Call the `portfolio_heartbeat` tool.

The heartbeat should:

1. validate server-side config,
2. sync open GitHub issues and PRs,
3. inspect local worktrees,
4. update local state,
5. return only blockers, user decisions, PRs ready for review, and warnings.

Do not start implementation.
Do not create issues.
Do not create branches.
Do not modify files.
Do not merge PRs.
```

---

# Recommended Hermes Cron Job

After installing the plugin and skills, create one cron job in Hermes:

```txt
Name: Portfolio heartbeat
Schedule: every 30 minutes, or user-defined active window
Skill: portfolio-heartbeat
Prompt: Run the read-only portfolio heartbeat. Check all configured projects from the server-side manifest. Return only blockers, user decisions, PRs ready for review, dirty/conflicted worktrees, and major warnings.
```

The cron job must manage all projects through one portfolio heartbeat.

Do not create one cron job per project for MVP 1.

---

# Security Rules

MVP 1 must be safe by default.

The plugin must not:

* modify GitHub state
* create issues
* create comments
* create labels
* create branches
* modify files
* run package manager commands
* run tests
* run coding harnesses
* run AI coding agents
* run `git pull`
* run `git rebase`
* run `git merge`
* run `git reset`
* run `git clean`
* run `git stash`
* run shell commands from user input

Allowed external commands:

```txt
gh --version
gh auth status
gh issue list ...
gh pr list ...
git status --porcelain=v1
git branch --show-current
git rev-parse ...
```

All subprocess calls must use argument arrays, not shell strings.

Do not use `shell=True`.

---

# Error Handling

The plugin must handle these expected errors gracefully:

* missing config file
* invalid YAML
* duplicate project IDs
* missing `gh`
* unauthenticated GitHub CLI
* inaccessible GitHub repo
* missing worktree path
* path exists but is not Git repo
* SQLite database locked
* heartbeat lock already held
* subprocess timeout

Subprocess timeout default:

```txt
30 seconds per command
```

For large GitHub syncs, allow:

```txt
60 seconds per project
```

---

# Logging

MVP 1 should write structured heartbeat events to SQLite.

It may also write local JSONL logs to:

```txt
/srv/agent-system/logs/YYYY-MM-DD/portfolio-heartbeat.jsonl
```

Each event should include:

```json
{
  "timestamp": "2026-04-25T10:00:00.000Z",
  "level": "info",
  "type": "github.sync.project",
  "project_id": "comapeo-cloud-app",
  "message": "GitHub sync completed",
  "data": {
    "issues_seen": 8,
    "prs_seen": 2
  }
}
```

Do not log secrets.

---

# Tests

Use Python tests, preferably `pytest`.

Required tests:

## Config tests

* loads valid projects.yaml
* rejects missing projects.yaml
* rejects invalid YAML
* rejects duplicate project IDs
* rejects invalid priority
* rejects invalid status
* excludes archived projects by default

## Worktree tests

Use temporary Git repos.

Test detection of:

* missing path
* path exists but not Git repo
* clean repo
* dirty tracked file
* dirty untracked file
* merge conflict indicator if feasible
* issue worktree name parsing

## Summary tests

* summarizes project counts
* summarizes needs-user items
* summarizes dirty worktrees
* does not include noisy low-value details

## Tool tests

Mock subprocess calls for GitHub commands.

Test:

* `portfolio_config_validate`
* `portfolio_project_list`
* `portfolio_github_sync`
* `portfolio_worktree_inspect`
* `portfolio_status`
* `portfolio_heartbeat`

## Lock tests

* heartbeat acquires lock
* heartbeat blocked if lock held
* expired lock can be replaced
* lock released after successful heartbeat
* lock released after handled failure

---

# Acceptance Criteria

MVP 1 is complete when:

1. Hermes loads the plugin without errors.
2. Hermes can see all MVP 1 tools.
3. `portfolio_config_validate` validates server-side project config.
4. `portfolio_project_list` lists all configured active projects.
5. `portfolio_github_sync` reads open issues and PRs using `gh` and updates SQLite.
6. `portfolio_worktree_inspect` detects clean, dirty, missing, blocked, and conflicted worktrees without modifying them.
7. `portfolio_status` returns a concise user-facing summary.
8. `portfolio_heartbeat` checks all active projects from one call.
9. The heartbeat uses one global lock.
10. The plugin does not require repo-local project YAML.
11. The plugin does not modify GitHub or repository files.
12. The plugin handles one project failing without failing the entire portfolio heartbeat.
13. Telegram responses are concise and action-oriented when Hermes uses the returned summaries.
14. Tests cover config parsing, worktree inspection, summaries, locks, and tool behavior.

---

# Implementation Plan for Agent

Follow these steps exactly.

## Step 1: Create plugin skeleton

Create:

```txt
hermes-portfolio-manager/
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
```

Add helper modules:

```txt
config.py
github_client.py
worktree.py
state.py
summary.py
errors.py
```

## Step 2: Implement config loader

In `config.py`:

* resolve root
* load YAML
* validate project fields
* normalize project paths
* sort/filter projects

Use `pydantic` if available, otherwise plain dataclasses plus explicit validation.

## Step 3: Implement SQLite state helper

In `state.py`:

* open database
* initialize minimum schema if missing
* acquire/release lock
* upsert projects
* upsert issues
* upsert PRs
* upsert worktrees
* start/finish heartbeat
* add event

Keep schema compatible with the broader `agent-state` spec.

## Step 4: Implement GitHub client

In `github_client.py`:

* check `gh` installed
* check `gh auth status`
* list open issues
* list open PRs
* parse JSON safely
* return structured errors per project

Use subprocess argument arrays.

Never use `shell=True`.

## Step 5: Implement worktree inspector

In `worktree.py`:

* inspect base project paths
* discover issue worktrees by naming convention
* run read-only Git commands
* detect state
* return structured worktree records

## Step 6: Implement summaries

In `summary.py`:

* create concise Telegram-friendly summaries
* prioritize user attention
* avoid noisy full listings unless requested

## Step 7: Implement Hermes tool schemas

In `schemas.py`, define schemas for:

```txt
portfolio_config_validate
portfolio_project_list
portfolio_github_sync
portfolio_worktree_inspect
portfolio_status
portfolio_heartbeat
```

Each schema should describe parameters clearly for the LLM.

## Step 8: Register tools

In `__init__.py`, register all schemas and handlers according to Hermes plugin conventions.

## Step 9: Implement tool handlers

In `tools.py`, wire tools to helper modules.

Handlers should:

1. validate input
2. call helper logic
3. update state where appropriate
4. return shared tool result format
5. catch expected exceptions

## Step 10: Add skills

Create:

```txt
skills/portfolio-status/SKILL.md
skills/portfolio-heartbeat/SKILL.md
```

Use the content specified above.

## Step 11: Add tests

Add pytest tests for config, worktree, summary, tools, and locks.

Use temp directories and temp SQLite files.

Mock GitHub subprocess calls.

## Step 12: Manual test inside Hermes

Install plugin into:

```txt
~/.hermes/plugins/portfolio-manager
```

Restart Hermes.

Ask Hermes:

```txt
List my managed projects.
```

Expected: Hermes calls `portfolio_project_list`.

Ask:

```txt
What needs me?
```

Expected: Hermes calls `portfolio_status`, likely with `refresh=true` if fresh status is needed.

Run manually:

```txt
Run the portfolio heartbeat.
```

Expected: Hermes calls `portfolio_heartbeat` and returns concise digest.

---

# Future MVPs

Do not implement these yet, but leave extension points for them.

## MVP 2

Project management through Telegram:

```txt
project_add
project_pause
project_resume
project_set_priority
project_remove
```

## MVP 3

Issue creation and brainstorming:

```txt
issue_create
issue_brainstorm
issue_spec_draft
issue_questions
```

## MVP 4

Maintenance skills:

```txt
maintenance_skill_list
maintenance_skill_enable
maintenance_run_due
```

## MVP 5

Safe implementation:

```txt
worktree_create
implementation_start
pr_create
qa_script_generate
```

## MVP 6

Review ladder:

```txt
review_status
review_start
review_continue
review_summarize
```

---

# Final Notes

MVP 1 should prove that one Hermes Agent can manage many projects safely.

The user experience should be simple:

```txt
User: What needs me?
Hermes: 3 active projects checked. PR #130 needs QA. Issue #47 needs clarification. One worktree is dirty.
```
