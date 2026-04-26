# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 2: Project Administration, Agent-Ready Revised Version

## Goal

Track implementation progress for **Hermes Portfolio Manager Plugin MVP 2**.

MVP 2 lets the user manage projects through Hermes, including from Telegram, after the initial server setup.

The user should be able to safely do these project administration tasks:

```txt
Add a project.
Pause a project.
Resume a project.
Archive a project.
Remove a project only with confirmation.
Change project priority.
Explain project configuration.
Create a project config backup.
Set future auto-merge policy.
```

MVP 2 still does **not** do autonomous coding.

---

# Agent-Readiness Verdict

This version is ready to hand to coding agents **if MVP 1 is complete and passing**.

It removes the remaining ambiguities from the previous version:

* first-run behavior is specified,
* YAML library and preservation behavior are specified,
* removal behavior in SQLite is specified,
* default protected paths are specified,
* dev CLI flags are specified,
* Hermes clarification behavior is specified,
* root migration behavior is specified,
* backup edge cases are specified.

If MVP 1 is not complete, stop and finish MVP 1 first.

---

# Major Path Change

Starting with MVP 2, the default system root is:

```txt
$HOME/.agent-system
```

Implementation must use:

```python
Path.home() / ".agent-system"
```

Do **not** hardcode:

```txt
/srv/agent-system
/usr/HOME/.agent-system
```

Root resolution priority:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

Expected runtime layout:

```txt
$HOME/.agent-system/
  config/
    projects.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
  backups/
```

---

# Additional Agent-Readiness Decisions

## First-run config behavior

If `projects.yaml` is missing:

* `portfolio_project_add` may create a new config:

```yaml
version: 1
projects: []
```

Then it must add the project through the normal atomic write path.

* Other mutation tools must return:

```txt
status: blocked
reason: config_missing
```

If there was no previous config, no backup is created. The tool result must include:

```json
{
  "backup_created": false,
  "backup_path": null
}
```

## YAML behavior

Use:

```txt
PyYAML + Pydantic v2
```

MVP 2 must preserve unknown YAML fields as data.

MVP 2 does **not** need to preserve comments or original formatting.

Required preservation scope:

* top-level unknown fields,
* project-level unknown fields,
* nested unknown fields under `labels`,
* nested unknown fields under `notes`,
* nested unknown fields under other known project dictionaries unless explicitly unsafe.

## Removal behavior

When `portfolio_project_remove(confirm=true)` succeeds:

* remove the project from `projects.yaml`,
* do not delete worktrees,
* do not delete logs,
* do not delete artifacts,
* do not delete SQLite history,
* set SQLite `projects.status = archived`.

## Default protected paths for new projects

If no protected paths are provided, new projects must get:

```yaml
protected_paths:
  - .github/workflows/**
  - infra/**
  - auth/**
  - security/**
  - migrations/**
```

## Dev CLI flags

Use these exact flags:

```txt
--project-id
--repo
--name
--priority
--status
--default-branch
--auto-merge-enabled
--auto-merge-max-risk
--validate-github
--confirm
--reason
--root
--json
```

Boolean flags must accept explicit values where useful in tests:

```txt
--validate-github true
--validate-github false
--auto-merge-enabled true
--auto-merge-enabled false
--confirm true
--confirm false
```

## Hermes clarification behavior

Tool handlers do not run multi-turn clarification flows.

The `project-admin` skill must ask follow-up questions before calling tools when the user request is ambiguous.

Tools must block invalid or unsafe input.

---

# MVP 2 Scope Boundary

MVP 2 may mutate:

```txt
$HOME/.agent-system/config/projects.yaml
SQLite project records
local backups under $HOME/.agent-system/backups/
```

MVP 2 must not:

```txt
create GitHub issues
comment on GitHub issues
create GitHub labels
create branches
create worktrees
modify repository files
run tests in project repos
run package managers
run coding harnesses
run maintenance skills
open PRs
merge PRs
auto-develop anything
auto-merge anything
edit repo-local YAML
```

---

# Non-Negotiable Rules

1. Write a meaningful test before implementation.
2. Confirm the test fails for the expected reason.
3. Implement the smallest change to pass.
4. Preserve all MVP 1 behavior.
5. Use `$HOME/.agent-system` as the default root.
6. Use atomic writes for config mutations.
7. Create a backup before every config mutation when an existing `projects.yaml` exists.
8. Acquire `config:projects` lock before every config mutation.
9. Never enable auto-merge by default.
10. Never run GitHub mutation commands in MVP 2.
11. Never run unsafe Git commands in MVP 2.
12. Never write outside the configured system root, except when resolving the standard user home via `Path.home()`.
13. Never edit repo-local automation YAML.
14. Keep all Hermes tool results in the shared tool-result shape.
15. Use PyYAML and Pydantic v2 unless the user explicitly changes this decision.

---

# Shared Tool Result Format

All tools must return:

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

Use statuses as follows:

```txt
success: operation completed
skipped: no change needed
blocked: known precondition prevented operation
failed: unexpected error
```

Blocked/skipped are controlled outcomes, not crashes.

---

# Completion Legend

```txt
[ ] Not started
[/] In progress
[x] Done
[!] Blocked
```

---

# Required MVP 2 Tools

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

---

# Required MVP 2 Dev CLI Commands

The dev CLI must support all MVP 2 tools outside Hermes.

Required examples:

```bash
python dev_cli.py portfolio_project_add \
  --repo awana-digital/edt-next \
  --priority medium \
  --validate-github false \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_pause \
  --project-id edt-next \
  --reason travel \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_resume \
  --project-id edt-next \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_archive \
  --project-id edt-next \
  --reason done \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_set_priority \
  --project-id edt-next \
  --priority high \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_set_auto_merge \
  --project-id edt-next \
  --auto-merge-enabled true \
  --auto-merge-max-risk low \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_remove \
  --project-id edt-next \
  --confirm true \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_explain \
  --project-id edt-next \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_project_config_backup \
  --root /tmp/agent-system-test \
  --json
```

---

# Phase 0 — Preflight and MVP 1 Compatibility

## 0.1 Confirm MVP 1 baseline passes

Status: [ ]

### Test first

Run the existing MVP 1 test suite before changing anything.

```bash
pytest
```

### Implementation

No implementation yet.

### Verification

Acceptance:

* all MVP 1 tests pass before MVP 2 work begins,
* if tests fail, fix MVP 1 first.

---

## 0.2 Update default root to `$HOME/.agent-system`

Status: [ ]

### Test first

Update or add tests for root resolution:

1. explicit root argument wins,
2. `AGENT_SYSTEM_ROOT` wins when explicit root is absent,
3. default is `Path.home() / ".agent-system"`,
4. no test expects `/srv/agent-system` as default.

### Implementation

Update `resolve_root` behavior.

Old default:

```txt
/srv/agent-system
```

New default:

```python
Path.home() / ".agent-system"
```

### Verification

Run:

```bash
pytest tests/test_config.py::test_resolve_root
pytest
```

Acceptance:

* root resolution works,
* MVP 1 tests still pass.

---

## 0.3 Update runtime layout expectations

Status: [ ]

### Test first

Update tests that create runtime directories to expect:

```txt
config/
state/
worktrees/
logs/
artifacts/
backups/
```

under the resolved root.

### Implementation

Update directory creation helpers to include `backups/`.

### Verification

Run:

```bash
pytest tests/test_tools.py::test_portfolio_config_validate
pytest tests/test_state.py::test_state_initialization
```

Acceptance:

* required directories are created under the resolved root,
* no code hardcodes `/srv/agent-system`.

---

## 0.4 Add regression test against hardcoded old roots

Status: [ ]

### Test first

Create a security/regression test that scans source files and fails if these strings appear in runtime code:

```txt
/srv/agent-system
/usr/HOME/.agent-system
```

Documentation may mention old paths only in migration notes.

### Implementation

Remove hardcoded old paths from runtime code.

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_hardcoded_old_system_roots
```

Acceptance:

* runtime code does not hardcode old roots.

---

## 0.5 Update fixtures and samples to use `~/.agent-system`

Status: [ ]

### Test first

Create or update a fixture test that scans sample configs and test fixtures.

Expected:

* runtime sample configs use `~/.agent-system`,
* tests use temp roots where possible,
* `/srv/agent-system` appears only in explicit migration notes if needed.

### Implementation

Update all fixtures and samples.

### Verification

Run:

```bash
pytest tests/test_fixtures.py::test_fixtures_use_home_agent_system_or_temp_roots
```

Acceptance:

* config examples reflect the new root path.

---

# Phase 1 — Project Admin Data Models and Validation

## 1.1 Lock dependency choices

Status: [ ]

### Test first

Create a test that verifies dependency declarations include:

```txt
PyYAML
pydantic>=2
```

### Implementation

Update `pyproject.toml` or `requirements-dev.txt`.

### Verification

Run:

```bash
pytest tests/test_dependencies.py::test_mvp2_dependency_choices_are_declared
```

Acceptance:

* dependency choices are explicit,
* implementation agents do not choose a different YAML/model stack.

---

## 1.2 Extend project config model for MVP 2 fields

Status: [ ]

### Test first

Create tests verifying project config supports optional fields:

```txt
auto_merge.enabled
auto_merge.max_risk
notes
created_by
created_at
updated_at
protected_paths
labels
```

Also test that unknown fields are preserved as data at these levels:

```txt
top-level config
project object
nested labels
nested notes
nested known dictionaries
```

Comments and original formatting do not need to be preserved.

### Implementation

Extend config model in `config.py` or model module.

Required behavior:

* known fields are validated,
* unknown fields are preserved as data,
* writing config does not drop unrelated project metadata.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_project_model_preserves_optional_and_unknown_fields
```

Acceptance:

* optional MVP 2 fields are supported,
* existing config metadata is not lost.

---

## 1.3 Validate project IDs

Status: [ ]

### Test first

Create tests for valid IDs:

```txt
comapeo-cloud-app
edt-next
docs2
```

Create tests rejecting invalid IDs:

```txt
../escape
.project
ProjectName
project_name
project/
-project
project-
""
```

Required regex:

```regex
^[a-z0-9][a-z0-9-]*[a-z0-9]$
```

### Implementation

Implement:

```python
validate_project_id(project_id: str) -> None
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_project_id_validation
```

Acceptance:

* path traversal and unsafe IDs are rejected.

---

## 1.4 Validate auto-merge policy

Status: [ ]

### Test first

Create tests verifying:

1. missing auto-merge config defaults to disabled,
2. `enabled=false` passes,
3. `enabled=true, max_risk=low` passes,
4. `enabled=true, max_risk=medium` passes,
5. `enabled=true, max_risk=high` is rejected,
6. `enabled=true, max_risk=critical` is rejected,
7. `enabled=true` with no `max_risk` defaults to `low`,
8. summary for enabling auto-merge states that MVP 2 stores policy only and does not merge PRs.

### Implementation

Implement auto-merge policy validation.

Default:

```yaml
auto_merge:
  enabled: false
```

Allowed max risk when enabled:

```txt
low
medium
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_auto_merge_policy_validation
```

Acceptance:

* auto-merge can never be high/critical risk,
* auto-merge is never enabled by default.

---

## 1.5 Validate project priority and status mutations

Status: [ ]

### Test first

Create tests verifying allowed priorities:

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

Invalid values must be rejected with clear errors.

### Implementation

Reuse or extend MVP 1 validation.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_priority_and_status_mutation_validation
```

Acceptance:

* invalid mutations cannot be written.

---

## 1.6 Normalize project local paths for writing

Status: [ ]

### Test first

Create tests verifying:

1. paths under home are serialized as `~/.agent-system/...`,
2. paths outside home are preserved as absolute only if explicitly allowed by root override,
3. runtime use expands `~` correctly,
4. project ID cannot influence paths outside root.

### Implementation

Implement helpers:

```python
expand_user_path(path: str) -> Path
serialize_path_for_config(path: Path) -> str
project_base_path(root: Path, project_id: str) -> str
issue_worktree_pattern(root: Path, project_id: str) -> str
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_project_local_path_normalization
```

Acceptance:

* config remains portable,
* unsafe path escape is impossible through project ID.

---

## 1.7 Apply default protected paths

Status: [ ]

### Test first

Create tests verifying:

1. new project with no protected paths receives default protected paths,
2. user-provided protected paths override the default,
3. default protected paths are exactly:

```yaml
protected_paths:
  - .github/workflows/**
  - infra/**
  - auth/**
  - security/**
  - migrations/**
```

### Implementation

Add default protected paths to new project creation.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_default_protected_paths
```

Acceptance:

* new projects are conservative by default.

---

# Phase 2 — GitHub Repo Parsing and Read-Only Validation

## 2.1 Parse `owner/repo` GitHub references

Status: [ ]

### Test first

Create test case:

```txt
awana-digital/edt-next
```

Expected normalized fields:

```python
owner = "awana-digital"
repo = "edt-next"
repo_url = "git@github.com:awana-digital/edt-next.git"
project_id = "edt-next"
```

### Implementation

Implement:

```python
parse_github_repo_ref(value: str) -> ParsedRepo
```

### Verification

Run:

```bash
pytest tests/test_project_admin_repo_parse.py::test_parse_owner_repo
```

Acceptance:

* short GitHub repo references parse correctly.

---

## 2.2 Parse HTTPS GitHub URLs

Status: [ ]

### Test first

Create test cases:

```txt
https://github.com/awana-digital/edt-next
https://github.com/awana-digital/edt-next.git
```

Expected same normalized fields as above.

### Implementation

Extend `parse_github_repo_ref`.

### Verification

Run:

```bash
pytest tests/test_project_admin_repo_parse.py::test_parse_https_github_url
```

Acceptance:

* HTTPS repo URLs parse correctly.

---

## 2.3 Parse SSH GitHub URLs

Status: [ ]

### Test first

Create test case:

```txt
git@github.com:awana-digital/edt-next.git
```

Expected same normalized fields as above.

### Implementation

Extend `parse_github_repo_ref`.

### Verification

Run:

```bash
pytest tests/test_project_admin_repo_parse.py::test_parse_ssh_github_url
```

Acceptance:

* SSH GitHub URLs parse correctly.

---

## 2.4 Reject invalid GitHub repo inputs

Status: [ ]

### Test first

Create tests rejecting:

```txt
not-a-repo
https://gitlab.com/owner/repo
https://example.com/owner/repo
git@notgithub.com:owner/repo.git
owner/repo/extra
../owner/repo
owner/../repo
```

### Implementation

Return structured validation error or blocked result with:

```txt
reason: invalid_github_repo
```

### Verification

Run:

```bash
pytest tests/test_project_admin_repo_parse.py::test_reject_invalid_github_repo_refs
```

Acceptance:

* only recognizable GitHub repos are accepted.

---

## 2.5 Validate repo with read-only `gh repo view`

Status: [ ]

### Test first

Mock subprocess and verify command is exactly argument-array form equivalent to:

```bash
gh repo view OWNER/REPO --json name,owner,defaultBranchRef,url,isPrivate
```

Test success parses:

```txt
owner
repo
default_branch
url
is_private
```

### Implementation

Implement:

```python
validate_github_repo(owner: str, repo: str) -> GitHubRepoValidationResult
```

Use no shell strings.

### Verification

Run:

```bash
pytest tests/test_project_admin_github_validation.py::test_validate_github_repo_success
```

Acceptance:

* validation is read-only and parsed correctly.

---

## 2.6 Handle GitHub validation blocked cases

Status: [ ]

### Test first

Mock cases:

1. `gh` missing,
2. `gh` unauthenticated,
3. repo inaccessible,
4. command timeout.

Expected:

* if `validate_github=true`, return blocked,
* if `validate_github=false`, allow project add with warning.

### Implementation

Reuse MVP 1 `gh` availability/auth checks where possible.

### Verification

Run:

```bash
pytest tests/test_project_admin_github_validation.py::test_github_validation_blocked_cases
```

Acceptance:

* validation failures are controlled and safe.

---

# Phase 3 — Pure Project Mutation Functions

Pure functions must not write files or update SQLite. They mutate in-memory config only.

## 3.1 Add project to empty config

Status: [ ]

### Test first

Create test with empty valid config:

```yaml
version: 1
projects: []
```

Call pure function:

```python
add_project_to_config(config, add_input)
```

Expected:

* project is added,
* default priority is `medium` if omitted,
* default status is `active` if omitted,
* default branch is `auto` if omitted,
* auto-merge disabled by default,
* default protected paths are added,
* local paths are set,
* `created_at` and `updated_at` set.

### Implementation

Implement pure add function.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_add_project_to_empty_config
```

Acceptance:

* a new project can be created safely in memory.

---

## 3.2 Add project to existing config

Status: [ ]

### Test first

Use golden config fixture.

Add a new non-duplicate project.

Expected:

* existing projects preserved,
* unknown fields preserved,
* new project appended or inserted deterministically,
* config remains valid.

### Implementation

Extend add function.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_add_project_to_existing_config
```

Acceptance:

* adding does not damage existing config.

---

## 3.3 Reject duplicate project ID

Status: [ ]

### Test first

Attempt to add project with ID already present.

Expected blocked/validation error:

```txt
duplicate_project_id
```

### Implementation

Check project ID uniqueness before add.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_add_rejects_duplicate_project_id
```

Acceptance:

* duplicate ID is impossible.

---

## 3.4 Reject duplicate GitHub owner/repo

Status: [ ]

### Test first

Attempt to add same GitHub owner/repo under a different project ID.

Expected blocked/validation error:

```txt
duplicate_github_repo
```

### Implementation

Check normalized `github.owner` + `github.repo` uniqueness.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_add_rejects_duplicate_github_repo
```

Acceptance:

* same repo cannot be configured twice silently.

---

## 3.5 Update project fields

Status: [ ]

### Test first

Use golden config fixture.

Update:

```txt
name
priority
status
default_branch
protected_paths
auto_merge.enabled
auto_merge.max_risk
```

Expected:

* only provided fields change,
* unprovided fields preserved,
* unknown fields preserved,
* `updated_at` changes.

### Implementation

Implement:

```python
update_project_in_config(config, project_id, updates)
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_update_project_fields
```

Acceptance:

* safe partial updates work.

---

## 3.6 Reject update with no fields

Status: [ ]

### Test first

Call update with only `project_id` and no mutation fields.

Expected blocked/validation error:

```txt
no_update_fields
```

### Implementation

Add no-op mutation guard.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_update_rejects_no_fields
```

Acceptance:

* accidental no-op updates are reported clearly.

---

## 3.7 Pause project

Status: [ ]

### Test first

Call:

```python
pause_project_in_config(config, project_id, reason="travel")
```

Expected:

* status becomes `paused`,
* reason stored under notes,
* updated_at changes.

### Implementation

Implement pause helper.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_pause_project
```

Acceptance:

* paused projects will be skipped by default heartbeat behavior.

---

## 3.8 Resume project

Status: [ ]

### Test first

Start with paused project.

Expected:

* status becomes `active`,
* updated_at changes,
* previous pause reason is preserved in notes history,
* `resumed_at` is added.

### Implementation

Implement resume helper.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_resume_project
```

Acceptance:

* paused project can become active again.

---

## 3.9 Archive project

Status: [ ]

### Test first

Call archive helper.

Expected:

* status becomes `archived`,
* reason stored if provided,
* updated_at changes.

### Implementation

Implement archive helper.

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_archive_project
```

Acceptance:

* archive is supported as safe alternative to removal.

---

## 3.10 Remove project requires confirmation

Status: [ ]

### Test first

Call remove helper with `confirm=False`.

Expected:

* blocked/validation error,
* project remains in config,
* summary recommends archive.

Then call with `confirm=True`.

Expected:

* project removed from config,
* no SQLite deletion happens in pure function.

### Implementation

Implement:

```python
remove_project_from_config(config, project_id, confirm=False)
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_remove_project_requires_confirmation
```

Acceptance:

* destructive config removal requires explicit confirmation.

---

## 3.11 Set priority helper

Status: [ ]

### Test first

Call set priority with each valid priority.

Special case:

```txt
priority=paused should also set status=paused
```

Invalid priority should fail.

### Implementation

Implement:

```python
set_project_priority_in_config(config, project_id, priority)
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_set_project_priority
```

Acceptance:

* priority updates are predictable.

---

## 3.12 Set auto-merge helper

Status: [ ]

### Test first

Verify:

1. disable auto-merge,
2. enable with default max risk -> low,
3. enable with max risk medium,
4. reject high/critical,
5. summary warns that MVP 2 only stores policy.

### Implementation

Implement:

```python
set_project_auto_merge_in_config(config, project_id, enabled, max_risk=None)
```

### Verification

Run:

```bash
pytest tests/test_project_admin_config.py::test_set_project_auto_merge
```

Acceptance:

* policy storage is safe and conservative.

---

# Phase 4 — Atomic Config Writes and Backups

## 4.1 Create manual config backup

Status: [ ]

### Test first

Create test verifying:

* backup directory is created if missing,
* backup file is created with timestamped name,
* backup contents equal current `projects.yaml`,
* backup path is returned.

Expected backup pattern:

```txt
projects.yaml.2026-04-25T10-30-00Z.bak
```

Use a deterministic/frozen clock in tests.

### Implementation

Implement:

```python
create_projects_config_backup(root: Path) -> Path
```

### Verification

Run:

```bash
pytest tests/test_project_admin_writes.py::test_create_projects_config_backup
```

Acceptance:

* backups are reliable and testable.

---

## 4.2 Define missing-config backup behavior

Status: [ ]

### Test first

Create tests verifying:

1. if `projects.yaml` does not exist and operation is `portfolio_project_add`, a new config is created and no backup is created,
2. result includes `backup_created=false` and `backup_path=null`,
3. if `projects.yaml` does not exist for any other mutation, result is blocked with `reason=config_missing`.

### Implementation

Implement missing-config behavior in config load/write path.

### Verification

Run:

```bash
pytest tests/test_project_admin_writes.py::test_missing_config_first_run_behavior
```

Acceptance:

* first project can be added on fresh install,
* other mutations block on missing config.

---

## 4.3 Write config through temp file and atomic replace

Status: [ ]

### Test first

Create test monkeypatching or inspecting write behavior to verify:

* writes a temp file named like `projects.yaml.tmp.<uuid>`,
* calls atomic replacement through `os.replace`,
* final `projects.yaml` exists,
* temp file is removed or replaced.

### Implementation

Implement:

```python
write_projects_config_atomic(root: Path, config: PortfolioConfig) -> WriteResult
```

### Verification

Run:

```bash
pytest tests/test_project_admin_writes.py::test_atomic_config_write_uses_temp_file_and_replace
```

Acceptance:

* no direct partial writes to `projects.yaml`.

---

## 4.4 Validate before and after write

Status: [ ]

### Test first

Create tests verifying:

1. invalid new config is rejected before write,
2. if written file cannot be reloaded/validated, result is `failed`,
3. valid config is reloadable after write.

### Implementation

Add validation before serialization and after atomic replace.

### Verification

Run:

```bash
pytest tests/test_project_admin_writes.py::test_config_write_validates_before_and_after
```

Acceptance:

* config writer never knowingly leaves invalid config.

---

## 4.5 Backup before every mutation when config exists

Status: [ ]

### Test first

For each mutating tool/function that writes config, test backup is created when config existed before mutation:

```txt
add
update
pause
resume
archive
remove
set priority
set auto-merge
```

### Implementation

Ensure all write paths call backup before write when existing config exists.

### Verification

Run:

```bash
pytest tests/test_project_admin_writes.py::test_every_mutation_creates_backup_when_config_exists
```

Acceptance:

* every durable config change is recoverable.

---

## 4.6 Restrict writes to system root

Status: [ ]

### Test first

Create security tests attempting malicious roots or project IDs that would escape root.

Examples:

```txt
project_id = ../escape
project_id = project/escape
local.base_path = ../../outside
```

Expected:

* invalid project ID rejected,
* generated paths stay under root,
* writer only writes to `{root}/config/projects.yaml` and `{root}/backups/`.

### Implementation

Add path containment checks.

### Verification

Run:

```bash
pytest tests/test_security.py::test_config_writes_cannot_escape_system_root
```

Acceptance:

* config mutation cannot write outside allowed paths.

---

# Phase 5 — Config Write Locking

## 5.1 Acquire `config:projects` lock for mutations

Status: [ ]

### Test first

Create tests verifying each mutating operation acquires:

```txt
config:projects
```

Default TTL:

```txt
60 seconds
```

### Implementation

Add lock wrapper:

```python
with_config_lock(conn, operation)
```

or explicit acquire/release around each mutating tool.

### Verification

Run:

```bash
pytest tests/test_project_admin_locks.py::test_mutations_acquire_config_lock
```

Acceptance:

* no config mutation runs without lock.

---

## 5.2 Block mutation if config lock is held

Status: [ ]

### Test first

Pre-acquire `config:projects` lock with another owner.

Call mutation tool.

Expected result:

```python
status = "blocked"
reason = "config_lock_already_held"
```

### Implementation

Use MVP 1 lock helper.

### Verification

Run:

```bash
pytest tests/test_project_admin_locks.py::test_mutation_blocked_when_config_lock_held
```

Acceptance:

* concurrent writes are prevented.

---

## 5.3 Release lock after success and handled failure

Status: [ ]

### Test first

Create tests verifying lock is released after:

1. successful mutation,
2. validation failure after lock acquisition,
3. handled write failure.

### Implementation

Use `try/finally` for lock release.

### Verification

Run:

```bash
pytest tests/test_project_admin_locks.py::test_config_lock_released_after_success_and_failure
```

Acceptance:

* no stale lock remains after handled outcomes.

---

# Phase 6 — SQLite State Integration

## 6.1 Upsert project after add/update mutations

Status: [ ]

### Test first

Create tests verifying SQLite project row updates after:

```txt
add
update
pause
resume
archive
set priority
set auto-merge
```

Expected:

* project row reflects current config status/priority/name/repo.

### Implementation

Call MVP 1 `upsert_project` after successful config write.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_mutations_upsert_project_state
```

Acceptance:

* state database tracks project admin changes.

---

## 6.2 Remove sets SQLite project status to archived

Status: [ ]

### Test first

Seed SQLite with project row.

Call remove with `confirm=True`.

Expected:

* project removed from `projects.yaml`,
* SQLite row still exists,
* SQLite project status is set to `archived`,
* logs/worktrees/artifacts are untouched.

### Implementation

On config remove, do not delete project row. Set SQLite project status to `archived`.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_remove_sets_sqlite_project_archived_without_deleting_history
```

Acceptance:

* historical state is preserved and marked inactive.

---

# Phase 7 — Hermes Tool Schemas and Handlers

## 7.1 Add MVP 2 tool schemas

Status: [ ]

### Test first

Create tests verifying schemas exist for:

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

Each schema must include clear parameter descriptions and use the exact flag/field names from this document.

### Implementation

Add schemas in `schemas.py` using the verified Hermes plugin API from MVP 1.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_mvp2_tool_schemas_exist
```

Acceptance:

* Hermes can understand MVP 2 tool inputs.

---

## 7.2 Implement `portfolio_project_add`

Status: [ ]

### Test first

Create tests verifying:

1. adds valid project,
2. creates initial config if missing,
3. validates GitHub repo by default,
4. can skip validation with warning,
5. blocks duplicate ID,
6. blocks duplicate GitHub repo,
7. defaults auto-merge disabled,
8. applies default protected paths,
9. creates backup when config existed,
10. does not create backup on first config creation,
11. updates SQLite,
12. returns concise summary.

### Implementation

Implement handler using:

* repo parser,
* optional GitHub validation,
* pure add function,
* config lock,
* atomic write,
* SQLite upsert.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_add
```

Acceptance:

* adding a project works safely through tool interface.

---

## 7.3 Implement `portfolio_project_update`

Status: [ ]

### Test first

Create tests verifying:

1. updates safe fields,
2. rejects missing project,
3. rejects no update fields,
4. rejects invalid priority/status/auto-merge risk,
5. blocks with `config_missing` if config missing,
6. creates backup,
7. updates SQLite,
8. returns changed fields in summary/data.

### Implementation

Wire update handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_update
```

Acceptance:

* safe partial config updates work through tool interface.

---

## 7.4 Implement `portfolio_project_pause`

Status: [ ]

### Test first

Create tests verifying:

* status becomes paused,
* optional reason stored,
* blocks with `config_missing` if config missing,
* backup created,
* SQLite updated,
* summary says future heartbeats skip it by default.

### Implementation

Wire pause handler to update/pause helper.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_pause
```

Acceptance:

* project can be paused safely.

---

## 7.5 Implement `portfolio_project_resume`

Status: [ ]

### Test first

Create tests verifying:

* paused project becomes active,
* blocks with `config_missing` if config missing,
* backup created,
* SQLite updated,
* summary says it will be included in future heartbeats.

### Implementation

Wire resume handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_resume
```

Acceptance:

* project can be resumed safely.

---

## 7.6 Implement `portfolio_project_archive`

Status: [ ]

### Test first

Create tests verifying:

* status becomes archived,
* optional reason stored,
* blocks with `config_missing` if config missing,
* backup created,
* SQLite updated,
* archived project excluded by normal project list after archive.

### Implementation

Wire archive handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_archive
```

Acceptance:

* archive works as preferred safe removal alternative.

---

## 7.7 Implement `portfolio_project_set_priority`

Status: [ ]

### Test first

Create tests verifying:

* priority changes to valid value,
* invalid priority blocks,
* priority `paused` also sets status `paused`,
* blocks with `config_missing` if config missing,
* backup created,
* SQLite updated.

### Implementation

Wire priority handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_set_priority
```

Acceptance:

* priority changes are safe and predictable.

---

## 7.8 Implement `portfolio_project_set_auto_merge`

Status: [ ]

### Test first

Create tests verifying:

* disable auto-merge,
* enable with max_risk low,
* enable with max_risk medium,
* enable without max_risk defaults to low,
* reject high/critical,
* blocks with `config_missing` if config missing,
* summary says MVP 2 stores policy only and does not merge PRs,
* backup created.

### Implementation

Wire auto-merge handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_set_auto_merge
```

Acceptance:

* auto-merge policy storage is conservative.

---

## 7.9 Implement `portfolio_project_remove`

Status: [ ]

### Test first

Create tests verifying:

* remove without `confirm=True` returns blocked,
* blocked summary recommends archive,
* remove with confirmation removes from config,
* blocks with `config_missing` if config missing,
* backup created,
* worktrees/logs/artifacts are not deleted,
* SQLite history not deleted,
* SQLite project status set to archived.

### Implementation

Wire remove handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_remove
```

Acceptance:

* removal is explicit and non-destructive outside config.

---

## 7.10 Implement `portfolio_project_explain`

Status: [ ]

### Test first

Create tests verifying explanation includes:

```txt
ID
name
GitHub repo
priority
status
default branch
auto-merge setting
protected paths
local paths
```

It should not mutate config or state.

If config is missing, return blocked with `reason=config_missing`.

### Implementation

Implement read-only explain handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_explain
```

Acceptance:

* user can inspect project config from Telegram.

---

## 7.11 Implement `portfolio_project_config_backup`

Status: [ ]

### Test first

Create tests verifying:

* backup is created,
* config is validated first,
* backup path returned,
* summary includes backup path in user-friendly form,
* missing config returns blocked with `reason=config_missing`.

### Implementation

Wire backup handler.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_portfolio_project_config_backup
```

Acceptance:

* user can manually back up project config.

---

## 7.12 Register MVP 2 tools with Hermes

Status: [ ]

### Test first

Create registration test verifying all MVP 2 tools are discoverable alongside MVP 1 tools.

### Implementation

Update `__init__.py` registration using verified Hermes plugin API.

### Verification

Run:

```bash
pytest tests/test_project_admin_tools.py::test_mvp2_tool_registration
```

Acceptance:

* Hermes can discover MVP 2 tools.

---

# Phase 8 — Dev CLI Support

## 8.1 Add dev CLI support for project add

Status: [ ]

### Test first

Create test invoking:

```bash
python dev_cli.py portfolio_project_add --repo awana-digital/edt-next --priority medium --root <tmp> --validate-github false --json
```

Expected:

* JSON tool result,
* project added to tmp root config.

### Implementation

Extend `dev_cli.py`.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_project_add
```

Acceptance:

* project add can be tested outside Hermes.

---

## 8.2 Add dev CLI support for project pause/resume/explain

Status: [ ]

### Test first

Create tests invoking:

```bash
python dev_cli.py portfolio_project_pause --project-id edt-next --root <tmp> --json
python dev_cli.py portfolio_project_resume --project-id edt-next --root <tmp> --json
python dev_cli.py portfolio_project_explain --project-id edt-next --root <tmp> --json
```

### Implementation

Extend `dev_cli.py`.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_project_pause_resume_explain
```

Acceptance:

* common admin commands run locally.

---

## 8.3 Add dev CLI support for backup, archive, remove, priority, auto-merge

Status: [ ]

### Test first

Create tests invoking each remaining MVP 2 command through `dev_cli.py` using exact flags from this document.

### Implementation

Extend CLI argument parsing.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_remaining_project_admin_commands
```

Acceptance:

* all MVP 2 tools are callable outside Hermes.

---

# Phase 9 — Hermes `project-admin` Skill

## 9.1 Create `project-admin` skill

Status: [ ]

### Test first

Create test verifying:

```txt
skills/project-admin/SKILL.md
```

exists and has frontmatter:

```yaml
name: project-admin
```

### Implementation

Create the skill file.

### Verification

Run:

```bash
pytest tests/test_project_admin_skill.py::test_project_admin_skill_exists
```

Acceptance:

* skill exists with correct name.

---

## 9.2 Ensure skill references correct tools

Status: [ ]

### Test first

Create test verifying the skill mentions:

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

### Implementation

Add tool guidance to `SKILL.md`.

### Verification

Run:

```bash
pytest tests/test_project_admin_skill.py::test_project_admin_skill_mentions_tools
```

Acceptance:

* Hermes has clear guidance on tool selection.

---

## 9.3 Ensure skill contains safety and clarification rules

Status: [ ]

### Test first

Create test verifying the skill says:

* ask follow-up if request is ambiguous before calling a mutating tool,
* tool handlers do not run clarification flows,
* prefer archive over remove,
* never enable auto-merge unless explicitly requested,
* if enabling auto-merge and risk is unspecified, use low risk,
* MVP 2 stores auto-merge policy but does not merge PRs,
* do not create issues,
* do not create branches,
* do not create worktrees,
* do not modify repository files.

### Implementation

Add safety guidance to skill.

### Verification

Run:

```bash
pytest tests/test_project_admin_skill.py::test_project_admin_skill_safety_and_clarification_rules
```

Acceptance:

* Telegram/Hermes behavior is constrained by the skill.

---

# Phase 10 — Security Hardening

## 10.1 Prove no GitHub mutation commands are used

Status: [ ]

### Test first

Create or extend source scan test to reject:

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

Allowed MVP 2 GitHub command:

```txt
gh repo view
```

plus MVP 1 read-only commands.

### Implementation

Audit GitHub command usage.

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_github_mutations
```

Acceptance:

* MVP 2 cannot mutate GitHub.

---

## 10.2 Prove no unsafe Git commands are used

Status: [ ]

### Test first

Reject unsafe Git commands:

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

MVP 2 should not need new Git commands.

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_unsafe_git_commands
```

Acceptance:

* MVP 2 cannot modify Git worktrees.

---

## 10.3 Prove subprocess calls do not use `shell=True`

Status: [ ]

### Test first

Create or extend test to monkeypatch subprocess calls and ensure commands are argument lists.

### Implementation

Use:

```python
subprocess.run([...], shell=False, ...)
```

### Verification

Run:

```bash
pytest tests/test_security.py::test_subprocess_uses_argument_arrays
```

Acceptance:

* no shell-string execution.

---

## 10.4 Redact secrets from errors and summaries

Status: [ ]

### Test first

Extend MVP 1 redaction tests with GitHub validation error examples.

Patterns:

```txt
ghp_...
gho_...
ghs_...
ghu_...
sk-...
Bearer <token>
```

### Implementation

Ensure all new tool handlers pass errors through `redact_secrets`.

### Verification

Run:

```bash
pytest tests/test_security.py::test_redact_secrets
```

Acceptance:

* secrets are never returned in tool summaries or errors.

---

## 10.5 Prove MVP 2 does not modify repositories

Status: [ ]

### Test first

Create a test that sets up a fake repo/worktree and runs MVP 2 admin tools.

Expected:

* no files inside repo path are created/modified/deleted,
* only config/state/backup files under system root change.

### Implementation

Ensure project admin tools do not call worktree mutation helpers.

### Verification

Run:

```bash
pytest tests/test_security.py::test_project_admin_does_not_modify_repositories
```

Acceptance:

* MVP 2 only changes server-side config/state/backups.

---

# Phase 11 — Full Regression and Integration Tests

## 11.1 Run full automated test suite

Status: [ ]

### Test first

The full test suite is the test.

### Implementation

Fix any regressions.

### Verification

Run:

```bash
pytest
```

Acceptance:

* all MVP 1 and MVP 2 automated tests pass.

---

## 11.2 Run local end-to-end admin flow through dev CLI

Status: [ ]

### Test first

Create a pytest e2e test that uses a temp root and calls the dev CLI to:

1. add first project with validation skipped and missing config,
2. explain project,
3. set priority high,
4. pause project,
5. resume project,
6. set auto-merge low-risk only,
7. archive project,
8. create backup,
9. attempt remove without confirmation and get blocked,
10. remove with confirmation,
11. verify SQLite project status is archived,
12. verify final config is valid.

Expected:

* every step returns shared tool-result JSON,
* backups are created for mutations when config existed,
* first add creates config without backup,
* final config is valid,
* no repo files are modified.

### Implementation

Add e2e test and fix CLI/tool gaps.

### Verification

Run:

```bash
pytest tests/test_project_admin_e2e.py
```

Acceptance:

* common user management flow works without Hermes.

---

# Phase 12 — Manual Hermes Smoke Tests

Do not start manual Hermes tests until all automated tests pass.

Use a test root first:

```bash
export AGENT_SYSTEM_ROOT=/tmp/hermes-portfolio-mvp2-test
```

## 12.1 Verify plugin loads with MVP 2 tools

Status: [ ]

### Precondition

```bash
pytest
```

passes.

### Implementation

Install or reload plugin using the verified MVP 1 Hermes procedure.

### Verification

Manual acceptance:

* Hermes loads plugin without errors,
* MVP 1 and MVP 2 tools are visible/discoverable.

---

## 12.2 Add first project from missing config

Status: [ ]

### Implementation

With an empty test root, ask Hermes:

```txt
Add awana-digital/test-project as a low-priority project. Skip GitHub validation.
```

Expected tool:

```txt
portfolio_project_add
```

### Verification

Manual acceptance:

* `projects.yaml` is created,
* project is added,
* auto-merge disabled,
* default protected paths added,
* no backup created because no previous config existed,
* summary is clear.

---

## 12.3 Explain an existing project

Status: [ ]

### Implementation

Ask Hermes:

```txt
Explain the test project configuration.
```

Expected tool:

```txt
portfolio_project_explain
```

### Verification

Manual acceptance:

* Hermes summarizes the project config,
* no config mutation happens.

---

## 12.4 Pause and resume project

Status: [ ]

### Implementation

Ask Hermes:

```txt
Pause the test project because I am traveling.
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

### Verification

Manual acceptance:

* status changes correctly,
* backups are created,
* summaries are concise.

---

## 12.5 Set project priority

Status: [ ]

### Implementation

Ask Hermes:

```txt
Set the test project priority to high.
```

Expected tool:

```txt
portfolio_project_set_priority
```

### Verification

Manual acceptance:

* priority changes to high,
* backup created.

---

## 12.6 Set auto-merge policy safely

Status: [ ]

### Implementation

Ask Hermes:

```txt
Enable auto-merge for the test project, but only for low-risk changes.
```

Expected tool:

```txt
portfolio_project_set_auto_merge
```

### Verification

Manual acceptance:

* config stores `auto_merge.enabled=true`,
* max risk is low,
* Hermes states that MVP 2 stores policy only and does not merge PRs.

---

## 12.7 Try to remove without confirmation

Status: [ ]

### Implementation

Ask Hermes:

```txt
Remove the test project.
```

Expected tool:

```txt
portfolio_project_remove
```

### Verification

Manual acceptance:

* result is blocked,
* summary recommends archive,
* project remains in config.

---

## 12.8 Remove with confirmation in test root

Status: [ ]

### Implementation

Ask Hermes:

```txt
Remove the test project with confirmation.
```

Expected tool:

```txt
portfolio_project_remove
```

### Verification

Manual acceptance:

* project removed from config,
* backup created,
* no worktrees/logs/artifacts/state history deleted,
* SQLite project status is archived.

---

## 12.9 Confirm MVP 1 status still works after project admin changes

Status: [ ]

### Implementation

Ask Hermes:

```txt
List my managed projects.
```

Then:

```txt
What needs me?
```

Expected tools:

```txt
portfolio_project_list
portfolio_status
```

### Verification

Manual acceptance:

* MVP 1 tools still work with updated config,
* archived/removed projects behave as expected.

---

# Definition of Done for MVP 2

MVP 2 is complete only when all are true:

* [ ] MVP 1 tests pass before MVP 2 work starts.
* [ ] Default root is `$HOME/.agent-system` using `Path.home() / ".agent-system"`.
* [ ] `AGENT_SYSTEM_ROOT` and explicit root override still work.
* [ ] No runtime code hardcodes `/srv/agent-system` or `/usr/HOME/.agent-system`.
* [ ] Fixtures and examples use `~/.agent-system` or temp roots.
* [ ] PyYAML and Pydantic v2 are declared dependencies.
* [ ] Unknown YAML fields are preserved as data.
* [ ] Server-side project config can be mutated safely.
* [ ] First project can be added when config is missing.
* [ ] Other mutations block with `config_missing` when config is missing.
* [ ] All project admin mutations are implemented as pure functions first.
* [ ] All config mutations use `config:projects` lock.
* [ ] All config mutations create backups when config existed.
* [ ] First config creation by project add does not require backup.
* [ ] All config writes are atomic.
* [ ] Written config is reloaded and validated after write.
* [ ] Duplicate project IDs are blocked.
* [ ] Duplicate GitHub repos are blocked.
* [ ] GitHub repo refs parse from `owner/repo`, HTTPS URL, and SSH URL.
* [ ] GitHub validation uses read-only `gh repo view` only.
* [ ] Validation can be skipped with warning.
* [ ] Auto-merge defaults to disabled.
* [ ] Auto-merge max risk defaults to low when enabled without explicit risk.
* [ ] Auto-merge max risk cannot be high or critical.
* [ ] New projects get default protected paths unless explicitly overridden.
* [ ] Remove requires explicit confirmation.
* [ ] Remove does not delete worktrees, logs, artifacts, or SQLite history.
* [ ] Remove sets SQLite project status to archived.
* [ ] Archive is implemented and preferred over remove.
* [ ] `portfolio_project_explain` is read-only and useful.
* [ ] `portfolio_project_config_backup` works.
* [ ] All MVP 2 tools are registered with Hermes.
* [ ] `dev_cli.py` supports all MVP 2 tools with exact flags from this document.
* [ ] `project-admin` skill exists and contains safety and clarification guidance.
* [ ] Security tests prove no GitHub mutation commands are used.
* [ ] Security tests prove no unsafe Git commands are used.
* [ ] Security tests prove no `shell=True` subprocess execution is used.
* [ ] Security tests prove repository files are not modified.
* [ ] Security tests prove config writes cannot escape system root.
* [ ] Full automated test suite passes with `pytest`.
* [ ] Local dev CLI e2e flow passes.
* [ ] Manual Hermes smoke tests pass using a test root.

---

# Suggested Implementation Order

Follow this exact order:

1. Phase 0 — MVP 1 compatibility and root migration
2. Phase 1 — project admin models and validation
3. Phase 2 — GitHub repo parsing and validation
4. Phase 3 — pure project mutation functions
5. Phase 4 — atomic writes and backups
6. Phase 5 — config write locking
7. Phase 6 — SQLite state integration
8. Phase 7 — Hermes tool schemas and handlers
9. Phase 8 — dev CLI support
10. Phase 9 — `project-admin` skill
11. Phase 10 — security hardening
12. Phase 11 — full regression and local e2e
13. Phase 12 — manual Hermes smoke tests

Reason:

* root migration must happen before new tools,
* data and validation decisions must be locked before mutation logic,
* pure functions are safer than tool-first implementation,
* file writes and locks must be correct before Hermes mutates config,
* CLI/e2e tests make debugging possible outside Hermes,
* manual Hermes tests come last.

---

# Future MVPs Not Allowed Here

Do not add these in MVP 2:

```txt
Telegram issue creation
issue brainstorming
maintenance skill execution
worktree creation
implementation loops
review ladders
budget routing
auto-development
auto-merge execution
```

MVP 2 is project administration only.
