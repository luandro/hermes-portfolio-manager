# MVP 4 Phase 1: State, Schema, Config Foundations (1.1-1.5)

## Context

Portfolio manager plugin MVP 4: Maintenance Skills. Phase 0.3 structure tests already exist. 2 tests still failing (tools_registered, tool_schemas_exist). 5 stub modules exist with docstrings only.

Read these files FIRST:
- docs/mvps/mvp4-spec.md (lines 1-600 for Phase 1 context)
- portfolio_manager/state.py (existing SQLite schema)
- portfolio_manager/schemas.py (existing schema definitions)
- portfolio_manager/config.py (existing config loader patterns)
- portfolio_manager/__init__.py (existing tool registry)
- portfolio_manager/tools.py (existing tool handler patterns)
- portfolio_manager/errors.py (existing error patterns)
- tests/test_structure.py (existing structure tests that need to pass)
- tests/test_maintenance_config.py (placeholder test file)
- tests/test_maintenance_runs.py (placeholder test file)

## Tasks

### Task 1.1: Add SQLite schema for maintenance_runs and maintenance_findings

In `portfolio_manager/state.py`, add to `_SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS maintenance_runs (
    run_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary TEXT,
    reason TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS maintenance_findings (
    finding_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    body TEXT,
    source_type TEXT NOT NULL,
    source_id TEXT,
    source_url TEXT,
    metadata_json TEXT DEFAULT '{}',
    draftable INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES maintenance_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project ON maintenance_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_runs_skill ON maintenance_runs(skill_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_findings_run ON maintenance_findings(run_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_findings_fingerprint ON maintenance_findings(fingerprint);
```

Write test first in `tests/test_maintenance_runs.py`:
- Test that `state.init_db()` creates maintenance_runs and maintenance_findings tables
- Test inserting a run and querying it back
- Test inserting findings and querying by run_id

### Task 1.2: Add maintenance_state.py with helper functions

Create proper implementation in `portfolio_manager/maintenance_state.py`:

```python
"""State helpers for MVP 4 maintenance runs."""

from __future__ import annotations
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def start_run(conn: sqlite3.Connection, project_id: str, skill_id: str, now: datetime | None = None) -> str:
    """Create a new maintenance run row. Returns run_id."""
    run_id = uuid.uuid4().hex[:12]
    ts = (now or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        "INSERT INTO maintenance_runs (run_id, project_id, skill_id, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (run_id, project_id, skill_id, ts),
    )
    conn.commit()
    return run_id

def finish_run(conn: sqlite3.Connection, run_id: str, status: str, summary: str = "", reason: str | None = None) -> None:
    """Mark a maintenance run as finished."""
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE maintenance_runs SET status=?, finished_at=?, summary=?, reason=? WHERE run_id=?",
        (status, ts, summary, reason, run_id),
    )
    conn.commit()

def insert_finding(conn: sqlite3.Connection, run_id: str, fingerprint: str, severity: str, title: str, body: str = "", source_type: str = "", source_id: str | None = None, source_url: str | None = None, metadata: dict[str, Any] | None = None, draftable: bool = True) -> int:
    """Insert a maintenance finding. Returns finding_id."""
    import json
    meta_json = json.dumps(metadata or {})
    cur = conn.execute(
        "INSERT INTO maintenance_findings (run_id, fingerprint, severity, title, body, source_type, source_id, source_url, metadata_json, draftable) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (run_id, fingerprint, severity, title, body, source_type, source_id, source_url, meta_json, int(draftable)),
    )
    conn.commit()
    return cur.lastrowid

def get_findings_by_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    """Get all findings for a run."""
    cur = conn.execute("SELECT * FROM maintenance_findings WHERE run_id=?", (run_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]

def get_latest_successful_run(conn: sqlite3.Connection, project_id: str, skill_id: str) -> dict[str, Any] | None:
    """Get the latest successful run for a project+skill combo."""
    cur = conn.execute(
        "SELECT * FROM maintenance_runs WHERE project_id=? AND skill_id=? AND status='success' ORDER BY finished_at DESC LIMIT 1",
        (project_id, skill_id),
    )
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None

def recover_stale_runs(conn: sqlite3.Connection, max_age_hours: int = 2) -> list[str]:
    """Mark stale 'running' runs as 'failed'. Returns recovered run_ids."""
    cutoff = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "SELECT run_id FROM maintenance_runs WHERE status='running' AND started_at < datetime('now', ?)",
        (f"-{max_age_hours} hours",),
    )
    stale_ids = [row[0] for row in cur.fetchall()]
    for rid in stale_ids:
        conn.execute(
            "UPDATE maintenance_runs SET status='failed', finished_at=?, reason='stale recovery' WHERE run_id=?",
            (cutoff, rid),
        )
    conn.commit()
    return stale_ids
```

Write tests in `tests/test_maintenance_runs.py`:
- Test start_run creates a row with status='running'
- Test finish_run updates status and sets finished_at
- Test insert_finding and get_findings_by_run
- Test get_latest_successful_run returns None when no runs
- Test get_latest_successful_run returns run after successful finish
- Test recover_stale_runs marks old running runs as failed

### Task 1.3: Add stale-running-run recovery

Already covered by `recover_stale_runs` above. Just ensure the tests cover it.

### Task 1.4: Add maintenance_config.py loader

Create proper implementation in `portfolio_manager/maintenance_config.py`:

```python
"""Maintenance configuration loader for MVP 4."""

from __future__ import annotations
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml

DEFAULT_CONFIG = {
    "skills": {
        "untriaged_issue_digest": {
            "enabled": True,
            "interval_hours": 24,
            "min_age_hours": 24,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "stale_issue_digest": {
            "enabled": True,
            "interval_hours": 168,
            "stale_after_days": 30,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "open_pr_health": {
            "enabled": True,
            "interval_hours": 12,
            "stale_after_days": 7,
            "include_review_pending": True,
            "include_checks_failed": True,
            "include_changes_requested": True,
            "max_findings": 20,
            "create_issue_drafts": False,
        },
        "repo_guidance_docs": {
            "enabled": True,
            "interval_hours": 168,
            "doc_paths": ["CONTRIBUTING.md", "DEVELOPMENT.md", "ARCHITECTURE.md", "DESIGN.md"],
            "max_findings": 20,
            "create_issue_drafts": False,
        },
    },
}

def config_path(root: Path) -> Path:
    return root / "config" / "maintenance.yaml"

def backup_path(root: Path) -> Path:
    return root / "backups" / "maintenance"

def load_config(root: Path) -> dict[str, Any]:
    """Load maintenance config. Returns defaults if file doesn't exist."""
    cp = config_path(root)
    if cp.is_file():
        with open(cp) as f:
            data = yaml.safe_load(f)
        if data and isinstance(data, dict):
            return data
    return DEFAULT_CONFIG.copy()

def _atomic_backup(root: Path) -> Path | None:
    """Create a timestamped backup of maintenance.yaml."""
    cp = config_path(root)
    if not cp.is_file():
        return None
    bp = backup_path(root)
    bp.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = bp / f"maintenance-{ts}.yaml"
    shutil.copy2(cp, dest)
    return dest

def save_config(root: Path, config: dict[str, Any]) -> Path:
    """Atomic save with backup."""
    _atomic_backup(root)
    cp = config_path(root)
    cp.parent.mkdir(parents=True, exist_ok=True)
    tmp = cp.with_suffix(".tmp")
    with open(tmp, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    tmp.replace(cp)
    return cp

def get_skill_config(root: Path, skill_id: str) -> dict[str, Any]:
    """Get merged config for a specific skill (defaults + overrides)."""
    cfg = load_config(root)
    defaults = DEFAULT_CONFIG.get("skills", {}).get(skill_id, {})
    overrides = cfg.get("skills", {}).get(skill_id, {})
    merged = {**defaults, **overrides}
    return merged

def enable_skill(root: Path, skill_id: str, interval_hours: int | None = None) -> dict[str, Any]:
    """Enable a skill in config. Returns updated config."""
    cfg = load_config(root)
    skills = cfg.setdefault("skills", {})
    skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = True
    if interval_hours is not None:
        skill_cfg["interval_hours"] = interval_hours
    save_config(root, cfg)
    return cfg

def disable_skill(root: Path, skill_id: str) -> dict[str, Any]:
    """Disable a skill in config. Returns updated config."""
    cfg = load_config(root)
    skills = cfg.setdefault("skills", {})
    skill_cfg = skills.setdefault(skill_id, {})
    skill_cfg["enabled"] = False
    save_config(root, cfg)
    return cfg
```

Write tests in `tests/test_maintenance_config.py`:
- Test load_config returns defaults when no file exists
- Test save_config creates file and can be loaded back
- Test save_config creates backup
- Test get_skill_config merges defaults with overrides
- Test enable_skill and disable_skill modify config
- Test enable_skill with interval_hours

### Task 1.5: Add maintenance config mutation helpers

Already covered by enable_skill/disable_skill above.

## Verification

After ALL tasks:
1. Run: `uv run pytest tests/test_maintenance_runs.py tests/test_maintenance_config.py -v`
2. Run: `uv run pytest tests/ -q --tb=short` to confirm all existing tests still pass
3. Run: `uv run ruff check .` and `uv run ruff format --check .`
4. Run: `uv run bandit -c pyproject.toml -r .`
5. Report the test counts
