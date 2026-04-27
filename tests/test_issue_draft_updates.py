"""Tests for issue draft creation, duplicate detection, and update — Phase 5."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from portfolio_manager.issue_artifacts import (
    generate_draft_id,
)
from portfolio_manager.issue_drafts import (
    create_issue_draft,
    update_issue_draft,
)
from portfolio_manager.state import (
    get_issue_draft,
    init_state,
    open_state,
    upsert_issue_draft,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_test_projects(tmp_path: Path) -> Path:
    root = tmp_path / "agent-system"
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "projects.yaml").write_text(
        """\
version: 1
projects:
  - id: comapeo-cloud-app
    name: CoMapeo Cloud App
    repo: git@github.com:digidem/comapeo-cloud-app.git
    github: {owner: digidem, repo: comapeo-cloud-app}
    priority: medium
    status: active
  - id: comapeo-mobile
    name: CoMapeo Mobile
    repo: git@github.com:digidem/comapeo-mobile.git
    github: {owner: digidem, repo: comapeo-mobile}
    priority: medium
    status: active
"""
    )
    return root


def _setup_db(root: Path) -> sqlite3.Connection:  # noqa: F821
    conn = open_state(root)
    init_state(conn)
    return conn


def _insert_project(conn: sqlite3.Connection, project_id: str) -> None:  # noqa: F821
    from portfolio_manager.state import _utcnow

    now = _utcnow()
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', 'active', ?, ?)",
        (project_id, project_id, f"https://github.com/test/{project_id}", now, now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 5.1 — create_issue_draft with resolved project
# ---------------------------------------------------------------------------


def test_create_draft_with_resolved_project(tmp_path: Path) -> None:
    """Create draft with explicit project_ref. Verify draft_id, artifacts, SQLite row."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    result = create_issue_draft(
        root,
        conn,
        "Users should be able to export selected styled layers as an SMP file for CoMapeo Cloud App.",
        project_ref="comapeo-cloud-app",
    )

    assert result["draft_id"].startswith("draft_")
    assert result["project_id"] == "comapeo-cloud-app"
    assert result["state"] in ("ready_for_creation", "needs_user_questions")
    assert result["title"]
    assert result["readiness"] >= 0.0

    # Verify SQLite row
    row = get_issue_draft(conn, result["draft_id"])
    assert row is not None
    assert row["project_id"] == "comapeo-cloud-app"

    # Verify artifacts exist
    artifact_dir = root / "artifacts" / "issues" / "comapeo-cloud-app" / result["draft_id"]
    assert (artifact_dir / "original-input.md").exists()
    assert (artifact_dir / "spec.md").exists()
    assert (artifact_dir / "metadata.json").exists()

    conn.close()


# ---------------------------------------------------------------------------
# 5.2 — Duplicate local draft detection
# ---------------------------------------------------------------------------


def test_duplicate_local_draft_detection(tmp_path: Path) -> None:
    """Create draft with title, then try again with same title. Should be blocked."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    first = create_issue_draft(
        root,
        conn,
        "Users should be able to export selected styled layers as an SMP file.",
        project_ref="comapeo-cloud-app",
        title="Export layers as SMP",
    )
    assert first["draft_id"]

    second = create_issue_draft(
        root,
        conn,
        "Users should be able to export selected styled layers as an SMP file.",
        project_ref="comapeo-cloud-app",
        title="Export layers as SMP",
    )
    assert second["blocked"] is True
    assert second["reason"] == "duplicate"
    assert second["duplicate_of"] == first["draft_id"]

    conn.close()


# ---------------------------------------------------------------------------
# 5.3 — Ambiguous project
# ---------------------------------------------------------------------------


def test_create_draft_with_ambiguous_project(tmp_path: Path) -> None:
    """Create draft with ambiguous text. State should be needs_project_confirmation."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    result = create_issue_draft(
        root,
        conn,
        "Add a feature for the comapeo application that syncs data between cloud and mobile.",
    )

    assert result["state"] == "needs_project_confirmation"
    assert result.get("candidates")
    assert len(result["candidates"]) >= 2

    conn.close()


# ---------------------------------------------------------------------------
# 5.4 — Project not found blocks
# ---------------------------------------------------------------------------


def test_create_draft_project_not_found_blocks(tmp_path: Path) -> None:
    """Create draft with unmatchable text. Should be blocked."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    result = create_issue_draft(
        root,
        conn,
        "Something completely unrelated to any configured project xyzzy foobar.",
    )

    assert result["blocked"] is True
    assert result["state"] == "blocked"

    conn.close()


# ---------------------------------------------------------------------------
# 5.5 — force_rough_issue cannot bypass project ambiguity
# ---------------------------------------------------------------------------


def test_force_rough_issue_cannot_bypass_project_ambiguity(tmp_path: Path) -> None:
    """force_rough_issue=true with ambiguous project -> needs_project_confirmation."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    result = create_issue_draft(
        root,
        conn,
        "Add a feature for the comapeo application that syncs data between cloud and mobile.",
        force_rough_issue=True,
    )

    assert result["state"] == "needs_project_confirmation"

    conn.close()


# ---------------------------------------------------------------------------
# 5.6 — Update draft with answers
# ---------------------------------------------------------------------------


def test_update_draft_with_answers(tmp_path: Path) -> None:
    """Create vague draft, update with answers. Readiness should increase."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    created = create_issue_draft(
        root,
        conn,
        "We should make it better.",
        project_ref="comapeo-cloud-app",
    )
    original_readiness = created["readiness"]

    updated = update_issue_draft(
        root,
        conn,
        created["draft_id"],
        answers="Target users are field mappers. Should support Android and iOS. Scope is limited to export functionality.",
    )

    assert updated["readiness"] >= original_readiness

    conn.close()


# ---------------------------------------------------------------------------
# 5.7 — Confirm project on ambiguous draft
# ---------------------------------------------------------------------------


def test_confirm_project_on_ambiguous_draft(tmp_path: Path) -> None:
    """Create ambiguous draft, update with project_id. State should change."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    created = create_issue_draft(
        root,
        conn,
        "Add a feature for the comapeo application that syncs data between cloud and mobile.",
    )
    assert created["state"] == "needs_project_confirmation"

    updated = update_issue_draft(
        root,
        conn,
        created["draft_id"],
        project_id="comapeo-cloud-app",
    )
    assert updated["state"] != "needs_project_confirmation"

    conn.close()


# ---------------------------------------------------------------------------
# 5.8 — Terminal drafts cannot be edited
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("terminal_state", ["created", "discarded", "blocked"])
def test_terminal_drafts_cannot_be_edited(tmp_path: Path, terminal_state: str) -> None:
    """Created/discarded/blocked drafts block update."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)
    _insert_project(conn, "comapeo-cloud-app")

    draft_id = generate_draft_id()
    upsert_issue_draft(
        conn,
        {
            "draft_id": draft_id,
            "project_id": "comapeo-cloud-app",
            "state": terminal_state,
            "title": "Test draft",
            "readiness": 0.5,
            "artifact_path": f"artifacts/issues/comapeo-cloud-app/{draft_id}",
        },
    )

    result = update_issue_draft(
        root,
        conn,
        draft_id,
        answers="More details",
    )
    assert result["blocked"] is True
    assert "terminal" in result["reason"].lower() or terminal_state in result["reason"]

    conn.close()


# ---------------------------------------------------------------------------
# 5.9 — creating_failed draft can be retried
# ---------------------------------------------------------------------------


def test_creating_failed_draft_can_be_retried(tmp_path: Path) -> None:
    """creating_failed state allows retries."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)
    _insert_project(conn, "comapeo-cloud-app")

    draft_id = generate_draft_id()
    upsert_issue_draft(
        conn,
        {
            "draft_id": draft_id,
            "project_id": "comapeo-cloud-app",
            "state": "creating_failed",
            "title": "Failed draft",
            "readiness": 0.8,
            "artifact_path": f"artifacts/issues/comapeo-cloud-app/{draft_id}",
        },
    )

    # Write artifact files so the update can find them
    from portfolio_manager.issue_artifacts import write_issue_artifact_files

    artifact_dir = root / "artifacts" / "issues" / "comapeo-cloud-app" / draft_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_issue_artifact_files(
        root,
        "comapeo-cloud-app",
        draft_id,
        {
            "original_input": "Failed to create",
            "title": "Failed draft",
            "spec_body": "## Goal\nTest",
            "github_body": "## Goal\nTest",
            "questions": "",
            "brainstorm_notes": "",
        },
    )

    # No github-created.json means retry is allowed
    result = update_issue_draft(
        root,
        conn,
        draft_id,
        answers="Updated answer for retry",
    )
    assert result.get("blocked") is not True
    assert result["state"] != "creating_failed"

    conn.close()


# ---------------------------------------------------------------------------
# 5.10 — force_ready preserves open questions
# ---------------------------------------------------------------------------


def test_force_ready_preserves_open_questions(tmp_path: Path) -> None:
    """force_ready=true creates ready state even with questions."""
    root = _make_test_projects(tmp_path)
    conn = _setup_db(root)

    created = create_issue_draft(
        root,
        conn,
        "Make it better.",
        project_ref="comapeo-cloud-app",
    )

    updated = update_issue_draft(
        root,
        conn,
        created["draft_id"],
        force_ready=True,
    )
    assert updated["state"] == "ready_for_creation"
    # Questions may still be present but state is ready
    assert "questions" in updated

    conn.close()
