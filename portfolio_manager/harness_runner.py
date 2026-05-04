"""Harness subprocess wrapper for MVP 6 implementation execution.

Runs an allowlisted coding harness inside a clean issue worktree with
strict env passthrough, output redaction, and timeout + process-group kill.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from portfolio_manager.harness_config import HarnessCheckConfig, HarnessConfig

from portfolio_manager.errors import redact_secrets
from portfolio_manager.implementation_artifacts import write_input_request_json
from portfolio_manager.maintenance_artifacts import redact_secrets as redact_secrets_full
from portfolio_manager.worktree_git import get_clean_state
from portfolio_manager.worktree_paths import assert_under_worktrees_root

logger = logging.getLogger(__name__)

_MAX_CAPTURE = 64 * 1024  # 64KB per stream
_SHELL_META_RE = re.compile(r"[;&|$<>\`\\*?\[\]{}()!#\n\r]")


def _redact_output(text: str) -> str:
    text = redact_secrets(text)
    text = redact_secrets_full(text)
    return text


def _build_safe_env(env_passthrough: list[str], extra_env: dict[str, str] | None = None) -> dict[str, str]:
    """Build a minimal safe environment for the harness subprocess.

    Only forwards env vars listed in *env_passthrough* that exist in
    ``os.environ``. Always sets ``GIT_TERMINAL_PROMPT=0`` and forwards
    essential OS vars (PATH, HOME, USER, LANG, LC_ALL, TMPDIR) so child
    processes can find executables and function correctly.
    """
    env: dict[str, str] = {"GIT_TERMINAL_PROMPT": "0"}
    # Always forward essential OS vars so child processes can find executables
    for baseline in ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TMPDIR"):
        val = os.environ.get(baseline)
        if val is not None:
            env[baseline] = val
    for name in env_passthrough:
        val = os.environ.get(name)
        if val is not None:
            env[name] = val
    if extra_env:
        env.update(extra_env)
    return env


@dataclass(frozen=True)
class HarnessResult:
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool
    harness_status: str | None  # implemented | needs_user | failed from harness-result.json
    harness_message: str | None


def _validate_command(command: list[str]) -> None:
    """Reject shell metacharacters and unsafe paths in any command element."""
    if not isinstance(command, list):
        raise ValueError("command must be a list")
    if not command:
        raise ValueError("command must not be empty")
    for i, elem in enumerate(command):
        if not isinstance(elem, str) or not elem:
            raise ValueError(f"command[{i}] must be a non-empty string")
        if _SHELL_META_RE.search(elem):
            raise ValueError(f"command[{i}] contains shell metacharacters: {elem!r}")
        if i == 0:
            if "/" in elem and not elem.startswith("/"):
                raise ValueError(f"command[0] must be a basename or absolute path, got {elem!r}")
            if ".." in elem:
                raise ValueError(f"command[0] must not contain '..': {elem!r}")


def run_harness(
    *,
    harness: HarnessConfig,
    workspace: Path,
    root: Path,
    source_artifact_path: Path,
    instructions: dict[str, Any],
    artifact_dir: Path,
    input_request_path: Path,
    extra_env: dict[str, str] | None = None,
) -> HarnessResult:
    """Run a coding harness inside a clean issue worktree."""
    _validate_command(harness.command)
    if harness.workspace_subpath:
        workspace = workspace / harness.workspace_subpath
    workspace = assert_under_worktrees_root(workspace, root)

    clean_state = get_clean_state(workspace)
    if clean_state != "clean":
        raise RuntimeError(f"workspace is not clean at entry (state={clean_state})")

    # Build protocol env vars
    protocol_env: dict[str, str] = {
        "PORTFOLIO_IMPLEMENTATION_INPUT": str(input_request_path),
        "PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR": str(artifact_dir),
        "PORTFOLIO_IMPLEMENTATION_SOURCE": str(source_artifact_path),
        "PORTFOLIO_IMPLEMENTATION_JOB_ID": "",  # caller sets via extra_env if needed
    }
    if extra_env:
        protocol_env.update(extra_env)

    env = _build_safe_env(harness.env_passthrough, protocol_env)

    # Write input-request.json
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_input_request_json(input_request_path.parent, instructions)

    # Run subprocess
    start = time.monotonic()
    timed_out = False
    truncated = False
    returncode = -1
    raw_stdout = ""
    raw_stderr = ""

    try:
        proc = subprocess.Popen(
            harness.command,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=harness.timeout_seconds)
            returncode = proc.returncode
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace")
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
            returncode = proc.returncode if proc.returncode is not None else -1
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
    except Exception as exc:
        duration = time.monotonic() - start
        message = _redact_output(str(exc))
        return HarnessResult(
            returncode=-1,
            duration_seconds=duration,
            stdout="",
            stderr=message,
            truncated=False,
            timed_out=False,
            harness_status="failed",
            harness_message=message,
        )

    duration = time.monotonic() - start

    if len(raw_stdout) > _MAX_CAPTURE:
        raw_stdout = raw_stdout[:_MAX_CAPTURE]
        truncated = True
    if len(raw_stderr) > _MAX_CAPTURE:
        raw_stderr = raw_stderr[:_MAX_CAPTURE]
        truncated = True

    # Redact
    stdout = _redact_output(raw_stdout)
    stderr = _redact_output(raw_stderr)

    # Read harness-result.json if present
    harness_status: str | None = None
    harness_message: str | None = None
    result_path = artifact_dir / "harness-result.json"
    if result_path.is_file():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
            harness_status = data.get("status")
            harness_message = data.get("message")
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse %s", result_path)

    # Fallback: infer status from returncode if no harness-result.json
    if harness_status is None:
        if timed_out:
            harness_status = "failed"
        elif returncode == 0:
            harness_status = "implemented"
        else:
            harness_status = "failed"

    return HarnessResult(
        returncode=returncode,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
        truncated=truncated,
        timed_out=timed_out,
        harness_status=harness_status,
        harness_message=harness_message,
    )


def run_required_check(
    *,
    check: HarnessCheckConfig,
    workspace: Path,
    root: Path,
    artifact_dir: Path,
    extra_env: dict[str, str] | None = None,
) -> HarnessResult:
    """Run a required check command (lint, typecheck, etc.) inside the workspace.

    Similar to :func:`run_harness` but simpler — no protocol env vars,
    no input-request.json, no harness-result.json.
    """
    _validate_command(check.command)
    assert_under_worktrees_root(workspace, root)

    env = _build_safe_env([], extra_env)

    start = time.monotonic()
    timed_out = False
    truncated = False
    returncode = -1
    raw_stdout = ""
    raw_stderr = ""

    try:
        proc = subprocess.Popen(
            check.command,
            cwd=workspace,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout_bytes, stderr_bytes = proc.communicate(timeout=check.timeout_seconds)
            returncode = proc.returncode
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace")
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except OSError:
                proc.kill()
            stdout_bytes, stderr_bytes = proc.communicate()
            returncode = proc.returncode if proc.returncode is not None else -1
            raw_stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            raw_stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
    except Exception as exc:
        duration = time.monotonic() - start
        message = _redact_output(str(exc))
        return HarnessResult(
            returncode=-1,
            duration_seconds=duration,
            stdout="",
            stderr=message,
            truncated=False,
            timed_out=False,
            harness_status="failed",
            harness_message=message,
        )

    duration = time.monotonic() - start

    if len(raw_stdout) > _MAX_CAPTURE:
        raw_stdout = raw_stdout[:_MAX_CAPTURE]
        truncated = True
    if len(raw_stderr) > _MAX_CAPTURE:
        raw_stderr = raw_stderr[:_MAX_CAPTURE]
        truncated = True

    stdout = _redact_output(raw_stdout)
    stderr = _redact_output(raw_stderr)

    harness_status = "implemented" if returncode == 0 else "failed"
    if timed_out:
        harness_status = "failed"

    return HarnessResult(
        returncode=returncode,
        duration_seconds=duration,
        stdout=stdout,
        stderr=stderr,
        truncated=truncated,
        timed_out=timed_out,
        harness_status=harness_status,
        harness_message=None,
    )
