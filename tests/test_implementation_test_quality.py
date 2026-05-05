"""Tests for portfolio_manager.implementation_test_quality — Phase 9.1 + 9.3."""

from __future__ import annotations

from typing import Any

from portfolio_manager.implementation_test_quality import (
    check_test_quality,
    collect_test_first_evidence,
)

# ---------------------------------------------------------------------------
# 9.1 — Test-first evidence tests
# ---------------------------------------------------------------------------


def test_evidence_records_failing_test_run_before_implementation() -> None:
    """A red-phase test run with non-zero exit code is recorded as failing."""
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first": [
            {"phase": "red", "command": ["pytest"], "exit_code": 1, "summary": "2 failed"},
            {"phase": "green", "command": ["pytest"], "exit_code": 0, "summary": "all passed"},
        ],
    }
    evidence = collect_test_first_evidence(harness_data, [])

    assert evidence.has_failing_phase is True
    assert evidence.has_passing_phase is True
    assert evidence.blocked_reason is None
    assert len(evidence.phases) == 2


def test_evidence_records_passing_test_run_after_implementation() -> None:
    """A green-phase test run with exit code 0 is recorded as passing."""
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first": [
            {"phase": "red", "command": ["pytest"], "exit_code": 1, "summary": "1 failed"},
            {"phase": "green", "command": ["pytest"], "exit_code": 0, "summary": "all passed"},
        ],
    }
    evidence = collect_test_first_evidence(harness_data, [])

    assert evidence.has_passing_phase is True
    assert evidence.blocked_reason is None


def test_evidence_blocks_when_no_failing_test_phase_found() -> None:
    """If no red-phase entry and no waiver, evidence is blocked."""
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first": [
            {"phase": "green", "command": ["pytest"], "exit_code": 0, "summary": "all passed"},
        ],
    }
    evidence = collect_test_first_evidence(harness_data, [])

    assert evidence.has_failing_phase is False
    assert evidence.blocked_reason == "no_failing_test_phase_found"


def test_evidence_allows_explicit_no_test_path_with_reason() -> None:
    """A valid waiver (reason >= 10 chars) prevents blocking."""
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first_waiver": {
            "reason": "Documentation-only change, no tests applicable for this task",
        },
    }
    evidence = collect_test_first_evidence(harness_data, [])

    assert evidence.waiver is not None
    assert len(evidence.waiver) >= 10
    assert evidence.blocked_reason is None


def test_evidence_waiver_requires_nonempty_reason_string() -> None:
    """A waiver with an empty or too-short reason is rejected."""
    # Empty reason
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first_waiver": {"reason": ""},
    }
    evidence = collect_test_first_evidence(harness_data, [])
    assert evidence.waiver is None
    assert evidence.blocked_reason == "no_failing_test_phase_found"

    # Short reason (< 10 chars)
    harness_data2: dict[str, Any] = {
        "status": "implemented",
        "test_first_waiver": {"reason": "short"},
    }
    evidence2 = collect_test_first_evidence(harness_data2, [])
    assert evidence2.waiver is None
    assert evidence2.blocked_reason == "no_failing_test_phase_found"


def test_evidence_writer_redacts_paths_under_user_home() -> None:
    """Secrets in summary text are redacted."""
    fake_token = "ghp_" + "abc123secret"
    harness_data: dict[str, Any] = {
        "status": "implemented",
        "test_first": [
            {
                "phase": "red",
                "command": ["pytest"],
                "exit_code": 1,
                "summary": f"token={fake_token} failed at /home/user/project",
            },
        ],
    }
    evidence = collect_test_first_evidence(harness_data, [])

    # The summary should have the token value redacted
    phase_summary = evidence.phases[0]["summary"]
    assert fake_token not in phase_summary
    assert "***" in phase_summary


# ---------------------------------------------------------------------------
# 9.3 — Test quality check tests
# ---------------------------------------------------------------------------


def test_quality_passes_when_added_tests_reference_acceptance_criteria_ids() -> None:
    """Tests referencing AC IDs from the spec body pass."""
    spec_body = """
    # Feature Spec

    ## Acceptance Criteria
    AC-1: The system must validate input
    AC-2: The system must return errors for invalid input
    """

    result = check_test_quality(
        changed_files=["src/validator.py", "tests/test_validator.py"],
        new_test_files=["tests/test_validator.py"],
        test_bodies={
            "tests/test_validator.py": (
                "# Tests for AC-1 and AC-2\n"
                "def test_ac1_validates_input():\n"
                "    assert validate('x') == 'x'\n\n"
                "def test_ac2_errors_on_invalid():\n"
                "    with pytest.raises(ValueError):\n"
                "        validate('')\n"
            ),
        },
        spec_body=spec_body,
        job_type="initial_implementation",
    )

    assert result.ok is True
    assert result.mode == "acceptance_criteria_ids"


def test_quality_blocks_when_zero_new_tests_for_initial_implementation() -> None:
    """Initial implementation with no new test files is blocked."""
    result = check_test_quality(
        changed_files=["src/feature.py"],
        new_test_files=[],
        test_bodies={},
        spec_body="Implement feature X",
        job_type="initial_implementation",
    )

    assert result.ok is False
    assert "zero_new_tests_for_initial_implementation" in result.reasons


def test_quality_allows_review_fix_without_new_tests_when_fix_is_doc_only() -> None:
    """Review fix with doc-only scope bypasses test quality check."""
    result = check_test_quality(
        changed_files=["docs/guide.md"],
        new_test_files=[],
        test_bodies={},
        spec_body="Fix documentation typo",
        job_type="review_fix",
        fix_scope=["docs/guide.md"],
    )

    assert result.ok is True
    assert result.mode == "doc_only_bypass"


def test_quality_blocks_when_added_tests_are_only_pass_assertions() -> None:
    """Test files with only `assert True` are rejected."""
    result = check_test_quality(
        changed_files=["src/feature.py", "tests/test_feature.py"],
        new_test_files=["tests/test_feature.py"],
        test_bodies={
            "tests/test_feature.py": ("def test_feature():\n    assert True\n"),
        },
        spec_body="Implement feature X with validation",
        job_type="initial_implementation",
    )

    assert result.ok is False
    assert "added_tests_are_only_pass_assertions" in result.reasons


def test_quality_blocks_when_added_tests_have_no_meaningful_asserts() -> None:
    """Test files with no meaningful assertions are rejected."""
    result = check_test_quality(
        changed_files=["src/feature.py", "tests/test_feature.py"],
        new_test_files=["tests/test_feature.py"],
        test_bodies={
            "tests/test_feature.py": ("def test_feature():\n    x = 1\n    y = 2\n    print(x + y)\n"),
        },
        spec_body="Implement feature X with validation",
        job_type="initial_implementation",
    )

    assert result.ok is False
    assert "added_tests_have_no_meaningful_asserts" in result.reasons


def test_quality_writer_produces_test_quality_md_with_per_test_summary() -> None:
    """check_test_quality returns structured data suitable for test-quality.md.

    Verifies the result has the right shape for artifact writers to consume.
    """
    spec_body = """
    # Feature: Calculator
    AC-1: Add two numbers
    AC-2: Subtract two numbers
    """

    result = check_test_quality(
        changed_files=["src/calc.py", "tests/test_calc.py"],
        new_test_files=["tests/test_calc.py"],
        test_bodies={
            "tests/test_calc.py": (
                "# Tests for AC-1 and AC-2\n"
                "def test_ac1_add():\n"
                "    assert add(2, 3) == 5\n\n"
                "def test_ac2_subtract():\n"
                "    assert subtract(5, 3) == 2\n"
            ),
        },
        spec_body=spec_body,
        job_type="initial_implementation",
    )

    assert result.ok is True
    assert result.mode == "acceptance_criteria_ids"
    assert "tests/test_calc.py" in result.new_test_files
    assert len(result.reasons) > 0
    # Verify it's serializable for artifact writers
    assert isinstance(result.reasons, list)
    assert isinstance(result.new_test_files, list)
    assert isinstance(result.mode, str)
