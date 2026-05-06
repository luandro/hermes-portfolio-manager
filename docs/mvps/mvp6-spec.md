# MVP 6 Spec - Implementation Harness Orchestration

## Purpose

MVP 6 starts controlled implementation work in prepared issue worktrees. It runs a configured coding harness only after an issue has a local draft/spec, a prepared clean worktree from MVP 5, and explicit user confirmation.

MVP 6 produces implementation artifacts and may create local commits. It must not push branches, open pull requests, run review ladders, merge, or auto-develop on a schedule.

## Roadmap Position

Previous layers observe the portfolio, manage projects, create issues, run maintenance checks, and prepare worktrees. MVP 6 adds implementation execution only.

Next layers handle PR creation, staged review, QA readiness, budget-aware scheduling, and constrained autonomy.

## What This MVP Adds

1. Implementation job state in SQLite.
2. Implementation artifacts under `$ROOT/artifacts/implementations/`.
3. Harness configuration read from server-side policy.
4. A preflight gate that requires a clean MVP 5 issue worktree.
5. Test-first execution requirements.
6. Scope-creep and test-quality checks.
7. Reusable harness job types for initial implementation and later review fixes.
8. Local commit creation when implementation succeeds.
9. Dev CLI and Hermes skill support.

## Explicit Non-Goals

MVP 6 must not:

```txt
create worktrees except through MVP 5 tools
push branches
open pull requests
merge pull requests
run review ladders
auto-start from cron
call paid providers without explicit command policy
change project configuration
clean, reset, stash, or delete worktrees
decide review stage pass/fail
classify PR review comments
```

## User Stories

User:

```txt
Start implementation for issue 42 in CoMapeo Cloud App.
```

Expected behavior:

```txt
resolve project and issue
verify issue draft/spec exists
verify clean prepared worktree exists
show the implementation plan
require confirmation before running the harness
run test-first implementation in the issue worktree
write artifacts
create a local commit if checks pass
return summary, commands run, files changed, tests added, and blockers
```

User:

```txt
Apply the approved review fixes for PR 130.
```

Expected behavior:

```txt
receive a structured review-fix request from MVP 7
verify the PR worktree is clean and on the expected branch
apply only the approved actionable feedback
rerun relevant checks
create a follow-up local commit
write artifacts that link back to the review stage and comments
return changed files, commit sha, commands run, and unresolved blockers
```

User:

```txt
Why did implementation stop?
```

Expected behavior:

```txt
explain the failed preflight, failing test, harness error, scope guard, dirty worktree, or ambiguous issue state
```

## Required State

Add implementation job tables or equivalent records for:

```txt
job_id
job_type
project_id
issue_number
worktree_id
pr_number
review_stage_id
source_artifact_path
status
harness_id
started_at
finished_at
commit_sha
artifact_path
failure_reason
```

Allowed statuses:

```txt
planned
blocked
running
failed
succeeded
needs_user
```

Allowed `job_type` values:

```txt
initial_implementation
review_fix
qa_fix
```

`initial_implementation` starts from an issue draft/spec before PR creation.

`review_fix` is created by MVP 7 after review feedback is classified and selected for fixing. MVP 6 must not decide which review comments are valid; it receives an approved, structured fix request and modifies the worktree safely.

`qa_fix` is reserved for MVP 8. MVP 6 may define the state shape now, but MVP 8 owns when QA feedback should create a fix job.

## Reusable Harness Job Contract

MVP 6 exposes one implementation-job interface that later MVPs can call without bypassing safety rules.

Inputs common to all job types:

```txt
project_id
issue_number
worktree_id
job_type
harness_id
source_artifact_path
instructions
expected_branch
base_sha
confirm
```

Additional inputs for `review_fix`:

```txt
pr_number
review_stage_id
review_iteration
approved_comment_ids
fix_scope
```

Naming note: `pr_number` is the GitHub PR number (e.g. 130). MVP 6 does not use a separate GitHub node-id; if a future MVP needs one it may add `pr_id` alongside, but MVP 6 schemas, SQLite columns, lock names, CLI args, and helper signatures use `pr_number` only.

Rules:

1. Every job requires explicit confirmation from the caller policy.
2. The worktree must be clean before the harness starts.
3. The worktree branch must match the expected branch.
4. The job must refuse to run if the local branch is behind or mismatched in a way MVP 6 cannot safely reason about.
5. The harness may change files only in the prepared issue worktree.
6. The job must create a local commit only after relevant checks pass.
7. The job returns local commit metadata but never pushes.
8. The job writes artifacts for the caller to inspect.
9. If feedback requires product judgment, the job returns `needs_user` instead of guessing.

MVP 7 may call this interface for review fixes, then MVP 7 owns pushing the follow-up commit and advancing the review stage.

## Artifact Layout

```txt
$ROOT/artifacts/implementations/<project_id>/issue-<issue_number>/<job_id>/
  plan.md
  preflight.json
  commands.json
  input-request.json
  test-first-evidence.md
  changed-files.json
  checks.json
  scope-check.md
  test-quality.md
  commit.json
  result.json
  error.json
  summary.md
```

Artifacts must not include hidden chain-of-thought, secrets, provider credentials, or private Telegram metadata.

## Safety Rules

1. Implementation requires explicit confirmation.
2. Worktree must be clean before the harness starts.
3. Harness must start from a local issue spec or draft artifact.
4. Meaningful failing tests must be produced or the job must explain why a test-first path is not practical.
5. Generated tests must map to acceptance criteria.
6. Scope guard must compare changed files and behavior against the issue spec.
7. If the harness dirties unrelated files, return blocked or failed with a clear summary.
8. Local commits are allowed only after configured checks pass.
9. No remote Git mutation is allowed.
10. Review-fix jobs must only address approved feedback passed by MVP 7.
11. Review-fix jobs must link artifacts back to the review stage and comment IDs that requested the fix.

## Acceptance Criteria

MVP 6 is done when Hermes can run one confirmed initial implementation job and one confirmed review-fix job in a clean prepared worktree, produce meaningful evidence, create local commits, and stop before any remote PR workflow begins.
