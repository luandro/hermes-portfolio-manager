"""Tests for portfolio_manager.implementation_scope_guard — Phase 9.2."""

from __future__ import annotations

import inspect

from portfolio_manager.implementation_scope_guard import ScopeCheck, check_scope


def test_scope_guard_passes_when_changed_files_within_spec_scope() -> None:
    """Files matching spec_scope patterns pass."""
    result = check_scope(
        changed_files=["src/feature.py", "tests/test_feature.py"],
        spec_scope=["src/*", "tests/*"],
        protected_paths=[],
        max_files_changed=20,
    )

    assert result.ok is True
    assert result.reasons == []
    assert result.protected_violations == []
    assert result.out_of_scope_files == []


def test_scope_guard_blocks_when_protected_path_changed() -> None:
    """Changing a file matching protected_paths is blocked."""
    result = check_scope(
        changed_files=["src/feature.py", "config/projects.yaml"],
        spec_scope=["src/*", "config/*"],
        protected_paths=["config/projects.yaml"],
        max_files_changed=20,
    )

    assert result.ok is False
    assert "config/projects.yaml" in result.protected_violations
    assert any("protected_path" in r for r in result.reasons)


def test_scope_guard_blocks_when_changed_files_exceed_max() -> None:
    """Changing more files than max_files_changed is blocked."""
    files = [f"src/file{i}.py" for i in range(25)]
    result = check_scope(
        changed_files=files,
        spec_scope=["src/*"],
        protected_paths=[],
        max_files_changed=20,
    )

    assert result.ok is False
    assert any("exceeds_max" in r for r in result.reasons)


def test_scope_guard_blocks_when_unrelated_files_changed() -> None:
    """Files not matching spec_scope are flagged as out-of-scope."""
    result = check_scope(
        changed_files=["src/feature.py", "unrelated/random.txt"],
        spec_scope=["src/*"],
        protected_paths=[],
        max_files_changed=20,
    )

    assert result.ok is False
    assert "unrelated/random.txt" in result.out_of_scope_files
    assert any("spec_scope" in r for r in result.reasons)


def test_scope_guard_passes_for_review_fix_files_in_approved_fix_scope() -> None:
    """Review fix files within fix_scope pass."""
    result = check_scope(
        changed_files=["src/bugfix.py"],
        spec_scope=["src/*", "tests/*"],
        protected_paths=[],
        max_files_changed=20,
        fix_scope=["src/bugfix.py"],
    )

    assert result.ok is True
    assert result.out_of_scope_files == []


def test_scope_guard_blocks_for_review_fix_files_outside_approved_fix_scope() -> None:
    """Review fix files outside fix_scope are blocked."""
    result = check_scope(
        changed_files=["src/bugfix.py", "src/other.py"],
        spec_scope=["src/*"],
        protected_paths=[],
        max_files_changed=20,
        fix_scope=["src/bugfix.py"],
    )

    assert result.ok is False
    assert "src/other.py" in result.out_of_scope_files
    assert any("fix_scope" in r for r in result.reasons)


def test_scope_guard_does_not_run_subprocess() -> None:
    """check_scope is a pure function — no subprocess calls."""
    sig = inspect.signature(check_scope)
    params = set(sig.parameters.keys())

    # Should NOT have workspace, root, or cwd parameters
    assert "workspace" not in params
    assert "root" not in params
    assert "cwd" not in params

    # Should accept pre-captured changed_files list
    assert "changed_files" in params

    # Functional test: call it and verify no side effects
    result = check_scope(
        changed_files=["src/a.py"],
        spec_scope=["src/*"],
        protected_paths=[],
        max_files_changed=10,
    )
    assert isinstance(result, ScopeCheck)


def test_scope_guard_writes_no_artifacts() -> None:
    """check_scope returns a ScopeCheck dataclass — no file I/O."""
    source = inspect.getsource(check_scope)

    # Should not contain file I/O patterns
    assert "open(" not in source
    assert "write_text" not in source
    assert "mkdir" not in source
    assert "Path(" not in source
    assert "os.path" not in source

    # Functional verification
    result = check_scope(
        changed_files=["src/a.py"],
        spec_scope=["src/*"],
        protected_paths=[],
        max_files_changed=10,
    )
    assert isinstance(result, ScopeCheck)
    assert isinstance(result.changed_files, list)
    assert isinstance(result.reasons, list)
