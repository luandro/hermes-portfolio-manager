"""Issue draft creation, state management, readiness scoring — MVP 3.

Deterministic draft generation and validation.
"""

from __future__ import annotations

import re
from typing import Any

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
    "readiness",
    "internal_notes",
    "private_metadata",
    "<!-- private",
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
