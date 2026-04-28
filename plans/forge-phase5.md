# Phase 5: Local Issue Draft Integration

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## Context
- Branch: feature/mvp4-maintenance-skills
- 621 tests currently passing
- Existing: maintenance_models.py, maintenance_registry.py, maintenance_state.py, maintenance_config.py, maintenance_artifacts.py, maintenance_reports.py, maintenance_due.py, maintenance_planner.py, maintenance_orchestrator.py
- Built-in skills in portfolio_manager/skills/builtin/
- MVP 3 issue draft system already exists (check what's available in the codebase)

## Tasks

### Task 5.1: Draft planning rules
Create `portfolio_manager/maintenance_drafts.py`:
- Function: `plan_maintenance_issue_drafts(findings_by_project_skill_run) -> list[DraftPlan]`
- DraftPlan is a dataclass with: project_id, skill_id, run_id, findings, should_create
- Rules:
  - create_issue_drafts config flag must be True
  - Finding must have draftable=True
  - Existing finding with issue_draft_id already set → skip (no duplicate)
  - One draft per project+skill+run combination
- Pure logic, no side effects, no MVP 3 calls yet

Tests in `tests/test_maintenance_drafts.py`:
- test_create_issue_drafts_false_creates_no_drafts
- test_create_issue_drafts_true_requires_skill_support
- test_non_draftable_findings_are_ignored_for_drafts
- test_existing_finding_with_issue_draft_id_does_not_duplicate
- test_one_draft_per_project_skill_run

### Task 5.2: Create local issue drafts through MVP 3 helpers
Add to `maintenance_drafts.py`:
- Function: `create_maintenance_drafts(root, conn, draft_plans, config) -> list[dict]`
- For each DraftPlan:
  - Build draft body: goal, findings summary, acceptance criteria, run_id reference
  - Exclude private metadata and chain-of-thought from body
  - Call existing MVP 3 draft helper (search codebase for issue draft functions)
  - On success: update finding.issue_draft_id in DB, write draft-created.json artifact
  - On failure: record warning, don't lose findings
- NEVER call: gh issue create, portfolio_issue_create, portfolio_issue_create_from_draft with confirm=true
- Only local draft creation

Tests (add to test_maintenance_drafts.py):
- test_draft_creation_uses_existing_issue_draft_helper (mocked)
- test_draft_body_has_goal_findings_acceptance_and_run_id
- test_draft_body_excludes_private_metadata_and_cot
- test_draft_creation_failure_records_warning
- test_draft_created_updates_finding_issue_draft_id
- test_draft_created_artifact_written

### Task 5.3: Repair behavior for partial draft creation
Add to `maintenance_drafts.py`:
- Function: `repair_draft_references(root, conn) -> int`
- Scans for draft-created.json artifacts whose findings are missing issue_draft_id in SQLite
- Updates SQLite to match the artifact
- Ignores missing or invalid artifacts
- Does not duplicate existing references
- Returns count of repairs made

Tests (add to test_maintenance_drafts.py):
- test_repair_draft_created_artifact_updates_missing_sqlite_reference
- test_repair_ignores_missing_or_invalid_draft_artifact
- test_repair_does_not_duplicate_existing_draft_reference

## Rules
1. Write tests FIRST, run them to confirm they FAIL, then implement
2. Run: uv run python -m pytest tests/ --ignore=tests/test_structure.py -x --tb=short -q
3. All 621 existing tests must stay passing
4. Search the codebase first for existing MVP 3 draft helpers to understand the API
5. Draft bodies must be clean — no internal metadata, no CoT
6. Only local drafts, never publish to GitHub
