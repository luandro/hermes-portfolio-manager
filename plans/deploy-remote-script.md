# Deploy Remote Script — Implementation Plan

## Goal
Create `scripts/deploy_remote.sh` — a bash script that syncs the portfolio-manager plugin (and optionally other hermes artifacts) to a remote machine via SSH/rsync.

## Location
`scripts/deploy_remote.sh` in the project root. Make executable (`chmod +x`).

## Requirements

### 1. Config storage
- Store remote config in `~/.config/hermes-deploy/config.json`
- Fields: `username`, `host`, `remote_base` (default: `~/.hermes`)
- If config exists, use stored values (with option to override via flags)
- If no config, prompt interactively for username and host

### 2. SSH key check
- Verify SSH key is set up: `ssh -o BatchMode=yes -o ConnectTimeout=5 ${username}@${host} 'echo ok'`
- If fails, print clear error about SSH key setup and exit

### 3. Plugin sync (always)
- Source: current project directory (where script lives, resolved via `SCRIPT_DIR`)
- Target: `${remote_base}/plugins/portfolio-manager/` on remote
- Use rsync with `--exclude` for: `.git/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `worktrees/`, `plans/`, `PROGRESS*.md`, `SPEC*.md`, `artifacts/`, `logs/`, `state/`
- After rsync, restart hermes gateway on remote: `ssh ... 'hermes gateway restart'` (best-effort, don't fail if gateway not running)

### 4. Optional additional syncs (interactive prompts)
After plugin sync, ask the user:

**a) Skills directory**
- Prompt: "Sync skills directory? [y/N]"
- If yes: rsync `~/.hermes/skills/` to `${remote_base}/skills/` on remote

**b) Environment file**
- Prompt: "Sync .env file? [y/N]"
- If yes: rsync `~/.hermes/.env` to `${remote_base}/.env` on remote

**c) Config.yaml selective copy**
- Prompt: "Sync config.yaml (selective)? [y/N]"
- If yes:
  - Parse `~/.hermes/config.yaml` locally using python (or yq if available, fallback to python)
  - Extract top-level section names
  - Present numbered list of sections (e.g., `1) model  2) terminal  3) gateway  4) agent  5) ...`)
  - User selects which sections to copy (e.g., "1 3 4" or "all")
  - Build a temporary yaml with only selected sections
  - On remote: read existing config, merge selected sections (preserve others), write back
  - Use python for yaml merge to avoid yq dependency issues

### 5. CLI flags
```
./deploy_remote.sh [OPTIONS]

Options:
  -u, --user USER       Remote username (overrides stored config)
  -h, --host HOST       Remote hostname (overrides stored config)
  -p, --path PATH       Remote hermes base path (default: ~/.hermes)
  --plugin-only         Only sync plugin, skip optional prompts
  --all                 Sync everything (skills + .env + full config)
  --dry-run             Show what would be synced without doing it
  --save-only           Just save/update remote config without syncing
  --help                Show help
```

### 6. Output
- Colored output (green=success, yellow=warning, red=error, blue=info)
- Summary at end: what was synced, where, and any warnings

### 7. Error handling
- Exit on SSH failure
- Exit on rsync error (non-zero)
- Trap errors with `set -euo pipefail`
- Cleanup temp files on exit

## Implementation notes
- Pure bash + python for yaml parsing (python3 is guaranteed on hermes machines)
- No external dependencies beyond rsync and ssh
- Config dir: `~/.config/hermes-deploy/` — create if not exists
- Remote base path: default `~/.hermes`, allow override
