#!/usr/bin/env python3
"""Phase 9 smoke test — exercises all portfolio tools locally outside Hermes."""

from __future__ import annotations

import json
import os
import sys


def _get_tools_module():
    """Import portfolio_manager.tools — relies on uv editable install."""
    import portfolio_manager.tools  # fmt: skip

    return portfolio_manager.tools


_tools = _get_tools_module()


def test(tool_name: str, handler, args: dict | None = None) -> dict:
    """Call a tool handler and print + return the result."""
    args = args or {}
    try:
        result_raw = handler(args)
        result = json.loads(result_raw) if isinstance(result_raw, str) else result_raw
    except Exception as e:
        result = {"status": "failed", "message": str(e)}
    status = result.get("status", "?")
    symbol = (
        "PASS"
        if status == "success"
        else "WARN"
        if status in ("skipped",)
        else "FAIL"
        if status == "failed"
        else "CHECK"
    )
    msg = result.get("message", "")
    print(f"  [{symbol}] {tool_name}: {status} — {msg}")
    if result.get("summary"):
        print(f"           summary: {result['summary']}")
    if result.get("warnings") or result.get("data", {}).get("has_warnings"):
        warns = result.get("data", {}).get("warnings", [])
        for w in warns:
            print(f"           warning: {w}")
    return result


def main():
    passed = 0
    failed = 0

    print("=== Portfolio Manager — Phase 9 Smoke Tests ===\n")
    print(f"AGENT_SYSTEM_ROOT={os.environ.get('AGENT_SYSTEM_ROOT', '~/.agent-system (default)')}")
    print()

    # 9.1 portfolio_ping
    print("[1/7] portfolio_ping")
    r = test("portfolio_ping", _tools._handle_portfolio_ping)
    if r.get("status") == "success":
        passed += 1
    else:
        failed += 1

    # 9.2 portfolio_config_validate
    print("[2/7] portfolio_config_validate")
    r = test("portfolio_config_validate", _tools._handle_portfolio_config_validate)
    if r.get("status") == "success":
        passed += 1
    else:
        failed += 1

    # 9.3 portfolio_project_list
    print("[3/7] portfolio_project_list")
    r = test("portfolio_project_list", _tools._handle_portfolio_project_list)
    if r.get("status") == "success":
        passed += 1
    else:
        failed += 1

    # 9.4 portfolio_worktree_inspect
    print("[4/7] portfolio_worktree_inspect")
    r = test("portfolio_worktree_inspect", _tools._handle_portfolio_worktree_inspect)
    # Worktree inspect may show warnings (no actual git clones) but should not fail
    if r.get("status") in ("success",):
        passed += 1
    else:
        failed += 1

    # 9.5 portfolio_github_sync
    print("[5/7] portfolio_github_sync")
    r = test("portfolio_github_sync", _tools._handle_portfolio_github_sync)
    if r.get("status") in ("success", "blocked"):
        passed += 1
    else:
        failed += 1

    # 9.6 portfolio_status
    print("[6/7] portfolio_status")
    r = test("portfolio_status", _tools._handle_portfolio_status)
    if r.get("status") in ("success",):
        passed += 1
    else:
        failed += 1

    # 9.7 portfolio_heartbeat
    print("[7/7] portfolio_heartbeat")
    r = test("portfolio_heartbeat", _tools._handle_portfolio_heartbeat)
    if r.get("status") in ("success", "blocked"):
        passed += 1
    else:
        failed += 1

    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
