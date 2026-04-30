---
name: worktree-prepare
description: Plan and prepare safe local Git worktrees for issue implementation. Plan first, dry-run before mutation, require explicit confirmation.
---

# Worktree Prepare

Use this skill whenever the user asks to prepare, plan, create, refresh, list, inspect, or explain a Git worktree for an issue. Six tools are available — never call any of them without first running the plan tool.

## Tools

- `portfolio_worktree_plan` — read-only. Always call this first.
- `portfolio_worktree_prepare_base` — clones the base repo (if missing) and safely fast-forwards the base branch. Mutation tool: requires `dry_run=false` AND `confirm=true`.
- `portfolio_worktree_create_issue` — creates the issue-specific worktree at `agent/<project_id>/issue-<n>`. Mutation tool: requires `dry_run=false` AND `confirm=true`.
- `portfolio_worktree_list` — lists known worktrees (read-only by default).
- `portfolio_worktree_inspect` — inspects one worktree's clean/dirty state.
- `portfolio_worktree_explain` — turns the latest inspection into a short paragraph plus a `next_safe_action`.

## Operating Rules

1. **Plan first.** For every worktree request, call `portfolio_worktree_plan` before anything else. Show the user the plan: base path, issue path, base branch, branch name, what the tool would do.
2. **Dry-run then confirm.** Mutation tools default to `dry_run=true` and `confirm=false`. The first call previews the work. Only call again with `dry_run=false` AND `confirm=true` after the user has explicitly said "yes / go / confirm / do it".
3. **Prefer blocked over guessing.** If the project reference, issue number, base branch, or remote URL is ambiguous, return `blocked` with the reason. Never pick silently.
4. **Warn, do not block, on missing local SQLite issue.** If the issue number isn't recorded in local state, surface a warning but still let the plan proceed.
5. **Explain dirty / conflicted worktrees clearly.** Use `portfolio_worktree_explain` to translate state codes (`dirty_uncommitted`, `dirty_untracked`, `merge_conflict`, `rebase_conflict`) into one short paragraph.
6. **Suggest only the safe next action.** Possible values: `plan`, `prepare_base`, `create`, `none`. Never suggest `git reset`, `git clean`, `git stash`, force pushes, or any branch repair.

## Hard Limits — MVP 5

- **No implementation agents in MVP 5.** This skill prepares worktrees; it does not run a coding harness, run `npm`/`pnpm`/`yarn`/`pip`/`cargo`/`make`/`pytest` in managed repos, install dependencies, or modify source files.
- **No GitHub remote mutation.** Never call `gh issue create`, `gh pr *`, `git push`, `git commit`, or any other command that changes remote state. Worktree mutations are local-only.
- **No automatic cleanup.** Never delete, reset, or stash existing worktrees. If unsafe → `blocked`.

## Example Interaction

User:
```text
Prepare a worktree for issue 42 in comapeo-cloud-app.
```

Skill (after `portfolio_worktree_plan`):
```text
Plan: clone/refresh base repo at $ROOT/worktrees/comapeo-cloud-app, then create branch
agent/comapeo-cloud-app/issue-42 at $ROOT/worktrees/comapeo-cloud-app-issue-42 from origin/main.
Confirm to run it.
```

User:
```text
Create it now.
```

Skill — call `portfolio_worktree_create_issue` with `dry_run=false, confirm=true`.

If the existing worktree already matches exactly: `status="skipped"` with the matching path. Repeat calls are idempotent.

If anything mismatches (different branch, different remote, dirty tree, conflict in progress): `status="blocked"` with the reason. Tell the user what blocked it and what safe action they can take. Do not auto-resolve.
