"""GitHub issue creation client and duplicate detection — MVP 3.

Uses gh issue create with --body-file. No shell strings.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

from portfolio_manager.issue_drafts import sanitize_public_issue_body, validate_public_issue_body

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reusable data type
# ---------------------------------------------------------------------------


@dataclass
class AvailableCheck:
    available: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _gh_env() -> dict[str, str]:
    """Return a copy of os.environ configured for script use."""
    env = os.environ.copy()
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["NO_COLOR"] = "1"
    for key in ("CLICOLOR_FORCE", "FORCE_COLOR", "GIT_CONFIG_PARAMETERS"):
        env.pop(key, None)
    return env


# ---------------------------------------------------------------------------
# 6.1 check_gh_available
# ---------------------------------------------------------------------------


def check_gh_available() -> AvailableCheck:
    """Check whether the GitHub CLI is installed."""
    try:
        proc = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_gh_env(),
        )
        if proc.returncode != 0:
            return AvailableCheck(available=False, message=f"GitHub CLI check failed: {proc.stderr.strip()}")
        return AvailableCheck(available=True)
    except FileNotFoundError:
        return AvailableCheck(available=False, message="GitHub CLI (gh) is not installed.")
    except Exception as exc:
        return AvailableCheck(available=False, message=str(exc))


# ---------------------------------------------------------------------------
# 6.2 check_gh_auth
# ---------------------------------------------------------------------------


def check_gh_auth() -> AvailableCheck:
    """Check whether the GitHub CLI is authenticated."""
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            env=_gh_env(),
        )
        if proc.returncode == 0:
            return AvailableCheck(available=True)
        return AvailableCheck(
            available=False,
            message="GitHub CLI is not authenticated. Run `gh auth login` on the server.",
        )
    except FileNotFoundError:
        return AvailableCheck(available=False, message="GitHub CLI (gh) is not installed.")
    except Exception as exc:
        return AvailableCheck(available=False, message=str(exc))


# ---------------------------------------------------------------------------
# 6.3 find_duplicate_github_issue
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip, remove punctuation."""
    title = title.lower().strip()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def find_duplicate_github_issue(owner: str, repo: str, title: str) -> dict[str, object] | None:
    """Search for an open GitHub issue with the same normalized title.

    Returns ``{"number": N, "title": "...", "url": "..."}`` if found, else None.
    """
    cmd: list[str] = [
        "gh",
        "issue",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        "open",
        "--search",
        f"{title} in:title",
        "--json",
        "number,title,url",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_gh_env())
    if proc.returncode != 0:
        logger.warning("gh issue list failed: %s", proc.stderr.strip())
        return None

    try:
        issues: list[dict[str, object]] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    norm = _normalize_title(title)
    for issue in issues:
        title_val = issue.get("title", "")
        assert isinstance(title_val, str)
        if _normalize_title(title_val) == norm:
            issue_num = issue["number"]
            issue_title_val = issue["title"]
            issue_url_val = issue.get("url", "")
            assert isinstance(issue_num, int)
            assert isinstance(issue_title_val, str)
            return {
                "number": issue_num,
                "title": issue_title_val,
                "url": issue_url_val,
            }
    return None


# ---------------------------------------------------------------------------
# 6.5 parse_issue_create_output
# ---------------------------------------------------------------------------


def parse_issue_create_output(stdout: str, owner: str, repo: str) -> dict[str, object]:
    """Parse the URL from ``gh issue create`` output.

    Returns ``{"issue_number": N, "issue_url": "..."}``.
    Raises ValueError on invalid output.
    """
    url = stdout.strip()
    pattern = rf"^https://github\.com/{re.escape(owner)}/{re.escape(repo)}/issues/(\d+)$"
    m = re.match(pattern, url)
    if not m:
        raise ValueError(f"Invalid gh issue create output: {url!r}")
    return {"issue_number": int(m.group(1)), "issue_url": url}


# ---------------------------------------------------------------------------
# 6.4 create_github_issue
# ---------------------------------------------------------------------------


def create_github_issue(
    owner: str,
    repo: str,
    title: str,
    body: str,
    *,
    labels: list[str] | None = None,
) -> dict[str, object]:
    """Create a GitHub issue via ``gh issue create`` using a body file.

    Returns ``{"issue_number": N, "issue_url": "..."}``.
    Raises RuntimeError on failure.
    """
    tmp_fd: int | None = None
    tmp_path: str | None = None
    try:
        # Sanitize and validate before sending to GitHub
        safe_body = sanitize_public_issue_body(body)
        validate_public_issue_body(safe_body)

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".md")
        os.write(tmp_fd, safe_body.encode("utf-8"))
        os.close(tmp_fd)
        tmp_fd = None

        cmd: list[str] = [
            "gh",
            "issue",
            "create",
            "--repo",
            f"{owner}/{repo}",
            "--title",
            title,
            "--body-file",
            tmp_path,
        ]
        if labels:
            for lbl in labels:
                cmd.extend(["--label", lbl])

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_gh_env())
        if proc.returncode != 0:
            raise RuntimeError(f"gh issue create failed: {proc.stderr.strip()}")

        return parse_issue_create_output(proc.stdout, owner, repo)
    finally:
        if tmp_fd is not None:
            with contextlib.suppress(OSError):
                os.close(tmp_fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
