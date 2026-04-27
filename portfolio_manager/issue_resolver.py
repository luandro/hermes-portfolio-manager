"""Project resolution for issue creation — MVP 3.

Deterministic fuzzy project matching via token scoring. No LLM calls.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from portfolio_manager.config import PortfolioConfig, ProjectConfig


class ProjectResolutionResult:
    """Outcome of attempting to resolve a project reference."""

    __slots__ = ("candidates", "message", "project_id", "state")

    def __init__(
        self,
        *,
        state: str,
        project_id: str | None = None,
        candidates: list[dict[str, Any]] | None = None,
        message: str = "",
    ) -> None:
        self.state: str = state
        self.project_id: str | None = project_id
        self.candidates: list[dict[str, Any]] = candidates if candidates is not None else []
        self.message: str = message


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Split *text* into lowercase word tokens."""
    return [t.lower() for t in _WORD_RE.findall(text)]


def _split_hyphenated(text: str) -> list[str]:
    """Split on hyphens and non-alphanumeric boundaries, return lowercase tokens."""
    return [t.lower() for t in re.split(r"[-_/]+", text) if t]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _score_project(
    project: ProjectConfig,
    project_ref: str | None,
    text: str | None,
) -> int:
    """Return a match score for *project* given the provided hints."""
    score = 0
    owner_repo = f"{project.github.owner}/{project.github.repo}"

    ref_lower = project_ref.lower() if project_ref else ""

    # Exact matches (only via project_ref)
    if project_ref:
        if ref_lower == project.id.lower():
            score += 5
        if ref_lower == owner_repo.lower():
            score += 5
        if ref_lower == project.name.lower():
            score += 4

    # Token-based fuzzy scoring (only via *text*, not project_ref)
    if text:
        text_tokens = _tokenize(text)
        repo_tokens = _split_hyphenated(project.github.repo)
        name_tokens = _tokenize(project.name)
        id_tokens = _split_hyphenated(project.id)

        for token in text_tokens:
            if token in repo_tokens:
                score += 2
            if token in name_tokens:
                score += 1
            if token in id_tokens:
                score += 1

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_project(
    config: PortfolioConfig,
    *,
    project_ref: str | None = None,
    text: str | None = None,
    include_archived: bool = False,
) -> ProjectResolutionResult:
    """Resolve a project reference to a single project or report ambiguity.

    Uses deterministic token scoring — no LLM calls.
    """
    # Build candidate list, excluding archived unless requested
    candidates_projects: list[ProjectConfig] = []
    for p in config.projects:
        if p.status == "archived" and not include_archived:
            continue
        candidates_projects.append(p)

    if not candidates_projects:
        return ProjectResolutionResult(
            state="not_found",
            message="No projects available.",
        )

    # Score every candidate
    scores: dict[str, int] = {}
    for p in candidates_projects:
        scores[p.id] = _score_project(p, project_ref, text)

    # Sort by score descending
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    top_id, top_score = ranked[0]

    # No meaningful match
    if top_score < 2:
        return ProjectResolutionResult(
            state="not_found",
            message=f"No project matched the given reference (best score {top_score}).",
        )

    # Check for clear winner
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score >= 3 and (top_score - second_score) >= 2:
        return ProjectResolutionResult(
            state="resolved",
            project_id=top_id,
            message=f"Resolved to {top_id} (score {top_score}).",
        )

    # Ambiguous — two or more projects with score >= 2 and close together
    tied: list[dict[str, Any]] = []
    for pid, sc in ranked:
        if sc >= 2 and (top_score - sc) < 2:
            tied.append({"project_id": pid, "score": sc})
        else:
            break

    if len(tied) >= 2:
        return ProjectResolutionResult(
            state="ambiguous",
            candidates=tied,
            message=f"Ambiguous match: {len(tied)} candidates with similar scores.",
        )

    # Single candidate above threshold but not meeting resolved criteria.
    # top_score >= 2 is guaranteed here: we returned early when < 2 above, and
    # we only reach this point if the ambiguous branch (len(tied) >= 2) didn't match.
    return ProjectResolutionResult(
        state="resolved",
        project_id=top_id,
        message=f"Resolved to {top_id} (score {top_score}).",
    )
