"""Tests for maintenance_models dataclasses and make_finding_fingerprint."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
    make_finding_fingerprint,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(**overrides: Any) -> MaintenanceSkillSpec:
    defaults: dict[str, Any] = dict(
        id="test-skill",
        name="Test Skill",
        description="A test skill",
        default_interval_hours=24,
        default_enabled=True,
        supports_issue_drafts=False,
        required_state=["cloned"],
        allowed_commands=[["git", "log"]],
        config_schema={"type": "object"},
    )
    defaults.update(overrides)
    return MaintenanceSkillSpec(**defaults)


def _make_finding(**overrides: Any) -> MaintenanceFinding:
    defaults: dict[str, Any] = dict(
        fingerprint="abc123",
        severity="medium",
        title="Test finding",
        body="Something found",
        source_type="commit",
        source_id="abc123def",
        source_url="https://example.com/commit/abc123def",
        metadata={"line": 42},
        draftable=True,
    )
    defaults.update(overrides)
    return MaintenanceFinding(**defaults)


def _make_result(**overrides: Any) -> MaintenanceSkillResult:
    finding = _make_finding()
    defaults: dict[str, Any] = dict(
        skill_id="test-skill",
        project_id="proj-1",
        status="success",
        findings=[finding],
        summary="Ran successfully",
    )
    defaults.update(overrides)
    return MaintenanceSkillResult(**defaults)


def _make_context(**overrides: Any) -> MaintenanceContext:
    conn = sqlite3.connect(":memory:")
    project = MagicMock()
    defaults: dict[str, Any] = dict(
        root=Path("/tmp/test-project"),
        conn=conn,
        project=project,
        skill_config={"enabled": True},
        now=datetime(2025, 1, 1, tzinfo=UTC),
        refresh_github=False,
    )
    defaults.update(overrides)
    ctx = MaintenanceContext(**defaults)
    return ctx


# ---------------------------------------------------------------------------
# MaintenanceSkillSpec
# ---------------------------------------------------------------------------


class TestMaintenanceSkillSpec:
    def test_creation_with_all_fields(self) -> None:
        spec = _make_spec()
        assert spec.id == "test-skill"
        assert spec.name == "Test Skill"
        assert spec.description == "A test skill"
        assert spec.default_interval_hours == 24
        assert spec.default_enabled is True
        assert spec.supports_issue_drafts is False
        assert spec.required_state == ["cloned"]
        assert spec.allowed_commands == [["git", "log"]]
        assert spec.config_schema == {"type": "object"}

    def test_frozen_immutable(self) -> None:
        spec = _make_spec()
        with pytest.raises(AttributeError):
            spec.id = "changed"  # type: ignore[misc]

    def test_stores_list_and_dict_references(self) -> None:
        """Mutable fields are stored as-is (frozen only prevents attribute assignment)."""
        cmds: list[list[str]] = [["git", "status"]]
        spec = _make_spec(allowed_commands=cmds)
        # The dataclass stores the same reference
        assert spec.allowed_commands is cmds

    def test_equality_same_values(self) -> None:
        a = _make_spec()
        b = _make_spec()
        assert a == b

    def test_inequality_different_values(self) -> None:
        a = _make_spec(id="skill-a")
        b = _make_spec(id="skill-b")
        assert a != b

    def test_hash_same_values(self) -> None:
        """frozen=True dataclasses are hashable when all fields are hashable.
        Lists/dicts are not hashable, so this should raise."""
        with pytest.raises(TypeError):
            hash(_make_spec())

    def test_empty_required_state(self) -> None:
        spec = _make_spec(required_state=[])
        assert spec.required_state == []

    def test_empty_allowed_commands(self) -> None:
        spec = _make_spec(allowed_commands=[])
        assert spec.allowed_commands == []

    def test_complex_config_schema(self) -> None:
        schema = {
            "type": "object",
            "properties": {
                "threshold": {"type": "number", "default": 0.5},
                "paths": {"type": "array", "items": {"type": "string"}},
            },
        }
        spec = _make_spec(config_schema=schema)
        assert spec.config_schema["properties"]["threshold"]["default"] == 0.5


# ---------------------------------------------------------------------------
# MaintenanceContext
# ---------------------------------------------------------------------------


class TestMaintenanceContext:
    def test_creation_with_all_fields(self) -> None:
        ctx = _make_context()
        assert ctx.root == Path("/tmp/test-project")
        assert isinstance(ctx.conn, sqlite3.Connection)
        assert ctx.skill_config == {"enabled": True}
        assert ctx.now == datetime(2025, 1, 1, tzinfo=UTC)
        assert ctx.refresh_github is False

    def test_frozen_immutable(self) -> None:
        ctx = _make_context()
        with pytest.raises(AttributeError):
            ctx.root = Path("/other")  # type: ignore[misc]

    def test_refresh_github_true(self) -> None:
        ctx = _make_context(refresh_github=True)
        assert ctx.refresh_github is True

    def test_now_timezone_aware(self) -> None:
        ctx = _make_context(now=datetime(2025, 6, 15, 12, 30, tzinfo=UTC))
        assert ctx.now.tzinfo is not None

    def test_empty_skill_config(self) -> None:
        ctx = _make_context(skill_config={})
        assert ctx.skill_config == {}


# ---------------------------------------------------------------------------
# MaintenanceFinding
# ---------------------------------------------------------------------------


class TestMaintenanceFinding:
    def test_creation_with_all_fields(self) -> None:
        f = _make_finding()
        assert f.fingerprint == "abc123"
        assert f.severity == "medium"
        assert f.title == "Test finding"
        assert f.body == "Something found"
        assert f.source_type == "commit"
        assert f.source_id == "abc123def"
        assert f.source_url == "https://example.com/commit/abc123def"
        assert f.metadata == {"line": 42}
        assert f.draftable is True

    def test_default_draftable_is_true(self) -> None:
        f = MaintenanceFinding(
            fingerprint="fp",
            severity="info",
            title="t",
            body="b",
            source_type="file",
            source_id=None,
            source_url=None,
            metadata={},
        )
        assert f.draftable is True

    def test_draftable_false(self) -> None:
        f = _make_finding(draftable=False)
        assert f.draftable is False

    def test_all_severity_levels(self) -> None:
        for level in ("info", "low", "medium", "high"):
            f = _make_finding(severity=level)
            assert f.severity == level

    def test_frozen_immutable(self) -> None:
        f = _make_finding()
        with pytest.raises(AttributeError):
            f.title = "changed"  # type: ignore[misc]

    def test_none_source_id(self) -> None:
        f = _make_finding(source_id=None)
        assert f.source_id is None

    def test_none_source_url(self) -> None:
        f = _make_finding(source_url=None)
        assert f.source_url is None

    def test_empty_metadata(self) -> None:
        f = _make_finding(metadata={})
        assert f.metadata == {}

    def test_complex_metadata(self) -> None:
        meta = {"lines": [1, 2, 3], "nested": {"key": "val"}, "flag": True}
        f = _make_finding(metadata=meta)
        assert f.metadata["nested"]["key"] == "val"

    def test_equality(self) -> None:
        a = _make_finding()
        b = _make_finding()
        assert a == b

    def test_inequality(self) -> None:
        a = _make_finding(fingerprint="fp1")
        b = _make_finding(fingerprint="fp2")
        assert a != b


# ---------------------------------------------------------------------------
# MaintenanceSkillResult
# ---------------------------------------------------------------------------


class TestMaintenanceSkillResult:
    def test_creation_with_required_fields(self) -> None:
        r = _make_result()
        assert r.skill_id == "test-skill"
        assert r.project_id == "proj-1"
        assert r.status == "success"
        assert len(r.findings) == 1
        assert r.summary == "Ran successfully"

    def test_default_reason_is_none(self) -> None:
        r = _make_result()
        assert r.reason is None

    def test_default_warnings_empty_list(self) -> None:
        r = _make_result()
        assert r.warnings == []

    def test_explicit_reason(self) -> None:
        r = _make_result(status="skipped", reason="Not applicable")
        assert r.reason == "Not applicable"

    def test_explicit_warnings(self) -> None:
        r = _make_result(warnings=["watch out", "deprecated"])
        assert r.warnings == ["watch out", "deprecated"]

    def test_all_status_values(self) -> None:
        for status in ("success", "skipped", "blocked", "failed"):
            r = _make_result(status=status)
            assert r.status == status

    def test_empty_findings(self) -> None:
        r = _make_result(findings=[], status="success", summary="No issues")
        assert r.findings == []

    def test_multiple_findings(self) -> None:
        findings = [_make_finding(fingerprint=f"fp{i}", title=f"Finding {i}") for i in range(5)]
        r = _make_result(findings=findings)
        assert len(r.findings) == 5

    def test_frozen_immutable(self) -> None:
        r = _make_result()
        with pytest.raises(AttributeError):
            r.status = "failed"  # type: ignore[misc]

    def test_failed_status_with_reason(self) -> None:
        r = _make_result(
            status="failed",
            reason="Command timed out",
            findings=[],
            summary="Skill failed",
        )
        assert r.status == "failed"
        assert r.reason == "Command timed out"

    def test_blocked_status(self) -> None:
        r = _make_result(
            status="blocked",
            reason="Missing required state",
            findings=[],
            summary="Blocked",
        )
        assert r.status == "blocked"


# ---------------------------------------------------------------------------
# make_finding_fingerprint
# ---------------------------------------------------------------------------


class TestMakeFindingFingerprint:
    def test_returns_16_char_hex_string(self) -> None:
        fp = make_finding_fingerprint("skill", "proj", "commit", "abc", "key")
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_deterministic(self) -> None:
        args = ("skill", "proj", "commit", "abc", "key")
        assert make_finding_fingerprint(*args) == make_finding_fingerprint(*args)

    def test_different_skill_id_different_fingerprint(self) -> None:
        fp1 = make_finding_fingerprint("skill-a", "proj", "commit", "abc", "key")
        fp2 = make_finding_fingerprint("skill-b", "proj", "commit", "abc", "key")
        assert fp1 != fp2

    def test_different_project_id_different_fingerprint(self) -> None:
        fp1 = make_finding_fingerprint("skill", "proj-a", "commit", "abc", "key")
        fp2 = make_finding_fingerprint("skill", "proj-b", "commit", "abc", "key")
        assert fp1 != fp2

    def test_different_source_type_different_fingerprint(self) -> None:
        fp1 = make_finding_fingerprint("skill", "proj", "commit", "abc", "key")
        fp2 = make_finding_fingerprint("skill", "proj", "file", "abc", "key")
        assert fp1 != fp2

    def test_different_key_different_fingerprint(self) -> None:
        fp1 = make_finding_fingerprint("skill", "proj", "commit", "abc", "key1")
        fp2 = make_finding_fingerprint("skill", "proj", "commit", "abc", "key2")
        assert fp1 != fp2

    def test_none_source_id_treated_as_empty(self) -> None:
        fp_none = make_finding_fingerprint("skill", "proj", "commit", None, "key")
        fp_empty = make_finding_fingerprint("skill", "proj", "commit", "", "key")
        assert fp_none == fp_empty

    def test_none_vs_real_source_id_differ(self) -> None:
        fp_none = make_finding_fingerprint("skill", "proj", "commit", None, "key")
        fp_real = make_finding_fingerprint("skill", "proj", "commit", "abc123", "key")
        assert fp_none != fp_real

    def test_matches_manual_sha256(self) -> None:
        raw = "skill|proj|commit|abc|key"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
        actual = make_finding_fingerprint("skill", "proj", "commit", "abc", "key")
        assert actual == expected

    def test_empty_strings(self) -> None:
        fp = make_finding_fingerprint("", "", "", "", "")
        assert len(fp) == 16
        # Empty strings produce "||||" (4 delimiters between 5 empty segments)
        raw = "||||"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:16]
        assert fp == expected

    def test_pipe_in_value_is_delimiter_ambiguous(self) -> None:
        """Values containing | are ambiguous with the pipe delimiter.

        This is a known limitation of the simple delimiter-based approach.
        """
        fp1 = make_finding_fingerprint("a|b", "c", "d", "e", "f")
        fp2 = make_finding_fingerprint("a", "b|c", "d", "e", "f")
        # These produce the same raw string, so same fingerprint
        assert fp1 == fp2
