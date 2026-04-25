"""Security and safety hardening tests for the Portfolio Manager plugin.

Phase 8 ensures all MVP-1 code stays read-only and avoids:
- Shell injection vectors (no shell=True, no string-based subprocess calls)
- Destructive git commands
- GitHub mutations
- Leaking secrets in output
- MVP-2 write operations
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from unittest.mock import ANY, call

import pytest

# ---------------------------------------------------------------------------
# Source directory helpers
# ---------------------------------------------------------------------------

SRC_DIR = Path(__file__).parent.parent / "portfolio_manager"
SOURCE_FILES = sorted(SRC_DIR.rglob("*.py"))


# ---------------------------------------------------------------------------
# 8.1 No shell strings — all subprocess calls use argument arrays
# ---------------------------------------------------------------------------


class TestSubprocessUsesArgumentArrays:
    """Monkeypatch subprocess and verify all calls use argument arrays."""

    def test_github_client_uses_argument_arrays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every subprocess.run call in github_client.py uses a list, not a string."""
        calls: list[tuple] = []
        original_run = subprocess.run

        def tracking_run(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            # Return a minimal mock
            result = original_run(["true"], capture_output=True, text=True)
            return result

        monkeypatch.setattr(subprocess, "run", tracking_run)

        # Import and call each function that uses subprocess
        import portfolio_manager.github_client as mod

        # Force module reload to pick up monkeypatched subprocess
        importlib.reload(mod)

        mod.check_gh_available()
        mod.check_gh_auth()

        for call_args, call_kwargs in calls:
            cmd = call_args[0] if call_args else call_kwargs.get("args", [])
            assert isinstance(cmd, list), f"Expected list, got {type(cmd).__name__}: {cmd}"
            assert not call_kwargs.get("shell", False), f"shell=True found in call: {cmd}"

    def test_worktree_uses_argument_arrays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every subprocess.run call in worktree.py uses a list, not a string."""
        calls: list[tuple] = []
        original_run = subprocess.run

        def tracking_run(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            return original_run(["true"], capture_output=True, text=True)

        monkeypatch.setattr(subprocess, "run", tracking_run)

        import portfolio_manager.worktree as mod

        importlib.reload(mod)

        # Trigger _run_git indirectly via inspect_worktree on a non-existent path
        from portfolio_manager.worktree import inspect_worktree

        inspect_worktree(Path("/nonexistent-xyz-99999"), project_id="test")

        for call_args, call_kwargs in calls:
            cmd = call_args[0] if call_args else call_kwargs.get("args", [])
            assert isinstance(cmd, list), f"Expected list, got {type(cmd).__name__}: {cmd}"
            assert not call_kwargs.get("shell", False), f"shell=True found in call: {cmd}"


# ---------------------------------------------------------------------------
# 8.2 No unsafe git commands in source
# ---------------------------------------------------------------------------


class TestNoUnsafeGitCommands:
    """Scan source files for banned destructive git commands."""

    BANNED_GIT = [
        "git pull",
        "git rebase",
        "git merge",
        "git reset",
        "git clean",
        "git stash",
        "git checkout",
        "git switch",
        "git commit",
        "git push",
    ]

    @pytest.mark.parametrize("banned", BANNED_GIT)
    def test_banned_git_command_not_present(self, banned: str) -> None:
        """Verify banned git command '{banned}' appears nowhere in source."""
        for src_file in SOURCE_FILES:
            content = src_file.read_text()
            assert banned not in content, f"Banned command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"


# ---------------------------------------------------------------------------
# 8.3 No GitHub mutations
# ---------------------------------------------------------------------------


class TestNoGithubMutations:
    """Scan source files for banned destructive GitHub CLI commands."""

    BANNED_GH = [
        "gh issue create",
        "gh pr create",
        "gh pr merge",
        "gh api --method POST",
        "gh api --method PATCH",
        "gh api --method DELETE",
    ]

    @pytest.mark.parametrize("banned", BANNED_GH)
    def test_banned_gh_command_not_present(self, banned: str) -> None:
        """Verify banned gh command '{banned}' appears nowhere in source."""
        for src_file in SOURCE_FILES:
            content = src_file.read_text()
            assert banned not in content, f"Banned gh command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"


# ---------------------------------------------------------------------------
# 8.4 Redact secrets
# ---------------------------------------------------------------------------


class TestRedactSecrets:
    """Verify redact_secrets() exists and properly redacts token patterns."""

    def test_redact_secrets_exists(self) -> None:
        """redact_secrets function is importable from errors module."""
        from portfolio_manager.errors import redact_secrets

        assert callable(redact_secrets)

    @pytest.mark.parametrize(
        ("input_text", "expected"),
        [
            # GitHub tokens
            ("ghp_abc123def456", "ghp_***"),
            ("gho_xyz789token", "gho_***"),
            ("github_pat_11abc22def33", "github_pat_***"),
            # GitHub OAuth access tokens
            ("ghu_xxxxxtoken", "ghu_***"),
            ("ghs_xxxxxtoken", "ghs_***"),
            # Bearer tokens in HTTP
            ("Authorization: Bearer sk-abc123def456", "Authorization: Bearer ***"),
                # Note: after the first pass, only the secret marker remains
            # Generic token patterns
            ("token=abcdef1234567890abcdef", "token=***"),
            # Multiple tokens in one string
            ("ghp_abc and github_pat_def", "ghp_*** and github_pat_***"),
            # No tokens should pass through unchanged
            ("hello world no tokens here", "hello world no tokens here"),
            # Empty string
            ("", ""),
        ],
    )
    def test_redact_secrets_redacts_tokens(self, input_text: str, expected: str) -> None:
        """Various token patterns are redacted."""
        from portfolio_manager.errors import redact_secrets

        result = redact_secrets(input_text)
        assert result == expected, f"redact_secrets({input_text!r}) = {result!r}, expected {expected!r}"


# ---------------------------------------------------------------------------
# 8.5 MVP-1 read-only boundary
# ---------------------------------------------------------------------------


class TestMvp1ReadOnlyBoundary:
    """Verify no code paths exist for write operations (MVP-2 features)."""

    BANNED_FUNCTIONS = [
        "create_issue",
        "create_pr",
        "merge_pr",
        "create_branch",
        "modify_manifest",
    ]

    @pytest.mark.parametrize("func_name", BANNED_FUNCTIONS)
    def test_no_write_function_definitions(self, func_name: str) -> None:
        """Verify banned function '{func_name}' is not defined anywhere in source."""
        for src_file in SOURCE_FILES:
            content = src_file.read_text()
            # Check for function definitions
            assert f"def {func_name}" not in content, (
                f"Write function '{func_name}()' defined in {src_file.relative_to(SRC_DIR.parent)}"
            )
            # Check for handler registrations
            assert f"({func_name}," not in content, (
                f"Write function '{func_name}' registered in {src_file.relative_to(SRC_DIR.parent)}"
            )
