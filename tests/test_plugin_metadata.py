"""Test plugin.yaml metadata validity for Phase 0.3."""

from pathlib import Path
from typing import Any

import yaml

PLUGIN_YAML = Path(__file__).resolve().parent.parent / "plugin.yaml"


def _load_plugin_yaml() -> dict[str, Any]:
    """Load and parse plugin.yaml."""
    with PLUGIN_YAML.open() as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


class TestPluginMetadata:
    """Verify plugin.yaml has valid metadata."""

    def test_plugin_yaml_exists(self) -> None:
        assert PLUGIN_YAML.is_file(), f"plugin.yaml not found at {PLUGIN_YAML}"

    def test_name_is_portfolio_manager(self) -> None:
        data = _load_plugin_yaml()
        assert data.get("name") == "portfolio-manager"

    def test_version_exists_and_nonempty(self) -> None:
        data = _load_plugin_yaml()
        version = data.get("version")
        assert version is not None, "version field is missing"
        assert isinstance(version, str) and version.strip(), "version must be a non-empty string"

    def test_description_exists_and_nonempty(self) -> None:
        data = _load_plugin_yaml()
        description = data.get("description")
        assert description is not None, "description field is missing"
        assert isinstance(description, str) and description.strip(), "description must be a non-empty string"

    def test_read_only_mode_documented(self) -> None:
        """Read-only mode must be documented in plugin.yaml description."""
        data = _load_plugin_yaml()
        description = data.get("description", "")
        assert "read-only" in description.lower(), "Plugin description must mention read-only mode for MVP 1"

    def test_author_exists(self) -> None:
        data = _load_plugin_yaml()
        author = data.get("author")
        assert author is not None, "author field is missing"
        assert isinstance(author, str) and author.strip(), "author must be a non-empty string"

    def test_kind_is_standalone(self) -> None:
        data = _load_plugin_yaml()
        assert data.get("kind") == "standalone"

    def test_provides_tools_includes_portfolio_ping(self) -> None:
        data = _load_plugin_yaml()
        tools = data.get("provides_tools", [])
        assert "portfolio_ping" in tools, "provides_tools must include portfolio_ping"
