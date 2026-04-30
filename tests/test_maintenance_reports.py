"""Tests for maintenance report generation and loading — Phase 3."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from portfolio_manager.maintenance_reports import (
    list_report_runs,
    load_latest_report,
    load_report,
    write_findings_json,
    write_maintenance_report,
    write_metadata_json,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_finding(
    fingerprint: str = "fp001",
    severity: str = "medium",
    title: str = "Test finding",
    body: str = "Details here",
    source_type: str = "issue",
    source_id: str | None = None,
    source_url: str | None = None,
) -> dict:
    return {
        "fingerprint": fingerprint,
        "severity": severity,
        "title": title,
        "body": body,
        "source_type": source_type,
        "source_id": source_id,
        "source_url": source_url,
        "metadata": {},
        "draftable": True,
    }


class TestReportMdContainsRequiredSections:
    def test_header_section(self, tmp_path: Path) -> None:
        findings = [_make_finding()]
        metadata = {
            "project_ids": ["proj1"],
            "skill_ids": ["skill1"],
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T01:00:00Z",
            "config_snapshot": {},
        }
        path = write_maintenance_report(tmp_path, "run001", findings, metadata)
        content = path.read_text()
        assert "run001" in content
        assert "Maintenance Report" in content

    def test_summary_section(self, tmp_path: Path) -> None:
        findings = [
            _make_finding(severity="high"),
            _make_finding(fingerprint="fp002", severity="low"),
        ]
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        path = write_maintenance_report(tmp_path, "run002", findings, metadata)
        content = path.read_text()
        assert "Summary" in content
        assert "high" in content
        assert "low" in content

    def test_findings_list_section(self, tmp_path: Path) -> None:
        findings = [_make_finding(title="Stale issue found")]
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        path = write_maintenance_report(tmp_path, "run003", findings, metadata)
        content = path.read_text()
        assert "Stale issue found" in content


class TestFindingsJsonContainsRequiredFields:
    def test_valid_json_list(self, tmp_path: Path) -> None:
        findings = [
            _make_finding(fingerprint="fp1"),
            _make_finding(fingerprint="fp2", severity="high"),
        ]
        path = write_findings_json(tmp_path, "run010", findings)
        data = json.loads(path.read_text())
        assert isinstance(data, list)
        assert len(data) == 2

    def test_finding_has_required_keys(self, tmp_path: Path) -> None:
        findings = [_make_finding()]
        path = write_findings_json(tmp_path, "run011", findings)
        data = json.loads(path.read_text())
        finding = data[0]
        for key in ("fingerprint", "severity", "title", "body", "source_type"):
            assert key in finding


class TestMetadataJsonContainsSelectedProjectsAndSkills:
    def test_metadata_has_project_ids(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": ["proj1", "proj2"],
            "skill_ids": ["skill_a"],
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T01:00:00Z",
            "config_snapshot": {"skills": {"skill_a": {"enabled": True}}},
        }
        path = write_metadata_json(tmp_path, "run020", metadata)
        data = json.loads(path.read_text())
        assert data["project_ids"] == ["proj1", "proj2"]
        assert data["skill_ids"] == ["skill_a"]

    def test_metadata_has_timestamps(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T01:00:00Z",
            "config_snapshot": {},
        }
        path = write_metadata_json(tmp_path, "run021", metadata)
        data = json.loads(path.read_text())
        assert "started_at" in data
        assert "completed_at" in data


class TestArtifactJsonIsValidAndStable:
    def test_deterministic_output(self, tmp_path: Path) -> None:
        findings = [_make_finding(fingerprint="fp1", severity="high")]
        path1 = write_findings_json(tmp_path, "run030", findings)
        content1 = path1.read_text()
        # Write again to same path
        path2 = write_findings_json(tmp_path, "run030", findings)
        content2 = path2.read_text()
        assert content1 == content2


class TestReportWithNoFindings:
    def test_empty_findings_report(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        path = write_maintenance_report(tmp_path, "run040", [], metadata)
        content = path.read_text()
        assert "0" in content  # zero findings count

    def test_empty_findings_json(self, tmp_path: Path) -> None:
        path = write_findings_json(tmp_path, "run041", [])
        data = json.loads(path.read_text())
        assert data == []


class TestReportWithMixedSeverityFindings:
    def test_counts_by_severity(self, tmp_path: Path) -> None:
        findings = [
            _make_finding(fingerprint="fp1", severity="high"),
            _make_finding(fingerprint="fp2", severity="high"),
            _make_finding(fingerprint="fp3", severity="medium"),
            _make_finding(fingerprint="fp4", severity="low"),
            _make_finding(fingerprint="fp5", severity="info"),
        ]
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        path = write_maintenance_report(tmp_path, "run050", findings, metadata)
        content = path.read_text()
        assert "high" in content
        assert "medium" in content
        assert "low" in content
        assert "info" in content


class TestListReportRunsEmpty:
    def test_no_runs_returns_empty(self, tmp_path: Path) -> None:
        assert list_report_runs(tmp_path) == []


class TestListReportRunsMultiple:
    def test_lists_run_ids(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        write_maintenance_report(tmp_path, "run_a", [], metadata)
        write_maintenance_report(tmp_path, "run_b", [], metadata)
        runs = list_report_runs(tmp_path)
        assert "run_a" in runs
        assert "run_b" in runs


class TestLoadLatestReport:
    def test_loads_most_recent(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "2025-01-01T00:00:00Z",
            "completed_at": "2025-01-01T01:00:00Z",
            "config_snapshot": {},
        }
        write_maintenance_report(tmp_path, "run_first", [], metadata)
        metadata2 = {
            "project_ids": [],
            "skill_ids": [],
            "started_at": "2025-06-01T00:00:00Z",
            "completed_at": "2025-06-01T01:00:00Z",
            "config_snapshot": {},
        }
        write_maintenance_report(tmp_path, "run_second", [], metadata2)
        report = load_latest_report(tmp_path)
        assert report is not None
        assert report["run_id"] == "run_second"

    def test_returns_none_when_empty(self, tmp_path: Path) -> None:
        assert load_latest_report(tmp_path) is None


class TestLoadReportNotFoundReturnsNone:
    def test_missing_report_returns_none(self, tmp_path: Path) -> None:
        assert load_report(tmp_path, "nonexistent") is None

    def test_load_existing_report(self, tmp_path: Path) -> None:
        metadata = {
            "project_ids": ["proj1"],
            "skill_ids": [],
            "started_at": "",
            "completed_at": "",
            "config_snapshot": {},
        }
        write_maintenance_report(tmp_path, "run_exists", [], metadata)
        report = load_report(tmp_path, "run_exists")
        assert report is not None
        assert report["run_id"] == "run_exists"
