# Fix Plan: Tool Schemas + Handler Arg Names (GAPs 1+2)

## Problem
Two related issues:
1. `schemas.py` — tool schemas missing spec-required parameters, use wrong param names
2. `maintenance_tools.py` — handlers read `project_filter`/`skill_filter`/`severity_filter` but SPEC and CLI pass `project_id`/`skill_id`/`severity`

## SPEC Requirements (source of truth)

### 1. portfolio_maintenance_skill_list
Schema needs:
```python
{
    "root": "string | null",
    "include_disabled": "boolean, default true",
    "include_project_overrides": "boolean, default false"
}
```
CURRENT schema only has `root`. MISSING: `include_disabled`, `include_project_overrides`.

### 2. portfolio_maintenance_skill_explain
Schema needs:
```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null"
}
```
CURRENT is correct. No changes needed.

### 3. portfolio_maintenance_skill_enable
Schema needs:
```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null",
    "interval_hours": "integer | null",
    "create_issue_drafts": "boolean | null",
    "config": "object | null"
}
```
CURRENT has `config_json` (string) instead of `config` (object). MISSING `create_issue_drafts`.
Handler already reads `config_json` and `create_issue_drafts` from args — schema just needs alignment.
Keep `config_json` in schema (CLI sends JSON string) but add `create_issue_drafts` boolean param.

### 4. portfolio_maintenance_skill_disable
Schema needs:
```python
{
    "skill_id": "string, required",
    "root": "string | null",
    "project_id": "string | null"
}
```
CURRENT is correct. No changes needed.

### 5. portfolio_maintenance_due
Schema needs:
```python
{
    "root": "string | null",
    "project_id": "string | null",
    "skill_id": "string | null",
    "include_disabled": "boolean, default false",
    "include_paused": "boolean, default false",
    "include_archived": "boolean, default false"
}
```
CURRENT uses `project_filter` (csv) and `skill_filter` (csv). SPEC wants singular `project_id` and `skill_id`.
ADD: `include_disabled`, `include_paused`, `include_archived`.
CHANGE: `project_filter` → `project_id`, `skill_filter` → `skill_id`.

### 6. portfolio_maintenance_run
Schema needs:
```python
{
    "root": "string | null",
    "skill_id": "string | null",
    "project_id": "string | null",
    "refresh_github": "boolean, default true",
    "create_issue_drafts": "boolean, default false",
    "include_not_due": "boolean, default false",
    "include_paused": "boolean, default false",
    "include_archived": "boolean, default false",
    "dry_run": "boolean, default false",
    "max_projects": "integer | null"
}
```
CURRENT uses `project_filter`/`skill_filter`. MISSING: `project_id`, `skill_id`, `include_not_due`, `include_paused`, `include_archived`, `max_projects`.

### 7. portfolio_maintenance_run_project
Schema needs:
```python
{
    "project_ref": "string, required",
    "root": "string | null",
    "skill_id": "string | null",
    "refresh_github": "boolean, default true",
    "create_issue_drafts": "boolean, default false",
    "include_not_due": "boolean, default true",
    "dry_run": "boolean, default false"
}
```
CURRENT MISSING: `skill_id`, `refresh_github`, `include_not_due`.

### 8. portfolio_maintenance_report
Schema needs:
```python
{
    "root": "string | null",
    "run_id": "string | null",
    "project_id": "string | null",
    "skill_id": "string | null",
    "status": "string | null",
    "severity": "string | null",
    "limit": "integer, default 20",
    "include_resolved": "boolean, default false"
}
```
CURRENT uses `project_filter`/`skill_filter`/`severity_filter`. MISSING: `project_id`, `skill_id`, `status`, `limit`, `include_resolved`.

## Changes Required

### File: portfolio_manager/schemas.py (lines 808-1025)

For EACH tool schema, replace the `properties` dict to match SPEC exactly:

1. **skill_list**: Add `include_disabled` (boolean, default true) and `include_project_overrides` (boolean, default false)
2. **skill_enable**: Add `create_issue_drafts` (boolean). Keep `config_json` as-is.
3. **due**: Replace `project_filter`→`project_id`, `skill_filter`→`skill_id`. Add `include_disabled`, `include_paused`, `include_archived`.
4. **run**: Replace `project_filter`→`project_id`, `skill_filter`→`skill_id`. Add `include_not_due`, `include_paused`, `include_archived`, `max_projects`.
5. **run_project**: Add `skill_id`, `refresh_github`, `include_not_due`.
6. **report**: Replace `project_filter`→`project_id`, `skill_filter`→`skill_id`, `severity_filter`→`severity`. Add `status`, `limit`, `include_resolved`.

### File: portfolio_manager/maintenance_tools.py

**Handler `_handle_portfolio_maintenance_due` (line 285):**
- Replace `args.get("project_filter")` → `args.get("project_id")`
- Replace `args.get("skill_filter")` → `args.get("skill_id")`
- Keep `_parse_csv_filter` since `project_id`/`skill_id` can still be used as single values in a list
- BUT: if SPEC passes singular strings, need to wrap in list: `_parse_csv_filter(args.get("project_id"))` already handles this
- Actually, the CLI passes singular `--project-id` which becomes `project_id` string. The handler should convert: `project_filter = [args["project_id"]] if args.get("project_id") else None`
- Keep using `_parse_csv_filter` but read from the correct arg name

**Handler `_handle_portfolio_maintenance_run` (line 330):**
- Replace `args.get("project_filter")` → `args.get("project_id")`
- Replace `args.get("skill_filter")` → `args.get("skill_id")`
- Add handling for `include_not_due`, `include_paused`, `include_archived`, `max_projects`
- Pass `skill_filter` to `run_maintenance` using the singular arg converted to list

**Handler `_handle_portfolio_maintenance_run_project` (line 408):**
- Add `skill_id` from args, convert to `skill_filter=[skill_id]` if present
- Add handling for `include_not_due`

**Handler `_handle_portfolio_maintenance_report` (line 503):**
- Replace `args.get("severity_filter")` → `args.get("severity")`
- Add handling for `project_id`, `skill_id`, `status`, `limit`, `include_resolved`

### IMPORTANT: Backwards compatibility
The `_parse_csv_filter` helper should remain for internal use. But arg reading should use SPEC names.

## Verification
```bash
/home/luandro/.local/bin/ruff check --fix --unsafe-fixes portfolio_manager/schemas.py portfolio_manager/maintenance_tools.py
/home/luandro/.local/bin/ruff format portfolio_manager/schemas.py portfolio_manager/maintenance_tools.py
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/ -x --tb=short -q
```
All 710+ tests must pass.
