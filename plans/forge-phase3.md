# Phase 3: Artifact Safety and Report Generation

## Working directory
/home/luandro/Dev/hermes-multi-projects/portfolio-manager

## Context
- Branch: feature/mvp4-maintenance-skills
- 563 tests currently passing
- Existing modules: maintenance_models.py, maintenance_registry.py, maintenance_state.py, maintenance_config.py
- Skills in portfolio_manager/skills/builtin/ (5 skills + __init__.py)

## Tasks

### Task 3.1: Maintenance artifact path helpers
Create `portfolio_manager/maintenance_artifacts.py`:
- Artifact directory: `$RUNTIME_ROOT/artifacts/maintenance/<run_id>/`
- Functions:
  - `get_artifact_dir(root, run_id) -> Path` — returns resolved artifact dir, rejects path traversal
  - `ensure_artifact_dir(root, run_id) -> Path` — creates dir if needed
  - `redact_secrets(text: str) -> str` — redacts common secret patterns (tokens, keys, passwords)
  - `write_artifact(root, run_id, filename, content)` — writes redacted content to artifact dir
- Path traversal protection: ensure resolved path is under root/artifacts/maintenance/
- Secret redaction: match patterns like gh*_*, github_pat_*, sk-*, password=*, token=*

Tests in `tests/test_maintenance_artifacts.py`:
- test_maintenance_artifact_dir_under_root
- test_run_id_path_traversal_rejected (e.g. run_id="../../../etc/passwd")
- test_artifact_paths_created_for_run_id
- test_artifact_write_redacts_secrets
- test_redact_secrets_various_patterns

### Task 3.2: Report writers
Create `portfolio_manager/maintenance_reports.py`:
- Functions:
  - `write_maintenance_report(root, run_id, findings, metadata) -> Path` — writes report.md
  - `write_findings_json(root, run_id, findings) -> Path` — writes findings.json
  - `write_metadata_json(root, run_id, metadata) -> Path` — writes metadata.json
- report.md sections: header with run_id/timestamp, summary (counts by severity), findings list
- findings.json: list of MaintenanceFinding dicts
- metadata.json: run metadata (project_ids, skill_ids, started_at, completed_at, config snapshot)
- All writes go through maintenance_artifacts.write_artifact (path safety + redaction)

Tests in `tests/test_maintenance_reports.py`:
- test_report_md_contains_required_sections (header, summary, findings)
- test_findings_json_contains_required_fields (valid JSON, list of findings)
- test_metadata_json_contains_selected_projects_and_skills
- test_artifact_json_is_valid_and_stable (deterministic output)
- test_report_with_no_findings
- test_report_with_mixed_severity_findings

### Task 3.3: Load latest report
Add to `maintenance_reports.py`:
- `load_latest_report(root) -> dict | None` — reads most recent report
- `list_report_runs(root) -> list[str]` — lists run_ids with reports
- `load_report(root, run_id) -> dict | None` — loads specific report

Tests (add to test_maintenance_reports.py):
- test_list_report_runs_empty
- test_list_report_runs_multiple
- test_load_latest_report
- test_load_report_not_found_returns_none

## Rules
1. Write tests FIRST, run them to confirm they FAIL, then implement
2. Run: uv run pytest tests/ --ignore=tests/test_structure.py -x --tb=short -q
3. All 563 existing tests must stay passing
4. Use Path from pathlib, not os.path
5. Follow existing code patterns (check existing modules)
