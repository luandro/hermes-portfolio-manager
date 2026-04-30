# Fix Plan: Artifacts, Fingerprint, Skill Flag (GAPs 3+4+5)

## GAP 3: Incomplete Artifact Files

### SPEC Requirements
Artifact layout per run:
```
$HOME/.agent-system/artifacts/maintenance/<run_id>/
  report.md          ← EXISTS but missing required sections
  findings.json      ← EXISTS but missing required fields
  metadata.json      ← EXISTS but missing required fields
  planned-checks.json ← MISSING
  github-refresh.json ← MISSING
  draft-created.json  ← MISSING
  error.json          ← MISSING
```

### SPEC required sections for report.md:
```
# Maintenance Report
Run ID
Started / finished
Selected projects
Selected skills
Summary
Findings by severity
Findings by project
Drafts created
Warnings
Errors
```

CURRENT report.md is missing: Started/finished, Selected projects, Selected skills, Drafts created, Warnings, Errors.

### SPEC required fields for findings.json:
```
fingerprint, project_id, skill_id, severity, status, title, body,
source_type, source_id, source_url, metadata, issue_draft_id
```

CURRENT findings.json just dumps the findings list. Need to ensure each finding dict includes `project_id`, `skill_id`, `status`, `issue_draft_id`.

### SPEC required fields for metadata.json:
```
run_id, root, started_at, finished_at, selected_project_ids,
selected_skill_ids, refresh_github, create_issue_drafts, dry_run
```

CURRENT metadata only has: run_id, project_id, skill_id, status, summary.

### New artifact files to create:

**planned-checks.json** — Written only for dry-runs or before a real run starts.
Fields: project_id, skill_id, due, reason, would_refresh_github, would_create_issue_drafts

**github-refresh.json** — Written when refresh_github=true.
Fields: project_id, issues_count, prs_count, warnings, error

**draft-created.json** — Written when local issue drafts are created.
Fields: finding_fingerprint, project_id, skill_id, draft_id, draft_artifact_path

**error.json** — Written when a run fails or a skill fails unexpectedly.
Fields: run_id, project_id, skill_id, error_type, message, redacted_trace_or_context

### Files to change:

**portfolio_manager/maintenance_reports.py:**
1. `write_maintenance_report` — Add all required sections to report.md
2. `write_findings_json` — Ensure each finding has all required fields (add project_id, skill_id, status, issue_draft_id if missing)
3. `write_metadata_json` — Ensure metadata has all required fields

**portfolio_manager/maintenance_reports.py** — Add new writer functions:
4. `write_planned_checks_json(root, run_id, planned_checks)` 
5. `write_github_refresh_json(root, run_id, project_id, issues_count, prs_count, warnings=None, error=None)`
6. `write_draft_created_json(root, run_id, entries)` — entries is list of dicts
7. `write_error_json(root, run_id, project_id, skill_id, error_type, message, trace=None)`

**portfolio_manager/maintenance_orchestrator.py:**
- Call `write_planned_checks_json` for dry-runs
- Call `write_github_refresh_json` when refresh_github=true (if/where GitHub refresh happens)
- Call `write_draft_created_json` after draft creation
- Call `write_error_json` on skill failure
- Pass richer metadata to `write_metadata_json` with all required fields

---

## GAP 4: Fingerprint Truncation

### SPEC Requirement
```
sha256(project_id + skill_id + source_type + source_id + normalized_title)
```

Normalization: lowercase, trim whitespace, collapse repeated whitespace, remove volatile timestamps.

### Current Issue
`maintenance_models.py` line 101: `return hashlib.sha256(raw.encode()).hexdigest()[:16]`
Returns only 16 hex chars. SPEC wants full SHA-256 hash (64 hex chars).

### Fix
**portfolio_manager/maintenance_models.py line 90-101:**

Change `make_finding_fingerprint` to:
1. Accept `project_id`, `skill_id`, `source_type`, `source_id`, `key` (already does)
2. Remove `[:16]` truncation — return full hexdigest
3. Add title normalization: lowercase, trim, collapse whitespace, remove volatile timestamps (ISO date patterns like `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}`)
4. Rename `key` param to `title` to match SPEC language (or keep `key` but document it's the normalized title)

```python
def make_finding_fingerprint(
    skill_id: str,
    project_id: str,
    source_type: str,
    source_id: str | None,
    key: str,
) -> str:
    """Produce a stable SHA-256 fingerprint for deduplication."""
    # Normalize the key (title): lowercase, trim, collapse whitespace, remove volatile timestamps
    normalized = key.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^ ]*", "", normalized)
    
    raw = json.dumps(
        [skill_id, project_id, source_type, source_id or "", normalized], 
        separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(raw.encode()).hexdigest()
```

Add `import re` at top of file.

### IMPORTANT: Update tests
Tests that check fingerprint length or exact values need updating. Search for `make_finding_fingerprint` in test files and update expected values.

---

## GAP 5: repo_guidance_docs supports_issue_drafts

### SPEC Requirement
```
repo_guidance_docs:
  Draft behavior: If issue drafts are requested, create one local draft per project recommending documentation updates.
```

### Current Issue
`portfolio_manager/skills/builtin/repo_guidance_docs.py` line ~27: `supports_issue_drafts=False`

### Fix
**portfolio_manager/skills/builtin/repo_guidance_docs.py:**
Change `supports_issue_drafts=False` to `supports_issue_drafts=True` in the SPEC dataclass.

## Verification
```bash
/home/luandro/.local/bin/ruff check --fix --unsafe-fixes portfolio_manager/maintenance_models.py portfolio_manager/maintenance_reports.py portfolio_manager/maintenance_orchestrator.py portfolio_manager/skills/builtin/repo_guidance_docs.py
/home/luandro/.local/bin/ruff format portfolio_manager/maintenance_models.py portfolio_manager/maintenance_reports.py portfolio_manager/maintenance_orchestrator.py portfolio_manager/skills/builtin/repo_guidance_docs.py
UV_CACHE_DIR=/tmp/uv-cache uv run python -m pytest tests/ -x --tb=short -q
```
All 710+ tests must pass.
