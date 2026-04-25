"""Tests for portfolio_manager tool handlers.

Uses monkeypatch/mock to avoid real filesystem/GitHub calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from portfolio_manager.tools import (
    _handle_portfolio_config_validate,
    _handle_portfolio_github_sync,
    _handle_portfolio_heartbeat,
    _handle_portfolio_ping,
    _handle_portfolio_project_list,
    _handle_portfolio_status,
    _handle_portfolio_worktree_inspect,
)

FIXTURES = Path(__file__).parent / "fixtures"
VALID_YAML = (FIXTURES / "projects.valid.yaml").read_text()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse(result: str) -> dict[str, Any]:
    return json.loads(result)


def _make_root_with_config(tmp_path: Path) -> Path:
    """Create a temp root with valid config."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "projects.yaml").write_text(VALID_YAML)
    return tmp_path


# ---------------------------------------------------------------------------
# portfolio_ping
# ---------------------------------------------------------------------------


def test_portfolio_ping() -> None:
    """portfolio_ping returns the exact shared tool result shape."""
    result = _parse(_handle_portfolio_ping({}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_ping"
    assert result["data"] == {}


# ---------------------------------------------------------------------------
# portfolio_config_validate
# ---------------------------------------------------------------------------


def test_config_validate_success(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    result = _parse(_handle_portfolio_config_validate({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_config_validate"
    assert result["data"]["valid"] is True
    assert result["data"]["project_count"] == 4
    # Directories should be created
    assert (root / "state").is_dir()
    assert (root / "worktrees").is_dir()


def test_config_validate_missing_config(tmp_path: Path) -> None:
    result = _parse(_handle_portfolio_config_validate({"root": str(tmp_path)}))

    assert result["status"] == "blocked"
    assert result["tool"] == "portfolio_config_validate"
    assert result["data"]["valid"] is False


def test_config_validate_no_root_arg(tmp_path: Path) -> None:
    """When no root arg, resolve_root should use env or default."""
    with patch("portfolio_manager.tools.resolve_root", return_value=tmp_path):
        # No config -> blocked
        result = _parse(_handle_portfolio_config_validate({}))
        assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# portfolio_project_list
# ---------------------------------------------------------------------------


def test_project_list_success(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    result = _parse(_handle_portfolio_project_list({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_project_list"
    # Default excludes archived and paused -> 2 active projects
    assert len(result["data"]["projects"]) == 2
    assert "summary" in result


def test_project_list_include_archived(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    result = _parse(_handle_portfolio_project_list({"root": str(root), "include_archived": True}))

    assert result["status"] == "success"
    # include_archived but still excludes paused -> 3 (2 active + 1 archived)
    assert len(result["data"]["projects"]) == 3


def test_project_list_filter_by_status(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    result = _parse(_handle_portfolio_project_list({"root": str(root), "status": "active"}))

    assert result["status"] == "success"
    assert len(result["data"]["projects"]) == 2
    assert all(p["status"] == "active" for p in result["data"]["projects"])


def test_project_list_missing_config(tmp_path: Path) -> None:
    result = _parse(_handle_portfolio_project_list({"root": str(tmp_path)}))

    assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# portfolio_github_sync
# ---------------------------------------------------------------------------


def test_github_sync_blocked_no_gh(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    with patch(
        "portfolio_manager.tools.check_gh_available",
        return_value=MagicMock(available=False, message="gh not installed"),
    ):
        result = _parse(_handle_portfolio_github_sync({"root": str(root)}))

    assert result["status"] == "blocked"
    assert result["tool"] == "portfolio_github_sync"


def test_github_sync_blocked_no_auth(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch(
            "portfolio_manager.tools.check_gh_auth",
            return_value=MagicMock(available=False, message="not authenticated"),
        ),
    ):
        result = _parse(_handle_portfolio_github_sync({"root": str(root)}))

    assert result["status"] == "blocked"


def test_github_sync_success(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    mock_sync_result = MagicMock(
        project_id="comapeo-cloud-app",
        issues_count=3,
        prs_count=1,
        warnings=[],
        error=None,
    )

    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.check_gh_auth", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.sync_project_github", return_value=mock_sync_result),
    ):
        result = _parse(_handle_portfolio_github_sync({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_github_sync"
    assert result["data"]["projects_synced"] >= 1


def test_github_sync_single_project(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    mock_sync_result = MagicMock(
        project_id="comapeo-cloud-app",
        issues_count=5,
        prs_count=2,
        warnings=[],
        error=None,
    )

    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.check_gh_auth", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.sync_project_github", return_value=mock_sync_result),
    ):
        result = _parse(_handle_portfolio_github_sync({"root": str(root), "project_id": "comapeo-cloud-app"}))

    assert result["status"] == "success"
    assert result["data"]["projects_synced"] == 1


# ---------------------------------------------------------------------------
# portfolio_worktree_inspect
# ---------------------------------------------------------------------------


def test_worktree_inspect_success(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    from portfolio_manager.worktree import WorktreeInspection

    mock_inspections = [
        WorktreeInspection(path="/fake/base", project_id="comapeo-cloud-app", state="clean", branch_name="main"),
    ]

    with patch("portfolio_manager.tools.inspect_project_worktrees", return_value=mock_inspections):
        result = _parse(_handle_portfolio_worktree_inspect({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_worktree_inspect"
    assert result["data"]["projects_inspected"] >= 1


def test_worktree_inspect_single_project(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    from portfolio_manager.worktree import WorktreeInspection

    mock_inspections = [
        WorktreeInspection(path="/fake/base", project_id="edt-next", state="missing"),
    ]

    with patch("portfolio_manager.tools.inspect_project_worktrees", return_value=mock_inspections):
        result = _parse(_handle_portfolio_worktree_inspect({"root": str(root), "project_id": "edt-next"}))

    assert result["status"] == "success"
    assert result["data"]["projects_inspected"] == 1


def test_worktree_inspect_missing_config(tmp_path: Path) -> None:
    result = _parse(_handle_portfolio_worktree_inspect({"root": str(tmp_path)}))

    assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# portfolio_status
# ---------------------------------------------------------------------------


def test_portfolio_status_no_refresh(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    # Need state DB with schema
    from portfolio_manager.state import init_state, open_state

    conn = open_state(root)
    init_state(conn)
    conn.close()

    result = _parse(_handle_portfolio_status({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_status"
    assert "summary" in result


def test_portfolio_status_with_refresh(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    from portfolio_manager.state import init_state, open_state

    conn = open_state(root)
    init_state(conn)
    conn.close()

    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.check_gh_auth", return_value=MagicMock(available=True)),
        patch(
            "portfolio_manager.tools.sync_project_github",
            return_value=MagicMock(issues_count=0, prs_count=0, warnings=[], error=None),
        ),
        patch("portfolio_manager.tools.inspect_project_worktrees", return_value=[]),
    ):
        result = _parse(_handle_portfolio_status({"root": str(root), "refresh": True}))

    assert result["status"] == "success"


def test_portfolio_status_needs_user_filter(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    from portfolio_manager.state import init_state, open_state

    conn = open_state(root)
    init_state(conn)
    conn.close()

    result = _parse(_handle_portfolio_status({"root": str(root), "filter": "needs_user"}))

    assert result["status"] == "success"


# ---------------------------------------------------------------------------
# portfolio_heartbeat
# ---------------------------------------------------------------------------


def test_heartbeat_success(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)

    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.check_gh_auth", return_value=MagicMock(available=True)),
        patch(
            "portfolio_manager.tools.sync_project_github",
            return_value=MagicMock(issues_count=5, prs_count=2, warnings=[], error=None),
        ),
        patch("portfolio_manager.tools.inspect_project_worktrees", return_value=[]),
    ):
        result = _parse(_handle_portfolio_heartbeat({"root": str(root)}))

    assert result["status"] == "success"
    assert result["tool"] == "portfolio_heartbeat"
    assert result["data"]["projects_checked"] >= 1
    assert "summary" in result


def test_heartbeat_blocked_by_lock(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)
    from portfolio_manager.state import init_state, open_state

    conn = open_state(root)
    init_state(conn)
    # Pre-acquire the lock
    conn.execute(
        "INSERT INTO locks (name, owner, acquired_at, expires_at) VALUES (?, ?, datetime('now'), datetime('now', '+900 seconds'))",
        ("heartbeat:portfolio", "other-owner"),
    )
    conn.commit()
    conn.close()

    result = _parse(_handle_portfolio_heartbeat({"root": str(root)}))

    assert result["status"] == "blocked"
    assert result["reason"] == "heartbeat_lock_already_held"


def test_heartbeat_blocked_missing_config(tmp_path: Path) -> None:
    # No config dir
    result = _parse(_handle_portfolio_heartbeat({"root": str(tmp_path)}))

    assert result["status"] == "blocked"


def test_heartbeat_blocked_no_gh(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)

    with patch(
        "portfolio_manager.tools.check_gh_available",
        return_value=MagicMock(available=False, message="gh not installed"),
    ):
        result = _parse(_handle_portfolio_heartbeat({"root": str(root)}))

    assert result["status"] == "blocked"


def test_heartbeat_continues_on_project_failure(tmp_path: Path) -> None:
    root = _make_root_with_config(tmp_path)

    call_count = 0

    def flaky_sync(conn: Any, project: Any, max_items: int = 50) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(
                project_id=project.id,
                issues_count=0,
                prs_count=0,
                warnings=["repo inaccessible"],
                error="repo inaccessible",
            )
        return MagicMock(
            project_id=project.id,
            issues_count=3,
            prs_count=1,
            warnings=[],
            error=None,
        )

    with (
        patch("portfolio_manager.tools.check_gh_available", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.check_gh_auth", return_value=MagicMock(available=True)),
        patch("portfolio_manager.tools.sync_project_github", side_effect=flaky_sync),
        patch("portfolio_manager.tools.inspect_project_worktrees", return_value=[]),
    ):
        result = _parse(_handle_portfolio_heartbeat({"root": str(root)}))

    # Should still succeed overall
    assert result["status"] == "success"
    assert result["data"]["projects_checked"] >= 2
