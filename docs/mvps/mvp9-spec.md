# MVP 9 Spec - Operations, Temporary Overrides, and Budget Scheduling

## Purpose

MVP 9 adds operational policy for when Hermes should work, what it should prioritize, and which providers or models it may spend. It also formalizes temporary user overrides such as "focus on this project tonight" without changing durable project configuration.

## What This MVP Adds

1. Provider and model budget state.
2. Work windows and pause policies.
3. Temporary operating directives.
4. Task ranking by priority, risk, budget, and time window.
5. Budget-aware model routing.
6. Digest and immediate notification rules.

## Explicit Non-Goals

MVP 9 must not:

```txt
change durable project config for temporary commands
auto-merge
bypass review stages
spend paid provider budget without configured limits
hide skipped work caused by budget or time-window policy
```

## User Stories

User:

```txt
For tonight, focus on EDT Website Migration and do not spend paid model budget.
```

Expected behavior:

```txt
store a temporary directive with expiry
rank EDT work first
skip paid-provider tasks
report the override in heartbeat summaries
leave durable project priority unchanged
```

User:

```txt
Set DeepSeek to three dollars per day and thirty dollars per month.
```

Expected behavior:

```txt
write durable provider budget config safely
track daily and monthly usage
reserve DeepSeek for configured high-value stages
block or downgrade tasks when the budget is exhausted
```

## Temporary Override Rules

Temporary directives must include:

```txt
directive_id
scope
reason
created_at
expires_at
source
status
```

They may affect:

```txt
project ranking
allowed task types
provider spending
notification urgency
work windows
```

They must not mutate:

```txt
projects.yaml durable priority
auto-merge policy
protected paths
review ladder config
provider budget ceilings
```

## Budget Accounting Rules

Budget state must record:

```txt
provider
model
estimated_cost
actual_cost if available
daily total
monthly total
remaining budget
source of measurement
last refreshed timestamp
```

If actual cost cannot be fetched, the system must mark estimates clearly and avoid treating estimates as exact billing truth.

## Acceptance Criteria

MVP 9 is done when heartbeat scheduling can explain what work was run, skipped, deferred, or downgraded because of priority, time windows, temporary directives, or provider budget.
