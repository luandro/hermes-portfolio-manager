"""Parse GitHub repo references into structured data."""

from __future__ import annotations

import re
from dataclasses import dataclass

GITHUB_SSH_RE = re.compile(r"^git@github\.com:(?P<owner>[A-Za-z0-9._-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?$")
GITHUB_HTTPS_RE = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9._-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?$")
OWNER_REPO_RE = re.compile(r"^(?P<owner>[A-Za-z0-9._-]+)/(?P<repo>[A-Za-z0-9._-]+?)(?:\.git)?$")


@dataclass(frozen=True)
class ParsedRepo:
    owner: str
    repo: str
    repo_url: str
    project_id: str


def parse_github_repo_ref(value: str) -> ParsedRepo:
    """Parse a GitHub repo reference (owner/repo, HTTPS URL, or SSH URL)."""
    if not value:
        raise ValueError("Empty GitHub repo reference")

    # SSH format: git@github.com:owner/repo.git
    m = GITHUB_SSH_RE.match(value)
    if m:
        owner, repo = m.group("owner"), m.group("repo")
        return ParsedRepo(
            owner=owner,
            repo=repo,
            repo_url=f"git@github.com:{owner}/{repo}.git",
            project_id=repo.lower().replace("_", "-").replace(".", "-"),
        )

    # HTTPS format: https://github.com/owner/repo[.git]
    m = GITHUB_HTTPS_RE.match(value)
    if m:
        owner, repo = m.group("owner"), m.group("repo")
        return ParsedRepo(
            owner=owner,
            repo=repo,
            repo_url=f"git@github.com:{owner}/{repo}.git",
            project_id=repo.lower().replace("_", "-").replace(".", "-"),
        )

    # Shorthand: owner/repo
    m = OWNER_REPO_RE.match(value)
    if m:
        owner, repo = m.group("owner"), m.group("repo")
        return ParsedRepo(
            owner=owner,
            repo=repo,
            repo_url=f"git@github.com:{owner}/{repo}.git",
            project_id=repo.lower().replace("_", "-").replace(".", "-"),
        )

    raise ValueError(f"Not a recognizable GitHub repo reference: {value!r}")
