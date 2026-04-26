"""Phase 6 — SQLite state integration tests for project admin mutations.

Verifies that upsert_project() correctly round-trips project data to/from
SQLite, including insert, update, archive-without-delete, and conversion
from AdminProjectConfig to ProjectConfig.
"""

from __future__ import annotations

from pathlib import Path

from portfolio_manager.admin_models import AdminProjectConfig
from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.state import init_state, open_state, upsert_issue, upsert_project

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
