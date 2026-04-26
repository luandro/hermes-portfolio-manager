# SPEC.md — Hermes Portfolio Manager Plugin MVP 2: Project Administration

## Purpose

MVP 2 adds safe project administration to the Hermes Portfolio Manager plugin.

MVP 1 was read-only. It validated config, listed projects, synced GitHub issues/PRs, inspected worktrees, and produced portfolio status/heartbeat summaries.

MVP 2 allows the user to manage the server-side project manifest through Hermes, including from Telegram.

The user should be able to say:

```txt
Add awana-digital/edt-next as a medium-priority project. Never auto-merge it.
```

Hermes should call plugin tools that safely update the server-side config under:

```txt
$HOME/.agent-system
```

MVP 2 is still not an autonomous coding system. It does not create issues, create branches, modify repositories, run coding harnesses, or merge PRs.

---

# Major System Path Change

Previous specs used:

```txt
/srv/agent-system
```

Starting with MVP 2, the default system root is:

```txt
$HOME/.agent-system
```

In code, do not hardcode `/usr/HOME`.

Use:

```python
Path.home() / ".agent-system"
```

Allow override with:

```bash
AGENT_SYSTEM_ROOT=/custom/path
```

Priority order:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

Runtime layout:

```txt
$HOME/.agent-system/
  config/
    projects.yaml
    providers.yaml
    review-ladders.yaml
    skills.yaml
    telegram.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
  backups/
```

MVP 2 requires:

```txt
config/projects.yaml
state/state.sqlite
worktrees/
logs/
artifacts/
backups/
```

---

# What MVP 2 Adds

MVP 2 adds these project administration tools:

```txt
portfolio_project_add
portfolio_project_update
portfolio_project_pause
portfolio_project_resume
portfolio_project_archive
portfolio_project_set_priority
portfolio_project_set_auto_merge
portfolio_project_remove
portfolio_project_explain
portfolio_project_config_backup
```

It also adds a Hermes skill:

```txt
project-admin
```

MVP 2 should support both:

1. Hermes tool calls from conversation/Telegram.
2. Local execution through `dev_cli.py` for testing outside Hermes.

---

# Explicit Non-Goals

MVP 2 must not:

* create GitHub issues
* brainstorm issues
* create branches
* create worktrees, except optionally clone/read-only validation is allowed only if explicitly configured as a future extension
* modify repository files
* run package managers
* run tests
* run coding harnesses
* trigger PR review ladders
* auto-develop
* auto-merge
* edit repo-local YAML

MVP 2 only changes server-side project configuration and local state.

---

# Critique of the MVP 2 Design

Before implementation, the design needs to avoid several risks.

## Risk 1: Telegram commands can accidentally mutate long-term config

A user may say:

```txt
Focus on this project tonight.
```

That should not permanently change project priority.

MVP 2 should only implement durable config mutations when the tool call is explicit. Temporary priority/focus overrides should be stored in state as future work, not added unless explicitly specified.

For MVP 2, supported durable mutations are:

```txt
add project
update project fields
pause project
resume project
archive project
remove project with confirmation
set priority
set auto-merge policy
```

Temporary overrides are not part of MVP 2 unless added as a later tool.

## Risk 2: Direct YAML writes can corrupt config

The plugin must use atomic writes:

1. read current config
2. validate current config
3. apply mutation in memory
4. validate new config
5. create timestamped backup
6. write to temp file
7. fsync temp file if possible
8. atomic rename over `projects.yaml`
9. reload and validate written config
10. update SQLite state

## Risk 3: Concurrent writes from cron and Telegram

MVP 2 must use a config write lock.

Lock name:

```txt
config:projects
```

Use SQLite lock table if available from MVP 1.

If lock is held, return:

```txt
blocked
```

Do not attempt simultaneous YAML writes.

## Risk 4: Project identity can become ambiguous

MVP 2 must distinguish:

* `project_id`, internal stable slug
* `name`, human display name
* GitHub owner/repo
* Git remote URL

Default `project_id` should be generated from GitHub repo name, but if there is a duplicate, the tool must block and ask for an explicit ID.

## Risk 5: GitHub repo validation can become a hidden mutation

Repo validation must be read-only.

Allowed GitHub validation command:

```bash
gh repo view OWNER/REPO --json name,owner,defaultBranchRef,url,isPrivate
```

Do not create GitHub resources in MVP 2.

## Risk 6: Auto-merge policy is dangerous

MVP 2 may store auto-merge settings, but it must not perform auto-merge.

Default must be:

```yaml
auto_merge:
  enabled: false
```

Any request to enable auto-merge must be stored conservatively and clearly marked as future policy only.

## Risk 7: Removing a project can lose history

Default behavior should be archive, not delete.

`portfolio_project_remove` must require:

```txt
confirm=True
```

Even with confirmation, the safer behavior should be to remove from active config but leave SQLite history untouched.

---

# Is This Implementation Ready?

This version is designed to be implementation-ready for coding agents.

It includes:

* exact default root path
* exact tool names
* exact config schema changes
* exact mutation behavior
* lock requirements
* atomic write requirements
* backup requirements
* validation rules
* test-first implementation tasks
* security boundaries
* local dev CLI requirements
* Hermes skill requirements
* acceptance criteria

The only dependency on MVP 1 is that the plugin API, state schema, shared tool result format, config loader pattern, and `dev_cli.py` pattern have already been implemented and tested.

If MVP 1 has not been completed, stop and complete MVP 1 first.

---

# Required Server-Side Config Schema

MVP 2 reads and writes:

```txt
$HOME/.agent-system/config/projects.yaml
```

Canonical config shape:

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
      base_path: ~/.agent-system/worktrees/comapeo-cloud-app
      issue_worktree_pattern: ~/.agent-system/worktrees/comapeo-cloud-app-issue-{issue_number}
    auto_merge:
      enabled: false
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
```

Required project fields:

```txt
id
name
repo
github.owner
github.repo
priority
status
```

Optional project fields:

```txt
default_branch
local.base_path
local.issue_worktree_pattern
auto_merge.enabled
auto_merge.max_risk
protected_paths
labels
notes
created_by
created_at
updated_at
```

Allowed priorities:

```txt
critical
high
medium
low
paused
```

Allowed statuses:

```txt
active
paused
archived
blocked
missing
```

Allowed auto-merge max risk values:

```txt
low
medium
```

MVP 2 must never default to auto-merge enabled.

---

# Project ID Rules

Project IDs must match:

```regex
^[a-z0-9][a-z0-9-]*[a-z0-9]$
```

Generate default ID from repo name:

```txt
awana-digital/comapeo-cloud-app -> comapeo-cloud-app
```

If duplicate ID already exists, block and ask for explicit ID.

Do not silently create:

```txt
comapeo-cloud-app-2
```

---

# GitHub Repo Parsing Rules

`portfolio_project_add` must accept these forms:

```txt
awana-digital/edt-next
https://github.com/awana-digital/edt-next
git@github.com:awana-digital/edt-next.git
```

Normalize to:

```python
{
  "owner": "awana-digital",
  "repo": "edt-next",
  "repo_url": "git@github.com:awana-digital/edt-next.git"
}
```

For MVP 2, assume GitHub only.

If input is not a recognizable GitHub repo, return blocked:

```txt
reason: invalid_github_repo
```

---

# File Write Safety

All writes to `projects.yaml` must be atomic.

Implement helper:

```python
write_projects_config_atomic(root: Path, config: PortfolioConfig) -> WriteResult
```

Required behavior:

1. Ensure `config/` exists.
2. Ensure `backups/` exists.
3. Read current `projects.yaml` if it exists.
4. Validate current config if it exists.
5. Write backup before mutation:

```txt
$HOME/.agent-system/backups/projects.yaml.2026-04-25T10-30-00Z.bak
```

6. Serialize new config to YAML.
7. Write to temp file:

```txt
projects.yaml.tmp.<uuid>
```

8. Atomically replace:

```python
os.replace(temp_path, projects_path)
```

9. Reload written file and validate it.
10. Return path to backup.

If validation after write fails, return failed and keep backup path in result.

Do not write partial YAML directly to `projects.yaml`.

---

# Config Locking

All config mutation tools must acquire lock:

```txt
config:projects
```

Default TTL:

```txt
60 seconds
```

If lock is held:

```json
{
  "status": "blocked",
  "reason": "config_lock_already_held"
}
```

Always release the lock in `finally` if acquired.

---

# Tool Result Format

Use the MVP 1 shared result format:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "portfolio_project_add",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None
}
```

---

# MVP 2 Tools

## Tool: `portfolio_project_add`

### Purpose

Add a new project to the server-side manifest.

### Input schema

```python
{
    "repo": {
        "type": "string",
        "description": "GitHub repo reference. Accepts owner/repo, https GitHub URL, or SSH GitHub URL."
    },
    "id": {
        "type": "string",
        "description": "Optional stable project ID. Defaults to repo name if not provided."
    },
    "name": {
        "type": "string",
        "description": "Optional human-readable project name. Defaults to title-cased repo name."
    },
    "priority": {
        "type": "string",
        "description": "critical, high, medium, low, or paused. Defaults to medium."
    },
    "status": {
        "type": "string",
        "description": "active or paused. Defaults to active."
    },
    "default_branch": {
        "type": "string",
        "description": "Branch name or auto. Defaults to auto."
    },
    "auto_merge_enabled": {
        "type": "boolean",
        "description": "Whether future auto-merge policy is enabled. Defaults to false."
    },
    "protected_paths": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional protected path globs."
    },
    "validate_github": {
        "type": "boolean",
        "description": "Whether to validate repo with gh repo view. Defaults to true."
    },
    "root": {
        "type": "string",
        "description": "Optional system root override."
    }
}
```

### Behavior

1. Resolve system root.
2. Parse repo reference.
3. Validate project ID or generate from repo name.
4. Load current config.
5. Block if project ID already exists.
6. Block if same GitHub owner/repo already exists under a different ID.
7. If `validate_github=true`, run read-only GitHub validation.
8. Build project config object.
9. Default `auto_merge.enabled=false`.
10. Acquire `config:projects` lock.
11. Write config atomically with backup.
12. Upsert project into SQLite.
13. Release lock.
14. Return summary.

### Success summary example

```txt
Project added: EDT Next.
ID: edt-next.
Priority: medium.
Auto-merge: disabled.
It will be included in the next portfolio heartbeat.
```

### Blocked cases

```txt
invalid_github_repo
duplicate_project_id
duplicate_github_repo
github_cli_missing
github_auth_missing
github_repo_inaccessible
config_lock_already_held
invalid_config
```

---

## Tool: `portfolio_project_update`

### Purpose

Update safe fields for an existing project.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "name": {"type": "string"},
    "priority": {"type": "string"},
    "status": {"type": "string"},
    "default_branch": {"type": "string"},
    "protected_paths": {
        "type": "array",
        "items": {"type": "string"}
    },
    "auto_merge_enabled": {"type": "boolean"},
    "auto_merge_max_risk": {"type": "string"},
    "root": {"type": "string"}
}
```

All fields except `project_id` and `root` are optional.

### Behavior

1. Load config.
2. Find project by ID.
3. Block if missing.
4. Validate provided fields.
5. Apply only provided fields.
6. Set `updated_at`.
7. Acquire config lock.
8. Write config atomically with backup.
9. Upsert project into SQLite.
10. Release lock.
11. Return summary of changed fields.

### Blocked cases

```txt
project_not_found
no_update_fields
invalid_priority
invalid_status
invalid_auto_merge_risk
config_lock_already_held
```

---

## Tool: `portfolio_project_pause`

### Purpose

Set a project status to `paused`.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "reason": {"type": "string"},
    "root": {"type": "string"}
}
```

### Behavior

Equivalent to:

```txt
portfolio_project_update(project_id, status="paused")
```

Add note if reason is provided:

```yaml
notes:
  pause_reason: "..."
```

### Success summary example

```txt
Paused project: EDT Website Migration.
It will be skipped by future portfolio heartbeats unless include_paused is enabled.
```

---

## Tool: `portfolio_project_resume`

### Purpose

Set a paused project back to `active`.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "root": {"type": "string"}
}
```

### Behavior

Equivalent to:

```txt
portfolio_project_update(project_id, status="active")
```

### Success summary example

```txt
Resumed project: EDT Website Migration.
It will be included in future portfolio heartbeats.
```

---

## Tool: `portfolio_project_archive`

### Purpose

Archive a project without deleting its config history from backups or SQLite history.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "reason": {"type": "string"},
    "root": {"type": "string"}
}
```

### Behavior

Set project status to:

```txt
archived
```

Archived projects are excluded by default from project lists and heartbeats.

### Success summary example

```txt
Archived project: Old Archived Project.
It will no longer appear in normal portfolio status or heartbeat runs.
```

---

## Tool: `portfolio_project_set_priority`

### Purpose

Change a project priority.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "priority": {"type": "string"},
    "root": {"type": "string"}
}
```

Allowed priorities:

```txt
critical
high
medium
low
paused
```

### Behavior

Equivalent to:

```txt
portfolio_project_update(project_id, priority=priority)
```

If priority is `paused`, also set status to `paused`.

### Success summary example

```txt
Updated priority for CoMapeo Cloud App: high.
```

---

## Tool: `portfolio_project_set_auto_merge`

### Purpose

Store future auto-merge policy for a project.

This tool only changes config. It must not merge anything.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "enabled": {"type": "boolean"},
    "max_risk": {
        "type": "string",
        "description": "low or medium. Defaults to low when enabled."
    },
    "root": {"type": "string"}
}
```

### Behavior

If `enabled=false`:

```yaml
auto_merge:
  enabled: false
```

If `enabled=true`:

```yaml
auto_merge:
  enabled: true
  max_risk: low
```

Allowed `max_risk`:

```txt
low
medium
```

Do not allow `high` or `critical`.

### Success summary example

```txt
Auto-merge policy updated for Docs Support Bot.
Enabled: true.
Maximum risk: low.
Note: MVP 2 only stores this policy. It does not perform auto-merges.
```

---

## Tool: `portfolio_project_remove`

### Purpose

Remove a project from `projects.yaml` only after explicit confirmation.

Default recommendation should be archive instead of remove.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "confirm": {"type": "boolean"},
    "root": {"type": "string"}
}
```

### Behavior

1. If `confirm` is not true, return blocked with recommendation to archive.
2. If confirmed:

   * remove project from config
   * write backup
   * do not delete worktrees
   * do not delete SQLite rows
   * do not delete logs or artifacts
3. Return summary.

### Blocked summary example

```txt
I did not remove the project because removal requires confirm=true. Safer option: archive it instead.
```

### Success summary example

```txt
Removed project from active config: Old Project.
I did not delete worktrees, logs, artifacts, or SQLite history.
```

---

## Tool: `portfolio_project_explain`

### Purpose

Explain one project’s current configuration in human-readable form.

### Input schema

```python
{
    "project_id": {"type": "string"},
    "root": {"type": "string"}
}
```

### Behavior

1. Load config.
2. Find project.
3. Return details:

   * ID
   * name
   * GitHub repo
   * priority
   * status
   * default branch
   * auto-merge setting
   * protected paths
   * local paths

### Summary example

```txt
CoMapeo Cloud App
ID: comapeo-cloud-app
Repo: awana-digital/comapeo-cloud-app
Priority: high
Status: active
Auto-merge: disabled
Protected paths: .github/workflows/**, infra/**, auth/**, migrations/**
```

---

## Tool: `portfolio_project_config_backup`

### Purpose

Create a manual backup of `projects.yaml`.

### Input schema

```python
{
    "root": {"type": "string"}
}
```

### Behavior

1. Load and validate current config.
2. Create timestamped backup.
3. Return backup path.

### Summary example

```txt
Created project config backup:
~/.agent-system/backups/projects.yaml.2026-04-25T10-30-00Z.bak
```

---

# GitHub Validation

Use `gh` for read-only repo validation.

Allowed command:

```bash
gh repo view OWNER/REPO --json name,owner,defaultBranchRef,url,isPrivate
```

Expected normalized output:

```python
{
  "owner": "awana-digital",
  "repo": "edt-next",
  "default_branch": "main",
  "url": "https://github.com/awana-digital/edt-next",
  "is_private": true
}
```

If `gh` is not installed or authenticated, return blocked unless `validate_github=false`.

If `validate_github=false`, still parse and add the project, but include warning:

```txt
GitHub validation skipped. The repo will be checked during the next heartbeat.
```

---

# Local Path Expansion

YAML may contain:

```txt
~/.agent-system/worktrees/project-id
```

When reading config, expand `~` for runtime use.

When writing config, prefer storing paths using:

```txt
~/.agent-system/...
```

rather than absolute `/home/user/...` paths, when the path is under the current user home.

---

# Hermes Skill: `project-admin`

Create:

```txt
skills/project-admin/SKILL.md
```

Content requirements:

```md
---
name: project-admin
description: Manage projects in the Hermes Portfolio Manager server-side manifest.
---

Use this skill when the user asks to:

- add a project
- pause a project
- resume a project
- archive a project
- remove a project
- change project priority
- explain project configuration
- change auto-merge policy
- back up project configuration

Use the Portfolio Manager plugin tools.

Important rules:

1. For permanent changes, summarize the change clearly.
2. If the user request is ambiguous, ask a follow-up question before mutating config.
3. Prefer archive over remove.
4. Never enable auto-merge unless the user explicitly asks.
5. Remind the user that MVP 2 stores auto-merge policy but does not merge PRs.
6. Do not create GitHub issues in this skill.
7. Do not create branches or worktrees in this skill.
8. Do not modify repository files.
```

---

# Required Tests

MVP 2 must include meaningful tests before implementation.

## Config mutation tests

Create:

```txt
tests/test_project_admin_config.py
```

Required tests:

* add project to empty config
* add project to existing config
* reject duplicate project ID
* reject duplicate GitHub owner/repo
* update project priority
* pause project
* resume project
* archive project
* remove project requires `confirm=True`
* remove project does not delete SQLite history
* auto-merge defaults to disabled
* enabling auto-merge with `max_risk=high` is rejected
* invalid project ID is rejected
* invalid GitHub repo input is rejected

## Atomic write tests

Create:

```txt
tests/test_project_admin_writes.py
```

Required tests:

* backup is created before mutation
* write uses temp file and atomic replace
* invalid new config is not written
* written config can be reloaded and validated
* backup path is returned
* config directory is created if missing
* backups directory is created if missing

## Lock tests

Create:

```txt
tests/test_project_admin_locks.py
```

Required tests:

* mutation acquires `config:projects` lock
* mutation returns blocked if lock is already held
* lock is released after success
* lock is released after handled failure

## GitHub repo parsing tests

Create:

```txt
tests/test_project_admin_repo_parse.py
```

Required tests for input forms:

```txt
owner/repo
https://github.com/owner/repo
git@github.com:owner/repo.git
```

Expected normalized fields:

```txt
owner
repo
repo_url
project_id
```

Invalid inputs should return blocked or validation errors.

## GitHub validation tests

Create:

```txt
tests/test_project_admin_github_validation.py
```

Mock `gh repo view`.

Required tests:

* validation succeeds for accessible repo
* missing `gh` blocks when validation enabled
* unauthenticated `gh` blocks when validation enabled
* inaccessible repo blocks when validation enabled
* validation skipped when `validate_github=false`

## Tool handler tests

Create:

```txt
tests/test_project_admin_tools.py
```

Required tests for each tool:

```txt
portfolio_project_add
portfolio_project_update
portfolio_project_pause
portfolio_project_resume
portfolio_project_archive
portfolio_project_set_priority
portfolio_project_set_auto_merge
portfolio_project_remove
portfolio_project_explain
portfolio_project_config_backup
```

Each tool test must verify:

* shared tool result shape
* state/config mutation when expected
* concise Telegram-friendly summary
* blocked behavior for invalid input

## Skill tests

Create:

```txt
tests/test_project_admin_skill.py
```

Required tests:

* `skills/project-admin/SKILL.md` exists
* frontmatter name is `project-admin`
* skill mentions the correct plugin tools
* skill explicitly says not to create issues, branches, worktrees, or repo file modifications
* skill says archive is preferred over remove

## Security tests

Create or extend:

```txt
tests/test_security.py
```

Required MVP 2 security tests:

* no GitHub mutation commands are used
* no unsafe Git commands are used
* no repository files are modified
* no shell-string subprocess calls
* secrets are redacted
* config writes are restricted to `$HOME/.agent-system/config/projects.yaml` or explicit test root
* path traversal in project ID is rejected

---

# Implementation Plan for Coding Agent

Follow these steps exactly.

## Step 1: Update root path behavior

Update MVP 1 root resolution from `/srv/agent-system` to:

```python
Path.home() / ".agent-system"
```

Keep `AGENT_SYSTEM_ROOT` override.

Update tests and fixtures accordingly.

## Step 2: Add project admin models

Add or extend config models for:

```txt
auto_merge
notes
created_at
updated_at
```

Ensure unknown fields are preserved when possible.

## Step 3: Implement repo parser

Implement:

```python
parse_github_repo_ref(value: str) -> ParsedRepo
```

Support:

```txt
owner/repo
https://github.com/owner/repo
git@github.com:owner/repo.git
```

## Step 4: Implement GitHub repo validation

Implement read-only validation using:

```bash
gh repo view OWNER/REPO --json name,owner,defaultBranchRef,url,isPrivate
```

Mock this in tests.

## Step 5: Implement atomic config writer

Implement:

```python
write_projects_config_atomic(root, config) -> WriteResult
```

Include backup and reload validation.

## Step 6: Implement config write lock usage

All mutating tools must acquire:

```txt
config:projects
```

Use state lock helpers from MVP 1.

## Step 7: Implement project mutation functions

Implement pure functions first:

```python
add_project(config, input) -> PortfolioConfig
update_project(config, input) -> PortfolioConfig
pause_project(config, project_id, reason=None) -> PortfolioConfig
resume_project(config, project_id) -> PortfolioConfig
archive_project(config, project_id, reason=None) -> PortfolioConfig
remove_project(config, project_id, confirm=False) -> PortfolioConfig
```

These should not write files directly.

## Step 8: Implement tool handlers

Wire functions into Hermes tools:

```txt
portfolio_project_add
portfolio_project_update
portfolio_project_pause
portfolio_project_resume
portfolio_project_archive
portfolio_project_set_priority
portfolio_project_set_auto_merge
portfolio_project_remove
portfolio_project_explain
portfolio_project_config_backup
```

## Step 9: Add schemas

Add tool schemas in `schemas.py` using the verified Hermes schema format from MVP 1.

## Step 10: Add dev CLI commands

Update `dev_cli.py` to support MVP 2 tools, for example:

```bash
python dev_cli.py portfolio_project_add --repo awana-digital/edt-next --priority medium --json
python dev_cli.py portfolio_project_pause --project-id edt-next --json
python dev_cli.py portfolio_project_explain --project-id edt-next --json
```

## Step 11: Add `project-admin` skill

Create:

```txt
skills/project-admin/SKILL.md
```

Follow the skill requirements above.

## Step 12: Run all tests

Run:

```bash
pytest
```

Do not proceed to manual Hermes smoke tests until all automated tests pass.

---

# Manual Hermes Smoke Tests

Only run after automated tests pass.

## Smoke 1: Explain existing project

Ask Hermes:

```txt
Explain the CoMapeo Cloud App project configuration.
```

Expected tool:

```txt
portfolio_project_explain
```

Expected result:

* project config summary
* no mutation

## Smoke 2: Add a project with validation disabled

Use a test root, not production root.

Ask Hermes:

```txt
Add awana-digital/test-project as a low-priority project. Skip GitHub validation.
```

Expected tool:

```txt
portfolio_project_add
```

Expected result:

* project added to test root config
* auto-merge disabled
* backup created

## Smoke 3: Pause and resume project

Ask Hermes:

```txt
Pause the test project.
```

Then:

```txt
Resume the test project.
```

Expected tools:

```txt
portfolio_project_pause
portfolio_project_resume
```

Expected result:

* status changes correctly
* backups created

## Smoke 4: Try to remove without confirmation

Ask Hermes:

```txt
Remove the test project.
```

Expected:

* blocked
* recommendation to archive instead

## Smoke 5: Remove with confirmation in test root

Ask Hermes:

```txt
Remove the test project with confirmation.
```

Expected:

* project removed from config
* backup created
* SQLite history not deleted

---

# Acceptance Criteria

MVP 2 is complete when:

1. Default root is `$HOME/.agent-system`, with env and explicit overrides.
2. Existing MVP 1 tests still pass after root path change.
3. Project config can be mutated safely through pure functions and tool handlers.
4. All config mutations use `config:projects` lock.
5. All config writes are atomic.
6. Every config mutation creates a timestamped backup.
7. Written config is reloaded and validated after write.
8. Duplicate project IDs are blocked.
9. Duplicate GitHub owner/repo entries are blocked.
10. GitHub repo references are parsed from owner/repo, HTTPS URL, and SSH URL forms.
11. GitHub repo validation uses read-only `gh repo view` only.
12. Auto-merge defaults to disabled.
13. Enabling auto-merge with high/critical risk is impossible.
14. Remove requires explicit confirmation.
15. Remove does not delete worktrees, logs, artifacts, or SQLite history.
16. Project archive is supported and preferred over remove.
17. `project-admin` Hermes skill exists and is safe.
18. `dev_cli.py` can run MVP 2 tools outside Hermes.
19. Security tests prove no GitHub mutation commands are used.
20. Security tests prove no unsafe Git commands are used.
21. Security tests prove no shell-string subprocess execution is used.
22. Security tests prove config writes cannot escape the configured system root.
23. All automated tests pass with `pytest`.
24. Manual Hermes smoke tests pass on a test root.

---

# Definition of Done

MVP 2 is done only when the user can manage projects through Hermes/Telegram after initial setup, without SSHing into the server for normal project administration.

The user should be able to do these safely:

```txt
Add a project.
Pause a project.
Resume a project.
Archive a project.
Change project priority.
Explain project configuration.
Create a project config backup.
Set future auto-merge policy.
Remove a project only with confirmation.
```

MVP 2 must remain safe. It manages configuration only. It does not start development work.
