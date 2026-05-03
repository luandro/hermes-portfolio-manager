# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 6: Implementation Harness Orchestration

## Goal

Implement MVP 6: confirmed, test-first implementation jobs that run a configured coding harness inside a clean MVP 5 issue worktree, write artifacts, and create a local commit when checks pass.

The final system must let Hermes:

1. Plan an implementation job for an issue (read-only).
2. Run an `initial_implementation` job after explicit user confirmation.
3. Run a `review_fix` job invoked by MVP 7 (later) using the same job interface.
4. Inspect job state, list jobs, and explain blockers.

It must not push branches, open/merge PRs, run review ladders, auto-start from cron, mutate worktrees outside the harness's own changes, or call paid providers without explicit policy.

Source of truth: `docs/mvps/mvp6-spec.md`. Read it before starting any task. This file scopes the spec into ordered, test-first tasks with difficulty levels so an orchestrator can route each task to an appropriately-sized model.

---

## Difficulty Legend

```txt
L1 — easy / mechanical. Single-file edits, schema additions, CLI parser entries, doc files,
     fixed-shape tests. Low blast radius. Suitable for haiku-class models.

L2 — medium / scoped logic. New helpers + tests, multi-file changes, integration with
     existing modules. Moderate safety surface. Suitable for sonnet-class models.

L3 — hard / safety-critical. Subprocess + git mutation orchestration, lock+idempotency
     state machines, security boundaries (path containment, command allowlists, redaction,
     scope guard, test-quality), crash recovery, E2E flows. Suitable for opus-class models.
```

Rule of thumb: if the task can corrupt local state, escape `$ROOT/worktrees/<project>-issue-<n>`, run a forbidden command, leak a secret, or create a wrong commit → L3.

---

## Agent-Readiness Verdict

Ready for a development agent **only after** MVP 5 is confirmed green.

Before implementing this file, the agent must run:

```bash
pytest
```

If MVP 1–5 tests fail, fix the regression first. Do not start MVP 6 on a failing baseline.

Existing assumptions to honor:

```txt
Source layout is flat under portfolio_manager/ (matches existing maintenance_*.py and worktree_*.py modules).
Tests live under tests/ as test_<area>.py.
Skills live under skills/<skill-name>/SKILL.md.
Config root resolution: explicit arg > AGENT_SYSTEM_ROOT > Path.home() / ".agent-system".
Locks use state.acquire_lock / release_lock; mirror the worktree_locks.py shape.
Tool result shape uses status="success"|"skipped"|"blocked"|"failed"; MVP 6 also permits
  status="needs_user" for implementation jobs that require product judgment.
Issue specs live at $ROOT/artifacts/issues/<project_id>/<draft_id>/ (MVP 3 layout) — REUSE issue_artifact_root.
Worktree probes (worktree_git.run_git, get_clean_state, list_worktrees, get_origin_url, branch_exists)
  exist in portfolio_manager/worktree_git.py — REUSE; do not re-implement subprocess wrappers.
Worktree inspection lives in portfolio_manager/worktree.py::inspect_worktree — REUSE for preflight state checks.
The shared redaction helper lives in portfolio_manager/errors.py::redact_secrets and
  maintenance_artifacts redactor — REUSE in artifact writers.
Tools register in portfolio_manager/__init__.py::_TOOL_REGISTRY.
```

---

## Non-Negotiable Rules

```txt
Test-first. Every task adds failing tests first, then implementation.
Preserve MVP 1–5 behavior.
shell=True is forbidden. Every subprocess call uses argument arrays + timeout + GIT_TERMINAL_PROMPT=0.
Every harness invocation goes through harness_runner with explicit allowlisted command + timeout +
  cwd=issue_worktree_path + redacted env passthrough.
The harness runs only inside the prepared issue worktree path resolved via worktree_state.
Default mutating tools to confirm=false. Real run requires confirm=true AND all preflight checks pass.
Plan / dry-run writes no SQLite implementation_jobs row and no implementation artifacts.
Real runs write SQLite + artifacts; artifacts redact secrets + harness env values + chain-of-thought.
Locks are always released in finally blocks. Lock contention returns blocked, not failed.
The job must refuse to run on a dirty worktree, mismatched branch, or missing source artifact.
Local commits are allowed only after the configured checks pass AND scope guard + test-quality pass.
Never push, open PRs, merge, run review ladders, decide review pass/fail, classify PR comments,
  or call any gh subcommand that mutates remote state.
Never create, refresh, clean, reset, stash, or delete worktrees from MVP 6 (use MVP 5 only).
Review-fix jobs apply only the approved comment IDs handed in by MVP 7. No re-classification.
```

---

## Scope Boundary

### May mutate

```txt
$ROOT/state/state.sqlite                                   (implementation_jobs rows + locks rows)
$ROOT/artifacts/implementations/<project_id>/issue-<n>/<job_id>/    (audit artifacts)
$ROOT/worktrees/<project_id>-issue-<n>/                    (only via the harness subprocess + a single
                                                            git commit at the end; no direct file writes
                                                            from MVP 6 modules)
```

### Must not mutate

```txt
GitHub remote state of any kind
$ROOT/worktrees/<project_id>/                              (the base repo; MVP 5 owns it)
$ROOT/config/projects.yaml                                 (project config; MVP 2 owns it)
$ROOT/config/maintenance.yaml                              (MVP 4 owns it)
issue draft artifacts                                      (MVP 3 owns them)
worktree state outside the issue worktree (no clean / reset / stash / push / commit-amend)
```

---

## Shared Tool Result Format

```python
{
    "status": "success" | "skipped" | "blocked" | "failed" | "needs_user",
    "tool": "tool_name",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None,
}
```

`blocked` is preferred over guessing on ambiguity. `needs_user` is for explicit product-judgment
requests from a harness job. `failed` is for unexpected exceptions after mutation started.

---

## Required New Tools

```txt
portfolio_implementation_plan                  (read-only)
portfolio_implementation_start                 (initial_implementation job)
portfolio_implementation_apply_review_fixes    (review_fix job, MVP 7 will call this)
portfolio_implementation_status                (lookup by job_id or by project+issue)
portfolio_implementation_list                  (filter by project/issue/status)
portfolio_implementation_explain               (why blocked / needs_user)
```

`qa_fix` job_type is reserved. MVP 6 stores the enum but provides no qa_fix orchestrator.

---

## Required Dev CLI Commands

```bash
python dev_cli.py implementation-plan          --project-ref <p> --issue-number 42 --harness-id forge --root /tmp/agent-system-test --json
python dev_cli.py implementation-start         --project-ref <p> --issue-number 42 --harness-id forge --confirm false --root /tmp/agent-system-test --json
python dev_cli.py implementation-start         --project-ref <p> --issue-number 42 --harness-id forge --confirm true  --root /tmp/agent-system-test --json
python dev_cli.py implementation-apply-review-fixes --project-ref <p> --issue-number 42 --pr-number 130 --review-stage-id stage1 \
       --review-iteration 1 --approved-comment-ids c1,c2 --fix-scope file:src/foo.py --confirm true --root /tmp/agent-system-test --json
python dev_cli.py implementation-status        --job-id <id> --root /tmp/agent-system-test --json
python dev_cli.py implementation-list          --project-ref <p> --issue-number 42 --root /tmp/agent-system-test --json
python dev_cli.py implementation-explain       --job-id <id> --root /tmp/agent-system-test --json
```

---

## Suggested Module Layout

Add as flat modules under `portfolio_manager/` (matches existing `maintenance_*.py` and `worktree_*.py` style).

```txt
portfolio_manager/implementation_paths.py        NEW   (job_id, harness_id validators, artifact dir resolvers)
portfolio_manager/implementation_state.py        NEW   (implementation_jobs table + helpers)
portfolio_manager/harness_config.py              NEW   (load + validate $ROOT/config/harnesses.yaml)
portfolio_manager/implementation_locks.py        NEW   (impl-job lock context manager)
portfolio_manager/implementation_artifacts.py    NEW   (writers + redaction for plan/preflight/commands/...)
portfolio_manager/implementation_preflight.py    NEW   (worktree clean / branch match / source artifact present)
portfolio_manager/implementation_planner.py      NEW   (pure plan logic)
portfolio_manager/harness_runner.py              NEW   (allowlisted subprocess wrapper for harness commands)
portfolio_manager/implementation_changes.py      NEW   (changed-file collection from git status/diff output)
portfolio_manager/implementation_scope_guard.py  NEW   (changed files vs source-spec scope; protected paths)
portfolio_manager/implementation_test_quality.py NEW   (test-first evidence; tests-map-to-acceptance)
portfolio_manager/implementation_commit.py       NEW   (single local commit through allowlisted git commands)
portfolio_manager/implementation_jobs.py         NEW   (initial_implementation + review_fix orchestrators)
portfolio_manager/implementation_tools.py        NEW   (six tool handlers, thin wrappers)
portfolio_manager/schemas.py                     EXTEND (six new OpenAI-style schema dicts)
portfolio_manager/state.py                       EXTEND (implementation_jobs table + idempotent ALTERs)
portfolio_manager/__init__.py                    EXTEND (register six new tools)
dev_cli.py                                       EXTEND (six new CLI commands)
skills/implementation-run/SKILL.md               NEW
config/harnesses.yaml                            NEW   (committed example; runtime copy lives under $ROOT/config/)
```

If equivalents already exist (a shared redaction helper, a generic lock wrapper), reuse them — do not duplicate.

---

## Harness Configuration and Protocol

`$ROOT/config/harnesses.yaml` is server-side policy. MVP 6 reads it but never writes it.

Required shape:

```yaml
harnesses:
  - id: forge
    command: ["forge", "run"]
    env_passthrough: ["OPENAI_API_KEY"]
    timeout_seconds: 1800
    max_files_changed: 20
    required_checks: ["unit_tests", "lint"]
    checks:
      unit_tests:
        command: ["uv", "run", "pytest"]
        timeout_seconds: 600
      lint:
        command: ["uv", "run", "ruff", "check", "."]
        timeout_seconds: 300
    workspace_subpath: null
```

Rules:

```txt
command and every checks.<id>.command are argv arrays. Shell strings are invalid.
required_checks must reference keys under checks and must use allowlisted IDs:
  lint, typecheck, unit_tests, format_check.
No command interpolation. The runner passes paths through environment variables only.
```

Harness environment variables:

```txt
PORTFOLIO_IMPLEMENTATION_INPUT        absolute path to input-request.json
PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR absolute path to the job artifact dir
PORTFOLIO_IMPLEMENTATION_SOURCE       absolute path to the source spec artifact
PORTFOLIO_IMPLEMENTATION_JOB_ID       job id
GIT_TERMINAL_PROMPT                   always "0"
```

Harness result protocol:

```txt
The harness may write $PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR/harness-result.json.
If present, MVP 6 consumes these fields:
  status: "implemented" | "needs_user" | "failed"
  message: string
  test_first: list of {phase: "red"|"green"|"waived", command: list[str], exit_code: int, summary: string}
  changed_files_hint: optional list[str]          (advisory only; git remains source of truth)
  needs_user: optional {question: string, context: dict}

If harness-result.json is absent, MVP 6 falls back to return code + captured output:
  returncode 0 => implemented
  nonzero => failed
No hidden chain-of-thought, private provider metadata, or secrets may be copied into artifacts.
```

Review-fix naming convention:

```txt
Use pr_number in schemas, CLI args, SQLite columns, locks, and helper signatures.
Do not introduce pr_id unless a later MVP adds a distinct GitHub node-id requirement.
```

---

# Phase 0 — Preflight and Discovery

## 0.1 Confirm baseline green  [L1]

Status: [ ]

### Test first
Run the existing suite:
```bash
pytest
```

### Implementation
None. Diagnostic only. If unrelated failures exist, get user sign-off before proceeding.

### Verification
```bash
pytest -q
```

### Acceptance
```txt
pytest exits 0, OR the user has explicitly accepted the baseline.
```

---

## 0.2 Inspect existing contracts  [L1]

Status: [ ]

### Test first
None.

### Implementation
Read these files end-to-end and write a short scratchpad note (do NOT commit) mapping spec names → existing helpers:
```txt
portfolio_manager/state.py                  (open_state, init_state, acquire_lock, release_lock, schema)
portfolio_manager/worktree_git.py           (run_git, get_clean_state, get_origin_url, branch_exists, list_worktrees)
portfolio_manager/worktree.py               (inspect_worktree, discover_issue_worktrees)
portfolio_manager/worktree_paths.py         (resolve_under_root, assert_under_worktrees_root)
portfolio_manager/worktree_locks.py         (with_project_lock, with_issue_lock, WorktreeLockBusy)
portfolio_manager/worktree_state.py         (issue_worktree_id, get_worktree, list_worktrees_for_project)
portfolio_manager/worktree_artifacts.py     (artifact dir helpers, write_* functions, redaction reuse)
portfolio_manager/issue_artifacts.py        (issue_artifact_root, write_text_atomic — REUSE for source spec lookup)
portfolio_manager/errors.py                 (redact_secrets — REUSE)
portfolio_manager/maintenance_artifacts.py  (redaction patterns — REUSE)
portfolio_manager/__init__.py               (_TOOL_REGISTRY shape)
dev_cli.py                                  (_to_bool, --root, --json patterns)
```

### Acceptance
```txt
The implementer can name the existing helpers they will reuse and the helpers they must add.
No code changed.
```

---

## 0.3 Add structure tests for MVP 6 modules  [L1]

Status: [ ]

### Test first
Add `tests/test_structure.py` cases (extend the existing file):
```txt
test_implementation_modules_exist                 (imports for the 14 new portfolio_manager/implementation_*.py + harness_*.py modules)
test_implementation_run_skill_folder_exists
test_implementation_tools_registered              (six tool names appear in _TOOL_REGISTRY)
test_dev_cli_implementation_commands_registered   (six CLI subcommands)
test_no_duplicate_tool_names
test_existing_worktree_tools_still_callable       (back-compat smoke for MVP 5 tools)
```
Confirm they fail.

### Implementation
None beyond test additions. Optional empty placeholder modules only if pytest cannot import the test file.

### Verification
```bash
pytest tests/test_structure.py -q
```

### Acceptance
```txt
Tests fail for missing MVP 6 functionality, not for unrelated import errors.
```

---

# Phase 1 — Validators (Pure Functions)

## 1.1 job_id + harness_id validators  [L1]

Status: [ ]

### Test first
`tests/test_implementation_paths.py`:
```txt
test_generate_job_id_format                       (matches ^impl_[0-9a-f]{8,}$ or uuid4 form)
test_validate_job_id_accepts_generated
test_validate_job_id_rejects_path_traversal
test_validate_job_id_rejects_uppercase
test_validate_job_id_rejects_empty
test_validate_harness_id_accepts_alnum_dash_underscore
test_validate_harness_id_rejects_shell_metachar
test_validate_harness_id_rejects_path_separator
test_validate_harness_id_rejects_overlong              (>64 chars)
```

### Implementation
Add `portfolio_manager/implementation_paths.py`:
```python
JOB_ID_RE = re.compile(r"^impl_[0-9a-f-]{8,}$")
HARNESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
def generate_job_id() -> str: ...                       # impl_<uuid4 hex>
def validate_job_id(job_id: str) -> str: ...            # returns job_id or raises ValueError
def validate_harness_id(harness_id: str) -> str: ...
```

### Verification
```bash
pytest tests/test_implementation_paths.py -q
```

### Acceptance
```txt
All tests pass. Validators never accept a string the regex would reject.
No filesystem or subprocess calls.
```

---

## 1.2 Implementation artifact path resolvers  [L2]

Status: [ ]

### Test first
`tests/test_implementation_paths.py` (continued):
```txt
test_implementation_artifact_dir_under_root
test_implementation_artifact_dir_rejects_path_traversal_in_project_id
test_implementation_artifact_dir_rejects_negative_issue_number
test_implementation_artifact_dir_rejects_invalid_job_id
test_resolve_source_artifact_for_issue_number_returns_existing_draft_path
test_resolve_source_artifact_returns_none_when_missing
test_resolve_source_artifact_rejects_path_outside_root
```

### Implementation
Add to `portfolio_manager/implementation_paths.py`:
```python
def implementation_artifact_dir(root: Path, project_id: str, issue_number: int, job_id: str) -> Path:
    # $ROOT/artifacts/implementations/<project_id>/issue-<n>/<job_id>/
def resolve_source_artifact(root: Path, conn, project_id: str, issue_number: int) -> Path | None:
    # Returns the issue spec markdown file for the issue, not just its artifact directory.
    # Resolution order:
    #   1. issues.spec_artifact_path when it points to an existing file.
    #   2. issues.spec_artifact_path / "spec.md" when it points to an existing directory.
    #   3. issue_drafts.artifact_path / "spec.md" for the draft linked by github_issue_number.
    # Verify the returned file exists and resolves under $ROOT/artifacts/issues.
```

### Verification
```bash
pytest tests/test_implementation_paths.py -q
```

### Acceptance
```txt
Paths always contained under root/artifacts/implementations.
Source artifact resolver returns a concrete spec file (`spec.md` or equivalent), never a directory,
and never returns a path outside `$ROOT/artifacts/issues`.
```

---

# Phase 2 — Harness Configuration

## 2.1 Load and validate harnesses.yaml  [L2]

Status: [ ]

### Test first
`tests/test_harness_config.py`:
```txt
test_load_harnesses_yaml_returns_validated_models
test_missing_harnesses_yaml_returns_empty_with_warning
test_invalid_yaml_raises_config_error
test_harness_must_define_command_array_no_shell_string
test_harness_command_path_must_be_absolute_or_basename_only_no_traversal
test_harness_timeout_seconds_required_positive_int_under_max
test_harness_max_files_changed_required
test_harness_required_checks_must_be_array_of_allowlisted_check_ids
test_harness_checks_must_be_mapping_of_check_ids_to_command_arrays
test_required_checks_must_reference_defined_checks
test_check_timeout_seconds_required_positive_int_under_max
test_get_harness_by_id_returns_typed_model
test_get_harness_by_id_unknown_returns_none
test_harness_id_field_must_match_HARNESS_ID_RE
```
Use `tmp_path` to write fake `config/harnesses.yaml` files.

### Implementation
Add `portfolio_manager/harness_config.py`:
```python
@dataclass(frozen=True)
class HarnessCheckConfig:
    id: str
    command: list[str]          # argv form, no shell string
    timeout_seconds: int

@dataclass(frozen=True)
class HarnessConfig:
    id: str
    command: list[str]            # argv form, no shell string
    env_passthrough: list[str]    # env var names allowed
    timeout_seconds: int
    max_files_changed: int
    required_checks: list[str]    # ids referencing checks
    checks: dict[str, HarnessCheckConfig]
    workspace_subpath: str | None # optional sub-dir under issue_worktree_path

ALLOWED_CHECK_IDS = {"lint", "typecheck", "unit_tests", "format_check"}
def load_harness_config(root: Path) -> dict[str, HarnessConfig]: ...
def get_harness(root: Path, harness_id: str) -> HarnessConfig | None: ...
```
Reuse `config.ConfigError` for invalid input. Reuse `validate_harness_id` from 1.1.

### Verification
```bash
pytest tests/test_harness_config.py -q
```

### Acceptance
```txt
Bad command shapes (string, traversal, empty) are rejected at load time, not at run time.
required_checks cannot reference an undefined check command.
Unknown harness id returns None — never raises.
```

---

# Phase 3 — Schema and State Helpers

## 3.1 implementation_jobs table + idempotent migration  [L2]

Status: [ ]

### Test first
`tests/test_implementation_state.py`:
```txt
test_init_state_creates_implementation_jobs_table_idempotent
test_implementation_jobs_columns_match_spec
test_status_check_constraint_rejects_unknown_value
test_job_type_check_constraint_rejects_unknown_value
test_existing_state_db_can_be_migrated_in_place
test_migration_does_not_break_mvp1_to_mvp5_state_tests
```
Allowed `status` values: `planned, blocked, running, failed, succeeded, needs_user`.
Allowed `job_type` values: `initial_implementation, review_fix, qa_fix`.

### Implementation
Extend `portfolio_manager/state.py::SCHEMA_SQL`:
```sql
CREATE TABLE IF NOT EXISTS implementation_jobs (
  job_id TEXT PRIMARY KEY,
  job_type TEXT NOT NULL CHECK(job_type IN ('initial_implementation','review_fix','qa_fix')),
  project_id TEXT NOT NULL,
  issue_number INTEGER,
  worktree_id TEXT,
  pr_number INTEGER,
  review_stage_id TEXT,
  source_artifact_path TEXT,
  status TEXT NOT NULL CHECK(status IN ('planned','blocked','running','failed','succeeded','needs_user')),
  harness_id TEXT,
  started_at TEXT,
  finished_at TEXT,
  commit_sha TEXT,
  artifact_path TEXT,
  failure_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_impl_jobs_proj_issue ON implementation_jobs(project_id, issue_number);
CREATE INDEX IF NOT EXISTS idx_impl_jobs_status ON implementation_jobs(status);
```
Migration must be idempotent (`PRAGMA table_info`).

### Verification
```bash
pytest tests/test_implementation_state.py tests/test_state.py -q
```

### Acceptance
```txt
init_state on an MVP 5 db adds the new table without dropping existing rows.
Existing MVP 1–5 state tests pass unchanged.
```

---

## 3.2 implementation_jobs CRUD helpers  [L2]

Status: [ ]

### Test first
`tests/test_implementation_state.py` (continued):
```txt
test_insert_job_planned_returns_row
test_update_job_status_transitions_planned_to_running
test_invalid_status_transition_rejected            (e.g. succeeded → running)
test_finish_job_sets_finished_at_and_commit_sha
test_get_job_by_id
test_list_jobs_for_project_filters_by_status
test_list_jobs_for_issue_filters_by_issue_number
test_concurrent_insert_with_same_job_id_rejected
```

### Implementation
Add `portfolio_manager/implementation_state.py`:
```python
ALLOWED_STATUS = {"planned","blocked","running","failed","succeeded","needs_user"}
ALLOWED_TRANSITIONS = {
    "planned": {"running","blocked","failed","needs_user"},
    "running": {"succeeded","failed","needs_user","blocked"},
    "blocked": {"planned"},
    "needs_user": {"planned","blocked"},
    "succeeded": set(),
    "failed": set(),
}
def insert_job(conn, job: dict) -> None: ...
def update_job_status(conn, job_id: str, *, status: str, **fields) -> None: ...
def finish_job(conn, job_id: str, *, status: str, commit_sha: str | None, artifact_path: str, failure_reason: str | None) -> None: ...
def get_job(conn, job_id: str) -> dict | None: ...
def list_jobs(conn, *, project_id: str | None, issue_number: int | None, status: str | None) -> list[dict]: ...
```

### Verification
```bash
pytest tests/test_implementation_state.py -q
```

### Acceptance
```txt
Invalid transitions raise. Terminal states (succeeded/failed) cannot be reopened.
```

---

# Phase 4 — Artifacts

## 4.1 Artifact writers  [L2]

Status: [ ]

### Test first
`tests/test_implementation_artifacts.py`:
```txt
test_write_plan_md_shape
test_write_preflight_json_shape
test_write_commands_json_shape_argv_arrays_only
test_write_input_request_json_shape
test_write_test_first_evidence_md_shape
test_write_changed_files_json_shape
test_write_checks_json_shape
test_write_scope_check_md_shape
test_write_test_quality_md_shape
test_write_commit_json_shape
test_write_result_json_shape
test_write_error_json_shape
test_write_summary_md_is_telegram_safe
test_dry_run_writes_no_files
test_artifact_dir_created_with_0o700_permissions
test_secrets_redacted_in_every_artifact                  (https://*:*@, ghp_*, env values)
test_no_chain_of_thought_marker_written                  (heuristic strings like "internal:" or "<|cot|>")
```

### Implementation
Add `portfolio_manager/implementation_artifacts.py` writers covering the spec layout:
```txt
plan.md preflight.json commands.json input-request.json test-first-evidence.md
changed-files.json checks.json scope-check.md test-quality.md commit.json
result.json error.json summary.md
```
Reuse the existing redaction helper from `errors.py::redact_secrets` and any pattern from `maintenance_artifacts`. Writers must be no-ops on `dry_run=True` paths (callers pass a flag).

### Verification
```bash
pytest tests/test_implementation_artifacts.py -q
```

### Acceptance
```txt
No artifact ever contains a credential, token, env value, harness internal-thought marker, or local user path
outside $ROOT.
```

---

## 4.2 Atomic write + redaction static-grep  [L1]

Status: [ ]

### Test first
`tests/test_implementation_artifacts.py` (continued):
```txt
test_atomic_replace_used_for_every_artifact_write          (calls os.replace, not bare open+write)
test_no_print_or_logger_writes_secret_pattern              (static grep over implementation_*.py)
```

### Implementation
Either reuse `issue_artifacts.write_text_atomic` or expose a shared atomic writer. Wire all writers through it.

### Verification
```bash
pytest tests/test_implementation_artifacts.py -q
```

### Acceptance
```txt
No writer leaves a partial file on crash. Static grep test passes against all new modules.
```

---

# Phase 5 — Locks

## 5.1 Implementation job lock  [L2]

Status: [ ]

### Test first
`tests/test_implementation_locks.py`:
```txt
test_implementation_lock_acquired_and_released
test_lock_name_is_implementation_issue_project_issue        (e.g. implementation:issue:<id>:<n>)
test_lock_released_on_exception
test_lock_contention_raises_typed_error                     (ImplementationLockBusy)
test_default_ttl_is_60_minutes                              (longer than worktree TTL — harness can be slow)
test_lock_must_be_acquired_after_worktree_locks_when_combined
```

### Implementation
Add `portfolio_manager/implementation_locks.py`. Mirror `worktree_locks.with_issue_lock` shape:
```python
IMPLEMENTATION_LOCK_TTL = 60 * 60
class ImplementationLockBusy(RuntimeError): ...
def with_implementation_lock(conn, project_id: str, issue_number: int): ...
def with_implementation_review_lock(conn, project_id: str, pr_number: int): ...
```
On contention, raise the typed exception so handlers translate to `status="blocked"`, never `failed`.

### Verification
```bash
pytest tests/test_implementation_locks.py -q
```

### Acceptance
```txt
Locks always released in finally. Contention → blocked. TTL respected.
```

---

# Phase 6 — Preflight

## 6.1 Preflight checker  [L3]

Status: [ ]

### Test first
`tests/test_implementation_preflight.py`:
```txt
test_preflight_passes_for_clean_worktree_matching_branch_and_existing_source
test_preflight_blocks_when_worktree_row_missing_in_sqlite
test_preflight_blocks_when_worktree_path_missing_on_disk
test_preflight_blocks_when_worktree_dirty_uncommitted
test_preflight_blocks_when_worktree_dirty_untracked
test_preflight_blocks_when_worktree_in_merge_conflict
test_preflight_blocks_when_worktree_in_rebase_conflict
test_preflight_blocks_when_branch_does_not_match_expected
test_preflight_blocks_when_source_artifact_missing
test_preflight_blocks_when_source_artifact_outside_root
test_preflight_for_review_fix_blocks_when_pr_branch_mismatch
test_preflight_for_review_fix_blocks_when_approved_comment_ids_empty
test_preflight_writes_no_artifacts_no_sqlite               (pure read)
```

### Implementation
Add `portfolio_manager/implementation_preflight.py`:
```python
@dataclass
class PreflightResult:
    ok: bool
    reasons: list[str]
    worktree_path: Path | None
    branch_name: str | None
    head_sha: str | None
    source_artifact_path: Path | None

def preflight_initial_implementation(conn, *, project_id, issue_number, expected_branch, root) -> PreflightResult: ...
def preflight_review_fix(conn, *, project_id, issue_number, pr_number, expected_branch,
                          approved_comment_ids: list[str], fix_scope: list[str], root) -> PreflightResult: ...
```
Use `worktree_state.get_worktree`, `worktree_git.get_clean_state`, `worktree_git.branch_exists`,
`worktree.inspect_worktree`, and `implementation_paths.resolve_source_artifact`.

### Verification
```bash
pytest tests/test_implementation_preflight.py -q
```

### Acceptance
```txt
Pure read. Every block path returns reasons; never raises uncaught.
```

---

# Phase 7 — Planner (Read-Only)

## 7.1 Plan input schema  [L1]

Status: [ ]

### Test first
`tests/test_implementation_tools.py`:
```txt
test_plan_schema_requires_project_ref_issue_number_harness_id
test_plan_schema_rejects_negative_issue_number
test_plan_schema_accepts_optional_root
test_plan_schema_accepts_optional_expected_branch
```

### Implementation
Add to `portfolio_manager/schemas.py`:
```python
PORTFOLIO_IMPLEMENTATION_PLAN_SCHEMA = {
    "name": "portfolio_implementation_plan",
    "description": "Plan a confirmed implementation job without mutating SQLite, artifacts, or worktrees.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_ref": {"type": "string"},
            "issue_number": {"type": "integer", "minimum": 1},
            "harness_id": {"type": "string"},
            "expected_branch": {"type": "string"},
            "root": {"type": "string"},
        },
        "required": ["project_ref", "issue_number", "harness_id"],
        "additionalProperties": False,
    },
}
```

### Verification
```bash
pytest tests/test_implementation_tools.py::test_plan_schema_requires_project_ref_issue_number_harness_id -q
```

### Acceptance
```txt
Schema validates per spec.
```

---

## 7.2 Plan logic (pure)  [L3]

Status: [ ]

### Test first
`tests/test_implementation_planner.py`:
```txt
test_plan_returns_proposed_commands_and_workspace
test_plan_resolves_source_artifact_path
test_plan_blocks_when_harness_unknown
test_plan_blocks_when_preflight_fails                     (delegates to preflight)
test_plan_returns_required_checks_from_harness_config
test_plan_does_not_run_harness                            (zero subprocess calls)
test_plan_writes_no_sqlite_no_artifacts
test_plan_for_review_fix_includes_approved_comment_ids
test_plan_for_review_fix_blocks_when_review_iteration_zero_or_negative
```

### Implementation
Add `portfolio_manager/implementation_planner.py`:
```python
@dataclass
class ImplementationPlan:
    job_type: str
    project_id: str
    issue_number: int
    harness_id: str
    workspace_path: Path
    source_artifact_path: Path
    expected_branch: str
    base_sha: str
    proposed_command: list[str]
    required_checks: list[str]
    blocked_reasons: list[str]
    warnings: list[str]

def build_initial_plan(conn, root, *, project_ref, issue_number, harness_id, expected_branch) -> ImplementationPlan: ...
def build_review_fix_plan(conn, root, *, project_ref, issue_number, pr_number, harness_id,
                           review_stage_id, review_iteration, approved_comment_ids, fix_scope) -> ImplementationPlan: ...
```
Pure functions — no SQLite writes, no artifact writes, no subprocess.

### Verification
```bash
pytest tests/test_implementation_planner.py -q
```

### Acceptance
```txt
Every block path enumerated in spec § Reusable Harness Job Contract is covered.
Plan never writes anywhere.
```

---

# Phase 8 — Harness Runner (Subprocess)

## 8.1 Allowlisted harness subprocess wrapper  [L3]

Status: [ ]

### Test first
`tests/test_harness_runner.py`:
```txt
test_runner_uses_argument_array
test_runner_rejects_string_command
test_runner_sets_GIT_TERMINAL_PROMPT_zero
test_runner_only_passes_env_in_env_passthrough_list
test_runner_strips_HOME_PATH_to_minimal_safe_set            (no parent shell secrets leak)
test_runner_sets_cwd_to_workspace_path
test_runner_workspace_path_must_be_under_worktrees_root
test_runner_enforces_timeout_seconds_from_harness_config
test_runner_kills_process_group_on_timeout
test_runner_captures_stdout_stderr_truncated_to_64KB_each
test_runner_redacts_token_patterns_in_captured_output
test_runner_passes_portfolio_input_artifact_source_env_vars
test_runner_reads_harness_result_json_when_present
test_runner_maps_harness_result_status_needs_user
test_runner_returns_typed_result_with_returncode_duration_truncated_flag
test_runner_rejects_command_path_with_shell_metachar
test_runner_rejects_command_when_workspace_dirty_at_entry      (re-checks via worktree_git.get_clean_state)
test_run_required_check_uses_check_command_and_timeout
```

### Implementation
Add `portfolio_manager/harness_runner.py`:
```python
@dataclass(frozen=True)
class HarnessResult:
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    harness_status: str | None     # implemented | needs_user | failed from harness-result.json
    harness_message: str | None

def run_harness(*, harness: HarnessConfig, workspace: Path, root: Path,
                source_artifact_path: Path, instructions: dict,
                artifact_dir: Path, input_request_path: Path,
                extra_env: dict[str, str] | None = None) -> HarnessResult: ...
def run_required_check(*, check: HarnessCheckConfig, workspace: Path, root: Path,
                       artifact_dir: Path, extra_env: dict[str, str] | None = None) -> HarnessResult: ...
```
Use `subprocess.Popen(..., start_new_session=True)`, no `shell=True`, allowlist check on the command basename,
redact env values not in passthrough, set the harness protocol env vars, and consume
`artifact_dir / "harness-result.json"` when present.

### Verification
```bash
pytest tests/test_harness_runner.py -q
```

### Acceptance
```txt
Forbidden commands and dirty workspaces raise before subprocess starts.
Timeouts terminate the process group, never orphan children.
Captured output never contains tokens or env values.
```

---

## 8.2 Changed-file collector  [L2]

Status: [ ]

### Test first
`tests/test_implementation_changes.py`:
```txt
test_collect_changed_files_uses_git_status_porcelain
test_collect_changed_files_includes_untracked_files
test_collect_changed_files_detects_renames
test_collect_changed_files_normalizes_to_posix_relative_paths
test_collect_changed_files_blocks_absolute_or_dotdot_paths
test_collect_changed_files_rejects_paths_outside_workspace
test_collect_changed_files_requires_workspace_under_worktrees_root
test_collect_changed_files_allows_dirty_workspace_after_harness_for_scope_gate
```

### Implementation
Add `portfolio_manager/implementation_changes.py`:
```python
@dataclass(frozen=True)
class ChangedFiles:
    files: list[str]
    statuses: list[dict[str, str]]  # {path, status, old_path?}

def collect_changed_files(workspace: Path, *, root: Path) -> ChangedFiles: ...
```
Use `worktree_git.run_git` with read-only commands only:
```txt
git status --porcelain=v1 --untracked-files=all
git diff --name-status --find-renames HEAD
```
Extend `worktree_git.run_git` allowlist only as needed for these read-only diff/status commands.

### Verification
```bash
pytest tests/test_implementation_changes.py -q
```

### Acceptance
```txt
Changed file paths are git-derived, POSIX-relative, and cannot escape the workspace.
This helper never writes SQLite, artifacts, or worktree files.
```

---

# Phase 9 — Test-First, Scope, Test-Quality Gates

## 9.1 Test-first evidence collector  [L2]

Status: [ ]

### Test first
`tests/test_implementation_test_quality.py`:
```txt
test_evidence_records_failing_test_run_before_implementation
test_evidence_records_passing_test_run_after_implementation
test_evidence_blocks_when_no_failing_test_phase_found
test_evidence_allows_explicit_no_test_path_with_reason     (spec § Safety Rule 4)
test_evidence_writer_redacts_paths_under_user_home
```

### Implementation
Add `portfolio_manager/implementation_test_quality.py::collect_test_first_evidence(...)` returning a structure suitable for `test-first-evidence.md`. Drives `git status` snapshots and harness output sections — does NOT execute tests itself; it consumes the harness's check output.

### Verification
```bash
pytest tests/test_implementation_test_quality.py -q -k evidence
```

### Acceptance
```txt
Missing failing-test phase blocks the job unless an explicit waiver string is present.
```

---

## 9.2 Scope guard  [L3]

Status: [ ]

### Test first
`tests/test_implementation_scope_guard.py`:
```txt
test_scope_guard_passes_when_changed_files_within_spec_scope
test_scope_guard_blocks_when_protected_path_changed         (project_config.protected_paths)
test_scope_guard_blocks_when_changed_files_exceed_max
test_scope_guard_blocks_when_unrelated_files_changed
test_scope_guard_passes_for_review_fix_files_in_approved_fix_scope
test_scope_guard_blocks_for_review_fix_files_outside_approved_fix_scope
test_scope_guard_does_not_run_subprocess                    (consumes a pre-captured changed-files list)
test_scope_guard_writes_no_artifacts                        (caller writes scope-check.md)
```

### Implementation
Add `portfolio_manager/implementation_scope_guard.py`:
```python
@dataclass
class ScopeCheck:
    ok: bool
    reasons: list[str]
    changed_files: list[str]
    protected_violations: list[str]
    out_of_scope_files: list[str]

def check_scope(*, changed_files: list[str], spec_scope: list[str], protected_paths: list[str],
                max_files_changed: int, fix_scope: list[str] | None = None) -> ScopeCheck: ...
```
Use `fnmatch` for glob patterns (matches `protected_paths` style in `projects.yaml`).

### Verification
```bash
pytest tests/test_implementation_scope_guard.py -q
```

### Acceptance
```txt
Every protected-path glob is enforced. No-op when fix_scope=None for initial implementation.
```

---

## 9.3 Test quality check  [L2]

Status: [ ]

### Test first
`tests/test_implementation_test_quality.py` (continued):
```txt
test_quality_passes_when_added_tests_reference_acceptance_criteria_ids
test_quality_blocks_when_zero_new_tests_for_initial_implementation
test_quality_allows_review_fix_without_new_tests_when_fix_is_doc_only
test_quality_blocks_when_added_tests_are_only_pass_assertions
test_quality_blocks_when_added_tests_have_no_meaningful_asserts
test_quality_writer_produces_test_quality_md_with_per_test_summary
```

### Implementation
Add `portfolio_manager/implementation_test_quality.py::check_test_quality(...)`. Heuristics:
1. Count new test files / functions in `changed-files.json`.
2. Read each test, look for non-trivial assertions (`assert ... ==`, `pytest.raises`, etc).
3. Cross-reference acceptance-criteria IDs from the source artifact (markdown headers / explicit IDs).

### Verification
```bash
pytest tests/test_implementation_test_quality.py -q
```

### Acceptance
```txt
A harness that produces no meaningful tests cannot reach the commit step.
```

---

# Phase 10 — Local Commit

## 10.1 Extend git wrapper for local commit only  [L3]

Status: [ ]

### Test first
`tests/test_implementation_commit.py`:
```txt
test_worktree_git_allows_add_A_for_implementation_commit
test_worktree_git_allows_commit_with_per_command_user_config_and_m_message
test_worktree_git_allows_rev_parse_head
test_worktree_git_rejects_commit_amend
test_worktree_git_rejects_commit_without_message
test_worktree_git_rejects_commit_with_global_config
test_worktree_git_still_rejects_push_rebase_reset_clean_stash
```

### Implementation
Extend `portfolio_manager/worktree_git.py` allowlist surgically, or add a narrowly-scoped wrapper in
`portfolio_manager/implementation_commit.py` that still calls `worktree_git.run_git` after validation.
Allowed MVP 6 git write commands:
```txt
git add -A
git -c user.name=<name> -c user.email=<email> commit -m <message>
git rev-parse HEAD
```
All other commit forms are forbidden, especially `--amend`, `--reset-author`, global config writes,
push, rebase, reset, clean, stash, checkout, and pull.

### Verification
```bash
pytest tests/test_implementation_commit.py tests/test_worktree_git.py -q
```

### Acceptance
```txt
MVP 6 can make exactly one local commit through a constrained path without weakening MVP 5's
remote-mutation and repo-rewrite protections.
```

---

## 10.2 Local commit helper  [L3]

Status: [ ]

### Test first
`tests/test_implementation_commit.py`:
```txt
test_commit_runs_only_after_checks_pass
test_commit_uses_argument_array_no_shell
test_commit_uses_minus_m_with_safe_message              (no embedded shell expansion)
test_commit_message_includes_job_id_and_issue_number
test_commit_message_omits_provider_credentials_or_paths_under_user_home
test_commit_blocks_when_worktree_dirty_with_unstaged_after_harness    (must be staged or all tracked)
test_commit_blocks_when_worktree_clean_no_changes_to_commit           (returns skipped, not failure)
test_commit_returns_sha_after_success
test_commit_does_NOT_call_git_push_amend_rebase_reset_clean_stash
test_commit_does_NOT_set_user_email_or_user_name_globally             (per-commit -c only)
```

### Implementation
Add `portfolio_manager/implementation_commit.py`:
```python
def make_local_commit(workspace: Path, *, job_id: str, issue_number: int,
                       message: str, author_name: str, author_email: str) -> str | None: ...
```
Sequence (all via `worktree_git.run_git`):
```
git add -A
git -c user.name=<n> -c user.email=<e> commit -m <message>
git rev-parse HEAD
```
Forbidden subcommands (`push`, `--amend`, `rebase`, `reset`, `clean`, `stash`) must remain blocked at the runner allowlist layer.
This task depends on 10.1; do not bypass the wrapper with raw `subprocess`.

### Verification
```bash
pytest tests/test_implementation_commit.py -q
```

### Acceptance
```txt
Single commit is made through allowlisted git only. Returns sha or skipped.
```

---

# Phase 11 — Initial Implementation Orchestrator

## 11.1 Start input schema  [L1]

Status: [ ]

### Test first
`tests/test_implementation_tools.py`:
```txt
test_start_schema_defaults_confirm_false
test_start_schema_requires_harness_id
test_start_schema_rejects_unknown_field
```

### Implementation
Add `PORTFOLIO_IMPLEMENTATION_START_SCHEMA` to `schemas.py`:
```python
PORTFOLIO_IMPLEMENTATION_START_SCHEMA = {
    "name": "portfolio_implementation_start",
    "description": "Run a confirmed initial_implementation job in a prepared issue worktree.",
    "parameters": {
        "type": "object",
        "properties": {
            "project_ref": {"type": "string"},
            "issue_number": {"type": "integer", "minimum": 1},
            "harness_id": {"type": "string"},
            "expected_branch": {"type": "string"},
            "base_sha": {"type": "string"},
            "instructions": {"type": "object"},
            "confirm": {"type": "boolean", "default": False},
            "root": {"type": "string"},
        },
        "required": ["project_ref", "issue_number", "harness_id"],
        "additionalProperties": False,
    },
}
```

### Verification
```bash
pytest tests/test_implementation_tools.py -q -k start_schema
```

### Acceptance
```txt
Defaults match spec.
```

---

## 11.2 initial_implementation orchestrator  [L3]

Status: [ ]

### Test first
`tests/test_implementation_jobs.py`:
```txt
test_initial_impl_dry_run_returns_plan_no_mutation        (confirm=false → blocked, no row inserted)
test_initial_impl_real_run_inserts_planned_row_then_running
test_initial_impl_real_run_acquires_implementation_lock
test_initial_impl_real_run_writes_plan_preflight_commands_artifacts_in_order
test_initial_impl_real_run_calls_harness_runner_once
test_initial_impl_real_run_runs_required_checks_after_harness
test_initial_impl_blocks_when_harness_dirties_protected_paths
test_initial_impl_blocks_when_test_quality_fails
test_initial_impl_creates_local_commit_when_all_gates_pass
test_initial_impl_writes_result_and_finishes_succeeded
test_initial_impl_writes_error_artifact_and_finishes_failed_on_uncaught_exception
test_initial_impl_returns_needs_user_when_harness_signals_unanswerable
test_initial_impl_releases_lock_on_exception
test_initial_impl_lock_contention_returns_blocked
test_initial_impl_does_NOT_call_git_push_or_gh_pr_create
```

### Implementation
Add `portfolio_manager/implementation_jobs.py::run_initial_implementation(...)`. Sequence:
```
build_initial_plan → confirm gate → insert_job(planned) → with_implementation_lock →
  update_job_status(running) → write plan/preflight/commands/input-request →
  preflight_initial_implementation → if not ok: blocked + finish_job
  run_harness → collect_changed_files → run required_checks via run_required_check →
  write changed-files.json + checks.json →
  collect_test_first_evidence → check_scope → check_test_quality →
  if any gate fails: blocked + finish_job
  make_local_commit → write commit.json + result.json + summary.md → finish_job(succeeded)
```

### Verification
```bash
pytest tests/test_implementation_jobs.py -q -k initial_impl
```

### Acceptance
```txt
All side effects gated by confirm=true AND every preflight + scope + test-quality check passing.
Lock always released. Forbidden commands cannot be reached from this code path
(verified by Phase 16 tests).
```

---

# Phase 12 — Review-Fix Orchestrator

## 12.1 Apply-review-fixes input schema  [L1]

Status: [ ]

### Test first
`tests/test_implementation_tools.py`:
```txt
test_apply_review_fixes_schema_defaults_confirm_false
test_apply_review_fixes_schema_requires_pr_number_and_review_stage_id
test_apply_review_fixes_schema_requires_non_empty_approved_comment_ids
test_apply_review_fixes_schema_validates_review_iteration_positive
```

### Implementation
Add `PORTFOLIO_IMPLEMENTATION_APPLY_REVIEW_FIXES_SCHEMA` to `schemas.py` per spec § Reusable Harness Job Contract,
using OpenAI-style schema dicts matching the existing file. Required fields:
`project_ref`, `issue_number`, `pr_number`, `review_stage_id`, `review_iteration`,
`approved_comment_ids`, `fix_scope`, and `harness_id`. `confirm` defaults to false.

### Verification
```bash
pytest tests/test_implementation_tools.py -q -k apply_review_fixes_schema
```

### Acceptance
```txt
Schema validates per spec.
```

---

## 12.2 review_fix orchestrator  [L3]

Status: [ ]

### Test first
`tests/test_implementation_jobs.py`:
```txt
test_review_fix_dry_run_returns_plan_no_mutation
test_review_fix_real_run_acquires_review_lock_scoped_to_pr
test_review_fix_writes_artifacts_linking_review_stage_and_comment_ids
test_review_fix_blocks_when_pr_branch_mismatch
test_review_fix_blocks_when_approved_comment_ids_empty
test_review_fix_blocks_when_changed_files_outside_fix_scope
test_review_fix_blocks_when_no_failing_test_added_for_regression_fix
test_review_fix_creates_followup_local_commit_with_message_referencing_comment_ids
test_review_fix_returns_needs_user_when_feedback_requires_product_judgment
test_review_fix_does_NOT_decide_pass_fail_for_review_stage
test_review_fix_does_NOT_push
```

### Implementation
Add `implementation_jobs.run_review_fix(...)`. Reuse the initial-implementation skeleton; differences:
- `job_type="review_fix"`, separate lock (`with_implementation_review_lock`), additional fields persisted.
- Scope check uses `fix_scope` instead of full spec scope.
- Test-quality may pass without new tests if `fix_scope` is doc-only (spec § 9.3).
- Artifacts include `input-request.json` with `approved_comment_ids` and the review stage/iteration.

### Verification
```bash
pytest tests/test_implementation_jobs.py -q -k review_fix
```

### Acceptance
```txt
MVP 6 makes no decisions about review pass/fail. It only modifies files for approved comment IDs.
```

---

# Phase 13 — Tool Handlers

## 13.1 plan + status + list + explain handlers  [L2]

Status: [ ]

### Test first
`tests/test_implementation_tools.py`:
```txt
test_plan_tool_returns_success_for_clean_path
test_plan_tool_returns_blocked_with_reason
test_plan_tool_does_not_persist_state
test_status_schema_accepts_job_id_or_project_ref_issue_number
test_list_schema_accepts_optional_project_issue_status_filters
test_explain_schema_requires_job_id
test_status_tool_returns_row_for_known_job_id
test_status_tool_blocks_for_unknown_job_id
test_list_tool_filters_by_project_and_issue
test_list_tool_filters_by_status
test_explain_tool_describes_block_reason_for_blocked_job
test_explain_tool_describes_needs_user_reason
test_explain_tool_returns_blocked_for_unknown_job_id
```

### Implementation
Add `PORTFOLIO_IMPLEMENTATION_STATUS_SCHEMA`, `PORTFOLIO_IMPLEMENTATION_LIST_SCHEMA`,
and `PORTFOLIO_IMPLEMENTATION_EXPLAIN_SCHEMA` to `portfolio_manager/schemas.py` as OpenAI-style
schema dicts. Add `portfolio_manager/implementation_tools.py` with thin handlers:
```python
def _handle_portfolio_implementation_plan(args, **kw) -> str: ...
def _handle_portfolio_implementation_status(args, **kw) -> str: ...
def _handle_portfolio_implementation_list(args, **kw) -> str: ...
def _handle_portfolio_implementation_explain(args, **kw) -> str: ...
```
Each handler ≤ 40 lines. Logic lives in `implementation_planner.py` / `implementation_state.py`.

### Verification
```bash
pytest tests/test_implementation_tools.py -q -k "plan or status or list or explain"
```

### Acceptance
```txt
Read-only handlers never write SQLite or artifacts.
```

---

## 13.2 start + apply_review_fixes handlers  [L2]

Status: [ ]

### Test first
`tests/test_implementation_tools.py`:
```txt
test_start_handler_blocks_when_confirm_false
test_start_handler_calls_run_initial_implementation_when_confirm_true
test_start_handler_returns_lock_contention_as_blocked
test_apply_review_fixes_handler_blocks_when_confirm_false
test_apply_review_fixes_handler_calls_run_review_fix_when_confirm_true
test_apply_review_fixes_handler_returns_blocked_for_unknown_pr_branch
test_handlers_register_in_TOOL_REGISTRY                     (added to portfolio_manager/__init__.py)
```

### Implementation
Add the two handlers to `implementation_tools.py`. Add to `_TOOL_REGISTRY` in `__init__.py`. Translate `ImplementationLockBusy` to `blocked`.

### Verification
```bash
pytest tests/test_implementation_tools.py -q -k "start or apply_review_fixes"
```

### Acceptance
```txt
All six tools registered. Confirm + lock semantics enforced at the handler boundary.
```

---

# Phase 14 — Dev CLI

## 14.1 Add CLI parser entries  [L1]

Status: [ ]

### Test first
`tests/test_dev_cli.py`:
```txt
test_cli_registers_implementation_plan
test_cli_registers_implementation_start
test_cli_registers_implementation_apply_review_fixes
test_cli_registers_implementation_status
test_cli_registers_implementation_list
test_cli_registers_implementation_explain
```

### Implementation
Extend `dev_cli.py` with the six subcommands listed in Required Dev CLI Commands. Reuse existing `_to_bool`, `--root`, `--json` patterns. For `--approved-comment-ids`, accept comma-separated list and split.

### Verification
```bash
pytest tests/test_dev_cli.py -q -k implementation
```

### Acceptance
```txt
All commands print valid JSON shared result objects when invoked with --json.
```

---

## 14.2 CLI behavior tests with test root  [L1]

Status: [ ]

### Test first
`tests/test_dev_cli.py`:
```txt
test_cli_implementation_plan_returns_blocked_for_unknown_project
test_cli_implementation_plan_returns_blocked_for_unknown_harness_id
test_cli_implementation_status_returns_blocked_for_unknown_job_id
test_cli_implementation_list_returns_empty_array_for_empty_root
```

### Implementation
Wire CLI commands to handlers. No new logic.

### Verification
```bash
pytest tests/test_dev_cli.py -q
```

### Acceptance
```txt
JSON exit code and shape match shared result format.
```

---

# Phase 15 — Hermes Skill Documentation

## 15.1 Add `implementation-run` skill folder  [L1]

Status: [ ]

### Test first
`tests/test_implementation_skill.py`:
```txt
test_implementation_run_skill_md_exists
test_skill_mentions_plan_first
test_skill_mentions_confirm_required
test_skill_mentions_blocked_over_guessing
test_skill_lists_six_expected_tools
test_skill_warns_no_push_no_pr_no_review_decision
test_skill_warns_no_worktree_mutation_outside_harness
test_skill_describes_review_fix_callable_only_after_mvp7
```

### Implementation
Create `skills/implementation-run/SKILL.md`. Cover spec § User Stories, the six tools, the confirmation flow, and explicit non-goals.

### Verification
```bash
pytest tests/test_implementation_skill.py -q
```

### Acceptance
```txt
A Hermes agent reading this skill cannot reasonably skip plan-first, confirm-required, or attempt
to push / open PRs / classify review comments.
```

---

# Phase 16 — Security Hardening Tests

## 16.1 Harness command allowlist + shell=True grep  [L2]

Status: [ ]

### Test first
`tests/test_security.py` (extend):
```txt
test_no_shell_true_in_implementation_modules
test_no_subprocess_string_command_in_implementation_modules
test_no_os_system_or_popen_in_implementation_modules
test_no_eval_or_exec_in_implementation_modules
test_only_harness_runner_invokes_subprocess_for_harness_commands
test_harness_runner_basename_allowlist_enforced
```
Implement as static-grep over `portfolio_manager/implementation_*.py` and `portfolio_manager/harness_*.py`.

### Verification
```bash
pytest tests/test_security.py -q -k "implementation or harness"
```

### Acceptance
```txt
Forbidden patterns cannot be introduced without breaking a security test.
```

---

## 16.2 Forbidden git/gh subcommands grep  [L2]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_no_git_push_in_implementation_modules
test_no_git_amend_in_implementation_modules
test_no_git_rebase_in_implementation_modules
test_no_git_reset_in_implementation_modules
test_no_git_clean_in_implementation_modules
test_no_git_stash_in_implementation_modules
test_no_gh_pr_create_in_implementation_modules
test_no_gh_pr_merge_in_implementation_modules
test_no_gh_issue_create_in_implementation_modules
test_no_npm_pnpm_yarn_pip_cargo_make_pytest_in_orchestrator   (these run only inside harness sandbox, not from MVP 6 code)
```

### Verification
```bash
pytest tests/test_security.py -q
```

### Acceptance
```txt
No remote-mutating or repo-rewriting subcommand can be added without breaking these tests.
```

---

## 16.3 Path containment + workspace escape  [L2]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_harness_workspace_outside_root_blocked_at_handler_layer
test_artifact_dir_path_traversal_in_job_id_blocked
test_artifact_dir_path_traversal_in_project_id_blocked
test_source_artifact_path_outside_root_blocked
test_symlink_under_worktrees_to_outside_blocked_for_harness_workspace
test_workspace_subpath_with_dotdot_blocked
```

### Verification
```bash
pytest tests/test_security.py -q -k "path or workspace or symlink"
```

### Acceptance
```txt
No tool path can escape $ROOT.
```

---

## 16.4 Secret + env redaction tests  [L1]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_https_token_in_remote_url_redacted_in_implementation_artifacts
test_ghp_token_in_harness_stderr_redacted_in_error_json
test_env_variable_value_not_in_passthrough_never_written_to_artifacts
test_no_chain_of_thought_marker_in_implementation_artifacts
test_no_user_home_path_in_summary_md
```

### Verification
```bash
pytest tests/test_security.py -q -k "redact or token or chain"
```

### Acceptance
```txt
No artifact contains a secret, env value, internal-thought marker, or absolute user-home path.
```

---

# Phase 17 — Local E2E with Bare Repos and Fake Harness

E2E tests must use **local temporary Git repos** + a **fake harness binary** (a Python script created in `tmp_path`), never real GitHub or paid providers.

## 17.1 Fake harness fixture  [L2]

Status: [ ]

### Test first
None (this task is the fixture itself).

### Implementation
Add to `tests/fixtures/implementation_fixtures.py`:
```python
@pytest.fixture
def fake_harness_script(tmp_path) -> Path:
    """Write a Python script that:
       1. reads the input-request.json passed via env var,
       2. modifies a single file in cwd,
       3. exits 0.
       Returns the script path.
    """

@pytest.fixture
def harnesses_yaml_with_fake(fake_harness_script, tmp_path) -> Path:
    """Write $ROOT/config/harnesses.yaml referencing the fake script."""

@pytest.fixture
def prepared_issue_worktree(bare_remote, tmp_path) -> dict:
    """Reuse MVP 5 fixtures to prepare a clean issue worktree. Returns project_id, issue_number, paths."""
```
Reuse MVP 5's `bare_remote` fixture from `tests/fixtures/worktree_fixtures.py`.

### Verification
```bash
python -m py_compile tests/fixtures/implementation_fixtures.py
```

### Acceptance
```txt
Fixtures usable by all E2E tests below. No network access. No paid provider calls.
```

---

## 17.2 E2E: initial implementation happy path  [L3]

Status: [ ]

### Test first
`tests/test_implementation_e2e.py`:
```txt
test_e2e_initial_impl_dry_run_no_side_effects
test_e2e_initial_impl_confirm_true_runs_fake_harness_and_commits
test_e2e_initial_impl_writes_all_thirteen_artifact_files
test_e2e_initial_impl_inserts_job_row_with_succeeded
test_e2e_repeated_initial_impl_for_same_issue_blocks_until_first_finishes
```

### Implementation
Call the tool handler against the prepared worktree fixture + fake harness.

### Verification
```bash
pytest tests/test_implementation_e2e.py -q -k e2e_initial_impl
```

### Acceptance
```txt
Real fake-harness run + commit happen exactly once with confirm. SQLite job row reflects status=succeeded.
```

---

## 17.3 E2E: block / failure / needs_user paths  [L3]

Status: [ ]

### Test first
`tests/test_implementation_e2e.py`:
```txt
test_e2e_initial_impl_blocks_when_worktree_dirty
test_e2e_initial_impl_blocks_when_branch_mismatch
test_e2e_initial_impl_blocks_when_source_artifact_missing
test_e2e_initial_impl_blocks_when_harness_writes_protected_path
test_e2e_initial_impl_finishes_failed_when_fake_harness_returns_nonzero
test_e2e_initial_impl_returns_needs_user_when_fake_harness_signals_unanswerable
test_e2e_review_fix_applies_only_for_approved_comment_ids
test_e2e_review_fix_blocks_when_change_outside_fix_scope
test_e2e_does_not_push_or_open_pr                          (assert no remote refs created in bare repo)
```

### Implementation
Configure the fake harness to take a flag controlling which behavior to emulate. Verify SQLite, artifacts, and the bare remote stay untouched.

### Verification
```bash
pytest tests/test_implementation_e2e.py -q
```

### Acceptance
```txt
Every block path returns status="blocked" with a reason. failure path returns "failed" with error.json.
needs_user path returns "needs_user" with input-request.json. No state mutated remotely.
```

---

# Phase 18 — Full Regression + Docs

## 18.1 Full pytest  [L1]

Status: [ ]

### Test first
Run the full suite:
```bash
pytest
```

### Implementation
Fix any regressions in MVP 1–5 behavior introduced by MVP 6.

### Verification
```bash
pytest -q
```

### Acceptance
```txt
pytest exits 0 with no skipped MVP 6 tests.
```

---

## 18.2 Update handoff status  [L1]

Status: [ ]

### Test first
None.

### Implementation
Update `docs/product/project-handoff.md` MVP 6 row only after Phase 17 + 18.1 are green. Mark MVP 6 implemented; do **not** claim manual smoke until 18.3 is run.

### Acceptance
```txt
Handoff doc reflects actual implementation state.
```

---

## 18.3 Manual smoke (deferred to user)  [L1]

Status: [ ]

### Test first
Automated tests must already pass.

### Implementation
Run an end-to-end manual smoke against `/tmp/agent-system-test`:
1. `worktree-create-issue` (MVP 5) for a bare-fixture project + issue.
2. `implementation-plan` for the same issue + a configured fake harness.
3. `implementation-start --confirm true` and inspect artifacts + commit.
4. Confirm no push, no PR, no remote refs added.
5. Manually invoke `implementation-apply-review-fixes` with a fabricated approved-comment-id list against a local PR worktree.

### Acceptance
```txt
All five smoke steps behave as expected. No remote mutation observed.
```

---

# Definition of Done

MVP 6 is complete when:

```txt
All MVP 1–5 tests still pass.
All MVP 6 tests pass.
Six new tools registered: plan, start, apply_review_fixes, status, list, explain.
Six new dev_cli subcommands work and return shared result JSON.
skills/implementation-run/SKILL.md exists and instructs plan-first + confirm-required behavior.
$ROOT/config/harnesses.yaml load + validation works; missing file returns empty with warning.
implementation_jobs SQLite table created idempotently; status + job_type CHECK constraints enforced.
Plan / dry-run never write SQLite implementation_jobs or implementation artifacts.
Real runs write SQLite + per-run artifacts under $ROOT/artifacts/implementations/...; artifacts redact secrets,
  env values, internal-thought markers, and user-home paths.
Every harness invocation goes through harness_runner with allowlisted basename + timeout + restricted env.
shell=True / os.system / os.popen / eval / exec grep tests pass over implementation_*.py and harness_*.py.
git push / amend / rebase / reset / clean / stash and gh pr/issue mutating subcommands grep tests pass.
Worktree workspace path always contained under $ROOT/worktrees; symlink escapes blocked.
Locks always released; contention returns blocked, not failed.
initial_implementation creates exactly one local commit when all gates pass; otherwise no commit.
review_fix uses only approved_comment_ids passed by caller; no MVP 6 classification of review comments.
qa_fix job_type enum accepted but no orchestrator implemented (reserved for MVP 8).
docs/product/project-handoff.md updated to reflect MVP 6 implemented (after 18.1).
```

---

# Suggested Implementation Order

```txt
0.1 → 0.2 → 0.3                         baseline + structure
1.1 → 1.2                               id + path validators
2.1                                     harness config loader
3.1 → 3.2                               state schema + CRUD
4.1 → 4.2                               artifacts
5.1                                     locks
6.1                                     preflight
7.1 → 7.2                               planner
8.1 → 8.2                               harness runner + changed-file collection
9.1 → 9.2 → 9.3                         test-first + scope + test-quality gates
10.1 → 10.2                             git allowlist + local commit
11.1 → 11.2                             initial_implementation orchestrator
12.1 → 12.2                             review_fix orchestrator
13.1 → 13.2                             tool handlers
14.1 → 14.2                             dev CLI
15.1                                    skill docs
16.1 → 16.2 → 16.3 → 16.4               security hardening
17.1 → 17.2 → 17.3                      E2E
18.1 → 18.2 → 18.3                      regression + docs + smoke
```

A "dumber" agent should pick exactly one task at a time, read its tests-first block, write the failing tests, get them failing for the right reason, then implement until green. Do not bundle tasks. Do not refactor unrelated code. Status checkbox flips to `[x]` only when the task's verification step passes.

---

# Implementation Notes

## Keep handlers thin

Tool handlers should only:
```txt
validate input → resolve root → open conn → call tested helpers → return shared result
```
Core behavior belongs in `implementation_planner.py`, `implementation_jobs.py`, `harness_runner.py`, etc.

## The harness is the only allowed non-git mutation source

MVP 6 modules never write to `$ROOT/worktrees/<project>-issue-<n>/` directly. The harness subprocess is the only writer; MVP 6 only reads the resulting state via `git status` / `git diff` and finalizes one commit through allowlisted git.

## No paid-provider calls without explicit policy

`harness_runner` does not load API keys. If a harness command requires credentials, those must be in `harness.env_passthrough` AND already present in the runtime environment. MVP 6 never reads `$ROOT/config/secrets.yaml` or similar — that is a later MVP.

## Prefer controlled outcomes

Use `blocked` / `skipped` / `needs_user` / `failed` instead of uncaught exceptions. Translate typed exceptions (`ImplementationLockBusy`, validation errors, harness timeouts) at the handler boundary.

## Subprocess discipline

Every harness/check/git/gh call goes through `harness_runner.run_harness`,
`harness_runner.run_required_check`, `implementation_commit.make_local_commit`, or
`worktree_git.run_git`. Each call must have:
```txt
argument array (no shell=True)
explicit timeout
env scrubbed to passthrough list (harness) or GIT_TERMINAL_PROMPT=0 (git)
allowlist check before exec
redacted stderr if logged or written
```

## Do not overbuild

MVP 6 is implementation-execution only. No PR creation, no review classification, no auto-cleanup of dirty worktrees, no provider-budget tracking, no QA orchestration, no scheduler. If a "useful" extra appears tempting, it belongs in MVP 7 or later.
