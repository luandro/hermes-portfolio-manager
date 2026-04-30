# Hermes Portfolio Manager

<!-- PROJECT SHIELDS -->
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
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

* [Python >= 3.11](https://www.python.org/)
* [Hermes Agent System](https://github.com/awana-digital/hermes)
* [GitHub CLI (`gh`)](https://cli.github.com/)
* [SQLite](https://www.sqlite.org/index.html)

---

## Getting Started

### Prerequisites

To run the Portfolio Manager, ensure you have the following installed on your host system:
* **Python 3.11+**
* **GitHub CLI (`gh`)** - Must be authenticated (`gh auth status`).
* **Hermes Agent** - Running on your VPS or local machine.

### Installation

1. **Clone the repository** (or symlink the plugin directory) into your Hermes plugins folder:
   ```bash
   ln -s /path/to/portfolio-manager ~/.hermes/plugins/portfolio-manager
   ```
2. **Install dependencies using uv**:
   ```bash
   cd portfolio-manager
   uv venv --python 3.11
   uv pip install -e ".[dev]"
   ```
3. **Install into Hermes' Python** (so the agent can import it):
   ```bash
   uv pip install --python ~/.hermes/hermes-agent/venv/bin/python3 -e .
   ```

---

## Configuration

The plugin relies on a centralized, server-side configuration manifest. No repository-local automation YAML is required.

**Default Configuration Path:**
```text
~/.agent-system/config/projects.yaml
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

## Remote Deployment

A deployment script (`scripts/deploy_remote.sh`) is included for syncing the plugin (and optionally other Hermes artifacts) to a remote machine via SSH/rsync.

### Prerequisites

* SSH public key authentication must be set up to the remote host.
* `rsync` and `python3` must be available on both local and remote machines.

### First Run

```bash
./scripts/deploy_remote.sh
```

Prompts for **username** and **hostname**, saves them to `~/.config/hermes-deploy/config.json` for future runs.

### Subsequent Runs

Uses saved config automatically:

```bash
# Sync plugin only (fastest)
./scripts/deploy_remote.sh --plugin-only

# Sync everything (plugin + skills + .env + full config)
./scripts/deploy_remote.sh --all

# Preview what would be synced
./scripts/deploy_remote.sh --dry-run
```

### CLI Reference

| Flag | Description |
|------|-------------|
| `-u, --user USER` | Override stored remote username |
| `-h, --host HOST` | Override stored remote hostname |
| `-p, --path PATH` | Remote hermes base path (default: `~/.hermes`) |
| `--plugin-only` | Sync plugin only, skip optional prompts |
| `--all` | Sync plugin + skills + .env + full config.yaml |
| `--dry-run` | Preview changes without executing |
| `--save-only` | Save/update remote config without syncing |
| `--help` | Show help text |

### What Gets Synced

**Always (plugin sync):**
* Project directory → `~/.hermes/plugins/portfolio-manager/` on remote
* Excludes: `.git`, `.venv`, `__pycache__`, caches, plans, progress/spec docs, logs, state
* Best-effort gateway restart on remote after sync

**Optional (interactive prompts unless `--all` or `--plugin-only`):**
* **Skills directory** — `~/.hermes/skills/` → remote
* **.env file** — `~/.hermes/.env` → remote
* **config.yaml selective** — parses sections, presents numbered list, merges only selected sections on remote (preserving existing remote config)

### Config Storage

Remote connection details stored at `~/.config/hermes-deploy/config.json`:

```json
{
  "username": "user",
  "host": "myserver.com",
  "remote_base": "~/.hermes"
}
```

See [the remote deployment plan](./plans/deploy-remote-script.md) for full details.

---

## Roadmap

The project grows through strict safety layers:

| MVP | Capability | Spec |
|---|---|---|
| 1 | Read-only portfolio visibility | [MVP 1 spec](./docs/mvps/mvp1-spec.md) |
| 2 | Project administration | [MVP 2 spec](./docs/mvps/mvp2-spec.md) |
| 3 | Issue creation and brainstorming | [MVP 3 progress](./docs/mvps/mvp3-progress.md) |
| 4 | Maintenance skills | [MVP 4 spec](./docs/mvps/mvp4-spec.md) |
| 5 | Worktree preparation | [MVP 5 spec](./docs/mvps/mvp5-spec.md), [progress](./docs/mvps/mvp5-progress.md) |
| 6 | Implementation harness orchestration | [MVP 6 spec](./docs/mvps/mvp6-spec.md) |
| 7 | Pull request and review ladder | [MVP 7 spec](./docs/mvps/mvp7-spec.md) |
| 8 | QA and merge readiness | [MVP 8 spec](./docs/mvps/mvp8-spec.md) |
| 9 | Operations, temporary overrides, and budget scheduling | [MVP 9 spec](./docs/mvps/mvp9-spec.md) |
| 10 | Constrained autonomy and auto-merge policy | [MVP 10 spec](./docs/mvps/mvp10-spec.md) |

See [the documentation index](./docs/README.md) and [audio-friendly product stories](./docs/product/user-stories.md) for the full staged roadmap.

---

## Documentation

Start with [docs/README.md](./docs/README.md). It indexes:

* product context and narrated user stories,
* MVP specs and progress plans,
* Hermes plugin API notes,
* active implementation plans,
* Hermes skill instructions.

The most important product docs are [project handoff](./docs/product/project-handoff.md), [user stories](./docs/product/user-stories.md), [MVP planning guide](./docs/mvps/planning-guide.md), and [progress authoring guide](./docs/mvps/progress-md-authoring-guide.md).

---

## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please refer to [`AGENTS.md`](./AGENTS.md) and [`docs/mvps/mvp1-spec.md`](./docs/mvps/mvp1-spec.md) for architectural guidelines and agent instructions.

---

## License

Distributed under the MIT License. See `pyproject.toml` or `plugin.yaml` for more information.
