# Fix GAP 1: Replace Built-in Skills

## Context
You are fixing portfolio-manager MVP 4 to match SPEC_4.md. DO NOT read SPEC_4.md — all requirements are below.

Working directory: portfolio-manager (repo root)
Branch: feature/mvp4-maintenance-skills

## Task
Replace the 5 wrong built-in skills with the 4 spec-required ones.

## Current (WRONG) skills in portfolio_manager/skills/builtin/:
- `health_check.py`
- `dependency_audit.py`
- `license_compliance.py`
- `security_advisory.py`
- `stale_branches.py`

## Required skills — implement each:

### 1. `untriaged_issue_digest`
Purpose: Find open issues in local state with state `needs_triage`.

Data source: SQLite `issues` table.

Default config:
```yaml
enabled: true
interval_hours: 24
min_age_hours: 24
max_findings: 20
create_issue_drafts: false
```

Finding rule: issue.state == "needs_triage" AND (last_seen_at or updated_at older than min_age_hours)
Severity: low by default, medium if older than 14 days
Draft behavior: one consolidated draft per project/run if requested

Required state: ["issues"]
Allowed commands: [] (reads SQLite only)

### 2. `stale_issue_digest`
Purpose: Find open issues not updated recently.

Data source: SQLite `issues` table.

Default config:
```yaml
enabled: true
interval_hours: 168
stale_after_days: 30
max_findings: 20
create_issue_drafts: false
```

Finding rule: issue visible in local open state AND (updated_at or last_seen_at older than stale_after_days)
Severity: low if older than stale_after_days, medium if older than stale_after_days * 2
Draft behavior: one consolidated draft per project/run if requested

Required state: ["issues"]
Allowed commands: [] (reads SQLite only)

### 3. `open_pr_health`
Purpose: Summarize open PRs needing attention.

Data source: SQLite `pull_requests` table.

Default config:
```yaml
enabled: true
interval_hours: 12
stale_after_days: 7
include_review_pending: true
include_checks_failed: true
include_changes_requested: true
max_findings: 20
create_issue_drafts: false
```

Finding rule:
- review_stage in ["checks_failed", "changes_requested"]
- OR review_stage == "review_pending" and updated_at/last_seen_at older than stale_after_days

Severity: high for checks_failed, medium for changes_requested, low for old review_pending
Draft behavior: one consolidated draft per project/run if explicitly requested

Required state: ["pull_requests"]
Allowed commands: [] (reads SQLite only)

### 4. `repo_guidance_docs`
Purpose: Check whether repos have basic agent/human guidance documents.

Data source: Read-only GitHub API through gh CLI.

Default config:
```yaml
enabled: false
interval_hours: 168
required_files:
  - README.md
  - AGENTS.md
optional_files:
  - CLAUDE.md
  - CONTRIBUTING.md
freshness_days: 180
create_issue_drafts: false
```

Finding rule: required file missing OR required file has no recent commit within freshness_days
Severity: medium for missing AGENTS.md, low for missing README.md, low for stale docs, info for missing optional docs

Allowed read-only GitHub commands:
```bash
gh api --method GET "repos/OWNER/REPO/commits?path=PATH&per_page=1"
```

Required state: [] (reads GitHub API)
Timeouts: 20 seconds per file request

Security: Reject path traversal (no `..`, no leading `/`, no shell metacharacters, no URL schemes)

## Implementation

1. Delete the 5 wrong skill files
2. Create 4 new skill files matching spec above
3. Update `portfolio_manager/skills/builtin/__init__.py` to register the 4 new skills
4. Update `portfolio_manager/maintenance_config.py` DEFAULT_CONFIG to have the 4 spec skills
5. Update ALL test files that reference the old skills to use the new ones
6. The `MaintenanceSkillSpec` dataclass already matches spec — use it

Each skill file should:
- Define a `MaintenanceSkillSpec` instance
- Define an `execute(ctx: MaintenanceContext) -> MaintenanceSkillResult` function
- Register itself via the registry
- Use `ctx.conn` to read SQLite (skills 1-3) or subprocess for gh api (skill 4)
- Generate stable fingerprints: `sha256(project_id + skill_id + source_type + source_id + normalized_title)`
- Follow severity rules exactly

## Verification
```bash
uv run ruff check --fix --unsafe-fixes portfolio_manager/skills/ portfolio_manager/maintenance_config.py
uv run ruff format portfolio_manager/skills/ portfolio_manager/maintenance_config.py
uv run pytest tests/ -x --tb=short -q
```

All tests must pass. Fix any test failures.
