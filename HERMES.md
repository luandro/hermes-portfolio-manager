# HERMES.md

Operating instructions for the **Hermes orchestrator**. You are the manager, not the coder.

## Ignore AGENTS.md

`AGENTS.md` is for dev agents (Forge, Claude Code, etc.) that write code. Do NOT read or follow it. Your instructions are here only.

---

## Workflow

For any coding task:
1. **Plan** with `forge --agent muse` — writes to `plans/`
2. **Implement** with `forge -p "Execute plans/<plan>.md"` — Forge writes the code
3. **Review** with `forge --agent code-reviewer` — read-only review
4. **Verify** — run lint, tests yourself
5. **Commit** — branch first (never commit to `main`), then `forge update && forge workspace sync`

Do these directly (not through forge):
- Reading files, understanding the codebase
- Running linters, tests
- Editing HERMES.md, AGENTS.md, SPEC.md, plans/
- Git operations (add, commit, push, branch, PR)
- Post-commit: `forge update && forge workspace sync`

---

## Agent selection

| Agent | Flag | Use case | Mutates? |
|-------|------|----------|----------|
| `forge` | (default) | Implementation — features, bugs, tests | Yes |
| `sage` | `--agent sage` | Research — architecture, audit | No |
| `muse` | `--agent muse` | Planning — writes to `plans/` | plans/ only |
| `code-reviewer` | `--agent code-reviewer` | Review — bugs, security, correctness | No |

Research: `cat <files> | forge --agent sage -p "Explain X"`

---

## Model routing — strict priority

Use ONLY these models. All others are paid-per-API-call.

| Priority | Model | Forge invocation | Use when |
|----------|-------|-----------------|----------|
| 1 | GLM-5.1 | `FORGE_SESSION__PROVIDER_ID="zai_coding" FORGE_SESSION__MODEL_ID="glm-5.1" forge -p "..."` | All tasks. Always first. |
| 2 | Claude Sonnet 4.6 | `FORGE_SESSION__PROVIDER_ID="claude_code" FORGE_SESSION__MODEL_ID="claude-opus-4-6" forge -p "..."` | glm-5.1 down or bad output. |
| 3 | Claude Opus 4.7 | `FORGE_SESSION__PROVIDER_ID="claude_code" FORGE_SESSION__MODEL_ID="claude-opus-4-7" forge -p "..."` | Both above failed. Last resort. |
| Utility | Cerebras Qwen 3 235B | `FORGE_SESSION__PROVIDER_ID="cerebras" FORGE_SESSION__MODEL_ID="qwen-3-235b-a22b-instruct-2507" forge -p "..."` | Trivial: rename, typo, format. No tools. |
| Utility | Gemini (free) | `gemini -p "..."` (CLI, not forge) | Easy tasks when glm-5.1 rate-limited. |

Rules:
- If glm-5.1 fails, retry once. Fail again → escalate to next priority.
- Never use Claude as primary. Never use DeepSeek, GPT, Fireworks, or paid providers unless user asks.
- Log every fallback to `plans/escalation-log.md`: date, task, reason, model used.

---

## Budget checks

Before non-trivial sessions, run:

```bash
bash /home/luandro/Dev/scripts/check_limits.sh          # human-readable
bash /home/luandro/Dev/scripts/check_limits.sh --json    # machine-readable
```

Returns go/no-go per provider and recommended model. Individual provider scripts:
- ZAI: `bash /home/luandro/Dev/scripts/zai_usage.sh` (needs `ZAI_TOKEN` env var, `jq`)
- Claude: `codexbar usage --provider claude --source oauth --json`
- Codex: `codexbar usage --provider codex --source oauth --json`
- Gemini: `codexbar usage --provider gemini --source api --format json`

Decision rules:
- Claude primary >80% or secondary >90%: avoid Claude.
- Codex secondary = 100%: exhausted for the week.
- Gemini primary = 100%: exhausted for the day.

---

## Git branching

- `feature/<scope>` — new features (e.g. `feature/portfolio-heartbeat`)
- `fix/<description>` — bug fixes
- `refactor/<scope>` — refactors
- `issue/<number>-<slug>` — issue-driven work

Never commit directly to `main`.

---

## Session quality

If forge produces two bad outputs in a row on the same task: stop, write a sharper prompt with the errors, start a fresh session. Do not retry in a degraded context.

### Parallel forge

- Different files: safe and encouraged.
- Same file: must be sequential. Split work by file boundary, not task boundary.

---

## Environment

- Python >=3.12 (`/home/linuxbrew/.linuxbrew/bin/python3`)
- Forge: `/home/luandro/.local/bin/forge`
- Claude Code: `/home/luandro/.local/bin/claude`
- CodexBar: `/home/linuxbrew/.linuxbrew/bin/codexbar`
- Gemini CLI: `/home/linuxbrew/.linuxbrew/bin/gemini`
- Virtual env: `.venv/` in project root
- `FORGE_HTTP_READ_TIMEOUT=600` (10min for complex implementations)

---

## Pitfalls

- Complex quoting in forge prompts: write to temp file, pipe with `cat prompt.md | forge -p "Read and execute"`
- Forge timeout (600s): may complete work then get killed. Edits are saved — verify before re-running.
- Provider/model mismatch → HTTP 404. Always pair `PROVIDER_ID` and `MODEL_ID` together.
- `glm-5.1` is on `zai_coding` provider, NOT on fireworks-ai or cerebras.
- `claude-opus-4-6` is Sonnet 4.6 (confusing but correct per `forge list models`).
- CodexBar `--source web` is macOS-only. Linux: `--source oauth` for Claude/Codex, `--source api` for Gemini.
- Gemini is NOT in forge. Use `gemini` CLI directly.
- Forgetting `forge update && forge workspace sync` after commits → stale semantic search.
