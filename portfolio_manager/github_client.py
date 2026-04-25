"""GitHub CLI client for the Portfolio Manager plugin.

Read-only interface to GitHub via the ``gh`` CLI.
Phases 5.2 through 5.7.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from portfolio_manager.state import upsert_issue, upsert_pull_request

if TYPE_CHECKING:
    from portfolio_manager.config import ProjectConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ToolCheckResult:
    available: bool
    message: str = ""


@dataclass
class IssueRecord:
    number: int
    title: str
    labels: list[str]
    author: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class PullRequestRecord:
    number: int
    title: str
    head_branch: str | None = None
    base_branch: str | None = None
    labels: list[str] = field(default_factory=list)
    review_stage: str = "review_pending"
    check_rollup: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class ProjectGitHubSyncResult:
    project_id: str
    issues_count: int = 0
    prs_count: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def _gh_env() -> dict[str, str]:
    """Return a copy of os.environ with GH_NO_UPDATE_NOTIFIER set."""
    env = os.environ.copy()
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    return env


# ---------------------------------------------------------------------------
# 5.2 check_gh_available
# ---------------------------------------------------------------------------


def check_gh_available() -> ToolCheckResult:
    """Check whether the GitHub CLI is installed."""
    try:
        subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=10, env=_gh_env())
        return ToolCheckResult(available=True)
    except FileNotFoundError:
        return ToolCheckResult(available=False, message="GitHub CLI (gh) is not installed.")
    except Exception as exc:
        return ToolCheckResult(available=False, message=str(exc))


# ---------------------------------------------------------------------------
# 5.3 check_gh_auth
# ---------------------------------------------------------------------------


def check_gh_auth() -> ToolCheckResult:
    """Check whether the GitHub CLI is authenticated."""
    try:
        proc = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=10, env=_gh_env())
        if proc.returncode == 0:
            return ToolCheckResult(available=True)
        return ToolCheckResult(
            available=False,
            message="GitHub CLI is not authenticated. Run `gh auth login` on the server.",
        )
    except FileNotFoundError:
        return ToolCheckResult(available=False, message="GitHub CLI (gh) is not installed.")
    except Exception as exc:
        return ToolCheckResult(available=False, message=str(exc))


# ---------------------------------------------------------------------------
# 5.4 list_open_issues
# ---------------------------------------------------------------------------


def list_open_issues(owner: str, repo: str, limit: int = 50) -> list[IssueRecord]:
    """Fetch open issues for *owner/repo* via ``gh issue list``."""
    cmd: list[str] = [
        "gh",
        "issue",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        "open",
        "--limit",
        str(limit),
        "--json",
        "number,title,labels,author,createdAt,updatedAt,url",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_gh_env())
        if proc.returncode != 0:
            logger.warning("gh issue list failed for %s/%s: %s", owner, repo, proc.stderr.strip())
            return []
        raw: list[dict[str, Any]] = json.loads(proc.stdout)
    except Exception as exc:
        logger.warning("gh issue list error for %s/%s: %s", owner, repo, exc)
        return []

    results: list[IssueRecord] = []
    for item in raw:
        labels = [lbl["name"] for lbl in item.get("labels", []) if isinstance(lbl, dict)]
        author_obj = item.get("author")
        author = author_obj.get("login") if isinstance(author_obj, dict) else None
        results.append(
            IssueRecord(
                number=item["number"],
                title=item["title"],
                labels=labels,
                author=author,
                url=item.get("url"),
                created_at=item.get("createdAt"),
                updated_at=item.get("updatedAt"),
            )
        )
    return results


# ---------------------------------------------------------------------------
# 5.5 list_open_prs
# ---------------------------------------------------------------------------


def list_open_prs(owner: str, repo: str, limit: int = 50) -> list[PullRequestRecord]:
    """Fetch open PRs for *owner/repo* via ``gh pr list``."""
    cmd: list[str] = [
        "gh",
        "pr",
        "list",
        "--repo",
        f"{owner}/{repo}",
        "--state",
        "open",
        "--limit",
        str(limit),
        "--json",
        "number,title,headRefName,baseRefName,labels,reviewDecision,statusCheckRollup,createdAt,updatedAt,url",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=_gh_env())
        if proc.returncode != 0:
            logger.warning("gh pr list failed for %s/%s: %s", owner, repo, proc.stderr.strip())
            return []
        raw: list[dict[str, Any]] = json.loads(proc.stdout)
    except Exception as exc:
        logger.warning("gh pr list error for %s/%s: %s", owner, repo, exc)
        return []

    results: list[PullRequestRecord] = []
    for item in raw:
        labels = [lbl["name"] for lbl in item.get("labels", []) if isinstance(lbl, dict)]
        review_stage = map_pr_state(item)
        rollup = item.get("statusCheckRollup")
        rollup_str = json.dumps(rollup) if rollup else None
        results.append(
            PullRequestRecord(
                number=item["number"],
                title=item["title"],
                head_branch=item.get("headRefName"),
                base_branch=item.get("baseRefName"),
                labels=labels,
                review_stage=review_stage,
                check_rollup=rollup_str,
                url=item.get("url"),
                created_at=item.get("createdAt"),
                updated_at=item.get("updatedAt"),
            )
        )
    return results


# ---------------------------------------------------------------------------
# 5.6 map_pr_state
# ---------------------------------------------------------------------------


def _has_failing_checks(rollup: list[dict[str, Any]] | None) -> bool:
    """Return True if any check in the rollup has conclusion=failure."""
    if not rollup:
        return False
    return any(c.get("conclusion") == "failure" for c in rollup if isinstance(c, dict))


def _all_passing(rollup: list[dict[str, Any]] | None) -> bool:
    """Return True if all completed checks have conclusion=success."""
    if not rollup:
        return True
    completed = [c for c in rollup if isinstance(c, dict) and c.get("status") == "completed"]
    if not completed:
        return True
    return all(c.get("conclusion") == "success" for c in completed)


def map_pr_state(pr_json: dict[str, Any]) -> str:
    """Map a PR JSON payload to a human-readable state string.

    Priority order:
    1. CHANGES_REQUESTED -> "changes_requested"
    2. failing checks -> "checks_failed"
    3. APPROVED + passing checks -> "ready_for_human"
    4. no reviewDecision -> "review_pending"
    5. fallback -> "open"
    """
    decision = pr_json.get("reviewDecision")
    rollup = pr_json.get("statusCheckRollup")

    # 1. Changes requested
    if decision == "CHANGES_REQUESTED":
        return "changes_requested"

    # 2. Failing checks
    if _has_failing_checks(rollup):
        return "checks_failed"

    # 3. Approved + passing
    if decision == "APPROVED" and _all_passing(rollup):
        return "ready_for_human"

    # 4. No review decision
    if not decision:
        return "review_pending"

    # 5. Fallback
    return "open"


# ---------------------------------------------------------------------------
# 5.7 sync_project_github
# ---------------------------------------------------------------------------


def sync_project_github(
    conn: Any,
    project: ProjectConfig,
    max_items: int = 50,
) -> ProjectGitHubSyncResult:
    """Sync open issues and PRs for a single project into the state DB.

    Handles inaccessible repos without crashing.
    """
    result = ProjectGitHubSyncResult(project_id=project.id)

    try:
        issues = list_open_issues(project.github.owner, project.github.repo, limit=max_items)
    except Exception as exc:
        msg = f"Failed to fetch issues for {project.id}: {exc}"
        logger.warning(msg)
        result.warnings.append(msg)
        result.error = msg
        return result

    try:
        prs = list_open_prs(project.github.owner, project.github.repo, limit=max_items)
    except Exception as exc:
        msg = f"Failed to fetch PRs for {project.id}: {exc}"
        logger.warning(msg)
        result.warnings.append(msg)
        result.error = msg
        return result

    for issue in issues:
        labels_json = json.dumps(issue.labels)
        upsert_issue(
            conn,
            project.id,
            {
                "number": issue.number,
                "title": issue.title,
                "state": "needs_triage",
                "labels_json": labels_json,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
            },
        )
    result.issues_count = len(issues)

    for pr in prs:
        upsert_pull_request(
            conn,
            project.id,
            {
                "number": pr.number,
                "title": pr.title,
                "branch_name": pr.head_branch,
                "base_branch": pr.base_branch,
                "state": pr.review_stage,
                "review_stage": pr.review_stage,
                "created_at": pr.created_at,
                "updated_at": pr.updated_at,
            },
        )
    result.prs_count = len(prs)

    return result
