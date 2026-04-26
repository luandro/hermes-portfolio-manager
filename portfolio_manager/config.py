"""Configuration loading for the Portfolio Manager plugin.

Handles: root resolution, YAML loading, field validation, enum validation,
duplicate-ID detection, path normalization, and project filtering/sorting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GithubRef:
    owner: str
    repo: str


@dataclass(frozen=True)
class LocalPaths:
    base_path: Path
    issue_worktree_pattern: str


@dataclass(frozen=True)
class ProjectConfig:
    id: str
    name: str
    repo: str
    github: GithubRef
    priority: str
    status: str
    default_branch: str = "auto"
    local: LocalPaths = field(default_factory=lambda: LocalPaths(Path(), ""))
    protected_paths: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PortfolioConfig:
    version: int
    projects: list[ProjectConfig]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PRIORITIES = ("critical", "high", "medium", "low", "paused")
VALID_STATUSES = ("active", "paused", "archived", "blocked", "missing")
PRIORITY_ORDER = {p: i for i, p in enumerate(VALID_PRIORITIES)}

REQUIRED_PROJECT_FIELDS = ("id", "name", "repo", "priority", "status")
REQUIRED_GITHUB_FIELDS = ("owner", "repo")


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """Raised when the portfolio configuration is invalid or missing."""


# ---------------------------------------------------------------------------
# 1.1 resolve_root
# ---------------------------------------------------------------------------


def resolve_root(root: str | None = None) -> Path:
    """Resolve the agent system root path.

    Priority: explicit arg > AGENT_SYSTEM_ROOT env > ~/.agent-system
    """
    if root is not None:
        return Path(root).expanduser()
    env = os.environ.get("AGENT_SYSTEM_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".agent-system"


# ---------------------------------------------------------------------------
# 1.3 load_projects_config
# ---------------------------------------------------------------------------


def load_projects_config(root: Path) -> PortfolioConfig:
    """Load and validate ``{root}/config/projects.yaml``.

    Raises ConfigError on missing file, parse failure, or validation errors.
    """
    config_path = root / "config" / "projects.yaml"

    if not config_path.exists():
        raise ConfigError(f"Config file is missing: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping at the top level.")

    version = raw.get("version")
    if version != 1:
        raise ConfigError(f"Unsupported config version: {version!r}")

    raw_projects = raw.get("projects")
    if not isinstance(raw_projects, list):
        raise ConfigError("'projects' must be a list.")

    projects = _validate_and_build_projects(raw_projects, root)
    return PortfolioConfig(version=version, projects=projects)


# ---------------------------------------------------------------------------
# Internal: validation + construction
# ---------------------------------------------------------------------------


def _validate_and_build_projects(
    raw_projects: list[dict[str, object]],
    root: Path,
) -> list[ProjectConfig]:
    """Validate every project entry and return a list of ProjectConfig."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    projects: list[ProjectConfig] = []

    for idx, raw in enumerate(raw_projects):
        prefix = f"project[{idx}]"
        entry_errors: list[str] = []

        if not isinstance(raw, dict):
            errors.append(f"{prefix}: must be a mapping, got {type(raw).__name__}")
            continue

        # 1.4 — required fields
        for fld in REQUIRED_PROJECT_FIELDS:
            if fld not in raw or not raw[fld]:
                entry_errors.append(f"{prefix}: missing required field '{fld}'")

        github_raw = raw.get("github")
        if not isinstance(github_raw, dict):
            entry_errors.append(f"{prefix}: 'github' must be a mapping")
        else:
            for fld in REQUIRED_GITHUB_FIELDS:
                if fld not in github_raw or not github_raw[fld]:
                    entry_errors.append(f"{prefix}: missing required field 'github.{fld}'")

        if entry_errors:
            errors.extend(entry_errors)
            # Keep collecting but skip enum / duplicate checks for broken entries
            continue

        # 1.5 — enum validation
        priority = str(raw["priority"])
        status = str(raw["status"])

        if priority not in VALID_PRIORITIES:
            entry_errors.append(f"{prefix}: invalid priority '{priority}'")
        if status not in VALID_STATUSES:
            entry_errors.append(f"{prefix}: invalid status '{status}'")

        # 1.6 — duplicate IDs
        project_id = str(raw["id"])
        if project_id in seen_ids:
            entry_errors.append(f"{prefix}: duplicate project id '{project_id}'")
        seen_ids.add(project_id)

        if entry_errors:
            errors.extend(entry_errors)
            continue

        # 1.7 — normalize local paths
        local_raw = raw.get("local")
        project_id_str = str(raw["id"])

        if isinstance(local_raw, dict):
            if local_raw.get("base_path"):
                bp = Path(str(local_raw["base_path"]))
                if not bp.is_absolute():
                    bp = root / bp
                bp = bp.resolve()
                if not bp.is_relative_to(root.resolve()):
                    errors.append(f"{prefix}: 'local.base_path' must be inside {root}")
                base_path = bp
            else:
                base_path = root / "worktrees" / project_id_str

            issue_pattern = (
                str(local_raw["issue_worktree_pattern"])
                if local_raw.get("issue_worktree_pattern")
                else str(root / "worktrees" / f"{project_id_str}-issue-{{issue_number}}")
            )
        else:
            base_path = root / "worktrees" / project_id_str
            issue_pattern = str(root / "worktrees" / f"{project_id_str}-issue-{{issue_number}}")

        protected = raw.get("protected_paths")
        protected_paths = list(protected) if isinstance(protected, list) else []

        # github_raw is guaranteed dict here: the isinstance check on line 153
        # adds an entry_error, and both error-guards (lines 160, 180) continue.
        assert isinstance(github_raw, dict)

        projects.append(
            ProjectConfig(
                id=project_id,
                name=str(raw["name"]),
                repo=str(raw["repo"]),
                github=GithubRef(
                    owner=str(github_raw["owner"]),
                    repo=str(github_raw["repo"]),
                ),
                priority=priority,
                status=status,
                default_branch=str(raw.get("default_branch", "auto") or "auto"),
                local=LocalPaths(base_path=base_path, issue_worktree_pattern=issue_pattern),
                protected_paths=protected_paths,
            )
        )

    if errors:
        # Report all accumulated validation errors
        raise ConfigError("; ".join(errors))

    return projects


# ---------------------------------------------------------------------------
# 1.8 select_projects
# ---------------------------------------------------------------------------


def select_projects(
    config: PortfolioConfig,
    *,
    status: str | None = None,
    include_archived: bool = False,
    include_paused: bool = False,
) -> list[ProjectConfig]:
    """Filter and sort projects from the portfolio config.

    When *status* is provided, only projects matching that status are returned
    (the ``include_archived`` / ``include_paused`` flags are ignored).

    When *status* is ``None``, projects are filtered by the boolean flags:
    archived and paused projects are excluded unless the corresponding flag is
    set.

    Results are sorted by priority: critical > high > medium > low > paused.
    """
    result: list[ProjectConfig] = []

    for p in config.projects:
        if status is not None:
            if p.status != status:
                continue
        else:
            if not include_archived and p.status == "archived":
                continue
            if not include_paused and p.status == "paused":
                continue
        result.append(p)

    result.sort(key=lambda p: PRIORITY_ORDER.get(p.priority, 99))
    return result
