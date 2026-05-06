# Implementation Run

Skill for MVP 6 implementation harness orchestration. Provides confirmed, test-first implementation jobs that run a configured coding harness inside a clean MVP 5 issue worktree.

## Plan-First Workflow

**Always call `portfolio_implementation_plan` before `portfolio_implementation_start`.**

The plan tool is read-only. It resolves the source artifact, validates the harness configuration, checks preflight conditions, and returns a proposed command + workspace layout. It writes no SQLite rows and no artifacts. Use it to inspect readiness before committing to a real run.

Calling `portfolio_implementation_start` without first reviewing the plan output is an error in workflow, not in code. The plan tells you whether the worktree is clean, the branch matches, the source artifact exists, and the harness is configured. Skipping it means flying blind.

## Confirm-Required

All mutating operations require `confirm=true`.

- `portfolio_implementation_start` with `confirm=false` returns a dry-run result (status `blocked`) and performs no mutation. No SQLite row is inserted, no harness is invoked, no artifacts are written.
- `portfolio_implementation_apply_review_fixes` with `confirm=false` behaves identically: plan-only, no side effects.
- Only `confirm=true` triggers the full orchestrator: lock acquisition, SQLite row insertion, harness invocation, artifact writes, and local commit.

This is a hard gate. There is no auto-confirm path. The operator or the calling agent must explicitly set `confirm=true` after reviewing the plan output.

## Blocked-Over-Guessing

When the outcome is uncertain, return `status=blocked` with a reason. Never guess.

Specific cases that must return `blocked` rather than proceeding or failing:

- Lock contention: another implementation job is running for the same project+issue.
- Preflight failure: worktree is dirty, branch mismatch, source artifact missing.
- Harness configuration not found: the `harness_id` does not exist in `harnesses.yaml`.
- Scope guard violation: changed files exceed the max or touch protected paths.
- Test quality failure: no meaningful tests detected for an initial implementation.
- Missing approved comment IDs for a review-fix job.

`status=failed` is reserved for unexpected exceptions after mutation has started. `status=needs_user` is for explicit product-judgment requests surfaced by the harness. When in doubt, `blocked` is always the safe choice.

## Six Tools

| Tool | Type | Description |
|------|------|-------------|
| `portfolio_implementation_plan` | Read-only | Plan an implementation job. Resolves source artifact, validates harness config, runs preflight checks. Writes nothing. |
| `portfolio_implementation_start` | Mutating (requires confirm=true) | Run an `initial_implementation` job in the prepared issue worktree. Invokes the harness, collects changed files, runs checks, enforces scope guard and test quality, creates a local commit if all gates pass. |
| `portfolio_implementation_apply_review_fixes` | Mutating (requires confirm=true) | Run a `review_fix` job scoped to approved comment IDs provided by MVP 7. Same orchestrator as start, but with fix_scope and approved_comment_ids constraints. |
| `portfolio_implementation_status` | Read-only | Look up a job by job_id or by project+issue. Returns current status, artifact paths, and failure reason if applicable. |
| `portfolio_implementation_list` | Read-only | List jobs filtered by project, issue number, and/or status. |
| `portfolio_implementation_explain` | Read-only | Explain why a job is blocked or needs_user. Returns the block reason and suggested next steps. |

## Non-Goals

This skill does **not**:

- Push branches to any remote.
- Create, merge, or update pull requests.
- Make review pass/fail decisions.
- Classify or re-classify PR review comments.
- Call any `gh` subcommand that mutates remote state.
- Create, refresh, clean, reset, stash, or delete worktrees. Worktree lifecycle is owned by MVP 5. The harness subprocess may modify files inside the issue worktree, and a single local commit is created after all gates pass, but no worktree mutation happens outside the harness's own changes.
- Pick a provider or model for the harness.
- Load or manage API keys.
- Retry failed harness invocations.

## Review-Fix Callable Only After MVP 7

`portfolio_implementation_apply_review_fixes` accepts `approved_comment_ids` as a required parameter. These IDs represent PR review comments that have been explicitly approved by the review system.

MVP 7 (Review Ladder) is responsible for:

- Running review stages on PRs.
- Classifying review comments.
- Producing the list of approved comment IDs that the implementation harness should address.

Until MVP 7 is implemented and provides approved comment IDs, the `apply_review_fixes` tool cannot be meaningfully called. It is registered and its schema is valid, but it will return `blocked` when invoked without approved comment IDs from the review system.

Do not fabricate or guess comment IDs. Do not bypass the review classification flow.

## Operator Prerequisites

MVP 6 does **not** pick a provider or model and does **not** load API keys. The operator (or the systemd unit / shell profile that launches the Hermes agent) is responsible for exporting the harness's required environment variables before any `portfolio_implementation_start` call.

### Required Environment Variables by Harness

**forge:**
```bash
export FORGE_SESSION__PROVIDER_ID=<provider>
export FORGE_SESSION__MODEL_ID=<model>
# Optionally:
export FORGE_HTTP_READ_TIMEOUT=<seconds>
```

**codex:**
```bash
export OPENAI_API_KEY=<key>
```

**claude-code:**
```bash
export ANTHROPIC_API_KEY=<key>
```

### What Happens If Environment Variables Are Absent

If the required environment variables are not present in the runtime environment, the job will still be dispatched, but the harness subprocess will fail at runtime. MVP 6 surfaces the harness exit code in `error.json` and does **not** retry. The job status will be set to `failed`.

MVP 6 only forwards environment variables that are:

1. Listed in the harness entry's `env_passthrough` field in `harnesses.yaml`, AND
2. Already present in the runtime environment of the process invoking the plugin.

It never injects, creates, or manages credentials. The operator must ensure the correct variables are exported before invoking any implementation tool with `confirm=true`.
