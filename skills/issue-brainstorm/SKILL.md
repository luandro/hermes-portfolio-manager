---
name: issue-brainstorm
description: Brainstorm rough ideas into structured issue drafts using the portfolio-manager plugin.
---

# issue-brainstorm

Use for: rough ideas, voice notes, vague feature requests.

## Process

1. Resolve project first. If ambiguous, ask user to choose.
2. Call `portfolio_issue_draft` to create a local draft.
3. Ask only the most important clarifying questions.
4. Call `portfolio_issue_update_draft` with user answers.
5. Ask for confirmation before `portfolio_issue_create_from_draft`.
6. Use dry-run if user wants to preview.

## Safety Rules

- Do NOT start development.
- Do NOT create branches or worktrees.
- Do NOT modify repositories.
- Do NOT create GitHub issues without confirmation.
