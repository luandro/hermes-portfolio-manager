---
name: issue-create
description: Create clear GitHub issues using the portfolio-manager plugin.
---

# issue-create

Use for: clear GitHub issue creation requests with structured title/body.

## Process

1. Resolve project first with `portfolio_project_resolve`.
   - If ambiguous, ask user to choose.
   - If not found, suggest available projects via `portfolio_project_list`.

2. If request is vague, use `issue-brainstorm` flow instead (create draft + questions).

3. For clear requests, use `portfolio_issue_create` with:
   - `project_id` from resolved project
   - `title` and `body` from user's request
   - `dry_run=true` to preview first (optional)
   - `confirm=true` to actually create

4. Use `portfolio_issue_create_from_draft` when working from an existing draft.

5. Use dry-run whenever user says "preview" or "show me first".

## Safety Rules

- Never include private Telegram metadata in GitHub issues.
- Never include readiness scores, internal notes, or chain-of-thought in public bodies.
- Never create labels automatically unless user explicitly provides them.
- Never start implementation, create branches, or modify repositories.
- Require explicit user confirmation for all GitHub mutations.
- Run duplicate detection before creating issues.
