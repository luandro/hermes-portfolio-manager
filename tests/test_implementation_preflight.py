"""Tests for portfolio_manager.implementation_preflight — MVP 6 Phase 6.1."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.implementation_preflight import (
    preflight_initial_implementation,
    preflight_review_fix,
)
from portfolio_manager.state import init_state
from portfolio_manager.worktree_state import init_worktree_schema, upsert_issue_worktree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}

PROJECT_ID = "testproj"
ISSUE_NUMBER = 42


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True)


def _make_db(root: Path) -> sqlite3.Connection:
    """Create an in-memory SQLite with full schema + worktree extensions."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    init_state(conn)
    init_worktree_schema(conn)
    # Insert a project row so FK constraints pass
    conn.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        (PROJECT_ID, "Test", "https://example.com/repo.git", "medium", "active"),
    )
    conn.commit()
    return conn


def _make_bare_and_clone(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare repo + clone, return (bare_path, clone_path)."""
    seed = tmp_path / "_seed"
    seed.mkdir()
    _git("init", "-b", "main", str(seed), cwd=tmp_path)
    (seed / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md", cwd=seed)
    _git("commit", "-m", "initial", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "--bare", str(seed), str(bare), cwd=tmp_path)
    clone = tmp_path / "worktrees" / f"{PROJECT_ID}-issue-{ISSUE_NUMBER}"
    clone.parent.mkdir(parents=True, exist_ok=True)
    _git("clone", str(bare), str(clone), cwd=tmp_path)
    return bare, clone


def _write_spec(root: Path) -> Path:
    """Write a spec.md under artifacts/issues/testproj/issue-42/spec.md."""
    spec_dir = root / "artifacts" / "issues" / PROJECT_ID / f"issue-{ISSUE_NUMBER}"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec = spec_dir / "spec.md"
    spec.write_text("# Spec\nDo the thing.\n", encoding="utf-8")
    return spec


def _setup_happy_path(tmp_path: Path) -> tuple[sqlite3.Connection, Path, Path]:
    """Set up all prerequisites for a passing preflight check."""
    root = tmp_path / "agent-root"
    root.mkdir()
    (root / "artifacts").mkdir()
    (root / "worktrees").mkdir()

    _bare, clone = _make_bare_and_clone(tmp_path)
    spec = _write_spec(root)

    conn = _make_db(root)
    # Insert issue row with spec_artifact_path
    conn.execute(
        "INSERT INTO issues (project_id, issue_number, title, state, last_seen_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), datetime('now'))",
        (PROJECT_ID, ISSUE_NUMBER, "Test issue", "open"),
    )
    conn.execute(
        "UPDATE issues SET spec_artifact_path=? WHERE project_id=? AND issue_number=?",
        (str(spec), PROJECT_ID, ISSUE_NUMBER),
    )
    conn.commit()

    # Insert worktree row
    upsert_issue_worktree(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        path=str(clone),
        state="clean",
        branch_name="main",
    )

    return conn, root, clone


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


def test_preflight_passes_for_clean_worktree_matching_branch_and_existing_source(
    tmp_path: Path,
) -> None:
    conn, root, clone = _setup_happy_path(tmp_path)

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        expected_branch="main",
        root=root,
    )

    assert result.ok
    assert result.reasons == []
    assert result.worktree_path == clone
    assert result.branch_name == "main"
    assert result.head_sha is not None and len(result.head_sha) == 40
    assert result.source_artifact_path is not None
    assert result.source_artifact_path.is_file()


# ---------------------------------------------------------------------------
# 2. SQLite row missing
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_row_missing_in_sqlite(tmp_path: Path) -> None:
    root = tmp_path / "agent-root"
    root.mkdir()
    (root / "artifacts").mkdir()

    conn = _make_db(root)
    # No worktree row inserted

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("not found in SQLite" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 3. Worktree path missing on disk
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_path_missing_on_disk(tmp_path: Path) -> None:
    root = tmp_path / "agent-root"
    root.mkdir()
    (root / "artifacts").mkdir()

    conn = _make_db(root)
    upsert_issue_worktree(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        path="/nonexistent/path/worktree",
        state="clean",
        branch_name="main",
    )

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("does not exist on disk" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 4. Dirty uncommitted
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_dirty_uncommitted(tmp_path: Path) -> None:
    conn, root, clone = _setup_happy_path(tmp_path)
    # Modify a tracked file
    (clone / "README.md").write_text("changed!\n", encoding="utf-8")

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("dirty_uncommitted" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 5. Dirty untracked
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_dirty_untracked(tmp_path: Path) -> None:
    conn, root, clone = _setup_happy_path(tmp_path)
    (clone / "newfile.txt").write_text("untracked\n", encoding="utf-8")

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("dirty_untracked" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 6. Merge conflict
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_in_merge_conflict(tmp_path: Path) -> None:
    conn, root, clone = _setup_happy_path(tmp_path)
    # Simulate merge conflict by writing MERGE_HEAD
    git_dir = clone / ".git"
    (git_dir / "MERGE_HEAD").write_text("0" * 40 + "\n", encoding="utf-8")

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("merge_conflict" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 7. Rebase conflict
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_worktree_in_rebase_conflict(tmp_path: Path) -> None:
    conn, root, clone = _setup_happy_path(tmp_path)
    (clone / ".git" / "rebase-apply").mkdir()

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("rebase_conflict" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 8. Branch mismatch
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_branch_does_not_match_expected(tmp_path: Path) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        expected_branch="feature/expected-branch",
        root=root,
    )

    assert not result.ok
    assert any("Branch mismatch" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 9. Source artifact missing
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_source_artifact_missing(tmp_path: Path) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)
    # Delete the spec file
    spec = root / "artifacts" / "issues" / PROJECT_ID / f"issue-{ISSUE_NUMBER}" / "spec.md"
    assert spec.exists()
    spec.unlink()

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    assert any("Source artifact" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 10. Source artifact outside root
# ---------------------------------------------------------------------------


def test_preflight_blocks_when_source_artifact_outside_root(tmp_path: Path) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)
    # Update the spec_artifact_path to point outside root
    conn.execute(
        "UPDATE issues SET spec_artifact_path=? WHERE project_id=? AND issue_number=?",
        ("/tmp/evil/escape/spec.md", PROJECT_ID, ISSUE_NUMBER),
    )
    conn.commit()

    result = preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    assert not result.ok
    # resolve_source_artifact raises ValueError for escape, caught as source not found
    assert any("Source artifact" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 11. Review fix — branch mismatch
# ---------------------------------------------------------------------------


def test_preflight_for_review_fix_blocks_when_pr_branch_mismatch(tmp_path: Path) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)

    result = preflight_review_fix(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        pr_number=7,
        expected_branch="fix/expected",
        approved_comment_ids=["comment1"],
        fix_scope=["typo"],
        root=root,
    )

    assert not result.ok
    assert any("Branch mismatch" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 12. Review fix — empty approved_comment_ids
# ---------------------------------------------------------------------------


def test_preflight_for_review_fix_blocks_when_approved_comment_ids_empty(
    tmp_path: Path,
) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)

    result = preflight_review_fix(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        pr_number=7,
        approved_comment_ids=[],
        fix_scope=["typo"],
        root=root,
    )

    assert not result.ok
    assert any("approved_comment_ids" in r for r in result.reasons)


# ---------------------------------------------------------------------------
# 13. Pure read — no artifacts written, no SQLite mutations
# ---------------------------------------------------------------------------


def test_preflight_writes_no_artifacts_no_sqlite(tmp_path: Path) -> None:
    conn, root, _clone = _setup_happy_path(tmp_path)

    # Snapshot SQLite and filesystem state
    tables_before = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    artifacts_dir = root / "artifacts"
    files_before = set(artifacts_dir.rglob("*")) if artifacts_dir.exists() else set()

    preflight_initial_implementation(
        conn,
        project_id=PROJECT_ID,
        issue_number=ISSUE_NUMBER,
        root=root,
    )

    tables_after = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    files_after = set(artifacts_dir.rglob("*")) if artifacts_dir.exists() else set()

    assert tables_before == tables_after
    assert files_before == files_after
