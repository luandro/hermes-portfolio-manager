# Project Handoff — Hermes Portfolio Manager / Multi-Project Agent System

## Purpose of This Document

This is the entry-point handoff document for the next agent working on the Hermes Portfolio Manager project.

The goal is to make the next agent productive without needing the prior conversation history.

Read this document first. Then verify the implementation status in the repository before continuing.

---

# Executive Summary

Hermes Portfolio Manager is a **single-agent, multi-project automation system** built around Hermes.

One Hermes Agent manages many GitHub projects from a server-side configuration stored under:

```txt
$HOME/.agent-system
```

The system is designed to run on a remote machine or VPS. Hermes provides the conversation interface, Telegram/Slack-style messaging, skills, plugins, and scheduled heartbeats. The Portfolio Manager plugin provides project state, GitHub sync, project administration, issue creation, and future implementation/review automation.

The long-term vision is:

```txt
User creates or discusses work through Telegram/Hermes
↓
Hermes turns rough ideas into good GitHub issues/specs
↓
System safely prepares worktrees and runs coding agents
↓
Review agents inspect PRs in a staged review ladder
↓
User is notified only when attention, QA, or merge approval is needed
```

The system must grow in safe stages. Each MVP has strict boundaries.

---

# Current Roadmap Position

MVP 6 is the current implementation boundary. Treat MVPs 1-5 as the baseline and MVP 6 as implemented (automated tests green; manual smoke deferred). The handoff table reflects actual status.

## Status Table

| Area | Intended Status | Required Verification |
|---|---:|---|
| MVP 1 - Portfolio visibility / read-only heartbeat | Baseline | Run full tests; verify Hermes plugin loads; run read-only heartbeat smoke test |
| MVP 2 - Project administration | Baseline | Run full tests; verify project add/pause/resume/archive flow using test root |
| MVP 3 - Issue creation and brainstorming | Baseline | Run full tests; verify draft, dry-run, duplicate detection, and create-from-draft using test repo or mocks |
| MVP 4 - Maintenance skills | Merge boundary | Run full tests; verify maintenance tools and local draft behavior |
| MVP 5 - Worktree preparation | Implemented (automated tests green; manual smoke deferred) | Run full tests; verify plan / prepare-base / create-issue tools dry-run + confirm flow against `/tmp/agent-system-test` with the local bare-repo fixture |
| MVP 6 - Implementation harness orchestration | Implemented (automated tests green; manual smoke deferred) | Run full tests; verify plan/start/status/list/explain tools and E2E fake-harness flow against `/tmp/agent-system-test` |
| MVP 7-10 - Review, QA, operations, constrained autonomy | Roadmap specs only | Must not implement before previous MVPs are green |

## Verification Gate Before New Work

Before starting MVP 7 or changing architecture, run:

```bash
pytest
```

Then verify, at minimum:

```txt
MVP 1: portfolio status and heartbeat work.
MVP 2: project admin works with $HOME/.agent-system or test root.
MVP 3: issue draft and dry-run issue creation work without unsafe side effects.
MVP 4: maintenance checks, reports, and optional local draft creation work.
MVP 5: worktree plan / prepare-base / create-issue tools work with test root.
MVP 6: implementation plan/start/status/list/explain tools work; E2E fake-harness flow passes.
```

If any MVP 1-6 tests fail, fix them before starting MVP 7 design or implementation.

---

# Non-Negotiable Architecture Decisions

These decisions are settled unless the user explicitly changes them.

## One Hermes Agent, Many Projects

Do not create one Hermes Agent per repository.

The architecture is:

```txt
One Hermes Agent
↓
Portfolio Manager plugin
↓
Server-side project manifest
↓
Many GitHub projects
```

## Server-Side Config Only

Project automation policy lives on the server, not inside repositories.

Do not require repo-local project YAML.

Repos may still contain normal guidance files such as:

```txt
README.md
AGENTS.md
CLAUDE.md
package.json
Makefile
justfile
```

But Portfolio Manager configuration belongs under:

```txt
$HOME/.agent-system/config/
```

## Default System Root

The default runtime root is:

```txt
$HOME/.agent-system
```

Implementation must use:

```python
Path.home() / ".agent-system"
```

Do not use:

```txt
/srv/agent-system
/usr/HOME/.agent-system
```

Root resolution priority:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

## SQLite Is the Local Runtime State Store

SQLite stores runtime state:

```txt
projects
issues
pull_requests
worktrees
heartbeats
heartbeat_events
locks
issue_drafts
```

The server-side YAML config remains the source of truth for project configuration.

SQLite reflects runtime state, sync state, and workflow state.

## Test-First Development

Every implementation task must follow:

```txt
1. Write or update a meaningful test.
2. Confirm the test fails for the expected reason.
3. Implement the smallest change needed.
4. Confirm the test passes.
5. Run the relevant test group.
6. Only then continue.
```

Do not implement broad features without tests.

## Safety Ladder

The MVPs intentionally increase capability slowly:

```txt
MVP 1: read-only portfolio visibility
MVP 2: project config mutation only
MVP 3: GitHub issue creation only
MVP 4: maintenance checks only
MVP 5: worktree preparation
MVP 6: implementation harness orchestration
MVP 7: pull request creation and review ladder
MVP 8: QA scripts and merge readiness
MVP 9: operations, temporary overrides, and provider/budget-aware scheduling
MVP 10: constrained auto-development / auto-merge policy
```

Do not skip ahead.

---

# Runtime Layout

Expected runtime layout:

```txt
$HOME/.agent-system/
  config/
    projects.yaml
    providers.yaml
    review-ladders.yaml
    skills.yaml
    telegram.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
    issues/
  backups/
```

Only some files are required in early MVPs.

## Required by MVP 1

```txt
config/projects.yaml
state/state.sqlite
worktrees/
logs/
artifacts/
```

## Added by MVP 2

```txt
backups/
```

## Added by MVP 3

```txt
artifacts/issues/<project_id>/<draft_id>/
  original-input.md
  brainstorm.md
  questions.md
  spec.md
  github-issue.md
  metadata.json
  creation-attempt.json
  github-created.json
  creation-error.json
```

---

# Plugin Layout

Expected Hermes plugin layout:

```txt
~/.hermes/plugins/portfolio-manager/
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
  config.py
  github_client.py
  worktree.py
  state.py
  summary.py
  errors.py
  dev_cli.py
  issue_resolver.py
  issue_drafts.py
  issue_artifacts.py
  issue_github.py
  skills/
    portfolio-status/
      SKILL.md
    portfolio-heartbeat/
      SKILL.md
    project-admin/
      SKILL.md
    issue-brainstorm/
      SKILL.md
    issue-create/
      SKILL.md
```

If actual layout differs, update this document only after verifying implementation.

---

# Source Documents

The detailed specs and progress trackers should exist as separate files or canvas-exported markdown documents.

Expected handoff package:

```txt
docs/product/project-handoff.md
docs/mvps/mvp1-spec.md
docs/mvps/mvp1-progress.md
docs/mvps/mvp2-spec.md
docs/mvps/mvp2-progress.md
docs/mvps/mvp3-progress.md
docs/mvps/mvp4-spec.md
docs/mvps/mvp4-progress.md
docs/mvps/mvp5-spec.md
docs/mvps/mvp6-spec.md
docs/mvps/mvp7-spec.md
docs/mvps/mvp8-spec.md
docs/mvps/mvp9-spec.md
docs/mvps/mvp10-spec.md
```

If files have different names, locate them and update this section.

Current planned documents from this work:

```txt
docs/mvps/mvp1-spec.md — Hermes Portfolio Manager Plugin MVP 1
docs/mvps/mvp1-progress.md — Hermes Portfolio Manager Plugin MVP 1, Agent-Ready Version
docs/mvps/mvp2-spec.md — Hermes Portfolio Manager Plugin MVP 2: Project Administration
docs/mvps/mvp2-progress.md — Hermes Portfolio Manager Plugin MVP 2: Project Administration, Agent-Ready Revised Version
docs/mvps/mvp3-progress.md — Hermes Portfolio Manager Plugin MVP 3: Issue Creation and Brainstorming, Final Agent-Ready Version
docs/mvps/mvp4-spec.md — Hermes Portfolio Manager Plugin MVP 4: Maintenance Skills
docs/mvps/mvp4-progress.md — Hermes Portfolio Manager Plugin MVP 4: Maintenance Skills
docs/mvps/mvp5-spec.md — Hermes Portfolio Manager Plugin MVP 5: Worktree Preparation
docs/mvps/mvp6-spec.md — Hermes Portfolio Manager Plugin MVP 6: Implementation Harness Orchestration
docs/mvps/mvp7-spec.md — Hermes Portfolio Manager Plugin MVP 7: Pull Request Creation and Review Ladder
docs/mvps/mvp8-spec.md — Hermes Portfolio Manager Plugin MVP 8: QA and Merge Readiness
docs/mvps/mvp9-spec.md — Hermes Portfolio Manager Plugin MVP 9: Operations, Temporary Overrides, and Budget Scheduling
docs/mvps/mvp10-spec.md — Hermes Portfolio Manager Plugin MVP 10: Constrained Autonomy and Auto-Merge Policy
```

---

# MVP 1 Summary — Portfolio Visibility / Read-Only Heartbeat

## Purpose

MVP 1 proves that one Hermes Agent can manage many projects safely in read-only mode.

It validates config, lists projects, syncs open GitHub issues/PRs, inspects local worktrees, records SQLite state, and returns concise portfolio summaries.

## Tools

```txt
portfolio_ping
portfolio_config_validate
portfolio_project_list
portfolio_github_sync
portfolio_worktree_inspect
portfolio_status
portfolio_heartbeat
```

## Skills

```txt
portfolio-status
portfolio-heartbeat
```

## Safety Boundary

MVP 1 must not mutate GitHub or repositories.

Allowed GitHub commands:

```txt
gh --version
gh auth status
gh issue list
gh pr list
```

Allowed Git commands:

```txt
git status
git branch
git rev-parse
```

Disallowed:

```txt
git pull
git rebase
git merge
git reset
git clean
git stash
git checkout
git switch
git commit
git push
gh issue create
gh pr create
gh pr merge
```

## Verification

Run:

```bash
pytest
python dev_cli.py portfolio_ping --json
python dev_cli.py portfolio_project_list --root /tmp/agent-system-test --json
python dev_cli.py portfolio_heartbeat --root /tmp/agent-system-test --json
```

Manual Hermes smoke:

```txt
Call portfolio_ping.
List my managed projects.
What needs me?
Run the portfolio heartbeat.
```

---

# MVP 2 Summary — Project Administration

## Purpose

MVP 2 lets the user manage projects through Hermes/Telegram after initial setup.

It safely mutates:

```txt
$HOME/.agent-system/config/projects.yaml
SQLite project records
$HOME/.agent-system/backups/
```

It does not start development work.

## Tools

```txt
portfolio_project_add
portfolio_project_update
portfolio_project_pause
portfolio_project_resume
portfolio_project_archive
portfolio_project_set_priority
portfolio_project_set_auto_merge
portfolio_project_remove
portfolio_project_explain
portfolio_project_config_backup
```

## Skill

```txt
project-admin
```

## Key Rules

```txt
Use $HOME/.agent-system as default root.
Use PyYAML + Pydantic v2.
Preserve unknown YAML fields as data.
First project add may create missing projects.yaml.
Other mutations block if config is missing.
All config mutations require config:projects lock.
All config writes are atomic.
Every mutation creates a backup when config existed.
Auto-merge defaults disabled.
Auto-merge is stored policy only; it does not merge anything.
Auto-merge max risk cannot be high or critical.
Remove requires explicit confirmation.
Remove does not delete worktrees, logs, artifacts, or SQLite history.
Remove sets SQLite project status to archived.
Archive is preferred over remove.
```

## GitHub Validation

Allowed read-only command:

```txt
gh repo view OWNER/REPO --json name,owner,defaultBranchRef,url,isPrivate
```

Do not create GitHub resources in MVP 2.

## Verification

Run:

```bash
pytest
python dev_cli.py portfolio_project_add --repo awana-digital/test-project --priority low --validate-github false --root /tmp/agent-system-test --json
python dev_cli.py portfolio_project_explain --project-id test-project --root /tmp/agent-system-test --json
python dev_cli.py portfolio_project_pause --project-id test-project --root /tmp/agent-system-test --json
python dev_cli.py portfolio_project_resume --project-id test-project --root /tmp/agent-system-test --json
python dev_cli.py portfolio_project_remove --project-id test-project --confirm true --root /tmp/agent-system-test --json
```

Manual Hermes smoke:

```txt
Add awana-digital/test-project as a low-priority project. Skip GitHub validation.
Explain the test project configuration.
Pause the test project.
Resume the test project.
Remove the test project with confirmation.
```

---

# MVP 3 Summary — Issue Creation and Brainstorming

## Purpose

MVP 3 lets the user create GitHub issues safely through Hermes/Telegram from clear requests or rough ideas.

It supports local issue drafts, follow-up questions, dry-runs, duplicate checks, confirmation, and safe GitHub issue creation.

## Tools

```txt
portfolio_project_resolve
portfolio_issue_draft
portfolio_issue_questions
portfolio_issue_update_draft
portfolio_issue_create
portfolio_issue_create_from_draft
portfolio_issue_explain_draft
portfolio_issue_list_drafts
portfolio_issue_discard_draft
```

## Skills

```txt
issue-brainstorm
issue-create
```

## Key Rules

```txt
Every GitHub issue created by the system must have a local draft artifact.
Direct issue creation must create a draft first.
Real GitHub issue creation requires confirm=true.
Dry-run does not require confirmation because it does not mutate GitHub.
Ambiguous project selection blocks issue creation.
Drafts use states including creating and creating_failed.
Duplicate local drafts are blocked.
Duplicate open GitHub issue titles are blocked unless allow_possible_duplicate=true.
GitHub issue creation uses gh issue create only.
Use --body-file, not shell strings.
No labels are created automatically.
No PRs, branches, worktrees, or repo files are modified.
Crash recovery uses creation-attempt.json, github-created.json, and creation-error.json.
Public GitHub issue body must not include private metadata.
Local artifacts must not contain hidden chain-of-thought.
```

## Draft States

```txt
draft
needs_project_confirmation
needs_user_questions
ready_for_creation
creating
creating_failed
created
discarded
blocked
```

## Artifact Files

Public-safe:

```txt
spec.md
github-issue.md
```

Private/local-only:

```txt
original-input.md
brainstorm.md
questions.md
metadata.json
creation-attempt.json
github-created.json
creation-error.json
```

Only `github-issue.md` is sent to GitHub.

## Allowed GitHub Mutation

```txt
gh issue create
```

Disallowed:

```txt
gh issue edit
gh issue comment
gh label create
gh pr create
gh pr merge
gh pr comment
gh api --method POST
gh api --method PATCH
gh api --method DELETE
```

## Verification

Run:

```bash
pytest
python dev_cli.py portfolio_issue_draft --project-ref comapeo-cloud-app --text "Users should export selected layers as SMP" --root /tmp/agent-system-test --json
python dev_cli.py portfolio_issue_list_drafts --project-id comapeo-cloud-app --root /tmp/agent-system-test --json
python dev_cli.py portfolio_issue_create_from_draft --draft-id <draft_id> --dry-run true --root /tmp/agent-system-test --json
```

Manual Hermes smoke:

```txt
Draft an issue for CoMapeo Cloud App: users should export selected styled layers as an SMP file for CoMapeo Mobile.
Show me what GitHub issue would be created from that draft, but do not create it yet.
I have an idea for the EDT migration. We need to make the stories better and easier to maintain.
Show my open issue drafts.
Discard the draft about export improvements.
```

---

# Current Safety Model

The project follows a staged safety model.

## MVP 1

Read-only.

No GitHub or repo mutations.

## MVP 2

Server-side config mutation only.

No GitHub issue creation.
No repo mutation.
No worktree creation.

## MVP 3

GitHub issue creation only.

No branches.
No worktrees.
No implementation.
No PRs.
No labels.
No repo file changes.

## Future MVPs

Future automation must add capability gradually:

```txt
MVP 4: maintenance checks, still no code changes
MVP 5: worktree preparation
MVP 6: implementation harness orchestration
MVP 7: pull request creation and review ladder
MVP 8: QA scripts and human merge readiness
MVP 9: operations, temporary overrides, and budget/provider-aware scheduling
MVP 10: constrained auto-development and auto-merge policy
```

Do not skip safety layers.

---

# Testing Protocol

Before changing anything:

```bash
pytest
```

For every task:

```txt
write test
confirm fail
implement minimum code
confirm pass
run relevant group
```

Before manual Hermes tests:

```bash
pytest
```

For GitHub-mutating behavior:

```txt
Use mocks by default.
Use a test repo only when explicitly configured.
Never run against production repos unless the user explicitly says so.
```

Expected test groups:

```txt
tests/test_structure.py
tests/test_config.py
tests/test_state.py
tests/test_worktree.py
tests/test_github_client.py
tests/test_summary.py
tests/test_tools.py
tests/test_security.py
tests/test_project_admin_config.py
tests/test_project_admin_tools.py
tests/test_issue_project_resolution.py
tests/test_issue_drafts.py
tests/test_issue_draft_updates.py
tests/test_issue_github_create.py
tests/test_issue_tools.py
tests/test_issue_e2e.py
tests/test_dev_cli.py
tests/test_issue_skills.py
```

---

# How the Next Agent Should Work

The next agent should follow this exact sequence.

## Step 1: Read Context

Read:

```txt
docs/product/project-handoff.md
docs/mvps/mvp1-spec.md
docs/mvps/mvp1-progress.md
docs/mvps/mvp2-spec.md
docs/mvps/mvp2-progress.md
docs/mvps/mvp3-progress.md
docs/mvps/mvp4-spec.md
docs/mvps/mvp4-progress.md
docs/mvps/mvp5-spec.md
docs/mvps/mvp5-progress.md
docs/mvps/mvp6-spec.md
docs/mvps/mvp6-progress.md
docs/mvps/mvp7-spec.md
```

If names differ, locate equivalent files.

## Step 2: Verify Implementation Status

Run:

```bash
pytest
```

Then inspect whether MVPs 1-6 are implemented or only specified.

Update the status table in this handoff if needed.

## Step 3: Do Not Start MVP 7 Until MVPs 1-6 Are Green

If tests fail, fix regressions first.

## Step 4: Continue with MVP 7

Create:

```txt
docs/mvps/mvp7-progress.md
```

Do not implement MVP 7 before writing and reviewing the progress plan.

## Step 5: Preserve Safety Boundaries

Do not add:

```txt
worktree creation
coding harness execution
PR creation
review ladders
auto-merge
provider budget routing
```

until the roadmap reaches those MVPs.

---

# Next Roadmap

MVP 6 is implemented. The remaining roadmap source files are:

```txt
docs/mvps/mvp5-spec.md  - Worktree preparation
docs/mvps/mvp6-spec.md  - Implementation harness orchestration
docs/mvps/mvp7-spec.md  - Pull request creation and review ladder
docs/mvps/mvp8-spec.md  - QA and merge readiness
docs/mvps/mvp9-spec.md  - Operations, temporary overrides, and budget scheduling
docs/mvps/mvp10-spec.md - Constrained autonomy and auto-merge policy
```

The key boundaries are:

```txt
MVP 5 prepares worktrees but does not run coding harnesses.
MVP 6 runs confirmed implementation jobs but does not push, open PRs, review, or merge.
MVP 7 may push and open PRs, then run bounded staged review, but does not merge.
MVP 8 prepares QA and merge-readiness evidence, but does not provide broad autonomy.
MVP 9 schedules work and budgets providers, including temporary overrides, but does not bypass safety gates.
MVP 10 adds constrained autonomy only for explicitly allowed low-risk work.
```

---

# Known Open Questions

The next agent should verify or resolve these before implementation decisions.

```txt
Which Hermes plugin API version is installed?
Are MVPs 1-4 actually implemented in the repo, or only specified?
Are all MVP 1-4 tests passing?
Are we using PyYAML + Pydantic v2 in the actual code?
Where are the final SPEC/PROGRESS files stored in the repository?
Which GitHub repositories are safe for real manual smoke tests?
Which Telegram users are authorized to control the system?
How should active hours / quiet hours be configured?
Which provider budget APIs or CLIs are available?
Which review agents are actually available and authenticated?
```

Do not guess these. Verify them.

---

# Do Not Do

Do not:

```txt
create one Hermes agent per repo
move project policy into repo-local YAML
return to /srv/agent-system as default root
start MVP 7 before MVPs 1-6 are verified green
add review ladders before MVP 7
add auto-merge before review ladder and QA readiness exist
silently create duplicate GitHub issues
create GitHub labels automatically
use raw gh api mutations unless a later MVP explicitly allows it
use shell=True
bypass tests
```

---

# Handoff Instruction for the Next Agent

Use this exact instruction when handing off:

```txt
Read docs/product/project-handoff.md first. Verify MVP 1-6 implementation status by running tests and inspecting the repo. Do not start MVP 7 until MVPs 1-6 are confirmed passing. If they are passing, create docs/mvps/mvp7-progress.md from docs/mvps/mvp7-spec.md using the same test-first, safety-gated style as previous MVPs.
```

---

# Final Notes

This system is meant to become powerful, but only through staged trust.

The design principle is:

```txt
observe first,
then manage configuration,
then create issues,
then run maintenance checks,
then prepare worktrees,
then implement,
then review,
then ask the human to merge.
```

Do not collapse these stages.
