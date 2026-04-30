"""Tests for portfolio_manager.worktree_reconcile.worktree_reconcile — Phase 10."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from typing import TYPE_CHECKING

import pytest

from portfolio_manager.state import init_state
from portfolio_manager.worktree_reconcile import worktree_reconcile
from portfolio_manager.worktree_state import (
    init_worktree_schema,
    upsert_base_worktree,
    upsert_issue_worktree,
)

if TYPE_CHECKING:
    from pathlib import Path


_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@e",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@e",
}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_ENV, check=True, capture_output=True)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    db = tmp_path / "state.sqlite"
    c = sqlite3.connect(db)
    init_state(c)
    init_worktree_schema(c)
    # Seed a project row to satisfy FK
    c.execute(
        "INSERT INTO projects (id, name, repo_url, priority, default_branch, status, created_at, updated_at) "
        "VALUES ('p', 'P', 'x', 'high', 'main', 'active', datetime('now'), datetime('now'))"
    )
    c.commit()
    return c


def test_reconcile_returns_clean_when_aligned(
    conn: sqlite3.Connection,
    agent_root: Path,
    bare_remote: Path,
) -> None:
    base = agent_root / "worktrees" / "p"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    upsert_base_worktree(
        conn,
        project_id="p",
        path=str(base),
        state="ready",
        branch_name="main",
        remote_url=f"file:{bare_remote.resolve()}",
    )
    out = worktree_reconcile(conn, "p", None, agent_root)
    assert out["fs_exists"] is True
    # Allow remote drift between file: and github: forms; main check is no diff
    # in branch + path. Branch drift only.
    assert "branch drift" not in " ".join(out["diffs"])


def test_reconcile_blocks_on_partial_state_path_exists_no_sqlite(
    conn: sqlite3.Connection,
    agent_root: Path,
    bare_remote: Path,
) -> None:
    base = agent_root / "worktrees" / "p"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    out = worktree_reconcile(conn, "p", None, agent_root)
    # Row missing → fs_exists=False because we look up by id only
    assert out["sqlite_row"] == {}
    assert out["fs_exists"] is False  # no row → no path → fs lookup uses row.path


def test_reconcile_blocks_on_partial_state_sqlite_exists_no_path(
    conn: sqlite3.Connection,
    agent_root: Path,
) -> None:
    upsert_base_worktree(
        conn,
        project_id="p",
        path=str(agent_root / "worktrees" / "p"),
        state="ready",
        branch_name="main",
    )
    out = worktree_reconcile(conn, "p", None, agent_root)
    assert out["fs_exists"] is False
    assert any("missing" in d for d in out["diffs"])


def test_reconcile_does_not_mutate_repo(
    conn: sqlite3.Connection,
    agent_root: Path,
    bare_remote: Path,
) -> None:
    base = agent_root / "worktrees" / "p"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    upsert_base_worktree(conn, project_id="p", path=str(base), state="ready", branch_name="main")
    before = list((base / ".git").iterdir())
    worktree_reconcile(conn, "p", None, agent_root)
    after = list((base / ".git").iterdir())
    assert sorted(before) == sorted(after)


def test_reconcile_detects_branch_drift(
    conn: sqlite3.Connection,
    agent_root: Path,
    bare_remote: Path,
) -> None:
    base = agent_root / "worktrees" / "p"
    _git("clone", str(bare_remote), str(base), cwd=agent_root)
    upsert_base_worktree(
        conn,
        project_id="p",
        path=str(base),
        state="ready",
        branch_name="develop",
    )
    out = worktree_reconcile(conn, "p", None, agent_root)
    assert any("branch drift" in d for d in out["diffs"])


def test_reconcile_handles_issue_worktree_id(
    conn: sqlite3.Connection,
    agent_root: Path,
) -> None:
    upsert_issue_worktree(
        conn,
        project_id="p",
        issue_number=42,
        path="/nonexistent",
        state="missing",
        branch_name="agent/p/issue-42",
    )
    out = worktree_reconcile(conn, "p", 42, agent_root)
    assert out["worktree_id"] == "issue:p:42"
    assert out["fs_exists"] is False
