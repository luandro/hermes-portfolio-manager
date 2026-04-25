"""Local CLI for running portfolio-manager tools outside Hermes."""

from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from portfolio_manager.tools import _handle_portfolio_ping

TOOL_HANDLERS: dict[str, Callable[[dict[str, str]], str] | None] = {
    "portfolio_ping": _handle_portfolio_ping,
    "portfolio_config_validate": None,
    "portfolio_project_list": None,
    "portfolio_github_sync": None,
    "portfolio_worktree_inspect": None,
    "portfolio_status": None,
    "portfolio_heartbeat": None,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-manager tools locally")
    parser.add_argument("tool", choices=list(TOOL_HANDLERS), help="Tool to run")
    parser.add_argument("--json", action="store_true", help="Output raw JSON result")
    args = parser.parse_args(argv)

    handler = TOOL_HANDLERS[args.tool]
    if handler is None:
        result = json.dumps(
            {
                "status": "blocked",
                "tool": args.tool,
                "message": f"{args.tool} is not yet implemented",
                "data": {},
                "summary": f"{args.tool} is not yet implemented.",
                "reason": None,
            },
            ensure_ascii=False,
        )
    else:
        result = handler({})

    print(result)


if __name__ == "__main__":
    main()
