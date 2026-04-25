# Guardrails Implementation Plan

## Objective

Set up local pre-commit hooks and CI pipeline for the Hermes Portfolio Manager plugin. This covers: linting (Ruff), type checking (MyPy), secret scanning (Gitleaks), security auditing (Bandit), dependency auditing (pip-audit), and standard pre-commit hygiene checks. The plan also adds `.gitignore` entries and `pyproject.toml` tool configuration.

All paths are relative to project root: `/home/luandro/Dev/hermes-multi-projects/portfolio-manager/`.

---

## File Layout

```
portfolio-manager/
  .gitignore
  .pre-commit-config.yaml
  .bandit.yaml
  pyproject.toml
  .github/
    workflows/
      ci.yml
```

No other files are created by this plan.

---

## Prerequisites

Tools that must be available on the developer machine (installed globally or in a venv):

| Tool | Install command | Purpose |
|------|----------------|---------|
| `pre-commit` | `pip install pre-commit` | Runs hooks on every commit |
| `ruff` | `pip install ruff` | Lint + format (also used in CI) |
| `mypy` | `pip install mypy` | Static type checking |
| `bandit` | `pip install bandit[toml]` | Python security linter |
| `gitleaks` | `brew install gitleaks` or download from [gitleaks releases](https://github.com/gitleaks/gitleaks/releases) | Secret scanning |
| `pip-audit` | `pip install pip-audit` | Dependency vulnerability scanning |

---

## Implementation Plan

### Step 1: Create `.gitignore`

- [ ] Create `.gitignore` at project root with the following content:

```gitignore
# Secrets and environment files
.secrets.*
.env
.env.*

# Database
*.sqlite
*.sqlite3
*.db

# Config with potential secrets
config/*.yaml
config/*.yml
!config/projects.example.yaml

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg

# Virtual environments
.venv/
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Testing
.coverage
htmlcov/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Gitleaks baseline
.gitleaks-report.json
```

Rationale: Prevents committing secrets, databases, config with credentials, and standard Python/IDE artifacts. The `!config/projects.example.yaml` exclusion allows an example config to be committed while blocking real configs that may contain org-specific details.

### Step 2: Create `pyproject.toml`

- [ ] Create `pyproject.toml` at project root with tool configuration sections:

```toml
[project]
name = "hermes-portfolio-manager"
version = "0.1.0"
description = "Hermes plugin to manage multiple GitHub projects from one server-side manifest. MVP 1 is read-only."
requires-python = ">=3.12"
license = "MIT"

[tool.ruff]
target-version = "py312"
line-length = 120

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "RUF",  # ruff-specific rules
]
ignore = [
    "E501",  # line length handled by formatter
]

[tool.ruff.lint.isort]
known-first-party = ["portfolio_manager"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict_equality = true

[[tool.mypy.overrides]]
module = ["yaml.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.bandit]
targets = ["hermes-portfolio-manager"]
exclude_dirs = ["tests"]
skips = ["B101"]  # allow assert in tests
```

Rationale: Ruff replaces flake8+isort+black with one fast tool. MyPy strict mode catches type errors early — important for a plugin that handles secrets and subprocess calls. Bandit skips B101 (assert used in test files) since pytest relies on assert. PyYAML (`yaml`) is the only expected external dependency without stubs, so it gets an override.

### Step 3: Create `.bandit.yaml`

- [ ] Create `.bandit.yaml` at project root:

```yaml
targets:
  - hermes-portfolio-manager
exclude_dirs:
  - tests
  - .git
  - .venv
skips:
  - B101
```

Rationale: Bandit can read config from both `pyproject.toml` and its own YAML file. The YAML file is kept for standalone `bandit` CLI usage outside of pre-commit (e.g., `bandit -c .bandit.yaml -r .`). Having both ensures consistency regardless of invocation method.

**Post-review update**: `.bandit.yaml` was removed — it's dead config since CI runs `bandit -c pyproject.toml` and the standalone CLI also reads from `pyproject.toml`. Removed to avoid config drift.

### Step 4: Create `.pre-commit-config.yaml`

- [ ] Create `.pre-commit-config.yaml` at project root:

```yaml
default_install_hook_types:
  - pre-commit

repos:
  # Ruff: lint + format (replaces flake8, isort, black)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.7
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        name: ruff lint
      - id: ruff-format
        name: ruff format

  # MyPy: static type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.15.0
    hooks:
      - id: mypy
        additional_dependencies:
          - pyyaml
        args: [--strict, --ignore-missing-imports]

  # Gitleaks: secret scanning
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.24.2
    hooks:
      - id: gitleaks

  # Standard pre-commit hooks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        args: [--unsafe]
      - id: check-json
      - id: check-added-large-files
        args: [--maxkb=500]
      - id: check-merge-conflict
      - id: check-ast
  # Forbid tabs (separate repo from pre-commit-hooks)
  - repo: https://github.com/Lucas-C/pre-commit-hooks
    rev: v1.5.5
    hooks:
      - id: forbid-tabs
```

Rationale: Ruff handles lint+format in one hook. MyPy runs with `--strict` to match pyproject.toml settings and `--ignore-missing-imports` to avoid failures on untyped transitive deps. Gitleaks catches 150+ secret patterns (tokens, keys, credentials). The pre-commit-hooks collection handles whitespace, file endings, YAML/JSON validity, large files, merge conflict markers, Python AST validity, and tab characters. The `--unsafe` flag on `check-yaml` allows multi-document YAML files (used in some CI configs). Large file threshold is 500KB to catch accidental data dumps.

### Step 5: Create `.github/workflows/ci.yml`

- [ ] Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  lint-and-typecheck:
    name: Lint + Typecheck
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff mypy pyyaml

      - name: Ruff lint
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: MyPy
        run: mypy --strict --ignore-missing-imports hermes-portfolio-manager/

  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov pyyaml

      - name: Run tests
        run: pytest --cov=hermes-portfolio-manager --cov-report=term-missing

  security:
    name: Security
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          persist-credentials: false
          fetch-depth: 0  # full history for gitleaks

      - name: Set up Python
        uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install bandit[toml] pip-audit

      - name: Bandit
        run: bandit -c pyproject.toml -r .

      - name: Gitleaks (full history)
        uses: gitleaks/gitleaks-action@ff98106e4c7b2bc287b24eaf42907196329070c7 # v2.3.9
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: pip-audit
        run: pip-audit --desc
```

Rationale: Three independent jobs run in parallel. Actions are pinned by SHA hash (not tag) to prevent supply chain attacks. `persist-credentials: false` prevents the GITHUB_TOKEN from persisting in the local git config. `fetch-depth: 0` gives gitleaks full history to scan. The `permissions: contents: read` block follows least-privilege — no write permissions needed for CI checks. Bandit reads config from `pyproject.toml` directly. `pip-audit --desc` shows vulnerability descriptions in output.

### Step 6: Install pre-commit hooks locally

- [ ] Run the following commands to activate pre-commit:

```bash
cd /home/luandro/Dev/hermes-multi-projects/portfolio-manager
pip install pre-commit ruff mypy bandit[toml] pip-audit
pre-commit install
pre-commit run --all-files
```

Rationale: `pre-commit install` registers the git hook. `pre-commit run --all-files` validates that all hooks work against the current codebase before any code is written. Since no Python source exists yet, only the hygiene hooks (trailing-whitespace, end-of-file-fixer, check-yaml, check-json, gitleaks) will produce meaningful results — ruff/mypy/bandit will pass vacuously on an empty target.

---

## Verification Criteria

Each step has a specific verification command:

| Step | What to verify | Command |
|------|---------------|---------|
| 1. `.gitignore` | Patterns match expected files | `git check-ignore .env config/projects.yaml state.sqlite` — each should print the path |
| 2. `pyproject.toml` | Ruff reads config | `ruff check --config pyproject.toml .` (exits 0) |
| 2. `pyproject.toml` | MyPy reads config | `mypy --version` (exits 0) |
| 2. `pyproject.toml` | Pytest reads config | `pytest --co -q` (exits 0, shows collected or empty) |
| 3. `.bandit.yaml` | Bandit reads config | `bandit -c .bandit.yaml -r .` (exits 0) |
| 4. `.pre-commit-config.yaml` | All hooks are valid | `pre-commit run --all-files` (exits 0 or shows only expected failures) |
| 5. `ci.yml` | YAML is valid | `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` (exits 0) |
| 6. Install | Hook is registered | `ls -la .git/hooks/pre-commit` (file exists) |

### End-to-end verification (after all steps)

```bash
# All of these should succeed:
pre-commit run --all-files
ruff check .
ruff format --check .
bandit -c pyproject.toml -r .
```

### CI verification (after pushing to GitHub)

Push to a PR branch and confirm all three CI jobs appear and pass (or fail with meaningful messages if source code has issues).

---

## Potential Risks and Mitigations

1. **Ruff/mypy versions drift between pre-commit and CI**
   Mitigation: Pin exact versions in `.pre-commit-config.yaml` `rev:` fields and install matching versions in CI via `pip install ruff==X.Y.Z mypy==X.Y.Z`. Update versions together in a single commit.

2. **MyPy strict mode too aggressive for early project**
   Mitigation: Start with `--ignore-missing-imports` in pre-commit (already configured). If strict mode blocks progress during early implementation, relax `disallow_untyped_defs` to `false` temporarily and tighten later. Do not remove the setting — comment it with a TODO.

3. **Gitleaks false positives on test fixtures**
   Mitigation: Add a `.gitleaksignore` file or use `allowlist` paths in gitleaks config if test data triggers false positives. Do not weaken gitleaks rules globally.

4. **Bandit flags subprocess usage as B602/B603**
   Mitigation: The project intentionally uses `subprocess.run` with argument arrays (not shell strings). Bandit's B603 (`subprocess_without_shell_equals_true`) is expected — it's safe when `shell=False` (the default). If Bandit raises it, add `# nosec B603` with a comment explaining the usage. Do not globally skip B603.

5. **GitHub Actions pinned SHAs become stale**
   Mitigation: Use a renovate/dependabot config to auto-update pinned SHAs monthly, or manually update them when updating dependencies. The SHA pins protect against tag mutation attacks.

---

## Alternative Approaches

1. **Use `requirements-dev.txt` instead of installing tools inline in CI**
   Trade-off: More maintainable for complex dependency trees, but adds a file to manage. Recommended for Phase 2 when the project grows beyond 3-4 dev dependencies. For now, inline installs in CI are simpler and sufficient.

2. **Use `uv` instead of `pip` for faster CI installs**
   Trade-off: `uv` is 10-100x faster than pip for dependency resolution. Worth considering once the project has a `pyproject.toml` with real dependencies. For MVP 1 with zero runtime deps, the speed difference is negligible.

3. **Add a `Makefile` or `justfile` for common commands**
   Trade-off: Convenient for developers but another file to maintain. Defer to when the project has actual build/run/test commands. The AGENTS.md already notes these as TODO.

---

## Notes for Forge (implementation agent)

- Create files in the exact order listed (Steps 1-5), then run Step 6.
- After creating all files, run `pre-commit run --all-files` and fix any issues before committing.
- The `hermes-portfolio-manager/` source directory does not exist yet. Ruff/mypy/bandit will pass vacuously on empty targets. The guardrails will become active as source code is added in subsequent implementation phases.
- The CI workflow references `hermes-portfolio-manager/` as the source directory — this matches the layout defined in SPEC.md.
- Commit all guardrail files in a single commit: "Add pre-commit hooks, CI pipeline, and project tooling config".
