"""Pytest configuration: re-export shared fixtures from tests/fixtures/."""

from __future__ import annotations

from tests.fixtures.worktree_fixtures import (  # noqa: F401
    agent_root,
    bare_remote,
    cloned_repo,
    projects_yaml_pointing_to_bare_remote,
)
