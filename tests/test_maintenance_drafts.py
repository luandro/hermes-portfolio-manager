"""Tests for maintenance draft planning, creation, and repair — Phase 5."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from portfolio_manager.maintenance_models import (
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
)
from portfolio_manager.maintenance_state import insert_finding, start_run
from portfolio_manager.state import init_state, open_state, upsert_issue_draft

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(**overrides: Any) -> MaintenanceSkillSpec:
    defaults: dict[str, Any] = dict(
        id="test-skill",
        name="Test Skill",
        description="A test skill",
        default_interval_hours=24,
        default_enabled=True,
        supports_issue_drafts=True,
        required_state=["cloned"],
        allowed_commands=[["git", "log"]],
        config_schema={"type": "object"},
    )
    defaults.update(overrides)
    return MaintenanceSkillSpec(**defaults)


def _make_finding(**overrides: Any) -> MaintenanceFinding:
    defaults: dict[str, Any] = dict(
        fingerprint="fp001",
        severity="medium",
        title="Test finding",
        body="Something found",
        source_type="commit",
        source_id="abc123def",
        source_url="https://example.com/commit/abc123def",
        metadata={"line": 42},
        draftable=True,
    )
    defaults.update(overrides)
    return MaintenanceFinding(**defaults)


def _make_result(**overrides: Any) -> MaintenanceSkillResult:
    finding = _make_finding()
    defaults: dict[str, Any] = dict(
        skill_id="test-skill",
        project_id="proj-1",
        status="success",
        findings=[finding],
        summary="Ran successfully",
    )
    defaults.update(overrides)
    return MaintenanceSkillResult(**defaults)


def _init_db(tmp_path: Path) -> sqlite3.Connection:
    """Create an initialized DB with tables ready and a project row."""
    conn = open_state(tmp_path)
    init_state(conn)
    conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, repo_url, priority, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
        ("proj-1", "Test Project", "https://github.com/test/repo", "high", "active"),
    )
    conn.commit()
    return conn


# ===========================================================================
# Task 5.1: plan_maintenance_issue_drafts
# ===========================================================================


class TestPlanMaintenanceIssueDrafts:
    """Tests for plan_maintenance_issue_drafts pure planning logic."""

    def test_create_issue_drafts_false_creates_no_drafts(self) -> None:
        from portfolio_manager.maintenance_drafts import plan_maintenance_issue_drafts

        config: dict[str, Any] = {"create_issue_drafts": False}
        findings_by_project_skill_run = {("proj-1", "test-skill", "run001"): _make_result()}
        plans = plan_maintenance_issue_drafts(findings_by_project_skill_run, config)
        assert plans == []

    def test_create_issue_drafts_true_requires_skill_support(self) -> None:
        from portfolio_manager.maintenance_drafts import plan_maintenance_issue_drafts

        config: dict[str, Any] = {"create_issue_drafts": True}
        result = _make_result()
        findings_by_project_skill_run = {("proj-1", "test-skill", "run001"): result}
        plans = plan_maintenance_issue_drafts(findings_by_project_skill_run, config)
        assert len(plans) == 1

    def test_non_draftable_findings_are_ignored_for_drafts(self) -> None:
        from portfolio_manager.maintenance_drafts import plan_maintenance_issue_drafts

        config: dict[str, Any] = {"create_issue_drafts": True}
        finding = _make_finding(draftable=False)
        result = _make_result(findings=[finding])
        findings_by_project_skill_run = {("proj-1", "test-skill", "run001"): result}
        plans = plan_maintenance_issue_drafts(findings_by_project_skill_run, config)
        assert plans == []

    def test_existing_finding_with_issue_draft_id_does_not_duplicate(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import plan_maintenance_issue_drafts

        config: dict[str, Any] = {"create_issue_drafts": True}
        conn = _init_db(tmp_path)
        # Insert a draft row so FK constraint is satisfied
        upsert_issue_draft(
            conn,
            {
                "draft_id": "draft-existing-123",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Existing draft",
                "readiness": 0.5,
                "artifact_path": "artifacts/issues/proj-1/draft-existing-123",
            },
        )
        # Insert a run and finding with issue_draft_id already set
        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp001",
            "medium",
            "Test finding",
            draftable=True,
        )
        conn.execute(
            "UPDATE maintenance_findings SET issue_draft_id=? WHERE fingerprint=?",
            ("draft-existing-123", "fp001"),
        )
        conn.commit()

        finding = _make_finding(fingerprint="fp001")
        result = _make_result(findings=[finding])
        findings_by_project_skill_run = {("proj-1", "test-skill", run_id): result}
        plans = plan_maintenance_issue_drafts(findings_by_project_skill_run, config, conn=conn)
        assert plans == []
        conn.close()

    def test_one_draft_per_project_skill_run(self) -> None:
        from portfolio_manager.maintenance_drafts import plan_maintenance_issue_drafts

        config: dict[str, Any] = {"create_issue_drafts": True}
        f1 = _make_finding(fingerprint="fp001")
        f2 = _make_finding(fingerprint="fp002")
        result = _make_result(findings=[f1, f2])
        findings_by_project_skill_run = {("proj-1", "test-skill", "run001"): result}
        plans = plan_maintenance_issue_drafts(findings_by_project_skill_run, config)
        assert len(plans) == 1
        assert plans[0].project_id == "proj-1"
        assert plans[0].skill_id == "test-skill"
        assert plans[0].run_id == "run001"
        assert plans[0].should_create is True


# ===========================================================================
# Task 5.2: create_maintenance_drafts
# ===========================================================================


class TestCreateMaintenanceDrafts:
    """Tests for create_maintenance_drafts using MVP 3 helpers."""

    def test_draft_creation_uses_existing_issue_draft_helper(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        finding = _make_finding()
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id="run001",
            findings=[finding],
            should_create=True,
        )

        with patch("portfolio_manager.issue_drafts.create_issue_draft") as mock_create:
            mock_create.return_value = {
                "draft_id": "draft-abc",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Maintenance: Test Skill findings for Test Project",
            }
            results = create_maintenance_drafts(tmp_path, conn, [plan], config)

        assert len(results) == 1
        assert results[0]["draft_id"] == "draft-abc"
        mock_create.assert_called_once()
        conn.close()

    def test_draft_body_has_goal_findings_acceptance_and_run_id(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        finding = _make_finding(title="Dep found", body="Something bad")
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id="run001",
            findings=[finding],
            should_create=True,
        )

        captured_text: dict[str, Any] = {}

        def _capture_create(root, conn, text, **kwargs):
            captured_text["text"] = text
            captured_text["kwargs"] = kwargs
            return {
                "draft_id": "draft-xyz",
                "project_id": "proj-1",
                "state": "draft",
                "title": kwargs.get("title", ""),
            }

        with patch(
            "portfolio_manager.issue_drafts.create_issue_draft",
            side_effect=_capture_create,
        ):
            create_maintenance_drafts(tmp_path, conn, [plan], config)

        text = captured_text.get("text", "")
        assert "Goal" in text
        assert "Findings" in text
        assert "Acceptance Criteria" in text
        assert "run001" in text
        conn.close()

    def test_draft_body_excludes_private_metadata_and_cot(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        finding = _make_finding(
            title="Dep found",
            body="Something bad",
            metadata={"internal_notes": "secret", "chain_of_thought": "reasoning"},
        )
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id="run001",
            findings=[finding],
            should_create=True,
        )

        captured_text: dict[str, Any] = {}

        def _capture_create(root, conn, text, **kwargs):
            captured_text["text"] = text
            return {
                "draft_id": "draft-xyz",
                "project_id": "proj-1",
                "state": "draft",
                "title": kwargs.get("title", ""),
            }

        with patch(
            "portfolio_manager.issue_drafts.create_issue_draft",
            side_effect=_capture_create,
        ):
            create_maintenance_drafts(tmp_path, conn, [plan], config)

        text = captured_text.get("text", "")
        assert "internal_notes" not in text
        assert "chain_of_thought" not in text
        assert "secret" not in text
        assert "reasoning" not in text
        conn.close()

    def test_draft_creation_failure_records_warning(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        finding = _make_finding()
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id="run001",
            findings=[finding],
            should_create=True,
        )

        with patch("portfolio_manager.issue_drafts.create_issue_draft") as mock_create:
            mock_create.return_value = {
                "blocked": True,
                "reason": "duplicate",
            }
            results = create_maintenance_drafts(tmp_path, conn, [plan], config)

        assert len(results) == 1
        assert "warning" in results[0]
        conn.close()

    def test_draft_created_updates_finding_issue_draft_id(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        # Insert a run and finding into DB
        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp001",
            "medium",
            "Test finding",
            draftable=True,
        )

        finding = _make_finding(fingerprint="fp001")
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id=run_id,
            findings=[finding],
            should_create=True,
        )

        with patch("portfolio_manager.issue_drafts.create_issue_draft") as mock_create:
            mock_create.return_value = {
                "draft_id": "draft-new-456",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Maintenance: Test Skill findings for Test Project",
            }
            # Insert draft row so FK constraint is satisfied
            upsert_issue_draft(
                conn,
                {
                    "draft_id": "draft-new-456",
                    "project_id": "proj-1",
                    "state": "draft",
                    "title": "Maintenance: Test Skill findings for Test Project",
                    "readiness": 0.5,
                    "artifact_path": "artifacts/issues/proj-1/draft-new-456",
                },
            )
            create_maintenance_drafts(tmp_path, conn, [plan], config)

        # Verify finding was updated
        row = conn.execute(
            "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint=?",
            ("fp001",),
        ).fetchone()
        assert row[0] == "draft-new-456"
        conn.close()

    def test_draft_created_artifact_written(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import (
            DraftPlan,
            create_maintenance_drafts,
        )

        conn = _init_db(tmp_path)
        config: dict[str, Any] = {"create_issue_drafts": True}

        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp001",
            "medium",
            "Test finding",
            draftable=True,
        )

        finding = _make_finding(fingerprint="fp001")
        plan = DraftPlan(
            project_id="proj-1",
            skill_id="test-skill",
            run_id=run_id,
            findings=[finding],
            should_create=True,
        )

        with patch("portfolio_manager.issue_drafts.create_issue_draft") as mock_create:
            mock_create.return_value = {
                "draft_id": "draft-artifact-789",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Maintenance: Test Skill findings for Test Project",
            }
            # Insert draft row so FK constraint is satisfied
            upsert_issue_draft(
                conn,
                {
                    "draft_id": "draft-artifact-789",
                    "project_id": "proj-1",
                    "state": "draft",
                    "title": "Maintenance: Test Skill findings for Test Project",
                    "readiness": 0.5,
                    "artifact_path": "artifacts/issues/proj-1/draft-artifact-789",
                },
            )
            create_maintenance_drafts(tmp_path, conn, [plan], config)

        # Check draft-created.json artifact exists
        artifact_dir = tmp_path / "artifacts" / "maintenance" / run_id
        draft_created_path = artifact_dir / "draft-created.json"
        assert draft_created_path.exists()
        data = json.loads(draft_created_path.read_text())
        assert data["draft_id"] == "draft-artifact-789"
        assert data["project_id"] == "proj-1"
        assert data["skill_id"] == "test-skill"
        assert "finding_fingerprint" in data
        conn.close()


# ===========================================================================
# Task 5.3: repair_draft_references
# ===========================================================================


class TestRepairDraftReferences:
    """Tests for repair_draft_references."""

    def test_repair_draft_created_artifact_updates_missing_sqlite_reference(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import repair_draft_references

        conn = _init_db(tmp_path)

        # Create a run and finding without issue_draft_id
        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp001",
            "medium",
            "Test finding",
            draftable=True,
        )

        # Write a draft-created.json artifact
        artifact_dir = tmp_path / "artifacts" / "maintenance" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        draft_created = {
            "finding_fingerprint": "fp001",
            "project_id": "proj-1",
            "skill_id": "test-skill",
            "draft_id": "draft-repair-001",
            "draft_artifact_path": "artifacts/issues/proj-1/draft-repair-001",
        }
        (artifact_dir / "draft-created.json").write_text(json.dumps(draft_created))
        # Insert draft row so FK constraint is satisfied
        upsert_issue_draft(
            conn,
            {
                "draft_id": "draft-repair-001",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Repaired draft",
                "readiness": 0.5,
                "artifact_path": "artifacts/issues/proj-1/draft-repair-001",
            },
        )

        repairs = repair_draft_references(tmp_path, conn)

        assert repairs == 1
        row = conn.execute(
            "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint=?",
            ("fp001",),
        ).fetchone()
        assert row[0] == "draft-repair-001"
        conn.close()

    def test_repair_ignores_missing_or_invalid_draft_artifact(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import repair_draft_references

        conn = _init_db(tmp_path)

        # Create a run with no artifact dir
        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp002",
            "medium",
            "Test finding",
            draftable=True,
        )

        # No draft-created.json written — repair should find nothing
        repairs = repair_draft_references(tmp_path, conn)
        assert repairs == 0

        # Also test with invalid JSON
        artifact_dir = tmp_path / "artifacts" / "maintenance" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "draft-created.json").write_text("not valid json{{{")

        repairs = repair_draft_references(tmp_path, conn)
        assert repairs == 0
        conn.close()

    def test_repair_does_not_duplicate_existing_draft_reference(self, tmp_path: Path) -> None:
        from portfolio_manager.maintenance_drafts import repair_draft_references

        conn = _init_db(tmp_path)

        # Create a run and finding WITH issue_draft_id already set
        run_id = start_run(conn, "proj-1", "test-skill")
        insert_finding(
            conn,
            run_id,
            "fp003",
            "medium",
            "Test finding",
            draftable=True,
        )
        # Need a draft row for FK
        upsert_issue_draft(
            conn,
            {
                "draft_id": "draft-already-set",
                "project_id": "proj-1",
                "state": "draft",
                "title": "Already set",
                "readiness": 0.5,
                "artifact_path": "artifacts/issues/proj-1/draft-already-set",
            },
        )
        conn.execute(
            "UPDATE maintenance_findings SET issue_draft_id=? WHERE fingerprint=?",
            ("draft-already-set", "fp003"),
        )
        conn.commit()

        # Write a draft-created.json that references the same finding
        artifact_dir = tmp_path / "artifacts" / "maintenance" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        draft_created = {
            "finding_fingerprint": "fp003",
            "project_id": "proj-1",
            "skill_id": "test-skill",
            "draft_id": "draft-repair-002",
            "draft_artifact_path": "artifacts/issues/proj-1/draft-repair-002",
        }
        (artifact_dir / "draft-created.json").write_text(json.dumps(draft_created))

        repairs = repair_draft_references(tmp_path, conn)
        assert repairs == 0

        # Verify original value is preserved
        row = conn.execute(
            "SELECT issue_draft_id FROM maintenance_findings WHERE fingerprint=?",
            ("fp003",),
        ).fetchone()
        assert row[0] == "draft-already-set"
        conn.close()
