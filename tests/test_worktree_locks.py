"""Tests for portfolio_manager.worktree_locks — Phase 5."""

from __future__ import annotations

import sqlite3

import pytest

from portfolio_manager.state import acquire_lock, init_state
from portfolio_manager.worktree_locks import (
    PROJECT_LOCK_TTL,
    WorktreeLockBusy,
    issue_lock_name,
    project_lock_name,
    with_issue_lock,
    with_project_and_issue_locks,
    with_project_lock,
)


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    init_state(c)
    return c


def _lock_count(conn: sqlite3.Connection, name: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM locks WHERE name=?", (name,)).fetchone()[0]


def test_lock_names() -> None:
    assert project_lock_name("p1") == "worktree:project:p1"
    assert issue_lock_name("p1", 7) == "worktree:issue:p1:7"


def test_default_ttl_is_15_minutes() -> None:
    assert PROJECT_LOCK_TTL == 15 * 60


def test_project_lock_acquired_and_released(conn: sqlite3.Connection) -> None:
    with with_project_lock(conn, "p1"):
        assert _lock_count(conn, "worktree:project:p1") == 1
    assert _lock_count(conn, "worktree:project:p1") == 0


def test_issue_lock_acquired_and_released(conn: sqlite3.Connection) -> None:
    with with_issue_lock(conn, "p1", 7):
        assert _lock_count(conn, "worktree:issue:p1:7") == 1
    assert _lock_count(conn, "worktree:issue:p1:7") == 0


def test_locks_acquired_in_stable_order_project_then_issue(conn: sqlite3.Connection) -> None:
    """Combined CM acquires project first, then issue; releases in reverse."""
    with with_project_and_issue_locks(conn, "p1", 5):
        assert _lock_count(conn, "worktree:project:p1") == 1
        assert _lock_count(conn, "worktree:issue:p1:5") == 1
    assert _lock_count(conn, "worktree:project:p1") == 0
    assert _lock_count(conn, "worktree:issue:p1:5") == 0


def test_lock_released_on_exception(conn: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError), with_project_lock(conn, "p1"):
        raise RuntimeError("boom")
    assert _lock_count(conn, "worktree:project:p1") == 0


def test_lock_contention_raises_typed_error(conn: sqlite3.Connection) -> None:
    """Pre-acquire from another owner; CM must raise WorktreeLockBusy."""
    res = acquire_lock(conn, "worktree:project:p1", "other-owner", PROJECT_LOCK_TTL)
    assert res.acquired
    with pytest.raises(WorktreeLockBusy), with_project_lock(conn, "p1"):
        pass


def test_combined_lock_releases_project_when_issue_contended(conn: sqlite3.Connection) -> None:
    """If issue lock is unavailable, project lock must still be released."""
    res = acquire_lock(conn, "worktree:issue:p1:5", "other", PROJECT_LOCK_TTL)
    assert res.acquired
    with pytest.raises(WorktreeLockBusy), with_project_and_issue_locks(conn, "p1", 5):
        pass
    assert _lock_count(conn, "worktree:project:p1") == 0


def test_expired_lock_can_be_stolen(conn: sqlite3.Connection) -> None:
    """An expired (TTL=0) foreign lock must not prevent acquisition."""
    res = acquire_lock(conn, "worktree:project:p1", "other", 0)
    assert res.acquired
    with with_project_lock(conn, "p1"):
        row = conn.execute("SELECT owner FROM locks WHERE name=?", ("worktree:project:p1",)).fetchone()
        assert row[0] != "other"
