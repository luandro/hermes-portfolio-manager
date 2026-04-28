"""Tests for GitHub issue creation client and create-from-draft (Phases 6+7).

Tests for:
- issue_github.py: check_gh_available, find_duplicate_github_issue,
  create_github_issue, parse_issue_create_output
- issue_drafts.py: create_issue_from_draft, create_issue
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.issue_artifacts import (
    issue_artifact_root,
    read_github_created_if_exists,
    write_github_created,
    write_issue_artifact_files,
)
from portfolio_manager.issue_drafts import (
    create_issue_from_draft,
)
from portfolio_manager.state import _utcnow, get_issue_draft, init_state, open_state, upsert_issue_draft

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_project(conn: object, project_id: str) -> None:
    """Insert a minimal project row so FK constraints pass."""
    now = _utcnow()
    conn.execute(  # type: ignore[union-attr]
        "INSERT OR IGNORE INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', 'active', ?, ?)",
        (project_id, project_id, f"https://github.com/test/{project_id}", now, now),
    )
    conn.commit()  # type: ignore[union-attr]


def _make_config(root: Path, projects: list[dict]) -> None:
    """Write a config/projects.yaml with the given projects."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    (config_dir / "projects.yaml").write_text(
        yaml.dump({"version": 1, "projects": projects}),
        encoding="utf-8",
    )


_VALID_PROJECT = {
    "id": "test-project",
    "name": "Test Project",
    "repo": "git@github.com:test-owner/test-repo.git",
    "github": {"owner": "test-owner", "repo": "test-repo"},
    "priority": "high",
    "status": "active",
}


def _setup_draft(
    root: Path,
    conn: object,
    *,
    draft_id: str = "draft_abc123",
    project_id: str = "test-project",
    state: str = "ready_for_creation",
    title: str = "Export layers as SMP file",
    readiness: float = 0.8,
) -> None:
    """Insert a draft row + write artifact files."""
    _insert_project(conn, project_id)
    artifact_path = f"artifacts/issues/{project_id}/{draft_id}"
    upsert_issue_draft(
        conn,
        {
            "draft_id": draft_id,
            "project_id": project_id,
            "state": state,
            "title": title,
            "readiness": readiness,
            "artifact_path": artifact_path,
        },
    )
    # Write artifact files so create_issue_from_draft can read github-issue.md
    artifact_content = {
        "original_input": "Users should be able to export layers",
        "title": title,
        "project_id": project_id,
        "issue_kind": "feature",
        "readiness": readiness,
        "spec_body": f"## Goal\n{title}\n\n## Acceptance Criteria\n",
        "github_body": f"## Goal\n{title}\n\n## Acceptance Criteria\n",
        "questions": "- Who is the target user?",
        "brainstorm_notes": "",
    }
    write_issue_artifact_files(root, project_id, draft_id, artifact_content)


def _mock_subprocess_run(
    monkeypatch: pytest.MonkeyPatch, stdout: str = "", returncode: int = 0, stderr: str = ""
) -> MagicMock:
    """Monkeypatch subprocess.run to return a CompletedProcess."""
    mock = MagicMock()
    mock.return_value = subprocess.CompletedProcess(
        args=["gh"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )
    monkeypatch.setattr(subprocess, "run", mock)
    return mock


# ===========================================================================
# TestGithubCliPreconditions
# ===========================================================================


class TestGithubCliPreconditions:
    def test_gh_available_calls_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from portfolio_manager.issue_github import check_gh_available

        mock = _mock_subprocess_run(monkeypatch, stdout="gh version 2.42.0\n")
        result = check_gh_available()
        assert result.available is True
        mock.assert_called_once()
        args = mock.call_args[0][0]
        assert args[0] == "gh"
        assert args[1] == "--version"


# ===========================================================================
# TestDuplicateGithubIssueDetection
# ===========================================================================


class TestDuplicateGithubIssueDetection:
    def test_exact_title_match_returns_duplicate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from portfolio_manager.issue_github import find_duplicate_github_issue

        stdout = json.dumps(
            [
                {
                    "number": 42,
                    "title": "Export layers as SMP file",
                    "url": "https://github.com/test-owner/test-repo/issues/42",
                }
            ]
        )
        _mock_subprocess_run(monkeypatch, stdout=stdout)

        result = find_duplicate_github_issue("test-owner", "test-repo", "Export layers as SMP file")
        assert result is not None
        assert result["number"] == 42

    def test_no_match_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from portfolio_manager.issue_github import find_duplicate_github_issue

        stdout = json.dumps(
            [
                {
                    "number": 10,
                    "title": "Completely different issue",
                    "url": "https://github.com/test-owner/test-repo/issues/10",
                }
            ]
        )
        _mock_subprocess_run(monkeypatch, stdout=stdout)

        result = find_duplicate_github_issue("test-owner", "test-repo", "Export layers as SMP file")
        assert result is None


# ===========================================================================
# TestCreateIssueWithBodyFile
# ===========================================================================


class TestCreateIssueWithBodyFile:
    def test_creates_issue_with_body_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from portfolio_manager.issue_github import create_github_issue

        _mock_subprocess_run(
            monkeypatch,
            stdout="https://github.com/test-owner/test-repo/issues/99\n",
        )

        result = create_github_issue("test-owner", "test-repo", "Test issue", "Body content")
        assert result["issue_number"] == 99
        assert result["issue_url"] == "https://github.com/test-owner/test-repo/issues/99"

    def test_temp_file_deleted_after_create(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from portfolio_manager.issue_github import create_github_issue

        created_files: list[str] = []

        original_mkstemp = __import__("tempfile").mkstemp

        def tracking_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
            fd, path = original_mkstemp(*args, **kwargs)  # type: ignore[misc]
            created_files.append(path)
            return fd, path

        monkeypatch.setattr("tempfile.mkstemp", tracking_mkstemp)
        _mock_subprocess_run(
            monkeypatch,
            stdout="https://github.com/test-owner/test-repo/issues/99\n",
        )

        create_github_issue("test-owner", "test-repo", "Test issue", "Body content")
        for path in created_files:
            assert not os.path.exists(path), f"Temp file not deleted: {path}"

    def test_labels_passed_when_provided(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from portfolio_manager.issue_github import create_github_issue

        mock = _mock_subprocess_run(
            monkeypatch,
            stdout="https://github.com/test-owner/test-repo/issues/99\n",
        )

        create_github_issue("test-owner", "test-repo", "Test issue", "Body", labels=["bug", "priority:high"])

        call_args = mock.call_args[0][0]
        # Now each label gets its own --label flag
        label_indices = [i for i, arg in enumerate(call_args) if arg == "--label"]
        assert len(label_indices) == 2, f"Expected 2 --label flags, got {len(label_indices)}"
        assert call_args[label_indices[0] + 1] == "bug", f"Expected 'bug', got {call_args[label_indices[0] + 1]}"
        assert call_args[label_indices[1] + 1] == "priority:high", (
            f"Expected 'priority:high', got {call_args[label_indices[1] + 1]}"
        )


# ===========================================================================
# TestParseIssueCreateOutput
# ===========================================================================


class TestParseIssueCreateOutput:
    def test_parses_valid_url(self) -> None:
        from portfolio_manager.issue_github import parse_issue_create_output

        result = parse_issue_create_output(
            "https://github.com/test-owner/test-repo/issues/123\n",
            "test-owner",
            "test-repo",
        )
        assert result["issue_number"] == 123
        assert result["issue_url"] == "https://github.com/test-owner/test-repo/issues/123"

    def test_rejects_invalid_output(self) -> None:
        from portfolio_manager.issue_github import parse_issue_create_output

        with pytest.raises(ValueError, match="Invalid gh issue create output"):
            parse_issue_create_output("not a url", "test-owner", "test-repo")


# ===========================================================================
# TestCreateFromDraftRequiresConfirmation
# ===========================================================================


class TestCreateFromDraftRequiresConfirmation:
    def test_requires_confirm(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123")
        assert result.get("blocked") is True
        assert result["reason"] == "confirm_required"


# ===========================================================================
# TestDryRunCreateFromDraft
# ===========================================================================


class TestDryRunCreateFromDraft:
    def test_dry_run_no_mutation(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        # No subprocess calls should be made
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", dry_run=True)

        assert result.get("dry_run") is True
        # State should not have changed
        row = get_issue_draft(conn, "draft_abc123")
        assert row is not None
        assert row["state"] == "ready_for_creation"
        # No gh CLI calls
        mock_run.assert_not_called()

    def test_dry_run_returns_preview(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", dry_run=True)

        assert result.get("dry_run") is True
        assert result["title"] == "Export layers as SMP file"
        assert result["owner"] == "test-owner"
        assert result["repo"] == "test-repo"
        assert "body_length" in result


# ===========================================================================
# TestCreateFromDraftIsIdempotent
# ===========================================================================


class TestCreateFromDraftIsIdempotent:
    def test_already_created_skips(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        # Write github-created.json to simulate a previous successful creation
        artifact_dir = issue_artifact_root(tmp_path, "test-project", "draft_abc123")
        write_github_created(artifact_dir, 55, "https://github.com/test-owner/test-repo/issues/55")

        # No subprocess calls should be made
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", confirm=True)

        assert result["state"] == "created"
        assert result["issue_number"] == 55
        assert result.get("recovered") is True
        mock_run.assert_not_called()

        # DB state should be "created"
        row = get_issue_draft(conn, "draft_abc123")
        assert row is not None
        assert row["state"] == "created"


# ===========================================================================
# TestCreationFailureHandling
# ===========================================================================


class TestCreationFailureHandling:
    def test_failure_writes_error_and_state(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        # Mock: duplicate check returns None, then create fails
        call_count = [0]

        def mock_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
            call_count[0] += 1
            if call_count[0] == 1:
                # find_duplicate_github_issue -> no duplicates
                return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="[]", stderr="")
            # create_github_issue -> failure
            return subprocess.CompletedProcess(
                args=["gh"], returncode=1, stdout="", stderr="gh issue create failed: network error"
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", confirm=True)

        assert result.get("blocked") is True
        assert result["reason"] == "creation_failed"
        assert "error" in result

        # DB state should be creating_failed
        row = get_issue_draft(conn, "draft_abc123")
        assert row is not None
        assert row["state"] == "creating_failed"

        # creation-error.json should exist
        artifact_dir = issue_artifact_root(tmp_path, "test-project", "draft_abc123")
        assert (artifact_dir / "creation-error.json").exists()

    def test_retry_after_failure(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn, state="creating_failed")

        call_count = [0]

        def mock_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
            call_count[0] += 1
            if call_count[0] == 1:
                # find_duplicate_github_issue -> no duplicates
                return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="[]", stderr="")
            # create_github_issue -> success this time
            return subprocess.CompletedProcess(
                args=["gh"],
                returncode=0,
                stdout="https://github.com/test-owner/test-repo/issues/77\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", confirm=True)

        assert result["state"] == "created"
        assert result["issue_number"] == 77


# ===========================================================================
# TestCreateFromDraftUpdatesMetadata
# ===========================================================================


class TestCreateFromDraftUpdatesMetadata:
    def test_updates_metadata_and_state(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        conn = open_state(tmp_path)
        init_state(conn)
        _make_config(tmp_path, [_VALID_PROJECT])
        _setup_draft(tmp_path, conn)

        call_count = [0]

        def mock_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
            call_count[0] += 1
            if call_count[0] == 1:
                # find_duplicate_github_issue -> no duplicates
                return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout="[]", stderr="")
            # create_github_issue -> success
            return subprocess.CompletedProcess(
                args=["gh"],
                returncode=0,
                stdout="https://github.com/test-owner/test-repo/issues/88\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = create_issue_from_draft(tmp_path, conn, "draft_abc123", confirm=True)

        assert result["state"] == "created"
        assert result["issue_number"] == 88
        assert result["issue_url"] == "https://github.com/test-owner/test-repo/issues/88"

        # Check DB
        row = get_issue_draft(conn, "draft_abc123")
        assert row is not None
        assert row["state"] == "created"
        assert row["github_issue_number"] == 88

        # Check github-created.json artifact
        artifact_dir = issue_artifact_root(tmp_path, "test-project", "draft_abc123")
        created = read_github_created_if_exists(artifact_dir)
        assert created is not None
        assert created["issue_number"] == 88
