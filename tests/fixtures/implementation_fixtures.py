"""E2E fixtures for MVP 6 implementation tests.

Creates a fake harness script, harnesses.yaml, and a fully prepared issue
worktree -- all local, no network.
"""

from __future__ import annotations

import os
import subprocess
import textwrap
from typing import TYPE_CHECKING

import pytest

from portfolio_manager.config import load_projects_config
from portfolio_manager.state import init_state, open_state, upsert_issue, upsert_project
from portfolio_manager.worktree_state import upsert_issue_worktree

if TYPE_CHECKING:
    from pathlib import Path

_GIT_ENV = {
    **os.environ,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# 17.1.1 -- Fake harness script
# ---------------------------------------------------------------------------

_FAKE_HARNESS_BODY = (
    "#!/usr/bin/env python3\n"
    "# Fake coding harness for E2E tests -- controlled by argv[1].\n"
    "from __future__ import annotations\n"
    "\n"
    "import json\n"
    "import os\n"
    "import sys\n"
    "import time\n"
    "from pathlib import Path\n"
    "\n"
    'mode = sys.argv[1] if len(sys.argv) > 1 else "ok"\n'
    "cwd = Path.cwd()\n"
    'artifact_dir = os.environ.get("PORTFOLIO_IMPLEMENTATION_ARTIFACT_DIR", "")\n'
    'input_path = os.environ.get("PORTFOLIO_IMPLEMENTATION_INPUT", "")\n'
    "\n"
    "def _write_result(data: dict) -> None:\n"
    "    if artifact_dir:\n"
    '        p = Path(artifact_dir) / "harness-result.json"\n'
    "        p.parent.mkdir(parents=True, exist_ok=True)\n"
    '        p.write_text(json.dumps(data, indent=2), encoding="utf-8")\n'
    "\n"
    "def _make_src_and_test() -> None:\n"
    "    src = cwd / 'src'\n"
    "    src.mkdir(exist_ok=True)\n"
    '    (src / "feature.py").write_text("def new_feature():\\n    return True\\n", encoding="utf-8")\n'
    "    tests = cwd / 'tests'\n"
    "    tests.mkdir(exist_ok=True)\n"
    '    (tests / "test_feature.py").write_text(\n'
    '        "from src.feature import new_feature\\n\\n"\n'
    '        "# AC-1: new_feature function exists\\n"\n'
    '        "# AC-2: function returns True\\n"\n'
    '        "def test_new_feature():\\n    assert new_feature() == True\\n",\n'
    '        encoding="utf-8",\n'
    "    )\n"
    "\n"
    'if mode == "ok":\n'
    "    _make_src_and_test()\n"
    '    _write_result({"status": "implemented"})\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "ok_no_result_json":\n'
    "    _make_src_and_test()\n"
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "nonzero":\n'
    "    sys.exit(2)\n"
    "\n"
    'elif mode == "timeout":\n'
    "    time.sleep(300)\n"
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "needs_user":\n'
    "    _write_result({\n"
    '        "status": "needs_user",\n'
    '        "needs_user": {\n'
    '            "question": "Should the feature use async or sync IO?",\n'
    '            "options": ["async", "sync"],\n'
    "        },\n"
    "    })\n"
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "protected_path":\n'
    '    (cwd / ".env").write_text("SECRET=leaked\\n", encoding="utf-8")\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "out_of_scope":\n'
    '    other = cwd / "unrelated_project"\n'
    "    other.mkdir(exist_ok=True)\n"
    '    (other / "hack.py").write_text("print(\'pwned\')\\n", encoding="utf-8")\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "no_tests":\n'
    "    src = cwd / 'src'\n"
    "    src.mkdir(exist_ok=True)\n"
    '    (src / "feature.py").write_text("def new_feature():\\n    return True\\n", encoding="utf-8")\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "empty_tests":\n'
    "    src = cwd / 'src'\n"
    "    src.mkdir(exist_ok=True)\n"
    '    (src / "feature.py").write_text("def new_feature():\\n    return True\\n", encoding="utf-8")\n'
    "    tests = cwd / 'tests'\n"
    "    tests.mkdir(exist_ok=True)\n"
    '    (tests / "test_feature.py").write_text("def test_nothing():\\n    assert True\\n", encoding="utf-8")\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "with_waiver":\n'
    "    docs = cwd / 'docs'\n"
    "    docs.mkdir(exist_ok=True)\n"
    '    (docs / "guide.md").write_text("# Guide\\n\\nHello world.\\n", encoding="utf-8")\n'
    "    _write_result({\n"
    '        "status": "implemented",\n'
    '        "test_first_waiver": {\n'
    '            "reason": "Documentation-only change: no functional code to test. "\n'
    '                      "The change updates the user guide with corrected instructions.",\n'
    "        },\n"
    "    })\n"
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "review_fix_in":\n'
    "    src = cwd / 'src'\n"
    "    src.mkdir(exist_ok=True)\n"
    '    (src / "bug.py").write_text("# fixed\\n", encoding="utf-8")\n'
    "    tests = cwd / 'tests'\n"
    "    tests.mkdir(exist_ok=True)\n"
    '    (tests / "test_bug.py").write_text(\n'
    '        "# AC-1: bug is fixed\\n"\n'
    '        "def test_bug_fixed():\\n    assert True != False\\n", encoding="utf-8",\n'
    "    )\n"
    '    _write_result({"status": "implemented"})\n'
    "    sys.exit(0)\n"
    "\n"
    'elif mode == "review_fix_out":\n'
    '    other = cwd / "unrelated"\n'
    "    other.mkdir(exist_ok=True)\n"
    '    (other / "hack.py").write_text("print(\'out of scope\')\\n", encoding="utf-8")\n'
    "    sys.exit(0)\n"
    "\n"
    "else:\n"
    "    sys.exit(1)\n"
)


@pytest.fixture
def fake_harness_script(tmp_path: Path) -> Path:
    """Write the fake harness script and return its path."""
    script = tmp_path / "fake_harness.py"
    script.write_text(_FAKE_HARNESS_BODY, encoding="utf-8")
    script.chmod(0o755)
    return script


# ---------------------------------------------------------------------------
# 17.1.2 -- harnesses.yaml with fake harness
# ---------------------------------------------------------------------------


@pytest.fixture
def harnesses_yaml_with_fake(
    fake_harness_script: Path,
    agent_root: Path,
) -> Path:
    """Write a harnesses.yaml pointing at the fake harness script."""
    cfg = agent_root / "config" / "harnesses.yaml"
    cfg.write_text(
        textwrap.dedent(f"""\
            harnesses:
              - id: fake
                command: ["python3", "{fake_harness_script}", "ok"]
                env_passthrough: []
                timeout_seconds: 30
                max_files_changed: 20
                required_checks:
                  - unit_tests
                checks:
                  unit_tests:
                    command: ["python3", "-c", "pass"]
                    timeout_seconds: 10
            """),
        encoding="utf-8",
    )
    return cfg


# ---------------------------------------------------------------------------
# 17.1.3 -- Prepared issue worktree
# ---------------------------------------------------------------------------


@pytest.fixture
def prepared_issue_worktree(
    bare_remote: Path,
    agent_root: Path,
    projects_yaml_pointing_to_bare_remote: Path,
    harnesses_yaml_with_fake: Path,
    tmp_path: Path,
) -> dict:
    """Create a fully prepared agent root with issue worktree for testproj/42.

    Returns dict with: root, project_id, issue_number, worktree_path, conn,
    spec_path, bare_remote.
    """
    root = agent_root
    project_id = "testproj"
    issue_number = 42

    # Open and init state DB
    conn = open_state(root)
    init_state(conn)

    # Upsert project into DB (needed for foreign keys)
    config = load_projects_config(root)
    project_cfg = config.projects[0]
    upsert_project(conn, project_cfg)

    # Create issue worktree: clone bare remote into worktrees/testproj-issue-42
    wt_path = root / "worktrees" / f"{project_id}-issue-{issue_number}"
    _git("clone", str(bare_remote), str(wt_path), cwd=root)
    # Create the expected branch
    _git("checkout", "-b", f"agent/{project_id}/issue-{issue_number}", cwd=wt_path)

    # Create issue spec artifact
    spec_dir = root / "artifacts" / "issues" / project_id / "draft_spec42"
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "spec.md"
    spec_path.write_text(
        "# Feature: New Feature\n\n## Acceptance Criteria\n\n"
        "AC-1: The system shall provide a new_feature function.\n"
        "AC-2: The function returns True when called.\n",
        encoding="utf-8",
    )

    # Upsert issue row with spec_artifact_path
    upsert_issue(
        conn,
        project_id,
        {
            "number": issue_number,
            "title": "Add new feature",
            "state": "open",
        },
    )
    # Update spec_artifact_path
    conn.execute(
        "UPDATE issues SET spec_artifact_path=? WHERE project_id=? AND issue_number=?",
        (str(spec_dir), project_id, issue_number),
    )
    conn.commit()

    # Upsert worktree row
    upsert_issue_worktree(
        conn,
        project_id=project_id,
        issue_number=issue_number,
        path=str(wt_path),
        state="clean",
        branch_name=f"agent/{project_id}/issue-{issue_number}",
        base_branch="main",
        remote_url=bare_remote.as_uri(),
    )

    return {
        "root": root,
        "project_id": project_id,
        "issue_number": issue_number,
        "worktree_path": wt_path,
        "conn": conn,
        "spec_path": spec_path,
        "bare_remote": bare_remote,
    }
