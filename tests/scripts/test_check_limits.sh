#!/bin/bash
set -euo pipefail

# Test for check_limits.sh
# Portable: use CHECK_LIMITS_SCRIPT env var, fallback to absolute path.

CHECK_LIMITS_SCRIPT="${CHECK_LIMITS_SCRIPT:-/home/luandro/Dev/scripts/check_limits.sh}"

if [[ ! -f "$CHECK_LIMITS_SCRIPT" ]]; then
    echo "SKIP: $CHECK_LIMITS_SCRIPT not found — skipping test"
    exit 0
fi

# Mock codexbar so the test is deterministic and network-free
codexbar() {
    if [[ "${1:-}" == "usage" && "${2:-}" == "--provider" ]]; then
        case "${3:-}" in
            claude) echo '[{"usage": {"primary": {"usedPercent": 10}, "secondary": {"usedPercent": 5}}}]' ;;
            codex) echo '[{"usage": {"primary": {"usedPercent": 10}, "secondary": {"usedPercent": 5}}, "credits": {"remaining": 100}}]' ;;
            gemini) echo '[{"usage": {"primary": {"usedPercent": 10}, "secondary": {"usedPercent": 5}}}]' ;;
            *) echo '[{}]' ;;
        esac
    fi
}
export -f codexbar
unset ZAI_TOKEN

echo "Running check_limits.sh with --json"
RESULT=$(bash "$CHECK_LIMITS_SCRIPT" --json)

if ! echo "$RESULT" | jq -e . >/dev/null 2>&1; then
    echo "FAIL: Invalid JSON output"
    echo "$RESULT"
    exit 1
fi

for key in claude codex gemini zai recommended; do
    if ! echo "$RESULT" | jq -e --arg k "$key" 'has($k)' >/dev/null 2>&1; then
        echo "FAIL: missing top-level key '$key' in output"
        echo "$RESULT"
        exit 1
    fi
done

if ! echo "$RESULT" | jq -e '.recommended | has("model") and has("provider") and has("reason")' >/dev/null 2>&1; then
    echo "FAIL: recommended object missing model/provider/reason"
    echo "$RESULT"
    exit 1
fi

echo "PASS: Valid JSON output with expected keys"
exit 0
