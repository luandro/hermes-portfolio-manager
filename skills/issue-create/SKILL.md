---
name: issue-create
description: Create clear GitHub issues using the portfolio-manager plugin.
---

# issue-create

Use for: clear GitHub issue creation requests with structured title/body.

## Process

1. Resolve project first. If ambiguous, ask user to choose.
2. If request is vague, use `portfolio_issue_draft` instead.
3. Require confirmation before `portfolio_issue_create` or `portfolio_issue_create_from_draft`.
4. Use dry-run when user asks to preview.

## Safety Rules

- Never include private Telegram metadata in GitHub issues.
- Never create labels automatically.
- Never start implementation.
- Require explicit user confirmation for GitHub mutations.
