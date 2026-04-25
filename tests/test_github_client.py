"""Tests for portfolio_manager.github_client — Phase 5.1 through 5.7."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from portfolio_manager.config import GithubRef, LocalPaths, ProjectConfig
from portfolio_manager.github_client import (
    IssueRecord,
    ProjectGitHubSyncResult,
    PullRequestRecord,
    ToolCheckResult,
    check_gh_auth,
    check_gh_available,
    list_open_issues,
    list_open_prs,
    map_pr_state,
    sync_project_github,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict]:
    path = FIXTURES_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def _make_project(project_id: str = "test-proj", owner: str = "acme", repo: str = "app") -> ProjectConfig:
    return ProjectConfig(
        id=project_id,
        name="Test Project",
        repo=f"git@github.com:{owner}/{repo}.git",
        github=GithubRef(owner=owner, repo=repo),
        priority="high",
        status="active",
        default_branch="main",
        local=LocalPaths(base_path=Path("/tmp/test"), issue_worktree_pattern="/tmp/test-issue-{issue_number}"),
    )


def _mock_subprocess_return(stdout: str = "", returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# 5.1 Fixture files exist and parse
# ---------------------------------------------------------------------------


class TestFixtures:
    def test_gh_fixtures_exist_and_parse(self):
        for name in (
            "gh_issues.open.json",
            "gh_prs.open.json",
            "gh_prs.failing-checks.json",
            "gh_prs.changes-requested.json",
            "gh_prs.approved-passing.json",
        ):
            data = _load_fixture(name)
            assert isinstance(data, list), f"{name} must be a JSON array"
            assert len(data) > 0, f"{name} must not be empty"


# ---------------------------------------------------------------------------
# 5.2 check_gh_available
# ---------------------------------------------------------------------------


class TestCheckGhAvailable:
    @patch("portfolio_manager.github_client.subprocess.run")
    def test_check_gh_available_success(self, mock_run: MagicMock):
        mock_run.return_value = _mock_subprocess_return(stdout="gh version 2.42.0\n")
        result = check_gh_available()
        assert isinstance(result, ToolCheckResult)
        assert result.available is True
        mock_run.assert_called_once_with(["gh", "--version"], capture_output=True, text=True, timeout=10, env=ANY)

    @patch("portfolio_manager.github_client.subprocess.run", side_effect=FileNotFoundError)
    def test_check_gh_available_missing(self, mock_run: MagicMock):
        result = check_gh_available()
        assert isinstance(result, ToolCheckResult)
        assert result.available is False
        assert result.message


# ---------------------------------------------------------------------------
# 5.3 check_gh_auth
# ---------------------------------------------------------------------------


class TestCheckGhAuth:
    @patch("portfolio_manager.github_client.subprocess.run")
    def test_check_gh_auth_success(self, mock_run: MagicMock):
        mock_run.return_value = _mock_subprocess_return(stdout="github.com\n  ✓ Logged in as bot\n")
        result = check_gh_auth()
        assert isinstance(result, ToolCheckResult)
        assert result.available is True

    @patch("portfolio_manager.github_client.subprocess.run")
    def test_check_gh_auth_fails(self, mock_run: MagicMock):
        mock_run.return_value = _mock_subprocess_return(stdout="", returncode=1)
        result = check_gh_auth()
        assert isinstance(result, ToolCheckResult)
        assert result.available is False
        assert result.message


# ---------------------------------------------------------------------------
# 5.4 list_open_issues
# ---------------------------------------------------------------------------


class TestListOpenIssues:
    @patch("portfolio_manager.github_client.subprocess.run")
    def test_list_open_issues(self, mock_run: MagicMock):
        fixture_data = _load_fixture("gh_issues.open.json")
        mock_run.return_value = _mock_subprocess_return(stdout=json.dumps(fixture_data))
        result = list_open_issues("acme", "app", limit=50)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], IssueRecord)
        assert result[0].number == 101
        assert result[0].title == "Fix login redirect loop"
        assert "bug" in result[0].labels
        assert result[0].author == "alice"
        assert result[0].url is not None
        # Verify command structure
        args = mock_run.call_args[0][0]
        assert args[0] == "gh"
        assert args[1] == "issue"
        assert args[2] == "list"
        assert "--repo" in args
        assert "acme/app" in args

    @patch("portfolio_manager.github_client.subprocess.run")
    def test_list_open_issues_error_raises(self, mock_run: MagicMock):
        import pytest

        from portfolio_manager.github_client import GitHubSyncError

        mock_run.side_effect = Exception("boom")
        with pytest.raises(GitHubSyncError):
            list_open_issues("acme", "app")


# ---------------------------------------------------------------------------
# 5.5 list_open_prs
# ---------------------------------------------------------------------------


class TestListOpenPrs:
    @patch("portfolio_manager.github_client.subprocess.run")
    def test_list_open_prs(self, mock_run: MagicMock):
        fixture_data = _load_fixture("gh_prs.open.json")
        mock_run.return_value = _mock_subprocess_return(stdout=json.dumps(fixture_data))
        result = list_open_prs("acme", "app", limit=50)
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], PullRequestRecord)
        assert result[0].number == 201
        assert result[0].title == "Refactor auth module"
        assert result[0].head_branch == "feature/auth-refactor"
        assert result[0].base_branch == "main"
        # Verify command structure
        args = mock_run.call_args[0][0]
        assert args[0] == "gh"
        assert args[1] == "pr"
        assert args[2] == "list"

    @patch("portfolio_manager.github_client.subprocess.run")
    def test_list_open_prs_error_raises(self, mock_run: MagicMock):
        import pytest

        from portfolio_manager.github_client import GitHubSyncError

        mock_run.side_effect = Exception("boom")
        with pytest.raises(GitHubSyncError):
            list_open_prs("acme", "app")


# ---------------------------------------------------------------------------
# 5.6 map_pr_state
# ---------------------------------------------------------------------------


class TestMapPrState:
    def test_map_pr_state_failing_checks(self):
        fixture_data = _load_fixture("gh_prs.failing-checks.json")
        state = map_pr_state(fixture_data[0])
        assert state == "checks_failed"

    def test_map_pr_state_changes_requested(self):
        fixture_data = _load_fixture("gh_prs.changes-requested.json")
        state = map_pr_state(fixture_data[0])
        assert state == "changes_requested"

    def test_map_pr_state_approved_passing(self):
        fixture_data = _load_fixture("gh_prs.approved-passing.json")
        state = map_pr_state(fixture_data[0])
        assert state == "ready_for_human"

    def test_map_pr_state_no_review(self):
        pr_json = {"reviewDecision": None, "statusCheckRollup": []}
        state = map_pr_state(pr_json)
        assert state == "review_pending"

    def test_map_pr_state_empty_review_decision(self):
        pr_json = {"reviewDecision": "", "statusCheckRollup": []}
        state = map_pr_state(pr_json)
        assert state == "review_pending"

    def test_map_pr_state_review_required(self):
        pr_json = {"reviewDecision": "REVIEW_REQUIRED", "statusCheckRollup": []}
        state = map_pr_state(pr_json)
        assert state == "review_pending"

    def test_map_pr_state_fallback_open(self):
        # Unknown reviewDecision that isn't one of the handled values hits the fallback
        pr_json = {
            "reviewDecision": "DISMISSED",
        }
        state = map_pr_state(pr_json)
        assert state == "open"


# ---------------------------------------------------------------------------
# 5.7 sync_project_github
# ---------------------------------------------------------------------------


class TestSyncProjectGithub:
    @patch("portfolio_manager.github_client.list_open_prs")
    @patch("portfolio_manager.github_client.list_open_issues")
    def test_sync_project_github(self, mock_issues: MagicMock, mock_prs: MagicMock, tmp_path: Path):
        fixture_issues = _load_fixture("gh_issues.open.json")
        fixture_prs = _load_fixture("gh_prs.open.json")
        mock_issues.return_value = [
            IssueRecord(
                number=i["number"],
                title=i["title"],
                labels=[lab["name"] for lab in i["labels"]],
                author=i["author"]["login"],
                url=i["url"],
                created_at=i["createdAt"],
                updated_at=i["updatedAt"],
            )
            for i in fixture_issues
        ]
        mock_prs.return_value = [
            PullRequestRecord(
                number=p["number"],
                title=p["title"],
                head_branch=p["headRefName"],
                base_branch=p["baseRefName"],
                labels=[lab["name"] for lab in p["labels"]],
                review_stage="open",
                url=p["url"],
                created_at=p["createdAt"],
                updated_at=p["updatedAt"],
            )
            for p in fixture_prs
        ]

        project = _make_project()

        result = sync_project_github(project, max_items=50)

        assert isinstance(result, ProjectGitHubSyncResult)
        assert result.project_id == "test-proj"
        assert result.issues_count == 2
        assert result.prs_count == 2
        assert len(result.issues) == 2
        assert len(result.prs) == 2
        assert result.error is None

    @patch("portfolio_manager.github_client.list_open_prs")
    @patch("portfolio_manager.github_client.list_open_issues")
    def test_sync_project_github_inaccessible(self, mock_issues: MagicMock, mock_prs: MagicMock):
        from portfolio_manager.github_client import GitHubSyncError

        mock_issues.side_effect = GitHubSyncError("repo not found")
        mock_prs.return_value = []

        project = _make_project()

        result = sync_project_github(project)

        assert isinstance(result, ProjectGitHubSyncResult)
        assert result.project_id == "test-proj"
        assert result.error is not None
        assert len(result.warnings) > 0
