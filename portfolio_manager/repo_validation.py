"""Validate GitHub repos exist and are accessible via the gh CLI."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


@dataclass
class GitHubRepoValidationResult:
    available: bool
    message: str = ""
    owner: str = ""
    repo: str = ""
    default_branch: str = ""
    url: str = ""
    is_private: bool = False


def validate_github_repo(owner: str, repo: str) -> GitHubRepoValidationResult:
    """Check that *owner/repo* exists and is accessible via ``gh repo view``."""
    ref = f"{owner}/{repo}"
    try:
        result = subprocess.run(
            [
                "gh",
                "repo",
                "view",
                ref,
                "--json",
                "name,owner,defaultBranchRef,url,isPrivate",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except FileNotFoundError:
        return GitHubRepoValidationResult(available=False, message="gh CLI not found")
    except subprocess.TimeoutExpired:
        return GitHubRepoValidationResult(available=False, message="gh repo view timed out")
    except subprocess.CalledProcessError as exc:
        return GitHubRepoValidationResult(
            available=False,
            message=exc.stderr.strip() or f"gh repo view failed for {ref}",
        )

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return GitHubRepoValidationResult(available=False, message="Failed to parse gh output")

    owner_data = data.get("owner", {})
    owner_login = owner_data.get("login", "") if isinstance(owner_data, dict) else ""
    branch_data = data.get("defaultBranchRef", {})
    default_branch = branch_data.get("name", "") if isinstance(branch_data, dict) else ""

    return GitHubRepoValidationResult(
        available=True,
        owner=owner_login,
        repo=data.get("name", ""),
        default_branch=default_branch,
        url=data.get("url", ""),
        is_private=data.get("isPrivate", False),
    )


def check_gh_available_for_project_add(
    validate_github: bool,
    owner: str,
    repo: str,
) -> GitHubRepoValidationResult | None:
    """Optionally validate a GitHub repo before adding a project.

    Returns ``None`` when *validate_github* is ``False`` (skip validation).
    Otherwise delegates to :func:`validate_github_repo`.
    """
    if not validate_github:
        return None
    return validate_github_repo(owner, repo)
