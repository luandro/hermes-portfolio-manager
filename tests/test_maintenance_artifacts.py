"""Tests for maintenance artifact path safety and secret redaction — Phase 3."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from portfolio_manager.maintenance_artifacts import (
    ensure_artifact_dir,
    get_artifact_dir,
    redact_secrets,
    write_artifact,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestMaintenanceArtifactDirUnderRoot:
    def test_dir_is_under_root_artifacts_maintenance(self, tmp_path: Path) -> None:
        result = get_artifact_dir(tmp_path, "abc123")
        expected = tmp_path / "artifacts" / "maintenance" / "abc123"
        assert result == expected

    def test_resolved_dir_is_under_root(self, tmp_path: Path) -> None:
        result = get_artifact_dir(tmp_path, "run456")
        assert result.resolve().is_relative_to(tmp_path.resolve())


class TestRunIdPathTraversalRejected:
    def test_dotdot_traversal_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=r"[Tt]raversal|[Ee]scape|[Ii]nvalid"):
            get_artifact_dir(tmp_path, "../../../etc/passwd")

    def test_dotdot_prefix_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            get_artifact_dir(tmp_path, "../escape")

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            get_artifact_dir(tmp_path, "/etc/passwd")

    def test_null_byte_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            get_artifact_dir(tmp_path, "run\x00evil")


class TestArtifactPathsCreatedForRunId:
    def test_ensure_creates_directory(self, tmp_path: Path) -> None:
        result = ensure_artifact_dir(tmp_path, "run001")
        assert result.is_dir()

    def test_ensure_idempotent(self, tmp_path: Path) -> None:
        first = ensure_artifact_dir(tmp_path, "run001")
        second = ensure_artifact_dir(tmp_path, "run001")
        assert first == second
        assert first.is_dir()


class TestArtifactWriteRedactsSecrets:
    def test_write_redacts_github_pat(self, tmp_path: Path) -> None:
        ensure_artifact_dir(tmp_path, "run1")
        write_artifact(tmp_path, "run1", "log.txt", "token is ghp_aaaa1111")
        content = (tmp_path / "artifacts" / "maintenance" / "run1" / "log.txt").read_text()
        assert "ghp_aaaa1111" not in content
        assert "ghp_***" in content

    def test_write_redacts_password(self, tmp_path: Path) -> None:
        ensure_artifact_dir(tmp_path, "run2")
        write_artifact(tmp_path, "run2", "log.txt", "password=testvalue")
        content = (tmp_path / "artifacts" / "maintenance" / "run2" / "log.txt").read_text()
        assert "testvalue" not in content
        assert "password=***" in content


class TestRedactSecretsVariousPatterns:
    def test_redact_ghp_token(self) -> None:
        result = redact_secrets("key=ghp_Aa11Bb22")
        assert "ghp_Aa11Bb22" not in result
        assert "ghp_***" in result

    def test_redact_github_pat(self) -> None:
        result = redact_secrets("token github_pat_Aa11Bb22_3344")
        assert "github_pat_Aa11Bb22_3344" not in result
        assert "github_pat_***" in result

    def test_redact_bearer_token(self) -> None:
        result = redact_secrets("Authorization: Bearer aaabbbcccddd")
        assert "aaabbbcccddd" not in result
        assert "Bearer ***" in result

    def test_redact_token_equals(self) -> None:
        result = redact_secrets("url?token=testval01&other=val")
        assert "testval01" not in result
        assert "token=***" in result

    def test_redact_sk_prefix(self) -> None:
        result = redact_secrets("key=sk-aaaa1111bbbb")
        assert "sk-aaaa1111bbbb" not in result
        assert "sk-***" in result

    def test_redact_password_equals(self) -> None:
        result = redact_secrets("password=testpass1")
        assert "testpass1" not in result
        assert "password=***" in result

    def test_no_secrets_unchanged(self) -> None:
        text = "normal text without secrets"
        assert redact_secrets(text) == text

    def test_redact_ghs_token(self) -> None:
        result = redact_secrets("ghs_Aa11Bb22Cc33")
        assert "ghs_Aa11Bb22Cc33" not in result
        assert "ghs_***" in result

    def test_redact_gho_token(self) -> None:
        result = redact_secrets("gho_Aa11Bb22Cc33")
        assert "gho_Aa11Bb22Cc33" not in result
        assert "gho_***" in result
