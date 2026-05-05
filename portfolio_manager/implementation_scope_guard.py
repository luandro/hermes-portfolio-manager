"""Scope guard for MVP 6 implementation runner.

Validates that changed files stay within the allowed spec scope,
respect protected paths, and don't exceed the configured file count limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch


@dataclass
class ScopeCheck:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    protected_violations: list[str] = field(default_factory=list)
    out_of_scope_files: list[str] = field(default_factory=list)


def _matches_any_pattern(path: str, patterns: list[str]) -> bool:
    """Check if a path matches any of the given glob patterns."""
    return any(fnmatch(path, pattern) for pattern in patterns)


def check_scope(
    *,
    changed_files: list[str],
    spec_scope: list[str],
    protected_paths: list[str],
    max_files_changed: int,
    fix_scope: list[str] | None = None,
) -> ScopeCheck:
    """Validate changed files against scope constraints.

    Parameters
    ----------
    changed_files
        List of POSIX-relative file paths changed by the harness.
    spec_scope
        Glob patterns defining the allowed scope for initial implementation.
    protected_paths
        Glob patterns for paths that must never be changed.
    max_files_changed
        Maximum number of files allowed to change.
    fix_scope
        For review_fix: approved fix scope patterns. If ``None``, use spec_scope.
    """
    reasons: list[str] = []
    protected_violations: list[str] = []
    out_of_scope_files: list[str] = []

    # 1. Check max_files_changed
    if len(changed_files) > max_files_changed:
        reasons.append(f"changed_files_count_{len(changed_files)}_exceeds_max_{max_files_changed}")

    # 2. Check protected_paths
    for path in changed_files:
        if _matches_any_pattern(path, protected_paths):
            protected_violations.append(path)

    if protected_violations:
        reasons.append(f"protected_path_violations_{len(protected_violations)}")

    # 3-4. Check scope
    # If fix_scope is provided (review_fix), check against fix_scope
    # If fix_scope is None (initial_implementation), check against spec_scope
    scope_patterns = fix_scope if fix_scope is not None else spec_scope

    if scope_patterns:
        for path in changed_files:
            if not _matches_any_pattern(path, scope_patterns):
                out_of_scope_files.append(path)

        if out_of_scope_files:
            scope_label = "fix_scope" if fix_scope is not None else "spec_scope"
            reasons.append(f"{scope_label}_violations_{len(out_of_scope_files)}")

    ok = len(reasons) == 0

    return ScopeCheck(
        ok=ok,
        reasons=reasons,
        changed_files=changed_files,
        protected_violations=protected_violations,
        out_of_scope_files=out_of_scope_files,
    )
