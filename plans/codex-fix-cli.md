# Fix GAP 4: Missing CLI Args

## Context
You are fixing portfolio-manager MVP 4 to match docs/mvps/mvp4-spec.md.
Working directory: /home/luandro/Dev/hermes-multi-projects/portfolio-manager
Branch: feature/mvp4-maintenance-skills

## Task
Add all 14 missing CLI arguments to dev_cli.py and wire them into the maintenance tool handlers.

## Currently only --skill-id is present. Add these:

```python
parser.add_argument("--interval-hours", type=int, help="Skill interval in hours (1-2160)")
parser.add_argument("--config-json", help="JSON object for skill config")
parser.add_argument("--include-disabled", type=str, help="Include disabled skills (true/false)")
parser.add_argument("--include-project-overrides", type=str, help="Include project overrides (true/false)")
parser.add_argument("--include-paused", type=str, help="Include paused projects (true/false)")
parser.add_argument("--include-archived", type=str, help="Include archived projects (true/false)")
parser.add_argument("--include-not-due", type=str, help="Include not-due checks (true/false)")
parser.add_argument("--refresh-github", type=str, help="Refresh GitHub state (true/false)")
parser.add_argument("--create-issue-drafts", type=str, help="Create local issue drafts (true/false)")
parser.add_argument("--max-projects", type=int, help="Max projects per run")
parser.add_argument("--run-id", help="Specific maintenance run ID")
parser.add_argument("--severity", help="Filter by severity (info/low/medium/high)")
parser.add_argument("--limit", type=int, help="Max results to return")
parser.add_argument("--include-resolved", type=str, help="Include resolved findings (true/false)")
```

## Wiring into handler_args

After the existing `if args.skill_id is not None:` block, add wiring for each arg:

```python
# Boolean args — use existing _to_bool helper
if args.include_disabled is not None:
    handler_args["include_disabled"] = _to_bool(args.include_disabled)
if args.include_project_overrides is not None:
    handler_args["include_project_overrides"] = _to_bool(args.include_project_overrides)
if args.include_paused is not None:
    handler_args["include_paused"] = _to_bool(args.include_paused)
if args.include_archived is not None:
    handler_args["include_archived"] = _to_bool(args.include_archived)
if args.include_not_due is not None:
    handler_args["include_not_due"] = _to_bool(args.include_not_due)
if args.refresh_github is not None:
    handler_args["refresh_github"] = _to_bool(args.refresh_github)
if args.create_issue_drafts is not None:
    handler_args["create_issue_drafts"] = _to_bool(args.create_issue_drafts)
if args.include_resolved is not None:
    handler_args["include_resolved"] = _to_bool(args.include_resolved)

# Integer args
if args.interval_hours is not None:
    handler_args["interval_hours"] = args.interval_hours
if args.max_projects is not None:
    handler_args["max_projects"] = args.max_projects
if args.limit is not None:
    handler_args["limit"] = args.limit

# String args
if args.config_json is not None:
    handler_args["config_json"] = args.config_json  # handler validates JSON
if args.run_id is not None:
    handler_args["run_id"] = args.run_id
if args.severity is not None:
    handler_args["severity"] = args.severity
```

## Spec CLI examples that must work:
```bash
python dev_cli.py portfolio_maintenance_skill_list --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_explain --skill-id stale_issue_digest --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_enable --skill-id stale_issue_digest --interval-hours 168 --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_skill_disable --skill-id repo_guidance_docs --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_due --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run --skill-id stale_issue_digest --refresh-github false --create-issue-drafts false --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_run_project --project-ref comapeo-cloud-app --skill-id open_pr_health --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py portfolio_maintenance_report --root /tmp/agent-system-test --json
```

Note: dev_cli.py uses hyphenated command names (maintenance-run) as aliases. Both `portfolio_maintenance_run` and `maintenance-run` should work.

## Verification
```bash
cd /home/luandro/Dev/hermes-multi-projects/portfolio-manager
/home/luandro/.local/bin/ruff check --fix --unsafe-fixes dev_cli.py
/home/luandro/.local/bin/ruff format dev_cli.py
uv run python -m pytest tests/ -x --tb=short -q
```

All tests must pass. Update test_maintenance_cli.py if needed to cover new args.
