# MVP 4 Phase 2: Models, Registry, Built-in Skills (2.1-2.7)

## Current State

Phase 0-1 are DONE. 500 tests passing (471 baseline + 27 new + 2 structure tests still failing for tool/schemas which come in Phase 6).

Already implemented (DO NOT re-implement):
- `portfolio_manager/state.py` — maintenance_runs and maintenance_findings tables added to SCHEMA_SQL
- `portfolio_manager/maintenance_state.py` — start_run, finish_run, insert_finding, get_findings_by_run, get_latest_successful_run, recover_stale_runs
- `portfolio_manager/maintenance_config.py` — load_config, save_config, get_skill_config, enable_skill, disable_skill, DEFAULT_CONFIG
- `portfolio_manager/maintenance_models.py` — MaintenanceSkillSpec, MaintenanceContext, MaintenanceFinding, MaintenanceSkillResult, make_finding_fingerprint
- `portfolio_manager/maintenance_registry.py` — _Registry class, REGISTRY singleton, get_registry(), SKILL_ID_RE validation
- `tests/test_maintenance_runs.py` — 15 tests covering schema + state helpers + stale recovery
- `tests/test_maintenance_config.py` — 12 tests covering config load/save/enable/disable

## Tasks Remaining

### Task 2.3: Stable finding fingerprints

`make_finding_fingerprint` already exists in `maintenance_models.py`. Write tests in `tests/test_maintenance_builtin.py`:

```python
def test_fingerprint_stable():
    """Same inputs produce same fingerprint."""
    from portfolio_manager.maintenance_models import make_finding_fingerprint
    fp1 = make_finding_fingerprint("skill-1", "proj-1", "issue", "42", "key-a")
    fp2 = make_finding_fingerprint("skill-1", "proj-1", "issue", "42", "key-a")
    assert fp1 == fp2

def test_fingerprint_differs_on_input_change():
    from portfolio_manager.maintenance_models import make_finding_fingerprint
    fp1 = make_finding_fingerprint("skill-1", "proj-1", "issue", "42", "key-a")
    fp2 = make_finding_fingerprint("skill-1", "proj-1", "issue", "42", "key-b")
    assert fp1 != fp2
```

### Task 2.4: Implement untriaged_issue_digest pure logic

In `portfolio_manager/maintenance_builtin.py`, implement:

```python
def run_untriaged_issue_digest(ctx: MaintenanceContext) -> MaintenanceSkillResult:
```

Logic:
1. Query SQLite `issues` table for `project_id=ctx.project.id` AND `state='needs_triage'`
2. Filter by `min_age_hours` from skill_config
3. Severity: "low" by default, "medium" if older than 14 days
4. Create MaintenanceFinding for each matching issue with stable fingerprint
5. Respect `max_findings` from config
6. Return MaintenanceSkillResult with status="success"

Register in registry with spec:
- id: "untriaged_issue_digest"
- name: "Untriaged Issue Digest"
- description: "Find open issues still in needs_triage state"
- default_interval_hours: 24
- default_enabled: True
- supports_issue_drafts: True
- required_state: ["issues"]
- allowed_commands: []
- config_schema: {"min_age_hours": {"type": "int"}, "max_findings": {"type": "int"}}

Write tests in `tests/test_maintenance_builtin.py`:
- Test with no untriaged issues returns empty findings
- Test with untriaged issues returns findings
- Test severity escalation for old issues (>14 days)
- Test max_findings limit
- Test fingerprint stability

### Task 2.5: Implement stale_issue_digest pure logic

In `portfolio_manager/maintenance_builtin.py`, add:

```python
def run_stale_issue_digest(ctx: MaintenanceContext) -> MaintenanceSkillResult:
```

Logic:
1. Query issues where `state != 'closed'` and `updated_at` or `last_seen_at` older than `stale_after_days`
2. Severity: "low" if older than stale_after_days, "medium" if older than stale_after_days * 2
3. Respect max_findings
4. Return findings with stable fingerprints

Register with spec similar to untriaged but with different defaults (interval_hours=168, stale_after_days=30).

Tests in same file.

### Task 2.6: Implement open_pr_health pure logic

```python
def run_open_pr_health(ctx: MaintenanceContext) -> MaintenanceSkillResult:
```

Logic:
1. Query pull_requests for project_id
2. Include if: review_stage in ["checks_failed", "changes_requested"]
   OR review_stage == "review_pending" and older than stale_after_days
3. Severity based on staleness
4. Respect max_findings and config flags (include_review_pending, include_checks_failed, include_changes_requested)

Tests in same file.

### Task 2.7: Implement repo_guidance_docs with mocked GitHub GET

```python
def run_repo_guidance_docs(ctx: MaintenanceContext) -> MaintenanceSkillResult:
```

Logic:
1. Check doc_paths from config (default: ["CONTRIBUTING.md", "DEVELOPMENT.md", "ARCHITECTURE.md", "DESIGN.md"])
2. For each doc, use `subprocess.run(["gh", "api", ...])` to check if file exists in repo
3. Create finding for each MISSING guidance doc
4. Severity: "info" for missing optional docs

For tests: mock `subprocess.run` to avoid real GitHub API calls.

Register with spec:
- id: "repo_guidance_docs"
- interval_hours: 168
- supports_issue_drafts: False

### Task 2.2 (completion): Register all 4 built-in skills

At bottom of `maintenance_builtin.py`, add a `register_builtin_skills(registry)` function that registers all 4 skills. This should be called during plugin init.

Write tests in `tests/test_maintenance_registry.py`:
- Test registry rejects invalid skill IDs
- Test registry rejects duplicate registrations
- Test registry list_specs returns all 4 built-in skills after registration
- Test registry returns blocked for unknown skill IDs
- Test registry executes known skill correctly

## Reference Files

Read these before implementing:
- SPEC_4.md (lines 306-560 for skill interface and built-in skill specs)
- portfolio_manager/maintenance_models.py (already exists)
- portfolio_manager/maintenance_registry.py (already exists)
- portfolio_manager/maintenance_config.py (for DEFAULT_CONFIG reference)
- portfolio_manager/maintenance_state.py (for DB helpers)
- portfolio_manager/config.py (for ProjectConfig dataclass)
- tests/test_maintenance_runs.py (for fixture patterns with DB setup)

## Verification

After ALL tasks:
1. Run: `.venv/bin/python -m pytest tests/test_maintenance_builtin.py tests/test_maintenance_registry.py -v --tb=short`
2. Run: `.venv/bin/python -m pytest tests/ -q --tb=short` — must keep 500 existing tests green
3. Report test counts
