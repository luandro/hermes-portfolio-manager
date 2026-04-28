# Phases 7-9: Dev CLI, Skill Docs, Security Hardening

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## Context
- Branch: feature/mvp4-maintenance-skills
- 655 tests passing (all structure tests passing)
- dev_cli.py has existing CLI command patterns
- skills/portfolio-maintenance/SKILL.md already exists (basic)
- tests/test_security.py already exists
- tests/test_maintenance_skills.py already exists

## Phase 7: Dev CLI Support

### Task 7.1: Add CLI parser entries
Update `dev_cli.py` to add CLI commands for all 8 maintenance tools:
- maintenance-skill-list
- maintenance-skill-explain (requires --skill-id)
- maintenance-skill-enable (requires --skill-id, optional --project-id, --interval-hours, --config-json)
- maintenance-skill-disable (requires --skill-id, optional --project-id)
- maintenance-due (optional --project-filter, --skill-filter)
- maintenance-run (optional --dry-run, --project-filter, --skill-filter, --create-issue-drafts, --refresh-github)
- maintenance-run-project (requires --project-ref, optional --dry-run, --create-issue-drafts)
- maintenance-report (optional --run-id, --severity, --limit)

Each CLI command calls the corresponding handler from maintenance_tools.py.

Tests in tests/test_maintenance_cli.py:
- test_cli_registers_maintenance_skill_list
- test_cli_registers_maintenance_run
- test_cli_registers_maintenance_report
- Plus 5 more for each tool

### Task 7.2: CLI behavior tests
Add tests that actually invoke CLI parser functions with a test root:
- test_cli_skill_list_returns_json
- test_cli_maintenance_due_returns_json
- test_cli_maintenance_run_dry_run
- test_cli_maintenance_report_empty

## Phase 8: Hermes Skill Documentation

### Task 8.1: Update skills/portfolio-maintenance/SKILL.md
Update the SKILL.md to include:
- Clear description of report-only default behavior
- Warning: no auto-fixes, no GitHub issue publishing
- List of all 8 maintenance tools with brief descriptions
- Guidance: use due before broad runs, prefer dry-run first

Tests in tests/test_maintenance_skills.py:
- test_portfolio_maintenance_skill_md_exists
- test_portfolio_maintenance_skill_mentions_report_only_default
- test_portfolio_maintenance_skill_warns_no_auto_fixes
- test_portfolio_maintenance_skill_lists_expected_tools

### Task 8.2: Add example phrases to SKILL.md
Add these example phrases to the skill doc:
- "List maintenance skills."
- "Explain stale issue checks."
- "Show checks due now."
- "Dry-run maintenance."
- "Run maintenance and report findings."
- "Show latest maintenance report."

Tests (add to test_maintenance_skills.py):
- test_skill_contains_example_phrases

## Phase 9: Security Hardening

### Task 9.1: Command allowlist tests
Add to tests/test_security.py:
- test_no_shell_true_in_maintenance_code
- test_only_allowed_gh_commands_in_maintenance_code
- test_no_gh_issue_create_in_maintenance_code
- test_no_gh_pr_mutation_in_maintenance_code
- test_no_gh_api_mutation_methods_in_maintenance_code

Implementation: scan maintenance*.py files for forbidden patterns.

### Task 9.2: Path containment tests
Add to tests/test_security.py:
- test_maintenance_config_path_contained
- test_maintenance_artifact_path_contained
- test_guidance_doc_rejects_dotdot
- test_guidance_doc_rejects_absolute_path
- test_guidance_doc_rejects_url_scheme
- test_guidance_doc_rejects_shell_metacharacters

Implementation: add validate_repo_relative_posix_path() to maintenance_artifacts.py if not present.

### Task 9.3: Privacy and redaction tests
Add to tests/test_security.py:
- test_error_artifact_redacts_tokens
- test_report_does_not_include_environment_variables
- test_maintenance_draft_excludes_private_metadata

Implementation: ensure maintenance_reports.py and maintenance_drafts.py redact properly.

## Rules
1. Write tests FIRST, confirm they fail, then implement
2. Run: uv run python -m pytest tests/ -x --tb=short -q
3. All 655 existing tests must stay passing
4. Follow existing patterns in dev_cli.py, test_security.py, test_maintenance_skills.py
