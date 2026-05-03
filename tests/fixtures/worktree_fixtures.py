"""Local-only fixtures for MVP 5 worktree tests.

Creates a bare git remote at ``$tmp/origin.git`` with one commit on ``main``
and writes a matching ``projects.yaml`` using a ``file://`` URL. No network.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True)


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """Create a bare repo at ``tmp_path/origin.git`` with one commit on ``main``."""
    seed = tmp_path / "_seed"
    seed.mkdir()
    _git("init", "-b", "main", str(seed), cwd=tmp_path)
    (seed / "README.md").write_text("hello\n", encoding="utf-8")
    _git("add", "README.md", cwd=seed)
    _git("commit", "-m", "initial", cwd=seed)
    bare = tmp_path / "origin.git"
    _git("clone", "--bare", str(seed), str(bare), cwd=tmp_path)
    return bare


@pytest.fixture
def agent_root(tmp_path: Path) -> Path:
    """Create ``$ROOT`` with the standard subdirs used by the plugin."""
    root = tmp_path / "agent-system"
    (root / "config").mkdir(parents=True)
    (root / "worktrees").mkdir()
    (root / "state").mkdir()
    (root / "artifacts").mkdir()
    return root


@pytest.fixture
def projects_yaml_pointing_to_bare_remote(bare_remote: Path, agent_root: Path) -> Path:
    """Write a projects.yaml pointing at the bare fixture remote."""
    cfg = agent_root / "config" / "projects.yaml"
    cfg.write_text(
        textwrap.dedent(f"""\
            version: 1
            projects:
              - id: testproj
                name: Test Project
                repo: {bare_remote.as_uri()}
                priority: high
                status: active
                default_branch: main
                github:
                  owner: testowner
                  repo: testrepo
            """),
        encoding="utf-8",
    )
    return cfg


@pytest.fixture
def cloned_repo(bare_remote: Path, agent_root: Path) -> Path:
    """Clone the bare remote into ``$ROOT/worktrees/testproj`` for probe tests."""
    target = agent_root / "worktrees" / "testproj"
    _git("clone", str(bare_remote), str(target), cwd=agent_root)
    return target
