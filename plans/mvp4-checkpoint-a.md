# MVP 4 Checkpoint A: Schema + Config + Registry + Models + Built-in Skills

## Context

You are implementing MVP 4 of the Hermes Portfolio Manager plugin: **Maintenance Skills**.

Read these files FIRST:
- `docs/mvps/mvp4-spec.md` — full specification
- `docs/mvps/mvp4-progress.md` — phased implementation plan with test-first tasks

The baseline is 471 passing tests on MVPs 1-3. Do NOT break existing tests.

## What to implement in this checkpoint

Implement PROGRESS_4 Phases 0 through 2, covering tasks 0.1 through 2.7.

### Phase 0 — Preflight

**0.1** Baseline pytest already green (471 tests). Skip.

**0.2** Inspect actual package layout. You already know the layout from context.

**0.3** Add structure tests as failing tests for MVP 4 modules/skills/tools/CLI.

### Phase 1 — State, Schema, Config Foundations

**1.1** Add SQLite schema for `maintenance_runs` and `maintenance_findings` tables to existing `state.py` SCHEMA_SQL. Add indexes. Tests must verify idempotent creation.

**1.2** Add maintenance state helper functions in a new `portfolio_manager/maintenance_state.py` module:
- `start_maintenance_run(conn, run: dict) -> str`
- `finish_maintenance_run(conn, run_id, status, summary, error)`
- `get_maintenance_run(conn, run_id) -> dict | None`
- `list_maintenance_runs(conn, filters) -> list[dict]`
- `upsert_maintenance_finding(conn, finding: dict)`
- `get_maintenance_finding(conn, fingerprint) -> dict | None`
- `list_maintenance_findings(conn, filters) -> list[dict]`
- `mark_resolved_missing_findings(conn, project_id, skill_id, seen_fingerprints, resolved_at) -> int`

Validate run statuses: planned, running, success, skipped, blocked, failed.
Validate finding statuses: open, resolved, draft_created, ignored.

**1.3** Add stale-running-run recovery:
- `recover_stale_maintenance_runs(conn, now, older_than_seconds) -> int`

**1.4** Add maintenance config loader in new `portfolio_manager/maintenance_config.py`:
- `load_maintenance_config(root, projects_config, registry) -> MaintenanceConfig`
- `get_effective_skill_config(project_id, skill_id, explicit_overrides=None) -> dict`
- Missing maintenance.yaml is valid (use registry defaults).

**1.5** Add maintenance config mutation helpers (same file):
- `enable_maintenance_skill(...)`
- `disable_maintenance_skill(...)`
- `write_maintenance_config_atomic(...)`
- `backup_maintenance_config(...)`
- Use existing `with_config_lock` from `admin_locks.py` with lock name `maintenance:config`.

### Phase 2 — Models, Registry, Built-in Pure Logic

**2.1** Create `portfolio_manager/maintenance_models.py` with dataclasses:
- `MaintenanceSkillSpec` (id, name, description, default_interval_hours, default_enabled, supports_issue_drafts, required_state, allowed_commands, config_schema)
- `MaintenanceContext` (root, conn, project, skill_config, now, refresh_github)
- `MaintenanceFinding` (fingerprint, severity, title, body, source_type, source_id, source_url, metadata, draftable)
- `MaintenanceSkillResult` (skill_id, project_id, status, findings, summary, reason, warnings)

**2.2** Create `portfolio_manager/maintenance_registry.py`:
- Register exactly 4 built-in skills: `untriaged_issue_digest`, `stale_issue_digest`, `open_pr_health`, `repo_guidance_docs`
- Skill IDs must match regex: `^[a-z][a-z0-9_]{2,63}$`
- Each skill must declare `MaintenanceSkillSpec` with all fields populated.
- No dynamic third-party loading.

**2.3** Implement stable finding fingerprints in registry or a utility:
- `make_finding_fingerprint(project_id, skill_id, source_type, source_id, title) -> str`
- SHA-256, normalize: lowercase, trim whitespace, collapse repeated whitespace.

**2.4** Implement `untriaged_issue_digest` pure logic in `portfolio_manager/maintenance_builtin.py`:
- Uses local SQLite `issues` table only (no GitHub commands).
- Finds issues with state='needs_triage' older than min_age_hours.
- Severity: low by default, medium if older than 14 days.
- Returns `MaintenanceSkillResult`.

**2.5** Implement `stale_issue_digest` pure logic (same file):
- Uses local SQLite `issues` table only.
- Finds open issues older than stale_after_days.
- Severity: low if older than threshold, medium if older than 2x threshold.

**2.6** Implement `open_pr_health` pure logic (same file):
- Uses local SQLite `pull_requests` table only.
- Finds PRs with checks_failed, changes_requested, or old review_pending.
- Severity: high for checks_failed, medium for changes_requested, low for old review_pending.

**2.7** Implement `repo_guidance_docs` with mocked GitHub GET only (same file):
- Uses `gh api --method GET repos/OWNER/REPO/contents/PATH` and `gh api --method GET "repos/OWNER/REPO/commits?path=PATH&per_page=1"`.
- Checks required_files and optional_files exist and are fresh.
- Severity: medium for missing AGENTS.md, low for missing README.md, info for optional.
- Only runs when not dry_run. Blocks when gh unavailable.
- Validate paths: relative POSIX only, no `..`, no `/` prefix, no URL schemes.

## Existing codebase contracts to follow

- Root resolution: `from portfolio_manager.config import resolve_root`
- Shared result helpers: `_result`, `_blocked`, `_failed`, `_success` in `tools.py`
- Lock helpers: `from portfolio_manager.admin_locks import with_config_lock`
- SQLite init: `init_db(conn)` in `state.py` — add new tables there
- Atomic YAML write: `write_projects_config_atomic` in `admin_writes.py` — follow similar pattern
- Backup naming: follow `create_projects_config_backup` pattern
- GitHub sync: `sync_project_github` in `github_client.py`
- Issue table schema: `issues` table in `state.py` has `state` column (values include 'needs_triage')
- PR table schema: `pull_requests` table has `review_stage` column (values: 'checks_failed', 'changes_requested', 'review_pending', 'ready_for_human', 'open', etc.)
- Issue draft helpers: `from portfolio_manager.issue_drafts import create_issue_draft`
- Tool registration: add to `__init__.py` SCHEMAS + TOOLS dicts
- Dev CLI: add to `dev_cli.py` TOOL_HANDLERS + argparse subcommands
- Redaction: `from portfolio_manager.errors import redact_secrets`

## IMPORTANT: _failed uses status="error"

Existing `_failed` returns `status="error"`. Do NOT change this for existing code. For MVP 4, create a `_maintenance_failed` helper that returns `status="failed"` as spec requires. Or add a new `_failed_v2` that uses "failed". Keep backward compatibility.

## Test files to create

```
tests/test_maintenance_config.py    — config load/mutate tests
tests/test_maintenance_registry.py  — registry + fingerprint tests
tests/test_maintenance_builtin.py   — built-in skill logic tests
tests/test_maintenance_runs.py      — state helpers (schema, run lifecycle)
tests/test_maintenance_artifacts.py — placeholder (Phase 3)
tests/test_maintenance_drafts.py    — placeholder (Phase 5)
tests/test_maintenance_tools.py     — placeholder (Phase 6)
tests/test_maintenance_cli.py       — placeholder (Phase 7)
tests/test_maintenance_e2e.py       — placeholder (Phase 10)
tests/test_maintenance_skills.py    — placeholder (Phase 8)
tests/test_maintenance_due.py       — placeholder (Phase 4)
```

Also update `tests/test_structure.py` with MVP 4 structure checks.

## Test-first rule

1. Write or update test BEFORE implementation.
2. Confirm test FAILS for expected reason.
3. Implement smallest change to pass.
4. Run `pytest` to confirm no regressions.

## Verification

After implementing all tasks in this checkpoint:
```bash
.venv/bin/python -m pytest tests/ -x --tb=short
```
All 471 existing tests + all new tests must pass.

## Non-negotiable rules

- Never use `shell=True`
- Mock all subprocess calls in tests
- No real GitHub calls in tests
- No network access in tests
- Keep MVP 1-3 tests green
- Do not create worktrees, branches, commits, PRs, or GitHub issues
