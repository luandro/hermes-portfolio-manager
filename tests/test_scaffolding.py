"""Phase 0.2: Test scaffolding — verifies dev dependency declarations exist."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


class TestPyprojectExists:
    def test_pyproject_toml_exists(self) -> None:
        assert PYPROJECT.is_file(), f"{PYPROJECT} not found"

    def test_pyproject_has_project_name(self) -> None:
        data = tomllib.loads(PYPROJECT.read_text())
        assert "project" in data
        assert data["project"].get("name") == "hermes-portfolio-manager"

    def test_pyproject_has_testpaths(self) -> None:
        data = tomllib.loads(PYPROJECT.read_text())
        assert data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("testpaths") == ["tests"]


class TestDevDependencies:
    """Verify dev dependencies are declared (either optional-dependencies or requirements-dev.txt)."""

    def test_dev_deps_declared(self) -> None:
        """pyproject.toml must have [project.optional-dependencies] dev group."""
        data = tomllib.loads(PYPROJECT.read_text())
        opt = data.get("project", {}).get("optional-dependencies", {})
        assert "dev" in opt, "Missing [project.optional-dependencies] dev group"

    def test_dev_deps_include_pytest(self) -> None:
        data = tomllib.loads(PYPROJECT.read_text())
        dev_deps = data["project"]["optional-dependencies"]["dev"]
        assert any("pytest" in d.lower() for d in dev_deps), "pytest missing from dev deps"

    def test_pyyaml_declared(self) -> None:
        """pyyaml must be declared as a runtime or dev dependency."""
        data = tomllib.loads(PYPROJECT.read_text())
        runtime = data.get("project", {}).get("dependencies", [])
        dev = data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
        all_deps = runtime + dev
        assert any("pyyaml" in d.lower() for d in all_deps), "pyyaml missing from dependencies"

    def test_dev_deps_include_pydantic(self) -> None:
        data = tomllib.loads(PYPROJECT.read_text())
        dev_deps = data["project"]["optional-dependencies"]["dev"]
        assert any("pydantic" in d.lower() for d in dev_deps), "pydantic missing from dev deps"


class TestPytestDiscovery:
    """Verify pytest can discover and run tests."""

    def test_this_file_is_discovered(self) -> None:
        """If this runs, pytest discovery works."""
        assert True
