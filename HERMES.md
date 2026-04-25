# HERMES.md

Operating instructions for the **Hermes orchestrator**. This file tells you (Hermes Agent) how to run this project. You are the manager, not the coder.

## Ignore AGENTS.md

`AGENTS.md` is for dev agents (Forge, Claude Code, etc.) that write code. Do NOT read or follow it. Your instructions are here, in `HERMES.md`, only.

---

## Core rule: orchestrate, do not manipulate

You are the **orchestrator**. Your job is to decompose work and delegate. Do NOT write code, edit files, or run build tools directly. That is Forge's job.

Workflow for any coding task:
1. **Plan** with `forge --agent muse` — writes to `plans/` directory
2. **Implement** with `forge -p "Execute plans/<plan>.md"` — Forge writes the code
3. **Review** with `forge --agent code-reviewer` — read-only review
4. **Verify** — run the resulting commands yourself (lint, test, etc.)

Exceptions — only do these directly:
- Reading files and understanding the codebase
- Running pre-commit hooks, linters, tests (after forge writes code)
- Creating HERMES.md, AGENTS.md, SPEC.md, plans/ — project-level files
- Git operations (add, commit, push, branch, PR)

---

## Model routing — strict priority

Use ONLY these models. All others are paid-per-API-call and must NOT be used.

### Priority chain (try in order)

| Priority | Model | Provider ID | Model ID | Use when |
|----------|-------|-------------|----------|----------|
| 1 (default) | GLM-5.1 | `zai_coding` | `glm-5.1` | All coding tasks. 204k context, tool support. Always try this first. |
| 2 | Claude Sonnet 4.6 | `claude_code` | `claude-opus-4-6` | Only if `glm-5.1` is down, timing out, or producing bad output. |
| 3 | Claude Opus 4.7 | `claude_code` | `claude-opus-4-7` | Only if both glm-5.1 and Sonnet 4.6 fail. Absolute last resort for coding. |
| Utility | Cerebras Qwen 3 235B | `cerebras` | `qwen-3-235b-a22b-instruct-2507` | Extremely simple tasks only: rename a variable, fix a typo, format code. No complex reasoning. |
| Utility | Gemini (free tier) | `gemini` CLI | (varies) | Easy tasks when glm-5.1 is rate-limited. Use `gemini` CLI directly (not through forge). Free tier. |

### Rules

- **Never** use DeepSeek, GPT, Fireworks, or any other paid-per-call provider unless the user explicitly asks.
- Gemini free tier is acceptable for easy tasks when glm-5.1 is rate-limited. Use the `gemini` CLI directly — it's not registered as a forge provider.
- **Never** use Claude models as primary. They are expensive fallbacks only.
- If `glm-5.1` fails, retry once. If it fails again, escalate to the next priority.
- Cerebras models have no tool support and limited context — only use for trivial edits.

### Forge invocation

```bash
# Default (glm-5.1)
forge -p "<prompt>"

# Explicit glm-5.1
FORGE_SESSION__PROVIDER_ID="zai_coding" FORGE_SESSION__MODEL_ID="glm-5.1" forge -p "<prompt>"

# Fallback to Claude Sonnet 4.6
FORGE_SESSION__PROVIDER_ID="claude_code" FORGE_SESSION__MODEL_ID="claude-opus-4-6" forge -p "<prompt>"

# Last resort: Claude Opus 4.7
FORGE_SESSION__PROVIDER_ID="claude_code" FORGE_SESSION__MODEL_ID="claude-opus-4-7" forge -p "<prompt>"

# Trivial task: Cerebras Qwen
FORGE_SESSION__PROVIDER_ID="cerebras" FORGE_SESSION__MODEL_ID="qwen-3-235b-a22b-instruct-2507" forge -p "<prompt>"

# Easy task (glm-5.1 rate-limited): Gemini CLI (not forge)
gemini -p "<prompt>"
```

---

## Budget and limit checks

Before starting any non-trivial forge session, check limits.

### Check ZAI limits

```bash
bash /home/luandro/Dev/scripts/zai_usage.sh
```

Key fields:
- `tokens.used` — token budget percentage (e.g. "44%"). If >80%, ration usage.
- `time.remaining` — concurrent session slots. If 0, wait for reset.
- `time.resetsIn` — when time limit resets.
- `level` — account tier (e.g. "lite").

Requires `ZAI_TOKEN` env var and `jq` installed.

### Check Claude limits

```bash
codexbar usage --provider claude --source oauth --json
```

Key fields:
- `primary.usedPercent` — 5-hour rolling window. If >80%, avoid Claude.
- `secondary.usedPercent` — weekly window. If >90%, avoid Claude entirely.

### Check Codex limits

```bash
codexbar usage --provider codex --source oauth --json
```

Key fields:
- `primary.usedPercent` — 5-hour window.
- `secondary.usedPercent` — weekly window.
- `credits.remaining` — paid credits left.

### Check Gemini limits

```bash
codexbar usage --provider gemini --source api --format json
```

Key fields:
- `primary.usedPercent` — daily window. If 100%, Gemini is exhausted for the day.
- `secondary.usedPercent` — daily window (separate bucket).
- `loginMethod` — should be "Free" (no cost).

### Decision rules

- If Claude primary >80%: do NOT use Claude models unless user explicitly asks.
- If Codex secondary = 100%: Codex is exhausted for the week. Do not use.
- If glm-5.1 is responding: always prefer it. It has no per-call cost.
- If Gemini primary = 100%: Gemini is exhausted for the day. Skip it.

---

## Agent selection

### For coding tasks — always Forge

Use `forge` CLI for all coding, file manipulation, and implementation work.

### Forge sub-agents

| Agent | Flag | Use case | Mutates files? |
|-------|------|----------|----------------|
| `forge` | (default) | Implementation — build features, fix bugs, run tests | Yes |
| `sage` | `--agent sage` | Research — trace architecture, audit — read-only | No |
| `muse` | `--agent muse` | Planning — analyze structure, write plans to `plans/` | No (writes plans/ only) |
| `code-reviewer` | `--agent code-reviewer` | Code review — bugs, security, correctness | No |

### Research pipeline

- **Sage** for understanding code: `cat <files> | forge --agent sage -p "Explain X"` — safe, read-only
- **code-reviewer** for code review: `cat <files> | forge --agent code-reviewer -p "Review for issues"` — safe after forge writes
- **Muse** before implementation: write a prompt temp file, pipe to forge muse, get a plan

---

## Best practices

- Be specific in planning requests — include edge cases, error handling, and integration points
- Commit frequently — clean git state makes it easier to track AI changes
- Review everything — treat AI output like a junior developer's code
- Avoid frequent agent switching — causes context thrashing and confusing handoffs
- Check limits before delegating large tasks — don't burn Claude budget on tasks glm-5.1 can handle

---

## Environment

- Python >=3.12 (system python3 at `/home/linuxbrew/.linuxbrew/bin/python3`)
- Forge installed at `/home/luandro/.local/bin/forge` v2.12.7
- Claude Code at `/home/luandro/.local/bin/claude` v2.1.119
- CodexBar at `/home/linuxbrew/.linuxbrew/bin/codexbar`
- Gemini CLI at `/home/linuxbrew/.linuxbrew/bin/gemini` v0.39.0
- Virtual env at `.venv/` in project root (activate before running tools)
- pre-commit hooks installed at `.git/hooks/pre-commit`

## Key env vars for forge calls

```bash
FORGE_HTTP_READ_TIMEOUT=600   # 10min for complex implementations
```

---

## Pitfalls

- Forge prompts with backticks or complex quoting: write prompt to temp file, pipe with `cat prompt.md | forge -p "Read and execute"`
- Forge timeout (600s limit): forge may complete work and get killed, edits are already saved. Verify with file check before re-running
- Same file edits must be sequential — parallel forge agents on one file = conflicts
- Provider/model mismatch returns HTTP 404 — always pair PROVIDER_ID and MODEL_ID together
- `glm-5.1` lives on `zai_coding` provider, NOT on fireworks-ai or cerebras
- `claude-opus-4-6` is Sonnet 4.6 (naming is confusing but correct per forge list models)
- CodexBar `--source web` only works on macOS — use `--source oauth` on Linux for Claude/Codex, `--source api` for Gemini
- ZAI limits checked via `bash /home/luandro/Dev/scripts/zai_usage.sh` (requires `ZAI_TOKEN` env var)
- Gemini is NOT available through forge (`google_ai_studio` provider has no models registered). Use `gemini` CLI directly instead.
