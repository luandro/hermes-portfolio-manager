"""Tests for portfolio_manager.worktree_artifacts — Phase 4."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from portfolio_manager.worktree_artifacts import (
    base_artifact_dir,
    issue_artifact_dir,
    write_commands,
    write_error,
    write_inspection,
    write_plan,
    write_preflight,
    write_result,
    write_summary_md,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# 4.1 Path helpers
# ---------------------------------------------------------------------------


def test_base_artifact_dir_under_root(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p1")
    assert d == (tmp_path / "artifacts" / "worktrees" / "p1" / "base").resolve()


def test_issue_artifact_dir_under_root(tmp_path: Path) -> None:
    d = issue_artifact_dir(tmp_path, "p1", 7)
    assert d == (tmp_path / "artifacts" / "worktrees" / "p1" / "issue-7").resolve()


def test_artifact_dir_rejects_path_traversal_in_project_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        base_artifact_dir(tmp_path, "../escape")
    with pytest.raises(ValueError):
        issue_artifact_dir(tmp_path, "../escape", 1)


def test_artifact_dir_rejects_negative_issue_number(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        issue_artifact_dir(tmp_path, "p", 0)
    with pytest.raises(ValueError):
        issue_artifact_dir(tmp_path, "p", -1)


def test_path_helpers_do_not_create_directories(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p1")
    assert not d.exists()


# ---------------------------------------------------------------------------
# 4.2 Writers + redaction
# ---------------------------------------------------------------------------


def test_plan_json_shape_for_real_run(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_plan(d, {"branch": "agent/p/issue-1", "would_clone_base": True})
    data = json.loads(out.read_text())
    assert data["branch"] == "agent/p/issue-1"


def test_commands_json_shape(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_commands(d, [["git", "clone", "url", "."], ["git", "fetch", "origin"]])
    data = json.loads(out.read_text())
    assert data["commands"][0][0] == "git"


def test_preflight_json_shape(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_preflight(d, {"clean": True, "remote_match": True})
    data = json.loads(out.read_text())
    assert data["clean"] is True


def test_result_json_shape_on_success(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_result(d, {"status": "success", "branch_created": True})
    data = json.loads(out.read_text())
    assert data["status"] == "success"


def test_inspection_json_shape(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_inspection(d, {"state": "clean", "branch_name": "main"})
    data = json.loads(out.read_text())
    assert data["state"] == "clean"


def test_error_json_shape_redacts_token_in_stderr(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    out = write_error(d, {"stderr": "fatal: ghp_AAAA1111BBBB2222 not authorized"})
    text = out.read_text()
    assert "ghp_AAAA1111BBBB2222" not in text
    assert "ghp_***" in text


def test_summary_md_is_public_safe_no_token_no_local_path_secrets(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    md = "# Result\n\nUsing token ghp_SECRET12345 and url https://user:pwd@github.com/o/r.git"
    out = write_summary_md(d, md)
    text = out.read_text()
    assert "ghp_SECRET12345" not in text
    assert "user:pwd" not in text


def test_dry_run_writes_no_artifact_files(tmp_path: Path) -> None:
    """Dry-run helpers in tools/ are expected to skip writers; we only test
    that writers themselves never auto-create the dir if it doesn't exist."""
    d = base_artifact_dir(tmp_path, "p")
    with pytest.raises(FileNotFoundError):
        write_plan(d, {"x": 1})


def test_remote_url_redacted_in_all_artifacts(tmp_path: Path) -> None:
    d = base_artifact_dir(tmp_path, "p")
    d.mkdir(parents=True)
    payload = {"remote_url": "https://user:secret@github.com/o/r.git"}
    for fn in (write_plan, write_preflight, write_result, write_inspection, write_error):
        out = fn(d, payload)
        text = out.read_text()
        assert "secret" not in text
