"""Verify docs/hermes-plugin-api-notes.md exists with all required headings."""

from pathlib import Path

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "hermes-plugin-api-notes.md"

REQUIRED_HEADINGS = [
    "# Hermes Plugin API Notes",
    "## Required Files",
    "## plugin.yaml Fields",
    "## Tool Registration API",
    "## Tool Schema Format",
    "## Handler Signature",
    "## Return Format",
    "## Skill Discovery",
    "## Plugin Reload or Restart Procedure",
    "## Source References",
]


def test_doc_file_exists() -> None:
    assert DOC_PATH.is_file(), f"Missing doc file: {DOC_PATH}"


def test_doc_has_all_required_headings() -> None:
    assert DOC_PATH.is_file(), f"Missing doc file: {DOC_PATH}"
    content = DOC_PATH.read_text()
    for heading in REQUIRED_HEADINGS:
        assert heading in content, f"Missing heading: {heading!r}"


def test_doc_has_key_api_details() -> None:
    """Spot-check that critical API details are documented."""
    assert DOC_PATH.is_file(), f"Missing doc file: {DOC_PATH}"
    content = DOC_PATH.read_text()

    # register_tool signature must mention key params
    assert "register_tool" in content
    assert "name" in content
    assert "schema" in content
    assert "handler" in content

    # Return helpers
    assert "tool_result" in content
    assert "tool_error" in content

    # Plugin structure
    assert "plugin.yaml" in content
    assert "__init__.py" in content
    assert "register" in content

    # No hot reload
    assert "restart" in content.lower()
