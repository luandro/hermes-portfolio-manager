"""Phase 0 — Preflight and MVP 1 compatibility tests."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

from portfolio_manager.config import resolve_root
from portfolio_manager.tools import _ensure_dirs

SRC_DIR = Path(__file__).parent.parent / "portfolio_manager"
PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# resolve_root
# ---------------------------------------------------------------------------


def test_resolve_root_explicit() -> None:
    """Explicit root argument takes highest priority."""
    result = resolve_root("/custom/explicit")
    assert result == Path("/custom/explicit")


def test_resolve_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """AGENT_SYSTEM_ROOT env var is used when no explicit root."""
    monkeypatch.setenv("AGENT_SYSTEM_ROOT", "/from/env")
    result = resolve_root(None)
    assert result == Path("/from/env")


def test_resolve_root_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to ~/.agent-system when nothing else is provided."""
    monkeypatch.delenv("AGENT_SYSTEM_ROOT", raising=False)
    result = resolve_root(None)
    assert result == Path.home() / ".agent-system"


# ---------------------------------------------------------------------------
# _ensure_dirs
# ---------------------------------------------------------------------------


def test_ensure_dirs_creates_backups(tmp_path: Path) -> None:
    """_ensure_dirs must create a backups/ subdirectory under root."""
    _ensure_dirs(tmp_path)
    assert (tmp_path / "backups").is_dir()


# ---------------------------------------------------------------------------
# No hardcoded old system roots
# ---------------------------------------------------------------------------


def test_no_hardcoded_old_system_roots_in_source() -> None:
    """Source files must not contain old hardcoded roots /srv/agent-system or /usr/HOME/.agent-system."""
    old_roots = ("/srv/agent-system", "/usr/HOME/.agent-system")
    py_files = [*SRC_DIR.glob("*.py"), PROJECT_ROOT / "dev_cli.py"]
    for path in py_files:
        text = path.read_text(encoding="utf-8")
        for old_root in old_roots:
            assert old_root not in text, f"{old_root!r} found in {path}"


# ---------------------------------------------------------------------------
# Fixtures hygiene
# ---------------------------------------------------------------------------


def test_fixtures_use_home_agent_system_or_temp_roots() -> None:
    """Fixture YAML files must not reference /srv/agent-system."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    if not fixtures_dir.exists():
        return
    for path in fixtures_dir.glob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        assert "/srv/agent-system" not in text, f"/srv/agent-system found in {path}"
