# MVP4_SPEC.md — Hermes Portfolio Manager Plugin MVP 4: Maintenance Skills

## Purpose

MVP 4 adds **safe, recurring maintenance checks** to the Hermes Portfolio Manager.

The system can now inspect the current state of each managed project, run small read-only maintenance checks, store reports and findings locally, and optionally create **local issue drafts** for follow-up work.

This MVP does **not** implement fixes. It does **not** create worktrees. It does **not** run coding agents. It does **not** open PRs. It does **not** merge anything.

The goal is to let the user ask questions like:

```txt
What maintenance checks are due?
Run maintenance across my active projects.
What stale issues or broken PRs need attention?
Create issue drafts for the maintenance findings, but do not publish them to GitHub.
```

MVP 4 is the bridge between “we can create good issues” and “we can later prepare worktrees for implementation.” It turns portfolio observation into structured, repeatable maintenance work.

---

## Roadmap Position

Previous MVPs:

```txt
MVP 1: read-only portfolio visibility and heartbeat
MVP 2: project administration through server-side config
MVP 3: issue creation and brainstorming with local drafts and safe GitHub issue creation
```

This MVP:

```txt
MVP 4: maintenance checks only
```

Future MVPs:

```txt
MVP 5: worktree preparation
MVP 6: implementation harness orchestration
MVP 7: review ladder
MVP 8: QA scripts and human merge readiness
MVP 9: provider/budget-aware scheduling
MVP 10: constrained auto-development / auto-merge policy
```

MVP 4 must preserve the safety ladder. It may observe and report. It may create local issue drafts through the MVP 3 draft system. It must not begin implementation work.

---

## Runtime Root

Default root remains:

```txt
$HOME/.agent-system
```

Root resolution order remains:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

Do not introduce `/srv/agent-system`, `/usr/HOME/.agent-system`, or repo-local portfolio config.

---

## What This MVP Adds

MVP 4 adds:

1. A maintenance-skill registry with a small, explicit plugin interface.
2. Server-side maintenance configuration in `$HOME/.agent-system/config/maintenance.yaml`.
3. SQLite state for maintenance runs and findings.
4. Local maintenance artifacts under `$HOME/.agent-system/artifacts/maintenance/`.
5. Tools to list, explain, enable, disable, check due status, run, and report maintenance skills.
6. Built-in read-only maintenance skills:

   * `untriaged_issue_digest`
   * `stale_issue_digest`
   * `open_pr_health`
   * `repo_guidance_docs`
7. Optional local issue draft creation for findings, using MVP 3 draft creation.
8. Dev CLI support for all new tools.
9. One Hermes skill folder for user-facing maintenance workflows.

---

## Explicit Non-Goals

MVP 4 must not:

```txt
create worktrees
clone repositories
modify repository files
run coding agents or harnesses
run Claude Code, Codex, Forge Code, Junie, Gemini, or similar implementation tools
create branches
commit changes
push changes
open pull requests
merge pull requests
edit GitHub issues
comment on GitHub issues
create GitHub labels
close GitHub issues
assign GitHub issues
change GitHub Projects, milestones, or releases
auto-fix anything
auto-publish GitHub issues from maintenance findings
introduce review ladders
introduce provider/budget-aware scheduling
introduce auto-merge policy
```

MVP 4 may create local issue drafts only when explicitly requested or explicitly configured.

---

## Scope Boundary

### May mutate

```txt
$HOME/.agent-system/config/maintenance.yaml
$HOME/.agent-system/backups/
$HOME/.agent-system/state/state.sqlite
$HOME/.agent-system/artifacts/maintenance/
$HOME/.agent-system/artifacts/issues/   # only through existing MVP 3 draft helpers
```

### Must not mutate

```txt
Git repositories
Git worktrees
Git branches
GitHub issues directly
GitHub pull requests
GitHub labels
GitHub project boards
GitHub milestones
GitHub releases
provider/model budgets
repo-local configuration files
```

### GitHub access

MVP 4 may use read-only GitHub CLI calls to refresh state and inspect repository guidance documents.

MVP 4 must not use GitHub mutation commands.

---

## User Stories

### Story 1 — List available maintenance checks

User:

```txt
What maintenance checks can this system run?
```

Expected behavior:

```txt
The system lists registered maintenance skills, whether they are enabled, their default interval, their purpose, and whether they can create local issue drafts.
```

---

### Story 2 — Enable a maintenance check

User:

```txt
Enable stale issue checks every week for all active projects.
```

Expected behavior:

```txt
The system writes config/maintenance.yaml atomically, creates a backup if needed, and reports the new schedule.
```

---

### Story 3 — Check what is due

User:

```txt
What maintenance checks are due right now?
```

Expected behavior:

```txt
The system checks enabled skills, active projects, intervals, and latest successful run timestamps, then returns a concise due list.
```

---

### Story 4 — Run maintenance without creating drafts

User:

```txt
Run maintenance across all active projects, but only report findings.
```

Expected behavior:

```txt
The system optionally refreshes GitHub state using read-only sync, runs due checks, writes a maintenance report, updates SQLite findings, and returns a summary. It creates no issue drafts.
```

---

### Story 5 — Run maintenance and create local issue drafts

User:

```txt
Run maintenance for CoMapeo Cloud App and create local issue drafts for findings.
```

Expected behavior:

```txt
The system runs configured checks for the resolved project, writes reports/findings, and creates local issue drafts for draftable findings. It does not publish those drafts to GitHub.
```

---

### Story 6 — Explain latest maintenance report

User:

```txt
Show the latest maintenance report.
```

Expected behavior:

```txt
The system returns the most recent report summary, with project-level findings, severity counts, linked local artifact paths, and draft IDs if any were created.
```

---

## New Files / Modules

Expected additions:

```txt
portfolio_manager/maintenance_config.py
portfolio_manager/maintenance_models.py
portfolio_manager/maintenance_registry.py
portfolio_manager/maintenance_runs.py
portfolio_manager/maintenance_artifacts.py
portfolio_manager/maintenance_skills.py
portfolio_manager/maintenance_builtin.py
skills/portfolio-maintenance/SKILL.md
```

Existing files to update:

```txt
portfolio_manager/state.py
portfolio_manager/tools.py
portfolio_manager/schemas.py
portfolio_manager/__init__.py
portfolio_manager/summary.py
dev_cli.py
tests/test_structure.py
tests/test_security.py
```

New tests should be added under:

```txt
tests/test_maintenance_config.py
tests/test_maintenance_registry.py
tests/test_maintenance_due.py
tests/test_maintenance_runs.py
tests/test_maintenance_artifacts.py
tests/test_maintenance_tools.py
tests/test_maintenance_cli.py
tests/test_maintenance_e2e.py
tests/test_maintenance_skills.py
```

---

## Maintenance Skill Interface

Maintenance checks must be easy to add, but not magical.

Each maintenance skill is a Python module/function registered in a local registry. Do not dynamically import arbitrary user-provided code in MVP 4.

### Skill definition

```python
@dataclass(frozen=True)
class MaintenanceSkillSpec:
    id: str
    name: str
    description: str
    default_interval_hours: int
    default_enabled: bool
    supports_issue_drafts: bool
    required_state: list[str]
    allowed_commands: list[list[str]]
    config_schema: dict[str, Any]
```

### Execution context

```python
@dataclass(frozen=True)
class MaintenanceContext:
    root: Path
    conn: sqlite3.Connection
    project: ProjectConfig
    skill_config: dict[str, Any]
    now: datetime
    refresh_github: bool
```

### Finding model

```python
@dataclass(frozen=True)
class MaintenanceFinding:
    fingerprint: str
    severity: Literal["info", "low", "medium", "high"]
    title: str
    body: str
    source_type: str
    source_id: str | None
    source_url: str | None
    metadata: dict[str, Any]
    draftable: bool = True
```

### Result model

```python
@dataclass(frozen=True)
class MaintenanceSkillResult:
    skill_id: str
    project_id: str
    status: Literal["success", "skipped", "blocked", "failed"]
    findings: list[MaintenanceFinding]
    summary: str
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
```

### Registry rules

```txt
Skill IDs must be lowercase snake_case.
Skill IDs must match: ^[a-z][a-z0-9_]{2,63}$
Unknown skill IDs must return blocked, not crash.
Only built-in registered skills may run in MVP 4.
Each skill must declare whether it supports local issue draft creation.
Each skill must declare required SQLite/GitHub state assumptions.
Each skill must be independently unit tested.
```

---

## Built-In Maintenance Skills

MVP 4 includes exactly these built-in skills.

Additional maintenance skills should be added in later MVPs or separate specs.

### 1. `untriaged_issue_digest`

Purpose:

```txt
Find open issues that are still in local state `needs_triage`.
```

Data source:

```txt
SQLite `issues` table after optional GitHub sync.
```

Default config:

```yaml
enabled: true
interval_hours: 24
min_age_hours: 24
max_findings: 20
create_issue_drafts: false
```

Finding rule:

```txt
An issue is included if:
- issue.state == "needs_triage"
- last_seen_at or updated_at is older than min_age_hours
```

Severity:

```txt
low by default
medium if older than 14 days
```

Draft behavior:

```txt
If issue drafts are requested, create one consolidated local draft per project/run, not one draft per issue.
```

---

### 2. `stale_issue_digest`

Purpose:

```txt
Find open issues that have not been updated recently.
```

Data source:

```txt
SQLite `issues` table after optional GitHub sync.
```

Default config:

```yaml
enabled: true
interval_hours: 168
stale_after_days: 30
max_findings: 20
create_issue_drafts: false
```

Finding rule:

```txt
An issue is included if:
- it is visible in the local open issue state
- updated_at or last_seen_at is older than stale_after_days
```

Severity:

```txt
low if older than stale_after_days
medium if older than stale_after_days * 2
```

Draft behavior:

```txt
If issue drafts are requested, create one consolidated local draft per project/run.
```

---

### 3. `open_pr_health`

Purpose:

```txt
Summarize open pull requests that need human attention.
```

Data source:

```txt
SQLite `pull_requests` table after optional GitHub sync.
```

Default config:

```yaml
enabled: true
interval_hours: 12
stale_after_days: 7
include_review_pending: true
include_checks_failed: true
include_changes_requested: true
max_findings: 20
create_issue_drafts: false
```

Finding rule:

```txt
A PR is included if:
- review_stage in ["checks_failed", "changes_requested"]
- OR review_stage == "review_pending" and updated_at/last_seen_at older than stale_after_days
```

Severity:

```txt
high for checks_failed
medium for changes_requested
low for old review_pending
```

Draft behavior:

```txt
By default, do not create issue drafts for PR health findings.
If explicitly requested, create one consolidated local draft per project/run describing PR follow-up work.
```

---

### 4. `repo_guidance_docs`

Purpose:

```txt
Check whether a repository has basic agent/human guidance documents.
```

Data source:

```txt
Read-only GitHub API through gh CLI.
```

Default config:

```yaml
enabled: false
interval_hours: 168
required_files:
  - README.md
  - AGENTS.md
optional_files:
  - CLAUDE.md
  - CONTRIBUTING.md
freshness_days: 180
create_issue_drafts: false
```

Finding rule:

```txt
A finding is produced if:
- a required file is missing
- OR a required file has no detectable recent commit within freshness_days
```

Severity:

```txt
medium for missing AGENTS.md
low for missing README.md only if repository metadata suggests no README exists
low for stale guidance docs
info for missing optional docs
```

Allowed read-only GitHub commands for this skill:

```txt
gh api --method GET repos/OWNER/REPO/contents/PATH
gh api --method GET "repos/OWNER/REPO/commits?path=PATH&per_page=1"
```

Draft behavior:

```txt
If issue drafts are requested, create one local draft per project recommending documentation updates.
```

---

## Deferred Maintenance Skills

Do not implement these in MVP 4 unless the spec is explicitly revised:

```txt
docs_link_check
security_dependency_alert_summary
old_branch_report
old_worktree_report
release_health
repo_size_or_large_file_check
license_check
code_owner_check
```

Reasons for deferral:

```txt
docs_link_check requires external HTTP fetching and timeout/rate-limit policy.
security/dependency alerts require GitHub permissions and API shape verification.
old branch checks can become branch-management work.
old worktree checks fit better after MVP 5 creates worktrees.
release/license/code-owner checks are useful but not needed for the first maintenance layer.
```

---

## New Tools

MVP 4 adds these tools:

```txt
portfolio_maintenance_skill_list
portfolio_maintenance_skill_explain
portfolio_maintenance_skill_enable
portfolio_maintenance_skill_disable
portfolio_maintenance_due
portfolio_maintenance_run
portfolio_maintenance_run_project
portfolio_maintenance_report
```

All tools must return the shared result shape:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "tool_name",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None,
}
```

Important implementation note:

```txt
Existing `_failed` currently returns status="error" in tools.py. MVP 4 should either align `_failed` with the documented status="failed" or explicitly preserve current behavior after updating the shared contract. Preferred: migrate to status="failed" and update tests if safe.
```

---

## Tool Specifications

### 1. `portfolio_maintenance_skill_list`

Purpose:

```txt
List registered maintenance skills and their config status.
```

Input schema:

```python
{
    "root": "string | null",
    "include_disabled": "boolean, default true",
    "include_project_overrides": "boolean, default false"
}
```

Behavior:

```txt
Load maintenance registry.
Load maintenance config if present.
If config is missing, use defaults and report that no maintenance config exists yet.
Return each skill with registry metadata, enabled status, interval, and supports_issue_drafts.
```

Side effects:

```txt
None.
```

Blocked cases:

```txt
Invalid maintenance.yaml.
Invalid root path.
```

---

### 2. `portfolio_maintenance_skill_explain`

Purpose:

```txt
Explain one maintenance skill, including what it checks, what data it reads, what commands it may run, and what it may write.
```

Input schema:

```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null"
}
```

Behavior:

```txt
Validate skill_id.
Return registry spec, default config, effective global config, and optional project override.
Explain exactly whether the skill can create local issue drafts.
```

Side effects:

```txt
None.
```

Blocked cases:

```txt
Unknown skill_id.
Invalid maintenance config.
Unknown project_id when project_id is supplied.
```

---

### 3. `portfolio_maintenance_skill_enable`

Purpose:

```txt
Enable a maintenance skill globally or for one project.
```

Input schema:

```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null",
    "interval_hours": "integer | null",
    "create_issue_drafts": "boolean | null",
    "config": "object | null"
}
```

Behavior:

```txt
Validate skill_id against registry.
Validate project_id if supplied.
Validate interval_hours if supplied: 1 <= interval_hours <= 2160.
Validate config keys against the skill config schema.
Create config/maintenance.yaml if missing.
Preserve unknown top-level fields.
Write atomically.
Create timestamped backup if file already existed.
Return effective config after write.
```

Side effects:

```txt
May create or update $HOME/.agent-system/config/maintenance.yaml.
May create backup under $HOME/.agent-system/backups/.
```

Lock:

```txt
maintenance:config
```

Blocked cases:

```txt
Unknown skill_id.
Unknown project_id.
Invalid config schema.
Config lock already held.
Path escape attempt.
```

---

### 4. `portfolio_maintenance_skill_disable`

Purpose:

```txt
Disable a maintenance skill globally or for one project.
```

Input schema:

```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null"
}
```

Behavior:

```txt
Validate skill_id.
If project_id is supplied, disable only the project override.
If project_id is omitted, disable globally.
Create config/maintenance.yaml if missing, storing the disabled state explicitly.
Write atomically and create backup if file existed.
Return effective config after write.
```

Side effects:

```txt
May create or update config/maintenance.yaml.
May create backup.
```

Lock:

```txt
maintenance:config
```

Blocked cases:

```txt
Unknown skill_id.
Unknown project_id.
Invalid existing maintenance.yaml.
Config lock already held.
```

---

### 5. `portfolio_maintenance_due`

Purpose:

```txt
Show which maintenance checks are due now.
```

Input schema:

```python
{
    "root": "string | null",
    "project_id": "string | null",
    "skill_id": "string | null",
    "include_disabled": "boolean, default false",
    "include_paused": "boolean, default false",
    "include_archived": "boolean, default false"
}
```

Behavior:

```txt
Load projects config.
Load maintenance config with defaults.
Filter active projects by default.
Check latest successful maintenance run for each project/skill.
Compute due status using interval_hours.
Return due, not_due, disabled, blocked counts.
```

Due formula:

```txt
A project/skill is due if:
- skill effective config enabled == true
- no previous successful run exists
- OR now >= latest_successful_finished_at + interval_hours
```

Side effects:

```txt
None.
```

Blocked cases:

```txt
Invalid projects config.
Invalid maintenance config.
Unknown project_id.
Unknown skill_id.
```

---

### 6. `portfolio_maintenance_run`

Purpose:

```txt
Run due maintenance checks across selected projects.
```

Input schema:

```python
{
    "root": "string | null",
    "skill_id": "string | null",
    "project_id": "string | null",
    "refresh_github": "boolean, default true",
    "create_issue_drafts": "boolean, default false",
    "include_not_due": "boolean, default false",
    "include_paused": "boolean, default false",
    "include_archived": "boolean, default false",
    "dry_run": "boolean, default false",
    "max_projects": "integer | null"
}
```

Behavior:

```txt
Resolve selected projects and skills.
If dry_run=true, compute and return planned checks only.
Acquire global maintenance run lock.
For each selected project/skill due item:
  - acquire project/skill lock
  - optionally refresh GitHub issue/PR state using existing read-only sync helpers
  - run the skill
  - store run row
  - upsert findings by fingerprint
  - write run artifacts
  - optionally create local issue draft if allowed/requested
  - release project/skill lock
Release global run lock.
Return compact summary and report path.
```

Side effects when `dry_run=false`:

```txt
May update SQLite maintenance tables.
May update SQLite issue/PR tables through existing read-only GitHub sync.
May write maintenance artifacts.
May create local issue drafts through MVP 3 helpers if create_issue_drafts=true.
```

Side effects when `dry_run=true`:

```txt
None.
```

Locks:

```txt
maintenance:run
maintenance:project:<project_id>:skill:<skill_id>
```

Blocked cases:

```txt
MVP 1-3 config/state cannot be loaded.
Unknown skill_id.
Unknown project_id.
Global maintenance lock held.
GitHub refresh requested but gh unavailable/auth unavailable; block only skills that require GitHub API, otherwise run with local state and warning.
create_issue_drafts=true but skill does not support drafts.
```

---

### 7. `portfolio_maintenance_run_project`

Purpose:

```txt
Convenience wrapper to run maintenance for one project.
```

Input schema:

```python
{
    "project_ref": "string, required",
    "root": "string | null",
    "skill_id": "string | null",
    "refresh_github": "boolean, default true",
    "create_issue_drafts": "boolean, default false",
    "include_not_due": "boolean, default true",
    "dry_run": "boolean, default false"
}
```

Behavior:

```txt
Resolve project_ref using MVP 3 deterministic project resolution.
If ambiguous or not found, return blocked.
Call portfolio_maintenance_run internally with project_id.
Default include_not_due=true because the user explicitly asked for one project.
```

Side effects:

```txt
Same as portfolio_maintenance_run.
```

Blocked cases:

```txt
Ambiguous project_ref.
Unknown project_ref.
Same blocked cases as portfolio_maintenance_run.
```

---

### 8. `portfolio_maintenance_report`

Purpose:

```txt
Return latest or selected maintenance reports and findings.
```

Input schema:

```python
{
    "root": "string | null",
    "run_id": "string | null",
    "project_id": "string | null",
    "skill_id": "string | null",
    "status": "string | null",
    "severity": "string | null",
    "limit": "integer, default 20",
    "include_resolved": "boolean, default false"
}
```

Behavior:

```txt
If run_id is provided, return that run and its artifact paths.
Otherwise return recent runs and open findings filtered by project/skill/severity.
Include draft IDs/paths when findings created local issue drafts.
Summaries must be concise enough for Telegram/Hermes chat.
```

Side effects:

```txt
None.
```

Blocked cases:

```txt
Unknown run_id.
Unknown project_id.
Unknown skill_id.
Invalid filter enum.
```

---

## State / Schema Changes

Update `portfolio_manager/state.py` schema idempotently.

### New table: `maintenance_runs`

```sql
CREATE TABLE IF NOT EXISTS maintenance_runs (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  project_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  due INTEGER NOT NULL DEFAULT 1,
  dry_run INTEGER NOT NULL DEFAULT 0,
  refresh_github INTEGER NOT NULL DEFAULT 1,
  finding_count INTEGER NOT NULL DEFAULT 0,
  draft_count INTEGER NOT NULL DEFAULT 0,
  report_path TEXT,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill
ON maintenance_runs(project_id, skill_id, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_status
ON maintenance_runs(status, finished_at);
```

### New table: `maintenance_findings`

```sql
CREATE TABLE IF NOT EXISTS maintenance_findings (
  fingerprint TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source_type TEXT,
  source_id TEXT,
  source_url TEXT,
  metadata_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  run_id TEXT,
  issue_draft_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (run_id) REFERENCES maintenance_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (issue_draft_id) REFERENCES issue_drafts(draft_id) ON DELETE SET NULL
);
```

Indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_maintenance_findings_project_skill
ON maintenance_findings(project_id, skill_id, status);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_severity
ON maintenance_findings(severity, status);
```

### Status enums

Run statuses:

```txt
planned
running
success
skipped
blocked
failed
```

Finding statuses:

```txt
open
resolved
draft_created
ignored
```

MVP 4 does not need a tool to manually ignore findings. `ignored` is reserved for future use and should not be emitted by MVP 4 unless explicitly implemented with tests.

### State helper functions

Add tested helpers:

```python
start_maintenance_run(conn, run: dict[str, Any]) -> str
finish_maintenance_run(conn, run_id: str, status: str, summary: str | None, error: str | None) -> None
get_maintenance_run(conn, run_id: str) -> dict[str, Any] | None
list_maintenance_runs(conn, filters: MaintenanceRunFilters) -> list[dict[str, Any]]
upsert_maintenance_finding(conn, finding: dict[str, Any]) -> None
get_maintenance_finding(conn, fingerprint: str) -> dict[str, Any] | None
list_maintenance_findings(conn, filters: MaintenanceFindingFilters) -> list[dict[str, Any]]
mark_resolved_missing_findings(conn, project_id: str, skill_id: str, seen_fingerprints: set[str], resolved_at: str) -> int
```

All helpers must validate statuses.

---

## Maintenance Config

New file:

```txt
$HOME/.agent-system/config/maintenance.yaml
```

This file is server-side policy. Do not require repo-local maintenance config.

### Example

```yaml
version: 1

defaults:
  refresh_github: true
  create_issue_drafts: false
  max_projects_per_run: 20

skills:
  untriaged_issue_digest:
    enabled: true
    interval_hours: 24
    min_age_hours: 24
    max_findings: 20
    create_issue_drafts: false

  stale_issue_digest:
    enabled: true
    interval_hours: 168
    stale_after_days: 30
    max_findings: 20
    create_issue_drafts: false

  open_pr_health:
    enabled: true
    interval_hours: 12
    stale_after_days: 7
    include_review_pending: true
    include_checks_failed: true
    include_changes_requested: true
    max_findings: 20
    create_issue_drafts: false

  repo_guidance_docs:
    enabled: false
    interval_hours: 168
    required_files:
      - README.md
      - AGENTS.md
    optional_files:
      - CLAUDE.md
      - CONTRIBUTING.md
    freshness_days: 180
    create_issue_drafts: false

projects:
  comapeo-cloud-app:
    skills:
      stale_issue_digest:
        enabled: true
        stale_after_days: 21
      repo_guidance_docs:
        enabled: true
        required_files:
          - README.md
          - AGENTS.md
          - MVP_PLANNING_GUIDE.md
```

### Config rules

```txt
Missing maintenance.yaml is allowed.
When missing, registry defaults are used.
Enable/disable tools may create maintenance.yaml.
Existing unknown top-level fields must be preserved.
Existing unknown project fields must be preserved.
Unknown skill IDs in maintenance.yaml should block validation unless explicitly under an `x_` extension key.
Invalid intervals block validation.
Invalid project IDs block validation.
Config writes must be atomic.
Existing config must be backed up before mutation.
```

### Effective config resolution

For a project/skill:

```txt
1. Registry defaults
2. maintenance.yaml defaults
3. maintenance.yaml skills.<skill_id>
4. maintenance.yaml projects.<project_id>.skills.<skill_id>
5. explicit tool args for one run only
```

Tool args must not persist unless the tool is an enable/disable/config mutation tool.

---

## Artifact Layout

MVP 4 writes reports under:

```txt
$HOME/.agent-system/artifacts/maintenance/<run_id>/
  report.md
  findings.json
  metadata.json
  planned-checks.json
  github-refresh.json
  draft-created.json
  error.json
```

Files:

### `report.md`

Human-readable maintenance report.

Required sections:

```txt
# Maintenance Report
Run ID
Started / finished
Selected projects
Selected skills
Summary
Findings by severity
Findings by project
Drafts created
Warnings
Errors
```

### `findings.json`

Machine-readable findings.

Must include:

```txt
fingerprint
project_id
skill_id
severity
status
title
body
source_type
source_id
source_url
metadata
issue_draft_id
```

### `metadata.json`

Run metadata.

Must include:

```txt
run_id
root
started_at
finished_at
selected_project_ids
selected_skill_ids
refresh_github
create_issue_drafts
dry_run
```

### `planned-checks.json`

Written only for dry-runs or before a real run starts.

Must include:

```txt
project_id
skill_id
due
reason
would_refresh_github
would_create_issue_drafts
```

### `github-refresh.json`

Written when `refresh_github=true`.

Must include:

```txt
project_id
issues_count
prs_count
warnings
error
```

### `draft-created.json`

Written when local issue drafts are created.

Must include:

```txt
finding_fingerprint
project_id
skill_id
draft_id
draft_artifact_path
```

### `error.json`

Written when a run fails or a skill fails unexpectedly.

Must include:

```txt
run_id
project_id
skill_id
error_type
message
redacted_trace_or_context
```

Do not store secrets in artifacts.

---

## Issue Draft Creation Policy

MVP 4 must prefer reports over drafts.

Default:

```txt
create_issue_drafts=false
```

A local issue draft may be created only if all are true:

```txt
The user explicitly passed create_issue_drafts=true for this run
OR effective config has create_issue_drafts=true.
The skill supports issue drafts.
The skill result has at least one draftable finding.
No existing open finding with the same fingerprint already has an issue_draft_id.
No duplicate local issue draft exists for the same normalized title.
The draft is created through existing MVP 3 draft helpers.
```

MVP 4 must never publish those drafts to GitHub.

No MVP 4 tool may call:

```txt
portfolio_issue_create
portfolio_issue_create_from_draft with confirm=true
gh issue create
```

Draft title format:

```txt
Maintenance: <Skill Name> findings for <Project Name>
```

Draft body format should include:

```txt
Goal
Why this matters
Findings
Suggested manual next step
Acceptance criteria
Source maintenance run ID
```

The body must not include hidden chain-of-thought or private runtime metadata beyond local run IDs and local artifact paths.

---

## Allowed Commands

MVP 4 may run only these external commands.

### Existing read-only GitHub sync

```txt
gh --version
gh auth status
gh issue list --repo OWNER/REPO --state open --limit N --json number,title,labels,author,createdAt,updatedAt,url
gh pr list --repo OWNER/REPO --state open --limit N --json number,title,headRefName,baseRefName,labels,reviewDecision,statusCheckRollup,createdAt,updatedAt,url
```

### Guidance docs check

```txt
gh api --method GET repos/OWNER/REPO/contents/PATH
gh api --method GET "repos/OWNER/REPO/commits?path=PATH&per_page=1"
```

No command may use `shell=True`.

All subprocess calls must use argument arrays.

Timeouts:

```txt
gh --version: 10 seconds
gh auth status: 10 seconds
gh issue list: 30 seconds
gh pr list: 30 seconds
gh api contents/commits: 20 seconds per file request
```

---

## Disallowed Commands

MVP 4 must not run:

```txt
git clone
git pull
git fetch
git rebase
git merge
git reset
git clean
git stash
git checkout
git switch
git commit
git push
gh issue create
gh issue edit
gh issue comment
gh issue close
gh label create
gh pr create
gh pr merge
gh pr comment
gh pr review
gh api --method POST
gh api --method PATCH
gh api --method PUT
gh api --method DELETE
```

MVP 4 should not add general-purpose HTTP requests for link checking.

---

## Locking and Concurrency

Use the existing SQLite advisory lock table.

Locks:

```txt
maintenance:config
maintenance:run
maintenance:project:<project_id>:skill:<skill_id>
```

Recommended TTLs:

```txt
maintenance:config: 60 seconds
maintenance:run: 30 minutes
maintenance:project:<project_id>:skill:<skill_id>: 10 minutes
```

Rules:

```txt
Config mutation requires maintenance:config.
Global maintenance run requires maintenance:run.
Each project/skill check requires maintenance:project:<project_id>:skill:<skill_id>.
If a project/skill lock is held, skip that item and record status=skipped.
If global run lock is held, return blocked.
All locks must be released in finally blocks.
Expired locks may be acquired using existing lock semantics.
```

---

## Idempotency and Duplicate Prevention

### Finding fingerprint

Each finding fingerprint must be stable:

```txt
sha256(project_id + skill_id + source_type + source_id + normalized_title)
```

Normalization:

```txt
lowercase
trim whitespace
collapse repeated whitespace
remove volatile timestamps
```

### Finding behavior

```txt
If fingerprint is new, insert finding with status=open.
If fingerprint already exists and status is open/draft_created, update last_seen_at, body, metadata, run_id.
If a previously open finding is not seen during a successful project/skill run, set status=resolved and resolved_at=now.
If a finding already has issue_draft_id, do not create another draft.
```

### Run behavior

```txt
Every real run gets a unique run_id.
Dry-run does not insert maintenance_runs.
A failed run records status=failed and error.json.
Retrying a failed run creates a new run but reuses finding fingerprints.
```

### Draft behavior

```txt
One consolidated issue draft per project/skill/run.
Do not create duplicate drafts for findings that already have issue_draft_id.
If a draft creation partially succeeds, store draft-created.json and update findings with issue_draft_id.
If artifact write succeeds but SQLite update fails, the next run should detect draft-created.json and repair SQLite state.
```

---

## Failure and Recovery

### Config write failure

```txt
Do not modify original config if atomic write fails.
Return failed with redacted error.
Backup remains available.
```

### GitHub unavailable

```txt
If refresh_github=true and gh is unavailable:
- For local-state-only skills, run using existing SQLite state and include warning.
- For repo_guidance_docs, return blocked for that skill.
```

### GitHub auth unavailable

Same behavior as GitHub unavailable.

### Skill failure

```txt
Record a failed maintenance_runs row for that project/skill.
Write error.json.
Continue other project/skill checks unless the failure is global config/state corruption.
```

### Artifact write failure

```txt
Run may still record findings in SQLite.
Return failed or partial success depending on whether core findings were persisted.
Include error in summary.
```

### Draft creation failure

```txt
Do not fail the full maintenance run if findings/report succeeded.
Record warning.
Write error.json or draft-created error entry.
Leave findings open without issue_draft_id.
```

### Crash recovery

At the start of a new run:

```txt
Find maintenance_runs with status=running and started_at older than lock TTL.
Mark them failed with error="stale running maintenance run".
Do not delete artifacts.
```

---

## Dry-Run Behavior

Dry-run must:

```txt
validate projects config
validate maintenance config
resolve selected projects/skills
compute due/not-due status
show commands that would be used at a high level
show whether GitHub refresh would run
show whether local issue drafts would be created
not run GitHub commands
not mutate SQLite
not write artifacts
not create issue drafts
```

Dry-run returns:

```txt
planned_checks
blocked_checks
not_due_checks
would_create_issue_drafts_count
warnings
```

---

## Security and Privacy Rules

```txt
No shell=True.
All subprocess calls use arrays.
Only listed gh commands are allowed.
Only gh api --method GET is allowed.
Reject path traversal in guidance doc paths.
Guidance doc paths must be relative POSIX paths without `..`, leading `/`, shell metacharacters, or URL schemes.
Skill IDs must match the registry ID regex.
Project IDs must resolve from trusted projects config.
Maintenance artifacts must stay under $HOME/.agent-system/artifacts/maintenance/.
Issue drafts must be created only through MVP 3 artifact helpers.
Secrets must be redacted using existing redact_secrets behavior.
Do not store gh tokens, env vars, or auth output in artifacts.
Do not include hidden chain-of-thought in reports or drafts.
```

---

## Dev CLI Requirements

Add CLI support for:

```bash
python dev_cli.py portfolio_maintenance_skill_list --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_explain --skill-id stale_issue_digest --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_enable --skill-id stale_issue_digest --interval-hours 168 --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_disable --skill-id repo_guidance_docs --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_due --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --skill-id stale_issue_digest --refresh-github false --create-issue-drafts false --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run_project --project-ref comapeo-cloud-app --skill-id open_pr_health --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_report --root /tmp/agent-system-test --json
```

New CLI args:

```txt
--skill-id
--interval-hours
--config-json
--include-disabled
--include-project-overrides
--include-paused
--include-archived
--include-not-due
--refresh-github
--create-issue-drafts
--max-projects
--run-id
--severity
--limit
--include-resolved
```

Boolean args should reuse existing `_to_bool` behavior.

`--config-json` must parse a JSON object and reject arrays/scalars.

---

## Hermes Skill Requirements

Add:

```txt
skills/portfolio-maintenance/SKILL.md
```

The skill must explain:

```txt
MVP 4 is maintenance/reporting only.
Prefer dry-run before real run.
Reports are default; local issue drafts are optional.
GitHub issues are not published by maintenance tools.
Use portfolio_maintenance_due before broad runs.
Use portfolio_maintenance_run_project for targeted checks.
Use portfolio_maintenance_report to summarize results.
Do not promise auto-fixes, implementation, PRs, or merges.
```

Example user flows to include:

```txt
List maintenance skills.
Enable weekly stale issue checks.
Show checks due now.
Dry-run maintenance.
Run maintenance and report findings.
Run project-specific maintenance and create local drafts.
Show latest maintenance report.
```

---

## Required Tests

### Structure tests

```txt
New maintenance modules exist.
portfolio-maintenance skill folder exists.
All new tools are registered in __init__.py.
All new tool schemas exist.
All new CLI commands exist.
```

### Config tests

```txt
Missing maintenance.yaml uses defaults.
Enable creates maintenance.yaml.
Disable creates maintenance.yaml if missing.
Atomic writes preserve old file on failure.
Backup is created when existing file is mutated.
Unknown top-level fields are preserved.
Unknown skill IDs block validation.
Unknown project IDs block validation.
Invalid interval_hours blocks validation.
Project override wins over global skill config.
Tool args override effective config only for one run.
Path containment for config/backups is enforced.
```

### Registry tests

```txt
All built-in skills are registered.
Skill IDs match regex.
Unknown skill ID returns blocked.
Each built-in skill declares default config and allowed commands.
Each built-in skill can be explained.
```

### Due computation tests

```txt
Never-run skill is due.
Recently successful run is not due.
Old successful run is due.
Disabled skill is not due.
Paused/archived projects are excluded by default.
include_paused/include_archived works.
Explicit project_id filters due list.
Explicit skill_id filters due list.
```

### Built-in skill tests

```txt
untriaged_issue_digest finds only needs_triage issues older than min_age_hours.
stale_issue_digest finds old issues and respects max_findings.
open_pr_health finds checks_failed, changes_requested, and old review_pending PRs.
repo_guidance_docs handles present, missing, stale, and inaccessible files using mocked gh api GET.
All fingerprints are stable across repeated runs.
Severity rules are deterministic.
```

### Artifact tests

```txt
Maintenance report path is contained under artifacts/maintenance.
run_id path traversal is rejected.
report.md includes required sections.
findings.json includes required fields.
metadata.json includes selected projects/skills.
error.json redacts secrets.
Dry-run writes no artifacts.
```

### State tests

```txt
maintenance_runs table initializes idempotently.
maintenance_findings table initializes idempotently.
Run statuses validate.
Finding statuses validate.
start/finish run helpers work.
Finding upsert updates last_seen_at.
Missing findings become resolved after successful run.
Finding with issue_draft_id does not duplicate drafts.
Stale running runs are marked failed on recovery.
```

### Tool tests

```txt
Each tool returns shared result shape.
skill_list works with missing config.
skill_explain blocks unknown skill.
skill_enable writes config under lock.
skill_disable writes config under lock.
due returns due/not_due/disabled counts.
run dry_run has no side effects.
run real stores runs/findings/artifacts.
run_project resolves project_ref and blocks ambiguity.
report reads latest run and filters by severity/project/skill.
```

### GitHub command/security tests

```txt
No shell=True anywhere in MVP 4 subprocess code.
Only allowed gh commands appear in maintenance code.
No gh api POST/PATCH/PUT/DELETE.
No gh issue create from maintenance code.
No gh pr create/merge/comment/review.
Guidance doc paths reject .., absolute paths, URLs, and shell metacharacters.
Mocked subprocess calls use argument arrays.
Timeouts are set.
Secrets are redacted.
```

### Draft integration tests

```txt
create_issue_drafts=false creates no drafts.
create_issue_drafts=true creates local draft for draftable findings.
Skill that does not support drafts blocks draft creation.
Existing finding with issue_draft_id does not create duplicate draft.
Draft creation failure records warning but does not lose findings.
Maintenance draft body does not include private metadata or chain-of-thought.
No maintenance code calls GitHub issue creation.
```

### E2E tests

```txt
With test root and seeded projects/issues/PRs, dry-run reports planned checks and no side effects.
With test root and seeded issues, real run stores findings and report.
With create_issue_drafts=true, real run creates local issue draft only.
Repeated real run updates same findings instead of duplicating them.
Resolved finding is marked resolved when no longer returned.
```

### Regression tests

Run full test suite:

```bash
pytest
```

Existing MVP 1-3 behavior must remain green.

---

## Manual Hermes Smoke Tests

Run only after automated tests pass.

```txt
List available maintenance skills.
Explain stale issue checks.
Enable weekly stale issue checks.
Show maintenance checks due now.
Dry-run maintenance across active projects.
Run maintenance across active projects without creating drafts.
Show the latest maintenance report.
Run maintenance for one test project and create local issue drafts.
Show open issue drafts and confirm they were not published to GitHub.
Disable repo guidance docs.
```

Manual smoke must use test repos or a safe configured test root unless the user explicitly authorizes production repos.

---

## Acceptance Criteria

1. `pytest` passes, including all MVP 1-3 regression tests.
2. All eight new maintenance tools are registered and callable from Hermes and `dev_cli.py`.
3. Missing `maintenance.yaml` is handled safely with registry defaults.
4. Enable/disable tools mutate only `config/maintenance.yaml` and backups, using locks and atomic writes.
5. Due computation is deterministic and test-covered.
6. Built-in maintenance checks produce deterministic findings from local SQLite state or allowed read-only GitHub calls.
7. Real runs write SQLite run/finding state and local maintenance artifacts.
8. Dry-runs perform no external commands and no mutations.
9. Optional draft creation creates local MVP 3 issue drafts only.
10. No MVP 4 code creates GitHub issues directly.
11. No MVP 4 code creates worktrees, branches, commits, PRs, labels, comments, or merges.
12. Security tests prove command allowlists, path containment, redaction, and no `shell=True`.
13. Manual Hermes smoke tests pass.

---

## Definition of Done

MVP 4 is done when Hermes can safely run recurring, read-only maintenance checks across active projects, store local reports and findings, and optionally convert those findings into local issue drafts without publishing anything to GitHub or modifying any repositories.

The user can now rely on Hermes to say:

```txt
Here is what needs attention across your portfolio.
Here are the reports.
Here are optional drafts you can review.
Nothing was implemented or published without your explicit next step.
```

---

## Self-Critique and Final Design Decisions

### Scope risk: too many maintenance checks

The original roadmap examples included docs link checks, dependency alerts, broken CI summaries, and old branch/worktree reports. This spec narrows MVP 4 to four built-in checks.

Decision:

```txt
Keep MVP 4 focused. Add more checks later only after the maintenance framework is proven.
```

### Mutation risk: enabling/disabling checks mutates config

MVP 4 is not purely read-only because enable/disable writes `maintenance.yaml`.

Decision:

```txt
Treat maintenance config mutation like MVP 2 admin mutation: server-side only, locked, atomic, backed up, and test-covered.
```

### Draft risk: maintenance could spam issues

Maintenance findings can become noisy.

Decision:

```txt
Default to reports only. If drafts are requested, create one consolidated local draft per project/skill/run. Never publish to GitHub from MVP 4.
```

### GitHub API risk

`repo_guidance_docs` requires `gh api`. That could be risky if left too broad.

Decision:

```txt
Allow only `gh api --method GET` for exact repository contents/commits endpoints. Security tests must reject POST/PATCH/PUT/DELETE and arbitrary gh api mutations.
```

### Scheduling risk

Hermes heartbeats may later call maintenance checks automatically, but this MVP should not require a full scheduler.

Decision:

```txt
Implement due computation and run tools. Actual recurring invocation remains a Hermes heartbeat/scheduler concern outside this spec unless already supported.
```

### Agent-readiness verdict

This SPEC is ready to turn into `MVP4_PROGRESS.md` if MVP 1-3 tests are green and PR #3 is treated as the implemented baseline.

Before implementation, create `MVP4_PROGRESS.md` with test-first phases and do not let the coding agent implement directly from this SPEC alone.
