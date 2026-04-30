# Gap Analysis: MVP 4 Spec vs Implementation

You are analyzing a codebase for spec conformance. DO NOT modify any files. Produce a structured analysis and action recommendation only.

## Project
- Repo: `portfolio-manager` (repo root)
- Branch: `feature/mvp4-maintenance-skills`
- PR: #4 (https://github.com/luandro/hermes-portfolio-manager/pull/4)
- 690 tests passing, 58 files changed, ~8k lines

## Task
Read docs/mvps/mvp4-spec.md (the spec) and compare against the actual implementation. I have identified the gaps below. Your job is to:
1. Verify each gap by reading the actual code
2. Classify each gap as: BLOCKER (must fix before merge), IMPORTANT (should fix), MINOR (nice to have), DEFER (post-merge)
3. For each gap, recommend ONE of: rewrite, extend, rename, add, accept-as-is
4. Produce a prioritized action plan

## Known Gaps (verify these by reading the code)

### GAP 1: Wrong built-in skills (CRITICAL)
**Spec requires:** `untriaged_issue_digest`, `stale_issue_digest`, `open_pr_health`, `repo_guidance_docs`
**Implementation has:** `health_check`, `dependency_audit`, `license_compliance`, `security_advisory`, `stale_branches`
These are completely different skills with different logic. The spec skills are about issue triage, stale issues, PR health, and repo guidance docs. The impl skills are about dependency auditing, license checking, security advisories, stale branches, and generic health checks.
**Files:** `portfolio_manager/skills/builtin/*.py`, `portfolio_manager/skills/builtin/__init__.py`

### GAP 2: DB schema mismatch (CRITICAL)
**Spec `maintenance_runs` expects columns:** `id` (PK), `skill_id`, `project_id`, `status`, `started_at`, `finished_at`, `due`, `dry_run`, `refresh_github`, `finding_count`, `draft_count`, `report_path`, `summary`, `error`, `created_at`
**Impl `maintenance_runs` has:** `run_id` (PK, not `id`), `project_id`, `skill_id`, `status`, `started_at`, `finished_at`, `summary`, `reason`
**Missing columns:** `due`, `dry_run`, `refresh_github`, `finding_count`, `draft_count`, `report_path`, `error`, `created_at`

**Spec `maintenance_findings` expects columns:** `fingerprint` (PK), `project_id`, `skill_id`, `severity`, `status`, `title`, `body`, `source_type`, `source_id`, `source_url`, `metadata_json`, `first_seen_at`, `last_seen_at`, `resolved_at`, `run_id`, `issue_draft_id`, `created_at`, `updated_at`
**Impl `maintenance_findings` has:** `finding_id` (AUTOINCREMENT PK, not `fingerprint`), `run_id`, `fingerprint`, `severity`, `title`, `body`, `source_type`, `source_id`, `source_url`, `metadata_json`, `draftable`, `issue_draft_id`, `created_at`
**Missing columns:** `project_id`, `skill_id`, `status`, `first_seen_at`, `last_seen_at`, `resolved_at`, `updated_at`
**Wrong PK:** Should be `fingerprint TEXT PRIMARY KEY`, not `finding_id INTEGER AUTOINCREMENT`

**File:** `portfolio_manager/state.py`

### GAP 3: Missing indexes (IMPORTANT)
**Spec requires:**
- `idx_maintenance_runs_project_skill` ON `(project_id, skill_id, finished_at)`
- `idx_maintenance_runs_status` ON `(status, finished_at)`
- `idx_maintenance_findings_project_skill` ON `(project_id, skill_id, status)`
- `idx_maintenance_findings_severity` ON `(severity, status)`

**Impl has:**
- `idx_maintenance_runs_project` ON `(project_id)`
- `idx_maintenance_runs_skill` ON `(skill_id)`
- `idx_maintenance_findings_run` ON `(run_id)`
- `idx_maintenance_findings_fingerprint` ON `(fingerprint)`

### GAP 4: Missing CLI args (IMPORTANT)
**Spec requires 15 CLI args:** `--skill-id`, `--interval-hours`, `--config-json`, `--include-disabled`, `--include-project-overrides`, `--include-paused`, `--include-archived`, `--include-not-due`, `--refresh-github`, `--create-issue-drafts`, `--max-projects`, `--run-id`, `--severity`, `--limit`, `--include-resolved`
**Impl has:** Only `--skill-id` (recently added for smoke test fix)
**Missing 14 args.** Many tools cannot receive their spec-defined parameters via CLI.
**File:** `dev_cli.py`

### GAP 5: Wrong state helper names (MINOR)
**Spec expects:** `start_maintenance_run`, `finish_maintenance_run`, `get_maintenance_run`, `list_maintenance_runs`, `upsert_maintenance_finding`, `get_maintenance_finding`, `list_maintenance_findings`, `mark_resolved_missing_findings`
**Impl has:** `start_run`, `finish_run`, `insert_finding`, `get_findings_by_run`, `get_latest_successful_run`, `recover_stale_runs`
**Missing:** `get_maintenance_run`, `list_maintenance_runs`, `upsert_maintenance_finding`, `get_maintenance_finding`, `list_maintenance_findings`, `mark_resolved_missing_findings`
**File:** `portfolio_manager/maintenance_state.py`

### GAP 6: Missing spec-expected files (MINOR)
**Spec expects:** `maintenance_runs.py`, `maintenance_skills.py`
**Impl splits functionality across:** `maintenance_state.py`, `maintenance_orchestrator.py`, `maintenance_tools.py`, `maintenance_due.py`, `maintenance_planner.py`, `maintenance_reports.py`, `maintenance_drafts.py`
This may be acceptable — functionality exists but file layout differs.

### GAP 7: Effective config resolution (NEEDS VERIFICATION)
**Spec requires 5-layer cascade:** registry defaults → yaml defaults → yaml skills.<id> → yaml projects.<id>.skills.<id> → tool args
Verify if implementation actually does this correctly.
**File:** `portfolio_manager/maintenance_config.py`

### GAP 8: Lock naming (NEEDS VERIFICATION)
**Spec requires:** `maintenance:config` (60s), `maintenance:run` (30min), `maintenance:project:<id>:skill:<id>` (10min)
Verify lock names and TTLs match.
**File:** `portfolio_manager/maintenance_tools.py`, `portfolio_manager/maintenance_orchestrator.py`

## Analysis Instructions

1. Read docs/mvps/mvp4-spec.md fully (2106 lines)
2. Read the actual implementation files to verify each gap
3. Read tests to understand coverage gaps
4. For each gap, classify severity and recommend action
5. Consider: can gaps be fixed incrementally (post-merge), or do they require a rewrite?
6. Consider: which gaps are structural (schema, skills) vs cosmetic (names, file layout)?
7. Produce a final recommendation: merge as-is + fix in follow-up PRs, or block merge until critical gaps fixed?

## Output Format

For each gap:
```text
### GAP N: <title>
**Verified:** yes/no
**Severity:** BLOCKER / IMPORTANT / MINOR / DEFER
**Action:** rewrite / extend / rename / add / accept-as-is
**Effort:** small (<1h) / medium (1-4h) / large (4h+)
**Rationale:** <why this classification>
**Recommendation:** <specific steps>
```

Final verdict:
```text
MERGE DECISION: <block until X fixed, then merge> OR <merge now, fix Y in follow-up>
PRIORITY ORDER: <ordered list of actions>
ESTIMATED TOTAL EFFORT: <hours>
```
