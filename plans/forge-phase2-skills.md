# Tasks 2.3-2.7: Built-in Maintenance Skills

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## What exists
- portfolio_manager/maintenance_models.py — MaintenanceSkillSpec, MaintenanceContext, MaintenanceFinding, MaintenanceSkillResult, make_finding_fingerprint
- portfolio_manager/maintenance_registry.py — _Registry with register(spec, executor), get_spec(skill_id), list_specs(), execute(skill_id, ctx)
- portfolio_manager/maintenance_state.py — start_run(), complete_run(), fail_run(), add_finding(), get_run()
- portfolio_manager/maintenance_config.py — DEFAULT_MAINTENANCE_CONFIG, load_maintenance_config()

## What to create

### 1. portfolio_manager/skills/builtin/__init__.py
- Import all 5 skill modules
- Each module self-registers on import via REGISTRY.register()
- Provide register_all() function that imports all

### 2. portfolio_manager/skills/builtin/health_check.py
- Create MaintenanceSkillSpec(id="health_check", description="Check project health status", tags=["health","core"])
- Executor function that takes MaintenanceContext, queries state DB for project statuses
- Returns MaintenanceSkillResult with findings for unhealthy projects
- Use add_finding() to record findings in DB

### 3. portfolio_manager/skills/builtin/dependency_audit.py
- MaintenanceSkillSpec(id="dependency_audit", description="Audit dependencies for vulnerabilities", tags=["dependencies","security"])
- Executor scans for dependency issues
- Returns findings with severity levels (info/warning/critical)

### 4. portfolio_manager/skills/builtin/license_compliance.py
- MaintenanceSkillSpec(id="license_compliance", description="Check license compliance", tags=["licenses","compliance"])
- Returns findings for problematic licenses

### 5. portfolio_manager/skills/builtin/stale_branches.py
- MaintenanceSkillSpec(id="stale_branches", description="Find stale branches", tags=["branches","cleanup"])
- Returns findings with branch names and last activity

### 6. portfolio_manager/skills/builtin/security_advisory.py
- MaintenanceSkillSpec(id="security_advisory", description="Check for security advisories", tags=["security","advisories"])
- Returns findings with CVE references

## Important patterns
- Each skill module calls REGISTRY.register(spec, executor_function) at module level
- Executor signature: def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult
- Skills should be functional (simplified but working) — they read from state DB
- Use MaintenanceFinding for individual issues
- Use make_finding_fingerprint() for finding dedup
- Follow existing code style (dataclasses, type hints)

## After creating files
Run: uv run pytest tests/ --ignore=tests/test_structure.py -x --tb=short -q
All existing tests must still pass.
