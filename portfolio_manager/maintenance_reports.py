"""Maintenance report generation and loading — Phase 3.

Writes report.md, findings.json, and metadata.json for maintenance runs.
All writes go through maintenance_artifacts.write_artifact for path safety
and secret redaction.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from portfolio_manager.maintenance_artifacts import write_artifact

if TYPE_CHECKING:
    from pathlib import Path


def write_maintenance_report(
    root: Path,
    run_id: str,
    findings: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> Path:
    """Write a human-readable report.md for a maintenance run."""
    now = datetime.now(UTC).isoformat()
    severity_counts = Counter(f.get("severity", "info") for f in findings)

    lines: list[str] = [
        "# Maintenance Report",
        "",
        f"- **Run ID**: {run_id}",
        f"- **Timestamp**: {now}",
        "",
        "## Summary",
        "",
        f"Total findings: {len(findings)}",
        "",
    ]

    if severity_counts:
        for sev in ("high", "medium", "low", "info"):
            count = severity_counts.get(sev, 0)
            if count:
                lines.append(f"- {sev}: {count}")
        lines.append("")

    lines.append("## Findings")
    lines.append("")

    if findings:
        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. {f.get('title', 'Untitled')}")
            lines.append(f"- **Severity**: {f.get('severity', 'info')}")
            lines.append(f"- **Source**: {f.get('source_type', 'unknown')}")
            if f.get("source_url"):
                lines.append(f"- **URL**: {f['source_url']}")
            lines.append("")
            lines.append(f.get("body", ""))
            lines.append("")
    else:
        lines.append("No findings.")
        lines.append("")

    content = "\n".join(lines)
    return write_artifact(root, run_id, "report.md", content)


def write_findings_json(
    root: Path,
    run_id: str,
    findings: list[dict[str, Any]],
) -> Path:
    """Write findings.json with deterministic output."""
    content = json.dumps(findings, indent=2, sort_keys=True)
    return write_artifact(root, run_id, "findings.json", content)


def write_metadata_json(
    root: Path,
    run_id: str,
    metadata: dict[str, Any],
) -> Path:
    """Write metadata.json for a maintenance run."""
    content = json.dumps(metadata, indent=2, sort_keys=True)
    return write_artifact(root, run_id, "metadata.json", content)


def list_report_runs(root: Path) -> list[str]:
    """List run_ids that have reports, sorted by modification time (newest first)."""
    base = root / "artifacts" / "maintenance"
    if not base.is_dir():
        return []
    runs: list[tuple[float, str]] = []
    for d in base.iterdir():
        if d.is_dir() and (d / "report.md").exists():
            runs.append((d.stat().st_mtime, d.name))
    runs.sort(key=lambda t: t[0], reverse=True)
    return [name for _, name in runs]


def load_report(root: Path, run_id: str) -> dict[str, Any] | None:
    """Load a specific report by run_id. Returns None if not found."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", run_id):
        return None
    base = root / "artifacts" / "maintenance" / run_id
    report_path = base / "report.md"
    if not report_path.exists():
        return None

    findings_path = base / "findings.json"
    metadata_path = base / "metadata.json"

    findings: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {}

    if findings_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            findings = json.loads(findings_path.read_text())

    if metadata_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            metadata = json.loads(metadata_path.read_text())

    return {
        "run_id": run_id,
        "report_md": report_path.read_text(),
        "findings": findings,
        "metadata": metadata,
    }


def load_latest_report(root: Path) -> dict[str, Any] | None:
    """Load the most recent report. Returns None if no reports exist."""
    runs = list_report_runs(root)
    if not runs:
        return None
    return load_report(root, runs[0])
