# Fix GAP 7+8: Config Cascade + Maintenance Locks

## Context
You are fixing portfolio-manager MVP 4 to match SPEC_4.md.
Working directory: /home/luandro/Dev/hermes-multi-projects/portfolio-manager
Branch: feature/mvp4-maintenance-skills

## GAP 7: Effective Config Resolution

### Required 5-layer cascade for project/skill config:
1. Registry defaults (from MaintenanceSkillSpec)
2. maintenance.yaml `defaults` section
3. maintenance.yaml `skills.<skill_id>` section
4. maintenance.yaml `projects.<project_id>.skills.<skill_id>` section
5. Explicit tool args for one run only (do NOT persist)

### Current problems in maintenance_config.py:
- No `defaults` layer
- No project override resolution
- No validation of unknown skill IDs
- No validation of unknown project IDs
- Tool args not applied as per-run override
- DEFAULT_CONFIG has wrong skills (will be fixed by another task)

### Config rules:
- Missing maintenance.yaml is allowed — use registry defaults
- Enable/disable tools may create maintenance.yaml
- Existing unknown top-level fields must be preserved on write
- Existing unknown project fields must be preserved on write
- Unknown skill IDs in maintenance.yaml should block validation unless under `x_` extension key
- Invalid intervals (not 1-2160) block validation
- Invalid project IDs block validation
- Config writes must be atomic (write to temp, rename)
- Existing config must be backed up before mutation

### Config YAML structure:
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
  # ... etc

projects:
  some-project:
    skills:
      some_skill:
        enabled: true
        stale_after_days: 21
```

### Functions to implement/fix:
- `load_config(root: Path) -> dict[str, Any]` — deep merge defaults + yaml
- `get_effective_config(root: Path, skill_id: str, project_id: str | None = None, tool_overrides: dict | None = None) -> dict[str, Any]` — 5-layer cascade
- `enable_skill(...)` — validate skill_id, project_id, interval, config schema; atomic write with backup
- `disable_skill(...)` — same validation

### Validation:
- skill_id must exist in registry
- project_id must exist in projects config (if provided)
- interval_hours must be 1-2160
- config keys must match skill's config_schema

## GAP 8: Maintenance Locks

### Required lock names and TTLs:
- `maintenance:config` — 60 seconds — for config mutation (enable/disable)
- `maintenance:run` — 30 minutes — for global maintenance run
- `maintenance:project:<project_id>:skill:<skill_id>` — 10 minutes — per project/skill check

### Lock behavior:
- Config mutation requires `maintenance:config`
- Global maintenance run requires `maintenance:run`
- Each project/skill check requires `maintenance:project:<id>:skill:<id>`
- If project/skill lock held → skip that item, record status=skipped
- If global run lock held → return blocked
- All locks released in finally blocks
- Expired locks may be acquired using existing lock semantics

### Existing lock system:
The project already has `acquire_lock(conn, name, owner, ttl_seconds)` and `release_lock(conn, name, owner, ttl_seconds)` in `portfolio_manager/state.py`. Use these.

### Files to modify:
- `portfolio_manager/maintenance_tools.py` — add config lock to enable/disable handlers
- `portfolio_manager/maintenance_orchestrator.py` — add global run lock + per-project/skill locks
- Tests for both

### Example lock usage:
```python
from portfolio_manager.state import acquire_lock, release_lock

# Config lock
conn = get_connection(root)
lock = acquire_lock(conn, "maintenance:config", "maintenance-tool", 60)
if not lock:
    return _blocked(tool, "Config is locked by another operation")
try:
    # ... do config mutation
finally:
    release_lock(conn, "maintenance:config", "maintenance-tool")
```

## Verification
```bash
cd /home/luandro/Dev/hermes-multi-projects/portfolio-manager
/home/luandro/.local/bin/ruff check --fix --unsafe-fixes portfolio_manager/maintenance_config.py portfolio_manager/maintenance_tools.py portfolio_manager/maintenance_orchestrator.py
/home/luandro/.local/bin/ruff format portfolio_manager/maintenance_config.py portfolio_manager/maintenance_tools.py portfolio_manager/maintenance_orchestrator.py
uv run python -m pytest tests/ -x --tb=short -q
```

All tests must pass.
