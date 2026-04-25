"""Tests for dev_cli.py local tool runner."""

import json
import subprocess
import sys


def test_dev_cli_portfolio_ping() -> None:
    """dev_cli.py portfolio_ping --json returns valid JSON with success status."""
    result = subprocess.run(
        [sys.executable, "dev_cli.py", "portfolio_ping", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    parsed = json.loads(result.stdout)
    assert parsed["status"] == "success"
    assert parsed["tool"] == "portfolio_ping"
