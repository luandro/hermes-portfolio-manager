# Hermes Portfolio Manager User Stories

These stories are written for audio narration. They describe the final product first, then the MVPs in roadmap order.

## FULL

I manage many repositories through one Hermes agent running on a remote machine. I add projects, set priorities, define budgets, and choose when the system is allowed to work. On each heartbeat, Hermes checks GitHub, local worktrees, provider limits, open issues, pull requests, and maintenance rules.

When an idea is rough, I can send it through Telegram as voice or text. Hermes turns it into a clear issue draft, asks only the questions that block progress, and creates a clean GitHub issue when I confirm. Private Telegram context, provider data, confidence notes, and local decision artifacts stay local unless I explicitly configure publication. When an issue is ready, Hermes prepares an isolated worktree, starts from meaningful failing tests, implements the smallest scoped change, runs the project checks, opens a pull request, and updates the docs and QA notes.

The pull request then moves through a review ladder. Cheaper reviewers go first. Stronger and paid reviewers are reserved for higher-risk work. Hermes applies valid feedback in bounded loops, watches for scope creep and weak tests, respects provider budgets, and never auto-merges high-impact changes. I get notified when a decision, QA pass, blocker, or merge approval needs human judgment.

The final product lets the machine do repetitive engineering work while I stay in control of priorities, product decisions, risk, and merge approval.

## MVP 1 - Portfolio Visibility

I ask Hermes what needs my attention. It reads the server-side project manifest, checks GitHub issues and pull requests, inspects local worktrees, and returns a concise portfolio digest. It does not change repositories, GitHub, or project configuration. This MVP proves one Hermes agent can safely observe many projects.

## MVP 2 - Project Administration

I tell Hermes to add, pause, resume, archive, remove, or reprioritize a project. Hermes updates the server-side project manifest safely, backs it up, validates it, and reports the result. It still does not create issues, branches, worktrees, pull requests, or code changes. This MVP makes the portfolio manageable from chat without SSH or manual YAML edits.

## MVP 3 - Issue Creation and Brainstorming

I give Hermes a clear request or a rough idea. If the request is ready, Hermes creates a local draft and, after confirmation, publishes a clean GitHub issue. If the idea is vague, Hermes asks focused follow-up questions, updates the draft, detects duplicates, and waits for confirmation before any GitHub mutation. This MVP turns conversation into useful issue specs without starting development.

## MVP 4 - Maintenance Skills

I ask Hermes what maintenance checks are available, what is due, or what needs attention across active projects. Hermes runs read-only maintenance skills, stores reports and findings, and can create local issue drafts for follow-up work when explicitly requested. It does not fix anything, create worktrees, run coding agents, or publish maintenance issues automatically. This MVP turns observation into repeatable maintenance work.

## MVP 5 - Worktree Preparation

I ask Hermes to prepare a worktree for a specific issue. Hermes resolves the project, validates the issue number, clones the base repo if needed, refreshes the clean base branch safely, creates a predictable issue worktree, records state, and writes artifacts. It can show the plan first, and repeated preparation is idempotent. This MVP prepares isolated workspaces for future implementation without running a coding harness.

## MVP 6 - Implementation Harness

I approve an issue for development. Hermes uses the prepared worktree, writes meaningful failing tests first, implements the smallest scoped change, runs the configured checks, and produces an implementation artifact. It does not merge or bypass review. This MVP begins controlled coding.

## MVP 7 - Pull Request and Review Ladder

I let Hermes open a pull request from a completed local implementation and move it through staged review. It starts with cheap or free reviewers, escalates only when policy and risk justify it, and sends valid review feedback back through the same controlled implementation harness for follow-up commits. Each fix loop has a limit, and unresolved risks are reported instead of chased forever. This MVP makes review systematic without spending the strongest models too early.

## MVP 8 - QA and Merge Readiness

I receive a merge-ready packet instead of a vague notification. Hermes summarizes acceptance criteria, commands run, review stages, remaining risks, and manual QA steps. Low-risk changes may be eligible for configured auto-merge; high-impact changes always wait for me. This MVP makes final human review faster and safer.

## MVP 9 - Operations and Budget Scheduling

I set model budgets, work windows, and temporary instructions like "focus on this project tonight" or "do not spend paid budget until Monday." Hermes chooses work that fits the available budget, reserves paid models for high-value decisions, and shifts to lower-risk tasks when stronger models are unavailable. Temporary instructions affect scheduling without silently changing durable project configuration. This MVP keeps autonomy cost-aware.

## MVP 10 - Constrained Autonomy

I define exactly where the system may act without asking me. Hermes can handle small, low-risk, fully reviewed changes inside project policy, while protected paths, high-impact work, and ambiguous decisions remain human-gated. This MVP completes the product as a cautious autonomous development system.
