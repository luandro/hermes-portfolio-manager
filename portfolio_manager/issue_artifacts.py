"""Issue artifact path safety and atomic file writing — MVP 3.

Handles draft ID validation, artifact root resolution, atomic writes.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_DRAFT_ID_RE = re.compile(r"^draft_[a-z0-9][a-z0-9-]*$")
_PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def validate_draft_id(draft_id: str) -> None:
    """Raise ValueError if draft_id is not a safe identifier."""
    if not _DRAFT_ID_RE.match(draft_id):
        raise ValueError(f"Invalid draft ID: {draft_id!r}")


def generate_draft_id() -> str:
    """Return a unique draft ID using UUID4."""
    return f"draft_{uuid.uuid4()}"


def _validate_project_id(project_id: str) -> None:
    if not _PROJECT_ID_RE.match(project_id):
        raise ValueError(f"Invalid project ID: {project_id!r}")


def issue_artifact_root(root: Path, project_id: str, draft_id: str) -> Path:
    """Resolve the artifact directory, validating inputs and preventing path escape."""
    _validate_project_id(project_id)
    validate_draft_id(draft_id)
    result = root / "artifacts" / "issues" / project_id / draft_id
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes root")
    return result


def write_text_atomic(path: Path, content: str) -> None:
    """Write content to a temp file, then atomically replace the target."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(path))
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
    # Best-effort fsync on parent directory
    try:
        dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
    except (OSError, AttributeError):
        return
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def write_json_atomic(path: Path, data: dict[str, object]) -> None:
    """Serialize data as JSON and write atomically."""
    write_text_atomic(path, json.dumps(data, indent=2))


def write_issue_artifact_files(root: Path, project_id: str, draft_id: str, content: dict[str, object]) -> None:
    """Write all six required artifact files atomically."""
    artifact_dir = issue_artifact_root(root, project_id, draft_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    write_text_atomic(artifact_dir / "original-input.md", str(content.get("original_input", "")))
    write_text_atomic(artifact_dir / "brainstorm.md", str(content.get("brainstorm_notes", "")))
    write_text_atomic(artifact_dir / "questions.md", str(content.get("questions", "")))
    write_text_atomic(artifact_dir / "spec.md", str(content.get("spec_body", "")))
    write_text_atomic(artifact_dir / "github-issue.md", str(content.get("github_body", "")))

    metadata: dict[str, object] = {
        "draft_id": draft_id,
        "project_id": project_id,
        "title": content.get("title", ""),
        "issue_kind": content.get("issue_kind", ""),
        "readiness": content.get("readiness", 0.0),
    }
    write_json_atomic(artifact_dir / "metadata.json", metadata)


def write_creation_attempt(artifact_dir: Path) -> None:
    """Write a timestamped creation-attempt.json."""
    data: dict[str, object] = {"attempted_at": datetime.now(tz=UTC).isoformat()}
    write_json_atomic(artifact_dir / "creation-attempt.json", data)


def write_github_created(artifact_dir: Path, issue_number: int, issue_url: str) -> None:
    """Write github-created.json with issue number and URL."""
    data: dict[str, object] = {"issue_number": issue_number, "issue_url": issue_url}
    write_json_atomic(artifact_dir / "github-created.json", data)


def write_creation_error(artifact_dir: Path, error: str) -> None:
    """Write creation-error.json with error message."""
    data: dict[str, object] = {"error": error}
    write_json_atomic(artifact_dir / "creation-error.json", data)


def read_github_created_if_exists(artifact_dir: Path) -> dict[str, object] | None:
    """Return github-created.json contents, or None if it doesn't exist."""
    path = artifact_dir / "github-created.json"
    if not path.exists():
        return None
    try:
        data: object = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def read_issue_artifact(root: Path, project_id: str, draft_id: str, filename: str) -> str | None:
    """Read a single artifact file. Returns None if not found."""
    artifact_dir = issue_artifact_root(root, project_id, draft_id)
    if "/" in filename or ".." in filename or filename.startswith("."):
        raise ValueError(f"Invalid filename: {filename!r}")
    path = artifact_dir / filename
    if not path.resolve().is_relative_to(artifact_dir.resolve()):
        raise ValueError(f"Path traversal detected: {filename!r}")
    if not path.exists():
        return None
    try:
        return path.read_text()
    except (UnicodeDecodeError, OSError):
        return None


def read_issue_metadata(root: Path, project_id: str, draft_id: str) -> dict[str, object] | None:
    """Read metadata.json for a draft. Returns None if not found."""
    artifact_dir = issue_artifact_root(root, project_id, draft_id)
    path = artifact_dir / "metadata.json"
    if not path.exists():
        return None
    try:
        data: object = json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data
