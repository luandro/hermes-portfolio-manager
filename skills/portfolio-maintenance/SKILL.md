# Portfolio Maintenance Skill

MVP 4 maintenance/reporting skill for the Hermes Portfolio Manager.

## Purpose

Run safe, read-only maintenance checks across managed projects and produce
reports.  **All checks are report-only by default** — nothing is fixed,
published, or mutated without an explicit user request.

> **WARNING: No auto-fixes.** Maintenance tools never modify repository state,
> create commits, push branches, or publish GitHub issues.  The only write
> actions are saving local reports and, when explicitly requested, creating
> local issue drafts.

> **WARNING: No GitHub issue publishing from maintenance.** Maintenance tools
> may create local issue drafts but will never call `gh issue create` or any
> other GitHub mutation.

## Tools

| Tool | Description |
|------|-------------|
| `portfolio_maintenance_skill_list` | List all registered maintenance skills and their status |
| `portfolio_maintenance_skill_explain` | Explain one maintenance skill in detail |
| `portfolio_maintenance_skill_enable` | Enable a maintenance skill |
| `portfolio_maintenance_skill_disable` | Disable a maintenance skill |
| `portfolio_maintenance_due` | Show which checks are due to run now |
| `portfolio_maintenance_run` | Execute or dry-run a full maintenance cycle |
| `portfolio_maintenance_run_project` | Run maintenance for a single project |
| `portfolio_maintenance_report` | Load and display the latest (or a specific) maintenance report |

## Guidance

1. **Use `maintenance_due` before broad runs** — see what is actually due
   before triggering a full cycle.
2. **Prefer dry-run first** — every `maintenance_run` defaults to
   `dry_run=True`.  Review the plan before committing to a real run.
3. **Create drafts only when requested** — local issue drafts are opt-in via
   `create_issue_drafts=True`.  Never create drafts automatically.

## Example Phrases

Users may say things like:

- "List maintenance skills."
- "Explain stale issue checks."
- "Show checks due now."
- "Dry-run maintenance."
- "Run maintenance and report findings."
- "Show latest maintenance report."
