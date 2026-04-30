# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 5: Worktree Preparation

## Goal

Implement MVP 5: safe local-only Git worktree preparation for the Portfolio Manager plugin.

The final system must let Hermes plan, clone, refresh, and create one issue-specific Git worktree per call, inspect/list/explain worktree state, and persist the result to SQLite + local artifacts. It must never push, commit, open PRs, run coding harnesses, or modify GitHub remote state.

Source of truth: `docs/mvps/mvp5-spec.md`. Read it before starting any task. This file scopes the spec into small, ordered, test-first tasks with difficulty levels so an orchestrator can route each task to an appropriately-sized model.

---

## Difficulty Legend

Each task has a difficulty tier. The orchestrator should pick a model that matches:

```txt
L1 — easy / mechanical. Single-file edits, schema additions, CLI parser entries, doc files,
     fixed-shape tests. Low blast radius. Suitable for haiku-class models.

L2 — medium / scoped logic. New helpers + tests, multi-file changes, integration with
     existing modules. Moderate safety surface. Suitable for sonnet-class models.

L3 — hard / safety-critical. Git mutation orchestration, lock+idempotency state machines,
     security boundaries (path containment, command allowlists, redaction), crash recovery,
     E2E flows over real local repos. Suitable for opus-class models.
```

Rule of thumb: if the task can corrupt local state, escape `$ROOT/worktrees`, run a
forbidden command, or leak a secret on failure → L3.

---

## Agent-Readiness Verdict

Ready for a development agent **only after** MVP 4 is confirmed green.

Before implementing this file, the agent must run:

```bash
pytest
```

If MVP 1–4 tests fail, fix the regression first. Do not start MVP 5 on a failing baseline. If MVP 4 is still in an open PR branch, branch from that PR head only after confirming its tests pass.

Existing assumptions to honor:

```txt
Source layout is flat under portfolio_manager/ (see existing maintenance_*.py modules).
Tests live under tests/ as test_<area>.py.
Skills live under skills/<skill-name>/SKILL.md.
Locks use state.acquire_lock / release_lock (see admin_locks.py for the wrapper pattern).
Tool result shape uses status="success"|"skipped"|"blocked"|"failed" (MVP 4 convention).
Config root resolution: explicit arg > AGENT_SYSTEM_ROOT > Path.home() / ".agent-system".
Existing portfolio_manager/worktree.py already has discover_issue_worktrees and
inspect_worktree primitives — extend them, do not replace them.
```

---

## Non-Negotiable Rules

```txt
Test-first. Every task adds failing tests first, then implementation.
Preserve MVP 1–4 behavior.
shell=True is forbidden. Every subprocess call uses argument arrays + timeout + GIT_TERMINAL_PROMPT=0.
Only allowlisted git/gh commands (see spec § Allowed Commands). Reject everything else in the helper layer.
All paths must stay under $ROOT/worktrees. Symlink escapes blocked.
Branch names must match ^agent/[a-z0-9][a-z0-9_-]{1,63}/issue-[1-9][0-9]{0,9}$.
Default mutation tools to dry_run=true, confirm=false. Real mutation requires both flipped.
Plan / dry-run writes no SQLite and no artifacts.
Real runs write SQLite + artifacts; artifacts redact secrets.
Locks are always released in finally blocks. Lock contention returns blocked, not failed.
Idempotency only for exact matching clean worktree. Mismatch → blocked.
Never clean, reset, stash, force, or delete existing worktrees. If unsafe → blocked.
Never call gh issue create / gh pr * / git push / git commit / git rebase / git reset / git clean / git stash.
```

---

## Scope Boundary

### May mutate

```txt
$ROOT/worktrees/<project_id>/                       (clone of base repo)
$ROOT/worktrees/<project_id>-issue-<n>/             (issue worktree)
$ROOT/state/state.sqlite                            (worktrees + locks rows)
$ROOT/artifacts/worktrees/<project_id>/{base|issue-<n>}/   (audit artifacts)
```

### Must not mutate

```txt
GitHub remote state of any kind
project source files (Git's own .git metadata is OK)
existing dirty/conflicted worktrees
project policy files
maintenance config
```

---

## Shared Tool Result Format

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

`blocked` is preferred over guessing on ambiguity. `failed` is for unexpected exceptions after mutation started.

---

## Required New Tools

```txt
portfolio_worktree_plan
portfolio_worktree_prepare_base
portfolio_worktree_create_issue
portfolio_worktree_list
portfolio_worktree_inspect           (extend existing handler if present; keep MVP 1 behavior)
portfolio_worktree_explain
```

---

## Required Dev CLI Commands

```bash
python dev_cli.py worktree-plan --project-ref <p> --issue-number 42 --root /tmp/agent-system-test --json
python dev_cli.py worktree-prepare-base --project-ref <p> --dry-run true  --root /tmp/agent-system-test --json
python dev_cli.py worktree-prepare-base --project-ref <p> --dry-run false --confirm true --root /tmp/agent-system-test --json
python dev_cli.py worktree-create-issue --project-ref <p> --issue-number 42 --dry-run true  --root /tmp/agent-system-test --json
python dev_cli.py worktree-create-issue --project-ref <p> --issue-number 42 --dry-run false --confirm true --root /tmp/agent-system-test --json
python dev_cli.py worktree-list    --project-ref <p> --root /tmp/agent-system-test --json
python dev_cli.py worktree-inspect --project-ref <p> --issue-number 42 --root /tmp/agent-system-test --json
python dev_cli.py worktree-explain --project-ref <p> --issue-number 42 --root /tmp/agent-system-test --json
```

---

## Suggested Module Layout

Add as flat modules under `portfolio_manager/` (matches existing `maintenance_*.py` style). Do not invent a new sub-package unless an L3 task explicitly needs it.

```txt
portfolio_manager/worktree.py                 EXTEND  (already has inspect_worktree)
portfolio_manager/worktree_paths.py           NEW     (path containment, branch regex, URL normalize)
portfolio_manager/worktree_git.py             NEW     (allowlisted subprocess + read-only git probes)
portfolio_manager/worktree_state.py           NEW     (SQLite helpers, worktree id keys, optional ALTERs)
portfolio_manager/worktree_artifacts.py       NEW     (plan/result/error/summary writers + redaction)
portfolio_manager/worktree_locks.py           NEW     (project + issue lock context managers)
portfolio_manager/worktree_planner.py         NEW     (plan logic shared by plan + prepare + create tools)
portfolio_manager/worktree_prepare.py         NEW     (clone + safe refresh logic)
portfolio_manager/worktree_create.py          NEW     (issue worktree creation + idempotency)
portfolio_manager/worktree_reconcile.py       NEW     (crash-recovery comparison helper)
portfolio_manager/worktree_tools.py           NEW     (six tool handlers, thin wrappers)
portfolio_manager/schemas.py                  EXTEND  (six new pydantic input schemas)
portfolio_manager/tools.py                    EXTEND  (register six new tools)
dev_cli.py                                    EXTEND  (eight new CLI commands)
skills/worktree-prepare/SKILL.md              NEW
```

If equivalents already exist (e.g. a generic redaction helper), reuse them — do not duplicate.

---

# Phase 0 — Preflight and Discovery

## 0.1 Confirm baseline green  [L1]

Status: [x]

### Test first
Run the existing suite:
```bash
pytest
```

### Implementation
None. Diagnostic only. If failures exist that are unrelated to MVP 5, get user sign-off before proceeding.

### Acceptance
```txt
pytest exits 0, OR the user has explicitly accepted the baseline.
```

---

## 0.2 Inspect existing worktree + lock + artifact contracts  [L1]

Status: [x]

### Test first
None.

### Implementation
Read these files end-to-end and write a short scratchpad note (do NOT commit) mapping spec names → existing helpers:
```txt
portfolio_manager/worktree.py            (discover_issue_worktrees, inspect_worktree, _run_git)
portfolio_manager/state.py               (worktrees table, acquire_lock, release_lock, schema init)
portfolio_manager/admin_locks.py         (with_config_lock pattern — copy the shape, not the lock name)
portfolio_manager/maintenance_artifacts.py   (artifact path containment + redaction helpers — REUSE)
portfolio_manager/config.py              (project resolver, ProjectConfig)
portfolio_manager/issue_resolver.py      (project_ref resolution rules — REUSE)
dev_cli.py                               (existing command pattern, _to_bool helper)
```

### Acceptance
```txt
The implementer can name the existing helpers they will reuse and the helpers they must add.
No code changed.
```

---

## 0.3 Add structure tests for MVP 5 modules  [L1]

Status: [x]

### Test first
Add `tests/test_structure.py` cases (extend the existing file):
```txt
test_worktree_modules_exist            (imports for the 10 new portfolio_manager/worktree_*.py modules)
test_worktree_prepare_skill_folder_exists
test_worktree_tools_registered         (six tool names appear in tools.TOOLS or equivalent registry)
test_dev_cli_worktree_commands_registered  (eight CLI subcommands)
test_no_duplicate_tool_names
test_existing_portfolio_worktree_inspect_still_callable  (back-compat smoke)
```
Confirm they fail.

### Implementation
None beyond test additions. Optional minimal placeholder modules only if pytest cannot import the test file.

### Acceptance
```txt
Tests fail for missing MVP 5 functionality, not for unrelated import errors.
```

---

# Phase 1 — Validation Primitives (Pure Functions)

These are pure functions with no I/O. They are the security boundary. Get them right before anything else.

## 1.1 Branch name validator  [L1]

Status: [x]

### Test first
`tests/test_worktree_paths.py`:
```txt
test_default_branch_name_format        (agent/<project_id>/issue-<n>)
test_explicit_valid_branch_accepted
test_reject_leading_dash
test_reject_double_dot
test_reject_at_brace
test_reject_trailing_slash
test_reject_trailing_dot
test_reject_backslash
test_reject_space
test_reject_colon
test_reject_shell_metacharacters       ($ ` ; | & > < newline)
test_reject_absolute_path
test_reject_path_traversal
test_reject_refs_heads_prefix
test_reject_overlong_segment           (>64 chars after agent/)
test_reject_zero_or_negative_issue
```

### Implementation
Add to `portfolio_manager/worktree_paths.py`:
```python
BRANCH_REGEX = re.compile(r"^agent/[a-z0-9][a-z0-9_-]{1,63}/issue-[1-9][0-9]{0,9}$")
def default_branch_name(project_id: str, issue_number: int) -> str: ...
def validate_branch_name(name: str) -> str: ...   # returns name or raises ValueError
```

### Acceptance
```txt
All tests pass. Validator never accepts a string the regex would reject.
No filesystem or subprocess calls.
```

---

## 1.2 Path containment + symlink escape guard  [L2]

Status: [x]

### Test first
`tests/test_worktree_paths.py` (continued):
```txt
test_path_inside_root_accepted
test_path_outside_root_rejected
test_relative_path_resolves_under_root
test_dotdot_traversal_rejected
test_symlink_inside_root_to_inside_root_accepted
test_symlink_inside_root_escaping_root_rejected
test_pattern_substitution_rejects_non_integer_issue
test_pattern_substitution_rejects_curly_injection
```
Use `tmp_path` and `os.symlink` in tests.

### Implementation
Add to `portfolio_manager/worktree_paths.py`:
```python
def resolve_under_root(path: Path, root: Path) -> Path: ...
    # path.resolve(strict=False).is_relative_to(root.resolve())
def assert_under_worktrees_root(path: Path, root: Path) -> Path: ...
def render_issue_worktree_path(pattern: str, project_id: str, issue_number: int, root: Path) -> Path: ...
def has_escaping_symlink(path: Path, root: Path) -> bool: ...
```

### Acceptance
```txt
Symlink escapes are caught. Pattern substitution accepts only validated int issue numbers.
```

---

## 1.3 Remote URL normalizer  [L2]

Status: [x]

### Test first
`tests/test_worktree_paths.py` (continued):
```txt
test_https_with_dot_git
test_https_without_dot_git
test_ssh_at_form
test_ssh_scheme_form
test_trailing_slash_normalized
test_local_file_scheme_normalized
test_local_absolute_path_normalized
test_different_owner_does_not_match
test_different_host_does_not_match
test_different_repo_does_not_match
test_credentials_in_url_redacted_for_artifact_form
```

### Implementation
Add to `portfolio_manager/worktree_paths.py`:
```python
def normalize_remote_url(url: str) -> str: ...     # returns "github:owner/repo" or local-resolved
def remotes_equal(a: str, b: str) -> bool: ...
def redact_remote_url(url: str) -> str: ...        # strips userinfo before artifact write
```

### Acceptance
```txt
Equivalent forms compare equal. Different forms compare unequal. Token-bearing URLs never
appear verbatim in artifact-bound output.
```

---

# Phase 2 — Allowlisted Git Runner + Read-Only Probes

## 2.1 Allowlisted subprocess wrapper  [L2]

Status: [x]

### Test first
`tests/test_worktree_git.py`:
```txt
test_run_git_uses_argument_array
test_run_git_sets_GIT_TERMINAL_PROMPT_zero
test_run_git_applies_timeout_per_command
test_run_git_rejects_non_allowlisted_subcommand
test_run_git_redacts_credentials_in_stderr_capture
test_run_gh_only_allows_get_methods             (no --method POST/PATCH/DELETE)
```

### Implementation
Add `portfolio_manager/worktree_git.py`:
```python
ALLOWED_GIT = {("--version",), ("rev-parse", ...), ("status", "--porcelain=v1"),
               ("remote", "get-url", "origin"), ("worktree", "list", "--porcelain"),
               ("branch", "--show-current"), ("for-each-ref", ...),
               ("clone", ...), ("fetch", "origin", ..., "--prune"),
               ("switch", ...), ("merge", "--ff-only", ...),
               ("worktree", "add", ..., "-b", ..., ...) }   # represent as a check function
def run_git(args: list[str], cwd: Path, timeout: int) -> CompletedProcess: ...
```
Reuse `portfolio_manager/worktree.py::_run_git` shape. Centralize the allowlist check here so security tests can target one module.

### Acceptance
```txt
Forbidden subcommands raise before subprocess starts. Timeouts respect spec defaults
(status/rev-parse 30s, fetch 120s, clone 300s, worktree add 120s).
```

---

## 2.2 Read-only git probes  [L2]

Status: [x]

### Test first
`tests/test_worktree_git.py` (use a local bare repo fixture, see Task 14.1):
```txt
test_is_git_repo_true_for_clone
test_is_git_repo_false_for_plain_dir
test_get_remote_url_returns_origin
test_clean_state_for_fresh_clone
test_dirty_uncommitted_for_modified_tracked_file
test_dirty_untracked_for_new_file
test_merge_conflict_state_detected
test_rebase_conflict_state_detected
test_branch_exists_local
test_branch_exists_origin
test_local_branch_has_commits_not_in_origin
test_worktree_list_porcelain_parsed
```

### Implementation
Add to `portfolio_manager/worktree_git.py`:
```python
def get_clean_state(path: Path) -> Literal["clean","dirty_uncommitted","dirty_untracked","merge_conflict","rebase_conflict"]: ...
def get_origin_url(path: Path) -> str | None: ...
def branch_exists(path: Path, name: str, *, remote: bool=False) -> bool: ...
def local_branch_diverges_from_origin(path: Path, branch: str) -> bool: ...
def list_worktrees(repo_path: Path) -> list[dict]: ...
```
Where existing `worktree.py` already has equivalents (`_run_git`, porcelain parsing), import and reuse — do not duplicate.

### Acceptance
```txt
Probes are pure read-only. They never write to the repo.
```

---

# Phase 3 — Schema and State Helpers

## 3.1 Worktree id keys + (optional) additive columns  [L2]

Status: [x]

### Test first
`tests/test_worktree_state.py`:
```txt
test_base_worktree_id_format            (returns "base:<project_id>")
test_issue_worktree_id_format           (returns "issue:<project_id>:<issue_number>")
test_schema_init_idempotent_after_mvp5_changes
test_existing_worktrees_rows_still_readable_after_init
```

### Implementation
Add `portfolio_manager/worktree_state.py`:
```python
def base_worktree_id(project_id: str) -> str: ...
def issue_worktree_id(project_id: str, issue_number: int) -> str: ...
```

Only add ALTER columns if Phase 6/7/8 logic genuinely needs them. Candidates from spec:
```sql
ALTER TABLE worktrees ADD COLUMN remote_url TEXT;
ALTER TABLE worktrees ADD COLUMN head_sha TEXT;
ALTER TABLE worktrees ADD COLUMN base_sha TEXT;
ALTER TABLE worktrees ADD COLUMN preparation_artifact_path TEXT;
```
Migration must be idempotent (`PRAGMA table_info(worktrees)` check before ALTER) and backward-compatible. If you add columns, add them to `state.SCHEMA_SQL` initialization too.

### Acceptance
```txt
Existing MVP 1–4 state tests still pass. ALTERs run at most once.
```

---

## 3.2 Worktree state upsert + read helpers  [L2]

Status: [x]

### Test first
`tests/test_worktree_state.py` (continued):
```txt
test_upsert_base_worktree_row_inserts
test_upsert_base_worktree_row_updates_existing
test_upsert_issue_worktree_row_inserts
test_upsert_issue_worktree_row_updates_existing
test_get_worktree_by_id_returns_row
test_list_worktrees_for_project_filters_correctly
test_state_value_must_be_in_allowed_set
```
Allowed states (from spec):
```txt
missing, planned, cloning, ready, clean, dirty_untracked, dirty_uncommitted,
merge_conflict, rebase_conflict, blocked, failed
```

### Implementation
Helpers in `portfolio_manager/worktree_state.py`:
```python
def upsert_base_worktree(conn, *, project_id, path, branch_name, base_branch, state, dirty_summary, ...): ...
def upsert_issue_worktree(conn, *, project_id, issue_number, path, branch_name, base_branch, state, ...): ...
def get_worktree(conn, worktree_id: str) -> dict | None: ...
def list_worktrees_for_project(conn, project_id: str) -> list[dict]: ...
```

### Acceptance
```txt
Upserts are idempotent on the worktree id key. Invalid state values rejected.
```

---

# Phase 4 — Artifacts

## 4.1 Artifact path helpers  [L1]

Status: [x]

### Test first
`tests/test_worktree_artifacts.py`:
```txt
test_base_artifact_dir_under_root
test_issue_artifact_dir_under_root
test_artifact_dir_rejects_path_traversal_in_project_id
test_artifact_dir_rejects_negative_issue_number
test_dry_run_does_not_create_artifact_dir
```

### Implementation
Add `portfolio_manager/worktree_artifacts.py`:
```python
def base_artifact_dir(root: Path, project_id: str) -> Path:
    # $ROOT/artifacts/worktrees/<project_id>/base/
def issue_artifact_dir(root: Path, project_id: str, issue_number: int) -> Path:
    # $ROOT/artifacts/worktrees/<project_id>/issue-<n>/
```

### Acceptance
```txt
Paths always contained under root/artifacts/worktrees.
```

---

## 4.2 Artifact writers + redaction  [L2]

Status: [x]

### Test first
`tests/test_worktree_artifacts.py` (continued):
```txt
test_plan_json_shape_for_real_run
test_commands_json_shape
test_preflight_json_shape
test_result_json_shape_on_success
test_inspection_json_shape
test_error_json_shape_redacts_token_in_stderr
test_summary_md_is_public_safe_no_token_no_local_path_secrets
test_dry_run_writes_no_artifact_files
test_remote_url_redacted_in_all_artifacts
```

### Implementation
Writers in `portfolio_manager/worktree_artifacts.py`:
```python
def write_plan(dir: Path, plan: dict) -> Path: ...
def write_commands(dir: Path, commands: list[list[str]]) -> Path: ...
def write_preflight(dir: Path, preflight: dict) -> Path: ...
def write_result(dir: Path, result: dict) -> Path: ...
def write_inspection(dir: Path, inspection: dict) -> Path: ...
def write_error(dir: Path, error: dict) -> Path: ...
def write_summary_md(dir: Path, summary_md: str) -> Path: ...
```
Reuse the existing redaction helper from `maintenance_artifacts.py` if present. Otherwise add a minimal redactor that strips `https://*:*@`, GitHub tokens (`ghp_*`, `github_pat_*`), and known env var names.

### Acceptance
```txt
No artifact ever contains a credential, token, or env var value.
```

---

# Phase 5 — Locks

## 5.1 Worktree lock context managers  [L2]

Status: [ ]

### Test first
`tests/test_worktree_locks.py`:
```txt
test_project_lock_acquired_and_released
test_issue_lock_acquired_and_released
test_locks_acquired_in_stable_order_project_then_issue
test_lock_released_on_exception
test_lock_contention_raises_typed_error_for_blocked_translation
test_expired_lock_can_be_stolen          (via existing acquire_lock CAS behavior)
test_default_ttl_is_15_minutes
```

### Implementation
Add `portfolio_manager/worktree_locks.py`. Mirror `admin_locks.with_config_lock` shape:
```python
PROJECT_LOCK_TTL = 15 * 60
def with_project_lock(conn, project_id: str): ...           # name = worktree:project:<id>
def with_issue_lock(conn, project_id: str, issue_number: int): ...  # worktree:issue:<id>:<n>
def with_project_and_issue_locks(conn, project_id, issue_number): ...
```
On contention, raise a typed exception (e.g. `WorktreeLockBusy`) so handlers translate to `status="blocked"`, never `failed`.

### Acceptance
```txt
Locks always released in finally. Stable acquisition order. Contention → blocked.
```

---

# Phase 6 — Plan Tool (Read-Only)

## 6.1 Plan input schema  [L1]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_plan_schema_requires_project_ref_and_issue_number
test_plan_schema_defaults_refresh_base_true
test_plan_schema_rejects_negative_issue_number
test_plan_schema_accepts_optional_branch_name
test_plan_schema_accepts_optional_base_branch
test_plan_schema_accepts_optional_root
```

### Implementation
Add to `portfolio_manager/schemas.py`:
```python
class WorktreePlanInput(BaseModel):
    project_ref: str
    issue_number: int = Field(gt=0)
    base_branch: str | None = None
    branch_name: str | None = None
    refresh_base: bool = True
    root: str | None = None
```

### Acceptance
```txt
Schema validates per spec § Tool Specifications.
```

---

## 6.2 Plan logic (pure)  [L3]

Status: [ ]

### Test first
`tests/test_worktree_planner.py`:
```txt
test_plan_returns_expected_paths_and_branch
test_plan_uses_configured_issue_worktree_pattern
test_plan_resolves_explicit_base_branch
test_plan_resolves_configured_default_branch
test_plan_blocks_when_default_branch_auto_unresolvable
test_plan_warns_when_issue_missing_from_local_sqlite
test_plan_blocks_invalid_issue_number
test_plan_blocks_invalid_branch_name
test_plan_blocks_path_escape_via_pattern
test_plan_detects_existing_clean_matching_worktree_as_skipped
test_plan_detects_existing_dirty_worktree_as_blocked
test_plan_detects_existing_branch_without_matching_worktree_as_blocked
test_plan_detects_remote_url_mismatch_as_blocked
test_plan_writes_no_sqlite_no_artifacts
```

### Implementation
Add `portfolio_manager/worktree_planner.py`:
```python
@dataclass
class WorktreePlan:
    project_id: str
    issue_number: int
    base_path: Path
    issue_worktree_path: Path
    base_branch: str
    branch_name: str
    would_clone_base: bool
    would_refresh_base: bool
    would_create_worktree: bool
    warnings: list[str]
    commands: list[list[str]]
    blocked_reasons: list[str]   # empty if not blocked

def build_plan(conn, project_ref: str, issue_number: int, *,
               base_branch: str | None, branch_name: str | None,
               refresh_base: bool, root: Path) -> WorktreePlan: ...
```
Use the existing project resolver, the new path/branch validators, and the read-only git probes. **No mutation, no SQLite writes, no artifact writes.**

### Acceptance
```txt
Plan returns a fully-typed structure for every spec input.
All blocked cases listed in spec § portfolio_worktree_plan are covered.
Plan never writes anywhere.
```

---

## 6.3 Plan tool handler  [L2]

Status: [ ]

### Test first
`tests/test_worktree_tools.py` (continued):
```txt
test_plan_tool_returns_success_for_clean_path
test_plan_tool_returns_blocked_with_reason
test_plan_tool_returns_skipped_for_existing_matching_clean_worktree
test_plan_tool_summary_is_telegram_friendly
test_plan_tool_does_not_persist_state
```

### Implementation
Thin handler in `portfolio_manager/worktree_tools.py`:
```python
def portfolio_worktree_plan(input: WorktreePlanInput) -> dict: ...
```
Validate input → resolve root → open conn → call `build_plan` → translate to shared result shape. Register in `tools.py`.

### Acceptance
```txt
Handler is < 40 lines. Logic lives in the planner.
```

---

# Phase 7 — Prepare Base Tool (Mutation)

## 7.1 Prepare-base input schema  [L1]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_prepare_base_schema_defaults_dry_run_true_and_confirm_false
test_prepare_base_schema_rejects_confirm_without_dry_run_false
```

### Implementation
Add to `schemas.py`:
```python
class WorktreePrepareBaseInput(BaseModel):
    project_ref: str
    base_branch: str | None = None
    refresh_base: bool = True
    dry_run: bool = True
    confirm: bool = False
    root: str | None = None
```

### Acceptance
```txt
Defaults match spec.
```

---

## 7.2 Clone-if-missing logic  [L2]

Status: [ ]

### Test first
`tests/test_worktree_prepare.py`:
```txt
test_clone_runs_only_when_confirm_true_and_path_missing
test_clone_target_path_must_be_under_root_worktrees
test_clone_uses_argument_array_no_shell
test_clone_failure_writes_error_artifact_and_removes_only_empty_dirs
test_clone_remote_url_must_match_project_config_after_clone
test_clone_blocks_when_path_exists_non_empty_non_git
```

### Implementation
Add `portfolio_manager/worktree_prepare.py::clone_base_repo(...)`. Use `worktree_git.run_git(["clone", url, str(path)], ...)`. Verify post-clone remote with `normalize_remote_url` + `remotes_equal`.

### Acceptance
```txt
Clone never runs without confirm=true. Bad post-clone remote triggers blocked + cleanup.
```

---

## 7.3 Safe base-branch refresh logic  [L3]

Status: [ ]

### Test first
`tests/test_worktree_prepare.py` (continued):
```txt
test_refresh_blocked_when_base_repo_dirty
test_refresh_blocked_when_in_merge_state
test_refresh_blocked_when_in_rebase_state
test_refresh_blocked_when_remote_mismatches
test_refresh_blocked_when_on_unexpected_branch_and_not_clean
test_refresh_switches_to_existing_local_base_branch_when_clean
test_refresh_blocks_when_local_base_branch_missing_and_repo_was_not_just_cloned
test_refresh_runs_fetch_then_ff_only
test_refresh_blocks_when_local_branch_has_commits_not_in_origin
test_refresh_returns_failed_with_error_artifact_when_fetch_fails
test_refresh_does_NOT_rebase_or_reset_on_ff_failure
```

### Implementation
Add `worktree_prepare.py::refresh_base_branch(...)`. Sequence: clean check → state check (merge/rebase) → remote match → branch resolution → ancestry check (`git merge-base --is-ancestor`) → `git fetch origin <b> --prune` → `git merge --ff-only origin/<b>`. Every command goes through `worktree_git.run_git`.

### Acceptance
```txt
No path escapes ff-only semantics. Divergence → blocked, never auto-resolved.
```

---

## 7.4 Prepare-base handler with locks + artifacts  [L3]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_prepare_base_dry_run_returns_plan_no_mutation
test_prepare_base_confirm_false_blocks_real_run
test_prepare_base_real_run_acquires_project_lock
test_prepare_base_real_run_writes_plan_commands_result_artifacts
test_prepare_base_real_run_updates_sqlite_base_worktree_row
test_prepare_base_lock_contention_returns_blocked
test_prepare_base_handler_releases_lock_on_exception
```

### Implementation
`worktree_tools.py::portfolio_worktree_prepare_base`. Pseudocode:
```python
plan = build_plan(...)
if dry_run: return success(plan)
if not confirm: return blocked("confirm=false")
if plan.blocked_reasons: return blocked(plan.blocked_reasons)
with with_project_lock(conn, project_id):
    write_artifacts(plan, ...)
    cloned = clone_base_repo(...) if plan.would_clone_base else False
    refreshed = refresh_base_branch(...) if plan.would_refresh_base else False
    inspection = inspect_base(...)
    upsert_base_worktree(conn, ..., state=inspection.state)
    write_result(...)
    return success(...)
```

### Acceptance
```txt
All side effects are gated by both dry_run=false AND confirm=true.
Lock always released. Artifacts written for real runs only.
```

---

# Phase 8 — Create Issue Worktree Tool (Mutation)

## 8.1 Create-issue input schema  [L1]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_create_issue_schema_defaults_dry_run_true_confirm_false
test_create_issue_schema_validates_issue_number_positive
```

### Implementation
Add to `schemas.py`: `WorktreeCreateIssueInput` mirroring spec § 3.

### Acceptance
```txt
Defaults match spec.
```

---

## 8.2 Idempotency check (the hard part)  [L3]

Status: [ ]

### Test first
`tests/test_worktree_create.py`:
```txt
test_idempotency_skipped_for_exact_matching_clean_worktree
test_idempotency_blocks_when_path_exists_with_wrong_remote
test_idempotency_blocks_when_path_exists_with_wrong_branch
test_idempotency_blocks_when_path_exists_dirty
test_idempotency_blocks_when_path_exists_in_merge_conflict
test_idempotency_blocks_when_path_exists_non_git
test_idempotency_blocks_when_branch_exists_without_matching_worktree
test_idempotency_blocks_when_sqlite_disagrees_with_filesystem
test_idempotency_consults_git_worktree_list_porcelain
```

### Implementation
Add `portfolio_manager/worktree_create.py::check_idempotency(...)` returning one of:
```python
("skipped", inspection)   # exact match, clean — return success
("create",  None)          # safe to create
("blocked", reason)        # any mismatch
```
The check must consult, in order: SQLite row, filesystem path existence, `git worktree list --porcelain`, branch existence, remote URL match.

### Acceptance
```txt
Tests cover every outcome path. No mutation in this function.
```

---

## 8.3 Create worktree command  [L2]

Status: [ ]

### Test first
`tests/test_worktree_create.py` (continued):
```txt
test_create_uses_worktree_add_with_b_flag
test_create_uses_origin_base_branch_as_start_point
test_create_post_create_inspection_is_clean
test_create_failure_writes_error_artifact_and_does_not_delete_target
test_create_does_not_attach_existing_branch
```

### Implementation
`worktree_create.py::create_issue_worktree(base_repo_path, issue_path, branch_name, base_branch)` runs:
```
git worktree add <issue_path> -b <branch_name> origin/<base_branch>
```
through `run_git` with the worktree-add timeout (120s). Post-create inspection via existing `worktree.inspect_worktree`.

### Acceptance
```txt
Single allowlisted command runs. No fallback strategy attaches an existing branch.
```

---

## 8.4 Create-issue handler with both locks + artifacts  [L3]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_create_issue_dry_run_returns_plan_no_mutation
test_create_issue_confirm_false_blocks
test_create_issue_real_run_acquires_project_then_issue_locks
test_create_issue_real_run_calls_prepare_base_first
test_create_issue_real_run_writes_artifacts
test_create_issue_real_run_upserts_issue_worktree_row
test_create_issue_repeat_call_returns_skipped_success
test_create_issue_locks_released_on_exception
test_create_issue_lock_contention_returns_blocked
test_create_issue_does_NOT_create_github_issue
test_create_issue_does_NOT_run_npm_pnpm_yarn_pip_make_pytest
```

### Implementation
`worktree_tools.py::portfolio_worktree_create_issue`. Sequence:
```
build_plan → dry_run/confirm gates → with_project_lock → with_issue_lock →
  prepare base (reuse Phase 7 helpers) → check_idempotency →
  branch on outcome (skipped/create/blocked) → upsert SQLite → write artifacts → return
```

### Acceptance
```txt
Spec § portfolio_worktree_create_issue blocked cases all return blocked, never failed.
No forbidden command can be reached from this code path (verified by Phase 13 tests).
```

---

# Phase 9 — Inspect / List / Explain

## 9.1 Extend portfolio_worktree_inspect (back-compat)  [L2]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_inspect_existing_mvp1_call_signature_still_works
test_inspect_with_issue_number_inspects_expected_issue_worktree
test_inspect_with_explicit_path_validates_containment
test_inspect_without_issue_or_path_inspects_base_repo
test_inspect_persists_state_to_sqlite
test_inspect_blocks_path_outside_worktrees_root
```

### Implementation
Locate the existing `portfolio_worktree_inspect` handler (likely in `tools.py`). Extend its schema with optional `issue_number`, `path`. Branch logic accordingly. Reuse `worktree.inspect_worktree`. **Do not change MVP 1 behavior when called with the original arguments.**

### Acceptance
```txt
MVP 1 inspect tests still pass unchanged. New parameters work as specified.
```

---

## 9.2 portfolio_worktree_list  [L2]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_list_returns_all_projects_when_project_ref_omitted
test_list_filters_by_project_ref_when_provided
test_list_excludes_archived_paused_by_default
test_list_includes_archived_when_flag_set
test_list_with_inspect_true_persists_inspection_to_sqlite
test_list_with_inspect_false_writes_no_sqlite
```

### Implementation
Add schema `WorktreeListInput` and handler in `worktree_tools.py`. Reuse `worktree.discover_issue_worktrees` and the new probes.

### Acceptance
```txt
Side effect (SQLite) only when inspect=true.
```

---

## 9.3 portfolio_worktree_explain  [L2]

Status: [ ]

### Test first
`tests/test_worktree_tools.py`:
```txt
test_explain_for_ready_worktree_returns_clean_message
test_explain_for_dirty_worktree_returns_dirty_summary
test_explain_for_missing_worktree_suggests_create
test_explain_for_conflicted_worktree_suggests_no_unsafe_action
test_explain_does_not_mutate_repo
```

### Implementation
Add schema + handler. Output a short paragraph + a `next_safe_action` string ∈ {`plan`, `prepare_base`, `create`, `none`}.

### Acceptance
```txt
Always read-only at filesystem level. Optional SQLite inspection update is allowed.
```

---

# Phase 10 — Crash Recovery / Reconcile

## 10.1 worktree_reconcile helper  [L3]

Status: [ ]

### Test first
`tests/test_worktree_reconcile.py`:
```txt
test_reconcile_returns_skipped_when_already_prepared_cleanly
test_reconcile_blocks_on_partial_state_path_exists_no_sqlite
test_reconcile_blocks_on_partial_state_sqlite_exists_no_path
test_reconcile_blocks_on_remote_url_drift
test_reconcile_blocks_on_branch_drift
test_reconcile_does_not_mutate_repo
test_reconcile_updates_sqlite_to_filesystem_truth_when_safe
```

### Implementation
Add `portfolio_manager/worktree_reconcile.py`:
```python
def worktree_reconcile(conn, project_id: str, issue_number: int | None, root: Path) -> dict: ...
```
Compares: SQLite row, filesystem path, `git worktree list`, current branch, remote URL, clean state. Never deletes or resets anything.

### Acceptance
```txt
Reconcile is safe to call before any mutation tool to recover from prior crashes.
```

---

# Phase 11 — Dev CLI

## 11.1 Add CLI parser entries  [L1]

Status: [ ]

### Test first
`tests/test_dev_cli.py`:
```txt
test_cli_registers_worktree_plan
test_cli_registers_worktree_prepare_base
test_cli_registers_worktree_create_issue
test_cli_registers_worktree_list
test_cli_registers_worktree_inspect
test_cli_registers_worktree_explain
```

### Implementation
Extend `dev_cli.py` with the eight subcommands listed in the Required Dev CLI Commands section. Reuse existing `_to_bool`, `--root`, `--json` flag patterns.

### Acceptance
```txt
All commands print valid JSON shared result objects when invoked with --json.
```

---

## 11.2 CLI behavior tests with test root  [L1]

Status: [ ]

### Test first
`tests/test_dev_cli.py`:
```txt
test_cli_worktree_plan_returns_blocked_for_unknown_project
test_cli_worktree_list_returns_empty_array_for_empty_root
test_cli_worktree_inspect_blocks_path_outside_root
```

### Implementation
Wire CLI commands to handlers. No new logic.

### Acceptance
```txt
JSON exit code and shape match shared result format.
```

---

# Phase 12 — Hermes Skill Documentation

## 12.1 Add `worktree-prepare` skill folder  [L1]

Status: [ ]

### Test first
`tests/test_worktree_skill.py` (new file) or extend `test_skills.py`:
```txt
test_worktree_prepare_skill_md_exists
test_skill_mentions_plan_first
test_skill_mentions_dry_run_then_confirm
test_skill_mentions_blocked_over_guessing
test_skill_lists_six_expected_tools
test_skill_warns_no_implementation_agents_in_mvp5
test_skill_warns_no_github_remote_mutation
```

### Implementation
Create `skills/worktree-prepare/SKILL.md`. Include guidance sections from spec § Hermes Skill Requirements and the example interactions.

### Acceptance
```txt
A Hermes agent reading this skill cannot reasonably skip plan-first or confirm-required behavior.
```

---

# Phase 13 — Security Hardening Tests

## 13.1 Branch validation security tests  [L1]

Status: [ ]

### Test first
`tests/test_security.py` (extend):
```txt
test_branch_with_double_dot_rejected_at_handler_layer
test_branch_with_at_brace_rejected_at_handler_layer
test_branch_with_leading_dash_rejected_at_handler_layer
test_branch_with_shell_metachar_rejected_at_handler_layer
test_branch_with_refs_heads_prefix_rejected_at_handler_layer
```
These re-verify Phase 1.1 rules at the tool boundary, not just the validator.

### Acceptance
```txt
Bad branch names cannot reach run_git via any tool path.
```

---

## 13.2 Path / symlink escape tests  [L2]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_issue_worktree_pattern_escape_blocked_at_tool_layer
test_symlink_under_worktrees_to_outside_blocked_at_tool_layer
test_artifact_dir_path_traversal_blocked
test_inspect_path_outside_root_blocked
```

### Acceptance
```txt
No tool path can escape $ROOT/worktrees.
```

---

## 13.3 Command allowlist tests  [L2]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_no_shell_true_in_worktree_modules         (grep portfolio_manager/worktree_*.py)
test_only_allowlisted_git_subcommands_in_worktree_modules
test_no_gh_issue_create_referenced_in_worktree_modules
test_no_git_push_commit_reset_clean_stash_rebase_referenced
test_no_npm_pnpm_yarn_pip_cargo_make_pytest_referenced
```
Implement these as static-grep tests over the new module files.

### Acceptance
```txt
Forbidden commands cannot be introduced without breaking a security test.
```

---

## 13.4 Secret redaction tests  [L1]

Status: [ ]

### Test first
`tests/test_security.py`:
```txt
test_https_token_in_remote_url_redacted_in_artifacts
test_ghp_token_in_stderr_redacted_in_error_json
test_env_variable_value_not_written_to_summary_md
test_no_chain_of_thought_marker_in_artifacts
```

### Acceptance
```txt
No artifact contains a secret. Verified by automated pattern checks.
```

---

# Phase 14 — Local E2E with Bare Repos

E2E tests must use **local temporary Git repos**, never real GitHub. Create a single fixture and reuse it.

## 14.1 Local bare-repo fixture  [L2]

Status: [ ]

### Test first
None (this task is the fixture itself).

### Implementation
Add to `tests/fixtures/` (create file e.g. `worktree_fixtures.py`):
```python
@pytest.fixture
def bare_remote(tmp_path) -> Path:
    """Create a bare git repo at tmp_path/origin.git with one initial commit on main."""
    ...

@pytest.fixture
def projects_yaml_pointing_to_bare_remote(bare_remote, tmp_path) -> Path:
    """Write a projects.yaml under tmp_path/config/ with file:// remote URL."""
    ...
```
Use `subprocess.run(["git", "init", "--bare", ...])` etc. No network.

### Acceptance
```txt
Fixtures usable by all E2E tests below. No network access needed.
```

---

## 14.2 E2E: prepare base end-to-end  [L2]

Status: [ ]

### Test first
`tests/test_worktree_e2e.py`:
```txt
test_e2e_prepare_base_dry_run_no_side_effects
test_e2e_prepare_base_clones_when_missing_with_confirm
test_e2e_prepare_base_ff_refresh_when_remote_advanced
test_e2e_prepare_base_blocks_when_local_base_dirty
```

### Implementation
Call the tool handler (not the CLI) against the bare remote fixture.

### Acceptance
```txt
Real clone + ff happen exactly once with confirm; blocked paths report dirty/conflict cleanly.
```

---

## 14.3 E2E: create issue worktree + idempotency  [L3]

Status: [ ]

### Test first
`tests/test_worktree_e2e.py`:
```txt
test_e2e_create_issue_worktree_creates_branch_and_path
test_e2e_create_issue_worktree_writes_sqlite_row
test_e2e_create_issue_worktree_writes_artifacts
test_e2e_repeat_create_returns_skipped_success
test_e2e_create_blocks_when_target_branch_exists_without_matching_worktree
```

### Acceptance
```txt
Repeat call is a no-op. Mismatched branch state always blocks.
```

---

## 14.4 E2E: dirty / conflict / divergence block paths  [L3]

Status: [ ]

### Test first
`tests/test_worktree_e2e.py`:
```txt
test_e2e_create_blocks_when_existing_issue_worktree_dirty
test_e2e_prepare_base_blocks_when_base_repo_in_merge_state
test_e2e_prepare_base_blocks_when_local_branch_diverges_from_origin
test_e2e_prepare_base_blocks_when_remote_url_mismatches_config
```
For divergence test: in the local clone, make a commit that origin doesn't have, then assert ff-only blocks.

### Acceptance
```txt
Every block path returns status="blocked" with a clear reason. Never status="failed". No
state mutated beyond inspection rows.
```

---

# Phase 15 — Full Regression + Docs

## 15.1 Full pytest  [L1]

Status: [ ]

### Test first
Run the full suite:
```bash
pytest
```

### Implementation
Fix any regressions in MVP 1–4 behavior introduced by MVP 5.

### Acceptance
```txt
pytest exits 0 with no skipped MVP 5 tests.
```

---

## 15.2 Update handoff status  [L1]

Status: [ ]

### Test first
None.

### Implementation
Update `docs/product/project-handoff.md` MVP 5 row only after Phase 14 + 15.1 are green. Mark MVP 5 implemented; do **not** claim manual smoke until Phase 15.3 is run.

### Acceptance
```txt
Handoff doc reflects actual implementation state.
```

---

## 15.3 Manual smoke (deferred to user)  [L1]

Status: [ ]

### Test first
Automated tests must already pass.

### Implementation
Run the spec § Manual Hermes Smoke Tests against a `/tmp/agent-system-test` root with the local bare-repo fixture (or a sandbox project the user designates). Report pass/fail per smoke step.

### Acceptance
```txt
All five smoke prompts in spec § Manual Hermes Smoke Tests behave as expected.
```

---

# Definition of Done

MVP 5 is complete when:

```txt
All MVP 1–4 tests still pass.
All MVP 5 tests pass.
Six new tools registered: plan, prepare_base, create_issue, list, inspect (extended), explain.
Eight new dev_cli subcommands work and return shared result JSON.
skills/worktree-prepare/SKILL.md exists and instructs plan-first + confirm-required behavior.
Plan / dry-run never write SQLite or artifacts.
Real runs write SQLite worktree rows and per-run artifacts; artifacts redact secrets.
All paths contained under $ROOT/worktrees; symlink escapes blocked.
All git/gh commands go through the allowlist; shell=True grep-test passes.
Branch names match the spec regex; security tests cover the bad-input list.
Locks always released; contention returns blocked, not failed.
Idempotency only succeeds for exact matching clean worktree; everything else blocks.
No GitHub remote mutation. No coding harness. No npm/pnpm/yarn/pip/cargo/make/pytest in worktree code paths.
docs/product/project-handoff.md updated to reflect MVP 5 implemented.
```

---

# Suggested Implementation Order

```txt
0.1 → 0.2 → 0.3                         baseline + structure
1.1 → 1.2 → 1.3                         pure validators
2.1 → 2.2                               git runner + probes
3.1 → 3.2                               schema + state helpers
4.1 → 4.2                               artifacts
5.1                                     locks
6.1 → 6.2 → 6.3                         plan tool (read-only first)
7.1 → 7.2 → 7.3 → 7.4                   prepare base
8.1 → 8.2 → 8.3 → 8.4                   create issue worktree
9.1 → 9.2 → 9.3                         inspect / list / explain
10.1                                    crash recovery
11.1 → 11.2                             dev CLI
12.1                                    skill docs
13.1 → 13.2 → 13.3 → 13.4               security hardening
14.1 → 14.2 → 14.3 → 14.4               E2E
15.1 → 15.2 → 15.3                      regression + docs + smoke
```

A "dumber" agent should pick exactly one task at a time, read its tests-first block, write the failing tests, get them failing for the right reason, then implement until green. Do not bundle tasks. Do not refactor unrelated code. Status checkbox flips to `[x]` only when the task's verification step passes.

---

# Implementation Notes

## Keep handlers thin

Tool handlers should only:
```txt
validate input → resolve root → open conn → call tested helpers → return shared result
```
Core behavior belongs in `worktree_planner.py`, `worktree_prepare.py`, `worktree_create.py`, etc.

## Prefer controlled outcomes

Use `blocked` / `skipped` / `failed` instead of uncaught exceptions. Translate typed exceptions (`WorktreeLockBusy`, branch validation errors) at the handler boundary.

## Subprocess discipline

Every git/gh call goes through `worktree_git.run_git` / `run_gh`. Each call must have:
```txt
argument array (no shell=True)
explicit timeout
GIT_TERMINAL_PROMPT=0 in env
allowlist check before exec
redacted stderr if logged or written
```

## Do not overbuild

MVP 5 is path-creation only. No coding harness, no dependency install, no test execution inside managed repos, no PR/issue/branch mutation on the remote, no auto-cleanup of dirty worktrees, no branch repair. If a "useful" extra appears tempting, it belongs in MVP 6 or later.
