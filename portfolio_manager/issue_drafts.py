"""Issue draft creation, state management, readiness scoring — MVP 3.

Deterministic draft generation and validation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

from portfolio_manager.config import load_projects_config
from portfolio_manager.issue_artifacts import (
    generate_draft_id,
    issue_artifact_root,
    read_github_created_if_exists,
    write_issue_artifact_files,
)
from portfolio_manager.issue_resolver import resolve_project
from portfolio_manager.state import (
    _utcnow,
    get_issue_draft,
    list_issue_drafts,
    upsert_issue_draft,
)

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def validate_input_length(text: str, max_chars: int, field_name: str) -> None:
    """Raise ValueError if *text* exceeds *max_chars*."""
    if len(text) > max_chars:
        msg = f"{field_name} too long: {len(text)} characters (max {max_chars})"
        raise ValueError(msg)


def validate_issue_title(title: str) -> None:
    """Validate an issue title: 5-120 chars, no newlines, no leading #."""
    if len(title) < 5 or len(title) > 120:
        raise ValueError(f"Title must be 5-120 characters, got {len(title)}")
    if "\n" in title:
        raise ValueError("Title must not contain newlines")
    if title.startswith("#"):
        raise ValueError("Title must not start with '#'")


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------


def generate_issue_title(text: str) -> str:
    """Derive a title from user-supplied text (first sentence, cleaned up)."""
    # For very short text, return as-is (if valid length)
    if len(text) <= 120:
        candidate = text.strip()
        if len(candidate) >= 5:
            return candidate

    # Take first sentence (up to period, question mark, or exclamation)
    sentence_end = re.search(r"[.!?]", text)
    candidate = text[: sentence_end.start()].strip() if sentence_end else text.strip()

    # Truncate to 120 chars if needed
    if len(candidate) > 120:
        candidate = candidate[:120].strip()

    return candidate


# ---------------------------------------------------------------------------
# Issue classification
# ---------------------------------------------------------------------------

_BUG_KEYWORDS = ("bug", "error", "fails", "broken", "crash", "not working", "regression")
_FEATURE_KEYWORDS = ("feature", "users should", "add support", "allow", "export", "import")


def classify_issue_kind(text: str) -> str:
    """Classify text as 'bug', 'feature', or 'unknown' based on keywords."""
    lower = text.lower()
    for kw in _BUG_KEYWORDS:
        if kw in lower:
            return "bug"
    for kw in _FEATURE_KEYWORDS:
        if kw in lower:
            return "feature"
    return "unknown"


# ---------------------------------------------------------------------------
# Readiness scoring
# ---------------------------------------------------------------------------


def compute_readiness(content: dict[str, Any]) -> float:
    """Compute a 0.0-1.0 readiness score for an issue draft.

    Deterministic heuristic based on content signals.
    """
    score = 0.0

    # +0.25 if non-empty title
    if content.get("title"):
        score += 0.25

    # +0.20 if non-empty project_id
    if content.get("project_id"):
        score += 0.20

    text = content.get("text", "")

    # +0.20 if text mentions expected behavior keywords
    expectation_keywords = ("should", "need", "would")
    if any(kw in text.lower() for kw in expectation_keywords):
        score += 0.20

    # +0.15 if acceptance criteria can be derived (goal-like text)
    goal_keywords = ("goal", "objective", "acceptance criteria", "so that", "in order to")
    if any(kw in text.lower() for kw in goal_keywords):
        score += 0.15

    # +0.10 if scope seems small (short text, single topic)
    if len(text) > 0 and len(text) < 200:
        score += 0.10

    # -0.20 if vague (few keywords, short text)
    word_count = len(text.split())
    if word_count < 8:
        score -= 0.20

    # -0.15 if mentions many separate features
    feature_count = 0
    feature_markers = (" and ", ", ", " also ", " plus ", "; ")
    for marker in feature_markers:
        feature_count += text.lower().count(marker)
    if feature_count >= 4:
        score -= 0.15

    # Clamp to 0.0-1.0
    return max(0.0, min(1.0, score))


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------


def generate_questions(text: str, kind: str) -> list[str]:
    """Generate clarifying questions based on issue kind."""
    if kind == "bug":
        return [
            "What are the steps to reproduce the issue?",
            "What is the expected behavior?",
        ]
    return [
        "Who is the target user for this feature?",
        "What platform(s) should this support?",
        "What is the scope of this request?",
    ]


# ---------------------------------------------------------------------------
# Spec body generation
# ---------------------------------------------------------------------------


def generate_spec_body(text: str, kind: str) -> str:
    """Generate a structured spec body from raw text."""
    if kind == "bug":
        return f"## Problem\n{text}\n\n## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior\n"
    if kind == "feature":
        return f"## Goal\n{text}\n\n## Context\n"
    return text


# ---------------------------------------------------------------------------
# GitHub issue body generation
# ---------------------------------------------------------------------------


def generate_github_issue_body(content: dict[str, Any]) -> str:
    """Build a public-facing GitHub issue body from draft content.

    Includes Goal and Acceptance Criteria sections.
    Excludes private metadata (readiness, internal notes, etc.).
    """
    parts: list[str] = []

    spec_body = content.get("spec_body", "")
    if spec_body:
        parts.append(spec_body)

    # Ensure Acceptance Criteria section exists
    if "## Acceptance Criteria" not in spec_body:
        parts.append("## Acceptance Criteria\n")

    # Ensure Goal section exists
    if "## Goal" not in spec_body:
        goal = content.get("title", "")
        if goal:
            parts.insert(0, f"## Goal\n{goal}\n")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Public body validation & sanitization
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS = (
    "<script",
    "</script>",
    "<style",
    "</style>",
    "onclick=",
    "onload=",
)

_PRIVATE_MARKERS = (
    "internal_notes",
    "private_metadata",
    "<!-- private",
    '"readiness":',
)


def validate_public_issue_body(body: str) -> None:
    """Reject bodies with dangerous HTML or private metadata."""
    lower = body.lower()

    for pattern in _DANGEROUS_PATTERNS:
        if pattern in lower:
            raise ValueError(f"Body contains forbidden HTML: {pattern}")

    if len(body) > 20000:
        raise ValueError(f"Body exceeds 20000 characters ({len(body)})")

    for marker in _PRIVATE_MARKERS:
        if marker in lower:
            raise ValueError(f"Body contains private metadata marker: {marker}")


def sanitize_public_issue_body(body: str) -> str:
    """Strip dangerous HTML tags and normalize blank lines."""
    # Remove <script>...</script>
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.IGNORECASE | re.DOTALL)
    # Remove <style>...</style>
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.IGNORECASE | re.DOTALL)
    # Normalize excessive blank lines (max 2 consecutive newlines)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


# ---------------------------------------------------------------------------
# Large feature detection
# ---------------------------------------------------------------------------


def detect_large_feature(text: str) -> bool:
    """Return True if text mentions 4+ distinct features or systems."""
    lower = text.lower()
    # Count distinct feature/system mentions
    feature_indicators = (
        "feature",
        "system",
        "module",
        "component",
        "integration",
        "service",
        "api",
        "dashboard",
        "notification",
        "export",
        "import",
        "sync",
        "auth",
        "payment",
        "search",
        "report",
    )
    count = sum(1 for indicator in feature_indicators if indicator in lower)
    return count >= 4


# ---------------------------------------------------------------------------
# Draft state computation
# ---------------------------------------------------------------------------


def compute_draft_state(content: dict[str, Any], *, force_rough_issue: bool = False) -> str:
    """Determine draft state based on readiness and project resolution.

    If content has ambiguous_project=True -> 'needs_project_confirmation'
    If content has no project_id -> 'needs_project_confirmation'
    If readiness >= 0.75 -> 'ready_for_creation'
    If 0.5 <= readiness < 0.75 and force_rough_issue -> 'ready_for_creation'
    Otherwise -> 'needs_user_questions'
    """
    if content.get("ambiguous_project"):
        return "needs_project_confirmation"
    if not content.get("project_id"):
        return "needs_project_confirmation"
    readiness = content.get("readiness", 0.0)
    if readiness >= 0.75:
        return "ready_for_creation"
    if 0.5 <= readiness < 0.75 and force_rough_issue:
        return "ready_for_creation"
    return "needs_user_questions"


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------


def normalize_title(title: str) -> str:
    """Normalize title: lowercase, strip, collapse whitespace, remove punctuation."""
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

_TERMINAL_STATES = frozenset({"created", "discarded", "blocked"})


def find_duplicate_draft(conn: sqlite3.Connection, project_id: str, title: str) -> str | None:
    """Check existing non-terminal drafts for same project + normalized title.

    Terminal states: created, discarded, blocked.
    Returns draft_id if duplicate found, None otherwise.
    """
    norm = normalize_title(title)
    drafts = list_issue_drafts(conn, project_id=project_id, include_created=True)
    for draft in drafts:
        if draft["state"] in _TERMINAL_STATES:
            continue
        if draft.get("title") and normalize_title(draft["title"]) == norm:
            draft_id: str | None = draft["draft_id"]
            return draft_id
    return None


# ---------------------------------------------------------------------------
# Helper: ensure project row exists for FK
# ---------------------------------------------------------------------------


def _ensure_project_row(conn: sqlite3.Connection, config: Any, project_id: str) -> None:
    """Insert a minimal project row if it doesn't exist (satisfies FK)."""
    # Try to get the real repo URL from config
    repo_url = f"https://github.com/test/{project_id}"
    project_name = project_id
    for p in getattr(config, "projects", []):
        if p.id == project_id:
            repo_url = p.repo
            project_name = p.name
            break
    now = _utcnow()
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', 'active', ?, ?)",
        (project_id, project_name, repo_url, now, now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Draft creation
# ---------------------------------------------------------------------------


def create_issue_draft(
    root: Path,
    conn: sqlite3.Connection,
    text: str,
    *,
    project_ref: str | None = None,
    title: str | None = None,
    force_rough_issue: bool = False,
) -> dict[str, Any]:
    """Create a new issue draft.

    1. Validate input length
    2. Determine project via resolve_project or project_ref
    3. Generate draft_id, title, kind, spec_body, questions
    4. Check for duplicate drafts
    5. Write artifact files
    6. Upsert to state DB
    7. Return result dict
    """
    validate_input_length(text, 20000, "text")

    # Resolve project
    config = load_projects_config(root)
    resolution = resolve_project(config, project_ref=project_ref, text=text)

    if resolution.state == "not_found":
        return {"blocked": True, "state": "blocked", "reason": resolution.message}

    # For ambiguous: still create a draft so user can confirm project later
    if resolution.state == "ambiguous":
        project_id = None
        draft_id = generate_draft_id()
        final_title = title or generate_issue_title(text)
        kind = classify_issue_kind(text)
        spec_body = generate_spec_body(text, kind)
        questions_list = generate_questions(text, kind)
        questions_text = "\n".join(f"- {q}" for q in questions_list)
        github_body = generate_github_issue_body({"title": final_title, "spec_body": spec_body})

        # Use a placeholder project for artifact storage
        placeholder_project = "unresolved"
        artifact_content = {
            "original_input": text,
            "title": final_title,
            "project_id": placeholder_project,
            "issue_kind": kind,
            "readiness": 0.0,
            "spec_body": spec_body,
            "github_body": github_body,
            "questions": questions_text,
            "brainstorm_notes": "",
        }
        write_issue_artifact_files(root, placeholder_project, draft_id, artifact_content)

        artifact_path = f"artifacts/issues/{placeholder_project}/{draft_id}"
        upsert_issue_draft(
            conn,
            {
                "draft_id": draft_id,
                "project_id": None,
                "state": "needs_project_confirmation",
                "title": final_title,
                "readiness": 0.0,
                "artifact_path": artifact_path,
            },
        )

        return {
            "draft_id": draft_id,
            "state": "needs_project_confirmation",
            "candidates": resolution.candidates,
            "message": resolution.message,
            "title": final_title,
            "readiness": 0.0,
            "questions": questions_list,
            "kind": kind,
        }

    # Resolved — project_id should be set
    if resolution.project_id is None:
        return {"blocked": True, "state": "blocked", "reason": "resolution_failed"}
    project_id = resolution.project_id
    _ensure_project_row(conn, config, project_id)
    draft_id = generate_draft_id()

    # Generate title
    final_title = title if title else generate_issue_title(text)

    # Classify and generate content
    kind = classify_issue_kind(text)
    spec_body = generate_spec_body(text, kind)
    questions_list = generate_questions(text, kind)
    questions_text = "\n".join(f"- {q}" for q in questions_list)
    github_body = generate_github_issue_body({"title": final_title, "spec_body": spec_body})

    # Check for duplicates
    dup = find_duplicate_draft(conn, project_id, final_title)
    if dup:
        return {
            "blocked": True,
            "reason": "duplicate",
            "duplicate_of": dup,
            "state": "blocked",
        }

    # Compute readiness and state
    content: dict[str, Any] = {
        "title": final_title,
        "project_id": project_id,
        "text": text,
    }
    readiness = compute_readiness(content)
    content["readiness"] = readiness
    state = compute_draft_state(content, force_rough_issue=force_rough_issue)

    # Write artifacts
    artifact_content = {
        "original_input": text,
        "title": final_title,
        "project_id": project_id,
        "issue_kind": kind,
        "readiness": readiness,
        "spec_body": spec_body,
        "github_body": github_body,
        "questions": questions_text,
        "brainstorm_notes": "",
    }
    write_issue_artifact_files(root, project_id, draft_id, artifact_content)

    # Upsert to DB
    artifact_path = f"artifacts/issues/{project_id}/{draft_id}"
    upsert_issue_draft(
        conn,
        {
            "draft_id": draft_id,
            "project_id": project_id,
            "state": state,
            "title": final_title,
            "readiness": readiness,
            "artifact_path": artifact_path,
        },
    )

    return {
        "draft_id": draft_id,
        "project_id": project_id,
        "state": state,
        "title": final_title,
        "readiness": readiness,
        "questions": questions_list,
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# Draft update
# ---------------------------------------------------------------------------


def update_issue_draft(
    root: Path,
    conn: sqlite3.Connection,
    draft_id: str,
    *,
    answers: str | None = None,
    project_id: str | None = None,
    title: str | None = None,
    force_ready: bool = False,
) -> dict[str, Any]:
    """Update an existing issue draft.

    1. Get existing draft
    2. Validate state is mutable (not terminal)
    3. If creating_failed, allow edit if no github-created.json
    4. Update content with answers/project_id/title
    5. Regenerate spec, questions, readiness
    6. Write updated artifact files
    7. Upsert updated state
    8. Return result
    """
    row = get_issue_draft(conn, draft_id)
    if row is None:
        return {"blocked": True, "reason": "not_found"}

    current_state = row["state"]
    current_project_id = row.get("project_id")
    current_title = row.get("title", "")

    # Terminal state check
    if current_state in _TERMINAL_STATES:
        return {
            "blocked": True,
            "reason": f"terminal_state:{current_state}",
        }

    # creating_failed: allow retry only if no github-created.json
    if current_state == "creating_failed" and current_project_id:
        artifact_dir = issue_artifact_root(root, current_project_id, draft_id)
        if read_github_created_if_exists(artifact_dir) is not None:
            return {
                "blocked": True,
                "reason": "terminal_state:creating_failed with github-created.json",
            }

    # Resolve effective project_id
    effective_project_id = project_id or current_project_id
    if not effective_project_id:
        return {"blocked": True, "reason": "no_project_id"}

    # Ensure project row exists for FK
    config = load_projects_config(root)
    _ensure_project_row(conn, config, effective_project_id)

    # Build updated content
    # Read original input from artifact — may be under "unresolved" if ambiguous
    from portfolio_manager.issue_artifacts import read_issue_artifact

    artifact_read_project = current_project_id if current_project_id else "unresolved"
    original_input = read_issue_artifact(root, artifact_read_project, draft_id, "original-input.md") or ""
    combined_text = original_input
    if answers:
        combined_text = f"{original_input}\n\n## Answers\n{answers}" if original_input else answers

    effective_title = title or current_title

    # Regenerate
    kind = classify_issue_kind(combined_text)
    spec_body = generate_spec_body(combined_text, kind)
    questions_list = generate_questions(combined_text, kind)
    questions_text = "\n".join(f"- {q}" for q in questions_list)
    github_body = generate_github_issue_body({"title": effective_title, "spec_body": spec_body})

    content = {
        "title": effective_title,
        "project_id": effective_project_id,
        "text": combined_text,
    }
    readiness = compute_readiness(content)

    # Determine state
    if force_ready:
        state = "ready_for_creation"
    else:
        content["readiness"] = readiness
        state = compute_draft_state(content)

    # Write updated artifacts
    artifact_content = {
        "original_input": original_input,
        "title": effective_title,
        "project_id": effective_project_id,
        "issue_kind": kind,
        "readiness": readiness,
        "spec_body": spec_body,
        "github_body": github_body,
        "questions": questions_text,
        "brainstorm_notes": "",
    }
    write_issue_artifact_files(root, effective_project_id, draft_id, artifact_content)

    # Upsert
    artifact_path = f"artifacts/issues/{effective_project_id}/{draft_id}"
    upsert_issue_draft(
        conn,
        {
            "draft_id": draft_id,
            "project_id": effective_project_id,
            "state": state,
            "title": effective_title,
            "readiness": readiness,
            "artifact_path": artifact_path,
        },
    )

    return {
        "draft_id": draft_id,
        "project_id": effective_project_id,
        "state": state,
        "title": effective_title,
        "readiness": readiness,
        "questions": questions_list,
        "kind": kind,
    }


# ---------------------------------------------------------------------------
# Create issue from draft (Phase 6+7)
# ---------------------------------------------------------------------------


def create_issue_from_draft(
    root: Path,
    conn: sqlite3.Connection,
    draft_id: str,
    *,
    confirm: bool = False,
    allow_open_questions: bool = False,
    allow_possible_duplicate: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a GitHub issue from an existing draft.

    Steps:
    1. Get draft from DB
    2. Check github-created.json exists -> idempotent recovery
    3. Validate state
    4. Require confirm (unless dry_run)
    5. Load config, get project owner/repo
    6. Dry-run returns preview without mutation
    7. Acquire project-level lock
    8. Write creation-attempt.json
    9. Duplicate GitHub issue check
    10. Call create_github_issue
    11. On success: write github-created.json, update metadata, upsert state, release lock
    12. On failure: write creation-error.json, set state creating_failed
    """
    from portfolio_manager.errors import redact_secrets
    from portfolio_manager.issue_artifacts import (
        issue_artifact_root,
        read_github_created_if_exists,
        read_issue_metadata,
        write_creation_attempt,
        write_creation_error,
        write_github_created,
        write_issue_artifact_files,
    )
    from portfolio_manager.issue_github import (
        create_github_issue,
        find_duplicate_github_issue,
    )
    from portfolio_manager.state import acquire_lock, release_lock, upsert_issue_draft

    # 1. Get draft from DB
    row = get_issue_draft(conn, draft_id)
    if row is None:
        return {"blocked": True, "reason": "not_found"}

    project_id = row.get("project_id")
    title = row.get("title", "")

    if not project_id:
        return {"blocked": True, "reason": "no_project_id"}

    artifact_dir = issue_artifact_root(root, project_id, draft_id)

    # 2. Check github-created.json -> idempotent recovery
    existing = read_github_created_if_exists(artifact_dir)
    if existing is not None:
        issue_number_rec: object = existing.get("issue_number")
        issue_url_rec: object = existing.get("issue_url")
        # Ensure DB is in sync
        upsert_issue_draft(
            conn,
            {
                "draft_id": draft_id,
                "project_id": project_id,
                "state": "created",
                "title": title,
                "readiness": row.get("readiness"),
                "artifact_path": row.get("artifact_path", ""),
                "github_issue_number": issue_number_rec,
                "github_issue_url": issue_url_rec,
            },
        )
        return {
            "draft_id": draft_id,
            "state": "created",
            "issue_number": issue_number_rec,
            "issue_url": issue_url_rec,
            "recovered": True,
        }

    # 3. Validate state
    current_state = row["state"]
    allowed_states = {"ready_for_creation", "creating_failed"}
    if allow_open_questions:
        allowed_states.add("needs_user_questions")
    if current_state not in allowed_states:
        return {
            "blocked": True,
            "reason": f"invalid_state:{current_state}",
        }

    # 4. Require confirm (unless dry_run)
    if not confirm and not dry_run:
        return {
            "blocked": True,
            "reason": "confirm_required",
            "title": title,
            "project_id": project_id,
        }

    # 5. Load config, get project owner/repo
    config = load_projects_config(root)
    project = None
    for p in config.projects:
        if p.id == project_id:
            project = p
            break
    if project is None:
        return {"blocked": True, "reason": f"project_not_found:{project_id}"}

    owner = project.github.owner
    repo = project.github.repo

    # Read github body from artifacts
    from portfolio_manager.issue_artifacts import read_issue_artifact

    github_body = read_issue_artifact(root, project_id, draft_id, "github-issue.md") or ""
    metadata = read_issue_metadata(root, project_id, draft_id) or {}

    # 6. Dry-run returns preview without mutation
    if dry_run:
        return {
            "draft_id": draft_id,
            "dry_run": True,
            "title": title,
            "project_id": project_id,
            "owner": owner,
            "repo": repo,
            "body_length": len(github_body),
            "state": current_state,
        }

    # 7. Acquire project-level lock
    lock_name = f"github_issue_create:{project_id}"
    lock_owner = f"draft:{draft_id}"
    lock_result = acquire_lock(conn, lock_name, lock_owner, ttl_seconds=120)
    if not lock_result.acquired:
        return {"blocked": True, "reason": f"lock_failed:{lock_result.reason}"}

    try:
        # 8. Write creation-attempt.json
        write_creation_attempt(artifact_dir)

        # 9. Duplicate GitHub issue check
        dup = find_duplicate_github_issue(owner, repo, title)
        if dup and not allow_possible_duplicate:
            write_creation_error(artifact_dir, f"possible_duplicate:{dup.get('number', '?')}")
            upsert_issue_draft(
                conn,
                {
                    "draft_id": draft_id,
                    "project_id": project_id,
                    "state": "blocked",
                    "title": title,
                    "readiness": row.get("readiness"),
                    "artifact_path": row.get("artifact_path", ""),
                },
            )
            return {
                "blocked": True,
                "reason": "possible_duplicate",
                "duplicate_issue": dup,
            }

        # 10. Call create_github_issue
        result = create_github_issue(owner, repo, title, github_body)

        issue_number_raw = result["issue_number"]
        issue_url_raw = result["issue_url"]
        if not isinstance(issue_number_raw, int):
            raise RuntimeError(f"Expected int issue_number, got {type(issue_number_raw)}: {issue_number_raw!r}")
        if not isinstance(issue_url_raw, str):
            raise RuntimeError(f"Expected str issue_url, got {type(issue_url_raw)}: {issue_url_raw!r}")

        # 11. On success
        write_github_created(artifact_dir, issue_number_raw, issue_url_raw)

        # Update metadata
        metadata["github_issue_number"] = issue_number_raw
        metadata["github_issue_url"] = issue_url_raw
        write_issue_artifact_files(
            root,
            project_id,
            draft_id,
            {
                "original_input": read_issue_artifact(root, project_id, draft_id, "original-input.md") or "",
                "title": title,
                "project_id": project_id,
                "issue_kind": metadata.get("issue_kind", ""),
                "readiness": metadata.get("readiness", 0.0),
                "spec_body": read_issue_artifact(root, project_id, draft_id, "spec.md") or "",
                "github_body": github_body,
                "questions": read_issue_artifact(root, project_id, draft_id, "questions.md") or "",
                "brainstorm_notes": read_issue_artifact(root, project_id, draft_id, "brainstorm.md") or "",
            },
        )

        upsert_issue_draft(
            conn,
            {
                "draft_id": draft_id,
                "project_id": project_id,
                "state": "created",
                "title": title,
                "readiness": row.get("readiness"),
                "artifact_path": row.get("artifact_path", ""),
                "github_issue_number": issue_number_raw,
                "github_issue_url": issue_url_raw,
            },
        )

        return {
            "draft_id": draft_id,
            "state": "created",
            "issue_number": issue_number_raw,
            "issue_url": issue_url_raw,
        }

    except Exception as exc:
        # 12. On failure
        error_msg = redact_secrets(str(exc))
        write_creation_error(artifact_dir, error_msg)
        upsert_issue_draft(
            conn,
            {
                "draft_id": draft_id,
                "project_id": project_id,
                "state": "creating_failed",
                "title": title,
                "readiness": row.get("readiness"),
                "artifact_path": row.get("artifact_path", ""),
            },
        )
        return {
            "blocked": True,
            "reason": "creation_failed",
            "error": error_msg,
        }

    finally:
        release_lock(conn, lock_name, lock_owner)


# ---------------------------------------------------------------------------
# Convenience: create_issue (draft + create)
# ---------------------------------------------------------------------------


def create_issue(
    root: Path,
    conn: sqlite3.Connection,
    text: str,
    title: str,
    body: str,
    *,
    project_ref: str | None = None,
    confirm: bool = False,
    dry_run: bool = False,
    allow_possible_duplicate: bool = False,
) -> dict[str, Any]:
    """Create a local draft and then create the GitHub issue.

    1. Create a local draft via create_issue_draft
    2. Call create_issue_from_draft with the draft_id
    """
    draft_result = create_issue_draft(
        root,
        conn,
        text,
        project_ref=project_ref,
        title=title,
    )

    if draft_result.get("blocked"):
        return draft_result

    draft_id = draft_result.get("draft_id")
    if not draft_id:
        return {"blocked": True, "reason": "draft_creation_failed"}

    return create_issue_from_draft(
        root,
        conn,
        draft_id,
        confirm=confirm,
        dry_run=dry_run,
        allow_possible_duplicate=allow_possible_duplicate,
    )
