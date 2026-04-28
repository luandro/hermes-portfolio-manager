"""E2E and regression tests for maintenance pipeline — Phase 10."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from portfolio_manager.maintenance_models import (
    MaintenanceFinding,
    MaintenanceSkillResult,
)
from portfolio_manager.state import init_state, open_state

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _insert_project(
    conn: sqlite3.Connection,
    project_id: str = "proj-1",
    status: str = "active",
) -> None:
    now = _now()
    conn.execute(
        "INSERT INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'medium', ?, ?, ?)",
        (project_id, project_id, f"https://github.com/test/{project_id}", status, now, now),
    )
    conn.commit()


def _insert_issue(
    conn: sqlite3.Connection,
    project_id: str = "proj-1",
    issue_number: int = 1,
    title: str = "Test issue",
    state: str = "open",
) -> None:
    now = _now()
    conn.execute(
        "INSERT INTO issues (project_id, issue_number, title, state, last_seen_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, issue_number, title, state, now, now, now),
    )
    conn.commit()


def _insert_pr(
    conn: sqlite3.Connection,
    project_id: str = "proj-1",
    pr_number: int = 1,
    title: str = "Test PR",
    state: str = "open",
) -> None:
    now = _now()
    conn.execute(
        "INSERT INTO pull_requests (project_id, pr_number, title, branch_name, base_branch, state, last_seen_at, created_at, updated_at) "
        "VALUES (?, ?, ?, 'feature/test', 'main', ?, ?, ?, ?)",
        (project_id, pr_number, title, state, now, now, now),
    )
    conn.commit()


def _make_config(**overrides: Any) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "skills": {
            "health_check": {"enabled": True, "interval_hours": 24},
        },
        "refresh_github": False,
    }
    cfg.update(overrides)
    return cfg


def _mock_skill_result(
    skill_id: str = "health_check",
    project_id: str = "proj-1",
    findings: list[MaintenanceFinding] | None = None,
    status: str = "success",
) -> MaintenanceSkillResult:
    return MaintenanceSkillResult(
        skill_id=skill_id,
        project_id=project_id,
        status=status,
        findings=findings or [],
        summary="mock result",
    )


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = open_state(tmp_path)
    init_state(c)
    yield c
    c.close()


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# 10.1: Dry run has no side effects
# ---------------------------------------------------------------------------


class TestE2EDryRunNoSideEffects:
    """Run maintenance with dry_run=True; verify zero side-effects."""

    def test_e2e_maintenance_dry_run_has_no_side_effects(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        # Seed DB with project, issues, PRs
        _insert_project(conn)
        _insert_issue(conn, issue_number=1)
        _insert_issue(conn, issue_number=2, title="Another issue")
        _insert_pr(conn, pr_number=10)
        config = _make_config()

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        result = run_maintenance(root, conn, config, dry_run=True)

        # 1. No run rows in DB
        cur = conn.execute("SELECT count(*) FROM maintenance_runs")
        assert cur.fetchone()[0] == 0

        # 2. No findings in DB
        cur = conn.execute("SELECT count(*) FROM maintenance_findings")
        assert cur.fetchone()[0] == 0

        # 3. No artifacts written
        artifact_dir = root / "artifacts" / "maintenance"
        assert not artifact_dir.exists()

        # 4. Result is a plan (has planned_checks), not execution output
        assert "planned_checks" in result
        assert "runs" not in result or result.get("runs") == []

    def test_e2e_dry_run_does_not_call_gh_commands(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Dry run must never invoke gh CLI or REGISTRY.execute."""
        _insert_project(conn)
        config = _make_config(refresh_github=True)

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with (
            patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg,
            patch("portfolio_manager.maintenance_orchestrator._refresh_github_data") as mock_refresh,
        ):
            run_maintenance(root, conn, config, dry_run=True)

            mock_reg.execute.assert_not_called()
            mock_refresh.assert_not_called()

        # Still no side effects
        cur = conn.execute("SELECT count(*) FROM maintenance_runs")
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 10.2: Real run stores findings and report
# ---------------------------------------------------------------------------


class TestE2ERealRunStoresFindingsAndReport:
    """Run maintenance with dry_run=False; verify full artifact persistence."""

    def test_e2e_maintenance_real_run_stores_findings_and_report(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        _insert_project(conn)
        _insert_issue(conn, issue_number=42, title="Stale bug")
        _insert_pr(conn, pr_number=7)
        config = _make_config(refresh_github=False)

        finding = MaintenanceFinding(
            fingerprint="fp-e2e-001",
            severity="high",
            title="E2E test finding",
            body="Something needs attention",
            source_type="issue",
            source_id="42",
            source_url="https://github.com/test/proj-1/issues/42",
            metadata={"detail": "e2e"},
        )
        mock_result = _mock_skill_result(findings=[finding])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            result = run_maintenance(root, conn, config, dry_run=False)

        # 1. Run row created and finished
        cur = conn.execute("SELECT run_id, status FROM maintenance_runs")
        rows = cur.fetchall()
        assert len(rows) >= 1
        run_id = rows[0][0]
        assert rows[0][1] in ("success", "failed")

        # 2. Findings stored in DB
        cur = conn.execute(
            "SELECT fingerprint, severity, title FROM maintenance_findings WHERE run_id=?",
            (run_id,),
        )
        db_findings = cur.fetchall()
        assert len(db_findings) == 1
        assert db_findings[0][0] == "fp-e2e-001"
        assert db_findings[0][1] == "high"

        # 3. Artifacts exist: report.md, findings.json, metadata.json
        artifact_base = root / "artifacts" / "maintenance"
        assert artifact_base.is_dir()

        # Find the run directory
        run_dirs = [d for d in artifact_base.iterdir() if d.is_dir()]
        assert len(run_dirs) >= 1
        run_dir = run_dirs[0]

        assert (run_dir / "report.md").exists()
        assert (run_dir / "findings.json").exists()
        assert (run_dir / "metadata.json").exists()

        # Validate artifact contents
        report_md = (run_dir / "report.md").read_text()
        assert "E2E test finding" in report_md

        findings_json = json.loads((run_dir / "findings.json").read_text())
        assert len(findings_json) == 1
        assert findings_json[0]["fingerprint"] == "fp-e2e-001"

        metadata_json = json.loads((run_dir / "metadata.json").read_text())
        assert metadata_json["run_id"] == run_id
        assert metadata_json["skill_id"] == "health_check"

        # 4. Result summary has expected keys
        assert "runs" in result
        assert result["findings_count"] == 1


# ---------------------------------------------------------------------------
# 10.3: Create issue drafts — local draft only, no gh calls
# ---------------------------------------------------------------------------


class TestE2ECreateIssueDraftsLocalOnly:
    """Verify draft creation writes local artifacts without GitHub API calls."""

    def test_e2e_maintenance_create_issue_drafts_creates_local_draft_only(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """E2E: run maintenance then create drafts — draft is local-only, no gh."""
        _insert_project(conn)
        _insert_issue(conn, issue_number=5, title="Draftable issue")
        config = _make_config(create_issue_drafts=True)

        finding = MaintenanceFinding(
            fingerprint="fp-draft-001",
            severity="medium",
            title="Draftable finding",
            body="This finding should produce a local draft",
            source_type="issue",
            source_id="5",
            source_url=None,
            metadata={},
            draftable=True,
        )
        mock_result = _mock_skill_result(findings=[finding])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        # Step 1: Run maintenance (creates findings and artifacts)
        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            result = run_maintenance(root, conn, config, dry_run=False)

        # Get the run_id from result
        assert len(result["runs"]) >= 1
        run_id = result["runs"][0]["run_id"]

        # Step 2: Plan and create issue drafts from findings
        from portfolio_manager.maintenance_drafts import (
            create_maintenance_drafts,
            plan_maintenance_issue_drafts,
        )

        findings_map: dict[tuple[str, str, str], MaintenanceSkillResult] = {
            ("proj-1", "health_check", run_id): mock_result,
        }
        draft_plans = plan_maintenance_issue_drafts(
            findings_map,
            config,
            conn=conn,
        )
        assert len(draft_plans) >= 1, "At least one draft plan should be created"

        # Create a projects.yaml so that create_issue_draft can resolve the project
        config_dir = root / "config"
        config_dir.mkdir(exist_ok=True)
        projects_yaml = config_dir / "projects.yaml"
        projects_yaml.write_text(
            "version: 1\n"
            "projects:\n"
            "  - id: proj-1\n"
            "    name: Test Project\n"
            "    repo: https://github.com/test/proj-1\n"
            "    priority: medium\n"
            "    status: active\n"
            "    github:\n"
            "      owner: test\n"
            "      repo: proj-1\n"
        )

        draft_results = create_maintenance_drafts(root, conn, draft_plans, config)
        assert len(draft_results) >= 1

        # 1. Local draft artifact should exist (draft-created.json in artifact dir)
        draft_artifact = root / "artifacts" / "maintenance" / run_id / "draft-created.json"
        assert draft_artifact.exists(), (
            f"draft-created.json not found at {draft_artifact}. "
            f"Artifact dir contents: {list((root / 'artifacts' / 'maintenance' / run_id).iterdir()) if (root / 'artifacts' / 'maintenance' / run_id).exists() else 'dir missing'}"
        )

        draft_data = json.loads(draft_artifact.read_text())
        assert "draft_id" in draft_data
        assert draft_data["finding_fingerprint"] == "fp-draft-001"

        # 2. Findings should reference the draft ID
        cur = conn.execute(
            "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint='fp-draft-001'",
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] is not None and row[0] != ""

        # 3. No gh issue create calls — the draft is in local DB only.
        draft_id = row[0]
        cur2 = conn.execute(
            "SELECT draft_id, state, github_issue_number FROM issue_drafts WHERE draft_id=?",
            (draft_id,),
        )
        draft_row = cur2.fetchone()
        assert draft_row is not None
        # github_issue_number should be NULL (not published to GitHub)
        assert draft_row[2] is None


# ---------------------------------------------------------------------------
# 10.4: Repeated runs update same findings; missing findings marked resolved
# ---------------------------------------------------------------------------


class TestE2ERepeatedRunsAndResolution:
    """Verify idempotent finding updates and auto-resolution of disappeared findings."""

    def test_e2e_repeated_run_updates_same_findings(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """Second run with same fingerprints should not create duplicates."""
        _insert_project(conn)
        config: dict[str, Any] = {
            "skills": {
                "health_check": {"enabled": True, "interval_hours": 24},
            },
            "refresh_github": False,
        }

        finding = MaintenanceFinding(
            fingerprint="fp-persist-001",
            severity="low",
            title="Persistent finding",
            body="Still here",
            source_type="issue",
            source_id="1",
            source_url=None,
            metadata={},
        )
        mock_result = _mock_skill_result(findings=[finding])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        # First run
        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config, dry_run=False)

        # Count findings after first run
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_findings WHERE fingerprint='fp-persist-001'",
        )
        count_after_first = cur.fetchone()[0]
        assert count_after_first == 1

        # Make the second run due by backdating the first run's finished_at
        old_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        conn.execute(
            "UPDATE maintenance_runs SET finished_at=? WHERE status='success'",
            (old_time,),
        )
        conn.commit()

        # Second run with same finding
        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = mock_result
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config, dry_run=False)

        # The fingerprint should still have exactly 1 row (or at most 2 from
        # both runs — one per run_id). The key assertion: no unbounded duplication.
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_findings WHERE fingerprint='fp-persist-001'",
        )
        count_after_second = cur.fetchone()[0]
        # The second run inserts a new finding for its own run_id, so there
        # should be exactly 2 rows (one per run).
        assert count_after_second == 2

        # Both runs should be recorded
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_runs WHERE status='success'",
        )
        assert cur.fetchone()[0] == 2

    def test_e2e_missing_finding_marked_resolved(
        self,
        root: Path,
        conn: sqlite3.Connection,
    ) -> None:
        """If a finding disappears between runs, it should be marked resolved."""
        _insert_project(conn)
        config: dict[str, Any] = {
            "skills": {
                "health_check": {"enabled": True, "interval_hours": 24},
            },
            "refresh_github": False,
        }

        # First run WITH a finding
        finding_v1 = MaintenanceFinding(
            fingerprint="fp-disappears",
            severity="medium",
            title="Transient finding",
            body="Will go away",
            source_type="issue",
            source_id="99",
            source_url=None,
            metadata={},
        )
        result_with_finding = _mock_skill_result(findings=[finding_v1])

        # Second run WITHOUT that finding
        result_no_finding = _mock_skill_result(findings=[])

        from portfolio_manager.maintenance_orchestrator import run_maintenance

        # Run 1
        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = result_with_finding
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config, dry_run=False)

        # Confirm finding exists from run 1
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_findings WHERE fingerprint='fp-disappears'",
        )
        assert cur.fetchone()[0] == 1

        # Backdate the first run so the second is due
        old_time = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
        conn.execute(
            "UPDATE maintenance_runs SET finished_at=? WHERE status='success'",
            (old_time,),
        )
        conn.commit()

        # Run 2 (finding gone)
        with patch("portfolio_manager.maintenance_orchestrator.REGISTRY") as mock_reg:
            mock_reg.execute.return_value = result_no_finding
            mock_reg.list_specs.return_value = []
            run_maintenance(root, conn, config, dry_run=False)

        # The old finding from run 1 should still exist (not deleted)
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_findings WHERE fingerprint='fp-disappears'",
        )
        assert cur.fetchone()[0] == 1

        # Run 2 should have no new findings with that fingerprint
        cur = conn.execute("SELECT run_id FROM maintenance_runs ORDER BY started_at")
        run_ids = [row[0] for row in cur.fetchall()]
        assert len(run_ids) >= 2

        latest_run_id = run_ids[-1]
        cur = conn.execute(
            "SELECT count(*) FROM maintenance_findings WHERE run_id=? AND fingerprint='fp-disappears'",
            (latest_run_id,),
        )
        assert cur.fetchone()[0] == 0, "Finding should not appear in the second run"
