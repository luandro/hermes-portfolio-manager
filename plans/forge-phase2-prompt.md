# Phase 2 Implementation: Models, Registry, Built-in Skills

## Context
You are working on the portfolio-manager project in /home/luandro/Dev/hermes-multi-projects/portfolio-manager
Branch: feature/mvp4-maintenance-skills

## What's ALREADY DONE (do NOT redo)
- portfolio_manager/maintenance_models.py — SkillDefinition, SkillResult, MaintenanceReport dataclasses exist
- portfolio_manager/maintenance_registry.py — SkillRegistry with register/get/list/validate exists
- portfolio_manager/maintenance_state.py — state helpers (start_run, complete_run, etc.)
- portfolio_manager/maintenance_config.py — config loader
- tests/test_maintenance_runs.py — 16 tests passing
- tests/test_maintenance_config.py — 11 tests passing

## What you MUST implement

### Task 2.2: Complete models and registry tests
Create `tests/test_maintenance_models.py`:
- Test SkillDefinition creation, validation, defaults
- Test SkillResult creation, success/failure factory methods
- Test MaintenanceReport creation, summary stats, finding counts
- Test edge cases: empty findings, missing optional fields

Create `tests/test_maintenance_registry.py`:
- Test SkillRegistry.register() — valid skill, duplicate, missing fields
- Test SkillRegistry.get() — found, not found
- Test SkillRegistry.list_skills() — empty, multiple, filtered by tag
- Test SkillRegistry.validate() — valid, invalid skill

### Task 2.3: Built-in skill — health_check
Create `portfolio_manager/skills/builtin/health_check.py`:
- Import from maintenance_models, maintenance_registry, maintenance_state, maintenance_config
- SkillDefinition with name="health_check", tags=["health", "core"]
- execute() function that:
  - Creates a maintenance run via maintenance_state
  - Checks each project's status (reads state DB)
  - Returns SkillResult with findings for projects with issues
  - Completes or fails the run
- Register the skill

### Task 2.4: Built-in skill — dependency_audit
Create `portfolio_manager/skills/builtin/dependency_audit.py`:
- Similar structure to health_check
- Scans for outdated/vulnerable dependencies
- Returns findings with severity levels

### Task 2.5: Built-in skill — license_compliance
Create `portfolio_manager/skills/builtin/license_compliance.py`:
- Checks license compatibility
- Returns findings for problematic licenses

### Task 2.6: Built-in skill — stale_branches
Create `portfolio_manager/skills/builtin/stale_branches.py`:
- Identifies branches not updated in X days
- Returns findings with branch names and ages

### Task 2.7: Built-in skill — security_advisory
Create `portfolio_manager/skills/builtin/security_advisory.py`:
- Checks for known security advisories
- Returns findings with CVE references

### Also needed
- `portfolio_manager/skills/builtin/__init__.py` that imports and registers all built-in skills

## Rules
1. Write tests FIRST, run them to confirm they FAIL, then implement
2. Use `uv run python -m pytest tests/ -x --tb=short` to run tests
3. All 500 existing tests must stay passing
4. Follow existing code style (check existing files for patterns)
5. Use dataclasses, not pydantic (match existing models.py style)
6. All skills must be functional — they can be simplified but must actually work against the state DB
