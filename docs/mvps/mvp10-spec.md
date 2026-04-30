# MVP 10 Spec - Constrained Autonomy and Auto-Merge Policy

## Purpose

MVP 10 adds narrowly scoped autonomous action for low-risk work that has already passed the previous safety layers. It can auto-run eligible tasks and may auto-merge only when project policy, risk, review, QA, and budget gates all pass.

This MVP completes the cautious autonomy story. It must default to blocked or human review when anything is ambiguous.

## What This MVP Adds

1. Auto-development eligibility policy.
2. Auto-merge eligibility policy.
3. Protected-path hard blocks.
4. Confidence and risk thresholds.
5. Human override and kill-switch controls.
6. Full audit trails for autonomous decisions.

## Explicit Non-Goals

MVP 10 must not:

```txt
auto-merge high-impact changes
auto-merge protected paths
override failing checks
skip review ladder stages
spend beyond provider budgets
hide autonomous actions from logs or notifications
```

## User Stories

User:

```txt
Allow this project to auto-merge low-risk docs fixes only.
```

Expected behavior:

```txt
store the durable policy
limit auto-merge to matching low-risk docs changes
require all checks, review stages, QA readiness, and protected-path gates
notify the user after action
```

User:

```txt
Pause all autonomous actions.
```

Expected behavior:

```txt
immediately stop new auto-development and auto-merge actions
let already-running safe read-only checks finish
report active jobs that need manual handling
```

## Auto-Merge Gates

Every auto-merge must satisfy:

```txt
project explicitly enables auto-merge for this task class
change is low risk
no protected paths changed
issue scope is satisfied
tests and CI pass
review ladder passes
QA readiness is complete or not applicable
provider budget policy was respected
no unresolved user questions remain
branch is up to date according to project policy
audit artifact is written before merge
```

If any gate is unknown, the result is blocked.

## Acceptance Criteria

MVP 10 is done when Hermes can safely handle a narrow class of low-risk work end to end while preserving human control over high-impact, ambiguous, protected, or policy-sensitive changes.
