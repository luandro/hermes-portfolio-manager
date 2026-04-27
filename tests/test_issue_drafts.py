"""Tests for issue_drafts state management (Phase 1: subtasks 1.1-1.6)."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.issue_drafts import (
    classify_issue_kind,
    compute_readiness,
    generate_github_issue_body,
    generate_issue_title,
    sanitize_public_issue_body,
    validate_input_length,
    validate_issue_title,
    validate_public_issue_body,
)
from portfolio_manager.state import _utcnow, init_state, open_state


def _insert_project(conn: object, project_id: str) -> None:
    """Insert a minimal project row so FK constraints pass."""
    now = _utcnow()
    conn.execute(  # type: ignore[union-attr]
        "INSERT OR IGNORE INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', 'active', ?, ?)",
        (project_id, project_id, f"https://github.com/test/{project_id}", now, now),
    )
    conn.commit()  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 1.1 — issue_drafts table initialization
# ---------------------------------------------------------------------------


class TestIssueDraftsTable:
    def test_issue_drafts_table_initializes(self, tmp_path: Path) -> None:
        """Verify init_state creates issue_drafts table with correct columns."""
        conn = open_state(tmp_path)
        init_state(conn)
        # Check table exists
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='issue_drafts'").fetchall()
        assert len(tables) == 1
        # Check columns
        cols = {row[1]: row[2] for row in conn.execute("PRAGMA table_info('issue_drafts')").fetchall()}
        assert "draft_id" in cols
        assert "project_id" in cols
        assert "state" in cols
        assert "title" in cols
        assert "readiness" in cols
        assert "artifact_path" in cols
        assert "github_issue_number" in cols
        assert "github_issue_url" in cols
        assert "created_at" in cols
        assert "updated_at" in cols
        # Check index exists
        idx = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_issue_drafts_project_state'"
        ).fetchall()
        assert len(idx) == 1

    def test_issue_drafts_init_is_idempotent(self, tmp_path: Path) -> None:
        """Calling init_state twice does not error."""
        conn = open_state(tmp_path)
        init_state(conn)
        init_state(conn)  # second call should not raise


# ---------------------------------------------------------------------------
# 1.2 — Draft state validation
# ---------------------------------------------------------------------------


class TestDraftStateValidation:
    VALID_STATES: ClassVar[list[str]] = [
        "draft",
        "needs_project_confirmation",
        "needs_user_questions",
        "ready_for_creation",
        "creating",
        "creating_failed",
        "created",
        "discarded",
        "blocked",
    ]

    def test_valid_states_accepted(self) -> None:
        """All valid states pass validation."""
        from portfolio_manager.state import validate_draft_state

        for s in self.VALID_STATES:
            validate_draft_state(s)  # must not raise

    def test_invalid_state_rejected(self) -> None:
        """Invalid state raises ValueError."""
        from portfolio_manager.state import validate_draft_state

        with pytest.raises(ValueError, match="Invalid draft state"):
            validate_draft_state("invalid_state")


# ---------------------------------------------------------------------------
# 1.3 — Upsert and get issue drafts
# ---------------------------------------------------------------------------


class TestUpsertAndGetIssueDraft:
    def test_insert_draft(self, tmp_path: Path) -> None:
        """Draft can be inserted and retrieved."""
        from portfolio_manager.state import get_issue_draft, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        _insert_project(conn, "comapeo-cloud-app")
        draft = {
            "draft_id": "draft_001",
            "project_id": "comapeo-cloud-app",
            "state": "draft",
            "title": "Test issue",
            "readiness": 0.5,
            "artifact_path": "/tmp/test/draft_001",
        }
        upsert_issue_draft(conn, draft)
        result = get_issue_draft(conn, "draft_001")
        assert result is not None
        assert result["draft_id"] == "draft_001"
        assert result["state"] == "draft"

    def test_update_draft(self, tmp_path: Path) -> None:
        """Draft can be updated and changes are reflected."""
        from portfolio_manager.state import get_issue_draft, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        _insert_project(conn, "comapeo-cloud-app")
        draft = {
            "draft_id": "draft_001",
            "project_id": "comapeo-cloud-app",
            "state": "draft",
            "title": "Original",
            "readiness": 0.5,
            "artifact_path": "/tmp/test/draft_001",
        }
        upsert_issue_draft(conn, draft)
        draft["state"] = "ready_for_creation"
        draft["readiness"] = 0.8
        upsert_issue_draft(conn, draft)
        result = get_issue_draft(conn, "draft_001")
        assert result is not None
        assert result["state"] == "ready_for_creation"
        assert result["readiness"] == 0.8

    def test_readiness_range_validated(self, tmp_path: Path) -> None:
        """readiness must be between 0 and 1."""
        from portfolio_manager.state import upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        with pytest.raises(ValueError, match="between 0 and 1"):
            upsert_issue_draft(
                conn,
                {
                    "draft_id": "bad",
                    "state": "draft",
                    "readiness": 1.5,
                    "artifact_path": "/tmp/test",
                },
            )

    def test_get_missing_draft_returns_none(self, tmp_path: Path) -> None:
        """Missing draft returns None, not error."""
        from portfolio_manager.state import get_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        result = get_issue_draft(conn, "nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# 1.4 — List issue drafts
# ---------------------------------------------------------------------------


class TestListIssueDrafts:
    def test_list_all_drafts(self, tmp_path: Path) -> None:
        """List returns all drafts."""
        from portfolio_manager.state import list_issue_drafts, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        for i in range(3):
            upsert_issue_draft(
                conn,
                {
                    "draft_id": f"draft_{i}",
                    "state": "draft",
                    "readiness": 0.5,
                    "artifact_path": f"/tmp/{i}",
                },
            )
        results = list_issue_drafts(conn)
        assert len(results) == 3

    def test_filter_by_project(self, tmp_path: Path) -> None:
        """Filter by project_id."""
        from portfolio_manager.state import list_issue_drafts, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        _insert_project(conn, "proj-a")
        _insert_project(conn, "proj-b")
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d1",
                "project_id": "proj-a",
                "state": "draft",
                "readiness": 0.5,
                "artifact_path": "/tmp/a",
            },
        )
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d2",
                "project_id": "proj-b",
                "state": "draft",
                "readiness": 0.5,
                "artifact_path": "/tmp/b",
            },
        )
        results = list_issue_drafts(conn, project_id="proj-a")
        assert len(results) == 1
        assert results[0]["draft_id"] == "d1"

    def test_exclude_created_by_default(self, tmp_path: Path) -> None:
        """include_created=False excludes 'created' drafts."""
        from portfolio_manager.state import list_issue_drafts, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d1",
                "state": "created",
                "readiness": 1.0,
                "artifact_path": "/tmp/1",
            },
        )
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d2",
                "state": "draft",
                "readiness": 0.5,
                "artifact_path": "/tmp/2",
            },
        )
        results = list_issue_drafts(conn, include_created=False)
        assert len(results) == 1
        assert results[0]["draft_id"] == "d2"

    def test_include_created(self, tmp_path: Path) -> None:
        """include_created=True returns all drafts."""
        from portfolio_manager.state import list_issue_drafts, upsert_issue_draft

        conn = open_state(tmp_path)
        init_state(conn)
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d1",
                "state": "created",
                "readiness": 1.0,
                "artifact_path": "/tmp/1",
            },
        )
        upsert_issue_draft(
            conn,
            {
                "draft_id": "d2",
                "state": "draft",
                "readiness": 0.5,
                "artifact_path": "/tmp/2",
            },
        )
        results = list_issue_drafts(conn, include_created=True)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# 1.5 — Draft mutation lock
# ---------------------------------------------------------------------------


class TestDraftMutationLock:
    def test_draft_lock_acquire(self, tmp_path: Path) -> None:
        """Draft-specific lock can be acquired."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        result = acquire_lock(conn, "issue_draft:draft_001", "test-owner", 120)
        assert result.acquired

    def test_draft_lock_blocks_second(self, tmp_path: Path) -> None:
        """Second acquire on same draft lock fails."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        acquire_lock(conn, "issue_draft:draft_001", "owner-1", 120)
        result = acquire_lock(conn, "issue_draft:draft_001", "owner-2", 120)
        assert not result.acquired

    def test_draft_creation_lock(self, tmp_path: Path) -> None:
        """Draft creation lock works."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        result = acquire_lock(conn, "issue_draft:create", "test-owner", 120)
        assert result.acquired


# ---------------------------------------------------------------------------
# 1.6 — Project-level issue creation lock
# ---------------------------------------------------------------------------


class TestProjectIssueCreationLock:
    def test_project_level_lock_acquire(self, tmp_path: Path) -> None:
        """Project-level issue creation lock can be acquired."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        result = acquire_lock(conn, "github_issue_create:comapeo-cloud-app", "test-owner", 120)
        assert result.acquired

    def test_project_level_lock_blocks_second(self, tmp_path: Path) -> None:
        """Second acquire on same project lock fails."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        acquire_lock(conn, "github_issue_create:comapeo-cloud-app", "owner-1", 120)
        result = acquire_lock(conn, "github_issue_create:comapeo-cloud-app", "owner-2", 120)
        assert not result.acquired

    def test_project_level_lock_release(self, tmp_path: Path) -> None:
        """Lock can be released."""
        from portfolio_manager.state import acquire_lock, release_lock

        conn = open_state(tmp_path)
        init_state(conn)
        acquire_lock(conn, "github_issue_create:comapeo-cloud-app", "owner-1", 120)
        result = release_lock(conn, "github_issue_create:comapeo-cloud-app", "owner-1")
        assert result.success

    def test_different_project_locks_independent(self, tmp_path: Path) -> None:
        """Locks for different projects don't interfere."""
        from portfolio_manager.state import acquire_lock

        conn = open_state(tmp_path)
        init_state(conn)
        acquire_lock(conn, "github_issue_create:proj-a", "owner-1", 120)
        result = acquire_lock(conn, "github_issue_create:proj-b", "owner-2", 120)
        assert result.acquired


# ---------------------------------------------------------------------------
# 4.x — Deterministic draft generation and readiness
# ---------------------------------------------------------------------------


class TestInputLengthLimits:
    def test_accepts_short_input(self) -> None:
        validate_input_length("short text", 20000, "text")

    def test_rejects_over_limit(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            validate_input_length("x" * 20001, 20000, "text")


class TestIssueTitleValidation:
    def test_accepts_valid_title(self) -> None:
        validate_issue_title("Export selected layers as SMP")

    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError):
            validate_issue_title("")

    def test_rejects_too_short(self) -> None:
        with pytest.raises(ValueError):
            validate_issue_title("A")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(ValueError):
            validate_issue_title("x" * 121)

    def test_rejects_newline(self) -> None:
        with pytest.raises(ValueError):
            validate_issue_title("Title\nSecond line")


class TestGenerateIssueTitle:
    def test_generates_title_from_clear_text(self) -> None:
        title = generate_issue_title(
            "Users should be able to export selected styled layers as an SMP file for CoMapeo Mobile."
        )
        assert len(title) >= 5
        assert len(title) <= 120
        assert "export" in title.lower()


class TestClassifyIssueKind:
    def test_classifies_bug(self) -> None:
        assert classify_issue_kind("The app crashes when uploading") == "bug"
        assert classify_issue_kind("This is broken, it fails to load") == "bug"

    def test_classifies_feature(self) -> None:
        assert classify_issue_kind("Users should be able to export layers") == "feature"
        assert classify_issue_kind("Add support for Markdown import") == "feature"

    def test_classifies_unknown(self) -> None:
        assert classify_issue_kind("We need to think about this more") == "unknown"


class TestReadinessScoring:
    def test_clear_request_high_readiness(self) -> None:
        content = {
            "title": "Export layers as SMP",
            "project_id": "comapeo-cloud-app",
            "text": "Users should export selected styled layers as an SMP file.",
        }
        readiness = compute_readiness(content)
        assert readiness >= 0.5

    def test_vague_request_low_readiness(self) -> None:
        content = {
            "title": "",
            "text": "We need to make the stories better.",
        }
        readiness = compute_readiness(content)
        assert readiness < 0.5


class TestGenerateGithubIssueBody:
    def test_includes_required_sections(self) -> None:
        body = generate_github_issue_body(
            {
                "title": "Export layers",
                "spec_body": "## Goal\nUsers can export.",
                "questions": [],
                "issue_kind": "feature",
                "readiness": 0.8,
            }
        )
        assert "## Goal" in body
        assert "## Acceptance Criteria" in body

    def test_excludes_private_metadata(self) -> None:
        body = generate_github_issue_body(
            {
                "title": "Export layers",
                "spec_body": "## Goal\nUsers can export.",
                "questions": [],
                "issue_kind": "feature",
                "readiness": 0.8,
            }
        )
        assert "readiness" not in body


class TestMarkdownSafety:
    def test_rejects_script_tags(self) -> None:
        with pytest.raises(ValueError):
            validate_public_issue_body("<script>alert('xss')</script>")

    def test_rejects_style_tags(self) -> None:
        with pytest.raises(ValueError):
            validate_public_issue_body("<style>body{}</style>")

    def test_rejects_event_handlers(self) -> None:
        with pytest.raises(ValueError):
            validate_public_issue_body("click here <div onclick='steal()'>")

    def test_normalizes_excessive_blank_lines(self) -> None:
        body = sanitize_public_issue_body("Line 1\n\n\n\n\nLine 2")
        assert body.count("\n") <= 3
