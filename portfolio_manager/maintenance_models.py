"""Maintenance data models for MVP 4."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    import sqlite3
    from datetime import datetime
    from pathlib import Path

    from portfolio_manager.config import ProjectConfig


# ---------------------------------------------------------------------------
# 2.1 Skill definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceSkillSpec:
    id: str
    name: str
    description: str
    default_interval_hours: int
    default_enabled: bool
    supports_issue_drafts: bool
    required_state: list[str]
    allowed_commands: list[list[str]]
    config_schema: dict[str, Any]


# ---------------------------------------------------------------------------
# 2.1 Execution context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceContext:
    root: Path
    conn: sqlite3.Connection
    project: ProjectConfig
    skill_config: dict[str, Any]
    now: datetime
    refresh_github: bool


# ---------------------------------------------------------------------------
# 2.1 Finding model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceFinding:
    fingerprint: str
    severity: Literal["info", "low", "medium", "high"]
    title: str
    body: str
    source_type: str
    source_id: str | None
    source_url: str | None
    metadata: dict[str, Any]
    draftable: bool = True


# ---------------------------------------------------------------------------
# 2.1 Result model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaintenanceSkillResult:
    skill_id: str
    project_id: str
    status: Literal["success", "skipped", "blocked", "failed"]
    findings: list[MaintenanceFinding]
    summary: str
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 2.3 Stable finding fingerprints
# ---------------------------------------------------------------------------


def make_finding_fingerprint(
    skill_id: str,
    project_id: str,
    source_type: str,
    source_id: str | None,
    key: str,
) -> str:
    """Produce a stable SHA-256 fingerprint for deduplication."""
    raw = f"{skill_id}|{project_id}|{source_type}|{source_id or ''}|{key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
