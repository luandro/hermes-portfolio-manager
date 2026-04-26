"""Tests for Phase 5 — Config Write Locking."""

from __future__ import annotations

from pathlib import Path

from portfolio_manager.state import acquire_lock, init_state, open_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_and_init(tmp: str) -> object:
    conn = open_state(Path(tmp))
    init_state(conn)
    return conn


# ---------------------------------------------------------------------------
# a) test_mutations_acquire_config_lock
# ---------------------------------------------------------------------------


def test_mutations_acquire_config_lock(tmp_path: Path) -> None:
    from portfolio_manager.admin_locks import CONFIG_LOCK_NAME, with_config_lock

    conn = _open_and_init(str(tmp_path))

    with with_config_lock(conn):
        # Lock row should exist while inside the context
        row = conn.execute(
            "SELECT name, owner FROM locks WHERE name=?",
            (CONFIG_LOCK_NAME,),
        ).fetchone()
        assert row is not None
        assert row[0] == CONFIG_LOCK_NAME

    # Lock should be released after exiting the context
    row = conn.execute(
        "SELECT name FROM locks WHERE name=?",
        (CONFIG_LOCK_NAME,),
    ).fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# b) test_mutation_blocked_when_config_lock_held
# ---------------------------------------------------------------------------


def test_mutation_blocked_when_config_lock_held(tmp_path: Path) -> None:
    from portfolio_manager.admin_locks import (
        CONFIG_LOCK_NAME,
        CONFIG_LOCK_TTL,
        with_config_lock,
    )

    conn = _open_and_init(str(tmp_path))

    # Manually acquire the lock first
    result = acquire_lock(conn, CONFIG_LOCK_NAME, "other-owner", CONFIG_LOCK_TTL)
    assert result.acquired is True

    # Attempting to acquire via with_config_lock should raise RuntimeError
    try:
        with with_config_lock(conn):
            pass  # pragma: no cover — should not reach
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "config_lock_already_held" in str(exc)

    assert raised is True


# ---------------------------------------------------------------------------
# c) test_config_lock_released_after_success_and_failure
# ---------------------------------------------------------------------------


def test_config_lock_released_after_success(tmp_path: Path) -> None:
    from portfolio_manager.admin_locks import CONFIG_LOCK_NAME, with_config_lock

    conn = _open_and_init(str(tmp_path))

    with with_config_lock(conn):
        pass  # normal exit

    row = conn.execute(
        "SELECT name FROM locks WHERE name=?",
        (CONFIG_LOCK_NAME,),
    ).fetchone()
    assert row is None


def test_config_lock_released_after_failure(tmp_path: Path) -> None:
    from portfolio_manager.admin_locks import CONFIG_LOCK_NAME, with_config_lock

    conn = _open_and_init(str(tmp_path))

    try:
        with with_config_lock(conn):
            raise ValueError("deliberate error")
    except ValueError:
        pass

    # Lock must be released even after an exception
    row = conn.execute(
        "SELECT name FROM locks WHERE name=?",
        (CONFIG_LOCK_NAME,),
    ).fetchone()
    assert row is None


# ---------------------------------------------------------------------------
# d) test_with_config_lock_context_manager
# ---------------------------------------------------------------------------


def test_with_config_lock_context_manager(tmp_path: Path) -> None:
    from portfolio_manager.admin_locks import (
        CONFIG_LOCK_NAME,
        CONFIG_LOCK_OWNER,
        CONFIG_LOCK_TTL,
        with_config_lock,
    )

    conn = _open_and_init(str(tmp_path))

    # Verify constants
    assert CONFIG_LOCK_NAME == "config:projects"
    assert CONFIG_LOCK_TTL == 60

    with with_config_lock(conn):
        row = conn.execute(
            "SELECT owner FROM locks WHERE name=?",
            (CONFIG_LOCK_NAME,),
        ).fetchone()
        assert row is not None
        assert row[0] == CONFIG_LOCK_OWNER

    # Released on exit
    row = conn.execute(
        "SELECT name FROM locks WHERE name=?",
        (CONFIG_LOCK_NAME,),
    ).fetchone()
    assert row is None
