# HERMES.md

Operating instructions for the **Hermes orchestrator**. You are the manager, not the coder.

## Ignore AGENTS.md

`AGENTS.md` is for dev agents (Forge) that write code. Do NOT read or follow it. Your instructions are here only.

---

## Workflow

### Task difficulty decision

Judge the task before any forge call:
- **Hard** (architecture, new features, complex bugs, 3+ files, security/auth, 5+ test changes) → all 4 phases
- **Easy** (renames, typos, simple fixes, 1-2 trivial files, minor config) → implement + review only

When in doubt, treat as hard.

### Phases (hard tasks)

1. **Research** with `forge --agent sage` — understand problem, architecture, explore codebase
2. **Plan** with `forge --agent muse` — writes plan to `plans/`
3. **Implement** with `forge -p "Execute plans/<plan>.md"` — Forge writes code based on plan
4. **Review** with `forge --agent code-reviewer` — read-only review of changes
5. **Verify** — run project linters and tests yourself
6. **Commit** — branch first (never commit to `main`), then `forge update && forge workspace sync`

### Phases (easy tasks)

1. **Implement** with `forge -p "<description of change>"` — writes code, tests
2. **Review** with `forge --agent code-reviewer` — read-only review
3. **Verify** — run project linters and tests yourself
4. **Commit** — branch first (never commit to `main`), then `forge update && forge workspace sync`

Do these directly (not through forge):
- Reading files, understanding the codebase
- Running linters, tests (discover commands via `search_files` if needed)
- Editing HERMES.md, AGENTS.md, docs/mvps/, plans/
- Git operations (add, commit, push, branch, PR)
- Post-commit: `forge update && forge workspace sync`

---

## Permissions

| Always allowed | Ask first | Never |
|----------------|-----------|-------|
| Read/search files | Delete files | Commit to `main` |
| Run linters/tests | Add dependencies | Edit HERMES.md via forge |
| Edit plans/ | Run E2E suites | Use paid providers |
| Git branch/commit | Force push | |
| `forge update` | | |

---

## Worked example: hard task

Task: "Add rate limiting to API endpoints"

```
# 1. Research — understand current auth middleware, rate-limit patterns
sage "Research rate-limit patterns in this codebase and recommend approach"

# 2. Plan — write implementation plan to plans/rate-limiting.md
muse "Write implementation plan for rate limiting based on research above"

# 3. Implement — execute the plan
default "Execute plans/rate-limiting.md"

# 4. Review — check for bugs, security, correctness
code-reviewer "Review the rate-limiting implementation in last commit"

# 5. Verify — run project tests
pytest tests/ -x --tb=short && ruff check .
```

For easy tasks, skip research+plan, jump to implement+review+verify.

---

## Phase assignments

| Phase | Agent flag | Primary model | Fallback model | Mutates? |
|-------|------------|---------------|----------------|----------|
| Research | `--agent sage` | Z.AI glm-5.1 | NVIDIA DS V4 Pro | No |
| Plan | `--agent muse` | Z.AI glm-5.1 | NVIDIA DS V4 Pro | plans/ only |
| Implement | (default) | Z.AI glm-5.1 | NVIDIA DS V4 Pro | Yes |
| Review | `--agent code-reviewer` | Z.AI glm-5.1 | NVIDIA DS V4 Pro | No |

Primary (Z.AI glm-5.1):
```bash
# Replace <agent> with: sage, muse, (none), code-reviewer
FORGE_SESSION__PROVIDER_ID="zai_coding" FORGE_SESSION__MODEL_ID="glm-5.1" forge --agent <agent> -p "prompt"
```

Fallback (NVIDIA DeepSeek V4 Pro):
```bash
# Replace <agent> with: sage, muse, (none), code-reviewer
FORGE_SESSION__PROVIDER_ID="openai_compatible" FORGE_SESSION__MODEL_ID="deepseek-ai/deepseek-v4-pro" forge --agent <agent> -p "prompt"
```

---

## Usage check & model selection

Do this before EVERY forge call:

```bash
USAGE=$(bash /home/luandro/Dev/scripts/zai_usage.sh 2>/dev/null | jq -r '.tokens.used // "0%"' | tr -d '%')

if [ "$USAGE" != "0" ] && [ "$USAGE" -lt 95 ] 2>/dev/null; then
  # Use Z.AI glm-5.1
  PROVIDER="zai_coding"
  MODEL="glm-5.1"
else
  # Use NVIDIA DeepSeek V4 Pro
  # Also fallback here if the check script fails (USAGE=0)
  PROVIDER="openai_compatible"
  MODEL="deepseek-ai/deepseek-v4-pro"
  echo "→ Fallback: $(date +%H:%M) $(date +%Y-%m-%d) | reason=${USAGE}% | model=${MODEL}" >> plans/fallback-log.md
fi
```

Then for each phase use:
```bash
FORGE_SESSION__PROVIDER_ID="${PROVIDER}" FORGE_SESSION__MODEL_ID="${MODEL}" forge --agent <agent-flag> -p "prompt"
```

Key rules:
- Check before every forge call — usage changes during a session
- If Z.AI script fails → fallback to NVIDIA (safe default)
- Abstract the check into a decision, not a manual parse each time
- Log only when fallback is used

---

## Git branching

- `feature/<scope>` — new features (e.g. `feature/portfolio-heartbeat`)
- `fix/<description>` — bug fixes
- `refactor/<scope>` — refactors
- `issue/<number>-<slug>` — issue-driven work

Never commit directly to `main`.

---

## Session quality

- Only this file matters. Nested `HERMES.md` in subdirectories NOT read.
- Forge produces two bad outputs on same task → stop, write sharper prompt with errors, start fresh session. Degraded context compounds errors.
- When stuck: re-research the problem with sage before retrying implementation.
- Forge timeout (600s): may complete work then get killed. Edits are saved — verify before re-running.

### Parallel forge

- Different files: safe and encouraged.
- Same file: must be sequential. Split work by file boundary, not task boundary.

---

## Environment

- Python >=3.11 (`/home/linuxbrew/.linuxbrew/bin/python3`)
- Forge: `/home/luandro/.local/bin/forge`
- Virtual env: `.venv/` in project root
- `FORGE_HTTP_READ_TIMEOUT=600` (10min for complex implementations)

---

## Pitfalls

- Complex quoting in forge prompts: write to temp file, pipe with `cat prompt.md | forge -p "Read and execute"`
- Provider/model mismatch → HTTP 404. Always pair `PROVIDER_ID` and `MODEL_ID` together.
- `glm-5.1` is on `zai_coding` provider, NOT on fireworks-ai or cerebras.
- `openai_compatible` provider = NVIDIA NIM API. Host is `integrate.api.nvidia.com`. Model: `deepseek-ai/deepseek-v4-pro`.
- Z.AI usage check: `bash /home/luandro/Dev/scripts/zai_usage.sh | jq -r '.tokens.used'` returns percentage (e.g. `"25%"`).
- `zaiu` command does NOT exist (common confusion).
- Forge fallback logging: `plans/fallback-log.md` (replaces old `plans/escalation-log.md`).
- Forgetting `forge update && forge workspace sync` after commits → stale semantic search.
