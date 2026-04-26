"""Tests for GitHub repo validation via gh CLI (repo_validation module)."""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    import pytest

from portfolio_manager.repo_validation import (
    check_gh_available_for_project_add,
    validate_github_repo,
)

FAKE_GH_JSON = json.dumps(
    {
        "name": "edt-next",
        "owner": {"login": "awana-digital"},
        "defaultBranchRef": {"name": "main"},
        "url": "https://github.com/awana-digital/edt-next",
        "isPrivate": False,
    }
)


# ---------------------------------------------------------------------------
# a) Successful validation
# ---------------------------------------------------------------------------


def test_validate_github_repo_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = FAKE_GH_JSON
    mock_proc.returncode = 0

    def fake_run(cmd, **kwargs):
        assert cmd == [
            "gh",
            "repo",
            "view",
            "awana-digital/edt-next",
            "--json",
            "name,owner,defaultBranchRef,url,isPrivate",
        ]
        return mock_proc

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = validate_github_repo("awana-digital", "edt-next")
    assert result.available is True
    assert result.owner == "awana-digital"
    assert result.repo == "edt-next"
    assert result.default_branch == "main"
    assert result.url == "https://github.com/awana-digital/edt-next"
    assert result.is_private is False


# ---------------------------------------------------------------------------
# b) Blocked / failure cases
# ---------------------------------------------------------------------------


def test_validation_gh_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = validate_github_repo("awana-digital", "edt-next")
    assert result.available is False
    assert "gh CLI not found" in result.message


def test_validation_gh_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            stderr="gh: You are not logged into any GitHub hosts.",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = validate_github_repo("awana-digital", "edt-next")
    assert result.available is False
    assert "not logged" in result.message


def test_validation_repo_inaccessible(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=cmd,
            stderr="HTTP 404: Not Found",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = validate_github_repo("awana-digital", "no-such-repo")
    assert result.available is False
    assert "404" in result.message


def test_validation_bad_json(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_proc = MagicMock()
    mock_proc.stdout = "not valid json"
    mock_proc.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = validate_github_repo("awana-digital", "edt-next")
    assert result.available is False
    assert "parse" in result.message.lower()


# ---------------------------------------------------------------------------
# c) Reporting: validate_github flag behavior
# ---------------------------------------------------------------------------


def test_check_gh_available_flag_true_blocks_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When validate_github=True and validation fails, result has available=False."""

    def fake_run(cmd, **kwargs):
        raise FileNotFoundError("gh not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = check_gh_available_for_project_add(
        validate_github=True,
        owner="awana-digital",
        repo="edt-next",
    )
    assert result is not None
    assert result.available is False


def test_check_gh_available_flag_false_skips_validation() -> None:
    """When validate_github=False, returns None (no validation attempted)."""
    result = check_gh_available_for_project_add(
        validate_github=False,
        owner="awana-digital",
        repo="edt-next",
    )
    assert result is None


def test_check_gh_available_flag_true_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When validate_github=True and gh succeeds, result has available=True."""
    mock_proc = MagicMock()
    mock_proc.stdout = FAKE_GH_JSON
    mock_proc.returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: mock_proc)

    result = check_gh_available_for_project_add(
        validate_github=True,
        owner="awana-digital",
        repo="edt-next",
    )
    assert result is not None
    assert result.available is True
