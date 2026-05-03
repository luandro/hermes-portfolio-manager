"""Lock context managers for MVP 5 — Phase 5.

Mirrors the shape of ``admin_locks.with_config_lock``. Always releases the
lock in a ``finally`` block. On contention raises :class:`WorktreeLockBusy`
so handlers can translate to a ``status="blocked"`` result instead of
``failed``.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import TYPE_CHECKING

from portfolio_manager.state import acquire_lock, release_lock

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Generator

logger = logging.getLogger(__name__)

#: Default TTL for worktree advisory locks (15 minutes per spec).
PROJECT_LOCK_TTL = 15 * 60
ISSUE_LOCK_TTL = 15 * 60

#: Stable owner identity for this process. Includes pid for diagnostics.
LOCK_OWNER = f"portfolio-manager-worktree:{os.getpid()}"


class WorktreeLockBusy(Exception):
    """Raised when a worktree lock is held by another owner."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"lock {name!r} busy: {reason}")
        self.name = name
        self.reason = reason


# ---------------------------------------------------------------------------
# Lock name helpers
# ---------------------------------------------------------------------------


def project_lock_name(project_id: str) -> str:
    return f"worktree:project:{project_id}"


def issue_lock_name(project_id: str, issue_number: int) -> str:
    return f"worktree:issue:{project_id}:{issue_number}"


# ---------------------------------------------------------------------------
# Context managers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _with_lock(conn: sqlite3.Connection, name: str, ttl: int) -> Generator[None, None, None]:
    result = acquire_lock(conn, name, LOCK_OWNER, ttl)
    if not result.acquired:
        raise WorktreeLockBusy(name, result.reason)
    try:
        yield
    finally:
        try:
            rel = release_lock(conn, name, LOCK_OWNER)
            if not rel.success:
                logger.warning("worktree lock %s release unsuccessful: %s", name, rel.reason)
        except Exception:
            logger.exception("failed to release worktree lock %s", name)


@contextlib.contextmanager
def with_project_lock(conn: sqlite3.Connection, project_id: str) -> Generator[None, None, None]:
    """Acquire ``worktree:project:<id>`` for the duration of the block."""
    with _with_lock(conn, project_lock_name(project_id), PROJECT_LOCK_TTL):
        yield


@contextlib.contextmanager
def with_issue_lock(conn: sqlite3.Connection, project_id: str, issue_number: int) -> Generator[None, None, None]:
    """Acquire ``worktree:issue:<id>:<n>`` for the duration of the block."""
    with _with_lock(conn, issue_lock_name(project_id, issue_number), ISSUE_LOCK_TTL):
        yield


@contextlib.contextmanager
def with_project_and_issue_locks(
    conn: sqlite3.Connection, project_id: str, issue_number: int
) -> Generator[None, None, None]:
    """Acquire project lock, then issue lock. Both are released on exit/exception."""
    with with_project_lock(conn, project_id), with_issue_lock(conn, project_id, issue_number):
        yield


__all__ = [
    "ISSUE_LOCK_TTL",
    "LOCK_OWNER",
    "PROJECT_LOCK_TTL",
    "WorktreeLockBusy",
    "issue_lock_name",
    "project_lock_name",
    "with_issue_lock",
    "with_project_and_issue_locks",
    "with_project_lock",
]
