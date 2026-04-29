# Spec Divergence Assessment Request

You are reviewing PR #4 for the portfolio-manager MVP 4 maintenance skills system.

The implementation intentionally diverges from SPEC_4.md in several places. Some divergences are improvements over the spec; others are bugs. Your job is to judge EACH divergence and classify it.

## Divergences to evaluate

### DIV-1: Schema param names
SPEC says tool schemas should use singular `project_id` and `skill_id`.
Implementation uses CSV-based `project_filter` and `skill_filter`.

Question: Is the CSV approach a valid improvement over the spec's singular approach? The CSV filters allow multiple projects/skills in one call. Or does the spec's singular approach have advantages (simpler API, clearer semantics)?

### DIV-2: CLI→handler arg name disconnect
CLI parses `--skill-id` into `args["skill_id"]` and `--project-id` into `args["project_id"]`.
But handlers read `args.get("skill_filter")` and `args.get("project_filter")`.

Question: Is this a real bug? When CLI sends `skill_id`, the handler reads `skill_filter` which doesn't exist — so the filter is silently ignored. Does this actually break anything or does the handler gracefully handle None?

### DIV-3: Missing artifact files
SPEC requires these artifact files per run: `planned-checks.json`, `github-refresh.json`, `draft-created.json`, `error.json`.
Implementation only writes: `report.md`, `findings.json`, `metadata.json`.

Question: Are the missing artifact files critical for MVP? Or are they observability nice-to-haves that can be added in a follow-up? The core functionality (runs, findings, reports) works without them.

### DIV-4: Fingerprint truncation
SPEC says: `sha256(project_id + skill_id + source_type + source_id + normalized_title)` — full SHA-256 hex (64 chars).
Implementation: `hashlib.sha256(raw.encode()).hexdigest()[:16]` — truncated to 16 hex chars (64 bits).

Question: Is truncation to 16 hex chars acceptable for local SQLite dedup? 64 bits of entropy means collision probability is negligible for typical portfolios (tens of projects, hundreds of findings). Or does the spec require full hash for a specific reason (e.g., future cross-system dedup)?

### DIV-5: repo_guidance_docs supports_issue_drafts
SPEC says: repo_guidance_docs can create one local draft per project when drafts are requested.
Implementation: `supports_issue_drafts=False` in the skill spec.

Question: Is this a meaningful divergence? Draft creation is opt-in anyway (create_issue_drafts defaults to false). Having supports_issue_drafts=False just means the feature is permanently disabled for this skill, even when explicitly requested.

## Instructions

1. Read SPEC_4.md fully to understand the intent behind each requirement.
2. Read the actual implementation files to understand how each divergence manifests.
3. For each divergence, classify as:
   - FIX: Real bug or meaningful gap that should be fixed before merge
   - ACCEPT: Implementation is equal or better than spec — no change needed
   - DEFER: Nice-to-have but not blocking for merge
4. Produce a final verdict: APPROVE (no FIX items), NEEDS_WORK (has FIX items), or REJECT.
5. Be pragmatic. Don't be a spec literalist. Judge by engineering quality.
