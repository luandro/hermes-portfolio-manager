"""Allowlisted subprocess wrapper + read-only git probes — MVP 5 Phase 2.

Centralizes every git/gh subprocess call for the worktree subsystem so that
security tests can target one module. Forbidden subcommands are rejected
*before* subprocess starts. Stderr is redacted before the caller ever sees it.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Literal

from portfolio_manager.maintenance_artifacts import redact_secrets
from portfolio_manager.worktree_paths import redact_remote_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

#: First-token allowlist for git. Some commands need finer flag-level checks
#: which are enforced in :func:`_check_git_args`.
_GIT_ALLOWED_LEADERS = frozenset(
    {
        "--version",
        "rev-parse",
        "status",
        "remote",
        "worktree",
        "branch",
        "for-each-ref",
        "clone",
        "fetch",
        "switch",
        "merge",
        "merge-base",
    }
)

#: Subcommands explicitly forbidden anywhere in the args list.
_GIT_FORBIDDEN = frozenset(
    {"push", "commit", "reset", "clean", "stash", "rebase", "tag", "rm", "mv", "checkout", "pull"}
)

#: Default per-command timeouts (seconds).
DEFAULT_TIMEOUTS = {
    "status": 30,
    "rev-parse": 30,
    "remote": 30,
    "branch": 30,
    "for-each-ref": 30,
    "worktree": 60,
    "switch": 60,
    "merge": 60,
    "merge-base": 30,
    "fetch": 120,
    "clone": 300,
}


class GitCommandError(Exception):
    """Raised when an arg list violates the allowlist."""


def _check_git_args(args: list[str]) -> None:
    if not args:
        raise GitCommandError("empty git arg list")
    if any(tok in _GIT_FORBIDDEN for tok in args):
        raise GitCommandError(f"forbidden git subcommand in {args!r}")
    leader = args[0]
    if leader not in _GIT_ALLOWED_LEADERS:
        raise GitCommandError(f"git subcommand {leader!r} not allowlisted")
    # Extra restrictions on merge: only --ff-only allowed.
    if leader == "merge" and "--ff-only" not in args:
        raise GitCommandError("git merge requires --ff-only")
    # Extra restrictions on fetch: never --force.
    if leader == "fetch" and any(a in {"--force", "-f"} for a in args):
        raise GitCommandError("git fetch --force is forbidden")


def _redact(text: str) -> str:
    """Redact secrets and credential-bearing URLs from *text*."""
    if not text:
        return text
    out = redact_secrets(text)
    out = re.sub(
        r"(https?|ssh|git)://[^/@\s]+@",
        lambda m: f"{m.group(1)}://***@",
        out,
    )
    return out


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("LC_ALL", "C")
    return env


def run_git(args: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a git command after allowlist + flag checks. Stderr/stdout are redacted."""
    _check_git_args(args)
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("git %s timed out after %ds in %s", args, timeout, cwd)
        return subprocess.CompletedProcess(["git", *args], 124, "", "timeout")
    return subprocess.CompletedProcess(
        result.args, result.returncode, _redact(result.stdout or ""), _redact(result.stderr or "")
    )


_GH_ALLOWED_LEADERS = frozenset({"--version", "auth", "api"})
_GH_FORBIDDEN = frozenset({"create", "edit", "delete", "close", "merge", "review", "comment"})


def run_gh(args: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    """Allowlisted gh wrapper. GET-only on ``api``; no mutation subcommands."""
    if not args:
        raise GitCommandError("empty gh arg list")
    if any(tok in _GH_FORBIDDEN for tok in args):
        raise GitCommandError(f"forbidden gh subcommand in {args!r}")
    leader = args[0]
    if leader not in _GH_ALLOWED_LEADERS:
        raise GitCommandError(f"gh subcommand {leader!r} not allowlisted")
    if "--method" in args:
        idx = args.index("--method")
        method = args[idx + 1] if idx + 1 < len(args) else ""
        if method.upper() != "GET":
            raise GitCommandError(f"gh --method {method!r} not allowed (GET only)")
    try:
        result = subprocess.run(
            ["gh", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["gh", *args], 124, "", "timeout")
    return subprocess.CompletedProcess(
        result.args, result.returncode, _redact(result.stdout or ""), _redact(result.stderr or "")
    )


# ---------------------------------------------------------------------------
# 2.2 Read-only probes
# ---------------------------------------------------------------------------

CleanState = Literal["clean", "dirty_uncommitted", "dirty_untracked", "merge_conflict", "rebase_conflict"]


def is_git_repo(path: Path) -> bool:
    """Return True iff *path* is inside a git work tree."""
    if not path.exists():
        return False
    r = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path, timeout=DEFAULT_TIMEOUTS["rev-parse"])
    return r.returncode == 0 and r.stdout.strip() == "true"


def get_origin_url(path: Path) -> str | None:
    """Return the ``origin`` remote URL or ``None`` if missing."""
    r = run_git(["remote", "get-url", "origin"], cwd=path, timeout=DEFAULT_TIMEOUTS["remote"])
    if r.returncode != 0:
        return None
    val = r.stdout.strip()
    return val or None


def _git_path(path: Path, name: str) -> Path:
    r = run_git(["rev-parse", "--git-path", name], cwd=path, timeout=DEFAULT_TIMEOUTS["rev-parse"])
    if r.returncode != 0 or not r.stdout.strip():
        return path / f"__missing_{name}__"
    out = Path(r.stdout.strip())
    return out if out.is_absolute() else path / out


def get_clean_state(path: Path) -> CleanState:
    """Classify the working-tree state without mutating anything."""
    if _git_path(path, "rebase-merge").exists() or _git_path(path, "rebase-apply").exists():
        return "rebase_conflict"
    if _git_path(path, "MERGE_HEAD").exists():
        return "merge_conflict"
    r = run_git(["status", "--porcelain=v1"], cwd=path, timeout=DEFAULT_TIMEOUTS["status"])
    modified: list[str] = []
    untracked: list[str] = []
    conflict: list[str] = []
    for line in (r.stdout or "").splitlines():
        if not line:
            continue
        xy = line[:2]
        if xy in ("UU", "AA", "DD", "AU", "UA", "DU", "UD"):
            conflict.append(line[3:])
        elif xy == "??":
            untracked.append(line[3:])
        elif xy[0] not in (" ", "?") or xy[1] not in (" ", "?"):
            modified.append(line[3:])
    if conflict:
        return "merge_conflict"
    if modified:
        return "dirty_uncommitted"
    if untracked:
        return "dirty_untracked"
    return "clean"


def branch_exists(path: Path, name: str, *, remote: bool = False) -> bool:
    """True iff a local (or origin/) branch *name* exists at *path*."""
    ref = f"refs/remotes/origin/{name}" if remote else f"refs/heads/{name}"
    r = run_git(
        ["for-each-ref", "--format=%(refname)", ref],
        cwd=path,
        timeout=DEFAULT_TIMEOUTS["for-each-ref"],
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def local_branch_diverges_from_origin(path: Path, branch: str) -> bool:
    """True iff local *branch* has commits not in ``origin/<branch>``.

    Uses ``git merge-base --is-ancestor local origin/branch``: exit 0 means
    local is an ancestor of origin (no divergence); non-zero means diverges.
    """
    if not branch_exists(path, branch, remote=False) or not branch_exists(path, branch, remote=True):
        return False
    r = run_git(
        ["merge-base", "--is-ancestor", branch, f"origin/{branch}"],
        cwd=path,
        timeout=DEFAULT_TIMEOUTS["merge-base"],
    )
    return r.returncode != 0


def list_worktrees(repo_path: Path) -> list[dict[str, str]]:
    """Parse ``git worktree list --porcelain`` into a list of dicts."""
    r = run_git(["worktree", "list", "--porcelain"], cwd=repo_path, timeout=DEFAULT_TIMEOUTS["worktree"])
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in (r.stdout or "").splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        if " " in line:
            key, val = line.split(" ", 1)
        else:
            key, val = line, ""
        current[key] = val
    if current:
        entries.append(current)
    return entries


__all__ = [
    "DEFAULT_TIMEOUTS",
    "GitCommandError",
    "branch_exists",
    "get_clean_state",
    "get_origin_url",
    "is_git_repo",
    "list_worktrees",
    "local_branch_diverges_from_origin",
    "redact_remote_url",
    "run_gh",
    "run_git",
]
