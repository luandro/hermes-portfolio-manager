# Progress.md Authoring Guide — Implementation Planning for Tiered Agents

## Purpose

This guide tells you how to turn an MVP **spec** into an MVP **progress.md** — an implementation plan that a less-capable ("dumber") coding agent can execute one task at a time, and that an orchestrator can route across model tiers (haiku / sonnet / opus) by reading a single difficulty marker per task.

Use this together with:

```txt
docs/mvps/planning-guide.md          (how to write the spec itself)
docs/product/project-handoff.md      (system context, roadmap, do-not-break list)
docs/mvps/mvp4-progress.md           (canonical example — large, security-sensitive)
docs/mvps/mvp5-progress.md           (canonical example — adds difficulty tiers)
```

A spec answers *what* and *why*. A progress.md answers *in what order, with what tests, and at what model cost*.

---

## When to Write One

Write a progress.md when **all** of these are true:

```txt
The spec is stable (acceptance criteria + non-goals listed).
The MVP touches more than ~3 modules OR introduces a security boundary.
You expect to hand work to a different session, agent, or person.
```

Skip it for:

```txt
Single-file refactors.
Bug fixes with one obvious failing test.
Doc-only changes.
```

For those, write the test, fix, commit. Don't ceremony.

---

## The Three Audiences

Every line in progress.md is read by one of three audiences. If a line serves none of them, delete it.

```txt
1. The orchestrator (or a human routing work)
   Reads: difficulty tier, dependency order, status checkbox.
   Needs: to pick the right model and dispatch one task at a time.

2. The implementing agent (often weaker than the author)
   Reads: one task block at a time.
   Needs: exact file paths, exact test names, exact acceptance criteria.
          Should never have to re-read the spec to start coding.

3. The reviewer (human, or a stronger reviewing agent)
   Reads: acceptance criteria + Definition of Done.
   Needs: to verify "is this actually done" without re-deriving the design.
```

---

## File Skeleton

Use this exact section order. Deviating breaks the orchestrator's ability to scan.

```txt
# PROGRESS.md — <project> MVP <N>: <one-line title>

## Goal                          (3–5 sentences max — what the user can do at the end)
## Difficulty Legend             (L1/L2/L3 definitions — see below)
## Agent-Readiness Verdict       (preconditions + baseline command)
## Non-Negotiable Rules          (≤15 bullets, each enforceable in code or test)
## Scope Boundary                (May mutate / Must not mutate)
## Shared Tool Result Format     (if applicable)
## Required New Tools            (flat list)
## Required Dev CLI Commands     (copy-pasteable shell)
## Suggested Module Layout       (file paths + NEW/EXTEND tag)

# Phase 0 — Preflight and Discovery
# Phase 1..N — implementation phases (see "Phase shape" below)
# Phase N+1 — Full Regression + Docs

# Definition of Done             (explicit, checkable list)
# Suggested Implementation Order (linear task ID list)
# Implementation Notes           (non-obvious gotchas only)
```

---

## The Difficulty Legend

This is the load-bearing innovation. Put it near the top. Use these exact tiers:

```txt
L1 — easy / mechanical. Single-file edits, schema additions, CLI parser entries,
     doc files, fixed-shape tests. Low blast radius. Suitable for haiku-class models.

L2 — medium / scoped logic. New helpers + tests, multi-file changes, integration
     with existing modules. Moderate safety surface. Suitable for sonnet-class models.

L3 — hard / safety-critical. Mutation orchestration, lock + idempotency state machines,
     security boundaries (path containment, command allowlists, redaction), crash
     recovery, E2E flows. Suitable for opus-class models.
```

### Tier assignment rule

Ask: *if this task goes wrong, what is the worst outcome?*

```txt
Wasted tokens, easy to revert       → L1
Broken local tests, easy to debug   → L2
Corrupt state / leaked secret /
forbidden command / data loss /
silent wrong answer                 → L3
```

Don't tier by line count. A 200-line schema migration is L1 if it's mechanical. A 30-line idempotency check is L3 if a wrong branch sends it down a destructive code path.

### Common mis-tiering

```txt
"It uses subprocess"        → L2 by default. Only L3 if it MUTATES.
"It has many tests"          → L1 if the tests are uniform shape.
"It's in the security file"  → look at what the function does, not where it lives.
"I'm not sure"               → bump up one tier. Cheaper than a bad commit.
```

---

## Phase Shape

A **phase** groups related tasks. Phases are sequential. Within a phase, tasks may be parallel-safe (mark them so).

A **task** is the atomic unit the orchestrator dispatches. Every task has:

```markdown
## <phase>.<n> <verb-first title>  [L1|L2|L3]

Status: [ ]

### Test first
<file path>:
```
test_name_one
test_name_two
test_name_three
```
Confirm they fail.

### Implementation
<exact file paths to create/edit>
<minimal API sketch — function names, signatures, key invariants>

### Verification
```bash
pytest path/to/test_file.py -q
```

### Acceptance
```txt
One or two sentences a reviewer can grade pass/fail.
```
```

### Hard rules for tasks

```txt
One task = one PR-sized change. If two things can be reverted independently, split them.
Test names are listed verbatim. Not "tests for X" — the actual function names.
File paths are absolute within the repo. No "the planner module" — write the path.
Acceptance is binary. "Works well" is not acceptance. "Tests pass + no SQLite writes during dry-run" is.
Status checkbox flips only when Verification passes. The implementing agent flips it.
```

### Anti-patterns

```txt
✗ "Refactor the X module." — too vague, unbounded blast radius.
✗ "Add tests for the existing helper." — without exact test names, the agent invents random shapes.
✗ "Update related docs." — name the doc and the section.
✗ One task that says "implement Phase 6" — the orchestrator can't dispatch a phase as a unit.
✗ Tasks that depend on tasks in a later phase — re-order them.
```

---

## Test-First Discipline

Every task's first action is: write failing tests. This isn't dogma; it's the only way a weaker agent can verify it understood the task.

```txt
1. List exact test names in the Test first block.
2. The implementing agent adds them, runs pytest, confirms RED for the right reason
   (missing module — not import error in unrelated code).
3. Then implementation proceeds until tests pass.
4. Then status flips.
```

Why this matters for tiered agents: an L1 model can copy a test name list and write a stub assertion. An L3 model can spend its budget on the hard logic, not on inventing test scaffolding.

---

## Dependency Order

End the doc with an explicit linear order:

```txt
0.1 → 0.2 → 0.3
1.1 → 1.2 → 1.3
2.1 → 2.2
...
N.1 → N.2 → N.3
```

The orchestrator should pick exactly one task at a time, in this order, unless tasks are explicitly marked parallel-safe. Bundling tasks defeats tiered routing — a phase containing one L3 + four L1 tasks gets dispatched at L3 cost.

If two tasks within a phase are independent, mark them:

```markdown
## 4.1 Artifact path helpers  [L1]  (parallel-safe with 4.2)
## 4.2 Artifact writers       [L2]  (parallel-safe with 4.1)
```

---

## Reuse Over Reinvention

Before adding new modules, force the implementer to look at what exists. Add a Phase 0 task like:

```markdown
## 0.2 Inspect existing contracts  [L1]

Read these files end-to-end and write a short scratchpad note (do NOT commit) mapping
spec names → existing helpers:

```txt
portfolio_manager/state.py            (acquire_lock, release_lock)
portfolio_manager/admin_locks.py      (with_config_lock — copy the SHAPE, not the lock name)
portfolio_manager/maintenance_artifacts.py   (redaction helper — REUSE)
...
```

Acceptance: the implementer can name the helpers they will reuse and the helpers
they must add. No code changed.
```

This single L1 task prevents a downstream L3 task from accidentally rebuilding lock infrastructure that already exists.

---

## Security Boundary Tasks

For any MVP that mutates filesystem, runs subprocesses, or calls external APIs, add a dedicated **Phase: Security Hardening** with these sub-task templates:

```txt
N.1 Input validation tests          [L1]   (regex / allowlist / bounds at the validator)
N.2 Path containment tests          [L2]   (escape attempts at the tool boundary)
N.3 Command allowlist static-grep   [L2]   (grep production code for forbidden strings)
N.4 Secret redaction tests          [L1]   (no token / env value in any artifact)
```

Static-grep tests (N.3) are particularly powerful: they fail the moment anyone introduces a forbidden command, no matter where. Example shape:

```python
def test_no_shell_true_in_worktree_modules():
    for path in glob("portfolio_manager/worktree_*.py"):
        assert "shell=True" not in Path(path).read_text()
```

---

## E2E Tasks

Real end-to-end tests should:

```txt
Use local fixtures (tmp_path + bare git repos / sqlite files), never live services.
Reuse one fixture across all E2E tests in the MVP — define it as a parallel-safe Phase task.
Cover the happy path AND at least one block path AND idempotency.
```

E2E tasks are almost always **L3** — they exercise the full mutation path including locks, artifacts, and recovery.

---

## Definition of Done

This is the reviewer's checklist. Make it copy-pasteable into a PR template. Each line is a binary check.

```txt
All MVP 1..N-1 tests still pass.
All MVP N tests pass.
<count> new tools registered: <names>.
<count> new dev_cli subcommands work and return shared result JSON.
skills/<skill-name>/SKILL.md exists and instructs <key behavior>.
<security invariant 1>
<security invariant 2>
<roadmap doc> updated to reflect MVP N implemented.
```

If a line in Definition of Done isn't covered by an automated test, add a task that covers it. If it can't be automated, mark it explicitly as a **manual smoke** task at the end of the last phase.

---

## What NOT to Put in a Progress.md

```txt
✗ Spec content (rationale, alternatives considered, design critique). That's the spec.
✗ Multi-paragraph prose explaining what a function does. Reference the spec section.
✗ Aspirational future work ("we should also..."). That's the next MVP's spec.
✗ Status updates ("as of yesterday..."). Use git log.
✗ Personal commentary. The doc outlives the conversation.
```

If a section serves the spec audience, move it to the spec. The progress.md is a build manifest, not a design document.

---

## Length Targets

```txt
Spec:        300–800 lines    (design + rationale)
Progress:    400–1000 lines   (one block per atomic task; longer = more tasks, not longer tasks)
Single task: 15–30 lines      (test list + impl sketch + acceptance — no prose)
```

If a single task block exceeds 40 lines, it's two tasks. Split it.

---

## Iteration

After the MVP ships:

```txt
1. Look at every task that needed a follow-up correction. What was missing from its block?
   Usually: a test name not listed, a file path implicit, an acceptance criterion vague.
2. Update THIS guide with the pattern that would have prevented it.
3. Skim the next MVP's draft progress.md against the updated guide before handing off.
```

The guide and the format compound. A progress.md written in the third MVP is dramatically tighter than the first.

---

## Quick Authoring Checklist

Before handing a progress.md to a dumber agent, verify:

```txt
[ ] Difficulty Legend present near the top with L1/L2/L3 definitions.
[ ] Every task has exactly one [L1|L2|L3] tag in its heading.
[ ] Every task has Test first / Implementation / Verification / Acceptance blocks.
[ ] Test first lists exact test function names, not descriptions.
[ ] Implementation names exact file paths, not module concepts.
[ ] Phase 0 includes "inspect existing contracts" before adding new modules.
[ ] Security-relevant MVPs have a dedicated hardening phase with static-grep tests.
[ ] E2E tasks use local fixtures, no live services.
[ ] Definition of Done is binary and matches automated test coverage.
[ ] Suggested Implementation Order is a flat linear list of task IDs.
[ ] No task block exceeds 40 lines. No task can be reverted half-way.
[ ] No spec rationale leaked into the progress doc.
```

If any line is unchecked, the dumber agent will guess. Fix it before dispatch.
