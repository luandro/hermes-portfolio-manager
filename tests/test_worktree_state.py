"""Tests for portfolio_manager.worktree_state — Phase 3."""

from __future__ import annotations

import sqlite3

import pytest

from portfolio_manager.state import init_state
from portfolio_manager.worktree_state import (
    ALLOWED_WORKTREE_STATES,
    base_worktree_id,
    get_worktree,
    init_worktree_schema,
    issue_worktree_id,
    list_worktrees_for_project,
    upsert_base_worktree,
    upsert_issue_worktree,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    init_state(c)
    init_worktree_schema(c)
    return c


# ---------------------------------------------------------------------------
# 3.1 ID keys + schema
# ---------------------------------------------------------------------------


def test_base_worktree_id_format() -> None:
    assert base_worktree_id("p1") == "base:p1"


def test_issue_worktree_id_format() -> None:
    assert issue_worktree_id("p1", 42) == "issue:p1:42"


def test_schema_init_idempotent_after_mvp5_changes(conn: sqlite3.Connection) -> None:
    init_worktree_schema(conn)
    init_worktree_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(worktrees)").fetchall()}
    for new in ("remote_url", "head_sha", "base_sha", "preparation_artifact_path"):
        assert new in cols


def test_existing_worktrees_rows_still_readable_after_init(conn: sqlite3.Connection) -> None:
    """Pre-MVP5 inserts (without new cols) must remain readable after migration."""
    upsert_base_worktree(conn, project_id="p", path="/tmp/w/p", branch_name="main", base_branch="main", state="clean")
    rows = list_worktrees_for_project(conn, "p")
    assert rows and rows[0]["state"] == "clean"


# ---------------------------------------------------------------------------
# 3.2 Upsert + read helpers
# ---------------------------------------------------------------------------


def test_upsert_base_worktree_row_inserts(conn: sqlite3.Connection) -> None:
    upsert_base_worktree(
        conn,
        project_id="p",
        path="/tmp/w/p",
        branch_name="main",
        base_branch="main",
        state="ready",
        remote_url="github:o/r",
    )
    row = get_worktree(conn, "base:p")
    assert row is not None
    assert row["state"] == "ready"
    assert row["remote_url"] == "github:o/r"


def test_upsert_base_worktree_row_updates_existing(conn: sqlite3.Connection) -> None:
    upsert_base_worktree(conn, project_id="p", path="/tmp/w/p", branch_name="main", base_branch="main", state="ready")
    upsert_base_worktree(conn, project_id="p", path="/tmp/w/p", branch_name="main", base_branch="main", state="clean")
    row = get_worktree(conn, "base:p")
    assert row is not None
    assert row["state"] == "clean"


def test_upsert_issue_worktree_row_inserts(conn: sqlite3.Connection) -> None:
    upsert_issue_worktree(
        conn,
        project_id="p",
        issue_number=7,
        path="/tmp/w/p-issue-7",
        branch_name="agent/p/issue-7",
        base_branch="main",
        state="clean",
    )
    row = get_worktree(conn, "issue:p:7")
    assert row is not None and row["issue_number"] == 7


def test_upsert_issue_worktree_row_updates_existing(conn: sqlite3.Connection) -> None:
    upsert_issue_worktree(conn, project_id="p", issue_number=7, path="/x", state="clean")
    upsert_issue_worktree(conn, project_id="p", issue_number=7, path="/x", state="dirty_uncommitted")
    row = get_worktree(conn, "issue:p:7")
    assert row is not None and row["state"] == "dirty_uncommitted"


def test_get_worktree_by_id_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    assert get_worktree(conn, "issue:none:1") is None


def test_list_worktrees_for_project_filters_correctly(conn: sqlite3.Connection) -> None:
    upsert_base_worktree(conn, project_id="a", path="/a", state="clean")
    upsert_base_worktree(conn, project_id="b", path="/b", state="clean")
    upsert_issue_worktree(conn, project_id="a", issue_number=1, path="/a-1", state="clean")
    rows = list_worktrees_for_project(conn, "a")
    assert {r["id"] for r in rows} == {"base:a", "issue:a:1"}


def test_state_value_must_be_in_allowed_set(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError):
        upsert_base_worktree(conn, project_id="p", path="/p", state="bogus")
    # Spot-check the documented allowed states are recognized
    for s in ALLOWED_WORKTREE_STATES:
        upsert_base_worktree(conn, project_id="p", path="/p", state=s)
