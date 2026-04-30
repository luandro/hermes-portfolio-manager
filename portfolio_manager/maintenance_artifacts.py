"""Maintenance artifact path safety and secret redaction — Phase 3.

Provides path helpers, traversal protection, secret redaction, and artifact
writing for maintenance run artifacts.
"""

from __future__ import annotations

import re
from pathlib import Path

# Artifact base directory relative to root
_ARTIFACT_BASE = Path("artifacts") / "maintenance"

# Run ID validation: alphanumeric, hyphens, underscores only
_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

# Secret patterns to redact (order matters — longer prefixes first)
_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"\b(github_pat_)[A-Za-z0-9_\-]+", r"\1***"),
    (r"\b(gh[rouspa]_)[A-Za-z0-9_\-]+", r"\1***"),
    (r"\b(sk-)[A-Za-z0-9_\-]+", r"\1***"),
    (r"\bBearer\s+\S+", "Bearer ***"),
    (r"(?<![\w])(token=)\S+", r"\1***"),
    (r"(?<![\w])(password=)\S+", r"\1***"),
]


def get_artifact_dir(root: Path, run_id: str) -> Path:
    """Return the resolved artifact directory for a run, rejecting path traversal."""
    if "\x00" in run_id:
        raise ValueError("Invalid run_id: null byte detected")
    if not _RUN_ID_RE.match(run_id):
        raise ValueError(f"Invalid run_id: {run_id!r}")
    artifact_base_resolved = (root / _ARTIFACT_BASE).resolve()
    result = (artifact_base_resolved / run_id).resolve()
    if not result.is_relative_to(artifact_base_resolved):
        raise ValueError(f"Path traversal detected for run_id: {run_id!r}")
    return result


def ensure_artifact_dir(root: Path, run_id: str) -> Path:
    """Return artifact dir, creating it if needed."""
    d = get_artifact_dir(root, run_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def redact_secrets(text: str) -> str:
    """Redact known secret/token patterns from a string.

    Replaces the secret value with ``***`` while preserving the prefix
    (e.g. ``ghp_abc123`` -> ``ghp_***``).
    """
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def write_artifact(root: Path, run_id: str, filename: str, content: str) -> Path:
    """Write redacted content to the artifact directory.

    Returns the path of the written file.
    """
    d = ensure_artifact_dir(root, run_id)
    # Reject suspicious filenames
    if (
        not filename
        or not filename.strip()
        or "/" in filename
        or "\\" in filename
        or ".." in filename
        or filename.startswith(".")
    ):
        raise ValueError(f"Invalid filename: {filename!r}")
    target = d / filename
    if not target.resolve().is_relative_to(d.resolve()):
        raise ValueError(f"Path traversal detected in filename: {filename!r}")
    safe_content = redact_secrets(content)
    target.write_text(safe_content, encoding="utf-8")
    return target
