# Review Fix Plan

Fix all CRITICAL and WARNING issues from code review. Read-only review first, then fix.

## CRITICAL fixes

### C1: maintenance_orchestrator.py:198 — failed→success mapping
The line `result.status if result.status in ("success", "skipped", "blocked") else "success"` silently converts "failed" to "success". Fix: change to include "failed" as a valid status:
```python
status = result.status if result.status in ("success", "skipped", "blocked", "failed") else "error"
```

### C2: maintenance_config.py:69 — shallow copy of DEFAULT_CONFIG
`DEFAULT_CONFIG.copy()` shares nested dicts. Fix with `copy.deepcopy`:
```python
import copy
...
return copy.deepcopy(DEFAULT_CONFIG)
```

### C3: maintenance_reports.py:107 — path traversal in load_report
Validate run_id before constructing path:
```python
import re
...
if not re.match(r'^[a-zA-Z0-9_-]+$', run_id):
    return None
```

### C4: test_structure.py:48 — wrong filename
`maintenance_builtin.py` doesn't exist. Change to `skills/builtin/__init__.py`.

## WARNING fixes

### W1: maintenance_drafts.py:134 — private metadata stripping leaks values
Strip both key AND value. Change the approach to redact the full "key: value" pair.

### W2: maintenance_orchestrator.py:53-55 — empty LocalPaths
Create with a temp dir or use None with proper handling.

### W3: maintenance_orchestrator.py:83 — hardcoded needs_triage state
Use the actual GitHub issue state from the API response if available.

## After fixing
Run: `uv run python -m pytest tests/ -x --tb=short -q`
Then smoke test all CLI commands again.
