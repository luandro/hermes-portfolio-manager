"""Path constants, validators, and artifact resolvers for MVP 6 implementation runner."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

# ---------------------------------------------------------------------------
# 1.1 Identifiers
# ---------------------------------------------------------------------------

JOB_ID_RE = re.compile(r"^impl_[0-9a-f-]{8,}$")
HARNESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def generate_job_id() -> str:
    """Return ``impl_<uuid4 hex>``."""
    return f"impl_{uuid4().hex}"


def validate_job_id(job_id: str) -> str:
    """Return *job_id* if valid, else raise ``ValueError``."""
    if not job_id or not JOB_ID_RE.match(job_id):
        raise ValueError(f"Invalid job_id: {job_id!r}")
    return job_id


def validate_harness_id(harness_id: str) -> str:
    """Return *harness_id* if valid, else raise ``ValueError``."""
    if not harness_id or not HARNESS_ID_RE.match(harness_id):
        raise ValueError(f"Invalid harness_id: {harness_id!r}")
    return harness_id


# ---------------------------------------------------------------------------
# 1.2 Artifact path resolvers
# ---------------------------------------------------------------------------


def _validate_project_id(project_id: str) -> None:
    if not _PROJECT_ID_RE.match(project_id):
        raise ValueError(f"Invalid project_id: {project_id!r}")


def implementation_artifact_dir(
    root: Path,
    project_id: str,
    issue_number: int,
    job_id: str,
) -> Path:
    """Return ``$ROOT/artifacts/implementations/<project_id>/issue-<n>/<job_id>/``.

    Validates all inputs and asserts the result is under *root*.
    """
    _validate_project_id(project_id)
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0:
        raise ValueError(f"issue_number must be a positive int, got {issue_number!r}")
    validate_job_id(job_id)

    result = root / "artifacts" / "implementations" / project_id / f"issue-{issue_number}" / job_id
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes root")
    return result


def resolve_source_artifact(
    root: Path,
    conn: object,
    project_id: str,
    issue_number: int,
) -> Path | None:
    """Resolve the issue spec markdown file for the given issue.

    Resolution order:
      1. ``issues.spec_artifact_path`` when it points to an existing file.
      2. ``issues.spec_artifact_path / "spec.md"`` when it points to an existing directory.
      3. ``issue_drafts.artifact_path / "spec.md"`` for the draft linked by
         ``github_issue_number``.

    Returns ``None`` when no spec file is found.  Raises ``ValueError`` if a
    candidate path resolves outside ``$ROOT/artifacts/issues``.
    """
    import sqlite3

    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("conn must be a sqlite3.Connection")

    _validate_project_id(project_id)
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number <= 0:
        raise ValueError(f"issue_number must be a positive int, got {issue_number!r}")

    issues_root = (root / "artifacts" / "issues").resolve()

    def _verify(path: Path) -> Path | None:
        """Return *path* if it exists and is under issues root, else None."""
        if not path.is_absolute():
            path = root / path
        resolved = path.resolve()
        if not resolved.is_relative_to(issues_root):
            raise ValueError(f"Source artifact path escapes root: {resolved}")
        return resolved if resolved.is_file() else None

    # 1. Try issues.spec_artifact_path as a direct file path
    row = conn.execute(
        "SELECT spec_artifact_path FROM issues WHERE project_id=? AND issue_number=?",
        (project_id, issue_number),
    ).fetchone()

    if row and row[0]:
        spec_path = Path(row[0])
        # If it's already a file, verify and return
        result = _verify(spec_path)
        if result is not None:
            return result

        # 2. Try spec_artifact_path / "spec.md" as a directory
        result = _verify(spec_path / "spec.md")
        if result is not None:
            return result

    # 3. Try issue_drafts.artifact_path / "spec.md" for the draft linked by github_issue_number
    draft_row = conn.execute(
        "SELECT artifact_path FROM issue_drafts WHERE github_issue_number=? AND project_id=?",
        (issue_number, project_id),
    ).fetchone()

    if draft_row and draft_row[0]:
        result = _verify(Path(draft_row[0]) / "spec.md")
        if result is not None:
            return result

    return None
