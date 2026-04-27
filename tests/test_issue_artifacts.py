"""Tests for issue artifact path safety and atomic file writing — Phase 2."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from portfolio_manager.issue_artifacts import (
    generate_draft_id,
    issue_artifact_root,
    read_github_created_if_exists,
    read_issue_artifact,
    read_issue_metadata,
    validate_draft_id,
    write_creation_attempt,
    write_creation_error,
    write_github_created,
    write_issue_artifact_files,
    write_json_atomic,
    write_text_atomic,
)


class TestDraftIdValidation:
    def test_accepts_valid_draft_id(self) -> None:
        validate_draft_id("draft_123")  # must not raise

    def test_accepts_uuid_draft_id(self) -> None:
        validate_draft_id("draft_550e8400-e29b-41d4-a716-446655440000")  # must not raise

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="Invalid draft ID"):
            validate_draft_id("../draft_123")

    def test_rejects_slash(self) -> None:
        with pytest.raises(ValueError):
            validate_draft_id("draft/123")

    def test_rejects_dot_prefix(self) -> None:
        with pytest.raises(ValueError):
            validate_draft_id(".draft_123")

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError):
            validate_draft_id("DRAFT_123")

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError):
            validate_draft_id("")


class TestGenerateDraftId:
    def test_starts_with_draft_prefix(self) -> None:
        draft_id = generate_draft_id()
        assert draft_id.startswith("draft_")

    def test_passes_validation(self) -> None:
        draft_id = generate_draft_id()
        validate_draft_id(draft_id)  # must not raise

    def test_unique_across_calls(self) -> None:
        ids = {generate_draft_id() for _ in range(100)}
        assert len(ids) == 100


class TestIssueArtifactRoot:
    def test_resolves_correct_path(self, tmp_path: Path) -> None:
        result = issue_artifact_root(tmp_path, "my-project", "draft_001")
        assert result == tmp_path / "artifacts" / "issues" / "my-project" / "draft_001"

    def test_rejects_invalid_project_id(self) -> None:
        # Invalid project IDs should raise
        with pytest.raises(ValueError):
            issue_artifact_root(Path("/tmp"), "../escape", "draft_001")

    def test_rejects_invalid_draft_id(self) -> None:
        with pytest.raises(ValueError):
            issue_artifact_root(Path("/tmp"), "my-project", "../draft_001")

    def test_path_does_not_escape_root(self, tmp_path: Path) -> None:
        # Crafty path should still resolve under root
        result = issue_artifact_root(tmp_path, "my-project", "draft_001")
        assert str(result).startswith(str(tmp_path))


class TestAtomicArtifactWriteHelpers:
    def test_write_text_atomic_creates_file(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        write_text_atomic(target, "hello world")
        assert target.read_text() == "hello world"

    def test_write_text_atomic_replaces_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("old")
        write_text_atomic(target, "new")
        assert target.read_text() == "new"

    def test_write_json_atomic_creates_valid_json(self, tmp_path: Path) -> None:
        target = tmp_path / "meta.json"
        data = {"key": "value", "num": 42}
        write_json_atomic(target, data)
        import json

        assert json.loads(target.read_text()) == data

    def test_temp_file_cleaned_up_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        write_text_atomic(target, "data")
        # No temp files should remain
        temps = list(tmp_path.glob("*.tmp"))
        assert len(temps) == 0


class TestWriteRequiredArtifactFiles:
    REQUIRED_FILES: ClassVar[list[str]] = [
        "original-input.md",
        "brainstorm.md",
        "questions.md",
        "spec.md",
        "github-issue.md",
        "metadata.json",
    ]

    def test_all_required_files_created(self, tmp_path: Path) -> None:
        content = {
            "original_input": "User wants to export layers as SMP",
            "title": "Export layers as SMP",
            "project_id": "my-project",
            "issue_kind": "feature",
            "readiness": 0.8,
            "spec_body": "## Goal\nUsers can export layers.",
            "github_body": "## Goal\n\nUsers can export layers.\n\n## Acceptance Criteria\n\n- [ ] Layers can be exported.",
            "questions": "What format?",
            "brainstorm_notes": "## Interpreted Request\nExport feature.",
        }
        write_issue_artifact_files(tmp_path, "my-project", "draft_001", content)
        artifact_dir = tmp_path / "artifacts" / "issues" / "my-project" / "draft_001"
        for f in self.REQUIRED_FILES:
            assert (artifact_dir / f).exists(), f"Missing required artifact: {f}"
        # metadata.json must be valid JSON
        import json

        meta = json.loads((artifact_dir / "metadata.json").read_text())
        assert "draft_id" in meta


class TestCreationAuditFiles:
    def test_write_creation_attempt(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts" / "issues" / "p" / "d1"
        artifact_dir.mkdir(parents=True)
        write_creation_attempt(artifact_dir)
        assert (artifact_dir / "creation-attempt.json").exists()
        import json

        data = json.loads((artifact_dir / "creation-attempt.json").read_text())
        assert "attempted_at" in data

    def test_write_github_created(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts" / "issues" / "p" / "d1"
        artifact_dir.mkdir(parents=True)
        write_github_created(artifact_dir, 42, "https://github.com/o/r/issues/42")
        assert (artifact_dir / "github-created.json").exists()
        import json

        data = json.loads((artifact_dir / "github-created.json").read_text())
        assert data["issue_number"] == 42
        assert data["issue_url"] == "https://github.com/o/r/issues/42"

    def test_write_creation_error(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts" / "issues" / "p" / "d1"
        artifact_dir.mkdir(parents=True)
        write_creation_error(artifact_dir, "GitHub API timed out")
        assert (artifact_dir / "creation-error.json").exists()
        import json

        data = json.loads((artifact_dir / "creation-error.json").read_text())
        assert "error" in data

    def test_read_github_created_when_exists(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts" / "issues" / "p" / "d1"
        artifact_dir.mkdir(parents=True)
        write_github_created(artifact_dir, 42, "https://github.com/o/r/issues/42")
        result = read_github_created_if_exists(artifact_dir)
        assert result is not None
        assert result["issue_number"] == 42

    def test_read_github_created_when_missing(self, tmp_path: Path) -> None:
        artifact_dir = tmp_path / "artifacts" / "issues" / "p" / "d1"
        artifact_dir.mkdir(parents=True)
        result = read_github_created_if_exists(artifact_dir)
        assert result is None


class TestReadArtifactFiles:
    def test_read_existing_artifact(self, tmp_path: Path) -> None:
        content = {"original_input": "test"}
        write_issue_artifact_files(tmp_path, "my-project", "draft_001", content)
        result = read_issue_artifact(tmp_path, "my-project", "draft_001", "original-input.md")
        assert "test" in result

    def test_read_missing_artifact_returns_error(self, tmp_path: Path) -> None:
        result = read_issue_artifact(tmp_path, "my-project", "draft_001", "nonexistent.md")
        assert result is None or "not found" in str(result).lower()

    def test_rejects_invalid_draft_id_in_read(self) -> None:
        with pytest.raises(ValueError):
            read_issue_artifact(Path("/tmp"), "p", "../escape.md", "file.md") or True

    def test_read_metadata(self, tmp_path: Path) -> None:
        content = {"original_input": "test", "title": "Test issue", "project_id": "p"}
        write_issue_artifact_files(tmp_path, "p", "draft_001", content)
        meta = read_issue_metadata(tmp_path, "p", "draft_001")
        assert meta is not None
        assert "title" in meta
