"""Repository guidance-docs skill."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from portfolio_manager.maintenance_models import (
    MaintenanceContext,
    MaintenanceFinding,
    MaintenanceSkillResult,
    MaintenanceSkillSpec,
)
from portfolio_manager.maintenance_registry import REGISTRY

SPEC = MaintenanceSkillSpec(
    id="repo_guidance_docs",
    name="Repo Guidance Docs",
    description="Check whether repositories have basic agent and human guidance documents",
    default_interval_hours=168,
    default_enabled=False,
    supports_issue_drafts=False,
    required_state=[],
    allowed_commands=[
        ["gh", "api", "--method", "GET", "repos/OWNER/REPO/contents/PATH"],
        ["gh", "api", "--method", "GET", "repos/OWNER/REPO/commits?path=PATH&per_page=1"],
    ],
    config_schema={
        "required_files": {"type": "array", "default": ["README.md", "AGENTS.md"]},
        "optional_files": {"type": "array", "default": ["CLAUDE.md", "CONTRIBUTING.md"]},
        "freshness_days": {"type": "integer", "default": 180},
        "create_issue_drafts": {"type": "boolean", "default": False},
    },
)

_URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_SHELL_META_RE = re.compile(r"[;&|$><`\\*?\[\]{}()!#\n\r]")


def _normalized_title(title: str) -> str:
    return " ".join(title.lower().split())


def _fingerprint(project_id: str, source_type: str, source_id: str, title: str) -> str:
    raw = f"{project_id}{SPEC.id}{source_type}{source_id}{_normalized_title(title)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _list_config(ctx: MaintenanceContext, key: str, default: list[str]) -> list[str]:
    value = ctx.skill_config.get(key, default)
    if not isinstance(value, list):
        return default
    return [str(item) for item in value]


def _int_config(ctx: MaintenanceContext, key: str, default: int) -> int:
    try:
        value = int(ctx.skill_config.get(key, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _validate_doc_path(path: str) -> str | None:
    if not path or path.startswith("/") or ".." in path.split("/"):
        return "path must be relative and cannot contain '..'"
    if _URL_SCHEME_RE.match(path):
        return "path cannot contain a URL scheme"
    if _SHELL_META_RE.search(path):
        return "path contains unsafe shell metacharacters"
    return None


def _run_gh(owner: str, repo: str, endpoint: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", "api", "--method", "GET", endpoint],
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
        cwd=None,
    )


def _gh_json(owner: str, repo: str, endpoint: str) -> tuple[bool, Any | None, str | None]:
    try:
        result = _run_gh(owner, repo, endpoint)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, None, str(exc)
    if result.returncode != 0:
        return False, None, result.stderr.strip() or result.stdout.strip() or "gh api request failed"
    try:
        return True, json.loads(result.stdout or "null"), None
    except json.JSONDecodeError as exc:
        return False, None, f"invalid gh api JSON: {exc}"


def _latest_commit_date(owner: str, repo: str, path: str) -> tuple[datetime | None, str | None]:
    endpoint = f"repos/{owner}/{repo}/commits?path={path}&per_page=1"
    ok, data, warning = _gh_json(owner, repo, endpoint)
    if not ok:
        return None, warning
    if not isinstance(data, list) or not data:
        return None, None
    first = data[0]
    if not isinstance(first, dict):
        return None, None
    commit = first.get("commit")
    if not isinstance(commit, dict):
        return None, None
    committer = commit.get("committer")
    if not isinstance(committer, dict):
        return None, None
    return _parse_timestamp(str(committer.get("date") or "")), None


def _finding(
    ctx: MaintenanceContext,
    severity: Literal["info", "low", "medium", "high"],
    title: str,
    body: str,
    path: str,
    reason: str,
) -> MaintenanceFinding:
    return MaintenanceFinding(
        fingerprint=_fingerprint(ctx.project.id, "repository_file", path, title),
        severity=severity,
        title=title,
        body=body,
        source_type="repository_file",
        source_id=path,
        source_url=f"https://github.com/{ctx.project.github.owner}/{ctx.project.github.repo}/blob/{ctx.project.default_branch}/{path}",
        metadata={"path": path, "reason": reason},
        draftable=False,
    )


def execute(ctx: MaintenanceContext) -> MaintenanceSkillResult:
    """Check required and optional guidance documents through read-only gh api calls."""
    owner = ctx.project.github.owner
    repo = ctx.project.github.repo
    required_files = _list_config(ctx, "required_files", ["README.md", "AGENTS.md"])
    optional_files = _list_config(ctx, "optional_files", ["CLAUDE.md", "CONTRIBUTING.md"])
    freshness_days = _int_config(ctx, "freshness_days", 180)
    stale_cutoff = ctx.now.astimezone(UTC) - timedelta(days=freshness_days)

    findings: list[MaintenanceFinding] = []
    warnings: list[str] = []

    for path, required in [(path, True) for path in required_files] + [(path, False) for path in optional_files]:
        validation_error = _validate_doc_path(path)
        if validation_error:
            warnings.append(f"Skipping unsafe guidance doc path {path!r}: {validation_error}")
            continue

        contents_endpoint = f"repos/{owner}/{repo}/contents/{path}"
        exists, _data, warning = _gh_json(owner, repo, contents_endpoint)
        if not exists:
            if warning:
                warnings.append(f"{path}: {warning}")
            if required:
                severity: Literal["low", "medium"] = "medium" if path == "AGENTS.md" else "low"
                findings.append(
                    _finding(
                        ctx,
                        severity,
                        f"Missing required guidance document: {path}",
                        f"{path} is configured as a required repository guidance document but was not found.",
                        path,
                        "missing_required",
                    )
                )
            else:
                findings.append(
                    _finding(
                        ctx,
                        "info",
                        f"Missing optional guidance document: {path}",
                        f"{path} is configured as an optional repository guidance document but was not found.",
                        path,
                        "missing_optional",
                    )
                )
            continue

        commit_date, commit_warning = _latest_commit_date(owner, repo, path)
        if commit_warning:
            warnings.append(f"{path}: {commit_warning}")
        if commit_date is not None and commit_date < stale_cutoff:
            findings.append(
                _finding(
                    ctx,
                    "low",
                    f"Stale guidance document: {path}",
                    f"{path} has not had a recent commit within {freshness_days} days.",
                    path,
                    "stale",
                )
            )

    return MaintenanceSkillResult(
        skill_id=SPEC.id,
        project_id=ctx.project.id,
        status="success",
        findings=findings,
        summary=f"Repo guidance docs check complete: {len(findings)} finding(s) found",
        warnings=warnings,
    )


REGISTRY.register(SPEC, execute)
