# MVP 7 Spec - Pull Request Creation and Review Ladder

## Purpose

MVP 7 turns a successful local implementation into a pull request and moves that PR through staged review. The review ladder starts with cheaper or free reviewers and escalates only when policy, risk, and budget allow.

MVP 7 may push a branch and open a pull request after explicit confirmation. It must not merge.

## What This MVP Adds

1. PR creation from a successful MVP 6 implementation job.
2. Review ladder configuration.
3. Review stage state and bounded retry loops.
4. Review feedback ingestion and classification.
5. Confirmed fix cycles for valid review comments through MVP 6 review-fix jobs.
6. Push of follow-up fix commits after MVP 6 succeeds.
7. Review artifacts and summaries.

## Explicit Non-Goals

MVP 7 must not:

```txt
auto-merge
ignore failing checks
run unbounded review loops
escalate to paid reviewers without policy approval
hide unresolved critical feedback
push unrelated changes
force push unless explicitly designed and confirmed
modify worktrees directly instead of using MVP 6 review-fix jobs
```

## User Stories

User:

```txt
Open a PR for the completed implementation of issue 42.
```

Expected behavior:

```txt
verify implementation job succeeded
verify local checks passed
push the branch only after confirmation
open a PR with linked issue, acceptance criteria, tests, risks, and QA notes
start the first configured review stage
```

User:

```txt
Continue review for PR 130.
```

Expected behavior:

```txt
fetch review comments and CI status
classify comments by severity and actionability
create a structured MVP 6 review-fix job for confirmed valid fixes
push the follow-up commit only after the fix job succeeds
rerun or re-read checks
advance or block the review stage
```

## MVP 6 Integration for Fix Loops

MVP 7 owns the review loop. MVP 6 owns worktree-modifying implementation jobs.

MVP 7 must not directly edit files, run coding harnesses ad hoc, or invent a separate fix mechanism. When review feedback needs code changes, MVP 7 creates a `review_fix` job through the MVP 6 implementation-job interface.

MVP 7 provides:

```txt
project_id
issue_number
pr_id
review_stage_id
review_iteration
expected_branch
base_sha
approved_comment_ids
fix_scope
source review artifact path
```

MVP 6 returns:

```txt
status
local commit sha
changed files
commands run
checks result
unresolved blockers
implementation artifact path
```

MVP 7 then:

```txt
verifies the fix job succeeded
verifies the local commit is on the expected PR branch
pushes the follow-up commit according to Git policy
refreshes CI and review state
increments the review iteration
advances, repeats, blocks, or asks the user
```

If MVP 6 returns `needs_user`, `blocked`, or `failed`, MVP 7 must not push and must report the blocker.

## Bounded Fix Loop Rules

Each review stage must define:

```txt
max_iterations
which severities require fixes
which reviewer comments require human confirmation
whether paid harnesses may be used for fixes
required checks after each fix
```

Default maximum:

```txt
2 fix iterations per review stage
```

After the maximum is reached, MVP 7 returns blocked with a summary of unresolved feedback and does not continue automatically.

## Review Pass Semantics

A stage passes only when:

```txt
required CI checks pass or are explicitly marked not applicable
no unresolved critical or high-confidence blocking comments remain
max iterations have not been exceeded
changed files remain within issue scope
tests remain meaningful
docs or QA notes are updated when behavior changed
```

If reviewers disagree, the stage must summarize the conflict and either ask the user or escalate according to configured policy.

## Required State

Track:

```txt
pr_id
project_id
issue_number
implementation_job_id
review_stage
reviewer_id
status
iteration
max_iterations
last_reviewed_sha
unresolved_count
critical_count
artifact_path
latest_fix_job_id
latest_pushed_sha
```

## Acceptance Criteria

MVP 7 is done when Hermes can open a confirmed PR, run staged reviews with bounded fix loops through MVP 6 review-fix jobs, push successful follow-up commits, and report whether the PR is blocked, needs user input, or ready for QA review. It still cannot merge.
