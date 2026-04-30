# MVP 8 Spec - QA and Merge Readiness

## Purpose

MVP 8 packages a reviewed pull request into a merge-readiness decision. It generates a human QA script, summarizes evidence, and classifies whether the PR is ready for human review or eligible for later constrained auto-merge.

MVP 8 may prepare merge-ready reports. It must not perform broad autonomy or budget scheduling.

## What This MVP Adds

1. QA script generation from issue acceptance criteria and changed behavior.
2. Merge-readiness reports.
3. Risk classification using project policy and changed files.
4. Protected-path detection.
5. Human approval tracking.
6. Optional low-risk merge eligibility flag for MVP 10.

## Explicit Non-Goals

MVP 8 must not:

```txt
merge high-impact PRs
change provider budget policy
auto-start implementation work
override project protected paths
declare readiness without review and checks evidence
```

## User Stories

User:

```txt
What PRs are ready for me?
```

Expected behavior:

```txt
list reviewed PRs with CI status, review stages passed, risk, protected paths, QA status, and recommended action
```

User:

```txt
Prepare QA for PR 130.
```

Expected behavior:

```txt
create a concise manual QA script
include setup, steps, expected results, rollback notes, and screenshots or artifacts if relevant
```

## Risk Classification

Risk must be computed from explicit inputs:

```txt
project policy
issue labels
changed file paths
protected path matches
security/auth/billing/migration/deployment keywords
test and QA coverage
review ladder outcome
user override
```

High-impact PRs always require human merge approval.

## Acceptance Criteria

MVP 8 is done when Hermes can explain exactly why a PR is or is not ready to merge, provide a useful QA script, and separate low-risk eligibility from actual auto-merge execution.
