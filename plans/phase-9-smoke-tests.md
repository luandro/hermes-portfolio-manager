# Phase 9 — Manual Hermes Smoke Tests

## Goal

Install portfolio-manager plugin into Hermes, verify all tools work live, then set up the heartbeat cron job.

## Steps

### 9.1 Install plugin into Hermes

Hermes plugin system needs `plugin.yaml` + `__init__.py` in same directory.

Current state:
- `plugin.yaml` at project root
- `__init__.py` in `portfolio_manager/` (not at root)

Fix: create root `__init__.py` that imports `register` from `portfolio_manager`.

Then:
1. Symlink: `~/.hermes/plugins/portfolio-manager/` -> project root
2. Enable: `hermes plugins enable portfolio-manager`
3. Restart Hermes session
4. Verify: no plugin errors in logs

### 9.2 Prepare projects.yaml

Create `/srv/agent-system/config/projects.yaml` with 2+ test projects.

Must reference actual GitHub repos that exist and are accessible via `gh`.

### 9.3 Call portfolio_ping inside Hermes

Ask "Call portfolio_ping." — expect "Portfolio plugin is loaded."

### 9.4 Test portfolio_project_list

Ask "List my managed projects." — expect project list.

### 9.5 Run portfolio heartbeat

Ask "Run the portfolio heartbeat." — expect full heartbeat.

### 9.6 Create Hermes cron job

Create cron job:
- Name: Portfolio heartbeat
- Schedule: every 30 minutes
- Skill: portfolio-heartbeat
- Prompt: Run the read-only portfolio heartbeat.

### 9.7 Update PROGRESS.md

Mark Phase 9 complete. Update Definition of Done.
