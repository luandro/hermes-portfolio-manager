# Phase 6: Tool Schemas and Handlers

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## Context
- Branch: feature/mvp4-maintenance-skills
- all tests passing, 2 structure tests failing (test_maintenance_tools_registered, test_maintenance_tool_schemas_exist)
- Phase 6 fixes those 2 failing tests

## CRITICAL: Structure test expectations

The test `test_maintenance_tools_registered` expects these 8 tool names in `_TOOL_REGISTRY` in `portfolio_manager/__init__.py`:
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

The test `test_maintenance_tool_schemas_exist` expects these attributes in `portfolio_manager/schemas.py`:
```txt
PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA
PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA
PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA
PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA
PORTFOLIO_MAINTENANCE_DUE_SCHEMA
PORTFOLIO_MAINTENANCE_RUN_SCHEMA
PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA
PORTFOLIO_MAINTENANCE_REPORT_SCHEMA
```

## Existing patterns

Schemas in `schemas.py` follow this pattern:
```python
PORTFOLIO_PING_SCHEMA = {
    "name": "portfolio_ping",
    "description": "...",
    "parameters": {
        "type": "object",
        "properties": {...},
        "required": [...],
    },
}
```

Handlers in `tools.py` follow this pattern:
```python
def _handle_portfolio_ping(params: dict) -> dict:
    ...
    return {"status": "ok", "tool": "portfolio_ping", "message": "...", "data": {...}}
```

Failed handlers return: `{"status": "error", "tool": "...", "message": "...", "reason": "..."}`

`_TOOL_REGISTRY` in `__init__.py` is a list of tuples:
```python
(name: str, schema: dict, handler: callable)
```

## Tasks

### Task 6.1: Add 8 tool schemas to schemas.py
Add after the MVP 3 schemas, in a clearly marked `# MVP 4` section:

1. PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA — no required params
2. PORTFOLIO_MAINTENANCE_SKILL_EXPLAIN_SCHEMA — required: skill_id; optional: project_id
3. PORTFOLIO_MAINTENANCE_SKILL_ENABLE_SCHEMA — required: skill_id; optional: project_id, interval_hours, config_json
4. PORTFOLIO_MAINTENANCE_SKILL_DISABLE_SCHEMA — required: skill_id; optional: project_id
5. PORTFOLIO_MAINTENANCE_DUE_SCHEMA — optional: project_filter, skill_filter
6. PORTFOLIO_MAINTENANCE_RUN_SCHEMA — optional: dry_run (bool default true), project_filter, skill_filter, create_issue_drafts (bool default false), refresh_github (bool default false)
7. PORTFOLIO_MAINTENANCE_RUN_PROJECT_SCHEMA — required: project_ref; optional: dry_run, create_issue_drafts
8. PORTFOLIO_MAINTENANCE_REPORT_SCHEMA — optional: run_id, project_filter, skill_filter, severity_filter

### Task 6.2: Implement handlers in tools.py (or maintenance_tools.py)
Create handler functions. Each should:
- Resolve root via resolve_root()
- Open state DB via open_state()
- Delegate to existing maintenance modules (maintenance_due, maintenance_planner, maintenance_orchestrator, maintenance_registry, maintenance_reports, maintenance_config, maintenance_drafts)
- Return dict with status/tool/message/data

Handlers:
1. _handle_portfolio_maintenance_skill_list — list all skills from registry, show enabled/disabled status from config
2. _handle_portfolio_maintenance_skill_explain — show skill spec + effective config for a skill
3. _handle_portfolio_maintenance_skill_enable — enable skill in config (use with_config_lock)
4. _handle_portfolio_maintenance_skill_disable — disable skill in config
5. _handle_portfolio_maintenance_due — call compute_due_checks, return counts
6. _handle_portfolio_maintenance_run — call run_maintenance from orchestrator
7. _handle_portfolio_maintenance_run_project — resolve project_ref, then run for that project
8. _handle_portfolio_maintenance_report — call load_report or load_latest_report

### Task 6.3: Register tools in __init__.py
Add imports for schemas and handlers, then add 8 entries to _TOOL_REGISTRY:
```python
# MVP 4 tools
("portfolio_maintenance_skill_list", PORTFOLIO_MAINTENANCE_SKILL_LIST_SCHEMA, _handle_portfolio_maintenance_skill_list),
... etc
```

### Task 6.4: Write tests
Add tests to `tests/test_maintenance_tools.py`:
- test_maintenance_skill_list_schema_defaults
- test_maintenance_skill_explain_requires_skill_id
- test_maintenance_skill_enable_validates_interval_bounds
- test_maintenance_run_schema_defaults
- test_maintenance_report_schema_defaults
- test_skill_list_works_with_missing_config
- test_skill_list_can_hide_disabled_skills
- test_skill_explain_returns_registry_and_effective_config
- test_skill_explain_blocks_unknown_skill
- test_skill_enable_writes_config
- test_skill_disable_writes_config
- test_maintenance_due_tool_returns_counts
- test_maintenance_run_dry_run_has_no_side_effects
- test_maintenance_report_returns_latest_run

## Rules
1. Write tests FIRST, confirm they fail, then implement
2. Run: uv run pytest tests/ -x --tb=short -q (all tests must pass including the 2 structure tests)
3. Follow existing code patterns EXACTLY
4. Keep handlers thin — delegate logic to existing modules
5. Handlers must import from portfolio_manager modules, not from portfolio_manager.tools
