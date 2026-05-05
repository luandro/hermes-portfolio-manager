"""Tests for portfolio_manager.implementation_locks — Phase 5, task 5.1."""

from __future__ import annotations

import sqlite3

import pytest

from portfolio_manager.implementation_locks import (
    IMPLEMENTATION_LOCK_TTL,
    ImplementationLockBusy,
    _impl_lock_name,
    with_implementation_lock,
    with_implementation_review_lock,
)
from portfolio_manager.state import acquire_lock, init_state
from portfolio_manager.worktree_locks import with_project_lock


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    init_state(c)
    return c


def _lock_count(conn: sqlite3.Connection, name: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM locks WHERE name=?", (name,)).fetchone()[0]


def test_lock_name_is_implementation_issue_project_issue() -> None:
    assert _impl_lock_name("proj-1", 42) == "implementation:issue:proj-1:42"


def test_default_ttl_is_90_minutes() -> None:
    assert IMPLEMENTATION_LOCK_TTL == 90 * 60


def test_implementation_lock_acquired_and_released(conn: sqlite3.Connection) -> None:
    name = _impl_lock_name("proj-1", 7)
    with with_implementation_lock(conn, "proj-1", 7):
        assert _lock_count(conn, name) == 1
    assert _lock_count(conn, name) == 0


def test_review_lock_acquired_and_released(conn: sqlite3.Connection) -> None:
    name = "implementation:review:proj-1:12"
    with with_implementation_review_lock(conn, "proj-1", 12):
        assert _lock_count(conn, name) == 1
    assert _lock_count(conn, name) == 0


def test_lock_released_on_exception(conn: sqlite3.Connection) -> None:
    name = _impl_lock_name("proj-1", 3)
    with pytest.raises(RuntimeError), with_implementation_lock(conn, "proj-1", 3):
        raise RuntimeError("boom")
    assert _lock_count(conn, name) == 0


def test_lock_contention_raises_typed_error(conn: sqlite3.Connection) -> None:
    """Pre-acquire from another owner; CM must raise ImplementationLockBusy."""
    name = _impl_lock_name("proj-1", 5)
    res = acquire_lock(conn, name, "other-owner", IMPLEMENTATION_LOCK_TTL)
    assert res.acquired
    with pytest.raises(ImplementationLockBusy), with_implementation_lock(conn, "proj-1", 5):
        pass


def test_lock_must_be_acquired_after_worktree_locks_when_combined(
    conn: sqlite3.Connection,
) -> None:
    """Verify ordering works when both worktree and implementation locks are used."""
    impl_name = _impl_lock_name("proj-1", 10)
    wt_name = "worktree:project:proj-1"
    with with_project_lock(conn, "proj-1"), with_implementation_lock(conn, "proj-1", 10):
        assert _lock_count(conn, wt_name) == 1
        assert _lock_count(conn, impl_name) == 1
    assert _lock_count(conn, wt_name) == 0
    assert _lock_count(conn, impl_name) == 0
