"""Phase 6 + Phase 7 — SQLite state integration tests and tool handler tests.

Verifies that upsert_project() correctly round-trips project data to/from
SQLite, including insert, update, archive-without-delete, and conversion
from AdminProjectConfig to ProjectConfig.

Phase 7 tests verify all 10 MVP 2 tool handlers via their public function
interfaces with tmp_path as system root.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch as mock_patch

import yaml

from portfolio_manager.admin_models import AdminProjectConfig
from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.state import init_state, open_state, upsert_issue, upsert_project
from portfolio_manager.tools import (
    _handle_portfolio_project_add,
    _handle_portfolio_project_archive,
    _handle_portfolio_project_config_backup,
    _handle_portfolio_project_explain,
    _handle_portfolio_project_pause,
    _handle_portfolio_project_remove,
    _handle_portfolio_project_resume,
    _handle_portfolio_project_set_auto_merge,
    _handle_portfolio_project_set_priority,
    _handle_portfolio_project_update,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_and_init(tmp: Path) -> object:
    conn = open_state(tmp)
    init_state(conn)
    return conn


def _make_project(project_id: str = "test-proj", **overrides) -> ProjectConfig:
    defaults = dict(
        id=project_id,
        name="Test Project",
        repo="git@github.com:test/test.git",
        github=GithubRef(owner="test", repo="test"),
        priority="high",
        status="active",
        default_branch="main",
        local=LocalPaths(
            base_path=Path("/tmp/test"),
            issue_worktree_pattern="/tmp/test-issue-{issue_number}",
        ),
    )
    defaults.update(overrides)
    return ProjectConfig(**defaults)


def _admin_to_project_config(admin: AdminProjectConfig) -> ProjectConfig:
    """Convert an AdminProjectConfig to a ProjectConfig for upsert."""
    return ProjectConfig(
        id=admin.id,
        name=admin.name,
        repo=admin.repo,
        github=GithubRef(owner=admin.github_owner, repo=admin.github_repo),
        priority=admin.priority,
        status=admin.status,
        default_branch=admin.default_branch,
        local=LocalPaths(
            base_path=Path("/tmp") / admin.id,
            issue_worktree_pattern=f"/tmp/{admin.id}-issue-{{issue_number}}",
        ),
        protected_paths=list(admin.protected_paths),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMutationsUpsertProjectState:
    """Verify upsert_project insert and update round-trips through SQLite."""

    def test_insert_then_verify_row(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)
        proj = _make_project("alpha")
        upsert_project(conn, proj)

        cur = conn.execute(
            "SELECT id, name, repo_url, priority, default_branch, status FROM projects WHERE id=?",
            ("alpha",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "alpha"
        assert row[1] == "Test Project"
        assert row[2] == "git@github.com:test/test.git"
        assert row[3] == "high"
        assert row[4] == "main"
        assert row[5] == "active"
        conn.close()

    def test_upsert_updates_existing_row(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)
        proj = _make_project("alpha")
        upsert_project(conn, proj)

        # Grab created_at before update
        cur = conn.execute("SELECT created_at, updated_at FROM projects WHERE id=?", ("alpha",))
        row_before = cur.fetchone()
        assert row_before is not None

        # Update with changed fields
        updated = _make_project(
            "alpha",
            name="Alpha Renamed",
            priority="critical",
            status="paused",
            default_branch="develop",
        )
        upsert_project(conn, updated)

        cur = conn.execute(
            "SELECT name, priority, status, default_branch, created_at, updated_at FROM projects WHERE id=?",
            ("alpha",),
        )
        row_after = cur.fetchone()
        assert row_after[0] == "Alpha Renamed"
        assert row_after[1] == "critical"
        assert row_after[2] == "paused"
        assert row_after[3] == "develop"
        # updated_at should have changed
        assert row_after[5] >= row_before[1]

        # Only one row should exist (no duplicate)
        cur = conn.execute("SELECT count(*) FROM projects WHERE id=?", ("alpha",))
        assert cur.fetchone()[0] == 1
        conn.close()


class TestRemoveSetsArchivedWithoutDeletingHistory:
    """When a project is removed from config, SQLite should archive it
    (status='archived') rather than deleting the row, preserving
    associated issues/PRs history."""

    def test_archive_preserves_row(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)
        proj = _make_project("beta", status="active")
        upsert_project(conn, proj)

        # Add an issue linked to this project
        upsert_issue(
            conn,
            "beta",
            {
                "number": 1,
                "title": "Some bug",
                "state": "needs_triage",
            },
        )

        # Simulate archive: update status without deleting
        archived = _make_project("beta", status="archived")
        upsert_project(conn, archived)

        # Row still exists with status=archived
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("beta",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "archived"
        conn.close()

    def test_archive_does_not_cascade_delete_issues(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)
        proj = _make_project("beta", status="active")
        upsert_project(conn, proj)

        # Insert two issues
        for i in (1, 2):
            upsert_issue(
                conn,
                "beta",
                {
                    "number": i,
                    "title": f"Issue {i}",
                    "state": "needs_triage",
                },
            )

        # Archive (not delete)
        archived = _make_project("beta", status="archived")
        upsert_project(conn, archived)

        # Issues still intact
        cur = conn.execute("SELECT count(*) FROM issues WHERE project_id=?", ("beta",))
        assert cur.fetchone()[0] == 2
        conn.close()

    def test_actual_delete_cascades_but_archive_does_not(self, tmp_path: Path):
        """Contrast: a real DELETE cascades and removes issues.
        Archive (status update) does not."""
        conn = _open_and_init(tmp_path)
        proj = _make_project("gamma", status="active")
        upsert_project(conn, proj)
        upsert_issue(
            conn,
            "gamma",
            {
                "number": 10,
                "title": "Important issue",
                "state": "in_progress",
            },
        )

        # Archive preserves issues
        archived = _make_project("gamma", status="archived")
        upsert_project(conn, archived)
        cur = conn.execute("SELECT count(*) FROM issues WHERE project_id=?", ("gamma",))
        assert cur.fetchone()[0] == 1

        # But a real DELETE would cascade (verify FK behavior)
        conn.execute("DELETE FROM projects WHERE id=?", ("gamma",))
        conn.commit()
        cur = conn.execute("SELECT count(*) FROM issues WHERE project_id=?", ("gamma",))
        assert cur.fetchone()[0] == 0
        conn.close()


class TestUpsertProjectFromAdminConfig:
    """Verify AdminProjectConfig -> ProjectConfig -> SQLite round-trip."""

    def test_admin_config_round_trips_through_sqlite(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)

        admin = AdminProjectConfig(
            id="my-webapp",
            name="My Web App",
            repo="git@github.com:acme/webapp.git",
            github_owner="acme",
            github_repo="webapp",
            priority="high",
            status="active",
            default_branch="main",
        )

        proj = _admin_to_project_config(admin)
        upsert_project(conn, proj)

        cur = conn.execute(
            "SELECT id, name, repo_url, priority, status, default_branch FROM projects WHERE id=?",
            ("my-webapp",),
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "my-webapp"
        assert row[1] == "My Web App"
        assert row[2] == "git@github.com:acme/webapp.git"
        assert row[3] == "high"
        assert row[4] == "active"
        assert row[5] == "main"
        conn.close()

    def test_admin_config_with_non_default_fields(self, tmp_path: Path):
        conn = _open_and_init(tmp_path)

        admin = AdminProjectConfig(
            id="infra-tools",
            name="Infrastructure Tools",
            repo="git@github.com:acme/infra.git",
            github_owner="acme",
            github_repo="infra",
            priority="critical",
            status="active",
            default_branch="develop",
            notes="Internal tooling",
        )

        proj = _admin_to_project_config(admin)
        upsert_project(conn, proj)

        cur = conn.execute(
            "SELECT id, name, priority, default_branch FROM projects WHERE id=?",
            ("infra-tools",),
        )
        row = cur.fetchone()
        assert row[0] == "infra-tools"
        assert row[1] == "Infrastructure Tools"
        assert row[2] == "critical"
        assert row[3] == "develop"
        conn.close()

    def test_admin_config_update_via_upsert(self, tmp_path: Path):
        """Insert from admin config, then update priority + status."""
        conn = _open_and_init(tmp_path)

        admin = AdminProjectConfig(
            id="my-api",
            name="My API",
            repo="git@github.com:acme/api.git",
            github_owner="acme",
            github_repo="api",
            priority="medium",
            status="active",
            default_branch="main",
        )
        proj = _admin_to_project_config(admin)
        upsert_project(conn, proj)

        # Simulate an update: change priority and status
        admin_updated = AdminProjectConfig(
            id="my-api",
            name="My API",
            repo="git@github.com:acme/api.git",
            github_owner="acme",
            github_repo="api",
            priority="low",
            status="paused",
            default_branch="main",
        )
        proj_updated = _admin_to_project_config(admin_updated)
        upsert_project(conn, proj_updated)

        cur = conn.execute(
            "SELECT priority, status FROM projects WHERE id=?",
            ("my-api",),
        )
        row = cur.fetchone()
        assert row[0] == "low"
        assert row[1] == "paused"

        # Still just one row
        cur = conn.execute("SELECT count(*) FROM projects WHERE id=?", ("my-api",))
        assert cur.fetchone()[0] == 1
        conn.close()


def _setup_root(tmp_path: Path) -> Path:
    """Create directories and return root."""
    for d in ("config", "state", "worktrees", "logs", "artifacts", "backups"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _write_config(root: Path, config: dict) -> None:
    """Write a projects.yaml config to the root."""
    config_path = root / "config" / "projects.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")


def _parse_result(result: str) -> dict:
    return json.loads(result)


def _seed_project(root: Path, project_id: str = "test-proj", **overrides) -> dict:
    """Write a config with one project and return the config dict."""
    defaults = {
        "id": project_id,
        "name": "Test Project",
        "repo": "git@github.com:acme/test-proj.git",
        "github": {"owner": "acme", "repo": "test-proj"},
        "priority": "medium",
        "status": "active",
        "default_branch": "main",
        "auto_merge": {"enabled": False, "max_risk": None},
        "protected_paths": [],
        "labels": [],
    }
    defaults.update(overrides)
    config = {"version": 1, "projects": [defaults]}
    _write_config(root, config)
    return config


# ---------------------------------------------------------------------------
# portfolio_project_add
# ---------------------------------------------------------------------------


class TestHandlerProjectAdd:
    def test_add_first_project_creates_config(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            result = _parse_result(
                _handle_portfolio_project_add({"repo": "acme/webapp", "validate_github": False, "root": str(root)})
            )
        assert result["status"] == "success"
        assert result["data"]["project_id"] == "webapp"
        assert result["data"]["is_first_run"] is True
        # Config should now exist
        config_path = root / "config" / "projects.yaml"
        assert config_path.exists()

    def test_add_project_to_existing_config(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            result = _parse_result(
                _handle_portfolio_project_add({"repo": "acme/new-project", "validate_github": False, "root": str(root)})
            )
        assert result["status"] == "success"
        assert result["data"]["project_id"] == "new-project"
        assert result["data"]["is_first_run"] is False
        assert result["data"]["backup_created"] is True

    def test_add_duplicate_project_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root, project_id="test-proj")
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            result = _parse_result(
                _handle_portfolio_project_add({"repo": "acme/test-proj", "validate_github": False, "root": str(root)})
            )
        assert result["status"] == "blocked"
        assert "duplicate" in result["message"].lower()

    def test_add_project_bad_repo_ref(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_add({"repo": "", "validate_github": False, "root": str(root)}))
        assert result["status"] == "blocked"

    def test_add_project_with_custom_name_and_priority(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            result = _parse_result(
                _handle_portfolio_project_add(
                    {
                        "repo": "acme/myapp",
                        "name": "My Application",
                        "priority": "critical",
                        "validate_github": False,
                        "root": str(root),
                    }
                )
            )
        assert result["status"] == "success"
        assert result["data"]["project_id"] == "myapp"

    def test_add_project_upserts_to_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            _handle_portfolio_project_add({"repo": "acme/sqltest", "validate_github": False, "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT id, status FROM projects WHERE id=?", ("sqltest",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "sqltest"
        assert row[1] == "active"
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_project_update
# ---------------------------------------------------------------------------


class TestHandlerProjectUpdate:
    def test_update_project_name(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_update({"project_id": "test-proj", "name": "Renamed", "root": str(root)})
        )
        assert result["status"] == "success"
        assert "name" in result["data"]["updated_fields"]

    def test_update_project_priority_and_status(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_update(
                {"project_id": "test-proj", "priority": "critical", "status": "paused", "root": str(root)}
            )
        )
        assert result["status"] == "success"
        assert "priority" in result["data"]["updated_fields"]
        assert "status" in result["data"]["updated_fields"]

    def test_update_no_fields_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_update({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_update_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(
            _handle_portfolio_project_update({"project_id": "test-proj", "name": "New", "root": str(root)})
        )
        assert result["status"] == "blocked"
        assert "config" in result["message"].lower()

    def test_update_nonexistent_project_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_update({"project_id": "no-such-proj", "name": "X", "root": str(root)})
        )
        assert result["status"] == "blocked"

    def test_update_syncs_to_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_update({"project_id": "test-proj", "priority": "high", "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT priority FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "high"
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_project_pause
# ---------------------------------------------------------------------------


class TestHandlerProjectPause:
    def test_pause_project(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_pause({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "success"
        assert "paused" in result["message"].lower()

    def test_pause_with_reason(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_pause({"project_id": "test-proj", "reason": "on vacation", "root": str(root)})
        )
        assert result["status"] == "success"
        assert result["data"]["reason"] == "on vacation"

    def test_pause_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_pause({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_pause_syncs_status_to_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_pause({"project_id": "test-proj", "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "paused"
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_project_resume
# ---------------------------------------------------------------------------


class TestHandlerProjectResume:
    def test_resume_paused_project(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root, status="paused")
        result = _parse_result(_handle_portfolio_project_resume({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "success"

    def test_resume_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_resume({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_resume_syncs_status_to_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root, status="paused")
        _handle_portfolio_project_resume({"project_id": "test-proj", "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "active"
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_project_archive
# ---------------------------------------------------------------------------


class TestHandlerProjectArchive:
    def test_archive_project(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_archive({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "success"

    def test_archive_with_reason(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_archive(
                {"project_id": "test-proj", "reason": "project completed", "root": str(root)}
            )
        )
        assert result["status"] == "success"
        assert result["data"]["reason"] == "project completed"

    def test_archive_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_archive({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_archive_syncs_status_to_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_archive({"project_id": "test-proj", "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "archived"
        conn.close()


# ---------------------------------------------------------------------------
# portfolio_project_set_priority
# ---------------------------------------------------------------------------


class TestHandlerProjectSetPriority:
    def test_set_priority(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_set_priority(
                {"project_id": "test-proj", "priority": "critical", "root": str(root)}
            )
        )
        assert result["status"] == "success"
        assert result["data"]["priority"] == "critical"

    def test_set_priority_paused_also_sets_status(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_set_priority({"project_id": "test-proj", "priority": "paused", "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT priority, status FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row[0] == "paused"
        assert row[1] == "paused"
        conn.close()

    def test_set_invalid_priority_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_set_priority(
                {"project_id": "test-proj", "priority": "invalid", "root": str(root)}
            )
        )
        assert result["status"] == "blocked"

    def test_set_priority_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(
            _handle_portfolio_project_set_priority({"project_id": "test-proj", "priority": "high", "root": str(root)})
        )
        assert result["status"] == "blocked"

    def test_set_priority_missing_args_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_set_priority({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# portfolio_project_set_auto_merge
# ---------------------------------------------------------------------------


class TestHandlerProjectSetAutoMerge:
    def test_enable_auto_merge(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_set_auto_merge({"project_id": "test-proj", "enabled": True, "root": str(root)})
        )
        assert result["status"] == "success"
        assert result["data"]["enabled"] is True

    def test_disable_auto_merge(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_set_auto_merge({"project_id": "test-proj", "enabled": False, "root": str(root)})
        )
        assert result["status"] == "success"
        assert result["data"]["enabled"] is False

    def test_auto_merge_with_max_risk(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_set_auto_merge(
                {"project_id": "test-proj", "enabled": True, "max_risk": "medium", "root": str(root)}
            )
        )
        assert result["status"] == "success"
        assert result["data"]["max_risk"] == "medium"

    def test_auto_merge_missing_enabled_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_set_auto_merge({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_auto_merge_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(
            _handle_portfolio_project_set_auto_merge({"project_id": "test-proj", "enabled": True, "root": str(root)})
        )
        assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# portfolio_project_remove
# ---------------------------------------------------------------------------


class TestHandlerProjectRemove:
    def test_remove_project_with_confirm(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_remove({"project_id": "test-proj", "confirm": True, "root": str(root)})
        )
        assert result["status"] == "success"
        assert result["data"]["backup_created"] is True

    def test_remove_without_confirm_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(
            _handle_portfolio_project_remove({"project_id": "test-proj", "confirm": False, "root": str(root)})
        )
        assert result["status"] == "blocked"

    def test_remove_archives_in_sqlite(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_remove({"project_id": "test-proj", "confirm": True, "root": str(root)})
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("test-proj",))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "archived"
        conn.close()

    def test_remove_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(
            _handle_portfolio_project_remove({"project_id": "test-proj", "confirm": True, "root": str(root)})
        )
        assert result["status"] == "blocked"

    def test_remove_project_gone_from_yaml(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        _handle_portfolio_project_remove({"project_id": "test-proj", "confirm": True, "root": str(root)})
        config_path = root / "config" / "projects.yaml"
        reloaded = yaml.safe_load(config_path.read_text())
        assert len(reloaded.get("projects", [])) == 0


# ---------------------------------------------------------------------------
# portfolio_project_explain
# ---------------------------------------------------------------------------


class TestHandlerProjectExplain:
    def test_explain_existing_project(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_explain({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "success"
        assert result["data"]["project"]["id"] == "test-proj"

    def test_explain_nonexistent_project_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_explain({"project_id": "no-such", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_explain_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_explain({"project_id": "test-proj", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_explain_shows_all_fields(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_explain({"project_id": "test-proj", "root": str(root)}))
        project = result["data"]["project"]
        assert "priority" in project
        assert "status" in project
        assert "repo" in project


# ---------------------------------------------------------------------------
# portfolio_project_config_backup
# ---------------------------------------------------------------------------


class TestHandlerProjectConfigBackup:
    def test_create_backup(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_config_backup({"root": str(root)}))
        assert result["status"] == "success"
        assert result["data"]["backup_created"] is True
        assert result["data"]["backup_path"] is not None

    def test_backup_missing_config_blocked(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        result = _parse_result(_handle_portfolio_project_config_backup({"root": str(root)}))
        assert result["status"] == "blocked"

    def test_backup_file_exists_on_disk(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_config_backup({"root": str(root)}))
        backup_path = result["data"]["backup_path"]
        assert Path(backup_path).exists()


# ---------------------------------------------------------------------------
# Cross-cutting: missing project_id
# ---------------------------------------------------------------------------


class TestMissingProjectIdBlocked:
    """Handlers that require project_id should return blocked when empty."""

    def test_update_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_update({"root": str(root), "name": "X"}))
        assert result["status"] == "blocked"

    def test_pause_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_pause({"root": str(root)}))
        assert result["status"] == "blocked"

    def test_resume_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_resume({"root": str(root)}))
        assert result["status"] == "blocked"

    def test_archive_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_archive({"root": str(root)}))
        assert result["status"] == "blocked"

    def test_set_priority_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_set_priority({"priority": "high", "root": str(root)}))
        assert result["status"] == "blocked"

    def test_set_auto_merge_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_set_auto_merge({"enabled": True, "root": str(root)}))
        assert result["status"] == "blocked"

    def test_remove_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_remove({"confirm": True, "root": str(root)}))
        assert result["status"] == "blocked"

    def test_explain_no_project_id(self, tmp_path: Path):
        root = _setup_root(tmp_path)
        _seed_project(root)
        result = _parse_result(_handle_portfolio_project_explain({"root": str(root)}))
        assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# Integration: full lifecycle add -> pause -> resume -> archive -> remove
# ---------------------------------------------------------------------------


class TestProjectLifecycle:
    def test_full_lifecycle(self, tmp_path: Path):
        root = _setup_root(tmp_path)

        # Add
        with mock_patch(
            "portfolio_manager.tools.check_gh_available_for_project_add",
            return_value=None,
        ):
            r = _parse_result(
                _handle_portfolio_project_add({"repo": "acme/lifecycle", "validate_github": False, "root": str(root)})
            )
        assert r["status"] == "success"

        # Pause
        r = _parse_result(
            _handle_portfolio_project_pause({"project_id": "lifecycle", "reason": "maintenance", "root": str(root)})
        )
        assert r["status"] == "success"

        # Resume
        r = _parse_result(_handle_portfolio_project_resume({"project_id": "lifecycle", "root": str(root)}))
        assert r["status"] == "success"

        # Set priority
        r = _parse_result(
            _handle_portfolio_project_set_priority({"project_id": "lifecycle", "priority": "high", "root": str(root)})
        )
        assert r["status"] == "success"

        # Explain
        r = _parse_result(_handle_portfolio_project_explain({"project_id": "lifecycle", "root": str(root)}))
        assert r["status"] == "success"
        assert r["data"]["project"]["priority"] == "high"
        assert r["data"]["project"]["status"] == "active"

        # Archive
        r = _parse_result(_handle_portfolio_project_archive({"project_id": "lifecycle", "root": str(root)}))
        assert r["status"] == "success"

        # Verify archived in SQLite
        conn = open_state(root)
        init_state(conn)
        cur = conn.execute("SELECT status FROM projects WHERE id=?", ("lifecycle",))
        row = cur.fetchone()
        assert row[0] == "archived"
        conn.close()
