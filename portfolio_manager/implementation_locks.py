"""Lock context managers for MVP 6 — implementation runner.

Mirrors the shape of ``worktree_locks``. Always releases the lock in a
``finally`` block. On contention raises :class:`ImplementationLockBusy`
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

IMPLEMENTATION_LOCK_TTL = 90 * 60  # 90 min
LOCK_OWNER = f"portfolio-manager-impl:{os.getpid()}"


class ImplementationLockBusy(RuntimeError):
    """Raised when an implementation lock is held by another owner."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"lock {name!r} busy: {reason}")
        self.name = name
        self.reason = reason


def _impl_lock_name(project_id: str, issue_number: int) -> str:
    return f"implementation:issue:{project_id}:{issue_number}"


def _review_lock_name(project_id: str, pr_number: int) -> str:
    return f"implementation:review:{project_id}:{pr_number}"


@contextlib.contextmanager
def _with_lock(conn: sqlite3.Connection, name: str, ttl: int) -> Generator[None, None, None]:
    result = acquire_lock(conn, name, LOCK_OWNER, ttl)
    if not result.acquired:
        raise ImplementationLockBusy(name, result.reason)
    try:
        yield
    finally:
        try:
            rel = release_lock(conn, name, LOCK_OWNER)
            if not rel.success:
                logger.warning("impl lock %s release unsuccessful: %s", name, rel.reason)
        except Exception:
            logger.exception("failed to release impl lock %s", name)


@contextlib.contextmanager
def with_implementation_lock(
    conn: sqlite3.Connection, project_id: str, issue_number: int
) -> Generator[None, None, None]:
    """Acquire ``implementation:issue:<id>:<n>`` for the duration of the block."""
    with _with_lock(conn, _impl_lock_name(project_id, issue_number), IMPLEMENTATION_LOCK_TTL):
        yield


@contextlib.contextmanager
def with_implementation_review_lock(
    conn: sqlite3.Connection, project_id: str, pr_number: int
) -> Generator[None, None, None]:
    """Acquire ``implementation:review:<id>:<n>`` for the duration of the block."""
    with _with_lock(conn, _review_lock_name(project_id, pr_number), IMPLEMENTATION_LOCK_TTL):
        yield
