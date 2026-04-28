---
name: issue-brainstorm
description: Brainstorm rough ideas into structured issue drafts using the portfolio-manager plugin.
---

# issue-brainstorm

Use for: rough ideas, voice notes, vague feature requests.

## Process

1. Resolve project first with `portfolio_project_resolve`.
   - If ambiguous, ask user to choose from candidates.
   - If not found, tell user no matching project exists.

2. Call `portfolio_issue_draft` to create a local draft.
   - Pass `text` from user's description.
   - Optionally pass `project_ref` if known.

3. Call `portfolio_issue_questions` to read clarifying questions.

4. Ask only the most important questions concisely. Don't ask every question.

5. Call `portfolio_issue_update_draft` with user's answers.
   - Pass `draft_id` and `answers` text.

6. Ask for confirmation before `portfolio_issue_create_from_draft`.
   - Use `dry_run=true` to preview if user wants.

7. When user confirms, call `portfolio_issue_create_from_draft` with `confirm=true`.

## Safety Rules

- Do NOT start development work.
- Do NOT create branches or worktrees.
- Do NOT modify repository files.
- Do NOT create GitHub issues without explicit user confirmation.
- Never include private Telegram metadata in GitHub issue bodies.
