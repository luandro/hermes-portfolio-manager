"""Tests for portfolio_manager/issue_resolver.py — Phase 3: Project Resolution.

Deterministic token-scoring resolution. No LLM calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from portfolio_manager.config import GithubRef, PortfolioConfig, ProjectConfig
from portfolio_manager.issue_resolver import resolve_project

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_test_config(
    projects: list[tuple[str, str, str]],
    *,
    statuses: list[str] | None = None,
) -> PortfolioConfig:
    """Build a PortfolioConfig from (project_id, name, owner/repo) tuples.

    If *statuses* is given it must be the same length as *projects*.
    """
    return PortfolioConfig(
        version=1,
        projects=[
            ProjectConfig(
                id=pid,
                name=name,
                repo=f"git@github.com:{repo}.git",
                github=GithubRef(
                    owner=repo.split("/")[0],
                    repo=repo.split("/")[1],
                ),
                priority="medium",
                status=statuses[i] if statuses else "active",
            )
            for i, (pid, name, repo) in enumerate(projects)
        ],
    )


# ===================================================================
# 3.1 Exact project-id match
# ===================================================================


class TestResolveExactProjectId:
    def test_resolve_exact_id(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
                ("comapeo-mobile", "CoMapeo Mobile", "digidem/comapeo-mobile"),
            ],
        )

        result = resolve_project(config, project_ref="comapeo-cloud-app")
        assert result.state == "resolved"
        assert result.project_id == "comapeo-cloud-app"


# ===================================================================
# 3.2 Exact owner/repo match
# ===================================================================


class TestResolveExactOwnerRepo:
    def test_resolve_exact_owner_repo(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
            ],
        )

        result = resolve_project(config, project_ref="digidem/comapeo-cloud")
        assert result.state == "resolved"
        assert result.project_id == "comapeo-cloud-app"


# ===================================================================
# 3.3 Exact project name match
# ===================================================================


class TestResolveExactProjectName:
    def test_resolve_exact_name(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
            ],
        )

        result = resolve_project(config, project_ref="CoMapeo Cloud App")
        assert result.state == "resolved"


# ===================================================================
# 3.4 Fuzzy single match via text tokens
# ===================================================================


class TestResolveFuzzySingleMatch:
    def test_fuzzy_single_match(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
                ("edt-migration", "EDT Migration", "digidem/edt-tool"),
            ],
        )

        result = resolve_project(
            config,
            text="Create an issue for the EDT migration project about Markdown imports",
        )
        assert result.state == "resolved"
        assert result.project_id == "edt-migration"


# ===================================================================
# 3.5 Ambiguous project — multiple candidates
# ===================================================================


class TestResolveAmbiguousProject:
    def test_ambiguous_project_returns_candidates(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
                ("comapeo-mobile", "CoMapeo Mobile", "digidem/comapeo-mobile"),
            ],
        )

        result = resolve_project(
            config,
            text="Create an issue for CoMapeo about export improvements",
        )
        assert result.state == "ambiguous"
        assert len(result.candidates) >= 2


# ===================================================================
# 3.6 Not found
# ===================================================================


class TestResolveProjectNotFound:
    def test_project_not_found(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("comapeo-cloud-app", "CoMapeo Cloud App", "digidem/comapeo-cloud"),
            ],
        )

        result = resolve_project(config, text="Create an issue for nonexistent-project")
        assert result.state == "not_found"


# ===================================================================
# 3.7 Archived projects excluded / included
# ===================================================================


class TestArchivedProjectsExcluded:
    def test_archived_excluded_by_default(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("old-project", "Old Project", "digidem/old-repo"),
                ("new-project", "New Project", "digidem/new-repo"),
            ],
            statuses=["archived", "active"],
        )

        result = resolve_project(config, project_ref="old-project")
        assert result.state == "not_found"

    def test_archived_included_when_requested(self, tmp_path: Path) -> None:
        config = _make_test_config(
            [
                ("old-project", "Old Project", "digidem/old-repo"),
                ("new-project", "New Project", "digidem/new-repo"),
            ],
            statuses=["archived", "active"],
        )

        result = resolve_project(config, project_ref="old-project", include_archived=True)
        assert result.state == "resolved"
        assert result.project_id == "old-project"
