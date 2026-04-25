"""Tests for portfolio_manager tool handlers."""

import json

from portfolio_manager.tools import _handle_portfolio_ping


def test_portfolio_ping() -> None:
    """portfolio_ping returns the exact shared tool result shape."""
    raw = _handle_portfolio_ping({})
    result = json.loads(raw)

    assert result == {
        "status": "success",
        "tool": "portfolio_ping",
        "message": "Portfolio plugin is loaded",
        "data": {},
        "summary": "Portfolio plugin is loaded.",
        "reason": None,
    }
