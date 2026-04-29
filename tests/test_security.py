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
import re
import subprocess
from pathlib import Path
from typing import ClassVar

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

    BANNED_GIT: ClassVar[list[str]] = [
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

    BANNED_GH: ClassVar[list[str]] = [
        "gh issue create",
        "gh pr create",
        "gh pr merge",
        "gh api --method POST",
        "gh api --method PATCH",
        "gh api --method DELETE",
    ]

    # Files where gh issue create is intentionally allowed (MVP 3)
    _GH_ISSUE_CREATE_EXEMPT: ClassVar[set[str]] = {"issue_github.py"}

    @pytest.mark.parametrize("banned", BANNED_GH)
    def test_banned_gh_command_not_present(self, banned: str) -> None:
        """Verify banned gh command '{banned}' appears nowhere in source."""
        for src_file in SOURCE_FILES:
            # Skip exempt files for gh issue create (intentionally allowed)
            if banned == "gh issue create" and src_file.name in self._GH_ISSUE_CREATE_EXEMPT:
                continue
            content = src_file.read_text()
            assert banned not in content, (
                f"Banned gh command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"
            )


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

    BANNED_FUNCTIONS: ClassVar[list[str]] = [
        "create_pr",
        "merge_pr",
        "create_branch",
        "modify_manifest",
    ]

    @pytest.mark.parametrize("func_name", BANNED_FUNCTIONS)
    def test_no_write_function_definitions(self, func_name: str) -> None:
        """Verify banned function '{func_name}' is not defined anywhere in source."""
        # Use word-boundary regex to match exact function names,
        # e.g. "def create_pr(" but not "def create_projects_config_backup("
        def_pattern = re.compile(rf"\bdef {func_name}\b")
        reg_pattern = re.compile(rf"\({func_name}\b")
        for src_file in SOURCE_FILES:
            content = src_file.read_text()
            # Check for function definitions
            assert not def_pattern.search(content), (
                f"Write function '{func_name}()' defined in {src_file.relative_to(SRC_DIR.parent)}"
            )
            # Check for handler registrations
            assert not reg_pattern.search(content), (
                f"Write function '{func_name}' registered in {src_file.relative_to(SRC_DIR.parent)}"
            )


# ---------------------------------------------------------------------------
# Phase 10 — MVP 2 security hardening
# ---------------------------------------------------------------------------

# Admin / MVP 2 source files to scan
ADMIN_FILES = sorted(
    p
    for p in SRC_DIR.rglob("*.py")
    if p.name
    in {
        "admin_functions.py",
        "admin_writes.py",
        "admin_locks.py",
        "admin_models.py",
        "repo_parser.py",
        "repo_validation.py",
    }
)


class TestMvp2NoGithubMutations:
    """MVP 2 admin modules must not contain GitHub mutation commands."""

    BANNED_GH: ClassVar[list[str]] = TestNoGithubMutations.BANNED_GH

    @pytest.mark.parametrize("banned", BANNED_GH)
    def test_no_github_mutations_in_admin_code(self, banned: str) -> None:
        """Verify banned gh command '{banned}' not in admin modules."""
        for src_file in ADMIN_FILES:
            content = src_file.read_text()
            assert banned not in content, (
                f"Banned gh command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"
            )


class TestMvp2NoUnsafeGitCommands:
    """MVP 2 admin modules must not contain unsafe git commands."""

    BANNED_GIT: ClassVar[list[str]] = TestNoUnsafeGitCommands.BANNED_GIT

    @pytest.mark.parametrize("banned", BANNED_GIT)
    def test_no_unsafe_git_in_admin_code(self, banned: str) -> None:
        """Verify banned git command '{banned}' not in admin modules."""
        for src_file in ADMIN_FILES:
            content = src_file.read_text()
            assert banned not in content, (
                f"Banned git command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"
            )


class TestMvp2SubprocessArgumentArrays:
    """repo_validation.py must use argument arrays, not shell strings."""

    def test_repo_validation_uses_argument_arrays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """validate_github_repo passes a list to subprocess.run, never a string."""
        calls: list[tuple] = []
        original_run = subprocess.run

        def tracking_run(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            return original_run(["true"], capture_output=True, text=True)

        monkeypatch.setattr(subprocess, "run", tracking_run)

        import portfolio_manager.repo_validation as mod

        importlib.reload(mod)

        # Call the function — will get a minimal result (gh not available in CI)
        mod.validate_github_repo("owner", "repo")

        assert len(calls) >= 1, "Expected at least one subprocess.run call"
        for call_args, call_kwargs in calls:
            cmd = call_args[0] if call_args else call_kwargs.get("args", [])
            assert isinstance(cmd, list), f"Expected list, got {type(cmd).__name__}: {cmd}"
            assert not call_kwargs.get("shell", False), f"shell=True found in call: {cmd}"


class TestMvp2RedactSecretsInToolOutput:
    """_result() in tools.py must redact secrets from output."""

    def test_redact_secrets_in_tool_output(self) -> None:
        """Tokens in _result() message are redacted."""
        from portfolio_manager.tools import _result

        output = _result(
            status="success",
            tool="test_tool",
            message="Token is ghp_abc123def456ghi789 in output",
        )
        assert "ghp_abc123def456ghi789" not in output, "GitHub token leaked in tool output"
        assert "ghp_***" in output, "Token not properly redacted"


class TestMvp2AdminDoesNotModifyRepositories:
    """Admin tool handlers must not create/modify files inside repository paths."""

    def test_admin_does_not_modify_repositories(self, tmp_path: Path) -> None:
        """Running admin handlers only touches config/state/backups, not repo dirs."""
        tmp = tmp_path

        # Create a fake repo-like directory (simulates a checked-out repo)
        repo_dir = tmp / "worktrees" / "my-project"
        repo_dir.mkdir(parents=True)
        repo_file = repo_dir / "README.md"
        repo_file.write_text("original content", encoding="utf-8")

        # Snapshot all files under the repo dir
        repo_files_before: dict[str, str] = {}
        for f in repo_dir.rglob("*"):
            if f.is_file():
                repo_files_before[str(f.relative_to(repo_dir))] = f.read_text(encoding="utf-8")

        # Create minimal config so handlers can load it
        config_dir = tmp / "config"
        config_dir.mkdir(parents=True)
        config_yaml = config_dir / "projects.yaml"
        config_yaml.write_text(
            "version: 1\nprojects:\n"
            "- id: my-project\n  name: My Project\n  repo: git@github.com:test/my-project.git\n"
            "  github: {owner: test, repo: my-project}\n"
            "  priority: medium\n  status: active\n  default_branch: auto\n",
            encoding="utf-8",
        )

        # Import handlers
        from portfolio_manager.tools import (
            _handle_portfolio_project_explain,
            _handle_portfolio_project_list,
            _handle_portfolio_project_update,
        )

        # Run read-only handlers
        _handle_portfolio_project_list({"root": str(tmp)})
        _handle_portfolio_project_explain({"root": str(tmp), "project_id": "my-project"})

        # Run a mutation handler (will write config, but not repo files)
        _handle_portfolio_project_update({"root": str(tmp), "project_id": "my-project", "priority": "high"})

        # Verify repo files unchanged
        repo_files_after: dict[str, str] = {}
        for f in repo_dir.rglob("*"):
            if f.is_file():
                repo_files_after[str(f.relative_to(repo_dir))] = f.read_text(encoding="utf-8")

        assert repo_files_before == repo_files_after, (
            f"Admin handler modified repo files: {set(repo_files_after) - set(repo_files_before)}"
        )


# ---------------------------------------------------------------------------
# Phase 12 — MVP 3 security hardening
# ---------------------------------------------------------------------------

# MVP 3 source files for security scanning
MVP3_FILES = sorted(
    p
    for p in SRC_DIR.rglob("*.py")
    if p.name
    in {
        "issue_resolver.py",
        "issue_drafts.py",
        "issue_artifacts.py",
        "issue_github.py",
    }
)

# Allowed gh mutation commands in MVP 3 (issue creation only)
ALLOWED_GH_MUTATIONS: list[str] = [
    "gh issue create",
]


class TestMvp3NoGitCommands:
    """MVP 3 modules must not contain git commands."""

    BANNED_GIT: ClassVar[list[str]] = TestNoUnsafeGitCommands.BANNED_GIT

    @pytest.mark.parametrize("banned", BANNED_GIT)
    def test_no_git_commands_in_mvp3_code(self, banned: str) -> None:
        """Verify banned git command '{banned}' not in MVP 3 modules."""
        for src_file in MVP3_FILES:
            content = src_file.read_text()
            assert banned not in content, (
                f"Banned git command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"
            )


class TestMvp3OnlyAllowsGhIssueCreateMutation:
    """MVP 3 modules must only use gh issue create for mutation."""

    # All other GH mutation commands are banned
    BANNED_GH: ClassVar[list[str]] = [cmd for cmd in TestNoGithubMutations.BANNED_GH if cmd not in ALLOWED_GH_MUTATIONS]

    @pytest.mark.parametrize("banned", BANNED_GH)
    def test_no_banned_gh_mutations_in_mvp3_code(self, banned: str) -> None:
        """Verify banned gh command '{banned}' not in MVP 3 modules."""
        for src_file in MVP3_FILES:
            content = src_file.read_text()
            assert banned not in content, (
                f"Banned gh command '{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"
            )


class TestMvp3SubprocessArgumentArrays:
    """MVP 3 modules must use argument arrays, not shell strings."""

    def test_issue_github_uses_argument_arrays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every subprocess.run call in issue_github.py uses a list, not a string."""
        calls: list[tuple] = []
        original_run = subprocess.run

        def tracking_run(*args: object, **kwargs: object) -> object:
            calls.append((args, kwargs))
            return original_run(["true"], capture_output=True, text=True)

        monkeypatch.setattr(subprocess, "run", tracking_run)

        import portfolio_manager.issue_github as mod

        importlib.reload(mod)

        mod.check_gh_available()
        mod.check_gh_auth()

        assert len(calls) >= 1, "Expected at least one subprocess.run call"
        for call_args, call_kwargs in calls:
            cmd = call_args[0] if call_args else call_kwargs.get("args", [])
            assert isinstance(cmd, list), f"Expected list, got {type(cmd).__name__}: {cmd}"
            assert not call_kwargs.get("shell", False), f"shell=True found in call: {cmd}"


# ---------------------------------------------------------------------------
# Phase 9 — MVP 4 maintenance security hardening
# ---------------------------------------------------------------------------

# Maintenance source files for security scanning
BUILTIN_SKILLS_DIR = SRC_DIR / "skills" / "builtin"
MAINTENANCE_FILES = sorted(
    set(p for p in SRC_DIR.rglob("*.py") if p.name.startswith("maintenance")) | set(BUILTIN_SKILLS_DIR.rglob("*.py"))
)


class TestMaintenanceCommandAllowlist:
    """Maintenance modules must only use safe, read-only commands."""

    def test_no_shell_true_in_maintenance_code(self) -> None:
        """No maintenance module uses shell=True in subprocess calls."""
        for src_file in MAINTENANCE_FILES:
            content = src_file.read_text()
            assert "shell=True" not in content, f"shell=True found in {src_file.relative_to(SRC_DIR.parent)}"

    def test_only_allowed_gh_commands_in_maintenance_code(self) -> None:
        """Only read-only gh commands are allowed in maintenance modules."""
        import ast

        allowed_prefixes = [
            ["gh", "--version"],
            ["gh", "auth", "status"],
            ["gh", "issue", "list"],
            ["gh", "pr", "list"],
            ["gh", "api", "--method", "GET"],
        ]

        def _check_gh_cmd(parts: list[str], src_file: Path) -> None:
            is_allowed = any(parts[: len(prefix)] == prefix for prefix in allowed_prefixes)
            assert is_allowed, f"Disallowed gh command '{' '.join(parts)}' in {src_file.relative_to(SRC_DIR.parent)}"

        for src_file in MAINTENANCE_FILES:
            content = src_file.read_text()
            # Check string-form gh calls: "gh <subcommand> ..."
            # Exclude strings that look like error messages (contain "failed", "error", etc.)
            _ERROR_MSG_RE = re.compile(r"\b(failed|error|invalid|unable|warning)\b", re.IGNORECASE)
            for match in re.finditer(
                r'"gh\s+(issue|pr|api|auth|repo|run|secret|gist|release|workflow)\b[^"]*"', content
            ):
                gh_cmd = match.group().strip('"')
                if _ERROR_MSG_RE.search(gh_cmd):
                    continue
                parts = gh_cmd.split()
                _check_gh_cmd(parts, src_file)
            # Check list-form gh calls via AST: ["gh", ...]
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.List):
                    elts = node.elts
                    if (
                        elts
                        and isinstance(elts[0], ast.Constant)
                        and isinstance(elts[0].value, str)
                        and elts[0].value == "gh"
                    ):
                        parts: list[str] = []
                        all_const = True
                        for elt in elts:
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                parts.append(elt.value)
                            else:
                                all_const = False
                                break
                        if all_const and parts:
                            _check_gh_cmd(parts, src_file)

    def test_no_gh_issue_create_in_maintenance_code(self) -> None:
        """No gh issue create in maintenance modules."""
        for src_file in MAINTENANCE_FILES:
            content = src_file.read_text()
            assert "gh issue create" not in content, (
                f"'gh issue create' found in {src_file.relative_to(SRC_DIR.parent)}"
            )

    def test_no_gh_pr_mutation_in_maintenance_code(self) -> None:
        """No gh pr create/merge/close in maintenance modules."""
        banned_pr = ["gh pr create", "gh pr merge", "gh pr close", "gh pr ready"]
        for src_file in MAINTENANCE_FILES:
            content = src_file.read_text()
            for banned in banned_pr:
                assert banned not in content, f"'{banned}' found in {src_file.relative_to(SRC_DIR.parent)}"

    def test_no_gh_api_mutation_methods_in_maintenance_code(self) -> None:
        """No POST/PUT/DELETE/PATCH in gh api calls in maintenance modules."""
        mutation_methods = ["POST", "PUT", "DELETE", "PATCH"]
        for src_file in MAINTENANCE_FILES:
            content = src_file.read_text()
            for method in mutation_methods:
                patterns = [
                    f"--method {method}",
                    f'--method "{method}"',
                    f"--method '{method}'",
                ]
                for pat in patterns:
                    assert pat not in content, (
                        f"gh api mutation method '{method}' found in {src_file.relative_to(SRC_DIR.parent)}"
                    )


class TestMaintenancePathContainment:
    """Maintenance paths must stay under the project root."""

    def test_maintenance_config_path_contained(self) -> None:
        """Config paths from maintenance_config stay under root."""
        from portfolio_manager.maintenance_config import config_path

        root = Path("/tmp/test-root")
        cp = config_path(root)
        resolved_root = root.resolve()
        assert cp.resolve().is_relative_to(resolved_root), f"Config path {cp} escapes root {resolved_root}"

    def test_maintenance_artifact_path_contained(self) -> None:
        """Artifact paths from maintenance_artifacts stay under root."""
        from portfolio_manager.maintenance_artifacts import get_artifact_dir

        root = Path("/tmp/test-root")
        artifact_dir = get_artifact_dir(root, "run-abc-123")
        resolved_root = root.resolve()
        assert artifact_dir.is_relative_to(resolved_root), f"Artifact path {artifact_dir} escapes root {resolved_root}"

    def test_guidance_doc_rejects_dotdot(self) -> None:
        """Guidance doc paths with '..' are rejected."""
        from portfolio_manager.maintenance_artifacts import get_artifact_dir

        root = Path("/tmp/test-root")
        with pytest.raises(ValueError, match="Invalid run_id"):
            get_artifact_dir(root, "../escape")

    def test_guidance_doc_rejects_absolute_path(self) -> None:
        """Absolute paths in run_id are rejected."""
        from portfolio_manager.maintenance_artifacts import get_artifact_dir

        root = Path("/tmp/test-root")
        with pytest.raises(ValueError, match="Invalid run_id"):
            get_artifact_dir(root, "/etc/passwd")

    def test_guidance_doc_rejects_url_scheme(self) -> None:
        """URL schemes in run_id are rejected."""
        from portfolio_manager.maintenance_artifacts import get_artifact_dir

        root = Path("/tmp/test-root")
        with pytest.raises(ValueError, match="Invalid run_id"):
            get_artifact_dir(root, "file:///etc/passwd")

    def test_guidance_doc_rejects_shell_metacharacters(self) -> None:
        """Shell metacharacters in run_id are rejected."""
        from portfolio_manager.maintenance_artifacts import get_artifact_dir

        root = Path("/tmp/test-root")
        for bad_id in ["run;rm -rf /", "run$(whoami)", "run`id`", "run|cat"]:
            with pytest.raises(ValueError, match="Invalid run_id"):
                get_artifact_dir(root, bad_id)


class TestMaintenancePrivacyRedaction:
    """Maintenance artifacts, reports, and drafts must not leak secrets."""

    def test_error_artifact_redacts_tokens(self) -> None:
        """Error artifacts have tokens redacted."""
        from portfolio_manager.maintenance_artifacts import redact_secrets

        text_with_token = "Error: ghp_ABC123DEF456 failed for repo"
        redacted = redact_secrets(text_with_token)
        assert "ghp_ABC123DEF456" not in redacted
        assert "ghp_***" in redacted

    def test_report_does_not_include_environment_variables(self, tmp_path: Path) -> None:
        """Reports do not include raw environment variable values."""
        from portfolio_manager.maintenance_reports import write_maintenance_report

        root = tmp_path / "test-report-env-check"
        run_id = "env-check-run"
        findings = [
            {
                "title": "Test finding",
                "severity": "info",
                "source_type": "test",
                "body": "Test body",
            }
        ]
        metadata = {
            "run_id": run_id,
            "projects": ["proj-1"],
        }

        report_path = write_maintenance_report(root, run_id, findings, metadata)
        content = report_path.read_text()

        # Report should not contain common env var patterns
        env_patterns = ["os.environ", "os.getenv", "HOME=", "PATH=", "USER="]
        for pat in env_patterns:
            assert pat not in content, f"Environment variable pattern '{pat}' found in report"

    def test_maintenance_draft_excludes_private_metadata(self) -> None:
        """Draft body excludes private metadata and chain-of-thought."""
        from portfolio_manager.maintenance_drafts import (
            _PRIVATE_META_KEYS,
            DraftPlan,
            _build_draft_body,
        )
        from portfolio_manager.maintenance_models import MaintenanceFinding

        finding = MaintenanceFinding(
            fingerprint="fp-test",
            severity="medium",
            title="Stale issue",
            body="Issue has been open 45 days.\ninternal_notes: secret\nchain_of_thought: thinking...",
            source_type="github_issue",
            source_id="123",
            source_url="https://github.com/test/repo/issues/123",
            metadata={},
        )

        plan = DraftPlan(
            project_id="test-project",
            skill_id="stale_issue_digest",
            run_id="run-test",
            findings=[finding],
            should_create=True,
        )

        body = _build_draft_body(plan)

        # Private keys should not appear in the body
        for key in _PRIVATE_META_KEYS:
            assert key not in body, f"Private key '{key}' found in draft body"
