"""Project admin data models and validation for MVP 2.

Pydantic-based models with field validators, auto-merge policy,
path normalization, and default protected paths.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PROTECTED_PATHS = [
    ".github/workflows/**",
    "infra/**",
    "auth/**",
    "security/**",
    "migrations/**",
]

VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low", "paused"})
VALID_STATUSES = frozenset({"active", "paused", "archived", "blocked", "missing"})
VALID_MAX_RISKS = frozenset({"low", "medium"})

PROJECT_ID_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


# ---------------------------------------------------------------------------
# Auto-merge sub-model
# ---------------------------------------------------------------------------


class AutoMergeConfig(BaseModel):
    model_config = {"extra": "forbid"}
    enabled: bool = False
    max_risk: str | None = None

    @field_validator("max_risk")
    @classmethod
    def _validate_max_risk(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_MAX_RISKS:
            raise ValueError(f"max_risk must be one of {sorted(VALID_MAX_RISKS)}, got {v!r}")
        return v

    @model_validator(mode="after")
    def _default_max_risk(self) -> AutoMergeConfig:
        if self.enabled and self.max_risk is None:
            self.max_risk = "low"
        return self


# ---------------------------------------------------------------------------
# Project model
# ---------------------------------------------------------------------------


class AdminProjectConfig(BaseModel):
    model_config = {"populate_by_name": True, "extra": "allow"}

    id: str
    name: str
    repo: str
    github_owner: str
    github_repo: str
    priority: str = "medium"
    status: str = "active"
    default_branch: str = "auto"
    auto_merge: AutoMergeConfig = Field(default_factory=AutoMergeConfig)
    notes: str | None = None
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    protected_paths: list[str] = Field(default_factory=lambda: list(DEFAULT_PROTECTED_PATHS))
    labels: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        if not v or not PROJECT_ID_RE.match(v):
            raise ValueError(f"Invalid project ID {v!r}. Must match {PROJECT_ID_RE.pattern}")
        return v

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: str) -> str:
        if v not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority {v!r}. Valid: {sorted(VALID_PRIORITIES)}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"Invalid status {v!r}. Valid: {sorted(VALID_STATUSES)}")
        return v


# ---------------------------------------------------------------------------
# Portfolio model
# ---------------------------------------------------------------------------


class AdminPortfolioConfig(BaseModel):
    model_config = {"extra": "allow"}
    version: int = 1
    projects: list[AdminProjectConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_project_id(project_id: str) -> None:
    if not project_id or not PROJECT_ID_RE.match(project_id):
        raise ValueError(f"Invalid project ID {project_id!r}. Must match {PROJECT_ID_RE.pattern}")


def validate_auto_merge(enabled: bool, max_risk: str | None = None) -> AutoMergeConfig:
    cfg = AutoMergeConfig(enabled=enabled, max_risk=max_risk)
    if enabled:
        _warn_auto_merge_policy_only()
    return cfg


def _warn_auto_merge_policy_only() -> None:
    warnings.warn(
        "MVP 2 stores auto-merge policy only. It does not execute merges or create PRs.",
        UserWarning,
        stacklevel=2,
    )


def validate_priority(priority: str) -> None:
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority {priority!r}. Valid: {sorted(VALID_PRIORITIES)}")


def validate_status(status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}. Valid: {sorted(VALID_STATUSES)}")


def get_default_protected_paths() -> list[str]:
    return list(DEFAULT_PROTECTED_PATHS)


def expand_user_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def serialize_path_for_config(p: Path) -> str:
    try:
        home = Path.home().resolve()
        relative = p.resolve().relative_to(home)
        return f"~/{relative}"
    except ValueError:
        return str(p)


def project_base_path(root: Path, project_id: str) -> str:
    validate_project_id(project_id)
    return str(root / "worktrees" / project_id)
