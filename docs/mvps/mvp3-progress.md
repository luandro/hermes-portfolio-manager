# PROGRESS.md — Hermes Portfolio Manager Plugin MVP 3: Issue Creation and Brainstorming, Final Agent-Ready Version

## Goal

Track implementation progress for **Hermes Portfolio Manager Plugin MVP 3**.

MVP 3 lets the user create GitHub issues through Hermes/Telegram from clear requests or rough ideas.

The system should support:

```txt
Create a clean GitHub issue from a clear request.
Create a local draft from a rough idea.
Ask follow-up questions for missing details.
Update a draft with user answers.
Confirm before creating a GitHub issue from a draft.
Run dry-runs before creating issues.
Detect possible duplicate drafts and GitHub issues.
List open drafts.
Discard drafts.
Block issue creation when the project is ambiguous.
Recover safely from partial GitHub issue creation failures.
```

MVP 3 must remain **issue-management only**.

It must not start development work.

---

# Agent-Readiness Verdict

This final version is ready to hand to coding agents **if MVP 1 and MVP 2 are complete and passing**.

It addresses the main risks of the first GitHub-mutating MVP:

* duplicate GitHub issue creation,
* duplicate local drafts,
* ambiguous project selection,
* direct issue creation without artifacts,
* retries after partial failure,
* crashes after GitHub issue creation but before local state update,
* vague issues becoming bad specs,
* public GitHub issue bodies leaking private metadata,
* unsafe shell or GitHub command usage,
* artifact path traversal,
* inconsistent readiness scoring,
* fuzzy project matching ambiguity.

If MVP 1 or MVP 2 is not complete, stop and finish them first.

---

# Runtime Root

The default system root is:

```txt
$HOME/.agent-system
```

Implementation must use:

```python
Path.home() / ".agent-system"
```

Root resolution priority:

```txt
1. explicit root argument
2. AGENT_SYSTEM_ROOT environment variable
3. Path.home() / ".agent-system"
```

Expected runtime layout after MVP 3:

```txt
$HOME/.agent-system/
  config/
    projects.yaml
  state/
    state.sqlite
  worktrees/
  logs/
  artifacts/
    issues/
      <project_id>/
        <draft_id>/
          original-input.md
          brainstorm.md
          questions.md
          spec.md
          github-issue.md
          metadata.json
          creation-attempt.json
          github-created.json
          creation-error.json
  backups/
```

No repo-local project automation YAML is required.

---

# Non-Negotiable Rules

1. Write a meaningful test before implementation.
2. Confirm the test fails for the expected reason.
3. Implement the smallest change needed to pass.
4. Preserve all MVP 1 and MVP 2 behavior.
5. Do not create issues if the project is ambiguous.
6. Do not create GitHub issues without a local draft artifact.
7. Do not create GitHub issues without explicit confirmation, except dry-run which creates no GitHub issue.
8. Do not start development work.
9. Do not create branches or worktrees.
10. Do not modify repository files.
11. Do not create GitHub labels.
12. Do not mutate PRs.
13. Do not run Git commands in MVP 3.
14. Do not use `shell=True`.
15. Use `gh issue create` only through subprocess argument arrays.
16. Use `--body-file` for GitHub issue creation.
17. Delete temporary GitHub issue body files after use.
18. Keep public GitHub issue body separate from private local artifacts.
19. Do not expose private Telegram metadata, confidence notes, internal reasoning, hidden chain-of-thought, or provider/budget info in GitHub issues.
20. Do not store hidden chain-of-thought in local artifacts.
21. Tool handlers do not run multi-turn conversations; Hermes skills do that.
22. Tools must return structured questions and blocked states instead of guessing.
23. All artifact writes for important files must be atomic.
24. Every GitHub issue created by this system must have a draft ID and artifact folder.
25. Creation from draft must be idempotent.
26. Direct issue creation must internally create a local draft first.
27. Duplicate GitHub issue checks must run before calling `gh issue create`.

---

# MVP 3 Scope Boundary

MVP 3 may mutate:

```txt
GitHub issues through gh issue create only
SQLite issue and draft records
local issue artifacts under $HOME/.agent-system/artifacts/issues/
```

MVP 3 must not mutate:

```txt
GitHub PRs
GitHub labels
GitHub milestones
GitHub projects
GitHub branches
repository files
worktrees
review ladders
provider budgets
maintenance skills
```

Allowed GitHub mutation command:

```txt
gh issue create
```

Allowed GitHub read commands inherited from earlier MVPs or added for duplicate detection:

```txt
gh issue list
gh pr list
gh repo view
gh auth status
gh --version
```

Disallowed GitHub commands include:

```txt
gh issue edit
gh issue comment
gh label create
gh pr create
gh pr merge
gh pr comment
gh api --method POST
gh api --method PATCH
gh api --method DELETE
```

Note: `gh issue edit` may be added in a later MVP, but is not allowed in MVP 3.

---

# Shared Tool Result Format

All tools must return:

```python
{
    "status": "success" | "skipped" | "blocked" | "failed",
    "tool": "portfolio_issue_draft",
    "message": "Human-readable one-line result",
    "data": {},
    "summary": "Concise Telegram-friendly summary",
    "reason": None
}
```

Use statuses as follows:

```txt
success: operation completed
skipped: no change needed, such as draft already created as issue
blocked: known precondition prevented operation
failed: unexpected error
```

Common blocked reasons:

```txt
config_missing
project_not_found
project_ambiguous
draft_not_found
draft_not_ready
draft_state_invalid
confirm_required
missing_required_input
github_cli_missing
github_auth_missing
github_issue_create_failed
invalid_issue_title
invalid_draft_id
artifact_path_escape
possible_duplicate_draft
possible_duplicate_issue
input_too_long
public_body_invalid
issue_create_lock_held
```

---

# Required MVP 3 Tools

```txt
portfolio_project_resolve
portfolio_issue_draft
portfolio_issue_questions
portfolio_issue_update_draft
portfolio_issue_create
portfolio_issue_create_from_draft
portfolio_issue_explain_draft
portfolio_issue_list_drafts
portfolio_issue_discard_draft
```

Optional internal helper, not required as public Hermes tool:

```txt
portfolio_issue_search_drafts
```

---

# Required MVP 3 Dev CLI Commands

The dev CLI must support all MVP 3 tools outside Hermes.

Required examples:

```bash
python dev_cli.py portfolio_project_resolve \
  --project-ref comapeo-cloud-app \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_draft \
  --project-ref comapeo-cloud-app \
  --text "Users should export selected layers as SMP" \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_questions \
  --draft-id draft_123 \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_update_draft \
  --draft-id draft_123 \
  --answers "Target CoMapeo Mobile first" \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_create \
  --project-id comapeo-cloud-app \
  --title "Export selected layers as SMP" \
  --body "## Goal\n\nUsers can export selected layers as SMP.\n\n## Acceptance Criteria\n\n- [ ] Selected layers can be exported." \
  --confirm true \
  --dry-run false \
  --allow-possible-duplicate false \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_create_from_draft \
  --draft-id draft_123 \
  --confirm true \
  --allow-open-questions false \
  --allow-possible-duplicate false \
  --dry-run false \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_explain_draft \
  --draft-id draft_123 \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_list_drafts \
  --project-id comapeo-cloud-app \
  --include-created false \
  --root /tmp/agent-system-test \
  --json

python dev_cli.py portfolio_issue_discard_draft \
  --draft-id draft_123 \
  --confirm true \
  --root /tmp/agent-system-test \
  --json
```

Boolean flags must accept explicit values:

```txt
--confirm true
--confirm false
--dry-run true
--dry-run false
--force-ready true
--force-ready false
--force-rough-issue true
--force-rough-issue false
--allow-open-questions true
--allow-open-questions false
--allow-possible-duplicate true
--allow-possible-duplicate false
--include-created true
--include-created false
```

---

# Final Design Decisions

## Direct issue creation must create a draft first

`portfolio_issue_create` must not call GitHub directly without artifacts.

It must:

1. validate structured title/body,
2. create a local draft/artifact folder,
3. write `github-issue.md`, `metadata.json`, and supporting files,
4. then call the same creation path used by `portfolio_issue_create_from_draft`.

Every GitHub issue created by the system must have:

```txt
draft_id
artifact folder
metadata.json
github-issue.md
creation-attempt.json
github-created.json on success or creation-error.json on failure
```

## Confirmation is required for every real GitHub issue creation

Both `portfolio_issue_create` and `portfolio_issue_create_from_draft` require:

```txt
confirm=true
```

Dry-run does not require confirmation because it does not create a GitHub issue.

## Dry-run behavior

All GitHub-mutating tools must support:

```txt
dry_run=true
```

Dry-run must:

1. create or update local draft artifacts as needed,
2. validate title/body,
3. run duplicate draft checks,
4. run duplicate GitHub issue checks if GitHub CLI is available and authenticated,
5. return the exact title/body that would be created,
6. not call `gh issue create`,
7. not mark draft as `created`.

## Duplicate draft detection

Before creating a new draft, check existing non-terminal drafts for the same project and similar title.

Terminal draft states:

```txt
created
discarded
blocked
```

If a non-terminal draft has the same normalized title, return:

```txt
status = blocked
reason = possible_duplicate_draft
```

Include existing draft ID in `data`.

Similarity rule for MVP 3:

```txt
Normalize title by lowercasing, trimming, collapsing whitespace, and removing punctuation.
Exact normalized title match = duplicate.
```

Do not implement fuzzy semantic duplicate draft detection in MVP 3.

## Duplicate GitHub issue detection

Before calling `gh issue create`, check open GitHub issues in that repo for title collisions.

Use:

```bash
gh issue list --repo OWNER/REPO --state open --search "TITLE in:title" --json number,title,url
```

Behavior:

```txt
If exact normalized title match exists:
  block with reason = possible_duplicate_issue
  return existing issue number and URL.

If similar title match exists:
  block unless allow_possible_duplicate=true.
```

Similarity rule for MVP 3:

```txt
Exact normalized title match = duplicate.
```

Do not implement fuzzy semantic GitHub duplicate detection in MVP 3.

If the user passes:

```txt
allow_possible_duplicate=true
```

then duplicate blocking may be bypassed, but only after confirmation.

## Draft states

Allowed draft states:

```txt
draft
needs_project_confirmation
needs_user_questions
ready_for_creation
creating
creating_failed
created
discarded
blocked
```

State meaning:

```txt
draft: local draft exists but is not yet classified as ready/questions
needs_project_confirmation: project is ambiguous and user must choose
needs_user_questions: more product/spec details are needed
ready_for_creation: draft is ready for GitHub after confirmation
creating: GitHub issue creation is in progress or was interrupted
creating_failed: GitHub issue creation failed and can be retried
created: GitHub issue was created and linked
discarded: user discarded the draft
blocked: draft cannot proceed without manual intervention
```

## Crash recovery files

Each artifact folder may contain:

```txt
creation-attempt.json
github-created.json
creation-error.json
```

Before calling `gh issue create`, write `creation-attempt.json` atomically.

Immediately after `gh issue create` succeeds and a valid issue URL is parsed, write `github-created.json` atomically before any other state update.

If issue creation fails, write `creation-error.json` atomically and set draft state to `creating_failed`.

On retry:

1. If `github-created.json` exists, do not call `gh issue create` again.
2. Complete metadata and SQLite updates from `github-created.json`.
3. If only `creation-attempt.json` exists, run duplicate GitHub issue check before retry.
4. If `creation-error.json` exists, allow retry with `confirm=true` after duplicate check.

## Project-level issue creation lock

Use a project-level lock around actual issue creation:

```txt
github_issue_create:<project_id>
```

Default TTL:

```txt
120 seconds
```

If held, return:

```txt
status = blocked
reason = issue_create_lock_held
```

This lock is in addition to draft-level locks.

## Force flags

`force_rough_issue`:

```txt
Used during draft creation.
Allows draft to become ready_for_creation even if readiness < 0.75.
Cannot bypass ambiguous project resolution.
Open questions must be preserved in the GitHub issue body.
```

`force_ready`:

```txt
Used during draft update.
Marks an existing draft ready even if questions remain.
Cannot bypass ambiguous project resolution.
Open questions must be preserved in the GitHub issue body.
```

## Public/private artifact classification

Public-safe:

```txt
spec.md
github-issue.md
```

Private/local-only:

```txt
original-input.md
brainstorm.md
questions.md
metadata.json
creation-attempt.json
github-created.json
creation-error.json
```

Only `github-issue.md` is sent to GitHub.

`brainstorm.md` must contain concise structured notes only. Do not store hidden chain-of-thought.

Allowed sections in `brainstorm.md`:

```txt
Interpreted Request
Scope Notes
Missing Decisions
Suggested Split
Project Resolution Notes
Public/Private Classification
```

## Input and output length limits

Set explicit limits:

```txt
issue title: 5–120 characters
user input text: max 20,000 characters
answers update: max 20,000 characters
GitHub issue body: max 20,000 characters
summary: max 2,000 characters
```

If input is too long, return:

```txt
status = blocked
reason = input_too_long
```

Do not silently truncate user input for issue creation.

## Markdown safety

Public GitHub issue body must:

```txt
reject <script> tags
reject <style> tags
reject raw HTML event handlers such as onclick=
normalize excessive blank lines
exclude private metadata markers
stay under max body length
```

If invalid, return:

```txt
status = blocked
reason = public_body_invalid
```

## Required GitHub issue body sections

Required:

```txt
Goal
Acceptance Criteria
```

Optional:

```txt
Context
Problem
Steps to Reproduce
Expected Behavior
Actual Behavior
Non-Goals
Notes
Open Questions
```

If acceptance criteria cannot be generated, draft should be `needs_user_questions` unless `force_rough_issue` or `force_ready` is explicitly used.

## Issue kinds

Drafts should classify issue kind as:

```txt
feature
bug
task
research
unknown
```

This is for body template selection and local metadata only.

No labels are applied by default.

## Label behavior

MVP 3 does not apply labels by default.

Only apply labels explicitly provided by the tool input.

Never create labels.

If explicit labels cause `gh issue create` to fail, return controlled error. Do not retry silently without labels.

## Created issue state mapping

When upserting into SQLite `issues` table:

```txt
spec_ready if draft was ready_for_creation, readiness >= 0.75, no open questions, and no force flag was used.
needs_triage if created with open questions.
needs_triage if force_ready or force_rough_issue was used.
needs_triage if issue kind is unknown.
```

---

# Deterministic Readiness Formula

Readiness must be deterministic. Do not invent model-based confidence.

Start at `0.0`.

Add:

```txt
+0.25 project resolved
+0.20 clear goal/title
+0.20 clear expected behavior or problem
+0.15 acceptance criteria can be derived
+0.10 scope is small or medium
+0.10 boundary/non-goal is clear or not needed
```

Subtract:

```txt
-0.25 ambiguous project
-0.20 vague outcome
-0.15 large multi-system feature
-0.15 missing target user/platform when relevant
-0.15 missing reproduction steps for bug reports
```

Clamp to:

```txt
0.0 <= readiness <= 1.0
```

Thresholds:

```txt
0.00 - 0.49: needs_user_questions
0.50 - 0.74: needs_user_questions unless force_rough_issue/force_ready is true
0.75 - 1.00: ready_for_creation if project is resolved
```

Ambiguous project always overrides readiness:

```txt
state = needs_project_confirmation
```

---

# Deterministic Project Fuzzy Matching

Use token scoring. Do not call LLMs in the tool handler.

Project tokens:

```txt
project_id split on hyphen
project name lowercased words
repo name lowercased words
owner/repo exact string
```

Score:

```txt
+5 exact project_id match
+5 exact owner/repo match
+4 exact project name match
+2 repo name token match
+1 project name token match
+1 project_id token match
```

Resolution thresholds:

```txt
resolved if top score >= 3 and second score <= top score - 2
ambiguous if two or more projects have score >= 2 and difference < 2
not_found if top score < 2
```

Archived projects are excluded by default.

---

# Phase 0 — Preflight and Regression Baseline

## 0.1 Confirm MVP 1 and MVP 2 tests pass

Status: [ ]

### Test first

Run the full existing test suite before changing anything.

```bash
pytest
```

### Implementation

No implementation yet.

### Verification

Acceptance:

* all MVP 1 and MVP 2 tests pass before MVP 3 work begins,
* if tests fail, fix earlier MVPs first.

---

## 0.2 Add MVP 3 file/module placeholders

Status: [ ]

### Test first

Create a structure test that expects these files:

```txt
issue_resolver.py
issue_drafts.py
issue_artifacts.py
issue_github.py
skills/issue-brainstorm/SKILL.md
skills/issue-create/SKILL.md
```

### Implementation

Create placeholder files only.

### Verification

Run:

```bash
pytest tests/test_structure.py::test_mvp3_files_exist
```

Acceptance:

* MVP 3 has a clear module boundary.

---

## 0.3 Add source-scan guard for MVP 3 forbidden operations

Status: [ ]

### Test first

Create or extend security tests to reject new uses of:

```txt
git commit
git push
git checkout
git switch
git pull
git rebase
git merge
git reset
git clean
git stash
gh pr create
gh pr merge
gh pr comment
gh label create
gh issue comment
gh issue edit
gh api --method POST
gh api --method PATCH
gh api --method DELETE
```

Allowed new command:

```txt
gh issue create
```

### Implementation

No implementation yet. This guard should fail only if unsafe code is introduced.

### Verification

Run:

```bash
pytest tests/test_security.py::test_mvp3_forbidden_operations_not_used
```

Acceptance:

* MVP 3 cannot accidentally grow beyond issue creation.

---

# Phase 1 — SQLite Draft State

## 1.1 Add `issue_drafts` table initialization

Status: [ ]

### Test first

Create test verifying that state initialization creates:

```txt
issue_drafts
```

with columns:

```txt
draft_id
project_id
state
title
readiness
artifact_path
github_issue_number
github_issue_url
created_at
updated_at
```

and index:

```txt
idx_issue_drafts_project_state
```

### Implementation

Extend `state.py` initialization:

```sql
CREATE TABLE IF NOT EXISTS issue_drafts (
  draft_id TEXT PRIMARY KEY,
  project_id TEXT,
  state TEXT NOT NULL,
  title TEXT,
  readiness REAL,
  artifact_path TEXT NOT NULL,
  github_issue_number INTEGER,
  github_issue_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_issue_drafts_project_state ON issue_drafts(project_id, state);
```

### Verification

Run:

```bash
pytest tests/test_state.py::test_issue_drafts_table_initializes
```

Acceptance:

* table exists after state init,
* repeated init is idempotent,
* MVP 1 and MVP 2 state tests still pass.

---

## 1.2 Validate draft states

Status: [ ]

### Test first

Create tests for allowed draft states:

```txt
draft
needs_project_confirmation
needs_user_questions
ready_for_creation
creating
creating_failed
created
discarded
blocked
```

Invalid states must be rejected.

### Implementation

Add draft state validation helper.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_draft_state_validation
```

Acceptance:

* only allowed states can be stored.

---

## 1.3 Upsert and get issue drafts

Status: [ ]

### Test first

Create tests verifying:

1. draft can be inserted,
2. draft can be updated,
3. readiness must be between 0 and 1,
4. draft can be retrieved by ID,
5. missing draft returns controlled not-found result.

### Implementation

Implement:

```python
upsert_issue_draft(conn, draft_record)
get_issue_draft(conn, draft_id)
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_upsert_and_get_issue_draft
```

Acceptance:

* draft metadata persists correctly.

---

## 1.4 List issue drafts

Status: [ ]

### Test first

Create tests verifying filters:

```txt
project_id
state
include_created=false by default
include_created=true
```

### Implementation

Implement:

```python
list_issue_drafts(conn, project_id=None, state=None, include_created=False)
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_list_issue_drafts
```

Acceptance:

* open drafts can be listed without showing created drafts by default.

---

## 1.5 Draft mutation lock

Status: [ ]

### Test first

Create tests verifying that mutating one draft uses a lock:

```txt
issue_draft:<draft_id>
```

For draft creation, use a short operation lock:

```txt
issue_draft:create
```

Expected:

* second mutation blocks when lock held,
* lock released after success,
* lock released after handled failure.

### Implementation

Use MVP 1 lock helper for draft mutations.

Default TTL:

```txt
120 seconds
```

### Verification

Run:

```bash
pytest tests/test_issue_draft_locks.py
```

Acceptance:

* duplicate concurrent draft updates/creations are prevented.

---

## 1.6 Project-level issue creation lock

Status: [ ]

### Test first

Create tests verifying actual GitHub issue creation uses lock:

```txt
github_issue_create:<project_id>
```

Expected:

* second issue creation blocks when lock held,
* lock released after success,
* lock released after GitHub failure,
* lock not required for dry-run.

### Implementation

Use MVP 1 lock helper.

Default TTL:

```txt
120 seconds
```

### Verification

Run:

```bash
pytest tests/test_issue_draft_locks.py::test_project_issue_creation_lock
```

Acceptance:

* concurrent issue creation in same repo is controlled.

---

# Phase 2 — Artifact Path Safety and Atomic File Writing

## 2.1 Validate draft IDs

Status: [ ]

### Test first

Create tests accepting:

```txt
draft_123
draft_550e8400-e29b-41d4-a716-446655440000
```

Reject:

```txt
../draft_123
draft/123
.draft_123
DRAFT_123
""
```

### Implementation

Implement:

```python
validate_draft_id(draft_id: str) -> None
```

Recommended regex:

```regex
^draft_[a-z0-9][a-z0-9-]*$
```

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_draft_id_validation
```

Acceptance:

* draft IDs cannot cause path traversal.

---

## 2.2 Generate draft IDs

Status: [ ]

### Test first

Create test verifying generated draft IDs:

* start with `draft_`,
* pass validation,
* are unique across repeated calls.

### Implementation

Implement:

```python
generate_draft_id() -> str
```

Use UUID.

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_generate_draft_id
```

Acceptance:

* draft IDs are safe and unique.

---

## 2.3 Resolve artifact root safely

Status: [ ]

### Test first

Create tests verifying:

1. valid project/draft resolves under `{root}/artifacts/issues/<project_id>/<draft_id>`,
2. invalid project ID is rejected,
3. invalid draft ID is rejected,
4. resolved path cannot escape root.

### Implementation

Implement:

```python
issue_artifact_root(root: Path, project_id: str, draft_id: str) -> Path
```

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_issue_artifact_root_safety
```

Acceptance:

* artifacts cannot escape `$HOME/.agent-system/artifacts/issues/`.

---

## 2.4 Atomic artifact write helper

Status: [ ]

### Test first

Create tests verifying:

* writes to temp file first,
* uses atomic replace,
* final file exists,
* partial temp file does not remain after success,
* existing file is replaced atomically.

### Implementation

Implement:

```python
write_text_atomic(path: Path, content: str) -> None
write_json_atomic(path: Path, data: dict) -> None
```

Use temp file in same directory and `os.replace`.

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_atomic_artifact_write_helpers
```

Acceptance:

* important artifact files are not partially written.

---

## 2.5 Write required artifact files

Status: [ ]

### Test first

Create test verifying draft creation writes atomically:

```txt
original-input.md
brainstorm.md
questions.md
spec.md
github-issue.md
metadata.json
```

and that `metadata.json` is valid JSON.

### Implementation

Implement:

```python
write_issue_artifact_files(root, project_id, draft_id, artifact_content)
```

Use atomic write helpers for every file.

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_write_required_issue_artifacts
```

Acceptance:

* every draft has complete artifact files.

---

## 2.6 Write creation audit files atomically

Status: [ ]

### Test first

Create tests verifying atomic write and read for:

```txt
creation-attempt.json
github-created.json
creation-error.json
```

### Implementation

Implement helpers:

```python
write_creation_attempt(...)
write_github_created(...)
write_creation_error(...)
read_github_created_if_exists(...)
```

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_creation_audit_files
```

Acceptance:

* crash recovery files are reliable.

---

## 2.7 Read artifact files safely

Status: [ ]

### Test first

Create tests verifying:

* existing artifacts can be read,
* missing artifact file returns controlled error,
* invalid draft ID cannot escape path.

### Implementation

Implement:

```python
read_issue_artifact(root, project_id, draft_id, filename)
read_issue_metadata(root, project_id, draft_id)
```

### Verification

Run:

```bash
pytest tests/test_issue_artifacts.py::test_read_issue_artifacts_safely
```

Acceptance:

* later tools can load drafts safely.

---

# Phase 3 — Project Resolution

## 3.1 Resolve exact project ID

Status: [ ]

### Test first

Use a config with multiple projects.

Input:

```txt
project_ref = comapeo-cloud-app
```

Expected:

```txt
resolved
project_id = comapeo-cloud-app
```

### Implementation

Implement first branch of:

```python
resolve_project(config, project_ref=None, text=None, include_archived=False)
```

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_exact_project_id
```

Acceptance:

* exact IDs resolve deterministically.

---

## 3.2 Resolve exact owner/repo

Status: [ ]

### Test first

Input:

```txt
awana-digital/comapeo-cloud-app
```

Expected resolved project.

### Implementation

Reuse GitHub repo parser from MVP 2 where possible.

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_exact_owner_repo
```

Acceptance:

* repo references resolve to configured project.

---

## 3.3 Resolve exact project name

Status: [ ]

### Test first

Input:

```txt
CoMapeo Cloud App
```

Case-insensitive match should resolve.

### Implementation

Add case-insensitive name matching.

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_exact_project_name
```

Acceptance:

* project display names resolve correctly.

---

## 3.4 Resolve fuzzy single match using explicit thresholds

Status: [ ]

### Test first

Input text:

```txt
Create an issue for the EDT migration project about Markdown imports.
```

Given only one EDT-like project, expected resolved project.

### Implementation

Implement deterministic token scoring exactly as defined in this document.

Do not call LLMs in the tool handler.

Resolution:

```txt
resolved if top score >= 3 and second score <= top score - 2
```

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_fuzzy_single_match
```

Acceptance:

* obvious natural-language project references resolve.

---

## 3.5 Return ambiguous candidates using explicit thresholds

Status: [ ]

### Test first

Config contains:

```txt
comapeo-cloud-app
comapeo-mobile
```

Input:

```txt
Create an issue for CoMapeo about export improvements.
```

Expected:

```txt
state = ambiguous
candidates include both projects
no issue is created
```

### Implementation

Use threshold:

```txt
ambiguous if two or more projects have score >= 2 and difference < 2
```

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_ambiguous_project_returns_candidates
```

Acceptance:

* ambiguous project references do not silently choose a project.

---

## 3.6 Return not found using explicit threshold

Status: [ ]

### Test first

Input references a project not in config.

Expected:

```txt
state = not_found
reason = project_not_found
```

### Implementation

Use threshold:

```txt
not_found if top score < 2
```

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_resolve_project_not_found
```

Acceptance:

* missing projects produce a clear blocked state.

---

## 3.7 Exclude archived projects by default

Status: [ ]

### Test first

Input matches an archived project.

Expected:

* not resolved by default,
* resolves only with `include_archived=True` if supported internally.

### Implementation

Use MVP 2 project selection behavior.

### Verification

Run:

```bash
pytest tests/test_issue_project_resolution.py::test_archived_projects_excluded_by_default
```

Acceptance:

* issues are not created against archived projects accidentally.

---

# Phase 4 — Deterministic Draft Generation and Readiness

## 4.1 Validate input length limits

Status: [ ]

### Test first

Create tests verifying limits:

```txt
user input text <= 20,000 characters
answers update <= 20,000 characters
summary <= 2,000 characters
```

Inputs over limit return:

```txt
blocked
reason = input_too_long
```

### Implementation

Implement length validation helpers.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_input_length_limits
```

Acceptance:

* long transcript dumps are blocked instead of silently truncated.

---

## 4.2 Validate issue title

Status: [ ]

### Test first

Valid titles:

```txt
Export selected layers as SMP
Fix broken Markdown import
```

Invalid titles:

```txt
""
"A"
string longer than 120 chars
"# Heading"
"Title\nSecond line"
```

Rules:

```txt
5 to 120 characters
no newline
no markdown heading marker
```

### Implementation

Implement:

```python
validate_issue_title(title: str) -> None
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_issue_title_validation
```

Acceptance:

* bad titles cannot reach GitHub.

---

## 4.3 Generate title from clear text

Status: [ ]

### Test first

Input:

```txt
Users should be able to export selected styled layers as an SMP file for CoMapeo Mobile.
```

Expected title similar to:

```txt
Export selected styled layers as an SMP file
```

Do not require exact wording if deterministic function is documented and tested against expected output.

### Implementation

Implement:

```python
generate_issue_title(text: str) -> str
```

Use deterministic heuristics.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_generate_issue_title_from_clear_text
```

Acceptance:

* clear user text produces usable title.

---

## 4.4 Classify issue kind

Status: [ ]

### Test first

Create tests for kinds:

```txt
feature
bug
task
research
unknown
```

Bug keywords:

```txt
bug
error
fails
broken
crash
not working
regression
```

Feature keywords:

```txt
feature
users should
add support
allow
export
import
```

### Implementation

Implement:

```python
classify_issue_kind(text: str) -> str
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_issue_kind_classification
```

Acceptance:

* body template can be selected deterministically.

---

## 4.5 Generate bug report template and questions

Status: [ ]

### Test first

Input:

```txt
The Markdown import crashes when uploading a file.
```

Expected body prefers sections:

```txt
Problem
Steps to Reproduce
Expected Behavior
Actual Behavior
Acceptance Criteria
```

If reproduction details are missing, draft state should be `needs_user_questions` unless forced.

### Implementation

Implement bug-specific template behavior.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_bug_report_template_and_questions
```

Acceptance:

* bug reports are not treated as generic feature requests.

---

## 4.6 Detect vague requests and generate questions

Status: [ ]

### Test first

Input:

```txt
We need to make the stories better and easier to maintain.
```

Expected:

```txt
state = needs_user_questions
readiness < 0.75
questions are present
no fake acceptance criteria
```

### Implementation

Implement question generation heuristics.

Questions should be short and decision-oriented.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_vague_request_generates_questions
```

Acceptance:

* vague requests do not become fake precise issues.

---

## 4.7 Detect clear requests and generate ready draft using exact readiness formula

Status: [ ]

### Test first

Input:

```txt
Users should export selected styled layers as an SMP file for CoMapeo Mobile. It should only include selected layers, not default catalog layers.
```

Expected:

```txt
state = ready_for_creation
readiness >= 0.75
acceptance criteria present
github-issue.md generated
```

### Implementation

Implement readiness scoring exactly as defined in this document.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_clear_request_generates_ready_draft
```

Acceptance:

* clear issues can go straight to confirmation.

---

## 4.8 Detect large feature and recommend split

Status: [ ]

### Test first

Input mentions multiple independent systems:

```txt
upload layers, style them, export SMP, sync with mobile, authenticate users, and update docs
```

Expected:

* draft may be ready as parent issue,
* brainstorm/spec mentions suggested split,
* GitHub issue body says implementation should be split,
* readiness is not inflated unrealistically.

### Implementation

Implement large-feature heuristic.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_large_feature_recommends_split
```

Acceptance:

* large ideas are scoped as parent issues, not giant implementation tasks.

---

## 4.9 Generate public GitHub issue body

Status: [ ]

### Test first

Create draft with private metadata and internal notes.

Expected `github-issue.md` contains required sections:

```txt
Goal
Acceptance Criteria
```

Expected it does not contain:

```txt
Telegram metadata
readiness score
internal confidence
private brainstorm labels
provider budget info
hidden chain-of-thought
```

### Implementation

Implement:

```python
generate_github_issue_body(draft_content) -> str
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_public_github_issue_body_excludes_private_metadata
```

Acceptance:

* public/private separation is enforced.

---

## 4.10 Markdown safety and body length validation

Status: [ ]

### Test first

Create tests verifying public body rejects:

```txt
<script>
<style>
onclick=
body longer than 20,000 characters
private metadata markers
```

Also verify excessive blank lines are normalized.

### Implementation

Implement:

```python
validate_public_issue_body(body: str) -> None
sanitize_public_issue_body(body: str) -> str
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_markdown_safety_and_body_length
```

Acceptance:

* public GitHub bodies are safe and bounded.

---

## 4.11 Issue body snapshot tests

Status: [ ]

### Test first

Add snapshot-style tests for generated bodies:

```txt
clear feature request
vague feature request with open questions
large parent issue
bug report
forced rough issue
```

### Implementation

Stabilize templates.

### Verification

Run:

```bash
pytest tests/test_issue_body_snapshots.py
```

Acceptance:

* public issue format remains stable.

---

# Phase 5 — Draft Creation, Duplicate Draft Detection, and Update

## 5.1 Create draft with resolved project

Status: [ ]

### Test first

Use clear text and explicit project ID.

Expected:

* draft ID generated,
* artifacts written,
* SQLite row created,
* state is ready or questions depending on input,
* summary is concise.

### Implementation

Implement:

```python
create_issue_draft(root, text, project_ref=None, title=None, force_rough_issue=False)
```

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_create_draft_with_resolved_project
```

Acceptance:

* local draft creation works end-to-end.

---

## 5.2 Detect duplicate local draft title

Status: [ ]

### Test first

Create an existing non-terminal draft with normalized title:

```txt
export selected layers as smp
```

Attempt to create another draft with same normalized title for same project.

Expected:

```txt
blocked
reason = possible_duplicate_draft
existing_draft_id returned
```

Terminal drafts should not block new draft creation.

### Implementation

Implement local draft duplicate detection.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_duplicate_local_draft_detection
```

Acceptance:

* repeated voice/text actions do not create many identical drafts.

---

## 5.3 Create draft with ambiguous project

Status: [ ]

### Test first

Use ambiguous project text.

Expected:

* draft created with state `needs_project_confirmation`,
* candidates stored in metadata or questions,
* no GitHub issue created.

### Implementation

Wire project resolver into draft creation.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_create_draft_with_ambiguous_project
```

Acceptance:

* ambiguous project creates local draft only.

---

## 5.4 Create draft with no project match

Status: [ ]

### Test first

Input cannot match configured projects.

Expected:

```txt
blocked with project_not_found; no draft created
```

### Implementation

Implement no-match handling.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_create_draft_project_not_found_blocks
```

Acceptance:

* drafts are not created without any project path unless future inbox flow is added.

---

## 5.5 Force rough issue cannot bypass ambiguous project

Status: [ ]

### Test first

Call draft creation with:

```txt
force_rough_issue=true
```

and ambiguous project.

Expected:

```txt
state = needs_project_confirmation
not ready_for_creation
```

### Implementation

Ensure project resolution overrides force flags.

### Verification

Run:

```bash
pytest tests/test_issue_drafts.py::test_force_rough_issue_cannot_bypass_project_ambiguity
```

Acceptance:

* force flags cannot create wrong-project issues.

---

## 5.6 Update draft with answers

Status: [ ]

### Test first

Create vague draft, then update with answers.

Expected:

* answers appended to brainstorm,
* spec regenerated,
* questions updated,
* readiness increases when details resolve ambiguity,
* updated_at changes.

### Implementation

Implement:

```python
update_issue_draft(root, draft_id, answers, project_id=None, title=None, force_ready=False)
```

### Verification

Run:

```bash
pytest tests/test_issue_draft_updates.py::test_update_draft_with_answers
```

Acceptance:

* drafts improve with user answers.

---

## 5.7 Confirm project on ambiguous draft

Status: [ ]

### Test first

Create ambiguous draft, update with confirmed project ID.

Expected:

* project_id set,
* state moves to needs_user_questions or ready_for_creation depending on content,
* artifacts regenerated.

### Implementation

Support `project_id` in update flow.

### Verification

Run:

```bash
pytest tests/test_issue_draft_updates.py::test_confirm_project_on_ambiguous_draft
```

Acceptance:

* project ambiguity can be resolved cleanly.

---

## 5.8 Prevent editing terminal drafts

Status: [ ]

### Test first

Draft states:

```txt
created
discarded
blocked
```

Attempt update.

Expected:

```txt
blocked
reason = draft_state_invalid
```

### Implementation

Add state guard.

### Verification

Run:

```bash
pytest tests/test_issue_draft_updates.py::test_terminal_drafts_cannot_be_edited
```

Acceptance:

* created/discarded drafts are immutable.

---

## 5.9 Allow retry edits for creating_failed drafts

Status: [ ]

### Test first

Draft state:

```txt
creating_failed
```

Expected:

* draft can be updated with new answers/title,
* can retry creation after update,
* cannot be edited if `github-created.json` exists.

### Implementation

Add special handling for `creating_failed`.

### Verification

Run:

```bash
pytest tests/test_issue_draft_updates.py::test_creating_failed_draft_can_be_retried
```

Acceptance:

* failed creations are recoverable.

---

## 5.10 Force ready preserves open questions

Status: [ ]

### Test first

Create draft with open questions.

Update with:

```txt
force_ready=true
```

Expected:

* state becomes ready_for_creation,
* open questions remain in `questions.md`,
* `github-issue.md` includes `Open Questions` section,
* force flag recorded in metadata.

### Implementation

Implement force-ready behavior.

### Verification

Run:

```bash
pytest tests/test_issue_draft_updates.py::test_force_ready_preserves_open_questions
```

Acceptance:

* user can create rough issues without losing unresolved questions.

---

# Phase 6 — GitHub Issue Creation Client and Duplicate Detection

## 6.1 Check GitHub CLI availability and auth

Status: [ ]

### Test first

Reuse or extend MVP 1 tests for:

```txt
gh missing
gh unauthenticated
gh available and authenticated
```

### Implementation

Reuse existing `check_gh_available` and `check_gh_auth` helpers.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_github_cli_preconditions
```

Acceptance:

* issue creation blocks cleanly if GitHub CLI is unavailable.

---

## 6.2 Check for duplicate open GitHub issue titles

Status: [ ]

### Test first

Mock command equivalent to:

```bash
gh issue list --repo OWNER/REPO --state open --search "TITLE in:title" --json number,title,url
```

Tests:

* exact normalized title match returns duplicate,
* no match returns no duplicate,
* malformed output returns controlled warning or failure,
* duplicate can be bypassed only with `allow_possible_duplicate=true` in higher-level flow.

### Implementation

Implement:

```python
find_duplicate_github_issue(owner, repo, title) -> DuplicateIssueResult
```

Use exact normalized title match only in MVP 3.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_duplicate_github_issue_detection
```

Acceptance:

* issue creation avoids obvious duplicate titles.

---

## 6.3 Create issue with body file

Status: [ ]

### Test first

Mock subprocess and verify command uses argument array equivalent to:

```bash
gh issue create --repo OWNER/REPO --title TITLE --body-file BODY_FILE
```

Expected:

* no shell string,
* body is written to temp file,
* temp file is deleted in `finally`,
* returned URL parsed.

### Implementation

Implement:

```python
create_github_issue(owner, repo, title, body, labels=None) -> GitHubIssueResult
```

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_create_issue_with_body_file
```

Acceptance:

* safe GitHub issue creation works.

---

## 6.4 Parse issue number and URL from GitHub CLI output variants

Status: [ ]

### Test first

Cover stdout variants:

```txt
URL with newline
URL plus warnings
empty stdout with nonzero exit
stdout without valid issue URL
```

Only accept valid URL matching:

```txt
https://github.com/<owner>/<repo>/issues/<number>
```

Expected:

```txt
issue_number parsed
url parsed
invalid output rejected
```

### Implementation

Implement:

```python
parse_issue_create_output(stdout, owner, repo) -> CreatedIssue
```

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_parse_issue_create_output_variants
```

Acceptance:

* issue number is stored reliably.

---

## 6.5 Label handling does not create labels

Status: [ ]

### Test first

Create tests verifying:

* no labels by default,
* provided labels are passed as `--label` arguments,
* no `gh label create` appears anywhere,
* if explicit labels cause `gh issue create` to fail, behavior is controlled,
* no silent retry without labels.

### Implementation

Add label arguments only when provided.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_labels_are_passed_but_not_created
```

Acceptance:

* labels never produce hidden repo mutations.

---

## 6.6 Handle GitHub issue creation failure

Status: [ ]

### Test first

Mock failure cases:

* subprocess non-zero,
* timeout,
* invalid stdout/no URL,
* stderr contains token-like string.

Expected:

* controlled failed or blocked result,
* secrets redacted,
* temp body file deleted.

### Implementation

Add robust exception handling and redaction.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_github_issue_create_failure_handling
```

Acceptance:

* failures are safe and do not leak secrets.

---

# Phase 7 — Create Issue From Draft, Crash Recovery, and Idempotency

## 7.1 Require confirmation before creating from draft

Status: [ ]

### Test first

Call create-from-draft with `confirm=false` and `dry_run=false`.

Expected:

```txt
blocked
reason = confirm_required
no GitHub command called
```

Dry-run may run with `confirm=false`.

### Implementation

Add confirmation guard.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_create_from_draft_requires_confirmation
```

Acceptance:

* drafts cannot become GitHub issues accidentally.

---

## 7.2 Dry-run create from draft

Status: [ ]

### Test first

Call create-from-draft with:

```txt
dry_run=true
```

Expected:

* validates title/body,
* runs duplicate checks if possible,
* does not call `gh issue create`,
* does not mark draft created,
* returns exact title/body that would be created.

### Implementation

Implement dry-run path before confirmation guard or allow dry-run without confirmation.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_dry_run_create_from_draft
```

Acceptance:

* user can preview GitHub mutation safely.

---

## 7.3 Block draft not ready unless open questions allowed

Status: [ ]

### Test first

Create draft state `needs_user_questions`.

Call create-from-draft with:

```txt
allow_open_questions=false
```

Expected blocked.

Call with:

```txt
allow_open_questions=true
```

Expected allowed only if project is resolved and `github-issue.md` includes open questions.

### Implementation

Implement readiness guard.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_create_from_draft_readiness_guard
```

Acceptance:

* rough issues require explicit user permission.

---

## 7.4 Prevent duplicate issue creation from same draft

Status: [ ]

### Test first

Draft already has:

```txt
state = created
github_issue_number = 47
github_issue_url = ...
```

Call create-from-draft again.

Expected:

```txt
status = skipped
reason = issue_already_created
no new gh command called
existing issue number returned
```

### Implementation

Check draft metadata before GitHub call.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_create_from_draft_is_idempotent
```

Acceptance:

* double taps or repeated tool calls do not create duplicate issues.

---

## 7.5 Set draft to creating and write creation-attempt before GitHub call

Status: [ ]

### Test first

Before mocked `gh issue create` is called, verify:

* draft state is `creating`,
* `creation-attempt.json` exists,
* project-level lock is held.

### Implementation

Update creation flow order.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_creation_attempt_written_before_gh_call
```

Acceptance:

* interrupted creation attempts are visible.

---

## 7.6 Write github-created immediately after GitHub success

Status: [ ]

### Test first

Mock successful `gh issue create`.

Expected:

* `github-created.json` written immediately after URL parse,
* file contains issue number and URL,
* metadata/SQLite updates may follow.

### Implementation

Write creation result before any other state update.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_github_created_written_immediately_after_success
```

Acceptance:

* crash recovery can complete after GitHub success.

---

## 7.7 Recovery when github-created exists

Status: [ ]

### Test first

Set up draft with:

```txt
github-created.json exists
metadata not updated
SQLite not updated
```

Call create-from-draft again.

Expected:

* no `gh issue create` call,
* metadata updated,
* SQLite updated,
* status success or skipped with existing issue.

### Implementation

Implement recovery path.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_recover_from_github_created_file
```

Acceptance:

* crash after GitHub success does not create duplicate issue.

---

## 7.8 Failure writes creation-error and creating_failed state

Status: [ ]

### Test first

Mock GitHub failure after draft enters creating.

Expected:

* `creation-error.json` written,
* draft state = `creating_failed`,
* error redacted,
* retry allowed later.

### Implementation

Add failure path.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_failure_writes_creation_error_and_state
```

Acceptance:

* failed creation is inspectable and recoverable.

---

## 7.9 Retry creating_failed draft safely

Status: [ ]

### Test first

Draft state:

```txt
creating_failed
```

Call create-from-draft with `confirm=true`.

Expected:

* checks for github-created first,
* runs duplicate GitHub issue check,
* calls gh only if no existing issue,
* updates state on success.

### Implementation

Implement retry behavior.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_retry_creating_failed_draft_safely
```

Acceptance:

* failed issue creation can be retried without obvious duplicates.

---

## 7.10 Duplicate GitHub issue blocks creation unless allowed

Status: [ ]

### Test first

Mock duplicate issue found by title.

Expected:

* with `allow_possible_duplicate=false`, blocked,
* with `allow_possible_duplicate=true`, creation proceeds after confirmation.

### Implementation

Wire duplicate detection into create path.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_duplicate_github_issue_blocks_unless_allowed
```

Acceptance:

* duplicate issue prevention works.

---

## 7.11 Update draft metadata after successful creation

Status: [ ]

### Test first

After successful issue creation:

Expected metadata:

```txt
state = created
github_issue_number set
github_issue_url set
updated_at changed
```

SQLite issue_drafts row matches metadata.

### Implementation

Update artifact metadata and SQLite draft row after GitHub success.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_create_from_draft_updates_metadata
```

Acceptance:

* local draft records link to GitHub issue.

---

## 7.12 Upsert created issue into SQLite issues table

Status: [ ]

### Test first

After issue creation, expected `issues` table row:

```txt
project_id
issue_number
title
state
labels_json
last_seen_at
```

Expected state mapping:

```txt
spec_ready if draft was ready_for_creation, readiness >= 0.75, no open questions, and no force flag was used.
needs_triage if created with open questions.
needs_triage if force_ready or force_rough_issue was used.
needs_triage if issue kind is unknown.
```

### Implementation

Call MVP 1 issue upsert helper.

### Verification

Run:

```bash
pytest tests/test_issue_github_create.py::test_created_issue_upserts_issues_table
```

Acceptance:

* created issues appear in portfolio state.

---

# Phase 8 — Direct Issue Creation Wrapper

## 8.1 Direct issue create requires confirmation or dry-run

Status: [ ]

### Test first

Call `portfolio_issue_create` with:

```txt
confirm=false
dry_run=false
```

Expected:

```txt
blocked
reason = confirm_required
```

Call with:

```txt
dry_run=true
```

Expected dry-run succeeds without GitHub mutation.

### Implementation

Add direct create confirmation guard.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_direct_issue_create_requires_confirmation_or_dry_run
```

Acceptance:

* direct creation cannot mutate GitHub accidentally.

---

## 8.2 Direct issue create creates draft first

Status: [ ]

### Test first

Call `portfolio_issue_create` with structured title/body.

Expected:

* local draft artifact is created,
* draft metadata exists,
* same create-from-draft path is used,
* GitHub issue created only after draft exists,
* idempotency records exist.

### Implementation

Implement `portfolio_issue_create` as wrapper around draft creation plus create-from-draft flow.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_direct_issue_create_creates_draft_first
```

Acceptance:

* no issue creation bypasses artifacts.

---

# Phase 9 — Tool Handlers and Schemas

## 9.1 Add MVP 3 tool schemas

Status: [ ]

### Test first

Create tests verifying schemas exist for:

```txt
portfolio_project_resolve
portfolio_issue_draft
portfolio_issue_questions
portfolio_issue_update_draft
portfolio_issue_create
portfolio_issue_create_from_draft
portfolio_issue_explain_draft
portfolio_issue_list_drafts
portfolio_issue_discard_draft
```

Each schema must include clear parameter descriptions and all relevant flags:

```txt
confirm
dry_run
allow_possible_duplicate
allow_open_questions
force_ready
force_rough_issue
include_created
```

### Implementation

Add schemas in `schemas.py` using verified Hermes plugin API.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_mvp3_tool_schemas_exist
```

Acceptance:

* Hermes can understand MVP 3 tool inputs.

---

## 9.2 Implement `portfolio_project_resolve`

Status: [ ]

### Test first

Test success, ambiguous, and not-found cases through tool handler.

### Implementation

Wire handler to resolver.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_project_resolve
```

Acceptance:

* project resolution is available as a Hermes tool.

---

## 9.3 Implement `portfolio_issue_draft`

Status: [ ]

### Test first

Verify handler:

* creates draft from clear text,
* creates questions from vague text,
* blocks if project not found,
* creates ambiguous-project draft when candidates exist,
* detects duplicate local drafts,
* supports force_rough_issue without bypassing ambiguous project,
* returns shared result shape.

### Implementation

Wire handler to draft creation.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_draft
```

Acceptance:

* Hermes can create local issue drafts.

---

## 9.4 Implement `portfolio_issue_questions`

Status: [ ]

### Test first

Verify handler:

* returns questions for draft,
* blocks if draft missing,
* handles draft with no questions.

### Implementation

Wire handler to artifact read.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_questions
```

Acceptance:

* Hermes can ask the user draft questions.

---

## 9.5 Implement `portfolio_issue_update_draft`

Status: [ ]

### Test first

Verify handler:

* updates answers,
* confirms project,
* supports force_ready,
* blocks terminal draft states,
* supports creating_failed retry edits,
* returns updated draft state.

### Implementation

Wire handler to draft update.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_update_draft
```

Acceptance:

* Hermes can refine drafts with user answers.

---

## 9.6 Implement `portfolio_issue_create`

Status: [ ]

### Test first

Verify handler:

* requires confirmation unless dry-run,
* creates draft first,
* validates project,
* validates title/body,
* blocks GitHub precondition failures,
* runs duplicate checks,
* upserts issue state,
* writes local artifact folder for created issue,
* returns issue URL and number.

### Implementation

Wire direct issue creation wrapper.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_create
```

Acceptance:

* clear structured issues can be created safely without bypassing draft artifacts.

---

## 9.7 Implement `portfolio_issue_create_from_draft`

Status: [ ]

### Test first

Verify handler:

* requires confirmation unless dry-run,
* blocks not-ready draft,
* supports allow_open_questions,
* supports allow_possible_duplicate,
* supports dry-run,
* is idempotent,
* supports crash recovery,
* updates metadata and SQLite after creation.

### Implementation

Wire draft-to-GitHub creation path.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_create_from_draft
```

Acceptance:

* drafts can safely become GitHub issues.

---

## 9.8 Implement `portfolio_issue_explain_draft`

Status: [ ]

### Test first

Verify handler returns:

```txt
draft state
project
title
readiness
issue kind
summary of spec
open questions
ready/not ready
GitHub issue link if created
creation error if failed
```

No mutation.

### Implementation

Wire handler to artifact/state reads.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_explain_draft
```

Acceptance:

* user can inspect draft state.

---

## 9.9 Implement `portfolio_issue_list_drafts`

Status: [ ]

### Test first

Verify filters:

```txt
project_id
state
include_created
```

Default excludes created drafts.

### Implementation

Wire handler to draft list helper.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_list_drafts
```

Acceptance:

* user can see open drafts.

---

## 9.10 Implement `portfolio_issue_discard_draft`

Status: [ ]

### Test first

Verify:

* requires confirmation,
* sets state to discarded,
* does not delete artifact files,
* blocks if draft missing,
* skipped if already discarded,
* blocks if draft is created.

### Implementation

Wire discard handler.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_portfolio_issue_discard_draft
```

Acceptance:

* drafts can be safely abandoned without data loss.

---

## 9.11 Register MVP 3 tools with Hermes

Status: [ ]

### Test first

Create registration test verifying all MVP 3 tools are discoverable alongside MVP 1 and MVP 2 tools.

### Implementation

Update `__init__.py` registration using verified Hermes plugin API.

### Verification

Run:

```bash
pytest tests/test_issue_tools.py::test_mvp3_tool_registration
```

Acceptance:

* Hermes can discover MVP 3 tools.

---

# Phase 10 — Dev CLI Support

## 10.1 Add dev CLI support for project resolution and draft creation

Status: [ ]

### Test first

Create tests invoking:

```bash
python dev_cli.py portfolio_project_resolve --project-ref comapeo-cloud-app --root <tmp> --json
python dev_cli.py portfolio_issue_draft --project-ref comapeo-cloud-app --text "Users should export selected layers as SMP" --root <tmp> --json
```

### Implementation

Extend `dev_cli.py`.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_issue_resolve_and_draft
```

Acceptance:

* draft flow can be tested outside Hermes.

---

## 10.2 Add dev CLI support for draft update, questions, explain, list, discard

Status: [ ]

### Test first

Create tests invoking each draft management CLI command.

### Implementation

Extend `dev_cli.py`.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_issue_draft_management
```

Acceptance:

* all draft management tools run locally.

---

## 10.3 Add dev CLI support for issue creation commands

Status: [ ]

### Test first

Create tests invoking:

```txt
portfolio_issue_create
portfolio_issue_create_from_draft
```

with GitHub calls mocked.

Include flags:

```txt
--confirm
--dry-run
--allow-possible-duplicate
--allow-open-questions
```

### Implementation

Extend `dev_cli.py`.

### Verification

Run:

```bash
pytest tests/test_dev_cli.py::test_dev_cli_issue_creation_commands
```

Acceptance:

* GitHub issue creation paths can be tested outside Hermes.

---

# Phase 11 — Hermes Skills

## 11.1 Create `issue-brainstorm` skill

Status: [ ]

### Test first

Create test verifying:

```txt
skills/issue-brainstorm/SKILL.md
```

exists and has frontmatter:

```yaml
name: issue-brainstorm
```

### Implementation

Create skill file.

### Verification

Run:

```bash
pytest tests/test_issue_skills.py::test_issue_brainstorm_skill_exists
```

Acceptance:

* skill exists.

---

## 11.2 Add issue-brainstorm process and safety rules

Status: [ ]

### Test first

Skill must say:

* use for rough ideas, voice notes, vague feature requests,
* resolve project first,
* ask user to choose if project ambiguous,
* call `portfolio_issue_draft`,
* ask only important questions,
* call `portfolio_issue_update_draft` with answers,
* ask for confirmation before `portfolio_issue_create_from_draft`,
* use dry-run if the user wants to preview,
* do not start development,
* do not create branches/worktrees,
* do not modify repos.

### Implementation

Write skill content.

### Verification

Run:

```bash
pytest tests/test_issue_skills.py::test_issue_brainstorm_skill_rules
```

Acceptance:

* Hermes has clear issue brainstorming guidance.

---

## 11.3 Create `issue-create` skill

Status: [ ]

### Test first

Create test verifying:

```txt
skills/issue-create/SKILL.md
```

exists and has frontmatter:

```yaml
name: issue-create
```

### Implementation

Create skill file.

### Verification

Run:

```bash
pytest tests/test_issue_skills.py::test_issue_create_skill_exists
```

Acceptance:

* skill exists.

---

## 11.4 Add issue-create process and safety rules

Status: [ ]

### Test first

Skill must say:

* use for clear GitHub issue creation requests,
* resolve project first,
* ask user if project ambiguous,
* use draft flow if request is vague,
* require confirmation before GitHub issue creation,
* use dry-run when user asks to preview,
* never include private Telegram metadata,
* never create labels automatically,
* never start implementation.

### Implementation

Write skill content.

### Verification

Run:

```bash
pytest tests/test_issue_skills.py::test_issue_create_skill_rules
```

Acceptance:

* Hermes creates issues only when safe.

---

# Phase 12 — Security Hardening

## 12.1 Prove no Git commands are introduced

Status: [ ]

### Test first

Create/extend source scan verifying MVP 3 does not add Git commands.

### Implementation

No Git needed for MVP 3.

### Verification

Run:

```bash
pytest tests/test_security.py::test_mvp3_introduces_no_git_commands
```

Acceptance:

* issue flow cannot modify worktrees.

---

## 12.2 Prove only allowed GitHub issue mutation command is used

Status: [ ]

### Test first

Reject all GitHub mutation commands except:

```txt
gh issue create
```

Also allow read command:

```txt
gh issue list
```

### Implementation

Audit `issue_github.py`.

### Verification

Run:

```bash
pytest tests/test_security.py::test_mvp3_only_allows_gh_issue_create_mutation
```

Acceptance:

* no PR/label/comment/API mutation slips in.

---

## 12.3 Prove issue body uses temp file and no shell string

Status: [ ]

### Test first

Mock subprocess and temp file handling.

Expected:

* command passed as list,
* `--body-file` used,
* `shell=True` not used,
* temp file deleted.

### Implementation

Harden issue creation client.

### Verification

Run:

```bash
pytest tests/test_security.py::test_issue_body_file_and_no_shell
```

Acceptance:

* long issue bodies are safe.

---

## 12.4 Prove artifacts cannot escape issue artifact root

Status: [ ]

### Test first

Try malicious project IDs and draft IDs.

Expected blocked or validation error.

### Implementation

Use path containment checks.

### Verification

Run:

```bash
pytest tests/test_security.py::test_issue_artifacts_cannot_escape_root
```

Acceptance:

* artifact writes are contained.

---

## 12.5 Prove GitHub body excludes private metadata

Status: [ ]

### Test first

Create local draft with private/internal fields.

Expected public GitHub body excludes them.

### Implementation

Ensure `github-issue.md` generator only uses public fields.

### Verification

Run:

```bash
pytest tests/test_security.py::test_public_issue_body_excludes_private_metadata
```

Acceptance:

* private context stays local.

---

## 12.6 Redact secrets from errors and summaries

Status: [ ]

### Test first

Extend redaction tests with GitHub issue creation failures containing token-like strings.

### Implementation

Apply `redact_secrets` to new handlers and GitHub client errors.

### Verification

Run:

```bash
pytest tests/test_security.py::test_redact_secrets
```

Acceptance:

* no secrets leak through summaries or errors.

---

## 12.7 Prove no hidden reasoning is stored

Status: [ ]

### Test first

Create tests verifying `brainstorm.md` uses allowed structured headings only and does not contain markers like:

```txt
chain of thought
hidden reasoning
private reasoning
step-by-step reasoning
```

### Implementation

Constrain brainstorm generation template.

### Verification

Run:

```bash
pytest tests/test_security.py::test_no_hidden_reasoning_in_artifacts
```

Acceptance:

* local artifacts remain concise and safe to inspect.

---

# Phase 13 — Full Regression and Local E2E

## 13.1 Run full automated test suite

Status: [ ]

### Test first

The full suite is the test.

### Implementation

Fix regressions.

### Verification

Run:

```bash
pytest
```

Acceptance:

* all MVP 1, MVP 2, and MVP 3 tests pass.

---

## 13.2 Local e2e: clear issue to created GitHub issue

Status: [ ]

### Test first

Create local e2e test with temp root and mocked GitHub calls:

1. seed project config,
2. draft clear issue,
3. confirm create from draft,
4. mock GitHub issue URL,
5. verify draft state created,
6. verify SQLite issue row,
7. verify artifacts exist,
8. verify creation audit files,
9. verify temp body file deleted.

### Implementation

Add e2e test and fix gaps.

### Verification

Run:

```bash
pytest tests/test_issue_e2e.py::test_clear_issue_to_github_issue
```

Acceptance:

* the happy path works without Hermes.

---

## 13.3 Local e2e: vague idea to questions to ready draft

Status: [ ]

### Test first

Create local e2e test:

1. seed project config,
2. create vague draft,
3. verify questions,
4. update with answers,
5. verify ready state,
6. verify public GitHub body includes user answers.

### Implementation

Add e2e test and fix gaps.

### Verification

Run:

```bash
pytest tests/test_issue_e2e.py::test_vague_idea_to_ready_draft
```

Acceptance:

* brainstorming flow works locally.

---

## 13.4 Local e2e: ambiguous project blocks issue creation

Status: [ ]

### Test first

Create local e2e test:

1. seed config with two similar projects,
2. draft ambiguous issue,
3. verify candidates returned,
4. attempt create from draft,
5. verify blocked,
6. confirm no GitHub call.

### Implementation

Add e2e test and fix gaps.

### Verification

Run:

```bash
pytest tests/test_issue_e2e.py::test_ambiguous_project_blocks_issue_creation
```

Acceptance:

* wrong-project issue creation is prevented.

---

## 13.5 Local e2e: duplicate prevention and retry recovery

Status: [ ]

### Test first

Create local e2e test:

1. create a draft,
2. simulate `github-created.json` exists but metadata/SQLite incomplete,
3. retry create-from-draft,
4. verify no second GitHub call,
5. verify metadata/SQLite completed,
6. create another draft with same title,
7. verify duplicate local draft or GitHub issue blocks.

### Implementation

Add e2e test and fix gaps.

### Verification

Run:

```bash
pytest tests/test_issue_e2e.py::test_duplicate_prevention_and_retry_recovery
```

Acceptance:

* duplicate and partial-failure recovery paths work locally.

---

## 13.6 Local e2e: dry-run does not mutate GitHub

Status: [ ]

### Test first

Create local e2e test:

1. draft clear issue,
2. run create-from-draft with `dry_run=true`,
3. verify no `gh issue create` call,
4. verify draft not marked created,
5. verify returned title/body are exact.

### Implementation

Add e2e test and fix gaps.

### Verification

Run:

```bash
pytest tests/test_issue_e2e.py::test_dry_run_does_not_mutate_github
```

Acceptance:

* users can preview safely.

---

# Phase 14 — Manual Hermes Smoke Tests

Do not start manual Hermes tests until all automated tests pass.

Use a test root first:

```bash
export AGENT_SYSTEM_ROOT=/tmp/hermes-portfolio-mvp3-test
```

## 14.1 Draft clear issue from Hermes

Status: [ ]

### Implementation

Ask Hermes:

```txt
Draft an issue for CoMapeo Cloud App: users should export selected styled layers as an SMP file for CoMapeo Mobile.
```

Expected tool:

```txt
portfolio_issue_draft
```

### Verification

Manual acceptance:

* draft is created,
* summary says whether it is ready for GitHub,
* no GitHub issue is created yet unless explicitly requested.

---

## 14.2 Dry-run issue creation

Status: [ ]

### Implementation

Ask Hermes:

```txt
Show me what GitHub issue would be created from that draft, but do not create it yet.
```

Expected:

```txt
portfolio_issue_create_from_draft with dry_run=true
```

### Verification

Manual acceptance:

* title/body preview is returned,
* GitHub issue is not created,
* draft is not marked created.

---

## 14.3 Brainstorm vague idea

Status: [ ]

### Implementation

Ask Hermes:

```txt
I have an idea for the EDT migration. We need to make the stories better and easier to maintain.
```

Expected:

* `issue-brainstorm` flow,
* `portfolio_issue_draft` called,
* draft state is `needs_user_questions`,
* Hermes asks concise follow-up questions.

### Verification

Manual acceptance:

* vague idea does not become GitHub issue prematurely.

---

## 14.4 Answer questions and create issue

Status: [ ]

### Implementation

Reply to Hermes with answers.

Expected:

```txt
portfolio_issue_update_draft
```

Then confirm creation.

Expected:

```txt
portfolio_issue_create_from_draft with confirm=true
```

### Verification

Manual acceptance:

* draft becomes ready,
* Hermes asks for confirmation,
* duplicate check runs,
* GitHub issue is created only after confirmation,
* SQLite issue row is created,
* draft state becomes created.

---

## 14.5 Ambiguous project does not create issue

Status: [ ]

### Implementation

With multiple CoMapeo projects configured, ask:

```txt
Create an issue for CoMapeo about export improvements.
```

Expected:

* Hermes asks which project,
* no GitHub issue is created.

### Verification

Manual acceptance:

* ambiguous project is blocked.

---

## 14.6 List and discard drafts

Status: [ ]

### Implementation

Ask:

```txt
Show my open issue drafts.
```

Then:

```txt
Discard the draft about export improvements.
```

Expected tools:

```txt
portfolio_issue_list_drafts
portfolio_issue_discard_draft
```

### Verification

Manual acceptance:

* open drafts are listed,
* discard requires confirmation or clear user intent,
* artifacts are not deleted.

---

# Definition of Done for MVP 3

MVP 3 is complete only when all are true:

* [ ] MVP 1 and MVP 2 tests pass before MVP 3 work starts.
* [ ] `issue_drafts` table exists and is initialized idempotently.
* [ ] Draft states include `creating` and `creating_failed` and are validated.
* [ ] Draft mutation locks prevent duplicate concurrent updates.
* [ ] Project-level GitHub issue creation lock prevents concurrent issue creation in same repo.
* [ ] Draft IDs are safe and unique.
* [ ] Issue artifacts are written under `$HOME/.agent-system/artifacts/issues/`.
* [ ] Artifact paths cannot escape the issue artifact root.
* [ ] Important artifact writes are atomic.
* [ ] Required artifact files are created for every draft.
* [ ] Creation audit files support crash recovery.
* [ ] Project resolution works for ID, name, owner/repo, and fuzzy text.
* [ ] Fuzzy matching uses explicit scoring and thresholds.
* [ ] Ambiguous project resolution returns candidates and blocks issue creation.
* [ ] Archived projects are excluded by default.
* [ ] Title validation works.
* [ ] Length limits are enforced.
* [ ] Issue kind classification works for feature, bug, task, research, unknown.
* [ ] Bug reports use bug-specific template and questions.
* [ ] Clear requests become ready drafts.
* [ ] Vague requests become drafts with questions.
* [ ] Large features recommend a split or parent issue.
* [ ] Public GitHub issue body has required sections.
* [ ] Public GitHub issue body excludes private metadata.
* [ ] Markdown safety validation works.
* [ ] Body snapshot tests pass.
* [ ] Duplicate local drafts are detected.
* [ ] Drafts can be updated with user answers.
* [ ] Terminal draft states cannot be edited.
* [ ] `creating_failed` drafts can be retried safely.
* [ ] Force flags cannot bypass ambiguous project resolution.
* [ ] Force-ready preserves open questions in the public issue body.
* [ ] GitHub issue creation uses `gh issue create` with a body file.
* [ ] Temp issue body files are deleted.
* [ ] Labels are never created automatically.
* [ ] Labels are only applied when explicitly provided.
* [ ] Duplicate open GitHub issue titles are detected before creation.
* [ ] `allow_possible_duplicate=true` is required to bypass duplicate issue block.
* [ ] Create-from-draft requires confirmation unless dry-run.
* [ ] Direct issue creation requires confirmation unless dry-run.
* [ ] Direct issue creation creates a draft first.
* [ ] Dry-run returns exact title/body and does not mutate GitHub.
* [ ] Create-from-draft is idempotent and prevents duplicate issues.
* [ ] Crash recovery works when `github-created.json` exists.
* [ ] Creation failures write `creation-error.json` and set `creating_failed`.
* [ ] Created drafts update metadata and SQLite.
* [ ] Created GitHub issues are upserted into the `issues` table with correct state mapping.
* [ ] MVP 3 tools are registered with Hermes.
* [ ] Dev CLI supports all MVP 3 tools and flags.
* [ ] `issue-brainstorm` skill exists and contains safety rules.
* [ ] `issue-create` skill exists and contains safety rules.
* [ ] Security tests prove no Git commands are introduced.
* [ ] Security tests prove no PR/label/comment/API mutation commands are used.
* [ ] Security tests prove no `shell=True` subprocess execution is used.
* [ ] Security tests prove private metadata is excluded from public issue body.
* [ ] Security tests prove no hidden reasoning is stored.
* [ ] Security tests prove secrets are redacted.
* [ ] Local e2e tests pass.
* [ ] Full automated test suite passes with `pytest`.
* [ ] Manual Hermes smoke tests pass using a test root.

---

# Suggested Implementation Order

Follow this exact order:

1. Phase 0 — preflight and safety guards
2. Phase 1 — SQLite draft state and locks
3. Phase 2 — artifact path safety and atomic file writing
4. Phase 3 — project resolution
5. Phase 4 — deterministic draft generation and readiness
6. Phase 5 — draft creation, duplicate draft detection, and update
7. Phase 6 — GitHub issue creation client and duplicate detection
8. Phase 7 — create-from-draft, crash recovery, and idempotency
9. Phase 8 — direct issue creation wrapper
10. Phase 9 — tool handlers and schemas
11. Phase 10 — dev CLI support
12. Phase 11 — Hermes skills
13. Phase 12 — security hardening
14. Phase 13 — full regression and local e2e
15. Phase 14 — manual Hermes smoke tests

Reason:

* state and artifacts must exist before draft tools,
* project resolution must be deterministic before issue creation,
* drafts should be local and safe before GitHub mutation is added,
* duplicate detection and crash recovery must exist before real GitHub issue creation,
* GitHub creation must be isolated and heavily tested,
* direct issue creation should wrap the safer draft creation path,
* Hermes tool handlers should wrap already-tested pure modules,
* manual Hermes tests come last.

---

# Future MVPs Not Allowed Here

Do not add these in MVP 3:

```txt
maintenance skill execution
worktree creation
implementation loops
review ladders
budget routing
auto-development
auto-merge execution
PR creation
branch creation
repo file modification
label creation
GitHub Projects integration
```

MVP 3 is issue creation and brainstorming only.
