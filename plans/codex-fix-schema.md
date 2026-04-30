# Fix GAP 2+3+5: Schema, Indexes, State Helpers

## Context
You are fixing portfolio-manager MVP 4 to match docs/mvps/mvp4-spec.md. DO NOT read docs/mvps/mvp4-spec.md — all requirements are below.

Working directory: /home/luandro/Dev/hermes-multi-projects/portfolio-manager
Branch: feature/mvp4-maintenance-skills

## Task
Fix the DB schema, indexes, and state helpers in these files:
- `portfolio_manager/state.py` — DDL for maintenance_runs and maintenance_findings tables
- `portfolio_manager/maintenance_state.py` — state helper functions

## GAP 2: DB Schema Rewrite

### maintenance_runs — current (WRONG):
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
```

### maintenance_runs — REQUIRED by spec:
```sql
CREATE TABLE IF NOT EXISTS maintenance_runs (
  id TEXT PRIMARY KEY,
  skill_id TEXT NOT NULL,
  project_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  due INTEGER NOT NULL DEFAULT 1,
  dry_run INTEGER NOT NULL DEFAULT 0,
  refresh_github INTEGER NOT NULL DEFAULT 1,
  finding_count INTEGER NOT NULL DEFAULT 0,
  draft_count INTEGER NOT NULL DEFAULT 0,
  report_path TEXT,
  summary TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```

### maintenance_findings — current (WRONG):
```sql
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
  issue_draft_id TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (run_id) REFERENCES maintenance_runs(run_id),
  FOREIGN KEY (issue_draft_id) REFERENCES issue_drafts(draft_id) ON DELETE SET NULL
);
```

### maintenance_findings — REQUIRED by spec:
```sql
CREATE TABLE IF NOT EXISTS maintenance_findings (
  fingerprint TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  skill_id TEXT NOT NULL,
  severity TEXT NOT NULL,
  status TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  source_type TEXT,
  source_id TEXT,
  source_url TEXT,
  metadata_json TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  run_id TEXT,
  issue_draft_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY (run_id) REFERENCES maintenance_runs(id) ON DELETE SET NULL,
  FOREIGN KEY (issue_draft_id) REFERENCES issue_drafts(draft_id) ON DELETE SET NULL
);
```

## GAP 3: Required Indexes

Replace current indexes with:
```sql
CREATE INDEX IF NOT EXISTS idx_maintenance_runs_project_skill
ON maintenance_runs(project_id, skill_id, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_runs_status
ON maintenance_runs(status, finished_at);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_project_skill
ON maintenance_findings(project_id, skill_id, status);

CREATE INDEX IF NOT EXISTS idx_maintenance_findings_severity
ON maintenance_findings(severity, status);
```

## GAP 5: Required State Helpers

Add/update these functions in maintenance_state.py. All must validate statuses against allowed enums.

### Status enums
- Run statuses: planned, running, success, skipped, blocked, failed
- Finding statuses: open, resolved, draft_created, ignored

### Required functions:
```python
def start_maintenance_run(conn: sqlite3.Connection, run: dict[str, Any]) -> str:
    """Insert a new maintenance run. Returns the run id."""

def finish_maintenance_run(conn: sqlite3.Connection, run_id: str, status: str, summary: str | None, error: str | None) -> None:
    """Update run status, finished_at, summary, error. Validates status."""

def get_maintenance_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """Get a single run by id."""

def list_maintenance_runs(conn: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """List runs with optional filters: project_id, skill_id, status, limit."""

def upsert_maintenance_finding(conn: sqlite3.Connection, finding: dict[str, Any]) -> None:
    """Insert or update a finding by fingerprint. If fingerprint exists and status is open/draft_created,
    update last_seen_at, body, metadata, run_id. If new, insert with status=open."""

def get_maintenance_finding(conn: sqlite3.Connection, fingerprint: str) -> dict[str, Any] | None:
    """Get a single finding by fingerprint."""

def list_maintenance_findings(conn: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """List findings with optional filters: project_id, skill_id, status, severity, limit, include_resolved."""

def mark_resolved_missing_findings(conn: sqlite3.Connection, project_id: str, skill_id: str, seen_fingerprints: set[str], resolved_at: str) -> int:
    """Set status=resolved and resolved_at for findings NOT in seen_fingerprints for the given project/skill. Returns count."""
```

## CRITICAL: Update all callers
After changing schema and helpers, update ALL files that reference:
- `run_id` column → now `id` (but keep variable names as `run_id` in Python code, just the SQL column is `id`)
- `finding_id` → removed, fingerprint is PK now
- Old helper function names → new names
- Old column names → new columns

Files that likely need updates:
- `portfolio_manager/maintenance_orchestrator.py`
- `portfolio_manager/maintenance_tools.py`
- `portfolio_manager/maintenance_reports.py`
- `portfolio_manager/maintenance_due.py`
- `portfolio_manager/maintenance_drafts.py`
- `portfolio_manager/maintenance_planner.py`
- All test files in `tests/test_maintenance_*.py`

## Verification
After all changes, run:
```bash
cd /home/luandro/Dev/hermes-multi-projects/portfolio-manager
/home/luandro/.local/bin/ruff check --fix --unsafe-fixes portfolio_manager/maintenance_state.py portfolio_manager/state.py
/home/luandro/.local/bin/ruff format portfolio_manager/maintenance_state.py portfolio_manager/state.py
uv run python -m pytest tests/ -x --tb=short -q
```

All 690+ tests must pass. Fix any test failures caused by schema changes.
