#!/usr/bin/env bash
# deploy_remote.sh — Sync portfolio-manager plugin (and optionally other hermes artifacts) to a remote machine.
set -euo pipefail

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLUGIN_NAME="portfolio-manager"
CONFIG_DIR="${HOME}/.config/hermes-deploy"
CONFIG_FILE="${CONFIG_DIR}/config.json"

# --- Defaults ---
REMOTE_BASE_DEFAULT="~/.hermes"

# --- Temp file tracking for cleanup ---
TEMP_FILES=()
cleanup() {
    for f in "${TEMP_FILES[@]:-}"; do
        [[ -f "${f}" ]] && rm -f "${f}"
    done
}
trap cleanup EXIT

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# --- CLI defaults ---
OPT_USER=""
OPT_HOST=""
OPT_PATH=""
OPT_PLUGIN_ONLY=false
OPT_ALL=false
OPT_DRY_RUN=false
OPT_SAVE_ONLY=false

# --- Usage ---
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Sync the ${PLUGIN_NAME} plugin to a remote Hermes instance via SSH/rsync.

Options:
  -u, --user USER       Remote username (overrides stored config)
  -h, --host HOST       Remote hostname (overrides stored config)
  -p, --path PATH       Remote hermes base path (default: ~/.hermes)
  --plugin-only         Only sync plugin, skip optional prompts
  --all                 Sync everything (skills + .env + full config)
  --dry-run             Show what would be synced without doing it
  --save-only           Just save/update remote config without syncing
  --help                Show this help
EOF
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--user)   OPT_USER="$2";   shift 2 ;;
        -h|--host)   OPT_HOST="$2";   shift 2 ;;
        -p|--path)   OPT_PATH="$2";   shift 2 ;;
        --plugin-only) OPT_PLUGIN_ONLY=true; shift ;;
        --all)       OPT_ALL=true;    shift ;;
        --dry-run)   OPT_DRY_RUN=true; shift ;;
        --save-only) OPT_SAVE_ONLY=true; shift ;;
        --help)      usage ;;
        *)
            err "Unknown option: $1"
            usage
            ;;
    esac
done

# --- Config helpers ---
ensure_config_dir() {
    mkdir -p "${CONFIG_DIR}"
}

load_config() {
    if [[ -f "${CONFIG_FILE}" ]]; then
        CONFIG_USERNAME=$(CONFIG_FILE="${CONFIG_FILE}" python3 -c 'import json, os; d=json.load(open(os.environ["CONFIG_FILE"])); print(d.get("username",""))')
        CONFIG_HOST=$(CONFIG_FILE="${CONFIG_FILE}" python3 -c 'import json, os; d=json.load(open(os.environ["CONFIG_FILE"])); print(d.get("host",""))')
        CONFIG_REMOTE_BASE=$(CONFIG_FILE="${CONFIG_FILE}" REMOTE_BASE_DEFAULT="${REMOTE_BASE_DEFAULT}" python3 -c 'import json, os; d=json.load(open(os.environ["CONFIG_FILE"])); print(d.get("remote_base",os.environ.get("REMOTE_BASE_DEFAULT","~/.hermes")))')
    else
        CONFIG_USERNAME=""
        CONFIG_HOST=""
        CONFIG_REMOTE_BASE="${REMOTE_BASE_DEFAULT}"
    fi
}

save_config() {
    ensure_config_dir
    CONFIG_FILE="${CONFIG_FILE}" SAVE_USER="${SAVE_USER}" SAVE_HOST="${SAVE_HOST}" SAVE_REMOTE_BASE="${SAVE_REMOTE_BASE}" \
    python3 - <<'PY'
import json, os, pathlib
pathlib.Path(os.environ["CONFIG_FILE"]).write_text(json.dumps({
    "username": os.environ["SAVE_USER"],
    "host": os.environ["SAVE_HOST"],
    "remote_base": os.environ["SAVE_REMOTE_BASE"],
}, indent=2) + "\n")
PY
    ok "Config saved to ${CONFIG_FILE}"
}

prompt_if_empty() {
    local varname="$1" prompt_text="$2"
    local -n ref="${varname}"
    if [[ -z "${ref}" ]]; then
        read -rp "${prompt_text}: " ref
        if [[ -z "${ref}" ]]; then
            err "${varname} is required."
            exit 1
        fi
    fi
}

# --- Resolve effective values ---
resolve_config() {
    load_config

    REMOTE_USER="${OPT_USER:-${CONFIG_USERNAME}}"
    REMOTE_HOST="${OPT_HOST:-${CONFIG_HOST}}"
    REMOTE_BASE="${OPT_PATH:-${CONFIG_REMOTE_BASE}}"
    # Normalize: expand $HOME or ${HOME} to ~ for rsync compatibility
    # rsync does NOT expand $HOME on remote, but DOES expand ~
    REMOTE_BASE="${REMOTE_BASE//\$HOME/~}"
    REMOTE_BASE="${REMOTE_BASE//\$\{HOME\}/~}"
    # If path doesn't start with ~ or /, treat as relative to home
    if [[ "${REMOTE_BASE}" != ~* && "${REMOTE_BASE}" != /* ]]; then
        REMOTE_BASE="~/${REMOTE_BASE}"
    fi
    # Default if still empty
    REMOTE_BASE="${REMOTE_BASE:-${REMOTE_BASE_DEFAULT}}"

    prompt_if_empty REMOTE_USER "Enter remote username"
    prompt_if_empty REMOTE_HOST "Enter remote hostname"

    # Store for save_config
    SAVE_USER="${REMOTE_USER}"
    SAVE_HOST="${REMOTE_HOST}"
    SAVE_REMOTE_BASE="${REMOTE_BASE}"
}

# --- SSH check ---
check_ssh() {
    info "Checking SSH connectivity to ${REMOTE_USER}@${REMOTE_HOST}..."
    if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "${REMOTE_USER}@${REMOTE_HOST}" 'echo ok' >/dev/null 2>&1; then
        err "SSH key authentication failed for ${REMOTE_USER}@${REMOTE_HOST}."
        err "Ensure your SSH key is authorized on the remote host."
        err "Run: ssh-copy-id ${REMOTE_USER}@${REMOTE_HOST}"
        exit 1
    fi
    ok "SSH connection verified."
}

# --- Rsync helpers ---
RSYNC_EXCLUDES=(
    --exclude='.git/'
    --exclude='.venv/'
    --exclude='__pycache__/'
    --exclude='*.pyc'
    --exclude='.pytest_cache/'
    --exclude='.ruff_cache/'
    --exclude='.mypy_cache/'
    --exclude='worktrees/'
    --exclude='plans/'
    --exclude='PROGRESS*.md'
    --exclude='SPEC*.md'
    --exclude='artifacts/'
    --exclude='logs/'
    --exclude='state/'
)

rsync_cmd() {
    local src="$1" dest="$2"
    shift 2
    if [[ "${OPT_DRY_RUN}" == true ]]; then
        rsync -avzn --itemize-changes "${RSYNC_EXCLUDES[@]}" "$@" "${src}" "${dest}"
    else
        rsync -az "${RSYNC_EXCLUDES[@]}" "$@" "${src}" "${dest}"
    fi
}

# --- Plugin sync ---
sync_plugin() {
    local remote_target="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/plugins/${PLUGIN_NAME}/"
    info "Syncing plugin to ${remote_target}..."
    rsync_cmd "${PROJECT_DIR}/" "${remote_target}"
    ok "Plugin synced."

    # Restart gateway (best-effort)
    info "Restarting hermes gateway on remote (best-effort)..."
    if [[ "${OPT_DRY_RUN}" == true ]]; then
        info "[dry-run] Would run: ssh ${REMOTE_USER}@${REMOTE_HOST} 'hermes gateway restart'"
    else
        if ssh "${REMOTE_USER}@${REMOTE_HOST}" 'hermes gateway restart' 2>/dev/null; then
            ok "Gateway restarted."
        else
            warn "Gateway restart skipped (not running or not installed)."
        fi
    fi
}

# --- Skills sync ---
sync_skills() {
    local local_skills="${HOME}/.hermes/skills/"
    local remote_target="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/skills/"
    if [[ ! -d "${local_skills}" ]]; then
        warn "Local skills directory not found at ${local_skills}. Skipping."
        return
    fi
    info "Syncing skills directory..."
    rsync_cmd "${local_skills}" "${remote_target}"
    ok "Skills synced."
}

# --- .env sync ---
sync_env() {
    local local_env="${HOME}/.hermes/.env"
    local remote_target="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/.env"
    if [[ ! -f "${local_env}" ]]; then
        warn "Local .env file not found at ${local_env}. Skipping."
        return
    fi
    info "Syncing .env file..."
    rsync_cmd "${local_env}" "${remote_target}"
    ok ".env synced."
}

# --- Config.yaml selective sync ---
sync_config_selective() {
    local local_config="${HOME}/.hermes/config.yaml"
    if [[ ! -f "${local_config}" ]]; then
        warn "Local config.yaml not found at ${local_config}. Skipping."
        return
    fi

    # Extract section names
    local sections
    sections=$(LOCAL_CONFIG="${local_config}" python3 -c '
import yaml, sys, os
with open(os.environ["LOCAL_CONFIG"]) as f:
    data = yaml.safe_load(f)
if not isinstance(data, dict):
    sys.exit(1)
for i, key in enumerate(data.keys(), 1):
    print(f"{i}) {key}")
')
    if [[ -z "${sections}" ]]; then
        warn "No sections found in config.yaml."
        return
    fi

    echo -e "${BLUE}Sections in config.yaml:${NC}"
    echo "${sections}"
    read -rp "Select sections to sync (e.g., '1 3 4' or 'all'): " selection

    local temp_local
    temp_local=$(mktemp)
    TEMP_FILES+=("${temp_local}")

    if [[ "${selection}" == "all" ]]; then
        cp "${local_config}" "${temp_local}"
    else
        # Build yaml with only selected sections
        LOCAL_CONFIG="${local_config}" SELECTION="${selection}" TEMP_LOCAL="${temp_local}" python3 -c '
import yaml, sys, os
with open(os.environ["LOCAL_CONFIG"]) as f:
    data = yaml.safe_load(f)
keys = list(data.keys())
selected = []
for part in os.environ["SELECTION"].split():
    try:
        idx = int(part) - 1
        if 0 <= idx < len(keys):
            selected.append(keys[idx])
    except ValueError:
        pass
subset = {k: data[k] for k in selected if k in data}
with open(os.environ["TEMP_LOCAL"], "w") as f:
    yaml.dump(subset, f, default_flow_style=False)
'
    fi

    info "Merging selected config sections on remote..."
    if [[ "${OPT_DRY_RUN}" == true ]]; then
        info "[dry-run] Would merge config sections to ${REMOTE_BASE}/config.yaml"
        info "Selected sections:"
        TEMP_LOCAL="${temp_local}" python3 -c '
import yaml, os
with open(os.environ["TEMP_LOCAL"]) as f:
    data = yaml.safe_load(f)
for k in (data or {}):
    print(f"  - {k}")
'
        return
    fi

    # Upload temp file, merge on remote via python
    local temp_remote="/tmp/hermes-config-merge-$$.yaml"
    scp -q "${temp_local}" "${REMOTE_USER}@${REMOTE_HOST}:${temp_remote}"

    ssh "${REMOTE_USER}@${REMOTE_HOST}" python3 -s - "${REMOTE_BASE}" "${temp_remote}" <<'PYEOF'
import yaml, os, sys

remote_base = os.path.expanduser(sys.argv[1])
remote_config = os.path.join(remote_base, "config.yaml")
temp_file = sys.argv[2]

try:
    os.chmod(temp_file, 0o600)

    # Load existing remote config
    existing = {}
    if os.path.isfile(remote_config):
        with open(remote_config) as f:
            existing = yaml.safe_load(f) or {}

    # Load incoming sections
    with open(temp_file) as f:
        incoming = yaml.safe_load(f) or {}

    # Merge (incoming overwrites existing keys)
    existing.update(incoming)

    # Write back
    with open(remote_config, "w") as f:
        yaml.dump(existing, f, default_flow_style=False)

    print("Config merged successfully.")
finally:
    try:
        os.remove(temp_file)
    except OSError:
        pass
PYEOF

    ok "Config synced and merged."
}

# --- Prompt helper ---
ask_yes_no() {
    local prompt="$1"
    local response
    read -rp "${prompt} [y/N] " response
    [[ "${response}" =~ ^[Yy]$ ]]
}

# --- Summary ---
print_summary() {
    echo ""
    echo -e "${GREEN}=== Deployment Summary ===${NC}"
    echo -e "  Remote: ${REMOTE_USER}@${REMOTE_HOST}"
    echo -e "  Base:   ${REMOTE_BASE}"
    echo -e "  Plugin: ${GREEN}synced${NC}"
    if [[ "${SYNCED_SKILLS:-}" == true ]]; then
        echo -e "  Skills: ${GREEN}synced${NC}"
    fi
    if [[ "${SYNCED_ENV:-}" == true ]]; then
        echo -e "  .env:   ${GREEN}synced${NC}"
    fi
    if [[ "${SYNCED_CONFIG:-}" == true ]]; then
        echo -e "  Config: ${GREEN}synced${NC}"
    fi
    if [[ "${OPT_DRY_RUN}" == true ]]; then
        echo -e "  ${YELLOW}(dry-run mode — nothing was actually changed)${NC}"
    fi
    echo ""
}

# ============================
# Main
# ============================
main() {
    resolve_config

    # Save config on first use or when flags override
    if [[ "${OPT_DRY_RUN}" != true ]] && { [[ ! -f "${CONFIG_FILE}" ]] || [[ -n "${OPT_USER}" ]] || [[ -n "${OPT_HOST}" ]]; }; then
        save_config
    fi

    if [[ "${OPT_SAVE_ONLY}" == true ]]; then
        ok "Config saved. Exiting (--save-only)."
        exit 0
    fi

    check_ssh
    sync_plugin

    if [[ "${OPT_PLUGIN_ONLY}" == true ]]; then
        print_summary
        exit 0
    fi

    if [[ "${OPT_ALL}" == true ]]; then
        sync_skills;   SYNCED_SKILLS=true
        sync_env;      SYNCED_ENV=true
        # For --all, sync full config
        local local_config="${HOME}/.hermes/config.yaml"
        if [[ -f "${local_config}" ]]; then
            local remote_target="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BASE}/config.yaml"
            info "Syncing full config.yaml..."
            rsync_cmd "${local_config}" "${remote_target}"
            ok "Full config synced."
            SYNCED_CONFIG=true
        else
            warn "Local config.yaml not found. Skipping."
        fi
        print_summary
        exit 0
    fi

    # Interactive prompts
    if ask_yes_no "Sync skills directory?"; then
        sync_skills; SYNCED_SKILLS=true
    fi
    if ask_yes_no "Sync .env file?"; then
        sync_env; SYNCED_ENV=true
    fi
    if ask_yes_no "Sync config.yaml (selective)?"; then
        sync_config_selective; SYNCED_CONFIG=true
    fi

    print_summary
}

main "$@"
