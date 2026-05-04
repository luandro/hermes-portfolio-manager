"""Tests for portfolio_manager.harness_runner — Phase 8.1."""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from portfolio_manager.harness_config import HarnessCheckConfig, HarnessConfig
from portfolio_manager.harness_runner import (
    HarnessResult,
    _build_safe_env,
    _validate_command,
    run_harness,
    run_required_check,
)

if TYPE_CHECKING:
    from pathlib import Path


def _make_harness(**overrides) -> HarnessConfig:
    defaults = dict(
        id="test-harness",
        command=["echo", "hello"],
        env_passthrough=[],
        timeout_seconds=5,
        max_files_changed=20,
        required_checks=[],
        checks={},
        workspace_subpath=None,
    )
    defaults.update(overrides)
    return HarnessConfig(**defaults)


def _make_check(**overrides) -> HarnessCheckConfig:
    defaults = dict(
        id="lint",
        command=["echo", "check"],
        timeout_seconds=5,
    )
    defaults.update(overrides)
    return HarnessCheckConfig(**defaults)


def _write_script(tmp_path: Path, name: str, code: str) -> str:
    """Write a Python script and return its absolute path as a string."""
    script = tmp_path / name
    script.write_text(code, encoding="utf-8")
    return str(script)


# ---------------------------------------------------------------------------
# _validate_command
# ---------------------------------------------------------------------------


def test_runner_uses_argument_array() -> None:
    _validate_command(["echo", "hello"])  # should not raise


def test_runner_rejects_string_command() -> None:
    with pytest.raises(ValueError, match="must be a list"):
        _validate_command("echo hello")  # type: ignore[arg-type]  # intentional bad type for validation


def test_runner_rejects_command_path_with_shell_metachar() -> None:
    with pytest.raises(ValueError, match="shell metacharacters"):
        _validate_command(["echo", "hello; rm -rf /"])


# ---------------------------------------------------------------------------
# _build_safe_env
# ---------------------------------------------------------------------------


def test_runner_sets_GIT_TERMINAL_PROMPT_zero() -> None:
    env = _build_safe_env([])
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_runner_only_passes_env_in_env_passthrough_list() -> None:
    with patch.dict(os.environ, {"MY_SECRET": "shhh", "MY_ALLOWED": "yes"}, clear=False):
        env = _build_safe_env(["MY_ALLOWED"])
    assert "MY_ALLOWED" in env
    assert "MY_SECRET" not in env


def test_runner_strips_HOME_PATH_to_minimal_safe_set() -> None:
    env = _build_safe_env([])
    # Essential OS vars (PATH, HOME, etc.) are always forwarded for child processes
    assert "PATH" in env
    assert "HOME" in env
    # Arbitrary env vars should NOT be present unless explicitly in passthrough
    assert "RANDOM_UNSET_VAR" not in env


# ---------------------------------------------------------------------------
# run_harness integration-style tests using script files
# ---------------------------------------------------------------------------


def _make_workspace_under_root(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "root"
    root.mkdir()
    wt_root = root / "worktrees"
    wt_root.mkdir()
    workspace = wt_root / "proj-issue-1"
    workspace.mkdir()
    return root, workspace


def _init_git_repo(workspace: Path) -> None:
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@e",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@e",
    }
    subprocess.run(["git", "init"], cwd=workspace, env=env, check=True, capture_output=True)
    (workspace / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=workspace, env=env, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=workspace, env=env, check=True, capture_output=True)


def test_runner_sets_cwd_to_workspace_path(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    script = _write_script(tmp_path, "cwd_check.py", "import os\nprint(os.getcwd())\n")
    harness = _make_harness(command=[sys.executable, script])
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={"task": "test"},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.stdout.strip() == str(workspace)


def test_runner_workspace_path_must_be_under_worktrees_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    harness = _make_harness(command=["echo", "hello"])

    with pytest.raises(ValueError, match="escapes worktrees root"):
        run_harness(
            harness=harness,
            workspace=outside,
            root=root,
            source_artifact_path=tmp_path / "source.md",
            instructions={},
            artifact_dir=tmp_path / "artifacts",
            input_request_path=tmp_path / "input.json",
        )


def test_runner_enforces_timeout_seconds_from_harness_config(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    script = _write_script(tmp_path, "slow.py", "import time\ntime.sleep(10)\n")
    harness = _make_harness(
        command=[sys.executable, script],
        timeout_seconds=1,
    )
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.timed_out is True
    assert result.duration_seconds < 5  # should have been killed within ~1s


def test_runner_kills_process_group_on_timeout(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    script = _write_script(tmp_path, "slow2.py", "import time\ntime.sleep(60)\n")
    harness = _make_harness(
        command=[sys.executable, script],
        timeout_seconds=1,
    )
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.timed_out is True
    assert result.harness_status == "failed"


def test_runner_captures_stdout_stderr_truncated_to_64KB_each(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    # Generate >64KB output
    big_output = "x" * (65 * 1024)
    script = _write_script(tmp_path, "big.py", f"print({big_output!r})\n")
    harness = _make_harness(
        command=[sys.executable, script],
        timeout_seconds=10,
    )
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.truncated is True
    assert len(result.stdout) <= 64 * 1024


def test_runner_redacts_token_patterns_in_captured_output(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    script = _write_script(tmp_path, "token.py", "print('token ghp_AAAA1111BBBB')\n")
    harness = _make_harness(
        command=[sys.executable, script],
        timeout_seconds=5,
    )
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert "ghp_AAAA1111BBBB" not in result.stdout
    assert "ghp_***" in result.stdout


def test_runner_passes_portfolio_input_artifact_source_env_vars(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    script = _write_script(
        tmp_path,
        "env_check.py",
        "import os\nprint(os.environ.get('PORTFOLIO_IMPLEMENTATION_INPUT', 'MISSING'))\n",
    )
    harness = _make_harness(
        command=[sys.executable, script],
        timeout_seconds=5,
    )
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert str(input_path) in result.stdout


def test_runner_reads_harness_result_json_when_present(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    script = _write_script(
        tmp_path,
        "write_result.py",
        textwrap.dedent("""\
        import json, os
        result = {"status": "implemented", "message": "all done"}
        artifact_dir = os.environ["PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR"]
        with open(os.path.join(artifact_dir, "harness-result.json"), "w") as f:
            json.dump(result, f)
    """),
    )
    harness = _make_harness(command=[sys.executable, script], timeout_seconds=5)

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.harness_status == "implemented"
    assert result.harness_message == "all done"


def test_runner_maps_harness_result_status_needs_user(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    script = _write_script(
        tmp_path,
        "needs_user.py",
        textwrap.dedent("""\
        import json, os
        result = {"status": "needs_user", "message": "need input"}
        artifact_dir = os.environ["PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR"]
        with open(os.path.join(artifact_dir, "harness-result.json"), "w") as f:
            json.dump(result, f)
    """),
    )
    harness = _make_harness(command=[sys.executable, script], timeout_seconds=5)

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert result.harness_status == "needs_user"


def test_runner_returns_typed_result_with_returncode_duration_truncated_flag(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    harness = _make_harness(command=["echo", "ok"], timeout_seconds=5)
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    result = run_harness(
        harness=harness,
        workspace=workspace,
        root=root,
        source_artifact_path=tmp_path / "source.md",
        instructions={},
        artifact_dir=artifact_dir,
        input_request_path=input_path,
    )
    assert isinstance(result, HarnessResult)
    assert isinstance(result.returncode, int)
    assert isinstance(result.duration_seconds, float)
    assert isinstance(result.truncated, bool)
    assert result.returncode == 0
    assert result.duration_seconds >= 0


def test_runner_rejects_command_when_workspace_dirty_at_entry(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    _init_git_repo(workspace)
    # Make it dirty
    (workspace / "new_file.txt").write_text("dirty", encoding="utf-8")

    harness = _make_harness(command=["echo", "hello"], timeout_seconds=5)
    artifact_dir = tmp_path / "artifacts"
    input_path = artifact_dir / "input-request.json"

    with pytest.raises(RuntimeError, match="not clean at entry"):
        run_harness(
            harness=harness,
            workspace=workspace,
            root=root,
            source_artifact_path=tmp_path / "source.md",
            instructions={},
            artifact_dir=artifact_dir,
            input_request_path=input_path,
        )


# ---------------------------------------------------------------------------
# run_required_check
# ---------------------------------------------------------------------------


def test_run_required_check_uses_check_command_and_timeout(tmp_path: Path) -> None:
    root, workspace = _make_workspace_under_root(tmp_path)
    script = _write_script(tmp_path, "check.py", "print('check output')\n")
    check = _make_check(
        command=[sys.executable, script],
        timeout_seconds=5,
    )
    artifact_dir = tmp_path / "artifacts"

    result = run_required_check(
        check=check,
        workspace=workspace,
        root=root,
        artifact_dir=artifact_dir,
    )
    assert result.returncode == 0
    assert "check output" in result.stdout
    assert result.harness_status == "implemented"
