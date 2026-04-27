"""Tests for GitHub repo reference parsing (repo_parser module)."""

from __future__ import annotations

import pytest

from portfolio_manager.repo_parser import ParsedRepo, parse_github_repo_ref

# ---------------------------------------------------------------------------
# a) owner/repo format
# ---------------------------------------------------------------------------


def test_parse_owner_repo() -> None:
    result = parse_github_repo_ref("awana-digital/edt-next")
    assert result == ParsedRepo(
        owner="awana-digital",
        repo="edt-next",
        repo_url="git@github.com:awana-digital/edt-next.git",
        project_id="edt-next",
    )


# ---------------------------------------------------------------------------
# b) HTTPS URL format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/awana-digital/edt-next",
        "https://github.com/awana-digital/edt-next.git",
    ],
)
def test_parse_https_github_url(value: str) -> None:
    result = parse_github_repo_ref(value)
    assert result.owner == "awana-digital"
    assert result.repo == "edt-next"
    assert result.repo_url == "git@github.com:awana-digital/edt-next.git"
    assert result.project_id == "edt-next"


# ---------------------------------------------------------------------------
# c) SSH URL format
# ---------------------------------------------------------------------------


def test_parse_ssh_github_url() -> None:
    result = parse_github_repo_ref("git@github.com:awana-digital/edt-next.git")
    assert result.owner == "awana-digital"
    assert result.repo == "edt-next"
    assert result.repo_url == "git@github.com:awana-digital/edt-next.git"
    assert result.project_id == "edt-next"


# ---------------------------------------------------------------------------
# d) Invalid references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "not-a-repo",
        "https://gitlab.com/owner/repo",
        "https://example.com/owner/repo",
        "git@notgithub.com:owner/repo.git",
        "owner/repo/extra",
        "../owner/repo",
        "owner/../repo",
    ],
)
def test_reject_invalid_github_repo_refs(value: str) -> None:
    with pytest.raises(ValueError, match=r"[Nn]ot a recognizable|invalid|Empty"):
        parse_github_repo_ref(value)


def test_reject_empty_input() -> None:
    with pytest.raises(ValueError, match="Empty"):
        parse_github_repo_ref("")
