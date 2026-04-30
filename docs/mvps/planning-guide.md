# MVP Planning Guide — How to Create Specs and Progress Plans

## Purpose

This guide explains how to design the next MVPs for the Hermes Portfolio Manager / multi-project agent system.

Use it together with:

```txt
docs/product/project-handoff.md
```

The goal is that each future chat can reliably produce:

```txt
MVPX_SPEC.md
MVPX_PROGRESS.md
```

with enough detail for a coding agent to implement the MVP safely, test-first, and without guessing.

---

# Critique of This Guide Strategy

The best context package should stay small.

Recommended files:

```txt
docs/product/project-handoff.md
docs/mvps/planning-guide.md
```

This is better than splitting the guidance across many files because future agents are less likely to miss important constraints.

## What docs/product/project-handoff.md Does

`docs/product/project-handoff.md` explains:

```txt
what the system is
where the roadmap is
what completed MVPs decided
what must not be broken
what comes next
```

## What This Guide Does

`docs/mvps/planning-guide.md` explains:

```txt
how to design the next SPEC.md
how to turn that SPEC into a PROGRESS.md
how to review both for agent-readiness
how to keep future MVPs safe and scoped
```

## Main Risk

The main risk of this guide is becoming too abstract.

To avoid that, every future MVP plan must include:

```txt
concrete tools
concrete inputs/outputs
concrete state/schema changes
concrete allowed/disallowed commands
concrete tests
concrete manual smoke tests
concrete definition of done
```

If an agent cannot implement the MVP without guessing, the plan is not ready.

## When More Files Might Be Needed

Only add more planning files if this guide becomes too large or if a topic becomes independently reusable.

Possible future files, only if needed:

```txt
SAFETY_MODEL.md
TESTING_GUIDE.md
HERMES_PLUGIN_GUIDE.md
```

Do not create these prematurely.

---

# Core Planning Principles

## 1. One MVP Adds One Capability Layer

Each MVP should introduce one clear new capability.

Good:

```txt
MVP 4: run read-only maintenance checks
MVP 5: prepare worktrees safely
MVP 6: run coding harnesses
```

Bad:

```txt
MVP 4: run maintenance, create worktrees, implement fixes, open PRs, and auto-merge
```

## 2. Do Not Skip Safety Layers

The roadmap intentionally grows slowly:

```txt
observe
manage config
create issues
run maintenance checks
prepare worktrees
implement
review
QA
budget-aware scheduling
auto-development / auto-merge policy
```

Never add a later capability into an earlier MVP.

## 3. Prefer Drafts Before External Side Effects

Before mutating GitHub, repositories, branches, worktrees, or provider budgets, prefer a local artifact first.

Examples:

```txt
issue draft before GitHub issue
worktree plan before creating worktree
implementation plan before coding harness call
review report before merge decision
```

## 4. Prefer Dry-Run Before Mutation

Any new external side effect should support dry-run when useful.

Dry-run should:

```txt
validate inputs
show intended action
run safe checks
not perform mutation
return a clear preview
```

## 5. Prefer Blocked Over Guessing

If the project, task, risk, repo, branch, or expected behavior is ambiguous, return:

```txt
status = blocked
```

or create a draft that asks questions.

Do not guess when a wrong guess could mutate GitHub, files, branches, PRs, or provider budgets.

## 6. Every Mutation Needs Safety Controls

Every new mutation must define:

```txt
lock
idempotency
duplicate prevention
crash recovery
rollback or repair path
logging/artifact trail
tests
```

If those are missing, the MVP is not implementation-ready.

## 7. Every Tool Must Be Testable Outside Hermes

Every tool should be callable through:

```txt
dev_cli.py
```

Manual Hermes tests come last.

## 8. Tool Handlers Should Be Thin

Core logic should live in pure/helper modules.

Tool handlers should:

```txt
validate inputs
call tested helpers
format shared tool result
return summary/data
```

Do not hide business logic inside Hermes-only code.

## 9. Human Confirmation Is Required for High-Impact Actions

Require explicit confirmation for:

```txt
GitHub issue creation
worktree creation if destructive or ambiguous
repo file modification
branch push
PR creation
merge
provider budget-consuming operations above threshold
```

Future low-risk auto-actions must still obey project policy and review gates.

## 10. All External Commands Must Be Explicitly Allowed

Every MVP must list:

```txt
allowed commands
disallowed commands
```

Never use:

```python
shell=True
```

unless a later design explicitly proves why it is safe. Current default: never use it.

---

# SPEC.md Template

Use this structure for every future MVP spec.

```md
# SPEC.md — Hermes Portfolio Manager Plugin MVP X: <Name>

## Purpose

What this MVP adds in one or two paragraphs.

## Roadmap Position

What came before.
What comes after.
Why this MVP exists now.

## Runtime Root

Confirm default root:

$HOME/.agent-system

Confirm root resolution order:

1. explicit root argument
2. AGENT_SYSTEM_ROOT
3. Path.home() / ".agent-system"

## What This MVP Adds

List new capabilities.

## Explicit Non-Goals

List what this MVP must not do.

## Scope Boundary

What this MVP may mutate.
What this MVP must not mutate.

## User Stories

Concrete examples of user interactions.

## New Tools

List tool names.

## Tool Specifications

For each tool:

- purpose
- input schema
- behavior
- success example
- blocked cases
- side effects

## State / Schema Changes

SQLite tables, YAML config changes, artifact files, or logs.

## Artifact Layout

Any files written under $HOME/.agent-system/artifacts.

## Allowed Commands

Exact external commands this MVP may run.

## Disallowed Commands

Commands this MVP must not run.

## Locking and Concurrency

Locks required for each mutation.

## Idempotency and Duplicate Prevention

How repeated tool calls avoid duplicate side effects.

## Failure and Recovery

What happens if the process crashes or external commands fail.

## Dry-Run Behavior

If applicable, define dry-run behavior.

## Security and Privacy Rules

Secrets, path traversal, public/private data separation, redaction.

## Dev CLI Requirements

Exact dev_cli.py commands and flags.

## Hermes Skill Requirements

Skills to add or update.

## Required Tests

Test categories and important cases.

## Manual Hermes Smoke Tests

Manual checks after pytest passes.

## Acceptance Criteria

Numbered list of completion criteria.

## Definition of Done

Plain-language final state.
```

---

# PROGRESS.md Template

Use this structure for every future MVP implementation tracker.

```md
# PROGRESS.md — Hermes Portfolio Manager Plugin MVP X: <Name>

## Goal

What this MVP must achieve.

## Agent-Readiness Verdict

Whether this plan is ready for coding agents and under what assumptions.

## Runtime Root

Confirm $HOME/.agent-system.

## Non-Negotiable Rules

List safety and implementation rules.

## Scope Boundary

What may mutate.
What must not mutate.

## Shared Tool Result Format

Repeat or reference the standard result format.

## Required Tools

List new tools.

## Required Dev CLI Commands

Exact commands and flags.

## Final Design Decisions

Important decisions that remove ambiguity.

## Phase 0 — Preflight and Regression Baseline

## Phase 1 — State / Schema / Config

## Phase 2 — Pure Logic

## Phase 3 — File / Artifact Safety

## Phase 4 — External Integration

## Phase 5 — Idempotency / Recovery / Locking

## Phase 6 — Tool Handlers and Schemas

## Phase 7 — Dev CLI Support

## Phase 8 — Hermes Skills

## Phase 9 — Security Hardening

## Phase 10 — Local E2E

## Phase 11 — Manual Hermes Smoke Tests

## Definition of Done

## Suggested Implementation Order

## Future MVPs Not Allowed Here
```

Each task inside a phase must use this format:

```md
## N.M Task Name

Status: [ ]

### Test first

Describe the meaningful test that must be written first.

### Implementation

Describe the smallest implementation needed.

### Verification

Command to run, usually pytest target.

### Acceptance

Concrete conditions that prove the task is done.
```

---

# Shared Tool Result Format

Every tool should return this shape unless a prior MVP changed it:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "tool_name",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None
}
```

Use statuses as follows:

```txt
success: operation completed
skipped: no change needed
blocked: known precondition prevented operation
failed: unexpected error
```

Blocked/skipped outcomes are controlled outcomes, not crashes.

---

# Agent-Readiness Checklist

Before calling a SPEC or PROGRESS ready, answer all of these.

## Capability Clarity

```txt
Is the MVP one clear capability layer?
Is the purpose clear?
Are non-goals explicit?
Are future-MVP features forbidden?
```

## Tool Clarity

```txt
Are all tool names listed?
Are all input schemas defined?
Are all outputs defined?
Are blocked cases defined?
Are side effects listed?
Are summaries expected to be Telegram-friendly?
```

## State Clarity

```txt
Are new SQLite tables defined?
Are schema migrations/idempotent init covered?
Are new YAML fields defined?
Are allowed states/enums defined?
Are artifact files defined?
Are public/private files classified?
```

## Safety Clarity

```txt
Are allowed commands listed?
Are disallowed commands listed?
Is shell=True forbidden?
Are secrets redacted?
Is path traversal tested?
Are duplicate side effects prevented?
Are locks defined?
Is crash recovery defined?
Is dry-run defined where useful?
Is user confirmation required for high-impact mutation?
```

## Testing Clarity

```txt
Are tests listed before implementation tasks?
Are tests meaningful?
Are external commands mocked?
Are local e2e tests included?
Are manual Hermes smoke tests included?
Is pytest the final automated gate?
```

## Agent Execution Clarity

```txt
Can a coding agent implement this without guessing?
Are exact CLI flags provided?
Are exact file paths provided?
Are exact thresholds/formulas provided when behavior is heuristic?
Are dependencies specified?
Are existing MVPs protected from regression?
```

If any answer is no, revise before implementation.

---

# Safety Checklist for New MVPs

For each new MVP, identify every mutation.

Possible mutation categories:

```txt
server config
SQLite state
local artifacts
worktrees
repository files
GitHub issues
GitHub PRs
GitHub labels/projects/milestones
branches
provider/model budgets
notifications
```

For each mutation, define:

```txt
who/what triggers it
required confirmation
lock name
idempotency key
duplicate detection
artifact/audit trail
crash recovery
dry-run behavior
rollback or repair path
tests
```

If a mutation cannot be made safe, do not include it in that MVP.

---

# Review Checklist for SPEC.md

Before creating PROGRESS.md, review the SPEC with these questions.

```txt
Is this MVP too large?
Can any part be split into a later MVP?
Are all non-goals explicit?
Are external side effects justified?
Are tool names stable and clear?
Are input schemas precise?
Are state transitions defined?
Are failures and retries defined?
Are duplicate risks handled?
Are privacy risks handled?
Are tests enough to prevent hallucinated implementation?
```

If the SPEC is not ready, revise it before creating PROGRESS.md.

---

# Review Checklist for PROGRESS.md

Before handing PROGRESS.md to a dev agent, review with these questions.

```txt
Does every task have Test first / Implementation / Verification / Acceptance?
Are tasks small enough to complete independently?
Are tasks ordered by dependency?
Are pure functions implemented before tool handlers?
Are external integrations mocked before real smoke tests?
Are security tests included before dangerous implementation?
Are local e2e flows included?
Are manual Hermes smoke tests last?
Is the definition of done complete?
```

If the coding agent would need to invent behavior, revise the PROGRESS.md.

---

# Best-Practice Patterns by Capability Type

## Config Mutation MVPs

Must include:

```txt
schema validation
unknown field preservation decision
atomic write
timestamped backup
config lock
reload after write
path containment
first-run behavior
```

## GitHub Mutation MVPs

Must include:

```txt
explicit allowed gh commands
confirmation requirement
dry-run
duplicate detection
idempotency
creation/update audit files
crash recovery
mocked tests
manual test repo only
```

## Worktree Mutation MVPs

Must include:

```txt
worktree lock
dirty state detection
branch naming rules
base branch detection
no destructive clean/reset without explicit design
conflict recovery
path containment
```

## Coding Harness MVPs

Must include:

```txt
provider/model selection policy
budget check
task scope guard
test-first enforcement
artifact logs
timeout behavior
cancellation behavior
no protected path modification without escalation
```

## Review Ladder MVPs

Must include:

```txt
review stages
pass/fail criteria
retry loop limits
review artifact storage
human escalation
cost limits
no merge authority unless later MVP allows it
```

## Auto-Merge MVPs

Must include:

```txt
strict project policy
low-risk-only gate
protected path exclusion
review ladder approval
tests passing
QA script generated
human override
audit trail
rollback/repair story
```

Do not implement auto-merge early.

---

# Recommended Workflow for Future Chats

Use this flow for each new MVP.

## Step 1: Ask for SPEC

Prompt:

```txt
Read docs/product/project-handoff.md and docs/mvps/planning-guide.md.
Create SPEC.md for MVP X: <name>.
Critique it carefully for ambiguity, safety gaps, missing tests, and scope creep.
Then create the revised SPEC.md as canvas.
```

## Step 2: Ask for PROGRESS

Prompt:

```txt
Now create PROGRESS.md for MVP X.
Think carefully about implementation order and best practices.
Make every task small, test-first, and verifiable.
Critique it for agent-readiness, then create the final canvas version.
```

## Step 3: Ask for Review

Prompt:

```txt
Review this implementation plan carefully.
Is it absolutely ready to hand to a dev agent?
Find ambiguity, hidden assumptions, unsafe side effects, missing tests, duplicate risks, recovery gaps, and scope creep.
Then revise it until it is implementation-ready.
```

## Step 4: Handoff to Dev Agent

Prompt:

```txt
Read docs/product/project-handoff.md, docs/mvps/planning-guide.md, MVPX_SPEC.md, and MVPX_PROGRESS.md.
Run pytest first.
Do not start implementation unless prior MVPs are green.
Follow MVPX_PROGRESS.md exactly, test-first.
```

---

# Minimal SPEC Generation Prompt

Use this when starting a new MVP:

```txt
Read docs/product/project-handoff.md and docs/mvps/planning-guide.md.
Create MVPX_SPEC.md for <MVP name>.
It must follow the staged safety roadmap, preserve prior MVP boundaries, define exact tools, schemas, state changes, allowed/disallowed commands, locking, idempotency, recovery, dev CLI, tests, manual smoke tests, acceptance criteria, and definition of done.
Critique it first, then create the final canvas document.
```

---

# Minimal PROGRESS Generation Prompt

Use this after the SPEC is approved:

```txt
Read docs/product/project-handoff.md, docs/mvps/planning-guide.md, and MVPX_SPEC.md.
Create MVPX_PROGRESS.md.
Make it agent-ready: small scoped tasks, each with Test first, Implementation, Verification, and Acceptance.
Include preflight regression, pure logic before handlers, mocked external integrations, security hardening, local e2e, manual Hermes smoke tests, definition of done, and future-MVP exclusions.
Critique it carefully, then create the final canvas document.
```

---

# Final Rule

The best MVP plan is not the longest plan.

The best MVP plan is the one where a coding agent can implement safely without guessing, without breaking prior MVPs, and without accidentally expanding scope.
