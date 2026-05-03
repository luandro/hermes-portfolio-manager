"""Local commit helper for MVP 6 implementation runner.

Creates per-command author-identity commits inside worktrees via the
allowlisted git wrapper.  Never pushes, amends, or mutates global config.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from portfolio_manager.worktree_git import (
    DEFAULT_TIMEOUTS,
    GitCommandError,
    get_clean_state,
    run_git,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


def make_local_commit(
    workspace: Path,
    *,
    job_id: str,
    issue_number: int,
    message: str,
    author_name: str = "Hermes Implementation Bot",
    author_email: str = "hermes-impl@localhost",
) -> str | None:
    """Stage all changes and create a local commit in *workspace*.

    Returns the SHA of the new commit, or ``None`` if the tree was clean
    (nothing to commit).
    """
    # Sanitize to prevent config injection via embedded newlines
    author_name = author_name.replace("\n", " ").replace("\r", " ")
    author_email = author_email.replace("\n", "").replace("\r", "")

    # 1. Skip if clean
    state = get_clean_state(workspace)
    if state == "clean":
        logger.info("workspace clean, skipping: job=%s issue=%s", job_id, issue_number)
        return None

    # 2. Stage everything
    run_git(["add", "-A"], cwd=workspace, timeout=DEFAULT_TIMEOUTS["add"])

    # 3. Build the commit message with job metadata
    full_message = f"{message}\n\nJob: {job_id} | Issue: #{issue_number}"

    # 4. Create the commit with per-command author config
    #    Uses global '-c' pairs so global gitconfig is never touched.
    #    git -c user.name=X -c user.email=Y commit -m "msg"
    cmd_args: list[str] = [
        "-c",
        f"user.name={author_name}",
        "-c",
        f"user.email={author_email}",
        "commit",
        "-m",
        full_message,
    ]
    result = run_git(cmd_args, cwd=workspace, timeout=DEFAULT_TIMEOUTS["commit"])
    if result.returncode != 0:
        raise GitCommandError(f"local commit failed (rc={result.returncode}): {result.stderr.strip()}")

    # 5. Retrieve the new SHA
    sha_result = run_git(["rev-parse", "HEAD"], cwd=workspace, timeout=DEFAULT_TIMEOUTS["rev-parse"])
    if sha_result.returncode != 0:
        raise GitCommandError("failed to retrieve SHA after commit")
    return sha_result.stdout.strip()
