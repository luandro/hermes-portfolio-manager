"""Tests for portfolio_manager.implementation_paths — validators and path resolvers (Phase 1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from portfolio_manager.implementation_paths import (
    JOB_ID_RE,
    generate_job_id,
    implementation_artifact_dir,
    resolve_source_artifact,
    validate_harness_id,
    validate_job_id,
)
from portfolio_manager.state import init_state, open_state, upsert_issue, upsert_project

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_root(tmp_path: Path) -> Path:
    """Create a minimal root directory structure."""
    root = tmp_path / "root"
    root.mkdir()
    return root


def _make_db(root: Path):
    """Open and initialise a state database under *root*."""
    conn = open_state(root)
    init_state(conn)
    return conn


def _insert_project(conn, project_id: str = "test-project") -> None:
    from portfolio_manager.config import GithubRef, ProjectConfig

    cfg = ProjectConfig(
        id=project_id,
        name="Test",
        repo="https://github.com/o/r",
        github=GithubRef(owner="o", repo="r"),
        priority="medium",
        status="active",
    )
    upsert_project(conn, cfg)


# ---------------------------------------------------------------------------
# 1.1 job_id + harness_id validators
# ---------------------------------------------------------------------------


def test_generate_job_id_format() -> None:
    job_id = generate_job_id()
    assert JOB_ID_RE.match(job_id), f"Generated job_id {job_id!r} does not match JOB_ID_RE"


def test_validate_job_id_accepts_generated() -> None:
    job_id = generate_job_id()
    assert validate_job_id(job_id) == job_id


def test_validate_job_id_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="Invalid job_id"):
        validate_job_id("impl_../etc/passwd")


def test_validate_job_id_rejects_uppercase() -> None:
    with pytest.raises(ValueError, match="Invalid job_id"):
        validate_job_id("impl_ABCDEF123456")


def test_validate_job_id_rejects_empty() -> None:
    with pytest.raises(ValueError, match="Invalid job_id"):
        validate_job_id("")


def test_validate_harness_id_accepts_alnum_dash_underscore() -> None:
    assert validate_harness_id("forge") == "forge"
    assert validate_harness_id("my-harness_1") == "my-harness_1"
    assert validate_harness_id("a") == "a"


def test_validate_harness_id_rejects_shell_metachar() -> None:
    with pytest.raises(ValueError, match="Invalid harness_id"):
        validate_harness_id("forge;rm -rf /")


def test_validate_harness_id_rejects_path_separator() -> None:
    with pytest.raises(ValueError, match="Invalid harness_id"):
        validate_harness_id("forge/sub")


def test_validate_harness_id_rejects_overlong() -> None:
    with pytest.raises(ValueError, match="Invalid harness_id"):
        validate_harness_id("a" * 65)


# ---------------------------------------------------------------------------
# 1.2 Artifact path resolvers
# ---------------------------------------------------------------------------


def test_implementation_artifact_dir_under_root(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    job_id = generate_job_id()
    result = implementation_artifact_dir(root, "my-project", 1, job_id)
    expected = root / "artifacts" / "implementations" / "my-project" / "issue-1" / job_id
    assert result == expected
    assert result.resolve().is_relative_to(root.resolve())


def test_implementation_artifact_dir_rejects_path_traversal_in_project_id(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    job_id = generate_job_id()
    with pytest.raises(ValueError, match="Invalid project_id"):
        implementation_artifact_dir(root, "../etc", 1, job_id)


def test_implementation_artifact_dir_rejects_negative_issue_number(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    job_id = generate_job_id()
    with pytest.raises(ValueError, match="issue_number must be a positive int"):
        implementation_artifact_dir(root, "my-project", -1, job_id)


def test_implementation_artifact_dir_rejects_invalid_job_id(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    with pytest.raises(ValueError, match="Invalid job_id"):
        implementation_artifact_dir(root, "my-project", 1, "bad_job_id")


def test_resolve_source_artifact_for_issue_number_returns_existing_draft_path(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    conn = _make_db(root)
    _insert_project(conn)

    # Create the artifact directory and spec.md file on disk
    artifact_dir = root / "artifacts" / "issues" / "test-project" / "draft_abc123"
    artifact_dir.mkdir(parents=True)
    spec_file = artifact_dir / "spec.md"
    spec_file.write_text("# Spec\n")

    # Insert an issue with spec_artifact_path pointing to the artifact directory
    upsert_issue(
        conn,
        "test-project",
        {
            "number": 42,
            "title": "Test issue",
            "state": "open",
        },
    )
    conn.execute(
        "UPDATE issues SET spec_artifact_path=? WHERE project_id=? AND issue_number=?",
        (str(artifact_dir), "test-project", 42),
    )
    conn.commit()

    result = resolve_source_artifact(root, conn, "test-project", 42)
    assert result is not None
    assert result.name == "spec.md"
    assert result.resolve().is_relative_to((root / "artifacts" / "issues").resolve())

    conn.close()


def test_resolve_source_artifact_returns_none_when_missing(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    conn = _make_db(root)
    _insert_project(conn)

    # Insert an issue but no spec artifact
    upsert_issue(
        conn,
        "test-project",
        {
            "number": 99,
            "title": "No spec",
            "state": "open",
        },
    )

    result = resolve_source_artifact(root, conn, "test-project", 99)
    assert result is None

    conn.close()


def test_resolve_source_artifact_rejects_path_outside_root(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    conn = _make_db(root)
    _insert_project(conn)

    # Insert an issue with spec_artifact_path pointing outside root
    upsert_issue(
        conn,
        "test-project",
        {
            "number": 7,
            "title": "Evil",
            "state": "open",
        },
    )
    evil_path = tmp_path / "outside-root" / "spec.md"
    evil_path.parent.mkdir(parents=True)
    evil_path.write_text("evil")
    conn.execute(
        "UPDATE issues SET spec_artifact_path=? WHERE project_id=? AND issue_number=?",
        (str(evil_path), "test-project", 7),
    )
    conn.commit()

    with pytest.raises(ValueError, match="escapes root"):
        resolve_source_artifact(root, conn, "test-project", 7)

    conn.close()
