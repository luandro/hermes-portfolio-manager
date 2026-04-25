"""Tool handlers for the Portfolio Manager plugin."""

from __future__ import annotations

import json
from typing import Any


def _handle_portfolio_ping(args: dict[str, Any], **kwargs: Any) -> str:
    """Smoke test handler — confirms the plugin is loaded."""
    result: dict[str, Any] = {
        "status": "success",
        "tool": "portfolio_ping",
        "message": "Portfolio plugin is loaded",
        "data": {},
        "summary": "Portfolio plugin is loaded.",
        "reason": None,
    }
    return json.dumps(result, ensure_ascii=False)
