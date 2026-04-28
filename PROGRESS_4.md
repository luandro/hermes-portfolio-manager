# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 4: Maintenance Skills

## Goal

Implement MVP 4: safe maintenance checks for the Hermes Portfolio Manager.

MVP 4 must let Hermes list, explain, configure, run, and report maintenance checks across managed projects. It may write local maintenance reports and local issue drafts. It must not modify repositories, create worktrees, run coding agents, open PRs, or publish GitHub issues from maintenance tools.

The final system should support this user flow:

```txt
List maintenance skills.
Enable stale issue checks.
Show what maintenance is due.
Dry-run maintenance.
Run maintenance and generate reports.
Optionally create local issue drafts for findings.
Review the latest maintenance report.
```

---

## Agent-Readiness Verdict

Ready for a development agent **only after** MVPs 1–3 are confirmed green in the repository.

Before implementing this file, the agent must run:

```bash
pytest
```

If any MVP 1–3 tests fail, fix regressions first. Do not start MVP 4 on top of a failing baseline.

Assumptions:

```txt
MVP 1 portfolio visibility exists.
MVP 2 project administration exists.
MVP 3 issue drafts and GitHub issue creation exist.
The current project root contains the Portfolio Manager plugin code and tests.
The implementation follows the existing package/module naming conventions in the repository.
```

If actual module names differ from this plan, adapt names minimally while preserving behavior, tests, and safety boundaries.

---

## Runtime Root

Default runtime root:

```txt
$HOME/.agent-system
```

Root resolution order:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT
3. Path.home() / ".agent-system"
```

Do not introduce any other default root.

---

## Non-Negotiable Rules

```txt
Follow test-first development.
Preserve MVP 1–3 behavior.
Use server-side config only.
Use SQLite for runtime state.
Use local artifacts before external side effects.
Default to report-only maintenance.
Create issue drafts only when explicitly requested or configured.
Never publish GitHub issues from MVP 4 maintenance tools.
Never create worktrees in MVP 4.
Never run coding agents in MVP 4.
Never create branches, commits, PRs, comments, labels, or merges.
Never use shell=True.
Use explicit command allowlists.
Use locks for every mutation.
Use dry-run before mutation where useful.
Return blocked instead of guessing on ambiguous or unsafe inputs.
```

---

## Scope Boundary

### May mutate

```txt
$HOME/.agent-system/config/maintenance.yaml
$HOME/.agent-system/backups/
$HOME/.agent-system/state/state.sqlite
$HOME/.agent-system/artifacts/maintenance/
$HOME/.agent-system/artifacts/issues/   # only through MVP 3 issue draft helpers
```

### Must not mutate

```txt
Git repositories
Git worktrees
Git branches
GitHub issues directly
GitHub pull requests
GitHub labels
GitHub comments
GitHub projects or milestones
Provider/model budgets
Repo-local configuration files
```

---

## Shared Tool Result Format

All new tools must return:

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

Implementation note:

```txt
If existing helpers currently use status="error", either migrate them to status="failed" with regression tests or add a compatibility wrapper while keeping MVP 4 outputs documented as "failed".
```

---

## Required Tools

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

---

## Required Dev CLI Commands

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

---

## Final Design Decisions

```txt
MVP 4 includes exactly four built-in maintenance skills.
Missing maintenance.yaml is valid and uses defaults.
Enable/disable may create maintenance.yaml.
Config mutations use atomic writes, backups, and maintenance:config lock.
Dry-run does not run GitHub commands and does not write state or artifacts.
Real maintenance runs store SQLite rows and local artifacts.
Findings are deduplicated by stable fingerprints.
Draft creation is optional and local-only.
One consolidated issue draft is created per project/skill/run, not one draft per finding.
repo_guidance_docs may use gh api GET only for contents and commit metadata.
Actual recurring invocation is outside MVP 4; this MVP only provides due/run/report tools.
```

---

## Future MVPs Not Allowed Here

Do not implement:

```txt
worktree creation
repo cloning
branch creation
branch cleanup
code changes
auto-fixes
coding harness execution
PR creation
review ladder
QA merge readiness
auto-merge
provider budget routing
link checking with arbitrary HTTP fetching
security/dependency alert integration
```

---

# Final Hardening Addendum — Required Before Implementation

This addendum closes the last ambiguity gaps before handing MVP 4 to a development agent.

## A. Implement as reviewable checkpoints, not one giant change

MVP 4 is large enough that a dev agent must implement it in focused checkpoints.

Recommended checkpoint order:

```txt
Checkpoint A: schema + config + registry
Checkpoint B: built-in local-state skills + due computation
Checkpoint C: artifacts + run orchestration without drafts
Checkpoint D: optional draft integration + tools + CLI
Checkpoint E: security hardening + E2E + docs
```

Rules:

```txt
Each checkpoint must keep pytest green before moving on.
Each checkpoint must include production code and related tests together.
Do not bundle unrelated refactors with feature work.
If a refactor is needed, make it minimal and test-covered before the feature change that depends on it.
```

## B. Audit existing codebase contracts before writing MVP 4 helpers

Before creating new abstractions, inspect and reuse existing contracts for:

```txt
root resolution
shared tool result helpers
lock helper API
SQLite initialization style
atomic YAML write helper
backup naming convention
GitHub sync helper return shape
GitHub subprocess wrapper style
issue table schema and issue state enums
pull_requests table schema and PR state/review enums
issue draft helper API
issue artifact helper API
project resolver API
tool registration pattern
dev_cli command pattern
skill folder conventions
redaction helper
safe path helper
```

Rules:

```txt
Do not invent parallel systems if equivalent MVP 1–3 helpers already exist.
Do not add duplicate issue/PR state tables.
Do not add incompatible issue/PR enums unless a migration is necessary and test-covered.
Adapt MVP 4 skill logic to the actual existing issue/PR schema first.
If required fields are missing, add the smallest migration or mapper needed, with tests.
```

## C. Preserve compatibility for shared result statuses

The spec prefers:

```txt
status="failed"
```

But existing code may use:

```txt
status="error"
```

Required audit:

```txt
Search current tools/tests for status="error" and status="failed".
Identify whether MVP 1–3 callers or tests depend on "error".
```

Decision rule:

```txt
If existing MVP 1–3 behavior depends on "error", do not globally migrate in MVP 4.
Either keep MVP 4-compatible wrappers local to new tools or perform a full compatibility migration with regression tests.
```

Acceptance:

```txt
No existing user-facing tool behavior changes accidentally.
MVP 4 tools still return the documented shared result shape unless a deliberate compatibility note is added.
```

## D. No real GitHub or network calls in automated tests

Automated tests must be hermetic.

Rules:

```txt
All gh/subprocess calls must be mocked in tests.
No automated test may require GitHub auth.
No automated test may require network access.
No automated test may depend on a real repository.
Real gh calls are manual smoke tests only.
```

Acceptance:

```txt
The full pytest suite can run offline on a fresh machine with no gh auth.
```

## E. Define exact per-check outcome semantics

Use these meanings consistently:

```txt
success = check completed, even if it produced zero findings
skipped = intentionally not run because it was disabled, not due, excluded, or locked
blocked = known precondition prevents running, such as unknown project, invalid config, missing gh for a GitHub-required skill
failed = unexpected exception or command failure after the check starts
```

Rules:

```txt
A project/skill lock conflict should be skipped, not failed.
Invalid config should block the run before checks start.
A failed skill should not hide successful results from other project/skill checks.
```

## F. Add explicit rate-limit and scale guardrails

Defaults must be enforced in code and tests:

```txt
max_projects_per_run default: 20
max_findings per skill default: skill config, usually 20
repo_guidance_docs max required_files: 20
repo_guidance_docs max optional_files: 20
gh issue list timeout: 30 seconds
gh pr list timeout: 30 seconds
gh api file/commit timeout: 20 seconds per request
overall project/skill check timeout: 120 seconds unless existing timeout policy differs
```

Rules:

```txt
If a configured list exceeds limits, return blocked with a clear reason.
If max_projects is exceeded, run only selected allowed count if explicit, or block if the user asked for all and config is unsafe.
Do not silently hammer GitHub APIs.
```

## G. Expand `repo_guidance_docs` edge-case tests

Add or confirm tests for:

```txt
valid commit date parsing
empty commit response
404 missing file
403 auth/rate-limit response
private repo inaccessible
malformed gh JSON
missing default branch metadata if relevant
large required_files/optional_files lists blocked by limits
```

Acceptance:

```txt
repo_guidance_docs fails safely and never treats malformed GitHub responses as success.
```

## H. Commit source-of-truth docs before or with implementation

The dev agent should add these files to the repository before implementation or in the first documentation checkpoint:

```txt
MVP4_SPEC.md
MVP4_PROGRESS.md
```

Rules:

```txt
Do not leave the MVP 4 source of truth only in chat/canvas.
Do not mark PROJECT_HANDOFF.md as MVP 4 complete until tests and smoke checks pass.
```

---

# Phase 0 — Preflight and Regression Baseline

## 0.1 Confirm repository baseline

Status: [x]

### Test first

Run the full suite before changing code:

```bash
pytest
```

### Implementation

Do not implement anything in this task. Inspect failures only if the suite is not green.

### Verification

```bash
pytest
```

### Acceptance

```txt
All existing tests pass before MVP 4 work starts.
If tests fail, document and fix pre-existing regression before continuing.
```

---

## 0.2 Inspect actual package layout

Status: [x]

### Test first

No new test yet. This is a discovery step.

### Implementation

Inspect the repository structure and identify the actual paths for:

```txt
plugin package
tools.py
schemas.py
state.py
config helpers
GitHub client helpers
issue draft helpers
dev_cli.py
skills directory
tests directory
```

### Verification

Create a short local implementation note in the agent scratchpad, not necessarily committed, mapping the spec names to actual module names.

### Acceptance

```txt
The agent knows exactly where to add MVP 4 code.
No architecture change is made during discovery.
```

---

## 0.3 Add structure expectations as failing tests

Status: [x]

### Test first

Add or update structure tests that assert the future MVP 4 modules, skill folder, tool registrations, and CLI entries exist.

Suggested tests:

```txt
tests/test_structure.py::test_maintenance_modules_exist
tests/test_structure.py::test_portfolio_maintenance_skill_folder_exists
tests/test_structure.py::test_maintenance_tools_registered
tests/test_dev_cli.py::test_maintenance_cli_commands_registered
```

Confirm they fail for missing modules/commands.

### Implementation

Do not satisfy all tests yet. Add only minimal placeholder modules if the test runner cannot import cleanly.

### Verification

```bash
pytest tests/test_structure.py tests/test_dev_cli.py -q
```

### Acceptance

```txt
The tests fail for expected MVP 4 missing functionality, not unrelated import errors.
```

---

# Phase 1 — State, Schema, and Config Foundations

## 1.1 Add SQLite schema for maintenance runs and findings

Status: [x]

### Test first

Add tests for idempotent schema initialization:

```txt
tests/test_maintenance_runs.py::test_maintenance_tables_created_idempotently
tests/test_maintenance_runs.py::test_maintenance_run_indexes_exist
tests/test_maintenance_runs.py::test_maintenance_finding_indexes_exist
```

Confirm they fail because tables do not exist.

### Implementation

Update the existing SQLite initialization in `state.py` or equivalent to create:

```txt
maintenance_runs
maintenance_findings
```

Add indexes defined in the spec.

### Verification

```bash
pytest tests/test_maintenance_runs.py::test_maintenance_tables_created_idempotently -q
pytest tests/test_state.py -q
```

### Acceptance

```txt
Schema initialization is idempotent.
Existing MVP 1–3 state tests still pass.
No migration breaks existing tables.
```

---

## 1.2 Add maintenance state helper functions

Status: [x]

### Test first

Add tests for:

```txt
start_maintenance_run
finish_maintenance_run
get_maintenance_run
list_maintenance_runs
upsert_maintenance_finding
get_maintenance_finding
list_maintenance_findings
mark_resolved_missing_findings
```

Confirm they fail because helpers do not exist.

### Implementation

Implement helpers in `state.py` or a new `maintenance_runs.py` module, depending on existing style.

Validate run statuses:

```txt
planned
running
success
skipped
blocked
failed
```

Validate finding statuses:

```txt
open
resolved
draft_created
ignored
```

### Verification

```bash
pytest tests/test_maintenance_runs.py -q
```

### Acceptance

```txt
Helpers insert, update, query, and resolve findings correctly.
Invalid statuses raise controlled validation errors or return blocked through tool layer.
```

---

## 1.3 Add stale-running-run recovery

Status: [x]

### Test first

Add tests:

```txt
test_recover_stale_running_maintenance_runs_marks_old_runs_failed
test_recover_stale_running_maintenance_runs_leaves_recent_runs_running
```

Confirm they fail.

### Implementation

Add helper:

```python
recover_stale_maintenance_runs(conn, now, older_than_seconds) -> int
```

It should mark old `running` runs as `failed` with a redacted/simple error message.

### Verification

```bash
pytest tests/test_maintenance_runs.py -q
```

### Acceptance

```txt
Old running runs are recoverable.
Recent running runs are untouched.
No artifacts are deleted.
```

---

## 1.4 Add maintenance config loader with defaults

Status: [x]

### Test first

Add config tests:

```txt
test_missing_maintenance_yaml_uses_registry_defaults
test_invalid_yaml_blocks_validation
test_unknown_skill_id_blocks_validation
test_unknown_project_id_blocks_validation
test_project_override_wins_over_global_config
test_tool_args_override_effective_config_for_one_run_only
```

Confirm they fail.

### Implementation

Create `maintenance_config.py` or equivalent.

Implement:

```python
load_maintenance_config(root, projects_config, registry) -> MaintenanceConfig
get_effective_skill_config(project_id, skill_id, explicit_overrides=None) -> dict
```

Missing config should be valid.

### Verification

```bash
pytest tests/test_maintenance_config.py -q
```

### Acceptance

```txt
Missing maintenance.yaml works.
Invalid maintenance.yaml blocks with clear errors.
Effective config resolution follows spec order.
```

---

## 1.5 Add maintenance config mutation helpers

Status: [x]

### Test first

Add tests:

```txt
test_enable_creates_maintenance_yaml_when_missing
test_disable_creates_maintenance_yaml_when_missing
test_existing_config_gets_timestamped_backup
test_atomic_write_preserves_original_on_failure
test_unknown_top_level_fields_preserved
test_interval_hours_bounds_enforced
test_config_lock_required_for_mutation
```

Confirm they fail.

### Implementation

Implement helpers:

```python
enable_maintenance_skill(...)
disable_maintenance_skill(...)
write_maintenance_config_atomic(...)
backup_maintenance_config(...)
```

Use existing lock helpers if present. Lock name:

```txt
maintenance:config
```

### Verification

```bash
pytest tests/test_maintenance_config.py -q
```

### Acceptance

```txt
Config mutation is atomic, backed up, locked, and preserves unknown allowed extension fields.
```

---

# Phase 2 — Maintenance Models, Registry, and Built-In Pure Logic

## 2.1 Add maintenance data models

Status: [x]

### Test first

Add tests that construct and validate:

```txt
MaintenanceSkillSpec
MaintenanceContext
MaintenanceFinding
MaintenanceSkillResult
```

Include invalid severity/status cases.

### Implementation

Create `maintenance_models.py` or equivalent.

Use dataclasses, Pydantic models, or the repository’s existing model style. Keep validation deterministic.

### Verification

```bash
pytest tests/test_maintenance_registry.py -q
```

### Acceptance

```txt
Models are importable and validate required fields.
Invalid severity/status values are rejected.
```

---

## 2.2 Add maintenance registry

Status: [x]

### Test first

Add tests:

```txt
test_all_builtin_skills_registered
test_skill_ids_match_regex
test_unknown_skill_id_returns_none_or_controlled_error
test_registry_lists_skill_specs
test_each_skill_declares_allowed_commands
```

Confirm they fail.

### Implementation

Create `maintenance_registry.py`.

Register exactly:

```txt
untriaged_issue_digest
stale_issue_digest
open_pr_health
repo_guidance_docs
```

Do not implement dynamic third-party skill loading in MVP 4.

### Verification

```bash
pytest tests/test_maintenance_registry.py -q
```

### Acceptance

```txt
Built-in skills are discoverable.
Unknown skills are controlled blocked cases at tool layer.
No arbitrary code loading exists.
```

---

## 2.3 Implement stable finding fingerprints

Status: [x]

### Test first

Add tests:

```txt
test_finding_fingerprint_stable_across_runs
test_finding_fingerprint_normalizes_whitespace_and_case
test_finding_fingerprint_ignores_volatile_timestamp_text
test_different_source_ids_produce_different_fingerprints
```

Confirm they fail.

### Implementation

Implement fingerprint helper:

```python
make_finding_fingerprint(project_id, skill_id, source_type, source_id, title) -> str
```

Use SHA-256 and normalization defined in the spec.

### Verification

```bash
pytest tests/test_maintenance_registry.py::test_finding_fingerprint_stable_across_runs -q
```

### Acceptance

```txt
Repeated runs produce stable fingerprints.
Different real findings remain distinct.
```

---

## 2.4 Implement `untriaged_issue_digest` pure logic

Status: [x]

### Test first

Add tests with seeded local issue rows:

```txt
test_untriaged_issue_digest_finds_old_needs_triage_issues
test_untriaged_issue_digest_ignores_recent_issues
test_untriaged_issue_digest_ignores_non_triage_issues
test_untriaged_issue_digest_respects_max_findings
test_untriaged_issue_digest_severity_medium_after_14_days
```

Confirm they fail.

### Implementation

Implement the skill using local SQLite issue state only.

### Verification

```bash
pytest tests/test_maintenance_builtin.py::test_untriaged_issue_digest_finds_old_needs_triage_issues -q
pytest tests/test_maintenance_builtin.py -q
```

### Acceptance

```txt
The skill returns deterministic findings and summary.
No GitHub command is used.
```

---

## 2.5 Implement `stale_issue_digest` pure logic

Status: [x]

### Test first

Add tests:

```txt
test_stale_issue_digest_finds_old_open_issues
test_stale_issue_digest_ignores_recent_issues
test_stale_issue_digest_respects_stale_after_days
test_stale_issue_digest_respects_max_findings
test_stale_issue_digest_severity_medium_after_double_threshold
```

Confirm they fail.

### Implementation

Implement the skill using local SQLite issue state only.

### Verification

```bash
pytest tests/test_maintenance_builtin.py -q
```

### Acceptance

```txt
Stale issues are found deterministically.
Thresholds are config-driven and tested.
```

---

## 2.6 Implement `open_pr_health` pure logic

Status: [x]

### Test first

Add tests:

```txt
test_open_pr_health_finds_checks_failed
test_open_pr_health_finds_changes_requested
test_open_pr_health_finds_old_review_pending
test_open_pr_health_ignores_recent_healthy_prs
test_open_pr_health_respects_config_flags
test_open_pr_health_respects_max_findings
```

Confirm they fail.

### Implementation

Implement the skill using local SQLite PR state only.

### Verification

```bash
pytest tests/test_maintenance_builtin.py -q
```

### Acceptance

```txt
PR health findings are deterministic.
Severity matches spec.
Config flags are honored.
```

---

## 2.7 Implement `repo_guidance_docs` with mocked GitHub GET only

Status: [x]

### Test first

Add tests with mocked subprocess/GitHub client:

```txt
test_repo_guidance_docs_detects_missing_required_file
test_repo_guidance_docs_detects_stale_required_file
test_repo_guidance_docs_reports_optional_missing_as_info
test_repo_guidance_docs_blocks_when_gh_unavailable
test_repo_guidance_docs_uses_only_gh_api_get
test_repo_guidance_docs_rejects_unsafe_paths
```

Confirm they fail.

### Implementation

Implement guidance doc inspection through a small helper that uses only:

```txt
gh api --method GET repos/OWNER/REPO/contents/PATH
gh api --method GET repos/OWNER/REPO/commits?path=PATH&per_page=1
```

Do not run this helper in dry-run.

### Verification

```bash
pytest tests/test_maintenance_builtin.py::test_repo_guidance_docs_detects_missing_required_file -q
pytest tests/test_security.py -q
```

### Acceptance

```txt
Guidance doc skill works with mocked gh responses.
Unsafe paths are rejected.
Only GET commands are possible.
```

---

# Phase 3 — Artifact Safety and Report Generation

## 3.1 Add maintenance artifact path helpers

Status: [x]

### Test first

Add tests:

```txt
test_maintenance_artifact_dir_under_root
test_run_id_path_traversal_rejected
test_artifact_paths_created_for_run_id
test_artifact_write_redacts_secrets
```

Confirm they fail.

### Implementation

Create `maintenance_artifacts.py`.

Implement contained paths under:

```txt
$HOME/.agent-system/artifacts/maintenance/<run_id>/
```

### Verification

```bash
pytest tests/test_maintenance_artifacts.py -q
```

### Acceptance

```txt
Artifact helpers cannot write outside the runtime root.
Secrets are redacted.
```

---

## 3.2 Write `report.md`, `findings.json`, and `metadata.json`

Status: [x]

### Test first

Add tests:

```txt
test_report_md_contains_required_sections
test_findings_json_contains_required_fields
test_metadata_json_contains_selected_projects_and_skills
test_artifact_json_is_valid_and_stable
```

Confirm they fail.

### Implementation

Implement report writers:

```python
write_maintenance_report(...)
write_findings_json(...)
write_metadata_json(...)
```

Keep report concise and human-readable.

### Verification

```bash
pytest tests/test_maintenance_artifacts.py -q
```

### Acceptance

```txt
Reports are useful in chat and inspectable on disk.
JSON files are valid and deterministic enough for tests.
```

---

## 3.3 Add planned, refresh, draft, and error artifact writers

Status: [x]

### Test first

Add tests:

```txt
test_planned_checks_json_shape
test_github_refresh_json_shape
test_draft_created_json_shape
test_error_json_redacts_secret_values
```

Confirm they fail.

### Implementation

Implement writers for:

```txt
planned-checks.json
github-refresh.json
draft-created.json
error.json
```

### Verification

```bash
pytest tests/test_maintenance_artifacts.py -q
```

### Acceptance

```txt
All required artifact files can be written safely.
Errors never expose secrets.
```

---

# Phase 4 — Due Computation and Run Orchestration

## 4.1 Implement due computation

Status: [x]

### Test first

Add tests:

```txt
test_never_run_skill_is_due
test_recent_successful_run_is_not_due
test_old_successful_run_is_due
test_disabled_skill_is_not_due
test_paused_and_archived_projects_excluded_by_default
test_include_paused_and_include_archived_flags_work
test_project_filter_works
test_skill_filter_works
```

Confirm they fail.

### Implementation

Implement `maintenance_due.py` or equivalent.

Due formula:

```txt
Due if enabled and no previous successful run exists.
Due if enabled and now >= latest_successful_finished_at + interval_hours.
Not due otherwise.
```

### Verification

```bash
pytest tests/test_maintenance_due.py -q
```

### Acceptance

```txt
Due computation is deterministic and independent of Hermes.
```

---

## 4.2 Implement dry-run planning

Status: [x]

### Test first

Add tests:

```txt
test_dry_run_returns_planned_checks
test_dry_run_does_not_insert_runs
test_dry_run_does_not_write_artifacts
test_dry_run_does_not_run_github_commands
test_dry_run_reports_would_create_issue_drafts
```

Confirm they fail.

### Implementation

Implement planning layer used by `portfolio_maintenance_run --dry-run true`.

It should validate config/projects/skills and return planned checks only.

### Verification

```bash
pytest tests/test_maintenance_runs.py::test_dry_run_returns_planned_checks -q
```

### Acceptance

```txt
Dry-run has zero side effects and gives a useful preview.
```

---

## 4.3 Implement real run orchestration without drafts

Status: [x]

### Test first

Add tests:

```txt
test_real_run_starts_and_finishes_run_rows
test_real_run_upserts_findings
test_real_run_marks_missing_findings_resolved
test_real_run_writes_report_artifacts
test_real_run_continues_after_one_skill_failure
test_global_run_lock_blocks_concurrent_runs
test_project_skill_lock_skips_locked_item
```

Confirm they fail.

### Implementation

Create `maintenance_runs.py` orchestration function:

```python
run_maintenance(...)
```

Behavior:

```txt
recover stale runs
acquire maintenance:run
resolve selected projects/skills
for each selected check, acquire project/skill lock
optionally refresh GitHub using existing read-only sync helper
run skill
persist run and findings
write artifacts
release locks
```

Do not implement draft creation in this task.

### Verification

```bash
pytest tests/test_maintenance_runs.py -q
pytest tests/test_maintenance_artifacts.py -q
```

### Acceptance

```txt
Real runs store state and artifacts.
Locking behavior is tested.
Failures are controlled and do not stop unrelated checks.
```

---

## 4.4 Integrate optional read-only GitHub refresh

Status: [x]

### Test first

Add tests:

```txt
test_refresh_github_true_calls_existing_sync_helper
test_refresh_github_false_skips_sync_helper
test_gh_unavailable_local_state_skills_continue_with_warning
test_gh_unavailable_repo_guidance_docs_blocks
test_github_refresh_summary_artifact_written
```

Confirm they fail.

### Implementation

Use existing MVP 1 GitHub sync helpers for issues/PRs.

Rules:

```txt
Local-state skills can run from existing SQLite state if refresh fails.
repo_guidance_docs blocks if GitHub access is unavailable.
Refresh errors are warnings unless the selected skill requires GitHub API.
```

### Verification

```bash
pytest tests/test_maintenance_runs.py::test_refresh_github_true_calls_existing_sync_helper -q
```

### Acceptance

```txt
Maintenance uses current GitHub data when possible but fails safely when unavailable.
```

---

# Phase 5 — Local Issue Draft Integration

## 5.1 Add draft planning rules

Status: [x]

### Test first

Add tests:

```txt
test_create_issue_drafts_false_creates_no_drafts
test_create_issue_drafts_true_requires_skill_support
test_non_draftable_findings_are_ignored_for_drafts
test_existing_finding_with_issue_draft_id_does_not_duplicate
test_one_draft_per_project_skill_run
```

Confirm they fail.

### Implementation

Implement draft planning helper:

```python
plan_maintenance_issue_drafts(findings_by_project_skill_run) -> list[DraftPlan]
```

Do not call MVP 3 helpers yet.

### Verification

```bash
pytest tests/test_maintenance_drafts.py -q
```

### Acceptance

```txt
Draft creation rules are deterministic before side effects are added.
```

---

## 5.2 Create local issue drafts through MVP 3 helpers

Status: [x]

### Test first

Add tests with mocked MVP 3 draft helper:

```txt
test_draft_creation_uses_existing_issue_draft_helper
test_draft_body_has_goal_findings_acceptance_and_run_id
test_draft_body_excludes_private_metadata_and_cot
test_draft_creation_failure_records_warning
test_draft_created_updates_finding_issue_draft_id
test_draft_created_artifact_written
```

Confirm they fail.

### Implementation

Integrate with existing MVP 3 local draft creation only.

Never call:

```txt
gh issue create
portfolio_issue_create
portfolio_issue_create_from_draft with confirm=true
```

### Verification

```bash
pytest tests/test_maintenance_drafts.py -q
pytest tests/test_issue_drafts.py -q
```

### Acceptance

```txt
Maintenance can create local drafts only.
No GitHub issue is created.
Failures do not lose findings.
```

---

## 5.3 Add repair behavior for partial draft creation

Status: [x]

### Test first

Add tests:

```txt
test_repair_draft_created_artifact_updates_missing_sqlite_reference
test_repair_ignores_missing_or_invalid_draft_artifact
test_repair_does_not_duplicate_existing_draft_reference
```

Confirm they fail.

### Implementation

At the start or end of a run, detect `draft-created.json` entries that refer to findings missing `issue_draft_id` and repair SQLite state if safe.

### Verification

```bash
pytest tests/test_maintenance_drafts.py -q
```

### Acceptance

```txt
Crash recovery can repair successful draft creation where SQLite update failed.
```

---

# Phase 6 — Tool Schemas and Handlers

## 6.1 Add tool schemas

Status: [x]

### Test first

Add schema tests:

```txt
test_maintenance_skill_list_schema_defaults
test_maintenance_skill_explain_requires_skill_id
test_maintenance_skill_enable_validates_interval_bounds
test_maintenance_run_schema_defaults
test_maintenance_report_schema_defaults
test_config_json_must_be_object
```

Confirm they fail.

### Implementation

Add Pydantic/dataclass schemas following existing `schemas.py` style.

Input schemas:

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

### Verification

```bash
pytest tests/test_maintenance_tools.py::test_maintenance_skill_list_schema_defaults -q
```

### Acceptance

```txt
Tool inputs validate safely before logic runs.
Defaults match the spec.
```

---

## 6.2 Implement list and explain tools

Status: [x]

### Test first

Add tests:

```txt
test_skill_list_works_with_missing_config
test_skill_list_can_hide_disabled_skills
test_skill_explain_returns_registry_and_effective_config
test_skill_explain_blocks_unknown_skill
test_skill_explain_blocks_unknown_project
```

Confirm they fail.

### Implementation

Implement:

```txt
portfolio_maintenance_skill_list
portfolio_maintenance_skill_explain
```

Handlers should be thin wrappers over registry/config helpers.

### Verification

```bash
pytest tests/test_maintenance_tools.py -q
```

### Acceptance

```txt
The user can see and understand available maintenance skills.
```

---

## 6.3 Implement enable and disable tools

Status: [x]

### Test first

Add tests:

```txt
test_skill_enable_writes_config
test_skill_enable_respects_project_override
test_skill_enable_blocks_unknown_skill
test_skill_enable_blocks_unknown_project
test_skill_disable_writes_config
test_skill_disable_uses_config_lock
test_skill_enable_returns_effective_config
```

Confirm they fail.

### Implementation

Implement:

```txt
portfolio_maintenance_skill_enable
portfolio_maintenance_skill_disable
```

Use config mutation helpers and return the shared result format.

### Verification

```bash
pytest tests/test_maintenance_tools.py -q
pytest tests/test_maintenance_config.py -q
```

### Acceptance

```txt
The user can safely configure maintenance checks.
Config mutation is locked, atomic, and backed up.
```

---

## 6.4 Implement due tool

Status: [x]

### Test first

Add tests:

```txt
test_maintenance_due_tool_returns_due_not_due_disabled_counts
test_maintenance_due_tool_filters_project_and_skill
test_maintenance_due_tool_blocks_invalid_project
test_maintenance_due_tool_blocks_invalid_skill
```

Confirm they fail.

### Implementation

Implement:

```txt
portfolio_maintenance_due
```

Use due computation helper.

### Verification

```bash
pytest tests/test_maintenance_tools.py::test_maintenance_due_tool_returns_due_not_due_disabled_counts -q
```

### Acceptance

```txt
The user can safely preview due maintenance work.
```

---

## 6.5 Implement run tools

Status: [x]

### Test first

Add tests:

```txt
test_maintenance_run_dry_run_has_no_side_effects
test_maintenance_run_real_run_stores_report
test_maintenance_run_with_create_drafts_creates_local_drafts_only
test_maintenance_run_blocks_unknown_skill
test_maintenance_run_respects_max_projects
test_maintenance_run_project_resolves_project_ref
test_maintenance_run_project_blocks_ambiguous_project_ref
```

Confirm they fail.

### Implementation

Implement:

```txt
portfolio_maintenance_run
portfolio_maintenance_run_project
```

Use MVP 3 project resolver for `project_ref`.

### Verification

```bash
pytest tests/test_maintenance_tools.py -q
pytest tests/test_maintenance_runs.py -q
```

### Acceptance

```txt
Maintenance can be run broadly or per-project.
Project ambiguity blocks instead of guessing.
```

---

## 6.6 Implement report tool

Status: [x]

### Test first

Add tests:

```txt
test_maintenance_report_returns_latest_run
test_maintenance_report_returns_selected_run
test_maintenance_report_filters_by_project_skill_severity
test_maintenance_report_blocks_unknown_run
test_maintenance_report_blocks_invalid_filter_enum
```

Confirm they fail.

### Implementation

Implement:

```txt
portfolio_maintenance_report
```

Keep summaries concise enough for Hermes/Telegram.

### Verification

```bash
pytest tests/test_maintenance_tools.py::test_maintenance_report_returns_latest_run -q
```

### Acceptance

```txt
The user can review recent maintenance results from chat.
```

---

# Phase 7 — Dev CLI Support

## 7.1 Add CLI parser entries for all maintenance tools

Status: [x]

### Test first

Add tests:

```txt
test_cli_registers_maintenance_skill_list
test_cli_registers_maintenance_skill_explain
test_cli_registers_maintenance_skill_enable
test_cli_registers_maintenance_skill_disable
test_cli_registers_maintenance_due
test_cli_registers_maintenance_run
test_cli_registers_maintenance_run_project
test_cli_registers_maintenance_report
```

Confirm they fail.

### Implementation

Update `dev_cli.py` using existing command patterns.

Add flags:

```txt
--skill-id
--project-id
--project-ref
--interval-hours
--config-json
--include-disabled
--include-project-overrides
--include-paused
--include-archived
--include-not-due
--refresh-github
--create-issue-drafts
--dry-run
--max-projects
--run-id
--severity
--limit
--include-resolved
```

### Verification

```bash
pytest tests/test_maintenance_cli.py -q
```

### Acceptance

```txt
All MVP 4 tools are callable outside Hermes.
```

---

## 7.2 Add CLI behavior tests with test root

Status: [x]

### Test first

Add tests that call CLI entrypoints or parser functions for:

```txt
portfolio_maintenance_skill_list
portfolio_maintenance_skill_explain
portfolio_maintenance_skill_enable
portfolio_maintenance_due
portfolio_maintenance_run --dry-run true
portfolio_maintenance_report
```

Confirm they fail.

### Implementation

Wire CLI commands to tool handlers.

Ensure JSON output works and boolean parsing reuses existing `_to_bool` behavior.

### Verification

```bash
pytest tests/test_maintenance_cli.py -q
```

Manual CLI smoke:

```bash
python dev_cli.py portfolio_maintenance_skill_list --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --dry-run true --root /tmp/agent-system-test --json
```

### Acceptance

```txt
CLI commands return valid JSON shared result shapes.
```

---

# Phase 8 — Hermes Skill Documentation

## 8.1 Add `portfolio-maintenance` skill folder

Status: [x]

### Test first

Add tests:

```txt
test_portfolio_maintenance_skill_md_exists
test_portfolio_maintenance_skill_mentions_report_only_default
test_portfolio_maintenance_skill_warns_no_auto_fixes
test_portfolio_maintenance_skill_lists_expected_tools
```

Confirm they fail.

### Implementation

Create:

```txt
skills/portfolio-maintenance/SKILL.md
```

Include guidance:

```txt
Use due before broad runs.
Prefer dry-run first.
Default to reports.
Create local drafts only when requested.
Never promise GitHub issue publishing, fixes, PRs, or merges.
```

### Verification

```bash
pytest tests/test_maintenance_skills.py -q
```

### Acceptance

```txt
Hermes has clear instructions for safe maintenance workflows.
```

---

## 8.2 Add Hermes-style examples

Status: [x]

### Test first

Add tests or static checks that required example phrases exist.

Examples:

```txt
List maintenance skills.
Explain stale issue checks.
Show checks due now.
Dry-run maintenance.
Run maintenance and report findings.
Run project-specific maintenance and create local drafts.
Show latest maintenance report.
```

Confirm they fail if examples are missing.

### Implementation

Update the skill file with concise example flows and tool-use guidance.

### Verification

```bash
pytest tests/test_maintenance_skills.py -q
```

### Acceptance

```txt
A Hermes agent can choose the correct MVP 4 tools safely.
```

---

# Phase 9 — Security Hardening

## 9.1 Add command allowlist tests

Status: [x]

### Test first

Add tests:

```txt
test_no_shell_true_in_maintenance_code
test_only_allowed_gh_commands_in_maintenance_code
test_no_gh_issue_create_in_maintenance_code
test_no_gh_pr_mutation_in_maintenance_code
test_no_gh_api_mutation_methods_in_maintenance_code
```

Confirm at least some fail until implementation is hardened.

### Implementation

Centralize subprocess calls in a safe helper if not already present.

Ensure allowed commands are checked before execution.

Allowed only:

```txt
gh --version
gh auth status
gh issue list
gh pr list
gh api --method GET repos/OWNER/REPO/contents/PATH
gh api --method GET repos/OWNER/REPO/commits?path=PATH&per_page=1
```

### Verification

```bash
pytest tests/test_security.py -q
```

### Acceptance

```txt
Security tests prove MVP 4 cannot run forbidden GitHub or git commands.
```

---

## 9.2 Add path containment and traversal tests

Status: [x]

### Test first

Add tests:

```txt
test_maintenance_config_path_contained
test_maintenance_artifact_path_contained
test_guidance_doc_rejects_dotdot
test_guidance_doc_rejects_absolute_path
test_guidance_doc_rejects_url_scheme
test_guidance_doc_rejects_shell_metacharacters
```

Confirm they fail.

### Implementation

Use existing safe path helpers where available.

Add guidance doc path validator:

```python
validate_repo_relative_posix_path(path: str) -> str
```

### Verification

```bash
pytest tests/test_security.py tests/test_maintenance_artifacts.py -q
```

### Acceptance

```txt
MVP 4 cannot escape runtime root or pass unsafe paths to gh api.
```

---

## 9.3 Add privacy and redaction tests

Status: [x]

### Test first

Add tests:

```txt
test_error_artifact_redacts_tokens
test_report_does_not_include_environment_variables
test_maintenance_draft_excludes_private_metadata
test_maintenance_outputs_do_not_include_chain_of_thought_label_or_private_scratchpad
```

Confirm they fail if current output is unsafe.

### Implementation

Use existing redaction helper or add one consistent with prior MVPs.

Never write raw auth output, env vars, tokens, or private model reasoning to artifacts.

### Verification

```bash
pytest tests/test_security.py tests/test_maintenance_artifacts.py tests/test_maintenance_drafts.py -q
```

### Acceptance

```txt
Maintenance reports, artifacts, and drafts are public-safe except for local file paths/run IDs.
```

---

# Phase 10 — Local E2E and Regression

## 10.1 E2E: dry-run with seeded test root

Status: [x]

### Test first

Add e2e test:

```txt
test_e2e_maintenance_dry_run_has_no_side_effects
```

Seed:

```txt
projects.yaml with one active test project
SQLite issue/PR rows
maintenance defaults or config
```

Confirm it fails.

### Implementation

Fix orchestration/tool integration until dry-run returns planned checks without side effects.

### Verification

```bash
pytest tests/test_maintenance_e2e.py::test_e2e_maintenance_dry_run_has_no_side_effects -q
```

### Acceptance

```txt
Dry-run creates no SQLite run rows, no artifacts, no drafts, and no GitHub commands.
```

---

## 10.2 E2E: real run stores findings and report

Status: [x]

### Test first

Add e2e test:

```txt
test_e2e_maintenance_real_run_stores_findings_and_report
```

Confirm it fails.

### Implementation

Fix state/artifact integration until the real run works using seeded local state and `refresh_github=false`.

### Verification

```bash
pytest tests/test_maintenance_e2e.py::test_e2e_maintenance_real_run_stores_findings_and_report -q
```

### Acceptance

```txt
A real run creates one run row, expected findings, and report artifacts.
```

---

## 10.3 E2E: local draft creation only

Status: [x]

### Test first

Add e2e test:

```txt
test_e2e_maintenance_create_issue_drafts_creates_local_draft_only
```

Confirm it fails.

### Implementation

Fix draft integration until local issue draft artifacts are created through MVP 3 helpers.

### Verification

```bash
pytest tests/test_maintenance_e2e.py::test_e2e_maintenance_create_issue_drafts_creates_local_draft_only -q
```

### Acceptance

```txt
A local draft exists.
No GitHub issue creation command was called.
Findings reference the local draft ID.
```

---

## 10.4 E2E: repeated run dedupes and resolves findings

Status: [x]

### Test first

Add tests:

```txt
test_e2e_repeated_run_updates_same_findings
test_e2e_missing_finding_marked_resolved_after_successful_run
```

Confirm they fail.

### Implementation

Fix fingerprint/upsert/resolution logic.

### Verification

```bash
pytest tests/test_maintenance_e2e.py -q
```

### Acceptance

```txt
Repeated runs do not duplicate findings.
Findings disappear cleanly when resolved.
```

---

## 10.5 Full regression suite

Status: [x]

### Test first

Run the full suite.

### Implementation

Fix any regressions in MVP 1–3 behavior or MVP 4 integration.

### Verification

```bash
pytest
```

### Acceptance

```txt
All tests pass.
No existing MVP behavior is broken.
```

---

# Phase 11 — Manual CLI and Hermes Smoke Tests

## 11.1 Manual CLI smoke with test root

Status: [ ]

### Test first

Automated CLI tests should already pass before this task.

### Implementation

Run these commands against a safe test root:

```bash
python dev_cli.py portfolio_maintenance_skill_list --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_explain --skill-id stale_issue_digest --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_enable --skill-id stale_issue_digest --interval-hours 168 --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_due --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --skill-id stale_issue_digest --refresh-github false --create-issue-drafts false --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_report --root /tmp/agent-system-test --json
```

### Verification

Inspect JSON output and local artifacts.

### Acceptance

```txt
All commands return valid shared result objects.
Real run writes expected local report artifacts.
No forbidden side effects occur.
```

---

## 11.2 Manual Hermes smoke

Status: [ ]

### Test first

Automated tests and CLI smoke must pass first.

### Implementation

Run from Hermes/Telegram-style interface:

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

### Verification

Confirm outputs are concise and safe.

### Acceptance

```txt
Hermes selects the correct tools.
The user-facing summaries are clear.
No direct GitHub issue creation, PR creation, worktree creation, or repo mutation occurs.
```

---

## 11.3 Update documentation and handoff status

Status: [ ]

### Test first

No code test required, but final `pytest` must already pass.

### Implementation

Update repository docs as appropriate:

```txt
Add MVP4_SPEC.md if not already committed.
Add MVP4_PROGRESS.md.
Update PROJECT_HANDOFF.md status table only after implementation is verified.
Mention MVP 4 completion criteria and smoke-test notes.
```

Do not mark MVP 4 complete until automated and manual checks pass.

### Verification

```bash
pytest
```

Review docs diff.

### Acceptance

```txt
Docs accurately reflect implementation status.
Future agents know MVP 4 is implemented only if tests and smoke checks passed.
```

---

# Definition of Done

MVP 4 is complete when:

```txt
All MVP 1–3 tests still pass.
All MVP 4 tests pass.
All eight maintenance tools are available through Hermes and dev_cli.py.
maintenance.yaml can be loaded, enabled, disabled, backed up, and written atomically.
Due computation works across active projects and enabled skills.
The four built-in maintenance skills produce deterministic findings.
Dry-run performs no mutations and no GitHub commands.
Real runs write SQLite rows and local maintenance artifacts.
Optional issue draft creation creates local MVP 3 drafts only.
Repeated runs dedupe findings.
Resolved findings are marked resolved.
Security tests prove no forbidden commands, no shell=True, safe paths, and redaction.
Manual CLI smoke passes.
Manual Hermes smoke passes.
PROJECT_HANDOFF.md is updated only after verification.
```

---

# Suggested Implementation Order

Use this exact order unless a failing test reveals a dependency issue:

```txt
0. Baseline pytest and repository inspection
1. Structure tests
2. SQLite schema and state helpers
3. Maintenance config load/mutate helpers
4. Models and registry
5. Fingerprint helper
6. Built-in local-state skills
7. repo_guidance_docs with mocked gh GET
8. Artifact writers
9. Due computation
10. Dry-run planner
11. Real run orchestration without drafts
12. Optional GitHub refresh integration
13. Draft planning
14. Local draft creation through MVP 3 helpers
15. Tool schemas
16. Tool handlers
17. Dev CLI
18. Hermes skill docs
19. Security hardening
20. E2E tests
21. Full pytest
22. Manual CLI smoke
23. Manual Hermes smoke
24. Documentation update
```

---

# Implementation Notes for Dev Agent

## Keep handlers thin

Tool handlers should only:

```txt
validate input
load config/state
call tested helpers
return shared result objects
```

Core behavior belongs in pure/helper modules.

## Prefer controlled outcomes

Use:

```txt
blocked
skipped
failed
```

rather than uncaught exceptions in user-facing tools.

## Be strict with commands

Every subprocess call added for MVP 4 must have:

```txt
argument array
timeout
allowlist validation
no shell=True
redacted errors
unit tests
```

## Do not overbuild scheduling

MVP 4 has due computation and run commands. It does not need a scheduler engine. Hermes heartbeats or future MVPs can call these tools later.

## Do not overbuild dynamic skills

MVP 4 has a registry and four built-in skills. Do not add arbitrary plugin loading or user-provided Python execution.

## Do not publish maintenance findings

Maintenance findings can become local issue drafts. Publishing to GitHub remains an explicit MVP 3 issue-creation flow and should require the user’s separate confirmation.
