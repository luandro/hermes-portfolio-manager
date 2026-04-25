# Hermes Portfolio Manager

<!-- PROJECT SHIELDS -->
[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## About The Project

**Hermes Portfolio Manager** is a plugin for the Hermes Agent ecosystem that allows a single server-side agent to manage multiple GitHub projects through a unified manifest.

Designed for developers, team leads, and automated workflows, it provides a read-only, bird's-eye view of your entire portfolio. It enables Hermes to answer critical questions like:
* *What projects am I managing?*
* *What needs my attention?*
* *Which projects have open issues or PRs?*
* *Which local worktrees are clean, dirty, missing, or conflicted?*

**Note on MVP 1:** This initial release is intentionally **read-only and safe**. It does not perform autonomous coding, create issues, modify files in repositories, or alter project configurations. It strictly inspects GitHub state, local worktree status, and provides concise summaries back to the Hermes Agent (e.g., via Telegram).

### Built With

* [Python >= 3.12](https://www.python.org/)
* [Hermes Agent System](https://github.com/awana-digital/hermes)
* [GitHub CLI (`gh`)](https://cli.github.com/)
* [SQLite](https://www.sqlite.org/index.html)

---

## Getting Started

### Prerequisites

To run the Portfolio Manager, ensure you have the following installed on your host system:
* **Python 3.12+**
* **GitHub CLI (`gh`)** - Must be authenticated (`gh auth status`).
* **Hermes Agent** - Running on your VPS or local machine.

### Installation

1. **Clone the repository** (or copy the plugin directory) into your Hermes plugins folder:
   ```bash
   cp -r portfolio-manager ~/.hermes/plugins/portfolio-manager/
   ```
2. **Install dependencies** (if any are specified in `pyproject.toml` outside of dev requirements):
   ```bash
   cd ~/.hermes/plugins/portfolio-manager
   pip install -e .
   ```

---

## Configuration

The plugin relies on a centralized, server-side configuration manifest. No repository-local automation YAML is required.

**Default Configuration Path:**
```text
/srv/agent-system/config/projects.yaml
```
*(You can override this location by setting the `AGENT_SYSTEM_ROOT` environment variable).*

### Example `projects.yaml`

```yaml
version: 1
projects:
  - id: comapeo-cloud-app
    name: CoMapeo Cloud App
    repo: git@github.com:awana-digital/comapeo-cloud-app.git
    github:
      owner: awana-digital
      repo: comapeo-cloud-app
    priority: high
    status: active
```

The plugin will automatically manage state and worktrees within the `AGENT_SYSTEM_ROOT`:
* `state/state.sqlite`
* `worktrees/`

---

## Usage (Tools)

Once installed, Hermes can invoke the following tools automatically during conversations or scheduled cron jobs. All tools are strictly read-only with respect to project data.

* `portfolio_config_validate` - Validates the server-side configuration file (`projects.yaml`) without contacting GitHub or inspecting worktrees.
* `portfolio_project_list` - Lists and filters configured projects based on their status or priority.
* `portfolio_github_sync` - Reads open GitHub issues and PRs for configured projects using the GitHub CLI and updates the local SQLite state.
* `portfolio_worktree_inspect` - Inspects local worktree folders (`base` and `issue` worktrees) to determine if they are clean, dirty, uncommitted, or conflicted.
* `portfolio_heartbeat` - Runs a comprehensive status check across all projects, syncing GitHub and worktree state.
* `portfolio_status` - Returns a Telegram-friendly summary of the current portfolio status.

---

## Roadmap

**Current Version (MVP 1):** Read-only visibility, configuration parsing, GitHub CLI integration, and local worktree inspection.

**Future Considerations (MVP 2+):**
* Adding or archiving projects directly via Telegram.
* Autonomous issue implementation and PR creation.
* Review ladder automation and AI-driven code review.
* Automated local worktree creation and teardown.
* Maintenance skills and auto-merge capabilities.

---

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please refer to [`AGENTS.md`](./AGENTS.md) and [`SPEC.md`](./SPEC.md) for architectural guidelines and agent instructions.

---

## License

Distributed under the MIT License. See `pyproject.toml` or `plugin.yaml` for more information.
