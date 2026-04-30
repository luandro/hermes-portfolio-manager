Automated AI Multi-Project Development System Spec
1. Goal
Build a remote daemon that runs on a configurable heartbeat and manages multiple coding projects across repositories. On each heartbeat it should:

Sync local worktrees.

Read a global user manifest.

Read per-project manifests.

Check provider/model usage limits.

Fetch GitHub issues and PRs.

Improve issue specs when needed.

Ask the user clarifying questions when confidence is low.

Start implementation loops when confidence is high.

Run test-first development through configured coding harnesses.

Dispatch PR review agents in a cost-aware order.

Apply review feedback through bounded loops.

Notify the user when action is needed.

Update docs, agent files, manifests, logs, and branch state.

Never auto-merge high-impact changes.

The system is not a single “agent.” It is a scheduler + state machine + tool adapter layer + policy engine.

2. Core Design Principle
The heartbeat should not “think from scratch” every time.

It should resume from stored state:

manifest + repo state + issue state + PR state + model budget + logs
Every issue, branch, worktree, PR, review, question, and decision needs a durable state record. A cron alone is not enough.

Recommended local state:

~/.agent-runner/
  user-manifest.yaml
  state.sqlite
  logs/
  worktrees/
  cache/
  artifacts/
  provider-usage/
Use SQLite for state. Use YAML for human-editable manifests. Use append-only Markdown/JSONL logs for auditability.

3. System Components
┌─────────────────────────────────────────────────────────────┐
│ Cron / Systemd Timer / Scheduler                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ Heartbeat Orchestrator                                      │
│ - loads manifests                                            │
│ - checks budget/time windows                                 │
│ - locks projects/issues                                      │
│ - dispatches state-machine jobs                              │
└───────┬─────────────┬─────────────┬─────────────┬───────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌────────────┐ ┌────────────┐ ┌────────────┐ ┌───────────────┐
│ GitHub     │ │ Git/       │ │ Provider   │ │ Notification  │
│ Adapter    │ │ Worktree   │ │ Budget     │ │ Adapter       │
└────────────┘ └────────────┘ └────────────┘ └───────────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent Dispatcher                                             │
│ - spec agents                                                │
│ - planning agents                                            │
│ - coding harnesses                                           │
│ - review agents                                              │
│ - QA agents                                                  │
│ - docs/update agents                                         │
└─────────────────────────────────────────────────────────────┘
4. Manifest Structure
There should be two manifest levels:

User manifest: global machine-level policy.

Project manifest: project/repo-specific rules.

4.1 User Manifest
Example:

version: 1

runner:
  id: awana-agent-runner-01
  worktree_root: /srv/ai-worktrees
  heartbeat:
    schedule: "*/20 * * * *"
    max_runtime_minutes: 15
  timezone: Pacific/Guadalcanal
  active_windows:
    - days: ["mon", "tue", "wed", "thu", "fri"]
      start: "20:00"
      end: "07:00"
    - days: ["sat", "sun"]
      start: "00:00"
      end: "23:59"
  pause_when_user_active: true

github:
  auth:
    type: app
    app_id_env: GITHUB_APP_ID
    private_key_env: GITHUB_PRIVATE_KEY
  default_base_branch_detection: github_api

notifications:
  default_channel: telegram
  telegram:
    bot_token_env: TELEGRAM_BOT_TOKEN
    chat_id_env: TELEGRAM_CHAT_ID
  slack:
    webhook_url_env: SLACK_WEBHOOK_URL

providers:
  gemini:
    type: cli_or_api
    monthly_limit_usd: 0
    usage_limit_policy: "free_but_limited"
    models:
      - id: gemini-pro
        tier: free_or_subscription
        roles: ["spec_review", "planning_review", "qa_review"]

  openai:
    type: api
    daily_limit_usd: 10
    monthly_limit_usd: 100
    models:
      - id: codex
        tier: paid
        roles: ["implementation", "deep_review", "test_generation"]

  anthropic:
    type: cli_or_api
    daily_limit_usd: 8
    monthly_limit_usd: 80
    models:
      - id: claude-sonnet
        tier: paid
        roles: ["planning", "review"]
      - id: claude-opus
        tier: expensive
        roles: ["final_architecture_review"]

  deepseek:
    type: api
    daily_limit_usd: 3
    monthly_limit_usd: 30
    reserve_for:
      - "final_review"
      - "high_impact_architecture_review"
    models:
      - id: deepseek-reasoner
        tier: paid
        roles: ["final_review"]

coding_harnesses:
  forge:
    command: "forge"
    roles: ["implementation", "codebase_research"]
    preferred_for: ["medium_tasks", "multi_file_changes"]

  claude_code:
    command: "claude"
    roles: ["planning", "architecture", "complex_refactor_review"]
    use_policy: "sparingly"

  codex:
    command: "codex"
    roles: ["implementation", "review", "bugfix"]
    use_policy: "paid_budgeted"

  junie:
    command: "junie"
    roles: ["free_review", "ide_level_review"]
    use_policy: "prefer_when_available"

review_agents:
  - id: coderabbit
    type: github_app
    cost_tier: free_or_low
    stage: 1

  - id: greptile
    type: github_app_or_api
    cost_tier: free_or_low
    stage: 1

  - id: gemini_review
    type: model_review
    provider: gemini
    cost_tier: free_limited
    stage: 2

  - id: codex_review
    type: model_review
    provider: openai
    model: codex
    cost_tier: paid
    stage: 3

  - id: deepseek_final_review
    type: model_review
    provider: deepseek
    model: deepseek-reasoner
    cost_tier: paid_limited
    stage: 4

policies:
  max_review_iterations_per_stage: 3
  max_total_iterations_per_pr: 10
  auto_development_min_confidence: 0.82
  auto_merge_min_confidence: 0.95
  require_human_for_high_impact: true
  require_tests_first: true
  require_meaningful_tests: true
  forbid_scope_creep: true
4.2 Project Manifest
Each repo should have a project manifest in the repo itself, for example:

.agent/project.yaml
Example:

version: 1

project:
  name: comapeo-docs-support-bot
  slug: comapeo-docs-support-bot
  repo_url: git@github.com:awana-digital/comapeo-docs-support-bot.git
  priority: high
  default_branch: auto

risk_policy:
  auto_merge_allowed: true
  auto_merge_max_risk: low
  high_impact_requires_human: true
  protected_paths:
    - "infra/**"
    - ".github/workflows/**"
    - "auth/**"
    - "billing/**"
    - "migrations/**"
    - "security/**"
  small_task_labels:
    - "good first issue"
    - "small"
    - "docs"
    - "test"
  high_impact_labels:
    - "architecture"
    - "security"
    - "database"
    - "breaking-change"
    - "migration"

maintenance_tasks:
  - id: dependency_check
    schedule: weekly
    command: "npm outdated || true"
    risk: low

  - id: docs_check
    schedule: weekly
    command: "npm run docs:check"
    risk: low

  - id: test_health
    schedule: every_heartbeat
    command: "npm test"
    risk: low

quality_gates:
  required_commands:
    - "npm run lint"
    - "npm run typecheck"
    - "npm test"
  optional_commands:
    - "npm run e2e"
  min_test_meaningfulness_score: 0.75
  require_qa_script_for_ui_changes: true
  require_docs_update_for:
    - "user-facing"
    - "api"
    - "cli"
    - "config"

agent_files:
  instructions:
    - "AGENTS.md"
    - ".agent/instructions.md"
  architecture:
    - "docs/architecture.md"
  qa:
    - ".agent/qa-checklist.md"

implementation_policy:
  test_first: true
  max_files_changed_without_human_review: 12
  max_lines_changed_auto_merge: 200
  branch_prefix: "agent"
  worktree_naming: "{repo}-issue-{issue_number}"
5. Worktree Strategy
Your naming idea is good:

worktrees/
  repo-name/
  repo-name-issue-123/
  repo-name-issue-124/
But I would avoid relying on git stash as the primary sync mechanism.

Better strategy
For each issue worktree:

Detect default branch via GitHub API.

Fetch origin.

Check worktree state.

If clean:

rebase onto latest default branch.

If dirty:

create a WIP commit or patch file.

mark state as dirty.

do not continue automation until resolved.

If rebase conflict:

abort rebase.

mark worktree as conflicted.

notify user or assign a conflict-resolution agent.

Never auto-force-push unless explicitly allowed.

Recommended states:

clean
dirty_uncommitted
dirty_untracked
rebase_conflict
merge_conflict
stale_base
ready
blocked
abandoned
Why not stash-first?
git stash && rebase && stash apply can work, but it is fragile for autonomous systems. It can silently create messy states, especially with untracked files, generated files, lockfiles, and partial agent work. WIP commits or patch artifacts are easier to audit and recover.

6. Heartbeat Algorithm
Each heartbeat should follow this order:

1. Acquire global runner lock
2. Load user manifest
3. Check active window and pause rules
4. Refresh provider usage/budget state
5. Load all project manifests
6. Rank projects by priority, urgency, blocked state, and budget fit
7. For each project:
   a. Acquire project lock
   b. Sync base repo
   c. Scan worktrees
   d. Mark dirty/conflicted worktrees
   e. Fetch GitHub issues
   f. Fetch GitHub PRs
   g. Process issue state machines
   h. Process PR review state machines
   i. Run allowed maintenance tasks
   j. Write heartbeat log
8. Send batched notifications
9. Release locks
Pseudo-code:

async function heartbeat() {
  acquireGlobalLock();

  const userManifest = loadUserManifest();
  if (!isWithinActiveWindow(userManifest)) return;

  const budget = await refreshProviderBudgets(userManifest);
  const projects = await loadProjectManifests(userManifest);

  for (const project of rankProjects(projects, budget)) {
    if (!tryAcquireProjectLock(project)) continue;

    try {
      await syncProjectBase(project);
      await inspectWorktrees(project);
      await processIssues(project, budget);
      await processPullRequests(project, budget);
      await runMaintenanceTasks(project, budget);
      await writeProjectHeartbeatLog(project);
    } finally {
      releaseProjectLock(project);
    }
  }

  await sendNotificationDigest();
  releaseGlobalLock();
}
7. Issue State Machine
Every open issue should have a state.

new
↓
needs_triage
↓
spec_drafting
↓
needs_user_questions ──→ user_answered ──→ spec_drafting
↓
spec_ready
↓
implementation_candidate
↓
implementing
↓
pr_opened
↓
reviewing
↓
ready_for_human
↓
merged / closed / blocked
Issue confidence score
The system should compute a confidence level before implementation.

Inputs:

+ clear acceptance criteria
+ clear reproduction steps for bugs
+ clear files/components affected
+ test strategy identified
+ risk level low or medium
+ no missing product/design decisions
+ no security/data/privacy ambiguity
+ repo instructions found
+ build/test commands known
- vague request
- large architectural impact
- missing UI expectations
- unknown dependencies
- unclear migration/data impact
Example thresholds:

confidence_policy:
  below_0_55: ask_user_questions
  0_55_to_0_82: improve_spec_only
  0_82_to_0_94: auto_develop_but_no_auto_merge
  above_0_95: auto_develop_and_maybe_auto_merge_if_low_risk
8. Spec Generation Loop
For every issue, the agent should produce an artifact:

.agent/issues/123/
  00-original-issue.md
  01-research.md
  02-questions.md
  03-spec.md
  04-test-plan.md
  05-implementation-plan.md
  06-risk-assessment.md
  07-review-log.md
  08-qa-script.md
The issue spec should include:

# Issue 123 Spec

## Original Request

## Interpreted Goal

## Non-Goals

## User Impact

## Acceptance Criteria

## Technical Notes

## Files/Areas Likely Affected

## Test Plan

## QA Script

## Risk Level

## Open Questions

## Confidence Score

## Decision
- ask user
- auto-develop
- split into sub-issues
- block
9. Splitting Large Tasks
The system should split large/high-impact issues into child issues or internal tasks.

Split when:

- expected changes touch more than N files
- issue has multiple independent acceptance criteria
- database/schema/auth/security changes are involved
- UI + backend + infra are all affected
- confidence is medium but not high
- tests cannot be written clearly yet
Example:

Parent issue: Add offline map package builder

Child tasks:
1. Define SMP export interface
2. Add backend/browser packaging function
3. Add map layer styling UI
4. Add download flow
5. Add tests and QA script
6. Update docs
High-impact parent PRs should never auto-merge. Small child PRs may be eligible if explicitly allowed.

10. Implementation Loop
The implementation loop should always be test-first.

1. Read issue spec
2. Read repo instructions
3. Research codebase
4. Write failing meaningful tests
5. Run tests and confirm failure
6. Implement minimum change
7. Run required checks
8. Check for scope creep
9. Check for meaningless tests
10. Update docs if needed
11. Generate QA script
12. Commit
13. Push branch
14. Open PR
Meaningful test checker
The system should reject tests that:

- only test mocks
- only assert that functions were called
- duplicate implementation logic
- pass before the implementation
- have no clear link to acceptance criteria
- only snapshot large output without semantic assertions
- increase coverage without increasing confidence
A test is meaningful when it proves one acceptance criterion or prevents one likely regression.

11. PR Review Loop
The review process should be staged and bounded.

Stage 1: free/low-cost external PR reviewers
  - CodeRabbit
  - Greptile

Stage 2: free/subscription model review
  - Gemini / Junie

Stage 3: paid strategic review
  - Codex / OpenAI

Stage 4: final expensive/deep review
  - DeepSeek or strongest configured model
Important correction: do not loop “until everyone agrees it is perfect.” That can become infinite, expensive, and meaningless.

Use this instead:

review_policy:
  max_iterations_per_stage: 3
  max_total_review_iterations: 10
  required_outcome:
    - no unresolved critical comments
    - no failing required checks
    - no scope creep
    - tests meaningful
    - docs updated when needed
    - QA script generated
Review states:

pr_opened
review_stage_1_requested
review_stage_1_changes_requested
review_stage_1_passed
review_stage_2_requested
review_stage_2_passed
review_stage_3_requested
review_stage_3_passed
final_review_requested
final_review_passed
ready_for_user
auto_merge_candidate
merged
blocked
12. Auto-Merge Policy
Auto-merge should be rare and conservative.

Allowed only when all are true:

- project manifest allows auto-merge
- issue confidence >= threshold
- risk = low
- PR is small
- no protected paths touched
- all required checks pass
- all review stages required for that risk pass
- generated QA says no manual QA needed
- no unresolved comments
- branch is up to date
Never auto-merge when:

- security/auth/permissions are touched
- database migrations are touched
- infra/deploy/CI is touched
- user-facing behavior changes significantly
- API contracts change
- many files are changed
- tests were added but implementation is suspiciously broad
- model reviewers disagree
- confidence is below threshold
- project manifest forbids it
Recommended default:

auto_merge:
  default: false
  allow_only:
    - docs
    - typo
    - small_tests
    - dependency_patch_if_ci_passes
13. Notification System
Notifications should be batched unless urgent.

Notify user when:
- issue needs clarification
- spec is ready for approval
- high-impact issue was split into child tasks
- dirty/conflicted worktree blocks progress
- PR is ready for review
- QA script needs manual execution
- PR is ready to merge
- budget is low
- provider quota/rate limit blocks high-priority work
- automation detected risky behavior
Example Telegram message:

Project: comapeo-cloud-app
Issue #123: Export styled map package

Status: Needs product decision
Confidence: 0.68

Question:
Should exported SMP files include only selected user layers, or should they also include the default country catalog layers?

Suggested default:
Only selected layers.

Reply:
1 = selected layers only
2 = include default catalog layers too
3 = explain
The system should store user answers back into the issue artifact and optionally comment on GitHub.

14. Budget and Model Selection
The provider budget manager should decide what kind of work is allowed per heartbeat.

Example:

High budget available:
- architecture review
- complex implementation
- final paid review

Medium budget:
- spec refinement
- medium implementation
- free review + one paid review

Low budget:
- docs cleanup
- issue triage
- test health checks
- dependency checks
- ask user questions
- no expensive implementation
Provider state:

provider_usage:
  deepseek:
    daily_spent_usd: 1.42
    daily_limit_usd: 3.00
    monthly_spent_usd: 12.80
    monthly_limit_usd: 30.00
    current_status: available
    last_429_at: null

  openai:
    daily_spent_usd: 4.20
    daily_limit_usd: 10.00
    current_status: available

  gemini:
    usage_status: limited_available
Budget-aware task routing:

If only low/free models are available:
  - triage
  - summarize
  - improve specs
  - run tests
  - docs checks
  - low-risk issue prep

If high-quality paid models are available:
  - complex planning
  - architecture review
  - final PR review
  - high-impact bug diagnosis
15. Heartbeat Logs
Each heartbeat should write:

logs/
  2026-04-25/
    heartbeat-2026-04-25T20-00-00.jsonl
    heartbeat-2026-04-25T20-00-00.md
Markdown summary:

# Heartbeat 2026-04-25 20:00

## Runner
- Active window: yes
- Duration: 12m 40s
- Budget status: healthy

## Projects Processed
### comapeo-cloud-app
- Synced base branch: main
- Worktrees checked: 3
- Dirty worktrees: 1
- Issues triaged: 4
- Specs improved: 2
- PRs reviewed: 1
- Notifications sent: 1

## Actions Taken
- Asked user question on issue #123
- Ran CodeRabbit review on PR #130
- Generated QA script for PR #129

## Blockers
- Worktree comapeo-cloud-app-issue-118 has rebase conflict

## Next Heartbeat Suggestions
- Resolve conflict on issue #118
- Continue review loop for PR #130
JSONL should be machine-readable for dashboards.

What Makes Sense
The strongest parts of your design are:

Heartbeat-based orchestration
This is much safer than always-on autonomous agents. Each run has a bounded scope.

Manifest-driven projects
This lets different repos have different risk levels, commands, auto-merge rules, and review chains.

Budget-aware model selection
Very important. Expensive/deep models should be reserved for high-value moments.

Human-in-the-loop by confidence level
This is the right pattern: low confidence asks questions; high confidence can act.

Separate worktrees per issue
This is much better than agents fighting inside a single checkout.

Review ladder from cheap/free to expensive
Good strategy, as long as loops are bounded.

Test-first requirement
Essential. Without this, the system will create convincing but fragile PRs.

QA scripts for UI/manual flows
Also essential. Agents cannot fully validate many interface changes.

What I Would Change
1. Do not depend on stash/rebase/stash-apply
Use clean worktrees, WIP commits, or patch files. Mark dirty worktrees as blocked. Autonomous stash workflows are too easy to corrupt.

2. Do not use “until perfect” as a stop condition
Use:

max iterations + no critical comments + all checks pass + no scope creep + human approval if high impact
“Perfect” is not measurable.

3. Do not dispatch reviewers only when PR has no comments
A PR may have old comments, stale comments, resolved comments, or irrelevant comments. Better condition:

review_needed if:
- no review from required stage
- new commits since last review
- unresolved critical comments
- required stage did not pass
4. Kapa.ai should probably be used for docs/Q&A, not core PR review
Use Kapa-like systems for:

- answering issues from docs
- checking whether docs need updates
- helping agents understand documented behavior
- support-style Q&A
Use CodeRabbit/Greptile/model-reviewers for code review.

5. Add a durable state database
Manifests are desired state. They are not runtime state.

You need SQLite for:

- issue state
- PR state
- worktree state
- budget snapshots
- review attempts
- notification history
- locks
- heartbeat history
6. Add lock management
Without locks, two heartbeats or two agents can touch the same branch/worktree.

Use:

global lock
project lock
issue lock
pr lock
worktree lock
7. Add “agent misconduct checks”
You already identified the right risks. Make them explicit gates:

- scope creep detector
- acceptance criteria coverage checker
- meaningful test checker
- fake green checker
- docs drift checker
- security-sensitive path detector
- dependency bloat checker
What Is Missing
1. Installation and secrets model
You need a clear setup flow:

agent-runner init
agent-runner doctor
agent-runner install-systemd-timer
agent-runner add-project
agent-runner test-notifications
agent-runner test-github-auth
Secrets should come from environment variables, 1Password CLI, Doppler, SOPS, or a local encrypted secrets file.

Do not put tokens in manifests.

2. GitHub identity and permissions
Decide whether to use:

- GitHub App: best for multi-repo automation
- PAT: simpler MVP, worse long term
- deploy keys: useful for read/write repo access, not issues/PRs
For MVP, PAT is easier. For production, GitHub App is better.

3. Branch naming policy
Recommended:

agent/{issue-number}-{short-slug}
Example:

agent/123-export-smp-file
4. Commit policy
Agents should create structured commits:

test: add failing coverage for SMP export selection
feat: implement selected-layer SMP export
docs: document SMP export behavior
Avoid giant “agent changes” commits.

5. PR template
Every automated PR should include:

## Summary

## Linked Issue

## Acceptance Criteria Coverage

## Tests Added

## Commands Run

## Screenshots / Manual QA

## Scope Creep Check

## Risk Level

## Review Stages

## Human QA Script
6. Rollback strategy
For auto-merged low-risk PRs, the system should be able to open a revert PR automatically if CI/deploy fails after merge.

7. Dashboard
Not necessary for MVP, but soon useful.

Minimum dashboard:

Projects
Issues by state
PRs by review stage
Blocked worktrees
Provider budget
Last heartbeat
Notifications waiting for user
Recommended MVP
Do not build the full system first.

Build this sequence:

MVP 1: Heartbeat + Manifest + GitHub Read
Capabilities:

- load user manifest
- load project manifests
- fetch repos
- detect default branch
- list open issues
- list open PRs
- inspect worktrees
- write heartbeat logs
- send notification digest
No autonomous coding yet.

MVP 2: Spec Agent
Capabilities:

- read open issues
- generate issue spec artifact
- compute confidence score
- ask user questions through Telegram/Slack
- comment back to GitHub if configured
MVP 3: Worktree + Test-First Implementation
Capabilities:

- create worktree for one approved issue
- run codebase research
- write failing tests
- implement
- run checks
- open PR
- generate QA script
Only manual trigger at first.

MVP 4: Review Ladder
Capabilities:

- detect PRs needing review
- trigger CodeRabbit/Greptile where available
- collect review comments
- ask coding harness to fix comments
- run bounded loop
- notify user when ready
MVP 5: Budget-Aware Autonomy
Capabilities:

- provider budget tracking
- low/medium/high task routing
- auto-development for high-confidence low-risk issues
- conservative auto-merge for tiny safe PRs
Quick GitHub Ticket
# Build MVP heartbeat runner for multi-project AI development system

## Goal

Create the first version of a manifest-driven AI development runner that runs on a cron/systemd heartbeat, checks configured projects, syncs local worktrees, fetches GitHub issues/PRs, records state, and sends a notification digest.

This ticket does **not** implement autonomous coding yet. It establishes the safe foundation.

## Requirements

### 1. User manifest

Create support for a global YAML manifest:

- runner settings
- worktree root
- heartbeat settings
- active work windows
- GitHub auth config
- notification config
- provider/model definitions
- coding harness definitions
- review agent definitions
- global policies

Example path:

```txt
~/.agent-runner/user-manifest.yaml
2. Project manifest
Each project should support a repo-local manifest:

.agent/project.yaml
The project manifest should include:

project name

repo URL

priority

default branch strategy

maintenance tasks

quality gates

auto-merge policy

protected paths

agent instruction files

3. Heartbeat runner
Implement:

agent-runner heartbeat
The heartbeat should:

acquire a global lock

load user manifest

check active time window

load project manifests

fetch GitHub issue and PR metadata

inspect local worktrees

detect dirty/conflicted/stale worktrees

write heartbeat logs

send notification digest

release lock

4. Worktree inspection
Expected worktree naming:

{repo}
{repo}-issue-{issue_number}
The runner should detect:

clean

dirty uncommitted

dirty untracked

stale base

rebase conflict

missing repo

missing project manifest

Do not auto-stash in this MVP.

5. State database
Add SQLite state storage for:

projects

issues

PRs

worktrees

heartbeat runs

notifications

provider usage snapshots

6. Logs
Each heartbeat should write:

logs/YYYY-MM-DD/heartbeat-{timestamp}.md
logs/YYYY-MM-DD/heartbeat-{timestamp}.jsonl
The Markdown log should be human-readable. JSONL should be machine-readable.

7. Notifications
Support at least one notification adapter:

Telegram or Slack

Digest should include:

projects processed

dirty/conflicted worktrees

open PRs needing review

open issues needing spec

provider/budget warnings if available

next recommended action

Non-goals
no autonomous implementation yet

no auto-merge yet

no paid model dispatch yet

no PR review loop yet

no issue spec generation yet

Acceptance Criteria
Running agent-runner heartbeat processes all configured projects.

The runner does not run outside configured active windows.

The runner detects local worktree states correctly.

The runner fetches open GitHub issues and PRs.

The runner writes a Markdown heartbeat log.

The runner writes machine-readable JSONL events.

The runner sends a notification digest.

A second simultaneous heartbeat exits safely because of locking.

No repo changes are made automatically in this MVP.

Future Tickets
Add issue spec generation and confidence scoring.

Add Telegram/Slack question-answer workflow.

Add worktree creation for approved issues.

Add test-first implementation loop.

Add PR review ladder with CodeRabbit, Greptile, Gemini, Codex, and DeepSeek.

Add budget-aware task routing.

Add conservative auto-merge policy.


# Best Overall Architecture Decision

Start with a **boring, auditable daemon**.

Not:

```txt
one giant autonomous agent
But:

cron heartbeat
+ manifests
+ SQLite state
+ GitHub adapter
+ worktree manager
+ provider budget manager
+ notification adapter
+ bounded agent loops
+ strict quality gates
That gives you the real benefit: agents can work while you sleep, but every action is logged, bounded, reversible, and aligned with project-specific policy.
