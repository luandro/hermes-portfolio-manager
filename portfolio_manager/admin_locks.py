"""Config write locking for the Portfolio Manager plugin.

Phase 5: context manager that wraps advisory-lock acquisition/release
around config mutations, preventing concurrent writes.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Generator

from portfolio_manager.state import acquire_lock, release_lock

CONFIG_LOCK_NAME = "config:projects"
CONFIG_LOCK_TTL = 60
CONFIG_LOCK_OWNER = "portfolio-manager-admin"


@contextlib.contextmanager
def with_config_lock(conn: sqlite3.Connection) -> Generator[None, None, None]:
    """Acquire the config:projects advisory lock, yield, then release.

    Raises ``RuntimeError`` if the lock is already held by another owner.
    The lock is always released on exit, even if the wrapped block raises.
    """
    result = acquire_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER, CONFIG_LOCK_TTL)
    if not result.acquired:
        raise RuntimeError(f"config_lock_already_held: {result.reason}")

    try:
        yield
    finally:
        release_lock(conn, CONFIG_LOCK_NAME, CONFIG_LOCK_OWNER)
