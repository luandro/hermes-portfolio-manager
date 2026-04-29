# Smoke Test Bug Fixes

## Bug 1: Registry returns 0 skills
**Root cause:** `portfolio_manager/skills/builtin/__init__.py` calls `register_all()` on import, but nothing imports it.
**Fix:** Add `import portfolio_manager.skills.builtin  # noqa: F401` at the top of `portfolio_manager/maintenance_tools.py` (after other imports, around line 22).

## Bug 2: `no such table: maintenance_runs`
**Root cause:** `maintenance_due.py` and `maintenance_orchestrator.py` use `open_state()` which opens the DB, but `init_state()` must be called first to create the tables.
**Fix:** In `maintenance_tools.py`, every handler that uses `open_state()` should also call `init_state()` first. The correct sequence is `init_state(root)` then `with open_state(root) as conn:`. Alternatively, since `init_state` takes a DB connection, use `with open_state(root) as conn: init_state(conn)`. Check handlers: `_handle_portfolio_maintenance_due`, `_handle_portfolio_maintenance_run`, `_handle_portfolio_maintenance_run_project`, `_handle_portfolio_maintenance_report`, `_handle_portfolio_maintenance_skill_enable`, `_handle_portfolio_maintenance_skill_disable`.

## Bug 3: CLI missing `--skill-id` argument
**Root cause:** `dev_cli.py` has no `--skill-id` argparse argument. The maintenance tool handlers expect `skill_id` in args dict.
**Fix:** Add to dev_cli.py argparse section (around line 118-127):
```python
parser.add_argument("--skill-id", help="Maintenance skill ID")
```
And in the args dict building section (around line 160-179):
```python
if args.skill_id is not None:
    handler_args["skill_id"] = args.skill_id
```

## Bug 4: `--dry-run` requires value instead of being a flag
**Root cause:** `--dry-run` is `type=str`, requiring `--dry-run true`.
**Fix:** This is actually fine for the tool API (expects string "true"/"false"), but the CLI experience is bad. Change `--dry-run` in dev_cli.py to `action="store_true"` for CLI convenience AND keep the existing `type=str` version as `--dry-run-val`. Better: just keep `type=str` but document that it needs `--dry-run true`. This is low priority - the current behavior matches other boolean args like `--confirm`, `--validate-github`.

## Verification
After fixes:
1. `uv run python dev_cli.py maintenance-skill-list` should show 5 skills
2. `uv run python dev_cli.py maintenance-skill-explain --skill-id health_check` should show spec
3. `uv run python dev_cli.py maintenance-due` should return success (empty due checks)
4. `uv run python dev_cli.py maintenance-run --dry-run true` should return success
5. `uv run python dev_cli.py maintenance-report` should work (no reports)
6. All 690 tests must still pass
