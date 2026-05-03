"""Test-first evidence collector and test quality gates for MVP 6.

Consumes harness output and check results to verify the test-first workflow
(red-green-refactor) and evaluate whether added tests are meaningful.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from portfolio_manager.errors import redact_secrets

# ---------------------------------------------------------------------------
# 9.1 — Test-first evidence collector
# ---------------------------------------------------------------------------


@dataclass
class FirstEvidenceResult:
    has_failing_phase: bool
    has_passing_phase: bool
    waiver: str | None = None  # Non-None if waiver was accepted
    phases: list[dict[str, Any]] = field(default_factory=list)
    blocked_reason: str | None = None


def collect_test_first_evidence(
    harness_result_data: dict[str, Any] | None,
    checks_data: list[dict[str, Any]],
) -> FirstEvidenceResult:
    """Consume harness output and check results to verify test-first workflow.

    Parameters
    ----------
    harness_result_data
        Parsed ``harness-result.json`` dict (may be ``None`` if absent).
    checks_data
        List of check result dicts from required checks.
    """
    phases: list[dict[str, Any]] = []
    has_failing = False
    has_passing = False

    # Collect test_first entries from harness-result.json
    if harness_result_data and isinstance(harness_result_data.get("test_first"), list):
        for entry in harness_result_data["test_first"]:
            phase = str(entry.get("phase", ""))
            command = entry.get("command", [])
            exit_code = entry.get("exit_code", -1)
            summary = str(entry.get("summary", ""))
            # Redact summary for safety
            summary = redact_secrets(summary)

            phases.append(
                {
                    "phase": phase,
                    "command": command,
                    "exit_code": exit_code,
                    "summary": summary,
                }
            )

            if phase == "red" and exit_code != 0:
                has_failing = True
            elif phase == "green" and exit_code == 0:
                has_passing = True
            elif phase == "waived":
                pass  # recorded but doesn't count as failing/passing

    # Also check checks_data for test phases (unit_tests check results)
    for check in checks_data:
        check_id = check.get("check_id", "")
        exit_code = check.get("exit_code", -1)
        if check_id == "unit_tests":
            if exit_code != 0:
                has_failing = True
            else:
                has_passing = True
            phases.append(
                {
                    "phase": "check",
                    "check_id": check_id,
                    "exit_code": exit_code,
                    "summary": redact_secrets(str(check.get("summary", ""))),
                }
            )

    # Check for waiver
    waiver: str | None = None
    if harness_result_data and isinstance(harness_result_data.get("test_first_waiver"), dict):
        waiver_data = harness_result_data["test_first_waiver"]
        raw_reason = str(waiver_data.get("reason", "")).strip()
        redacted_reason = redact_secrets(raw_reason)
        # Accept waiver if reason >= 10 chars after redaction
        if len(redacted_reason) >= 10:
            waiver = redacted_reason

    # Determine blocked state
    blocked_reason: str | None = None
    if not has_failing and waiver is None:
        blocked_reason = "no_failing_test_phase_found"

    return FirstEvidenceResult(
        has_failing_phase=has_failing,
        has_passing_phase=has_passing,
        waiver=waiver,
        phases=phases,
        blocked_reason=blocked_reason,
    )


# ---------------------------------------------------------------------------
# 9.3 — Test quality check
# ---------------------------------------------------------------------------


@dataclass
class QualityCheckResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    new_test_files: list[str] = field(default_factory=list)
    mode: str = ""  # 'acceptance_criteria_ids' or 'keyword_overlap' or 'doc_only_bypass'


# Heuristic patterns for non-trivial assertions
_NON_TRIVIAL_ASSERT_RE = re.compile(
    r"assert\s+.*(?:==|!=|<=|>=|<|>|in\s|not\s+in|is\s+not|is\sNone|isinstance|len\(|bool\()"
)
_PYTEST_RAISES_RE = re.compile(r"pytest\.raises\(")
_ASSERT_NOT_RE = re.compile(r"assert\s+not\s+")
_ASSERT_FALSE_RE = re.compile(r"assertFalse\(|assert\s+\w+\s+is\s+False")
_AC_ID_RE = re.compile(r"\bAC[-_]\d+\b", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
_STOP_WORDS = frozenset(
    {
        "true",
        "false",
        "none",
        "self",
        "test",
        "tests",
        "that",
        "this",
        "with",
        "from",
        "into",
        "should",
        "would",
        "could",
        "when",
        "then",
        "must",
        "have",
        "been",
        "will",
        "does",
        "they",
        "them",
        "their",
        "what",
        "which",
        "there",
        "about",
        "each",
        "every",
        "also",
        "some",
        "such",
        "than",
        "other",
        "more",
        "most",
        "very",
        "just",
        "only",
        "first",
        "second",
        "third",
        "last",
        "next",
        "over",
        "after",
        "before",
        "between",
        "under",
        "above",
        "below",
        "both",
        "same",
        "another",
        "these",
        "those",
        "many",
        "much",
        "need",
        "make",
        "like",
        "well",
        "back",
        "even",
        "still",
        "take",
        "come",
        "know",
        "want",
        "give",
        "case",
        "where",
        "value",
        "result",
        "return",
        "assert",
        "check",
        "valid",
        "input",
        "output",
        "error",
        "raise",
        "class",
        "def",
        "function",
        "method",
        "object",
        "string",
        "number",
        "list",
        "dict",
        "file",
        "name",
        "type",
        "data",
        "call",
        "pass",
        "fail",
    }
)


def _has_meaningful_assertions(body: str) -> bool:
    """Check if a test body contains non-trivial assertions."""
    if _PYTEST_RAISES_RE.search(body):
        return True
    if _ASSERT_NOT_RE.search(body):
        return True
    if _ASSERT_FALSE_RE.search(body):
        return True
    return bool(_NON_TRIVIAL_ASSERT_RE.search(body))


def _extract_ac_ids(text: str) -> set[str]:
    """Extract acceptance criteria IDs like AC-1, AC_2 from text."""
    return set(_AC_ID_RE.findall(text))


def _extract_tokens(text: str) -> set[str]:
    """Extract >=4-char identifier-like tokens, stop-word filtered, case-folded."""
    raw = _TOKEN_RE.findall(text)
    return {t.casefold() for t in raw if t.casefold() not in _STOP_WORDS}


def check_test_quality(
    *,
    changed_files: list[str],
    new_test_files: list[str],
    test_bodies: dict[str, str],
    spec_body: str,
    job_type: str,
    fix_scope: list[str] | None = None,
) -> QualityCheckResult:
    """Evaluate whether added tests are meaningful.

    Parameters
    ----------
    changed_files
        All files changed by the harness.
    new_test_files
        Subset of changed_files that are new test files.
    test_bodies
        Mapping of test filename -> file content.
    spec_body
        The source spec body text for cross-referencing.
    job_type
        ``initial_implementation`` or ``review_fix``.
    fix_scope
        For review_fix: the approved fix scope. If doc-only, bypass test quality.
    """
    reasons: list[str] = []

    # 4. For review_fix with doc-only fix_scope: bypass test quality
    if job_type == "review_fix" and fix_scope is not None:
        stripped = [f.strip() for f in fix_scope if f.strip()]
        doc_only = bool(stripped) and all(
            f.endswith((".md", ".txt", ".rst")) or f.startswith("docs/") for f in stripped
        )
        if doc_only:
            return QualityCheckResult(
                ok=True,
                reasons=["doc_only_fix_scope_bypass"],
                new_test_files=new_test_files,
                mode="doc_only_bypass",
            )

    # 1. Count new test files
    if not new_test_files and job_type == "initial_implementation":
        reasons.append("zero_new_tests_for_initial_implementation")
        return QualityCheckResult(
            ok=False,
            reasons=reasons,
            new_test_files=new_test_files,
            mode="",
        )

    # 2. Check for non-trivial assertions in each test file
    files_with_meaningful: list[str] = []
    files_without_meaningful: list[str] = []

    for tf in new_test_files:
        body = test_bodies.get(tf, "")
        if _has_meaningful_assertions(body):
            files_with_meaningful.append(tf)
        else:
            files_without_meaningful.append(tf)

    if new_test_files and not files_with_meaningful:
        # All test files lack meaningful assertions
        has_only_pass = all(
            "assert True" in test_bodies.get(tf, "") for tf in new_test_files if test_bodies.get(tf, "").strip()
        )
        if has_only_pass:
            reasons.append("added_tests_are_only_pass_assertions")
        else:
            reasons.append("added_tests_have_no_meaningful_asserts")
        return QualityCheckResult(
            ok=False,
            reasons=reasons,
            new_test_files=new_test_files,
            mode="",
        )

    # 3. Cross-reference spec body
    if not spec_body or not spec_body.strip():
        reasons.append("spec_unparseable_for_test_quality")
        return QualityCheckResult(
            ok=False,
            reasons=reasons,
            new_test_files=new_test_files,
            mode="",
        )

    # Gather all test text (names + bodies)
    all_test_text = " ".join(new_test_files)
    for tf in new_test_files:
        all_test_text += " " + test_bodies.get(tf, "")

    # 3a. Check for explicit AC IDs
    spec_ac_ids = _extract_ac_ids(spec_body)
    if spec_ac_ids:
        test_ac_ids = _extract_ac_ids(all_test_text)
        if test_ac_ids & spec_ac_ids:
            return QualityCheckResult(
                ok=True,
                reasons=["acceptance_criteria_ids_matched"],
                new_test_files=new_test_files,
                mode="acceptance_criteria_ids",
            )
        else:
            reasons.append("no_test_references_acceptance_criteria_ids")
            return QualityCheckResult(
                ok=False,
                reasons=reasons,
                new_test_files=new_test_files,
                mode="acceptance_criteria_ids",
            )

    # 3b. Keyword overlap
    spec_tokens = _extract_tokens(spec_body)
    test_tokens = _extract_tokens(all_test_text)
    overlap = spec_tokens & test_tokens

    if len(overlap) >= 3:
        return QualityCheckResult(
            ok=True,
            reasons=[f"keyword_overlap_{len(overlap)}_tokens"],
            new_test_files=new_test_files,
            mode="keyword_overlap",
        )
    else:
        reasons.append(f"insufficient_keyword_overlap_{len(overlap)}_tokens_need_3")
        return QualityCheckResult(
            ok=False,
            reasons=reasons,
            new_test_files=new_test_files,
            mode="keyword_overlap",
        )
