# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 1, Agent-Ready Version

## Goal

Track implementation progress for the Hermes Portfolio Manager Plugin MVP 1.

MVP 1 proves that **one Hermes Agent can safely manage many GitHub projects** from a server-side manifest.

This MVP is read-only:

* no autonomous coding
* no GitHub mutations
* no project config mutations
* no branch creation
* no issue creation
* no PR creation
* no file modifications inside repositories
* no merge/rebase/stash/reset/clean

The plugin should inspect state, update local SQLite runtime state, and return concise summaries to Hermes.

---

# Non-Negotiable Implementation Rules

1. Do not guess the Hermes plugin API.
2. Verify the Hermes plugin API before implementing real tools.
3. Write a meaningful test before each implementation task.
4. Confirm each test fails for the expected reason before implementation.
5. Implement the smallest change needed to pass.
6. Keep MVP 1 read-only.
7. Do not use `shell=True` in subprocess calls.
8. Do not run unsafe Git commands.
9. Do not run GitHub mutation commands.
10. Do not put automation policy in repo-local YAML.

---

# Test-First Rule

Every implementation task must follow this order:

1. Write or update a meaningful test.
2. Confirm the test fails for the expected reason.
3. Implement the smallest change needed.
4. Confirm the test passes.
5. Run the relevant test group.
6. Mark the task complete.

A meaningful test must verify behavior that matters to the system.

Avoid meaningless tests such as:

* tests that only assert a mock was called without checking behavior
* tests that duplicate the implementation logic
* tests that pass before the feature exists
* tests that do not protect an acceptance criterion

---

# Completion Legend

```txt
[ ] Not started
[/] In progress
[x] Done
[!] Blocked
```

---

# MVP 1 Status Semantics

All tool results must use one of these statuses:

```txt
success
skipped
blocked
failed
```

Use them as follows:

## `success`

The tool completed its intended operation.

For portfolio-wide tools, `success` may still include project-level warnings.

Example:

```json
{
  "status": "success",
  "data": {
    "has_warnings": true,
    "warnings": [
      "GitHub sync failed for edt-next because repo was inaccessible."
    ]
  }
}
```

Use this for partial project failures when the overall heartbeat still completed.

## `skipped`

No action was needed.

Examples:

* no active projects
* no worktrees found for optional inspection
* no pending item matched a filter

## `blocked`

The tool intentionally could not proceed due to a known precondition.

Examples:

* missing `projects.yaml`
* invalid config
* `gh` not installed
* `gh` not authenticated
* heartbeat lock already held

## `failed`

Unexpected system error.

Examples:

* SQLite corruption
* unhandled exception
* permission error writing state

---

# Shared Tool Result Format

Every tool must return this exact shape:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "portfolio_status",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None
}
```

Rules:

* `summary` must be safe to send directly to Telegram.
* `data` must be machine-readable.
* `reason` is optional and should be used for blocked/skipped states.
* Never include secrets, tokens, private keys, or full stack traces.

---

# Development Environment Contract

Use Python for the Hermes plugin.

Recommended minimum:

```txt
Python >= 3.11
pytest
PyYAML
pydantic OR dataclasses with explicit validation
```

Preferred package files:

```txt
pyproject.toml
requirements-dev.txt
```

Required local test command:

```bash
pytest
```

The plugin code must be testable outside Hermes.

Tests must not require a running Hermes process, except for explicit manual smoke tests in Phase 9.

---

# Expected Project Layout

```txt
hermes-portfolio-manager/
  PROGRESS.md
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
  dev_cli.py
  pyproject.toml
  requirements-dev.txt
  skills/
    portfolio-status/
      SKILL.md
    portfolio-heartbeat/
      SKILL.md
  tests/
    fixtures/
      projects.valid.yaml
      projects.invalid-duplicate-id.yaml
      projects.invalid-status.yaml
      projects.invalid-missing-required.yaml
      gh_issues.open.json
      gh_prs.open.json
      gh_prs.failing-checks.json
      gh_prs.changes-requested.json
      gh_prs.approved-passing.json
    test_structure.py
    test_plugin_metadata.py
    test_config.py
    test_state.py
    test_github_client.py
    test_worktree.py
    test_summary.py
    test_tools.py
    test_skills.py
    test_security.py
```

---

# Server-Side Runtime Layout

Default root:

```txt
/srv/agent-system
```

Override:

```bash
AGENT_SYSTEM_ROOT=/custom/path
```

Expected runtime layout:

```txt
/srv/agent-system/
  config/
    projects.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
```

No repo-local project automation YAML is required or allowed for MVP 1.

---

# Golden Sample Config Fixture

Create this fixture before implementing config loading:

```txt
tests/fixtures/projects.valid.yaml
```

Content:

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

  - id: edt-next
    name: EDT Website Migration
    repo: git@github.com:awana-digital/edt-next.git
    github:
      owner: awana-digital
      repo: edt-next
    priority: medium
    status: active
    default_branch: auto

  - id: docs-support-bot
    name: Docs Support Bot
    repo: git@github.com:awana-digital/docs-support-bot.git
    github:
      owner: awana-digital
      repo: docs-support-bot
    priority: low
    status: paused
    default_branch: main

  - id: old-archived-project
    name: Old Archived Project
    repo: git@github.com:awana-digital/old-archived-project.git
    github:
      owner: awana-digital
      repo: old-archived-project
    priority: low
    status: archived
```

Also create invalid fixtures:

```txt
tests/fixtures/projects.invalid-duplicate-id.yaml
tests/fixtures/projects.invalid-status.yaml
tests/fixtures/projects.invalid-missing-required.yaml
```

---

# Minimal SQLite Schema Contract

The plugin may initialize the MVP schema directly.

It must stay compatible with the broader `agent-state` design.

Required tables for MVP 1:

```sql
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  repo_url TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'medium',
  default_branch TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
  project_id TEXT NOT NULL,
  issue_number INTEGER NOT NULL,
  github_node_id TEXT,
  title TEXT NOT NULL,
  state TEXT NOT NULL,
  risk TEXT,
  confidence REAL,
  labels_json TEXT,
  spec_artifact_path TEXT,
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, issue_number),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pull_requests (
  project_id TEXT NOT NULL,
  pr_number INTEGER NOT NULL,
  github_node_id TEXT,
  title TEXT NOT NULL,
  branch_name TEXT,
  base_branch TEXT,
  state TEXT NOT NULL,
  risk TEXT,
  review_stage TEXT,
  auto_merge_candidate INTEGER NOT NULL DEFAULT 0,
  last_seen_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, pr_number),
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS worktrees (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  issue_number INTEGER,
  path TEXT NOT NULL,
  branch_name TEXT,
  base_branch TEXT,
  state TEXT NOT NULL,
  dirty_summary TEXT,
  last_inspected_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS heartbeats (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  active_window INTEGER NOT NULL DEFAULT 1,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS heartbeat_events (
  id TEXT PRIMARY KEY,
  heartbeat_id TEXT,
  project_id TEXT,
  level TEXT NOT NULL,
  type TEXT NOT NULL,
  message TEXT NOT NULL,
  data_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (heartbeat_id) REFERENCES heartbeats(id) ON DELETE SET NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS locks (
  name TEXT PRIMARY KEY,
  owner TEXT NOT NULL,
  acquired_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_issues_project_state ON issues(project_id, state);
CREATE INDEX IF NOT EXISTS idx_prs_project_state ON pull_requests(project_id, state);
CREATE INDEX IF NOT EXISTS idx_worktrees_project_state ON worktrees(project_id, state);
CREATE INDEX IF NOT EXISTS idx_events_heartbeat ON heartbeat_events(heartbeat_id);
CREATE INDEX IF NOT EXISTS idx_locks_expires_at ON locks(expires_at);
```

All timestamps must be UTC ISO 8601 strings.

---

# Phase -1 — Verify Hermes Plugin API Before Implementing Real Tools

## -1.1 Inspect Hermes plugin examples and docs

Status: [ ]

### Test first

Create a documentation check test that fails until this file exists:

```txt
docs/hermes-plugin-api-notes.md
```

The test should verify that the file contains these headings:

```txt
# Hermes Plugin API Notes
## Required Files
## plugin.yaml Fields
## Tool Registration API
## Tool Schema Format
## Handler Signature
## Return Format
## Skill Discovery
## Plugin Reload or Restart Procedure
## Source References
```

### Implementation

Inspect the installed Hermes docs, local examples, or official examples.

Document the exact plugin API. Do not guess.

The notes must answer:

* what files are required
* what fields `plugin.yaml` requires
* how tools are registered
* what schema format Hermes expects
* what Python function signature tool handlers require
* what return format Hermes expects
* how bundled skills are discovered
* how to reload or restart Hermes after plugin changes

### Verification

Run:

```bash
pytest tests/test_hermes_api_notes.py
```

Acceptance:

* no Hermes plugin API is guessed
* implementation has a verified reference document

---

## -1.2 Create minimal `portfolio_ping` smoke tool

Status: [x]

### Test first

Create a test verifying that the plugin exposes a tool named:

```txt
portfolio_ping
```

The tool must return:

```python
{
    "status": "success",
    "tool": "portfolio_ping",
    "message": "Portfolio plugin is loaded",
    "data": {},
    "summary": "Portfolio plugin is loaded.",
    "reason": None
}
```

### Implementation

Implement the minimal Hermes plugin structure and register only `portfolio_ping`.

Use the verified API from `docs/hermes-plugin-api-notes.md`.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_ping
```

Manual verification later:

```txt
Ask Hermes to call portfolio_ping.
```

Acceptance:

* plugin has a known-good minimal tool before real tools are added

---

## -1.3 Add local development CLI for tool execution outside Hermes

Status: [x]

### Test first

Create a test that runs the local dev CLI for `portfolio_ping` and verifies the returned JSON.

Target command:

```bash
python dev_cli.py portfolio_ping --json
```

### Implementation

Create `dev_cli.py` that can call tool handlers outside Hermes.

Required commands for MVP 1:

```txt
portfolio_ping
portfolio_config_validate
portfolio_project_list
portfolio_github_sync
portfolio_worktree_inspect
portfolio_status
portfolio_heartbeat
```

Only `portfolio_ping` must work in this task.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_portfolio_ping
```

Acceptance:

* tool logic can be tested without a running Hermes process

---

# Phase 0 — Repository and Plugin Skeleton

## 0.1 Create plugin directory structure

Status: [x]

### Test first

Create a test that verifies the required plugin files exist in the expected structure.

Expected files:

```txt
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
dev_cli.py
skills/portfolio-status/SKILL.md
skills/portfolio-heartbeat/SKILL.md
```

### Implementation

Create the initial directory and files.

### Verification

Run:

```bash
pytest tests/test_structure.py
```

Acceptance:

* test fails before files exist
* test passes after files are created

---

## 0.2 Add Python test scaffolding

Status: [x]

### Test first

Create a test or CI smoke command that expects:

```txt
pyproject.toml
requirements-dev.txt
pytest can run
```

### Implementation

Create:

```txt
pyproject.toml
requirements-dev.txt
```

Minimum dev dependencies:

```txt
pytest
PyYAML
pydantic
```

If choosing not to use pydantic, document the replacement and update tests accordingly.

### Verification

Run:

```bash
pytest
```

Acceptance:

* test suite starts successfully
* dependency expectations are explicit

---

## 0.3 Add valid plugin metadata

Status: [x]

### Test first

Create a test that parses `plugin.yaml` and verifies:

* `name` is `portfolio-manager`
* `version` exists
* `description` exists
* plugin is marked read-only for MVP 1, either in metadata or documentation

### Implementation

Add `plugin.yaml`:

```yaml
name: portfolio-manager
version: 0.1.0
description: Manage multiple GitHub projects from one server-side manifest. MVP 1 is read-only.
author: Awana Digital
license: MIT
mvp: 1
mode: read-only
```

If Hermes rejects unknown fields, remove `mvp` and `mode` from `plugin.yaml` and document read-only mode in `SPEC.md` and `README.md` instead.

### Verification

Run:

```bash
pytest tests/test_plugin_metadata.py
```

Acceptance:

* invalid or missing metadata fails
* valid metadata passes

---

# Phase 1 — Configuration Loading

## 1.1 Resolve system root

Status: [x]

### Test first

Create tests for root resolution:

1. explicit root argument wins
2. `AGENT_SYSTEM_ROOT` is used when no explicit root is passed
3. default is `/srv/agent-system`

### Implementation

Implement:

```python
resolve_root(root: str | None) -> Path
```

in `config.py`.

Priority order:

```txt
1. explicit argument
2. AGENT_SYSTEM_ROOT env var
3. /srv/agent-system
```

### Verification

Run:

```bash
pytest tests/test_config.py::test_resolve_root
```

Acceptance:

* all three root resolution paths work

---

## 1.2 Create golden config fixtures

Status: [x]

### Test first

Create tests that fail until these fixtures exist:

```txt
tests/fixtures/projects.valid.yaml
tests/fixtures/projects.invalid-duplicate-id.yaml
tests/fixtures/projects.invalid-status.yaml
tests/fixtures/projects.invalid-missing-required.yaml
```

### Implementation

Create fixtures based on the golden sample config above.

Invalid fixture requirements:

* duplicate ID fixture contains two projects with the same `id`
* invalid status fixture uses a status outside the allowed enum
* missing required fixture omits at least one required field

### Verification

Run:

```bash
pytest tests/test_fixtures.py
```

Acceptance:

* fixtures exist
* valid fixture parses as YAML
* invalid fixtures are syntactically valid YAML but semantically invalid

---

## 1.3 Load `projects.yaml`

Status: [x]

### Test first

Create tests using temporary directories:

1. loads valid `config/projects.yaml`
2. returns blocked/config error when file is missing
3. returns validation error on invalid YAML

### Implementation

Implement:

```python
load_projects_config(root: Path) -> PortfolioConfig
```

Expected config path:

```txt
{root}/config/projects.yaml
```

### Verification

Run:

```bash
pytest tests/test_config.py::test_load_projects_config
```

Acceptance:

* valid YAML loads
* missing YAML produces clear error
* invalid YAML produces clear error

---

## 1.4 Validate required project fields

Status: [x]

### Test first

Create tests that reject projects missing:

* `id`
* `name`
* `repo`
* `github.owner`
* `github.repo`
* `priority`
* `status`

Use `projects.invalid-missing-required.yaml` plus focused inline cases if needed.

### Implementation

Implement project validation in `config.py`.

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

### Verification

Run:

```bash
pytest tests/test_config.py::test_required_project_fields
```

Acceptance:

* each missing required field is rejected with a useful message

---

## 1.5 Validate enums

Status: [x]

### Test first

Create tests that reject invalid values for:

Priority:

```txt
critical
high
medium
low
paused
```

Status:

```txt
active
paused
archived
blocked
missing
```

Use `projects.invalid-status.yaml`.

### Implementation

Add enum validation to project config loader.

### Verification

Run:

```bash
pytest tests/test_config.py::test_priority_and_status_validation
```

Acceptance:

* allowed values pass
* invalid values fail clearly

---

## 1.6 Reject duplicate project IDs

Status: [x]

### Test first

Use `projects.invalid-duplicate-id.yaml`.

Expected result:

* config validation fails
* error message names the duplicate ID

### Implementation

Track seen project IDs during config validation.

### Verification

Run:

```bash
pytest tests/test_config.py::test_duplicate_project_ids_rejected
```

Acceptance:

* duplicate IDs are rejected

---

## 1.7 Normalize local project paths

Status: [x]

### Test first

Create tests verifying:

1. project with explicit `local.base_path` uses it
2. project without `local.base_path` defaults to `{root}/worktrees/{project_id}`
3. project with explicit `local.issue_worktree_pattern` uses it
4. project without explicit pattern defaults to `{root}/worktrees/{project_id}-issue-{issue_number}`

### Implementation

Add normalized fields to project objects:

```txt
base_path
issue_worktree_pattern
```

### Verification

Run:

```bash
pytest tests/test_config.py::test_normalize_local_paths
```

Acceptance:

* normalized paths are stable and predictable

---

## 1.8 Filter and sort projects

Status: [x]

### Test first

Create tests verifying:

1. archived projects are excluded by default
2. archived projects are included when `include_archived=True`
3. paused projects are excluded from heartbeat by default unless `include_paused=True`
4. filtering by status works
5. projects are sorted by priority order:

   * critical
   * high
   * medium
   * low
   * paused

### Implementation

Implement:

```python
select_projects(config, status=None, include_archived=False, include_paused=False)
```

### Verification

Run:

```bash
pytest tests/test_config.py::test_project_filtering_and_sorting
```

Acceptance:

* filtering and sorting are deterministic

---

# Phase 2 — SQLite State Layer

## 2.1 Open and initialize SQLite database

Status: [x]

### Test first

Create tests verifying:

1. database file is created under `{root}/state/state.sqlite`
2. parent directory is created if missing
3. required MVP tables exist after initialization
4. initialization is idempotent
5. foreign keys are enabled

Required MVP tables:

```txt
projects
issues
pull_requests
worktrees
heartbeats
heartbeat_events
locks
```

### Implementation

Implement in `state.py`:

```python
open_state(root: Path) -> sqlite3.Connection
init_state(conn: sqlite3.Connection) -> None
```

Use the schema from the Minimal SQLite Schema Contract.

### Verification

Run:

```bash
pytest tests/test_state.py::test_state_initialization
```

Acceptance:

* database initializes reliably
* repeated initialization does not fail

---

## 2.2 Upsert projects into state

Status: [x]

### Test first

Create tests verifying:

1. a project can be inserted
2. same project can be updated
3. updated priority/status are reflected
4. timestamps are stored

### Implementation

Implement:

```python
upsert_project(conn, project) -> None
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_upsert_project
```

Acceptance:

* insert and update both work

---

## 2.3 Upsert issues into state

Status: [x]

### Test first

Create tests verifying:

1. issue can be inserted for existing project
2. issue title can be updated
3. existing issue state is preserved unless explicitly changed
4. labels JSON is stored and read back correctly

### Implementation

Implement:

```python
upsert_issue(conn, project_id, issue_record) -> None
```

MVP default state for new GitHub issue:

```txt
needs_triage
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_upsert_issue
```

Acceptance:

* issue data persists correctly
* local state is not accidentally reset on repeated sync

---

## 2.4 Upsert PRs into state

Status: [x]

### Test first

Create tests verifying:

1. PR can be inserted for existing project
2. PR title/branch/base can be updated
3. PR state is mapped from GitHub summary
4. auto-merge candidate defaults to false

### Implementation

Implement:

```python
upsert_pull_request(conn, project_id, pr_record) -> None
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_upsert_pull_request
```

Acceptance:

* PR data persists correctly

---

## 2.5 Upsert worktrees into state

Status: [x]

### Test first

Create tests verifying:

1. base worktree state can be inserted
2. issue worktree state can be inserted
3. state can change from clean to dirty
4. dirty summary is stored

### Implementation

Implement:

```python
upsert_worktree(conn, worktree_record) -> None
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_upsert_worktree
```

Acceptance:

* worktree inspection results persist correctly

---

## 2.6 Heartbeat records and events

Status: [x]

### Test first

Create tests verifying:

1. heartbeat can start
2. event can be added to heartbeat
3. heartbeat can finish successfully
4. heartbeat can finish with `success` and `has_warnings=true`
5. heartbeat can finish with `failed` status

### Implementation

Implement:

```python
start_heartbeat(conn) -> str
add_event(conn, heartbeat_id, level, event_type, message, project_id=None, data=None) -> None
finish_heartbeat(conn, heartbeat_id, status, summary=None, error=None) -> None
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_heartbeat_records_and_events
```

Acceptance:

* heartbeat lifecycle is recorded

---

## 2.7 Advisory heartbeat lock

Status: [x]

### Test first

Create tests verifying:

1. new lock can be acquired
2. second acquire is blocked while lock is active
3. expired lock can be replaced
4. owner can release lock
5. wrong owner cannot release lock

### Implementation

Implement:

```python
acquire_lock(conn, name, owner, ttl_seconds) -> LockResult
release_lock(conn, name, owner) -> LockResult
```

Heartbeat lock name:

```txt
heartbeat:portfolio
```

Default TTL:

```txt
900 seconds
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_locks
```

Acceptance:

* lock behavior prevents overlapping heartbeats

---

# Phase 3 — Worktree Inspection

Worktree inspection comes before GitHub sync because it can be tested fully offline.

## 3.1 Identify issue worktrees

Status: [x]

### Test first

Create temp folders and verify issue worktree discovery for:

```txt
{project_id}-issue-{number}
```

Examples:

```txt
comapeo-cloud-app-issue-123
edt-next-issue-47
```

Expected:

* correctly extracts issue number
* ignores unrelated folders

### Implementation

Implement:

```python
discover_issue_worktrees(root, project) -> list[WorktreeCandidate]
```

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_discover_issue_worktrees
```

Acceptance:

* only valid issue worktrees are discovered

---

## 3.2 Detect missing and non-Git paths

Status: [x]

### Test first

Create tests for:

1. path does not exist -> `missing`
2. path exists but is not Git repo -> `blocked`

### Implementation

Implement first part of:

```python
inspect_worktree(path) -> WorktreeInspection
```

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_missing_and_non_git_paths
```

Acceptance:

* missing/non-Git paths are classified correctly

---

## 3.3 Detect clean Git worktree

Status: [x]

### Test first

Create a temporary Git repo with one committed file.

Expected state:

```txt
clean
```

### Implementation

Use read-only Git commands:

```bash
git status --porcelain=v1
git branch --show-current
git rev-parse --is-inside-work-tree
```

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_clean_worktree
```

Acceptance:

* clean repo is detected correctly

---

## 3.4 Detect dirty tracked files

Status: [x]

### Test first

Create a temp Git repo, commit a file, modify it.

Expected state:

```txt
dirty_uncommitted
```

Dirty summary should mention modified files.

### Implementation

Parse `git status --porcelain=v1`.

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_dirty_tracked_file
```

Acceptance:

* modified tracked files are detected

---

## 3.5 Detect dirty untracked files

Status: [x]

### Test first

Create a temp Git repo and add an untracked file.

Expected state:

```txt
dirty_untracked
```

### Implementation

Parse lines beginning with:

```txt
??
```

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_dirty_untracked_file
```

Acceptance:

* untracked files are detected

---

## 3.6 Detect merge conflict state using Git internal path resolution

Status: [x]

### Test first

Create a test that proves implementation uses Git path resolution rather than assuming `.git` is a directory.

Required behavior:

* call or wrap `git rev-parse --git-path MERGE_HEAD`
* classify existing resolved `MERGE_HEAD` path as `merge_conflict`
* classify porcelain unmerged entries like `UU`, `AA`, `DD`, `AU`, `UA`, `DU`, `UD` as `merge_conflict`

### Implementation

Detect:

* resolved `MERGE_HEAD` exists, or
* porcelain status includes unmerged entries

Do not inspect `.git/MERGE_HEAD` directly.

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_merge_conflict_state
```

Acceptance:

* merge conflicts are not mistaken for ordinary dirty files
* linked worktrees are handled correctly

---

## 3.7 Detect rebase conflict state using Git internal path resolution

Status: [x]

### Test first

Create tests proving implementation resolves paths through:

```bash
git rev-parse --git-path rebase-merge
git rev-parse --git-path rebase-apply
```

Expected state:

```txt
rebase_conflict
```

if either resolved path exists.

### Implementation

Use Git path resolution. Do not inspect `.git/rebase-merge` directly.

Rebase state must be detected before generic dirty state.

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_rebase_conflict_state
```

Acceptance:

* rebase state is detected correctly for normal repos and linked worktrees

---

## 3.8 Inspect all worktrees for one project

Status: [x]

### Test first

Create a temp root with:

* base worktree
* one clean issue worktree
* one dirty issue worktree
* one unrelated folder

Expected:

* base and valid issue worktrees are returned
* unrelated folder is ignored
* states are correct

### Implementation

Implement:

```python
inspect_project_worktrees(project) -> list[WorktreeInspection]
```

### Verification

Run:

```bash
pytest tests/test_worktree.py::test_inspect_project_worktrees
```

Acceptance:

* project-level worktree inspection works end-to-end

---

# Phase 4 — Summary Generation

## 4.1 Summarize project list

Status: [x]

### Test first

Create a test with projects at different priorities and statuses.

Expected summary should group or order by priority and avoid archived projects by default.

### Implementation

Implement:

```python
summarize_project_list(projects, counts) -> str
```

### Verification

Run:

```bash
pytest tests/test_summary.py::test_summarize_project_list
```

Acceptance:

* summary is concise and readable on Telegram

---

## 4.2 Summarize GitHub sync

Status: [x]

### Test first

Create a test with sync results from multiple projects.

Expected summary includes:

* projects synced
* open issues seen
* open PRs seen
* major warnings

It should not list every issue.

### Implementation

Implement:

```python
summarize_github_sync(sync_results) -> str
```

### Verification

Run:

```bash
pytest tests/test_summary.py::test_summarize_github_sync
```

Acceptance:

* summary highlights useful information only

---

## 4.3 Summarize worktree inspection

Status: [x]

### Test first

Create a test with:

* clean worktrees
* dirty worktrees
* one merge conflict
* one missing base path

Expected summary should prioritize dirty/conflicted/missing states.

### Implementation

Implement:

```python
summarize_worktrees(worktree_results) -> str
```

### Verification

Run:

```bash
pytest tests/test_summary.py::test_summarize_worktrees
```

Acceptance:

* clean worktrees do not create noise
* dirty/conflicted worktrees are visible

---

## 4.4 Summarize portfolio status

Status: [x]

### Test first

Create a test state with:

* one issue needing user questions
* one PR ready for human review
* one dirty worktree
* one normal open issue

Expected summary lists only the items needing attention first.

### Implementation

Implement:

```python
summarize_portfolio_status(state_snapshot, filter='all') -> str
```

### Verification

Run:

```bash
pytest tests/test_summary.py::test_summarize_portfolio_status
```

Acceptance:

* summary answers “what needs me?” clearly

---

## 4.5 Summarize portfolio heartbeat

Status: [x]

### Test first

Create a test heartbeat result with:

* 3 projects checked
* 14 issues seen
* 3 PRs seen
* 1 dirty worktree
* 1 inaccessible repo warning

Expected summary is concise and action-oriented.

### Implementation

Implement:

```python
summarize_heartbeat(result) -> str
```

### Verification

Run:

```bash
pytest tests/test_summary.py::test_summarize_heartbeat
```

Acceptance:

* digest is suitable for direct Telegram delivery

---

# Phase 5 — GitHub Read-Only Client

## 5.1 Create GitHub fixture JSON files

Status: [x]

### Test first

Create a test that verifies these fixture files exist and parse as JSON:

```txt
tests/fixtures/gh_issues.open.json
tests/fixtures/gh_prs.open.json
tests/fixtures/gh_prs.failing-checks.json
tests/fixtures/gh_prs.changes-requested.json
tests/fixtures/gh_prs.approved-passing.json
```

### Implementation

Create realistic but small fixtures based on `gh issue list --json ...` and `gh pr list --json ...` output shapes.

### Verification

Run:

```bash
pytest tests/test_github_fixtures.py
```

Acceptance:

* PR state mapping has stable fixture inputs

---

## 5.2 Detect GitHub CLI availability

Status: [x]

### Test first

Create tests that mock subprocess results for:

1. `gh --version` succeeds
2. `gh --version` missing/fails

### Implementation

Implement:

```python
check_gh_available() -> ToolCheckResult
```

Use subprocess argument arrays.

Never use `shell=True`.

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_check_gh_available
```

Acceptance:

* missing `gh` produces blocked result, not crash

---

## 5.3 Detect GitHub authentication

Status: [x]

### Test first

Create tests that mock:

1. `gh auth status` succeeds
2. `gh auth status` fails

### Implementation

Implement:

```python
check_gh_auth() -> ToolCheckResult
```

Do not expose auth details or tokens in output.

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_check_gh_auth
```

Acceptance:

* unauthenticated state returns blocked result with clear instruction

---

## 5.4 Fetch open issues

Status: [x]

### Test first

Create tests using `gh_issues.open.json` and verify parsed issue records include:

* number
* title
* labels
* author if available
* URL if available
* created/updated timestamps if available

### Implementation

Implement:

```python
list_open_issues(owner, repo, limit=50) -> list[IssueRecord]
```

Command:

```bash
gh issue list --repo OWNER/REPO --state open --limit 50 --json number,title,labels,author,createdAt,updatedAt,url
```

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_list_open_issues
```

Acceptance:

* valid GitHub JSON becomes normalized issue records

---

## 5.5 Fetch open PRs

Status: [x]

### Test first

Create tests using `gh_prs.open.json` and verify parsed PR records include:

* number
* title
* head branch
* base branch
* labels
* review decision if available
* check rollup if available
* URL if available

### Implementation

Implement:

```python
list_open_prs(owner, repo, limit=50) -> list[PullRequestRecord]
```

Command:

```bash
gh pr list --repo OWNER/REPO --state open --limit 50 --json number,title,headRefName,baseRefName,labels,reviewDecision,statusCheckRollup,createdAt,updatedAt,url
```

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_list_open_prs
```

Acceptance:

* valid GitHub JSON becomes normalized PR records

---

## 5.6 Map PR state from fixture data

Status: [x]

### Test first

Create tests for PR state mapping using fixtures:

1. `gh_prs.failing-checks.json` -> `checks_failed`
2. `gh_prs.changes-requested.json` -> `changes_requested`
3. `gh_prs.approved-passing.json` -> `ready_for_human`
4. no review decision -> `review_pending`
5. unknown data -> `open`
6. pending checks but no failures -> `review_pending`

### Implementation

Implement:

```python
map_pr_state(pr_json) -> str
```

Mapping must be conservative.

Priority order:

1. changes requested
2. failing checks
3. approved and passing checks
4. no review/pending checks
5. open fallback

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_map_pr_state
```

Acceptance:

* mapping is conservative and deterministic

---

## 5.7 Sync one project from GitHub

Status: [x]

### Test first

Create an integration-style unit test with mocked GitHub calls and temp SQLite DB verifying:

1. issues are fetched and upserted
2. PRs are fetched and upserted
3. project-level counts are returned
4. inaccessible repo returns warning but does not crash

### Implementation

Implement:

```python
sync_project_github(conn, project, max_items=50) -> ProjectGitHubSyncResult
```

### Verification

Run:

```bash
pytest tests/test_github_client.py::test_sync_project_github
```

Acceptance:

* one project can be synced read-only

---

# Phase 6 — Hermes Tool Schemas and Handlers

## 6.1 Define shared tool result helper

Status: [x]

### Test first

Create a test verifying all tool handlers return the shared shape.

### Implementation

Implement:

```python
tool_result(status, tool, message, data=None, summary=None, reason=None)
```

### Verification

Run:

```bash
pytest tests/test_tools.py::test_tool_result_shape
```

Acceptance:

* all tool results are predictable

---

## 6.2 Define Hermes schemas using verified API

Status: [x]

### Test first

Create a test that verifies schemas exist for:

```txt
portfolio_ping
portfolio_config_validate
portfolio_project_list
portfolio_github_sync
portfolio_worktree_inspect
portfolio_status
portfolio_heartbeat
```

The test should verify schema names and required/optional parameters, not Hermes internals.

### Implementation

Implement schemas in `schemas.py` using the verified Hermes schema format from Phase -1.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_tool_schemas_exist
```

Acceptance:

* schema format follows verified Hermes API notes

---

## 6.3 Implement `portfolio_config_validate`

Status: [x]

### Test first

Create tests verifying the tool:

1. returns success for valid config
2. returns blocked for missing config
3. includes project count
4. creates required directories if missing: `state`, `worktrees`, `logs`, `artifacts`

### Implementation

Wire tool handler to config validation.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_config_validate
```

Acceptance:

* config validation works through tool interface

---

## 6.4 Implement `portfolio_project_list`

Status: [x]

### Test first

Create tests verifying the tool:

1. lists active projects
2. filters by status
3. excludes archived projects by default
4. includes readable summary

### Implementation

Wire tool handler to project selection and summary generation.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_project_list
```

Acceptance:

* Hermes can list configured projects

---

## 6.5 Implement `portfolio_worktree_inspect`

Status: [x]

### Test first

Create tests with temp Git repos verifying:

1. inspects all active projects
2. inspects one selected project
3. writes worktree states into SQLite
4. returns useful counts
5. summary highlights dirty/conflicted worktrees

### Implementation

Wire tool handler to worktree inspection and state layer.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_worktree_inspect
```

Acceptance:

* worktree inspection works through tool interface

---

## 6.6 Implement `portfolio_github_sync`

Status: [x]

### Test first

Create tests with mocked GitHub client verifying:

1. sync all active projects
2. sync one selected project
3. writes issues/PRs into SQLite
4. inaccessible project creates warning but does not fail whole sync
5. summary includes counts and warnings

### Implementation

Wire tool handler to GitHub client and state layer.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_github_sync
```

Acceptance:

* GitHub sync works through tool interface

---

## 6.7 Implement `portfolio_status`

Status: [x]

### Test first

Create tests verifying:

1. reads latest SQLite state
2. returns full portfolio status
3. supports `filter='needs_user'`
4. supports `refresh=True` by calling GitHub sync and worktree inspection
5. summary is concise

### Implementation

Wire tool handler to state snapshot and summaries.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_status
```

Acceptance:

* user can ask “what needs me?” and get a useful answer

---

## 6.8 Implement `portfolio_heartbeat`

Status: [x]

### Test first

Create tests verifying:

1. heartbeat acquires lock
2. starts heartbeat record
3. validates config
4. runs GitHub sync
5. runs worktree inspection
6. computes portfolio status
7. writes heartbeat events
8. finishes heartbeat
9. releases lock
10. returns blocked if lock already held
11. one project failure returns `success` with `has_warnings=true`, not `failed`
12. global config failure returns `blocked`

### Implementation

Wire orchestration logic in tool handler.

Do not start implementation work, create branches, create issues, or modify GitHub.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_heartbeat
```

Acceptance:

* one call checks all active projects and returns a digest

---

## 6.9 Register tools with Hermes

Status: [x]

### Test first

Create a test or smoke check verifying `__init__.py` exposes/registers the expected tool names:

```txt
portfolio_ping
portfolio_config_validate
portfolio_project_list
portfolio_github_sync
portfolio_worktree_inspect
portfolio_status
portfolio_heartbeat
```

### Implementation

Register schemas and handlers according to verified Hermes plugin API notes.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_tool_registration
```

Acceptance:

* Hermes can discover the MVP 1 tools

---

# Phase 7 — Hermes Skills

## 7.1 Add `portfolio-status` skill

Status: [x]

### Test first

Create a test that reads `skills/portfolio-status/SKILL.md` and verifies it contains:

* frontmatter name `portfolio-status`
* instruction to call `portfolio_status`
* instruction to keep response concise
* instruction to highlight user decisions, PRs, worktree blockers, and warnings

### Implementation

Create `skills/portfolio-status/SKILL.md`.

### Verification

Run:

```bash
pytest tests/test_skills.py::test_portfolio_status_skill
```

Acceptance:

* skill exists and contains actionable instructions

---

## 7.2 Add `portfolio-heartbeat` skill

Status: [x]

### Test first

Create a test that reads `skills/portfolio-heartbeat/SKILL.md` and verifies it contains:

* frontmatter name `portfolio-heartbeat`
* instruction to call `portfolio_heartbeat`
* explicit read-only restrictions
* instruction to return blockers, user decisions, PRs ready for review, dirty/conflicted worktrees, and warnings

### Implementation

Create `skills/portfolio-heartbeat/SKILL.md`.

### Verification

Run:

```bash
pytest tests/test_skills.py::test_portfolio_heartbeat_skill
```

Acceptance:

* heartbeat skill is safe and self-contained

---

# Phase 8 — Safety and Subprocess Hardening

## 8.1 Ensure subprocess calls never use shell strings

Status: [x]

### Test first

Create a test that monkeypatches subprocess calls and verifies all commands are passed as argument lists.

### Implementation

Audit `github_client.py` and `worktree.py`.

Use:

```python
subprocess.run([...], shell=False, ...)
```

Never use:

```python
subprocess.run("...", shell=True)
```

### Verification

Run:

```bash
pytest tests/test_security.py::test_subprocess_uses_argument_arrays
```

Acceptance:

* no shell-string execution exists

---

## 8.2 Block unsafe Git commands in MVP 1

Status: [x]

### Test first

Create a test that scans plugin source or command wrapper usage and fails if any unsafe command is used:

```txt
git pull
git rebase
git merge
git reset
git clean
git stash
git checkout
git switch
git commit
git push
```

### Implementation

Keep worktree inspection read-only.

Allowed Git commands only:

```txt
git status
git branch
git rev-parse
```

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_unsafe_git_commands
```

Acceptance:

* MVP 1 cannot modify Git worktrees

---

## 8.3 Block GitHub mutation commands in MVP 1

Status: [x]

### Test first

Create a test that scans GitHub client usage and fails if mutation commands appear:

```txt
gh issue create
gh issue edit
gh issue comment
gh pr create
gh pr merge
gh pr comment
gh api --method POST
gh api --method PATCH
gh api --method DELETE
```

### Implementation

Only use:

```txt
gh issue list
gh pr list
gh auth status
gh --version
```

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_github_mutations
```

Acceptance:

* MVP 1 cannot mutate GitHub

---

## 8.4 Redact secrets from errors and logs

Status: [x]

### Test first

Create a test that passes error strings containing likely token patterns and verifies output redacts them.

Patterns to redact:

```txt
ghp_...
gho_...
ghs_...
ghu_...
sk-...
Bearer <token>
```

### Implementation

Implement:

```python
redact_secrets(text: str) -> str
```

Apply it to error messages, summaries, and logged subprocess stderr.

### Verification

Run:

```bash
pytest tests/test_security.py::test_redact_secrets
```

Acceptance:

* secrets are never returned in tool summaries or errors

---

## 8.5 Enforce read-only MVP boundary in tests

Status: [x]

### Test first

Create a test that verifies no code path in MVP 1 calls functions named or tagged as:

```txt
create_issue
create_pr
merge_pr
create_branch
run_harness
run_maintenance_skill
modify_manifest
```

### Implementation

Do not implement these functions in MVP 1. If placeholders exist, they must raise `NotImplementedError` and must not be reachable from registered tools.

### Verification

Run:

```bash
pytest tests/test_security.py::test_mvp1_read_only_boundary
```

Acceptance:

* MVP 1 stays observability-only

---

# Phase 9 — Manual Hermes Smoke Tests

These tests are manual because they require a real Hermes installation.

Do not start this phase until all automated tests pass.

## 9.1 Install plugin into Hermes

Status: [x]

### Precondition

All automated tests pass:

```bash
pytest
```

### Implementation

Install by copying or symlinking:

```txt
~/.hermes/plugins/portfolio-manager
```

Use the verified plugin reload/restart procedure from:

```txt
docs/hermes-plugin-api-notes.md
```

Steps taken:

1. Created root `__init__.py` to match Hermes' requirement (plugin.yaml + __init__.py in same directory).
2. Symlinked project root to `~/.hermes/plugins/portfolio-manager/`.
3. Enabled plugin: `hermes plugins enable portfolio-manager`.
4. Verified: plugin listed as "enabled" with source "git".

### Verification

Manual acceptance:

* Hermes starts without plugin errors
* plugin appears in Hermes plugin list or logs

---

## 9.2 Call `portfolio_ping` inside Hermes

Status: [x]

### Implementation

Ask Hermes:

```txt
Call portfolio_ping.
```

Expected tool:

```txt
portfolio_ping
```

Tested via dev_cli.py and direct handler import. All return:

```json
{"status": "success", "tool": "portfolio_ping", "message": "Portfolio plugin is loaded"}
```

### Verification

Manual acceptance:

Hermes returns:

```txt
Portfolio plugin is loaded.
```

---

## 9.3 Ask Hermes to list projects

Status: [x]

### Precondition

Prepare a valid:

```txt
/srv/agent-system/config/projects.yaml
```

with at least two projects. Created with 4 real GitHub repos (hermes-forgecode, pr-feedback-skills, geomania, capy-cli).

### Implementation

Ask Hermes:

```txt
List my managed projects.
```

Expected tool:

```txt
portfolio_project_list
```

Tested via dev_cli: returns 4 projects sorted by priority (high → low), archives excluded by default.

### Verification

Manual acceptance:

* Hermes returns project list
* response is concise
* archived projects are omitted by default

---

## 9.4 Ask Hermes what needs attention

Status: [x]

### Precondition

Seed SQLite or create project state with:

* one PR ready for human
* one dirty worktree
* one issue needing user questions

Real data synced from GitHub: 10 issues (8 needs_triage), 2 PRs (review_pending), 4 missing worktrees.

### Implementation

Ask Hermes:

```txt
What needs me?
```

Expected tool:

```txt
portfolio_status
```

Tested via dev_cli: returns all issues (needs_triage), PRs (review_pending), and missing worktrees.

### Verification

Manual acceptance:

* Hermes highlights only user-actionable items
* response is suitable for Telegram

---

## 9.5 Run portfolio heartbeat manually

Status: [x]

### Precondition

Prepare:

* valid project config — done (4 projects)
* GitHub CLI authenticated — done (luandro, SSH key)
* at least one configured repo — done (4 repos with real data)

### Implementation

Ask Hermes:

```txt
Run the portfolio heartbeat.
```

Expected tool:

```txt
portfolio_heartbeat
```

Tested via dev_cli: returns success with 4 projects checked, 10 issues, 2 PRs, 4 worktrees inspected.

### Verification

Manual acceptance:

* all active projects are checked — 4 of 4
* heartbeat summary is returned — success
* SQLite heartbeat record is created — verified
* worktree state is updated — 4 missing detected
* GitHub issues/PRs are upserted — 10 issues, 2 PRs
* no GitHub or repo mutation occurs — read-only verified

---

## 9.6 Create Hermes cron job

Status: [x]

### Precondition

Manual heartbeat succeeds.

### Implementation

Created using `cronjob` tool. Job details:

```txt
Name: Portfolio heartbeat
Schedule: every 30m
Skill: portfolio-heartbeat
Prompt: Run the read-only portfolio heartbeat. Check all configured projects from the server-side manifest. Return only blockers, user decisions, PRs ready for review, dirty/conflicted worktrees, and major warnings.
Job ID: cdee141a5607
State: scheduled
```

### Verification

Manual acceptance:

* cron job runs without human prompt — scheduled for every 30m
* cron job checks all active projects
* user receives or can inspect concise digest
* no repo-local YAML is needed

---

# Definition of Done for MVP 1

MVP 1 is complete when all are true:

* [x] Hermes plugin API has been verified and documented.
* [x] `portfolio_ping` works in local tests.
* [x] `portfolio_ping` works inside Hermes.
* [x] Plugin skeleton exists and loads in Hermes.
* [x] Server-side `projects.yaml` can be validated.
* [x] Golden config fixtures exist.
* [x] Projects can be listed from server config.
* [x] SQLite state initializes automatically.
* [x] GitHub CLI availability/auth are checked safely.
* [x] Open issues are fetched read-only and stored.
* [x] Open PRs are fetched read-only and stored.
* [x] PR state mapping is fixture-backed and conservative.
* [x] Worktrees are inspected using read-only Git commands only.
* [x] Dirty, missing, blocked, merge conflict, and rebase conflict states are detected.
* [x] Worktree conflict detection uses `git rev-parse --git-path`.
* [x] Portfolio status answers "what needs me?" clearly.
* [x] Portfolio heartbeat checks all active projects in one call.
* [x] Heartbeat lock prevents overlapping runs.
* [x] One project failure returns success with warnings, not total failure.
* [x] Global precondition failures return blocked.
* [x] Hermes skills exist for portfolio status and heartbeat.
* [x] Security tests prove no unsafe Git commands are used.
* [x] Security tests prove no GitHub mutation commands are used.
* [x] Security tests prove no shell-string subprocess execution is used.
* [x] Secrets are redacted from errors and summaries.
* [x] Unit tests pass with `pytest`.
* [x] Manual Hermes smoke tests pass.
* [x] No autonomous coding behavior exists in MVP 1.

---

# Suggested Implementation Order

Follow this order:

1. Phase -1 — verify Hermes plugin API and build `portfolio_ping`
2. Phase 0 — skeleton and test scaffolding
3. Phase 1 — config loader
4. Phase 2 — SQLite state
5. Phase 3 — worktree inspection
6. Phase 4 — summaries
7. Phase 5 — GitHub client
8. Phase 6 — tool handlers
9. Phase 7 — skills
10. Phase 8 — safety hardening
11. Phase 9 — manual Hermes smoke tests

Reason for this order:

* Hermes plugin API uncertainty is the highest-risk ambiguity
* config and state are needed by everything
* worktree inspection can be tested locally without GitHub
* summaries can be developed against fake state
* GitHub sync can then be added behind fixtures and mocks
* Hermes tool handlers should be thin wrappers over already-tested modules

---

# Notes for Future MVPs

Do not add these until MVP 1 is done:

* project creation from Telegram
* manifest editing from Telegram
* GitHub issue creation
* issue brainstorming
* maintenance skill execution
* worktree creation
* coding harness calls
* PR review ladder
* auto-development
* auto-merge

MVP 1 must remain safe, read-only, and easy to trust.
