# Phase 4: Due Computation and Run Orchestration

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## Context
- Branch: feature/mvp4-maintenance-skills
- 599 tests currently passing
- Existing modules: maintenance_models.py, maintenance_registry.py, maintenance_state.py, maintenance_config.py, maintenance_artifacts.py, maintenance_reports.py
- Built-in skills in portfolio_manager/skills/builtin/ (health_check, dependency_audit, license_compliance, stale_branches, security_advisory)
- Registry singleton: REGISTRY with register(spec, executor), get_spec(skill_id), list_specs(), execute(skill_id, ctx)

## Tasks

### Task 4.1: Due computation
Create `portfolio_manager/maintenance_due.py`:
- Function: `compute_due_checks(conn, config=None, project_filter=None, skill_filter=None) -> list[dict]`
- Each dict has: project_id, skill_id, is_due, reason, last_run_at
- Due logic:
  - Not due if skill is disabled in config
  - Not due if project is paused/archived (unless include_paused/include_archived flags)
  - Due if no previous successful run exists for this project+skill
  - Due if now >= last_successful_finished_at + interval_hours
  - Not due otherwise
- Query maintenance_runs table for last successful runs
- Query projects table for status filtering

Tests in `tests/test_maintenance_due.py`:
- test_never_run_skill_is_due
- test_recent_successful_run_is_not_due
- test_old_successful_run_is_due
- test_disabled_skill_is_not_due
- test_paused_and_archived_projects_excluded_by_default
- test_include_paused_and_include_archived_flags_work
- test_project_filter_works
- test_skill_filter_works

### Task 4.2: Dry-run planning
Create `portfolio_manager/maintenance_planner.py`:
- Function: `plan_maintenance_run(conn, config, project_filter=None, skill_filter=None) -> dict`
- Returns: {planned_checks: [...], skipped: [...], summary: {...}}
- Does NOT insert any rows, write files, or run commands
- Just computes what WOULD be done based on due checks
- Includes would_create_issue_drafts flag (based on config)

Tests in `tests/test_maintenance_planner.py`:
- test_dry_run_returns_planned_checks
- test_dry_run_does_not_insert_runs (verify DB unchanged)
- test_dry_run_does_not_write_artifacts (verify no files)
- test_dry_run_does_not_run_github_commands
- test_dry_run_reports_would_create_issue_drafts

### Task 4.3: Real run orchestration
Create `portfolio_manager/maintenance_orchestrator.py`:
- Function: `run_maintenance(root, conn, config, project_filter=None, skill_filter=None, dry_run=False) -> dict`
- Steps:
  1. If dry_run, delegate to planner and return
  2. Recover stale runs via maintenance_state.recover_stale_runs()
  3. Compute due checks via maintenance_due
  4. For each due check:
     - start_run() in state DB
     - Execute skill via REGISTRY.execute(skill_id, ctx)
     - Store findings via add_finding()
     - complete_run() or fail_run()
     - Write artifacts via maintenance_reports
  5. Return summary with run_id, findings count, errors

Tests in `tests/test_maintenance_orchestrator.py`:
- test_real_run_starts_and_finishes_run_rows
- test_real_run_upserts_findings
- test_real_run_marks_missing_findings_resolved
- test_real_run_writes_report_artifacts
- test_real_run_continues_after_one_skill_failure
- test_run_returns_summary

### Task 4.4: GitHub refresh integration
Add to `maintenance_orchestrator.py`:
- If config has refresh_github=True, attempt GitHub sync before running skills
- Use existing sync helpers from the codebase (check what's available in admin or state modules)
- If GitHub unavailable:
  - Local-state skills (health_check, dependency_audit, etc.) continue with warning
  - Log the failure, don't crash

Tests (add to test_maintenance_orchestrator.py):
- test_refresh_github_true_calls_sync
- test_refresh_github_false_skips_sync
- test_gh_unavailable_continues_with_warning

## Rules
1. Write tests FIRST, run them to confirm they FAIL, then implement
2. Run: uv run python -m pytest tests/ --ignore=tests/test_structure.py -x --tb=short -q
3. All 599 existing tests must stay passing
4. Follow existing code patterns
5. Use sqlite3 connections directly (same as maintenance_state.py)
6. Keep orchestrator thin — delegate to existing modules
