"""End-to-end test: full project admin lifecycle through dev_cli.py subprocess.

Exercises every admin tool in sequence against a single tmp_path root,
validating JSON results, SQLite state, and config integrity at each step.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from typing import Any

import yaml


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "dev_cli.py", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _parse(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
    return json.loads(result.stdout)


def _read_db_status(root: str, project_id: str) -> str | None:
    """Read project status from SQLite state database."""
    db_path = f"{root}/state/state.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _load_config_yaml(root: str) -> dict[str, Any]:
    """Load and return the projects.yaml config."""
    with open(f"{root}/config/projects.yaml") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "Config must be a dict"
    return data


def test_project_admin_full_lifecycle(tmp_path: Any) -> None:
    """E2e lifecycle: add -> explain -> priority -> pause -> resume ->
    auto-merge -> archive -> backup -> remove(blocked) -> remove(confirmed).
    """
    root = str(tmp_path / "portfolio")
    pid = "e2e-test-project"

    # ------------------------------------------------------------------
    # 1. Add project (creates missing config, no backup on first run)
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_add",
            "--repo",
            "acme/e2e-test-project",
            "--name",
            "E2E Test Project",
            "--priority",
            "medium",
            "--root",
            root,
            "--validate-github",
            "false",
        )
    )
    assert r["status"] == "success", f"add failed: {r}"
    assert r["data"]["project_id"] == pid
    assert r["data"]["is_first_run"] is True
    assert r["data"]["backup_created"] is False

    # ------------------------------------------------------------------
    # 2. Explain project (read-only)
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_explain",
            "--project-id",
            pid,
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert r["data"]["project"]["id"] == pid
    assert r["data"]["project"]["name"] == "E2E Test Project"
    assert r["data"]["project"]["priority"] == "medium"
    assert r["data"]["project"]["status"] == "active"

    # ------------------------------------------------------------------
    # 3. Set priority to high
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_set_priority",
            "--project-id",
            pid,
            "--priority",
            "high",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert "high" in r["message"]

    # Verify in config
    cfg = _load_config_yaml(root)
    proj = cfg["projects"][0]
    assert proj["priority"] == "high"

    # ------------------------------------------------------------------
    # 4. Pause project with reason
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_pause",
            "--project-id",
            pid,
            "--reason",
            "waiting on upstream fix",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert r["data"]["reason"] == "waiting on upstream fix"

    # Verify SQLite state
    db_status = _read_db_status(root, pid)
    assert db_status == "paused", f"Expected paused, got {db_status}"

    # ------------------------------------------------------------------
    # 5. Resume project
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_resume",
            "--project-id",
            pid,
            "--root",
            root,
        )
    )
    assert r["status"] == "success"

    db_status = _read_db_status(root, pid)
    assert db_status == "active", f"Expected active, got {db_status}"

    # ------------------------------------------------------------------
    # 6. Set auto-merge low-risk
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_set_auto_merge",
            "--project-id",
            pid,
            "--auto-merge-enabled",
            "true",
            "--auto-merge-max-risk",
            "low",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert r["data"]["enabled"] is True
    assert r["data"]["max_risk"] == "low"

    # Verify in config
    cfg = _load_config_yaml(root)
    am = cfg["projects"][0].get("auto_merge", {})
    assert am.get("enabled") is True
    assert am.get("max_risk") == "low"

    # ------------------------------------------------------------------
    # 7. Archive project
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_archive",
            "--project-id",
            pid,
            "--reason",
            "project completed",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"

    db_status = _read_db_status(root, pid)
    assert db_status == "archived", f"Expected archived, got {db_status}"

    # ------------------------------------------------------------------
    # 8. Create a config backup
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_config_backup",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert r["data"]["backup_created"] is True
    assert r["data"]["backup_path"] is not None

    # ------------------------------------------------------------------
    # 9. Attempt remove without confirmation (should be blocked)
    # ------------------------------------------------------------------
    result = _run_cli(
        "portfolio_project_remove",
        "--project-id",
        pid,
        "--root",
        root,
    )
    r = json.loads(result.stdout)
    assert r["status"] == "blocked", f"Expected blocked, got {r['status']}"
    assert "confirm" in r["message"].lower() or "confirmation" in r["message"].lower()

    # Project should still be in config
    cfg = _load_config_yaml(root)
    ids = [p["id"] for p in cfg["projects"]]
    assert pid in ids, "Project should still exist after blocked remove"

    # ------------------------------------------------------------------
    # 10. Remove with confirmation
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_project_remove",
            "--project-id",
            pid,
            "--confirm",
            "true",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"

    # Project should be gone from config
    cfg = _load_config_yaml(root)
    ids = [p["id"] for p in cfg.get("projects", [])]
    assert pid not in ids, "Project should be removed from config"

    # ------------------------------------------------------------------
    # 11. Verify SQLite project status is "archived" (preserved by remove handler)
    # ------------------------------------------------------------------
    db_status = _read_db_status(root, pid)
    assert db_status == "archived", f"Expected archived in SQLite, got {db_status}"

    # ------------------------------------------------------------------
    # 12. Verify final config is valid
    # ------------------------------------------------------------------
    r = _parse(
        _run_cli(
            "portfolio_config_validate",
            "--root",
            root,
        )
    )
    assert r["status"] == "success"
    assert r["data"]["valid"] is True
    assert r["data"]["project_count"] == 0
