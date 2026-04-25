---
name: portfolio-heartbeat
description: Periodic health check across all portfolio projects.
---

# Portfolio Heartbeat

Call `portfolio_heartbeat` to run a read-only periodic health check across all configured projects on the server.

## Instructions

1. Call the `portfolio_heartbeat` tool. It will:
   - Validate server-side config.
   - Check GitHub CLI availability and authentication.
   - Sync open issues and PRs from each project's GitHub repo.
   - Inspect local worktrees for each project.

2. **Read-only restrictions**: This tool MUST NOT create, modify, or delete any resources on GitHub or the server. It only reads data and stores it locally in the state database.

3. Return the result as a concise digest that includes:
   - **Blockers** — GitHub CLI unavailable, not authenticated, lock already held.
   - **User decisions needed** — issues stuck in `needs_triage` or `needs_user_questions`.
   - **PRs ready for review** — PRs with `ready_for_human` or `qa_required` state.
   - **Dirty or conflicted worktrees** — any `merge_conflict`, `rebase_conflict`, `dirty_uncommitted`, or `dirty_untracked` worktrees.
   - **Warnings** — repo inaccessible, rate limiting, sync failures.

4. Format the response as a short Telegram-friendly message.
5. If everything is clean, confirm that concisely.

## Example response format

```
Portfolio heartbeat complete:
3 projects checked, 14 issues, 3 PRs.
1 dirty worktree found.
No warnings.
```
