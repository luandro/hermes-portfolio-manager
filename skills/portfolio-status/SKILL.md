---
name: portfolio-status
description: Report current status of all projects in the portfolio.
---

# Portfolio Status

Call `portfolio_status` to produce a concise snapshot of the entire project portfolio on the server.

## Instructions

1. Call the `portfolio_status` tool with `filter=needs_user` to surface items that require human attention.
2. Keep the response concise — 3–5 sentences in a Telegram-friendly format.
3. Highlight the following in order of importance:
   - **User decisions needed** — issues that are stuck in `needs_triage` or `needs_user_questions` state.
   - **PRs ready for review** — PRs with `ready_for_human` or `qa_required` state.
   - **Worktree blockers** — any `merge_conflict`, `rebase_conflict`, `dirty_uncommitted`, or `missing` worktrees.
   - **Warnings** from GitHub sync or worktree inspection.
4. Include project IDs and issue/PR numbers so the user can take action directly.
5. If nothing needs attention, state that clearly.

## Example response format

```
Portfolio status:
- proj-a issue #47: Fix login bug (needs triage)
- proj-b PR #130: Fix auth (ready for review)
- /srv/worktrees/proj-a is dirty: auth.py
1 worktree needs attention, 3 clean.
```
