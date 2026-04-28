# CI Fix Plan

3 CI failures on PR #4. Fix all.

## Fix 1: test_maintenance_cli.py imports dev_cli
The test file imports `dev_cli` as a module but dev_cli.py is in project root (not a package). CI runs pytest from project root and can't import it.

Fix: Change test_maintenance_cli.py to use subprocess to invoke dev_cli.py instead of importing it. Or use `importlib` / `sys.path.insert`. Simplest: add `sys.path.insert(0, str(Path(__file__).resolve().parent))` at top of test file before importing dev_cli.

Read tests/test_maintenance_cli.py to understand current imports, then fix.

## Fix 2: Bandit B608 SQL injection in maintenance_due.py:42
```python
cur = conn.execute(f"SELECT id, status FROM projects WHERE {where}", params)
```
The `where` is built from hardcoded strings, not user input. But Bandit flags it. Fix: add `# nosec B608` comment on that line (matching the pattern used in state.py:573).

## Fix 3: GitGuardian false positives
GitGuardian uses its own config, not .gitleaks.toml. Create a `.gitguardian.yml` file at project root:
```yaml
version: 2
matches:
  - name: Test secret strings
    id: gg-test-secrets
    paths:
      - "tests/test_maintenance_artifacts.py"
```
OR simpler: add `# ggignore` comments on the lines with test secrets in test_maintenance_artifacts.py.

## After fixes:
Run: uv run python -m pytest tests/ -x --tb=short -q
All 690 tests must pass.
