"""Local CLI for running portfolio-manager tools outside Hermes."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from portfolio_manager.tools import (
    _handle_portfolio_config_validate,
    _handle_portfolio_github_sync,
    _handle_portfolio_heartbeat,
    _handle_portfolio_ping,
    _handle_portfolio_project_list,
    _handle_portfolio_status,
    _handle_portfolio_worktree_inspect,
)

TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "portfolio_ping": _handle_portfolio_ping,
    "portfolio_config_validate": _handle_portfolio_config_validate,
    "portfolio_project_list": _handle_portfolio_project_list,
    "portfolio_github_sync": _handle_portfolio_github_sync,
    "portfolio_worktree_inspect": _handle_portfolio_worktree_inspect,
    "portfolio_status": _handle_portfolio_status,
    "portfolio_heartbeat": _handle_portfolio_heartbeat,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run portfolio-manager tools locally")
    parser.add_argument("tool", choices=list(TOOL_HANDLERS), help="Tool to run")
    parser.add_argument("--json", action="store_true", help="Output raw JSON result")
    args = parser.parse_args(argv)

    handler = TOOL_HANDLERS[args.tool]
    result = handler({})

    print(result)


if __name__ == "__main__":
    main()
