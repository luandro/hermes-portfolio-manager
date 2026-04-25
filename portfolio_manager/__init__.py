"""Hermes Portfolio Manager plugin — MVP 1 (read-only)."""

from __future__ import annotations

import json
from typing import Any

from portfolio_manager.tools import _handle_portfolio_ping

PORTFOLIO_PING_SCHEMA = {
    "name": "portfolio_ping",
    "description": "Smoke test: confirm the Portfolio Manager plugin is loaded.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def tool_result(
    *,
    status: str,
    tool: str,
    message: str,
    data: dict[str, Any] | None = None,
    summary: str = "",
    reason: str | None = None,
) -> str:
    """Build a JSON string in the shared tool result format."""
    return json.dumps(
        {
            "status": status,
            "tool": tool,
            "message": message,
            "data": data if data is not None else {},
            "summary": summary,
            "reason": reason,
        },
        ensure_ascii=False,
    )


def register(ctx: Any) -> None:
    """Register portfolio tools with the Hermes plugin context."""
    ctx.register_tool(
        name="portfolio_ping",
        toolset="portfolio-manager",
        schema=PORTFOLIO_PING_SCHEMA,
        handler=_handle_portfolio_ping,
        check_fn=None,
        emoji="",
    )
