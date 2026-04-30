# SPEC.md — Hermes Portfolio Manager Plugin MVP 5: Worktree Preparation

## Purpose

MVP 5 adds the first controlled local repository mutation layer: safe worktree preparation for issue implementation.

The system should be able to clone a missing base repository into the configured local project path, safely refresh the base branch, create one predictable issue-specific Git worktree, inspect related worktrees, and record the resulting state in SQLite and local artifacts.

This MVP prepares the ground for implementation agents, but it must not run any coding harness, modify source files intentionally, commit, push, open PRs, or merge anything.

## Preflight Gate

Do not implement MVP 5 until MVP 4 is merged or otherwise confirmed as the active baseline.

Before implementation begins, the dev agent must run:

```bash
pytest
```

MVP 5 work may begin only if MVP 1–4 tests are green, or if any failures are clearly unrelated environmental failures and the user explicitly accepts that baseline.

If MVP 4 is still in an open PR branch, the dev agent must use that branch as the baseline only after confirming it contains the implemented MVP 4 work and its tests pass.

## Roadmap Position

Previous capability layers:

```txt
MVP 1: read-only portfolio visibility
MVP 2: project config mutation only
MVP 3: GitHub issue creation only
MVP 4: maintenance checks and maintenance reports
```

MVP 5 adds:

```txt
local base repo preparation
safe base branch refresh
issue worktree planning
issue worktree creation
worktree state persistence
worktree preparation artifacts
```

Next capability layer:

```txt
MVP 6: implementation / coding harness orchestration
```

MVP 5 exists now because implementation harnesses need isolated, predictable issue worktrees. Without this layer, MVP 6 would need to invent branch names, clone behavior, safety checks, and recovery rules inside the coding-harness layer. That would be unsafe.

## Runtime Root

Default runtime root remains:

```txt
$HOME/.agent-system
```

Root resolution order remains:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

All worktree paths must stay inside the resolved runtime root and under:

```txt
$ROOT/worktrees
```

## Existing Layout and Conventions to Preserve

Current project config behavior already defines local paths:

```txt
base_path default:
$ROOT/worktrees/<project_id>

issue_worktree_pattern default:
$ROOT/worktrees/<project_id>-issue-{issue_number}
```

Current worktree discovery already expects issue worktrees named:

```txt
<project_id>-issue-<issue_number>
```

MVP 5 must preserve these conventions.

## What This MVP Adds

1. Safe base repository preparation.
2. Safe base branch refresh for clean base repos only.
3. Issue worktree planning before creation.
4. Issue worktree creation for a specific issue number.
5. Strict idempotency for already-created matching issue worktrees.
6. Worktree state persistence to SQLite.
7. Worktree preparation artifact files.
8. Dev CLI commands for every tool.
9. One Hermes skill for worktree preparation.
10. Security tests for path containment, branch naming, command allowlists, symlink escapes, secret redaction, and dirty-state blocking.

## Handoff Contract for MVP 6

MVP 5 must leave enough structured state for the implementation harness layer to start without inventing Git policy.

For every prepared issue worktree, MVP 5 should persist or make derivable:

```txt
project_id
issue_number
base_path
issue_worktree_path
branch_name
base_branch
remote_url
head_sha
base_sha or origin/<base_branch> sha
clean/dirty/conflict state
preparation artifact path
```

MVP 6 may rely on this contract. MVP 6 must not create its own branch naming rules, path rules, clone behavior, or dirty-state cleanup behavior. If MVP 5 cannot provide a clean prepared worktree, MVP 6 must return blocked.

## Explicit Non-Goals

MVP 5 must not:

```txt
run coding harnesses
modify repository files intentionally
commit files
push branches
open pull requests
merge pull requests
create GitHub issues
edit GitHub issues
create labels
run dependency install commands
run tests inside project repos
clean dirty worktrees
reset branches
force-update branches
delete worktrees
prune Git branches
resolve merge/rebase conflicts
stash user work
attach arbitrary pre-existing branches to new worktrees
repair branch divergence
call provider/model APIs
schedule implementation jobs
```

MVP 5 prepares the filesystem only.

## Scope Boundary

### May Mutate

```txt
$ROOT/worktrees/<project_id>
$ROOT/worktrees/<project_id>-issue-<issue_number>
$ROOT/state/state.sqlite
$ROOT/artifacts/worktrees/<project_id>/<issue_number-or-base>/
$ROOT/logs/ if existing logging infrastructure writes there
```

### Must Not Mutate

```txt
GitHub remote state
repository source files by design
branches on the remote
pull requests
issues
labels
repo-local project policy files
provider budgets
review-ladder config
maintenance skill config unless read-only inspection requires it
```

Git will naturally create `.git` metadata and branch refs inside local clones/worktrees. That is allowed. Intentional source-file changes are not allowed.

## User Stories

```txt
Prepare a worktree for issue 42 in CoMapeo Cloud App.
```

Expected behavior:

```txt
resolve the project
validate issue number shape
warn if issue 42 is not known in local SQLite issue state
clone base repo if missing
refresh the base branch only if clean and safe
create $ROOT/worktrees/<project_id>-issue-42
create branch agent/<project_id>/issue-42
record worktree state
return a concise summary
```

```txt
Show me the plan before creating a worktree for issue 42.
```

Expected behavior:

```txt
perform validation
show target paths, branch name, base branch, and commands that would run
do not mutate filesystem, Git state, SQLite, or artifacts
```

```txt
List prepared worktrees for this project.
```

Expected behavior:

```txt
inspect base and issue worktrees
show clean/dirty/conflicted/missing states
update SQLite inspection state
```

```txt
Prepare the worktree again for issue 42.
```

Expected behavior:

```txt
if the existing worktree exactly matches the expected project, issue, branch, path, remote, and base, return skipped/success
if mismatched or unsafe, return blocked
```

## Issue Validation Policy

MVP 5 is not responsible for GitHub issue syncing.

Issue validation rules:

1. `issue_number` must be a positive integer.
2. If the issue exists in the local SQLite `issues` table for the project, include its title/state in the plan and artifacts.
3. If the issue is missing from SQLite, do not call GitHub by default. Return a warning in `data.warnings`, but allow planning and worktree creation to proceed when the user explicitly confirms.
4. If the user wants stronger issue validation, they should run the existing GitHub sync / status tools before preparing the worktree.

MVP 5 must not add `gh issue view`, `gh issue create`, or any GitHub-mutating issue command.

## New Tools

```txt
portfolio_worktree_plan
portfolio_worktree_prepare_base
portfolio_worktree_create_issue
portfolio_worktree_list
portfolio_worktree_inspect
portfolio_worktree_explain
```

If `portfolio_worktree_inspect` already exists, MVP 5 must extend it instead of creating a duplicate handler. Preserve backward compatibility with MVP 1 behavior.

## Shared Tool Result Format

Every tool returns:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "tool_name",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None,
}
```

`blocked` is preferred over guessing when project, issue, branch, path, remote, or dirty state is ambiguous.

## Tool Specifications

### 1. `portfolio_worktree_plan`

Purpose:

```txt
Validate and preview the worktree preparation steps for a project issue without mutating anything.
```

Input schema:

```python
{
    "project_ref": str,
    "issue_number": int,
    "base_branch": str | None = None,
    "branch_name": str | None = None,
    "refresh_base": bool = True,
    "root": str | None = None,
}
```

Behavior:

1. Resolve root.
2. Load config.
3. Resolve project using existing project resolver rules.
4. Validate issue number is positive.
5. Check local SQLite issue state and include warning if missing.
6. Compute base path from project config.
7. Compute issue worktree path from `project.local.issue_worktree_pattern`.
8. Determine base branch:
   - explicit `base_branch`, if provided;
   - otherwise project `default_branch`, if not `auto`;
   - otherwise remote default branch from existing local base repo metadata, if available;
   - otherwise blocked.
9. Determine branch name:
   - explicit `branch_name`, only if it matches the strict allowlist;
   - otherwise `agent/<project_id>/issue-<issue_number>`.
10. Validate path containment under `$ROOT/worktrees`.
11. Validate branch name allowlist.
12. Inspect existing base repo and issue worktree if present.
13. Detect whether target branch already exists.
14. Return command plan and blocked/skipped status.

Success example:

```python
{
  "status": "success",
  "data": {
    "project_id": "comapeo-cloud-app",
    "issue_number": 42,
    "base_path": "/home/user/.agent-system/worktrees/comapeo-cloud-app",
    "issue_worktree_path": "/home/user/.agent-system/worktrees/comapeo-cloud-app-issue-42",
    "base_branch": "main",
    "branch_name": "agent/comapeo-cloud-app/issue-42",
    "would_clone_base": false,
    "would_refresh_base": true,
    "would_create_worktree": true,
    "warnings": [],
    "commands": [
      ["git", "fetch", "origin", "main", "--prune"],
      ["git", "merge", "--ff-only", "origin/main"],
      ["git", "worktree", "add", "...", "-b", "agent/comapeo-cloud-app/issue-42", "origin/main"]
    ]
  }
}
```

Blocked cases:

```txt
unknown project
ambiguous project
invalid issue number
issue worktree path escapes root
base path escapes root
invalid branch name
base branch cannot be resolved
base path exists but is not a Git repo
base repo has merge/rebase conflict
base repo has uncommitted tracked changes
base repo is on a non-base branch and cannot safely switch
existing issue worktree is dirty/conflicted and does not match expected state
existing path belongs to another repo/project
existing target branch exists but no exact matching clean issue worktree exists
```

Side effects:

```txt
none
```

Dry-run / plan must not write SQLite or artifacts.

### 2. `portfolio_worktree_prepare_base`

Purpose:

```txt
Clone the project base repo if missing, then safely refresh the configured base branch if possible.
```

Input schema:

```python
{
    "project_ref": str,
    "base_branch": str | None = None,
    "refresh_base": bool = True,
    "dry_run": bool = True,
    "confirm": bool = False,
    "root": str | None = None,
}
```

Behavior:

1. Reuse `portfolio_worktree_plan` base-path and base-branch logic.
2. If `dry_run=true`, return plan only.
3. If base repo is missing and `confirm=false`, return blocked.
4. If confirmed, clone the repo into `project.local.base_path`.
5. Verify clone remote URL matches configured repo using `normalize_remote_url()`.
6. Resolve base branch.
7. If `refresh_base=true`, refresh only when base repo is clean and either:
   - already on the base branch; or
   - can safely switch to an existing local base branch.
8. If the local base branch does not exist, block. Do not create a local base branch in MVP 5 except as part of a fresh clone.
9. Fetch origin base branch.
10. Fast-forward only with `git merge --ff-only origin/<base_branch>`.
11. If local base branch has commits not in `origin/<base_branch>`, block.
12. Update SQLite `worktrees` row for the base repo.
13. Write artifact files.

Success example:

```txt
Base repo ready for comapeo-cloud-app on main. Cloned: no. Refreshed: yes.
```

Blocked cases:

```txt
confirm=false for clone mutation
path already exists and is not empty non-Git directory
path exists but is not Git repo
remote URL mismatch
base repo dirty
base repo conflicted
base branch missing or ambiguous
base repo is on an unexpected branch and cannot safely switch
local base branch has local commits not in origin/base
fetch failed
git version unavailable
```

Side effects when `dry_run=false` and confirmed:

```txt
may create base repo directory
may run git clone
may run git fetch
may run git switch <base_branch>
may fast-forward local base branch only
updates SQLite
writes artifacts
```

### 3. `portfolio_worktree_create_issue`

Purpose:

```txt
Create or verify one issue-specific local Git worktree for a project issue.
```

Input schema:

```python
{
    "project_ref": str,
    "issue_number": int,
    "base_branch": str | None = None,
    "branch_name": str | None = None,
    "refresh_base": bool = True,
    "dry_run": bool = True,
    "confirm": bool = False,
    "root": str | None = None,
}
```

Behavior:

1. Resolve project and issue number.
2. Reuse the plan logic.
3. If `dry_run=true`, return the plan only.
4. If `confirm=false`, return blocked because worktree creation is a local mutation.
5. Acquire worktree locks.
6. Prepare base repo using the same safety rules.
7. Check whether the issue worktree already exists.
8. If it exists and exactly matches the expected repo, path, branch, issue number, and base, inspect and return success/skipped.
9. If it exists but is dirty, conflicted, not Git, wrong repo, wrong branch, wrong issue, or otherwise ambiguous, return blocked.
10. If target branch already exists and no exact matching clean issue worktree exists, return blocked.
11. If the issue worktree does not exist and target branch does not exist, create a new branch and worktree from the resolved base ref.
12. Inspect the new worktree.
13. Persist SQLite state.
14. Write artifacts.

Default branch name:

```txt
agent/<project_id>/issue-<issue_number>
```

Default issue worktree path:

```txt
$ROOT/worktrees/<project_id>-issue-<issue_number>
```

Existing branch behavior:

```txt
If the target branch already exists but there is no exact matching clean issue worktree at the expected path, return blocked.
```

MVP 5 must not attach arbitrary pre-existing branches to new worktrees. That can be a later repair feature.

Blocked cases:

```txt
confirm=false
base preparation blocked
issue worktree path exists and is unsafe
branch name invalid
target branch already exists without exact matching clean issue worktree
base ref unavailable
worktree add fails
post-create inspection is not clean
```

Side effects when `dry_run=false` and confirmed:

```txt
may clone/fetch/fast-forward base repo
may create local branch
may create issue worktree
updates SQLite
writes artifacts
```

### 4. `portfolio_worktree_list`

Purpose:

```txt
List known and discovered base/issue worktrees for one project or all projects.
```

Input schema:

```python
{
    "project_ref": str | None = None,
    "include_archived": bool = False,
    "include_paused": bool = False,
    "inspect": bool = True,
    "root": str | None = None,
}
```

Behavior:

1. Load config.
2. Select projects.
3. Discover base and issue worktrees.
4. Optionally inspect each worktree.
5. Upsert inspection results into SQLite when `inspect=true`.
6. Return concise table-ready data.

Side effects:

```txt
SQLite state update only when inspect=true
```

### 5. `portfolio_worktree_inspect`

Purpose:

```txt
Inspect a specific base or issue worktree and update state.
```

Input schema:

```python
{
    "project_ref": str,
    "issue_number": int | None = None,
    "path": str | None = None,
    "root": str | None = None,
}
```

Behavior:

- If this tool already exists, extend it without breaking existing MVP 1 behavior.
- If `issue_number` is provided, inspect the expected issue worktree.
- If `path` is provided, ensure it is contained in the project/root worktree area before inspection.
- If neither is provided, inspect the base worktree.
- Reuse existing `inspect_worktree` logic where possible.
- Persist state to SQLite.

Blocked cases:

```txt
path escapes root
path does not match project layout
project is archived unless explicitly allowed by future config
```

### 6. `portfolio_worktree_explain`

Purpose:

```txt
Explain why a worktree is ready, missing, dirty, conflicted, or blocked.
```

Input schema:

```python
{
    "project_ref": str,
    "issue_number": int | None = None,
    "root": str | None = None,
}
```

Behavior:

- Inspect relevant worktree.
- Return human-friendly explanation.
- Include next safe action, if any.
- Do not mutate beyond optional SQLite inspection state.

## State / Schema Changes

The existing `worktrees` table is already present:

```sql
CREATE TABLE IF NOT EXISTS worktrees (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  issue_number INTEGER,
  path TEXT NOT NULL,
  branch_name TEXT,
  base_branch TEXT,
  state TEXT NOT NULL,
  dirty_summary TEXT,
  last_inspected_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

MVP 5 should extend the schema only if needed. If migrations are added, they must be idempotent and backward-compatible.

Recommended additive columns, only if implementation needs them:

```sql
ALTER TABLE worktrees ADD COLUMN remote_url TEXT;
ALTER TABLE worktrees ADD COLUMN head_sha TEXT;
ALTER TABLE worktrees ADD COLUMN base_sha TEXT;
ALTER TABLE worktrees ADD COLUMN upstream TEXT;
ALTER TABLE worktrees ADD COLUMN prepared_by TEXT;
ALTER TABLE worktrees ADD COLUMN preparation_artifact_path TEXT;
```

If these columns are not needed for MVP 5 functionality, do not add them.

Worktree IDs:

```txt
base:<project_id>
issue:<project_id>:<issue_number>
```

Allowed worktree states:

```txt
missing
planned
cloning
ready
clean
dirty_untracked
dirty_uncommitted
merge_conflict
rebase_conflict
blocked
failed
```

`ready` may be used for prepared, clean issue worktrees. Existing inspection states such as `clean`, `dirty_untracked`, and `dirty_uncommitted` should continue to work.

## Remote URL Normalization

Implement and test:

```python
normalize_remote_url(url: str) -> str
```

It must normalize common equivalent forms:

```txt
https://github.com/owner/repo.git
https://github.com/owner/repo
git@github.com:owner/repo.git
git@github.com:owner/repo
ssh://git@github.com/owner/repo.git
```

Canonical GitHub form:

```txt
github:owner/repo
```

Local test remotes must also be supported:

```txt
file:///tmp/test-remote.git
/tmp/test-remote.git
```

For local file remotes, canonicalize to resolved local path where possible.

Remote matching must reject different owners, repos, hosts, or local paths.

Remote URLs written to artifacts must be redacted if they contain credentials or tokens.

## Artifact Layout

Artifacts live under:

```txt
$ROOT/artifacts/worktrees/<project_id>/base/
$ROOT/artifacts/worktrees/<project_id>/issue-<issue_number>/
```

Files for real mutation runs:

```txt
plan.json
commands.json
preflight.json
result.json
inspection.json
error.json
summary.md
```

Dry-run / plan calls must not write artifacts in MVP 5.

### Public-safe Artifact

```txt
summary.md
```

### Local-only Artifacts

```txt
plan.json
commands.json
preflight.json
result.json
inspection.json
error.json
```

Artifacts must redact secrets from:

```txt
remote URLs
command stderr
command stdout
environment-derived paths if sensitive
error messages containing tokens
```

Do not store hidden chain-of-thought.

## Allowed Commands

All external commands must use argument arrays. `shell=True` is forbidden.

### General

```txt
git --version
gh --version
gh auth status
```

### Read-only Git

```txt
git rev-parse --is-inside-work-tree
git rev-parse --show-toplevel
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git rev-parse origin/<branch>
git rev-parse --verify <branch>
git rev-parse --verify origin/<branch>
git merge-base --is-ancestor <commit_a> <commit_b>
git branch --show-current
git status --porcelain=v1
git remote get-url origin
git remote show origin
git worktree list --porcelain
git for-each-ref refs/heads/<branch> --format=<format>
```

### Safe Local Mutations

```txt
git clone <repo_url> <base_path>
git fetch origin <base_branch> --prune
git switch <base_branch>
git merge --ff-only origin/<base_branch>
git worktree add <issue_path> -b <branch_name> origin/<base_branch>
```

`git switch` is allowed only in the base repo and only when the base repo is clean and the target branch is the resolved base branch.

`git merge --ff-only` is allowed only in the base repo and only for fast-forwarding the resolved base branch.

`git worktree add` is allowed only when the target branch does not already exist.

## Disallowed Commands

```txt
git push
git commit
git add
git restore
git checkout -- <path>
git reset
git reset --hard
git clean
git stash
git merge without --ff-only
git rebase
git cherry-pick
git worktree remove
git worktree prune
git branch -D
git branch -f
git tag
gh issue view
gh issue create
gh issue edit
gh pr create
gh pr merge
gh pr comment
gh api --method POST
gh api --method PATCH
gh api --method DELETE
npm install
pnpm install
yarn install
pip install
cargo build
make
pytest inside managed repos
any coding harness command
```

MVP 5 is not allowed to modify remote GitHub state.

## Branch Naming Rules

Default branch name:

```txt
agent/<project_id>/issue-<issue_number>
```

Allowed branch regex:

```regex
^agent/[a-z0-9][a-z0-9_-]{1,63}/issue-[1-9][0-9]{0,9}$
```

Explicit branch names may be accepted only if they match the same safe shape.

Branch names must reject:

```txt
leading dash
.. sequence
@{ sequence
trailing slash
trailing dot
backslash
space
colon
shell metacharacters
absolute paths
path traversal
refs/heads/ prefix supplied by user
```

## Path Safety Rules

All resolved paths must satisfy:

```txt
path.resolve().is_relative_to(root.resolve())
path.resolve().is_relative_to((root / "worktrees").resolve())
```

The issue worktree path must be derived from the configured `issue_worktree_pattern`, after substituting only a validated integer issue number.

The tool must not accept arbitrary filesystem paths for creation. Arbitrary `path` is allowed only for inspection, and only after containment checks.

Symlink escapes must be blocked. If any path component under `$ROOT/worktrees` is a symlink that resolves outside `$ROOT/worktrees`, return blocked.

If a target path exists:

```txt
empty directory: block in MVP 5 unless it is the exact expected clean Git worktree
non-empty non-Git directory: blocked
Git repo with wrong remote: blocked
Git repo with wrong branch: blocked
Git repo dirty/conflicted: blocked
matching clean issue worktree: skipped/success
```

## Base Branch Refresh Rules

Base refresh is intentionally conservative.

Rules:

1. The base repo must be clean.
2. The base repo must not be in merge or rebase state.
3. The base repo remote must match the configured project repo.
4. The base branch must be explicit or resolved from config/local metadata.
5. If base repo is on another branch, switch only if:
   - the repo is clean;
   - the target local base branch already exists;
   - the target branch is the resolved base branch.
6. If local base branch does not exist, block in MVP 5. Do not create it except during fresh clone.
7. Run `git fetch origin <base_branch> --prune`.
8. Before fast-forwarding, verify the local base branch has no commits that are not in `origin/<base_branch>` using read-only ancestry checks.
9. Run only `git merge --ff-only origin/<base_branch>`.
10. If fast-forward fails, block or fail with an artifact. Do not rebase, reset, or manually merge.

## Locking and Concurrency

Use SQLite advisory locks.

Lock names:

```txt
worktree:project:<project_id>
worktree:issue:<project_id>:<issue_number>
```

Rules:

1. Base preparation requires `worktree:project:<project_id>`.
2. Issue worktree creation requires both locks.
3. Acquire locks in stable order:
   - project lock first;
   - issue lock second.
4. Use TTL, default 15 minutes.
5. Always release locks in `finally` blocks.
6. If lock acquisition fails, return `blocked`, not `failed`.
7. Expired locks may be stolen only through the existing lock CAS behavior.

## Idempotency and Duplicate Prevention

Idempotency key:

```txt
project_id + issue_number + issue_worktree_path + branch_name + base_branch
```

Repeated calls must not create duplicate worktrees.

Before creating a worktree:

1. Check SQLite for an existing `issue:<project_id>:<issue_number>` worktree.
2. Check filesystem for target path.
3. Check `git worktree list --porcelain` from the base repo.
4. Check whether the branch already exists.
5. Verify remote URL matches project config.

Outcomes:

```txt
same worktree already exists and clean -> skipped/success
same worktree exists but dirty -> blocked; report dirty state; do not mutate
same path exists but mismatched -> blocked
branch exists without exact matching clean issue worktree -> blocked
```

MVP 5 should not attempt branch repair, branch reuse, or branch attachment beyond exact idempotency.

## Failure and Recovery

### Clone Failure

If clone fails:

```txt
write error.json
remove only empty directories created by this operation
leave non-empty directories untouched
return failed with safe stderr summary
```

### Fetch Failure

If fetch fails:

```txt
write error.json
keep existing base repo unchanged
return failed
```

### Fast-forward Failure

If `git merge --ff-only` fails:

```txt
do not merge manually
do not rebase
return blocked or failed depending on reason
write error.json
```

### Worktree Add Failure

If `git worktree add` fails:

```txt
write error.json
inspect target path
if target path was created but is not valid/clean, mark state failed or blocked
never delete non-empty target path automatically
```

### Crash Recovery

Implement an internal helper:

```python
worktree_reconcile(project_id: str, issue_number: int | None, root: Path) -> dict
```

It should compare:

```txt
SQLite worktree rows
filesystem paths
git worktree list --porcelain
current branch
remote URL
clean/dirty/conflict state
```

On next call after a crash:

```txt
inspect base path
inspect issue worktree path
inspect git worktree list
reconcile SQLite to filesystem truth
return skipped/success if already prepared cleanly
return blocked if partial state is unsafe
```

## Dry-Run Behavior

Dry-run is required for:

```txt
portfolio_worktree_plan
portfolio_worktree_prepare_base
portfolio_worktree_create_issue
```

Dry-run must:

```txt
validate all inputs
resolve project
resolve branch/path plan where possible
inspect existing paths with read-only Git commands
show intended commands
show expected side effects
not run clone/fetch/switch/merge/worktree add
not write artifacts
not update SQLite
```

Default for mutation-capable tools:

```txt
dry_run=true
confirm=false
```

Real mutation requires:

```txt
dry_run=false
confirm=true
```

## Security and Privacy Rules

1. `shell=True` is forbidden.
2. Only allowlisted Git/GH commands may run.
3. All paths must stay under `$ROOT/worktrees`.
4. Branch names must pass strict validation.
5. Remote URLs must be normalized before comparison.
6. Remote URLs must be redacted before artifact writes.
7. Stderr/stdout must be redacted before artifact writes.
8. No secrets from environment variables may be written to artifacts.
9. No hidden chain-of-thought in artifacts.
10. Do not follow symlinks that escape root.
11. Do not use repo-local config to override Portfolio Manager policy.
12. Do not intentionally run Git hooks or project scripts.
13. Set non-interactive Git environment for external commands:

```txt
GIT_TERMINAL_PROMPT=0
```

14. Timeout every external command.

Recommended default timeouts:

```txt
git status/rev-parse/branch/remote: 30s
git fetch: 120s
git clone: 300s
git worktree add: 120s
```

## Dev CLI Requirements

Add or update commands:

```bash
python dev_cli.py worktree-plan --project-ref <project> --issue-number 42 --root /tmp/agent-system-test --json
python dev_cli.py worktree-prepare-base --project-ref <project> --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py worktree-prepare-base --project-ref <project> --dry-run false --confirm true --root /tmp/agent-system-test --json
python dev_cli.py worktree-create-issue --project-ref <project> --issue-number 42 --dry-run true --root /tmp/agent-system-test --json
python dev_cli.py worktree-create-issue --project-ref <project> --issue-number 42 --dry-run false --confirm true --root /tmp/agent-system-test --json
python dev_cli.py worktree-list --project-ref <project> --root /tmp/agent-system-test --json
python dev_cli.py worktree-inspect --project-ref <project> --issue-number 42 --root /tmp/agent-system-test --json
python dev_cli.py worktree-explain --project-ref <project> --issue-number 42 --root /tmp/agent-system-test --json
```

CLI command names may follow existing conventions, but they must be documented in README and tests.

## Hermes Skill Requirements

Add skill:

```txt
skills/worktree-prepare/SKILL.md
```

The skill must instruct Hermes to:

1. Plan first for any worktree request.
2. Prefer dry-run previews when the user has not explicitly confirmed mutation.
3. Require explicit confirmation before creating a base clone or issue worktree.
4. Block instead of guessing on project or issue ambiguity.
5. Warn, but do not block, when issue number is not present in local SQLite issue state.
6. Never run implementation agents in MVP 5.
7. Explain dirty/conflicted worktrees clearly.
8. Suggest safe next action only.

Example interactions:

```txt
Prepare a worktree for issue 42 in comapeo-cloud-app.
```

If not yet confirmed:

```txt
I can prepare it. The plan is: clone/refresh base repo, then create branch agent/comapeo-cloud-app/issue-42 at $ROOT/worktrees/comapeo-cloud-app-issue-42. Confirm to run it.
```

```txt
Create it now.
```

Then call the mutation tool with:

```txt
dry_run=false
confirm=true
```

## Required Tests

### Preflight / Regression Tests

```txt
pytest passes before MVP 5 implementation begins
MVP 1 portfolio tests still pass
MVP 2 project admin tests still pass
MVP 3 issue draft/create tests still pass
MVP 4 maintenance tests still pass
```

### Structure Tests

```txt
new modules are importable
new tools are registered
new CLI commands exist
new skill folder exists
no duplicate tool names
existing portfolio_worktree_inspect behavior remains backward-compatible
```

### Plan Tests

```txt
plans expected base path and issue path
uses configured issue_worktree_pattern
resolves explicit base branch
resolves configured default branch
blocks when default branch auto cannot be resolved from local metadata
warns when issue number missing from local SQLite
blocks invalid issue number
blocks invalid branch names
blocks path traversal through pattern or path input
plan/dry-run writes no SQLite and no artifacts
```

### Remote URL Normalization Tests

```txt
normalizes HTTPS GitHub URL with .git suffix
normalizes HTTPS GitHub URL without .git suffix
normalizes SSH git@github.com URL
normalizes ssh://git@github.com URL
normalizes trailing slash
normalizes local file remotes for temp test repos
rejects different owner/repo/host/path
redacts credentials/tokens in artifact output
```

### Command Allowlist Tests

```txt
all command calls use argument arrays
shell=True is never used
only allowed git/gh commands are executed
forbidden commands are rejected in helper layer
gh issue view is not used
git worktree add with existing branch is not used
```

### Base Preparation Tests

```txt
dry-run does not clone, fetch, switch, merge, update SQLite, or write artifacts
confirm=false blocks mutation
missing base repo clones with confirm=true
existing clean base repo fetches and fast-forwards
existing dirty base repo blocks
existing conflicted base repo blocks
remote URL mismatch blocks
non-Git target directory blocks
missing local base branch blocks except after fresh clone
local-only commits on base branch block fast-forward
fetch failure writes error artifact
clone failure writes error artifact
```

### Issue Worktree Creation Tests

```txt
dry-run does not create worktree, update SQLite, or write artifacts
confirm=false blocks mutation
creates expected branch name
creates expected issue worktree path
records SQLite worktree row
writes artifacts
repeated call is idempotent only for exact matching clean worktree
existing matching clean worktree returns skipped/success
existing dirty worktree blocks and reports dirty
existing wrong-remote path blocks
existing target branch without exact matching worktree blocks
worktree add failure writes error artifact
```

### Inspection Tests

```txt
missing path -> missing
non-Git path -> blocked
clean repo -> clean
tracked changes -> dirty_uncommitted
untracked only -> dirty_untracked
merge conflict -> merge_conflict
rebase conflict -> rebase_conflict
inspection persists SQLite rows
list discovers base and issue worktrees
```

### Locking Tests

```txt
project lock acquired for base prepare
project + issue locks acquired for issue creation
lock contention returns blocked
locks released on success
locks released on failure
expired locks can be acquired through existing lock behavior
```

### Artifact Tests

```txt
plan.json written for real runs
result.json written on success
error.json written on failure
summary.md is public-safe
secrets redacted from stderr/stdout/remote URLs
path traversal blocked for artifacts
dry-run writes no artifacts
```

### Security Tests

```txt
reject branch with ..
reject branch with @{
reject branch with leading dash
reject branch with shell metacharacters
reject symlink escape from worktrees root
reject issue_worktree_pattern escaping root
redact token in https remote URL
redact API key-like strings in command output
```

### E2E Tests

Use local temporary Git repositories, not production GitHub repos.

```txt
create bare remote repo
create projects.yaml pointing to local file remote
prepare base repo
create issue worktree
rerun create issue worktree and verify idempotency
make issue worktree dirty and verify mutation blocks
make base repo dirty and verify refresh blocks
create existing target branch without matching worktree and verify blocked
```

Final gate:

```bash
pytest
```

## Manual Hermes Smoke Tests

Run only after automated tests pass.

```txt
Plan a worktree for issue 42 in the test project. Do not create it.
```

Expected:

```txt
returns dry-run plan with path, branch, base branch, commands, and no mutation
```

```txt
Prepare the base repo for the test project. Dry run only.
```

Expected:

```txt
shows clone/fetch plan, no mutation
```

```txt
Create the issue 42 worktree for the test project. Confirmed.
```

Expected:

```txt
creates local worktree, records state, returns concise summary
```

```txt
List prepared worktrees for the test project.
```

Expected:

```txt
shows base and issue worktree states
```

```txt
Explain the worktree for issue 42.
```

Expected:

```txt
explains clean/ready or dirty/conflicted state and next safe action
```

## Acceptance Criteria

1. MVP 4 is confirmed as the active baseline before implementation begins.
2. All MVP 1–4 tests pass before MVP 5 implementation begins.
3. `portfolio_worktree_plan` previews base and issue worktree preparation without mutation, SQLite writes, or artifact writes.
4. `portfolio_worktree_prepare_base` can clone and safely refresh a base repo only with `dry_run=false` and `confirm=true`.
5. `portfolio_worktree_create_issue` can create exactly one issue worktree with a safe branch name only with `dry_run=false` and `confirm=true`.
6. Repeated create calls are idempotent only for exact matching clean issue worktrees.
7. Existing target branches without exact matching clean issue worktrees are blocked.
8. Dirty or conflicted base repos block refresh and worktree creation.
9. Dirty or conflicted issue worktrees are reported but never cleaned, reset, stashed, deleted, or modified.
10. All paths are contained under `$ROOT/worktrees` and symlink escapes are blocked.
11. Remote URL matching is normalized and tested.
12. All command calls use argument arrays and the allowlist.
13. SQLite `worktrees` state reflects prepared and inspected worktrees.
14. Artifacts are written for real runs and redact secrets.
15. Dry-runs write no artifacts and no SQLite state.
16. Dev CLI commands exist and are tested.
17. Hermes skill exists and requires plan-first behavior.
18. MVP 1–4 tests continue passing.
19. No GitHub remote mutation occurs.
20. No coding harness runs.

## Definition of Done

MVP 5 is done when Hermes can safely prepare local worktrees for future issue implementation while preserving the staged safety model.

At completion, the system can:

```txt
plan a worktree
clone a missing base repo
fast-forward a clean base branch
create one issue worktree
inspect worktree state
persist state
write audit artifacts for real runs
explain readiness or blockers
```

It still cannot:

```txt
write code
run coding agents
commit
push
open PRs
review PRs
merge
clean/reset/stash/delete user work
repair divergent branches automatically
attach arbitrary existing branches
```

## Design Critique and Scope Check

This MVP is intentionally narrow. The main temptation is to include implementation-agent setup, dependency installation, test execution, branch pushing, PR creation, or branch-repair behavior. Those belong in MVP 6 or later.

The highest-risk area is local Git mutation. The spec limits this through:

```txt
dry-run by default
explicit confirmation for mutation
strict command allowlist
path containment
branch-name validation
remote URL normalization
dirty-state blocking
locks
strict idempotency only
artifact trail
no destructive cleanup
```

The second risk is branch divergence. MVP 5 blocks on divergence rather than trying to recover automatically.

The third risk is accidental path escape through configurable `issue_worktree_pattern`. MVP 5 treats path containment as a security boundary and tests it directly.

The fourth risk is accidental scope creep into implementation automation. MVP 5 explicitly forbids coding harnesses, dependency installs, tests inside managed repos, commits, pushes, PRs, and GitHub mutations.

With these constraints, MVP 5 is ready to become a PROGRESS.md implementation plan.
