"""Tests for MVP 3 tool handlers — Phase 8 + 9."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


from portfolio_manager.schemas import (
    ALL_SCHEMAS,
    PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_CREATE_SCHEMA,
    PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA,
    PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA,
    PORTFOLIO_ISSUE_QUESTIONS_SCHEMA,
    PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA,
    PORTFOLIO_PROJECT_RESOLVE_SCHEMA,
)


def _make_config(root: Path) -> Path:
    """Set up a valid config with one project."""
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "projects.yaml").write_text("""\
version: 1
projects:
  - id: comapeo-cloud-app
    name: CoMapeo Cloud App
    repo: git@github.com:digidem/comapeo-cloud-app.git
    github: {owner: digidem, repo: comapeo-cloud-app}
    priority: medium
    status: active
  - id: comapeo-mobile
    name: CoMapeo Mobile
    repo: git@github.com:digidem/comapeo-mobile.git
    github: {owner: digidem, repo: comapeo-mobile}
    priority: medium
    status: active
""")
    return root


class TestMvp3ToolSchemas:
    def test_schemas_exist(self) -> None:
        """Verify all MVP 3 schemas are defined."""
        schemas = {
            PORTFOLIO_PROJECT_RESOLVE_SCHEMA["name"]: PORTFOLIO_PROJECT_RESOLVE_SCHEMA,
            PORTFOLIO_ISSUE_DRAFT_SCHEMA["name"]: PORTFOLIO_ISSUE_DRAFT_SCHEMA,
            PORTFOLIO_ISSUE_QUESTIONS_SCHEMA["name"]: PORTFOLIO_ISSUE_QUESTIONS_SCHEMA,
            PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA["name"]: PORTFOLIO_ISSUE_UPDATE_DRAFT_SCHEMA,
            PORTFOLIO_ISSUE_CREATE_SCHEMA["name"]: PORTFOLIO_ISSUE_CREATE_SCHEMA,
            PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA["name"]: PORTFOLIO_ISSUE_CREATE_FROM_DRAFT_SCHEMA,
            PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA["name"]: PORTFOLIO_ISSUE_EXPLAIN_DRAFT_SCHEMA,
            PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA["name"]: PORTFOLIO_ISSUE_LIST_DRAFTS_SCHEMA,
            PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA["name"]: PORTFOLIO_ISSUE_DISCARD_DRAFT_SCHEMA,
        }
        assert len(schemas) == 9
        assert PORTFOLIO_ISSUE_DRAFT_SCHEMA["parameters"]["required"] == ["text"]

    def test_all_schemas_in_list(self) -> None:
        """Verify MVP 3 schemas are in ALL_SCHEMAS list."""
        names = {s["name"] for s in ALL_SCHEMAS}
        mvp3_names = {
            "portfolio_project_resolve",
            "portfolio_issue_draft",
            "portfolio_issue_questions",
            "portfolio_issue_update_draft",
            "portfolio_issue_create",
            "portfolio_issue_create_from_draft",
            "portfolio_issue_explain_draft",
            "portfolio_issue_list_drafts",
            "portfolio_issue_discard_draft",
        }
        assert mvp3_names.issubset(names), f"Missing schemas: {mvp3_names - names}"


class TestMvp3ToolHandlers:
    def test_project_resolve_exact(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_project_resolve

        result = json.loads(
            _handle_portfolio_project_resolve({"project_ref": "comapeo-cloud-app", "root": str(tmp_path)})
        )
        assert result["status"] == "success"
        assert result["data"]["state"] == "resolved"
        assert result["data"]["project_id"] == "comapeo-cloud-app"

    def test_issue_draft(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_issue_draft

        result = json.loads(
            _handle_portfolio_issue_draft(
                {"text": "Users should export layers as SMP", "project_ref": "comapeo-cloud-app", "root": str(tmp_path)}
            )
        )
        assert result["status"] == "success"
        assert "draft_id" in result["data"]
        assert result["data"]["state"] in ("ready_for_creation", "needs_user_questions")

    def test_issue_questions(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_issue_draft, _handle_portfolio_issue_questions

        draft_result = json.loads(
            _handle_portfolio_issue_draft(
                {
                    "text": "Fix the crash when uploading files",
                    "project_ref": "comapeo-cloud-app",
                    "root": str(tmp_path),
                }
            )
        )
        draft_id = draft_result["data"]["draft_id"]
        questions_result = json.loads(_handle_portfolio_issue_questions({"draft_id": draft_id, "root": str(tmp_path)}))
        assert questions_result["status"] == "success"
        assert "questions" in questions_result["data"]

    def test_issue_update_draft(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_issue_draft, _handle_portfolio_issue_update_draft

        draft_result = json.loads(
            _handle_portfolio_issue_draft(
                {"text": "Make the stories better", "project_ref": "comapeo-cloud-app", "root": str(tmp_path)}
            )
        )
        draft_id = draft_result["data"]["draft_id"]
        update_result = json.loads(
            _handle_portfolio_issue_update_draft(
                {"draft_id": draft_id, "answers": "Target CoMapeo Mobile first", "root": str(tmp_path)}
            )
        )
        assert update_result["status"] == "success"
        assert update_result["data"]["draft_id"] == draft_id

    def test_issue_list_drafts(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_issue_draft, _handle_portfolio_issue_list_drafts

        _handle_portfolio_issue_draft(
            {"text": "Test issue for listing", "project_ref": "comapeo-cloud-app", "root": str(tmp_path)}
        )
        list_result = json.loads(_handle_portfolio_issue_list_drafts({"root": str(tmp_path)}))
        assert list_result["status"] == "success"
        assert list_result["data"]["count"] >= 1

    def test_issue_discard_draft(self, tmp_path: Path) -> None:
        _make_config(tmp_path)
        from portfolio_manager.tools import _handle_portfolio_issue_discard_draft, _handle_portfolio_issue_draft

        draft_result = json.loads(
            _handle_portfolio_issue_draft(
                {"text": "Discard this idea", "project_ref": "comapeo-cloud-app", "root": str(tmp_path)}
            )
        )
        draft_id = draft_result["data"]["draft_id"]
        discard_result = json.loads(
            _handle_portfolio_issue_discard_draft({"draft_id": draft_id, "confirm": True, "root": str(tmp_path)})
        )
        assert discard_result["status"] == "success"
