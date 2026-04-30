"""Tests for portfolio_manager.worktree_paths — validators (Phase 1)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from portfolio_manager.worktree_paths import (
    assert_under_worktrees_root,
    default_branch_name,
    has_escaping_symlink,
    normalize_remote_url,
    redact_remote_url,
    remotes_equal,
    render_issue_worktree_path,
    resolve_under_root,
    validate_branch_name,
)

# ---------------------------------------------------------------------------
# 1.1 Branch validator
# ---------------------------------------------------------------------------


def test_default_branch_name_format() -> None:
    assert default_branch_name("my-project", 42) == "agent/my-project/issue-42"


def test_explicit_valid_branch_accepted() -> None:
    assert validate_branch_name("agent/foo_bar-1/issue-7") == "agent/foo_bar-1/issue-7"


@pytest.mark.parametrize(
    "bad",
    [
        "-agent/foo/issue-1",  # leading dash on the whole name
        "agent/foo..bar/issue-1",  # double dot
        "agent/foo@{bar}/issue-1",  # @{ sequence
        "agent/foo/issue-1/",  # trailing slash
        "agent/foo/issue-1.",  # trailing dot
        "agent\\foo\\issue-1",  # backslash
        "agent/foo bar/issue-1",  # space
        "agent/foo:bar/issue-1",  # colon
        "agent/foo$bar/issue-1",  # $
        "agent/foo`bar/issue-1",  # backtick
        "agent/foo;bar/issue-1",  # ;
        "agent/foo|bar/issue-1",  # |
        "agent/foo&bar/issue-1",  # &
        "agent/foo>bar/issue-1",  # >
        "agent/foo<bar/issue-1",  # <
        "agent/foo\nbar/issue-1",  # newline
        "/agent/foo/issue-1",  # absolute
        "../agent/foo/issue-1",  # traversal
        "refs/heads/agent/foo/issue-1",  # refs/heads prefix
        "agent/" + ("a" * 65) + "/issue-1",  # >64 segment
        "agent/foo/issue-0",  # zero issue
        "agent/foo/issue--1",  # negative
        "Agent/foo/issue-1",  # uppercase
        "agent/Foo/issue-1",  # uppercase in segment
    ],
)
def test_branch_validator_rejects_bad(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_branch_name(bad)


# ---------------------------------------------------------------------------
# 1.2 Path containment + symlink escape guard
# ---------------------------------------------------------------------------


def test_path_inside_root_accepted(tmp_path: Path) -> None:
    inner = tmp_path / "worktrees" / "p"
    inner.mkdir(parents=True)
    assert resolve_under_root(inner, tmp_path) == inner.resolve()


def test_path_outside_root_rejected(tmp_path: Path) -> None:
    other = tmp_path.parent / "elsewhere"
    with pytest.raises(ValueError):
        resolve_under_root(other, tmp_path)


def test_relative_path_resolves_under_root(tmp_path: Path) -> None:
    (tmp_path / "worktrees").mkdir()
    rel = Path("worktrees/p")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        out = resolve_under_root(rel, tmp_path)
    finally:
        os.chdir(cwd)
    assert out == (tmp_path / "worktrees" / "p").resolve()


def test_dotdot_traversal_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        resolve_under_root(tmp_path / ".." / "etc", tmp_path)


def test_assert_under_worktrees_root_accepts(tmp_path: Path) -> None:
    (tmp_path / "worktrees" / "p").mkdir(parents=True)
    p = tmp_path / "worktrees" / "p"
    assert assert_under_worktrees_root(p, tmp_path) == p.resolve()


def test_assert_under_worktrees_root_rejects_outside_worktrees(tmp_path: Path) -> None:
    (tmp_path / "elsewhere").mkdir()
    with pytest.raises(ValueError):
        assert_under_worktrees_root(tmp_path / "elsewhere", tmp_path)


def test_symlink_inside_root_to_inside_root_accepted(tmp_path: Path) -> None:
    target = tmp_path / "worktrees" / "real"
    target.mkdir(parents=True)
    link = tmp_path / "worktrees" / "link"
    os.symlink(target, link)
    assert not has_escaping_symlink(link, tmp_path)


def test_symlink_inside_root_escaping_root_rejected(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    (tmp_path / "worktrees").mkdir()
    link = tmp_path / "worktrees" / "escape"
    os.symlink(outside, link)
    assert has_escaping_symlink(link, tmp_path)


def test_pattern_substitution_rejects_non_integer_issue(tmp_path: Path) -> None:
    pattern = str(tmp_path / "worktrees" / "p-issue-{issue_number}")
    with pytest.raises((TypeError, ValueError)):
        render_issue_worktree_path(pattern, "p", "abc", tmp_path)  # type: ignore[arg-type]


def test_pattern_substitution_rejects_curly_injection(tmp_path: Path) -> None:
    pattern = str(tmp_path / "worktrees" / "{project_id}-issue-{issue_number}")
    with pytest.raises(ValueError):
        render_issue_worktree_path(pattern, "../escape", 1, tmp_path)


def test_render_issue_worktree_path_happy(tmp_path: Path) -> None:
    pattern = str(tmp_path / "worktrees" / "p-issue-{issue_number}")
    out = render_issue_worktree_path(pattern, "p", 7, tmp_path)
    assert out == (tmp_path / "worktrees" / "p-issue-7").resolve()


# ---------------------------------------------------------------------------
# 1.3 Remote URL normalizer
# ---------------------------------------------------------------------------


def test_https_with_dot_git() -> None:
    assert normalize_remote_url("https://github.com/owner/repo.git") == "github:owner/repo"


def test_https_without_dot_git() -> None:
    assert normalize_remote_url("https://github.com/owner/repo") == "github:owner/repo"


def test_ssh_at_form() -> None:
    assert normalize_remote_url("git@github.com:owner/repo.git") == "github:owner/repo"


def test_ssh_scheme_form() -> None:
    assert normalize_remote_url("ssh://git@github.com/owner/repo.git") == "github:owner/repo"


def test_trailing_slash_normalized() -> None:
    assert normalize_remote_url("https://github.com/owner/repo/") == "github:owner/repo"


def test_local_file_scheme_normalized(tmp_path: Path) -> None:
    repo = tmp_path / "origin.git"
    repo.mkdir()
    n = normalize_remote_url(f"file://{repo}")
    assert n.startswith("file:") and n.endswith(str(repo.resolve()))


def test_local_absolute_path_normalized(tmp_path: Path) -> None:
    repo = tmp_path / "origin.git"
    repo.mkdir()
    n = normalize_remote_url(str(repo))
    assert n == f"file:{repo.resolve()}"


def test_remotes_equal_equivalent_forms() -> None:
    assert remotes_equal("https://github.com/o/r.git", "git@github.com:o/r.git")
    assert remotes_equal("https://github.com/o/r/", "https://github.com/o/r")


def test_different_owner_does_not_match() -> None:
    assert not remotes_equal("https://github.com/o1/r.git", "https://github.com/o2/r.git")


def test_different_host_does_not_match() -> None:
    assert not remotes_equal("https://gitlab.com/o/r.git", "https://github.com/o/r.git")


def test_different_repo_does_not_match() -> None:
    assert not remotes_equal("https://github.com/o/r1.git", "https://github.com/o/r2.git")


def test_credentials_in_url_redacted_for_artifact_form() -> None:
    redacted = redact_remote_url("https://user:secret@github.com/o/r.git")
    assert "secret" not in redacted
    assert "user" not in redacted or redacted.count("***") >= 1
    assert "github.com/o/r" in redacted


def test_redact_remote_url_passthrough_clean() -> None:
    assert redact_remote_url("https://github.com/o/r.git") == "https://github.com/o/r.git"
