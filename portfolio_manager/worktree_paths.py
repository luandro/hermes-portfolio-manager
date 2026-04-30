"""Pure validators for MVP 5 — branch names, path containment, URL forms.

These functions are the security boundary. They never touch subprocess
or perform I/O beyond ``Path.resolve``/``Path.is_symlink`` checks.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# 1.1 Branch name validator
# ---------------------------------------------------------------------------

#: Allowed branch shape: ``agent/<project_id>/issue-<n>``.
#: Project segment must start alnum, only ``[a-z0-9_-]``, length 2-64.
#: Issue number: positive integer, no leading zero, up to 10 digits.
BRANCH_REGEX = re.compile(r"^agent/[a-z0-9][a-z0-9_-]{1,63}/issue-[1-9][0-9]{0,9}$")

# Disallowed substrings beyond the regex (defense-in-depth against
# git ref-format quirks that the regex already covers but we re-check
# explicitly for clarity in error messages).
_FORBIDDEN_SUBSTRINGS = ("..", "@{", "//", "\\", " ", "\t", "\n", "\r")


def default_branch_name(project_id: str, issue_number: int) -> str:
    """Return the canonical branch name for *project_id* + *issue_number*."""
    if issue_number <= 0:
        raise ValueError(f"issue_number must be positive, got {issue_number}")
    return f"agent/{project_id}/issue-{issue_number}"


def validate_branch_name(name: str) -> str:
    """Return *name* unchanged if valid; raise ``ValueError`` otherwise."""
    if not isinstance(name, str) or not name:
        raise ValueError("branch name must be a non-empty string")
    if name.startswith("-") or name.startswith("/") or name.endswith("/") or name.endswith("."):
        raise ValueError(f"invalid branch name: {name!r}")
    if name.startswith("refs/heads/"):
        raise ValueError(f"branch name must not include refs/heads/: {name!r}")
    for bad in _FORBIDDEN_SUBSTRINGS:
        if bad in name:
            raise ValueError(f"branch name contains forbidden sequence {bad!r}: {name!r}")
    if not BRANCH_REGEX.match(name):
        raise ValueError(f"branch name does not match {BRANCH_REGEX.pattern}: {name!r}")
    return name


# ---------------------------------------------------------------------------
# 1.2 Path containment + symlink escape guard
# ---------------------------------------------------------------------------


def resolve_under_root(path: Path, root: Path) -> Path:
    """Resolve *path* and assert it lies under *root*. Returns the resolved path."""
    resolved_root = Path(root).resolve(strict=False)
    resolved = Path(path).resolve(strict=False)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"path escapes root: {resolved} not under {resolved_root}")
    return resolved


def assert_under_worktrees_root(path: Path, root: Path) -> Path:
    """Same as :func:`resolve_under_root` but pinned to ``$ROOT/worktrees``."""
    worktrees_root = (Path(root) / "worktrees").resolve(strict=False)
    resolved = Path(path).resolve(strict=False)
    if not resolved.is_relative_to(worktrees_root):
        raise ValueError(f"path escapes worktrees root: {resolved} not under {worktrees_root}")
    return resolved


def render_issue_worktree_path(
    pattern: str,
    project_id: str,
    issue_number: int,
    root: Path,
) -> Path:
    """Render an issue worktree path from *pattern* and assert containment.

    Substitutes only ``{project_id}`` and ``{issue_number}``. *issue_number* must
    be a positive int; *project_id* must not contain path separators or ``..``.
    """
    if not isinstance(issue_number, int) or isinstance(issue_number, bool):
        raise TypeError(f"issue_number must be int, got {type(issue_number).__name__}")
    if issue_number <= 0:
        raise ValueError(f"issue_number must be positive, got {issue_number}")
    if "/" in project_id or "\\" in project_id or ".." in project_id or project_id.startswith("."):
        raise ValueError(f"project_id contains illegal chars: {project_id!r}")
    try:
        rendered = pattern.format(project_id=project_id, issue_number=issue_number)
    except (KeyError, IndexError) as exc:
        raise ValueError(f"invalid issue worktree pattern: {pattern!r}") from exc
    return assert_under_worktrees_root(Path(rendered), root)


def has_escaping_symlink(path: Path, root: Path) -> bool:
    """Return True if *path* (or any ancestor inside root) is a symlink that escapes root."""
    resolved_root = Path(root).resolve(strict=False)
    p = Path(path)
    # Walk from the given path up through ancestors until we reach the root.
    # Check each component for a symlink that resolves outside root.
    current = p
    while True:
        if current.is_symlink():
            try:
                target = current.resolve(strict=False)
            except OSError:
                return True
            if not target.is_relative_to(resolved_root):
                return True
        # Stop when we reach or pass the root
        try:
            if current.resolve(strict=False) == resolved_root or current.parent == current:
                break
        except OSError:
            break
        current = current.parent
    return False


# ---------------------------------------------------------------------------
# 1.3 Remote URL normalizer
# ---------------------------------------------------------------------------

_GITHUB_HOSTS = {"github.com", "www.github.com"}
_SCP_LIKE = re.compile(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<path>.+)$")


def _strip_git_suffix(s: str) -> str:
    return s[:-4] if s.endswith(".git") else s


def normalize_remote_url(url: str) -> str:
    """Collapse equivalent remote URL forms to a canonical key.

    GitHub forms (https/ssh/scp) → ``github:<owner>/<repo>``.
    Local file:// or absolute paths → ``file:<resolved-absolute-path>``.
    Other hosts → ``<host>:<owner>/<repo>``.
    """
    s = url.strip().rstrip("/")
    if not s:
        return ""
    # SCP-like ``git@host:owner/repo``
    m = _SCP_LIKE.match(s)
    if m:
        host = m.group("host").lower()
        path = _strip_git_suffix(m.group("path").lstrip("/"))
        return f"github:{path}" if host in _GITHUB_HOSTS else f"{host}:{path}"
    # Absolute local path
    if s.startswith("/"):
        return f"file:{Path(s).resolve()}"
    parsed = urlparse(s)
    if parsed.scheme == "file":
        return f"file:{Path(parsed.path).resolve()}"
    if parsed.scheme in ("http", "https", "ssh", "git"):
        host = (parsed.hostname or "").lower()
        path = _strip_git_suffix(parsed.path.lstrip("/").rstrip("/"))
        return f"github:{path}" if host in _GITHUB_HOSTS else f"{host}:{path}"
    # Fallback: treat as opaque local path
    return f"file:{Path(s).resolve()}"


def remotes_equal(a: str, b: str) -> bool:
    """True iff *a* and *b* normalize to the same remote key."""
    return normalize_remote_url(a) == normalize_remote_url(b)


def redact_remote_url(url: str) -> str:
    """Return *url* with any ``user:password@`` segment replaced by ``***``."""
    return re.sub(r"(https?|ssh|git)://[^/@]+@", lambda m: f"{m.group(1)}://***@", url)
