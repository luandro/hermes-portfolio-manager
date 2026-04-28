# Code Review: MVP 4 Maintenance Skills

Perform a thorough code review of all new/modified files in the MVP 4 maintenance skills implementation. This is a read-only review — do NOT modify any files.

## Files to review (group by area):

### Core modules
- portfolio_manager/maintenance_state.py
- portfolio_manager/maintenance_config.py
- portfolio_manager/maintenance_models.py
- portfolio_manager/maintenance_registry.py
- portfolio_manager/maintenance_artifacts.py
- portfolio_manager/maintenance_reports.py
- portfolio_manager/maintenance_due.py
- portfolio_manager/maintenance_planner.py
- portfolio_manager/maintenance_orchestrator.py
- portfolio_manager/maintenance_drafts.py
- portfolio_manager/maintenance_tools.py

### Built-in skills
- portfolio_manager/skills/builtin/__init__.py
- portfolio_manager/skills/builtin/health_check.py
- portfolio_manager/skills/builtin/dependency_audit.py
- portfolio_manager/skills/builtin/license_compliance.py
- portfolio_manager/skills/builtin/security_advisory.py
- portfolio_manager/skills/builtin/stale_branches.py

### Modified existing files
- portfolio_manager/state.py (maintenance_runs + maintenance_findings tables added)
- portfolio_manager/schemas.py (8 new tool schemas)
- portfolio_manager/__init__.py (8 new tool registrations)
- dev_cli.py (8 new CLI commands + --skill-id arg)

### Tests
- tests/test_maintenance_models.py
- tests/test_maintenance_registry.py
- tests/test_maintenance_skills.py
- tests/test_maintenance_reports.py
- tests/test_maintenance_due.py
- tests/test_maintenance_planner.py
- tests/test_maintenance_orchestrator.py
- tests/test_maintenance_drafts.py
- tests/test_maintenance_tools.py
- tests/test_maintenance_runs.py
- tests/test_maintenance_config.py
- tests/test_maintenance_artifacts.py
- tests/test_maintenance_e2e.py
- tests/test_maintenance_cli.py
- tests/test_security.py
- tests/test_structure.py

## Review criteria

For each file, check:
1. **Correctness** — Logic errors, off-by-one, missing edge cases, wrong types
2. **Security** — SQL injection, path traversal, secret leaks, missing validation
3. **Error handling** — Missing try/except, swallowed exceptions, bad error messages
4. **API consistency** — Do tool handlers match schemas? Do return shapes match _result/_blocked/_failed patterns from tools.py?
5. **Type safety** — Missing type annotations, Any where specific types needed, Optional not checked
6. **Imports** — Unused imports, circular import risks, TYPE_CHECKING guard correctness
7. **Test coverage** — Missing test cases for error paths, edge cases, boundary conditions
8. **Documentation** — Missing docstrings, unclear function purposes
9. **Naming** — Inconsistent naming, unclear variable names
10. **Dead code** — Unused functions, unreachable branches, TODO/FIXME comments

## Output format

Produce a structured review with:
- **CRITICAL** — Must fix before merge (bugs, security, crashes)
- **HIGH** — Should fix (missing error handling, type issues)
- **MEDIUM** — Nice to fix (naming, docs, style)
- **LOW** — Optional (minor suggestions)

For each issue, provide: file, line number (approximate), description, suggested fix.
