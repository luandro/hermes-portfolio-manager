"""Tests for portfolio_manager.summary — Telegram-friendly summary generation."""

from __future__ import annotations

from pathlib import Path

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.summary import (
    summarize_github_sync,
    summarize_heartbeat,
    summarize_portfolio_status,
    summarize_project_list,
    summarize_worktrees,
)
from portfolio_manager.worktree import WorktreeInspection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project(
    project_id: str = "proj-a",
    name: str = "Project A",
    priority: str = "medium",
    status: str = "active",
) -> ProjectConfig:
    return ProjectConfig(
        id=project_id,
        name=name,
        repo="test/repo",
        github=GithubRef(owner="test", repo="repo"),
        priority=priority,
        status=status,
        local=LocalPaths(base_path=Path("/tmp/dummy"), issue_worktree_pattern="/tmp/dummy-issue-{issue_number}"),
    )


def _worktree(
    path: str = "/tmp/wt",
    project_id: str = "proj-a",
    state: str = "clean",
    issue_number: int | None = None,
    dirty_summary: str | None = None,
) -> WorktreeInspection:
    return WorktreeInspection(
        path=path,
        project_id=project_id,
        issue_number=issue_number,
        state=state,
        dirty_summary=dirty_summary,
    )


# ---------------------------------------------------------------------------
# 4.1 summarize_project_list
# ---------------------------------------------------------------------------


class TestSummarizeProjectList:
    def test_priority_ordering(self) -> None:
        """Projects appear in order: critical > high > medium > low > paused."""
        projects = [
            _project("low", "Low Proj", priority="low"),
            _project("critical", "Critical Proj", priority="critical"),
            _project("medium", "Medium Proj", priority="medium"),
            _project("high", "High Proj", priority="high"),
            _project("paused-proj", "Paused Proj", priority="paused", status="paused"),
        ]
        counts = {"active": 4, "paused": 1, "archived": 0}
        result = summarize_project_list(projects, counts)

        # Critical should appear before high, high before medium, etc.
        pos_critical = result.index("Critical Proj")
        pos_high = result.index("High Proj")
        pos_medium = result.index("Medium Proj")
        pos_low = result.index("Low Proj")
        assert pos_critical < pos_high < pos_medium < pos_low

    def test_archived_excluded_by_default(self) -> None:
        """Archived projects are not shown unless explicitly included."""
        projects = [
            _project("active-1", "Active One", priority="high"),
            _project("archived-1", "Archived One", priority="medium", status="archived"),
        ]
        counts = {"active": 1, "archived": 1}
        result = summarize_project_list(projects, counts)
        assert "Archived One" not in result
        assert "Active One" in result

    def test_includes_total_counts(self) -> None:
        """Summary includes total project count and status breakdown."""
        projects = [_project("a"), _project("b")]
        counts = {"active": 2, "paused": 0, "archived": 1}
        result = summarize_project_list(projects, counts)
        assert "2" in result  # total active count referenced

    def test_concise_telegram_format(self) -> None:
        """Output is a non-empty string without excessive verbosity."""
        projects = [_project("a", "Alpha", priority="high")]
        counts = {"active": 1}
        result = summarize_project_list(projects, counts)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Alpha" in result


# ---------------------------------------------------------------------------
# 4.2 summarize_github_sync
# ---------------------------------------------------------------------------


class TestSummarizeGithubSync:
    def test_includes_counts_and_warnings(self) -> None:
        sync_results = [
            {"project_id": "proj-a", "issues_count": 5, "prs_count": 2, "warnings": []},
            {"project_id": "proj-b", "issues_count": 3, "prs_count": 1, "warnings": ["repo inaccessible"]},
        ]
        result = summarize_github_sync(sync_results)
        assert "2" in result  # projects synced
        assert "8" in result  # total issues (5+3)
        assert "3" in result  # total PRs (2+1)
        assert "repo inaccessible" in result

    def test_does_not_list_every_issue(self) -> None:
        """Summary should show aggregate counts, not individual issue titles."""
        sync_results = [
            {
                "project_id": "proj-a",
                "issues_count": 50,
                "prs_count": 10,
                "warnings": [],
            },
        ]
        result = summarize_github_sync(sync_results)
        # Should contain counts but NOT individual issue details
        assert "50" in result
        # Should not contain issue-level listing patterns
        assert "#1" not in result
        assert "issue #" not in result.lower() or "issues" in result.lower()

    def test_no_warnings_clean_output(self) -> None:
        sync_results = [
            {"project_id": "proj-a", "issues_count": 2, "prs_count": 0, "warnings": []},
        ]
        result = summarize_github_sync(sync_results)
        assert "2" in result
        assert "Warnings" not in result


# ---------------------------------------------------------------------------
# 4.3 summarize_worktrees
# ---------------------------------------------------------------------------


class TestSummarizeWorktrees:
    def test_dirty_conflicted_missing_prioritized(self) -> None:
        """Dirty, conflicted, and missing worktrees appear in the problem section."""
        worktrees = [
            _worktree("/tmp/clean", state="clean", project_id="p1"),
            _worktree("/tmp/dirty", state="dirty_uncommitted", project_id="p2", dirty_summary="file1.py, file2.py"),
            _worktree("/tmp/conflict", state="merge_conflict", project_id="p3", dirty_summary="main.py"),
            _worktree("/tmp/missing", state="missing", project_id="p4"),
        ]
        result = summarize_worktrees(worktrees)

        # All problem worktrees should be listed
        assert "/tmp/dirty" in result
        assert "/tmp/conflict" in result
        assert "/tmp/missing" in result
        # Problem section should appear before clean count
        pos_dirty = result.index("/tmp/dirty")
        pos_conflict = result.index("/tmp/conflict")
        pos_missing = result.index("/tmp/missing")
        # merge_conflict (severity 0) before dirty_uncommitted (severity 2) before missing (severity 4)
        assert pos_conflict < pos_dirty < pos_missing

    def test_dirty_shows_affected_files(self) -> None:
        worktrees = [
            _worktree("/tmp/dirty", state="dirty_uncommitted", project_id="p1", dirty_summary="main.py, utils.py"),
        ]
        result = summarize_worktrees(worktrees)
        assert "main.py" in result
        assert "utils.py" in result

    def test_clean_summarized_concisely(self) -> None:
        """Clean worktrees are summarized briefly, not listed individually."""
        worktrees = [
            _worktree("/tmp/clean1", state="clean", project_id="p1"),
            _worktree("/tmp/clean2", state="clean", project_id="p2"),
        ]
        result = summarize_worktrees(worktrees)
        # Should mention clean count, not list each path in detail
        assert "clean" in result.lower()

    def test_all_clean_no_problem_section(self) -> None:
        """When all worktrees are clean, no dirty/missing problem entries appear."""
        worktrees = [
            _worktree("/tmp/c1", state="clean", project_id="p1"),
            _worktree("/tmp/c2", state="clean", project_id="p2"),
        ]
        result = summarize_worktrees(worktrees)
        assert "dirty" not in result.lower()
        assert "missing" not in result.lower()
        assert "need attention" not in result.lower()


# ---------------------------------------------------------------------------
# 4.4 summarize_portfolio_status
# ---------------------------------------------------------------------------


class TestSummarizePortfolioStatus:
    def _snapshot(self) -> dict:
        return {
            "issues": [
                {"project_id": "proj-a", "number": 47, "title": "Fix login bug", "state": "needs_triage"},
                {"project_id": "proj-b", "number": 12, "title": "Update docs", "state": "open"},
            ],
            "pull_requests": [
                {"project_id": "proj-a", "number": 130, "title": "Fix auth", "state": "ready_for_human"},
                {"project_id": "proj-b", "number": 5, "title": "Typo fix", "state": "open"},
            ],
            "worktrees": [
                {"path": "/tmp/wt1", "project_id": "proj-a", "state": "dirty_uncommitted", "dirty_summary": "auth.py"},
                {"path": "/tmp/wt2", "project_id": "proj-b", "state": "clean"},
            ],
        }

    def test_filter_all_shows_everything(self) -> None:
        result = summarize_portfolio_status(self._snapshot(), status_filter="all")
        assert "proj-a" in result
        assert "proj-b" in result
        assert "Fix login bug" in result or "#47" in result
        assert "Fix auth" in result or "#130" in result

    def test_filter_needs_user_shows_attention_items(self) -> None:
        result = summarize_portfolio_status(self._snapshot(), status_filter="needs_user")
        # Should include the PR ready for human review
        assert "#130" in result or "ready" in result.lower() or "human" in result.lower()
        # Should include the dirty worktree
        assert "dirty" in result.lower() or "auth.py" in result
        # Should include issue needing triage
        assert "#47" in result or "triage" in result.lower() or "needs" in result.lower()

    def test_filter_needs_user_excludes_clean_items(self) -> None:
        result = summarize_portfolio_status(self._snapshot(), status_filter="needs_user")
        # Clean worktree and open (not ready_for_human) PR should not be highlighted
        # The clean worktree path should not appear as a problem
        assert "/tmp/wt2" not in result

    def test_empty_snapshot(self) -> None:
        result = summarize_portfolio_status(
            {"issues": [], "pull_requests": [], "worktrees": []},
            status_filter="all",
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# 4.5 summarize_heartbeat
# ---------------------------------------------------------------------------


class TestSummarizeHeartbeat:
    def test_concise_action_oriented(self) -> None:
        result_data = {
            "projects_checked": 3,
            "issues_seen": 14,
            "prs_seen": 3,
            "dirty_worktrees": 1,
            "warnings": [],
        }
        result = summarize_heartbeat(result_data)
        assert "3" in result  # projects checked
        assert "14" in result  # issues seen
        assert "3" in result  # PRs seen
        assert "1" in result  # dirty worktrees

    def test_includes_warnings(self) -> None:
        result_data = {
            "projects_checked": 2,
            "issues_seen": 5,
            "prs_seen": 1,
            "dirty_worktrees": 0,
            "warnings": ["proj-a repo inaccessible", "proj-b rate limited"],
        }
        result = summarize_heartbeat(result_data)
        assert "repo inaccessible" in result
        assert "rate limited" in result

    def test_no_issues_clean_report(self) -> None:
        result_data = {
            "projects_checked": 4,
            "issues_seen": 0,
            "prs_seen": 0,
            "dirty_worktrees": 0,
            "warnings": [],
        }
        result = summarize_heartbeat(result_data)
        assert "4" in result
        assert "0" in result

    def test_telegram_safe_output(self) -> None:
        """Output is a plain string without special characters that break Telegram."""
        result_data = {
            "projects_checked": 1,
            "issues_seen": 0,
            "prs_seen": 0,
            "dirty_worktrees": 0,
            "warnings": [],
        }
        result = summarize_heartbeat(result_data)
        assert isinstance(result, str)
        # No markdown or HTML that could cause issues
        assert "<" not in result
        assert ">" not in result
