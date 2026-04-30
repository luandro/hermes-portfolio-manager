Technical narrative: an automated AI multi-project system that works while you sleep
Imagine you have a remote machine running quietly somewhere. It could be a small server, a VPS, or a spare computer in your office. On that machine lives your automated development system.

You do not interact with it like a chatbot all day. You interact with it mostly through GitHub, Telegram, Slack, and a few simple manifest files.

The system wakes up on a rhythm. Every few minutes, or every hour, or only at night, depending on your configuration, a heartbeat runs. At each heartbeat, it asks: what projects does the user care about, what work is waiting, what models are available, what can be safely done now, and what needs the human?

From your perspective, the most common workflow starts in GitHub.

You open a new issue in one of your repositories. Maybe you write something rough, like: “Add an export button so users can download selected map layers as an SMP file.” You do not need to write a perfect technical spec. You just describe the feature, the bug, or the maintenance task as clearly as you can.

Then you walk away.

At the next heartbeat, the system checks your user manifest. This manifest is the control center. It lists all the projects the system is allowed to work on, the repository URLs, their priorities, the active work windows, the coding harnesses it can call, the review agents it should use, the providers and models available, and the budget limits for paid APIs.

The system sees that your CoMapeo Cloud App project is high priority. It fetches the open issues from GitHub. It finds your new issue. It checks whether the issue already has enough detail to act on. It looks for acceptance criteria, likely affected files, technical risks, testing strategy, design ambiguity, and whether the change is small or high impact.

If the issue is vague, it does not jump into coding. Instead, it drafts a spec. It reads the codebase, reads the project’s AGENTS.md or .agent/project.yaml, looks at nearby files, and creates an internal artifact for the issue. Something like: original request, interpreted goal, non-goals, acceptance criteria, test plan, risk assessment, open questions, and confidence score.

Then it may message you on Telegram or Slack.

It might say:

“Project: CoMapeo Cloud App. Issue 123: Export selected map layers as SMP. Confidence: 0.68. I need one product decision. Should the exported SMP include only the user-selected layers, or should it also include the default country catalog layers? Suggested default: selected layers only. Reply 1 to accept, 2 to include catalog layers, or 3 to explain.”

You reply from your phone. The system records your answer, updates the issue artifact, and may also comment back on the GitHub issue so the decision is visible to the team.

On a later heartbeat, the system checks again. Now the issue has enough detail. The confidence score is higher. Maybe it is 0.86. The project manifest says medium-risk issues can be automatically developed, but not automatically merged. So the system starts an implementation cycle.

It creates a dedicated Git worktree for that issue. The naming convention is simple: the base repo is checked out under the repo name, and each issue gets its own separate worktree, like comapeo-cloud-app-issue-123. This prevents agents from stepping on each other’s changes.

Before it touches anything, the system fetches the latest main or master branch. It detects the default branch from GitHub. It checks whether the worktree is clean. If it is clean, it rebases or updates from the latest base branch. If it is dirty, conflicted, or has unknown changes, it does not blindly stash and continue. It marks the worktree as dirty in the project state and notifies you. The system is allowed to be useful, but it is not allowed to make a mess silently.

Once the worktree is ready, the implementation starts from tests.

This is one of the core rules of the system: agents should not simply write code and then invent tests afterward. The issue spec includes acceptance criteria. The implementation agent first writes meaningful failing tests that prove those criteria. The system then runs the tests and confirms that they fail for the right reason. Only then does it implement the smallest reasonable change.

After implementation, it runs the project’s quality gates. These are defined in the project manifest. For a TypeScript project, that might mean linting, type checking, unit tests, and maybe end-to-end tests. For a docs project, it might mean link checking, build validation, and markdown formatting. For a Python project, it might mean pytest, type checking, and formatting.

The system also runs agent-specific quality checks. It asks: did the implementation drift away from the original issue? Did the agent touch too many unrelated files? Did it add meaningless tests? Did it create tests that only test mocks? Did it update documentation if the behavior changed? Did it create a QA script if there is a user interface to manually verify?

If the change passes the local gates, the system commits the work with structured commits. It pushes a branch, opens a pull request, and writes a PR description that explains the linked issue, the acceptance criteria, the tests added, commands run, known risks, and human QA steps.

Now the pull request enters the review ladder.

The system does not send every PR immediately to the most expensive model. It starts with cheaper or free review agents. For example, it might first wait for CodeRabbit and Greptile. Those tools review the PR in GitHub and leave comments. If they request changes, the system reads the comments, decides which ones are valid, applies fixes through a coding harness, runs tests again, and pushes another commit.

But this review loop is bounded. It does not chase perfection forever. Each review stage has a maximum number of iterations. The goal is not “everyone says it is perfect.” The goal is measurable: no unresolved critical comments, no failing checks, no scope creep, meaningful tests, updated docs when needed, and a QA script when manual testing is required.

After the first review stage passes, the system moves to a stronger but still cheap or subscription-based reviewer, like Gemini or Junie, depending on what you configured. If that passes, and the change is important enough, it may call Codex or another stronger coding model for deeper review. Finally, for high-impact changes, it can call a final reasoning model, such as DeepSeek, but only if the daily and monthly budget allows it.

This is where the provider budget manager matters.

Each heartbeat checks the available model budget. If free or low-cost models are available, the system can do triage, spec drafting, documentation cleanup, small tests, and low-risk review. If high-quality paid models are available, the system can spend them on high-value moments: architecture review, final PR review, difficult bug diagnosis, or complex planning. If DeepSeek has a daily limit of three dollars, the system respects that. If the limit is reached, it does not keep spending. It downgrades the type of work it attempts.

Eventually, the PR reaches a final state.

If it is a small low-risk change, and the project manifest explicitly allows auto-merge, and all checks pass, and no protected paths were touched, and all review stages passed, then the system may merge it automatically.

But for high-impact PRs, it never auto-merges. Instead, it notifies you.

It might say:

“Project: CoMapeo Cloud App. PR 130 is ready for human review. Risk: high. Reason: touches export behavior and user-facing map package generation. All automated checks passed. Review stages passed: CodeRabbit, Greptile, Gemini, Codex, DeepSeek. Manual QA script is ready. Recommended action: run QA steps and merge if satisfied.”

Then you open the PR. You read the summary. You run the QA script. Maybe the script says: open the app, upload a GeoJSON layer, style the layer, select it, export as SMP, import it into CoMapeo, and verify that only selected layers appear. You follow the script. If it works, you merge. If not, you comment, and the system picks that up in a future heartbeat.

That is the normal feature flow.

There is also a maintenance flow.

Instead of creating issues manually for everything, each project manifest can define maintenance tasks. These are recurring checks the system should run. For example: check dependencies weekly, run documentation link checks, check test health, update generated agent files, verify that docs build, inspect stale branches, or open small PRs for safe updates.

You configure these in .agent/project.yaml.

You might say: for this project, every week, run npm outdated; every heartbeat, run npm test; every month, check whether screenshots or generated docs need updating. Each task has a risk level. Low-risk tasks can run often. Medium-risk tasks may only open PRs. High-risk maintenance tasks require your approval before any implementation begins.

From your perspective, this means you can configure the system once and then receive useful prompts instead of manually remembering everything.

Now let’s go underneath the surface.

Technically, the system is not one big autonomous agent. That would be dangerous and hard to debug. The safer architecture is a boring, auditable daemon.

At the center is the heartbeat orchestrator. Cron or a systemd timer wakes it up. The orchestrator loads the user manifest, checks whether it is allowed to work at this time of day, refreshes provider budget state, loads project manifests, ranks projects by priority, and then starts processing them one by one.

The ranking matters. If the system only has a little time or budget, it should work on the most important projects first. It should also prefer tasks that fit the available model budget. If only low-cost models are available, it should avoid complex high-impact implementation and instead do triage, issue cleanup, documentation checks, and low-risk maintenance.

The orchestrator talks to several adapters.

The GitHub adapter fetches issues, pull requests, comments, reviews, labels, branch information, and CI status. It may also create comments, open pull requests, update labels, and eventually merge if allowed.

The Git adapter manages local repositories and worktrees. It detects the default branch, fetches from origin, checks whether each worktree is clean, identifies dirty or conflicted worktrees, and makes sure each issue branch is isolated.

The provider budget adapter tracks usage across OpenAI, Anthropic, Gemini, DeepSeek, or any other model provider. It stores daily and monthly usage, rate limits, failures, and current availability. The model router uses this information to decide what kind of agent work is allowed.

The notification adapter sends messages through Telegram, Slack, or another messaging platform. It should avoid spamming you. Most notifications should be batched into a digest. But blockers, merge-ready PRs, user questions, and budget warnings can be sent immediately.

The agent dispatcher is the layer that actually calls coding harnesses and review systems. It might call Forge for implementation, Claude Code for planning, Codex for bug fixing or deeper review, Junie or Gemini for free review, Greptile or CodeRabbit for PR feedback, and DeepSeek for final reasoning review. The important point is that these tools are not called randomly. They are called by state-machine transitions and project policy.

The durable state lives in SQLite.

This is very important. The manifest is not enough. The manifest describes what should exist. The database records what is currently happening.

The database tracks projects, issues, PRs, worktrees, review attempts, provider usage snapshots, notification history, heartbeat runs, locks, and blockers. Without durable state, every heartbeat would be forced to rediscover the world from scratch, and the system would eventually repeat work, lose context, or make unsafe decisions.

Each issue has a state machine.

A new issue starts as untriaged. Then it moves into spec drafting. If the issue is unclear, it moves to needs-user-questions. Once the user answers, it returns to spec drafting. If the spec becomes good enough, it moves to spec-ready. If confidence and risk policy allow it, it becomes an implementation candidate. Then it enters implementation, opens a PR, moves into review, and eventually becomes ready for human review, auto-merge candidate, merged, closed, or blocked.

The pull request has its own state machine.

A PR can be opened, waiting for first-stage review, waiting for review fixes, passed first-stage review, waiting for Gemini review, waiting for Codex review, waiting for final review, ready for human, auto-merge candidate, merged, or blocked.

This separation matters because issues and PRs are related but not identical. One issue may split into several PRs. One PR may close several issues. One high-impact issue may become a parent task with multiple child tasks.

Large tasks should be split. The system should not try to solve huge, ambiguous issues in one heroic branch. If an issue touches frontend, backend, database, docs, and CI, the system should pause and create a plan. It can propose child issues or internal subtasks. For example: define the export interface, implement the packaging function, add the UI, add tests, update docs, then create the final integration PR.

This is especially important for your use case, because you want agents to work while you sleep, but not wake up to a giant unreviewable PR.

The quality system is another core layer.

Every implementation is checked against the original issue. The system asks: did we solve the requested problem, or did we wander into improvements that were never asked for? Did we introduce a new abstraction that is not justified? Did we add dependencies unnecessarily? Did we change behavior outside the acceptance criteria? Did we update docs if user-facing behavior changed?

The test quality checker is particularly important.

AI agents often add tests that look good but do not prove much. They may test mocks instead of behavior. They may assert that a function was called, but not that the right outcome happened. They may duplicate implementation logic inside the test. They may add snapshots that are too broad to be useful. Or worse, they may write tests that would have passed before the implementation.

So the system should score tests for meaningfulness. A meaningful test connects directly to an acceptance criterion. It should fail before the implementation, pass after the implementation, and protect against a real regression.

For interface-heavy work, the system generates a QA script. This is not just a checklist for the agent. It is a human-readable manual test plan. It says what to click, what to upload, what to expect, and what screenshots or outputs to check. The system should run as much as possible automatically, but it should admit when human eyes are required.

The system also needs a strict risk policy.

Low-risk changes might be docs, typo fixes, small tests, or simple internal refactors. Medium-risk changes might be small user-facing behavior changes. High-risk changes include security, authentication, permissions, database migrations, deployment workflows, CI, billing, API contracts, or major architecture changes.

Each project can define protected paths. For example, .github/workflows, auth, security, migrations, infra, or billing. If a PR touches those paths, auto-merge is disabled, no matter how confident the model sounds.

This is how you prevent the system from becoming dangerous.

Now, about logs.

Every heartbeat should produce a human-readable log and a machine-readable event log. The Markdown log tells you what happened: projects processed, issues triaged, specs improved, PRs reviewed, worktrees blocked, notifications sent, and next suggested actions. The JSONL log records the same events in a format that can later power a dashboard.

A heartbeat log might say: synced three projects, found one dirty worktree, generated two issue specs, asked one user question, triggered CodeRabbit on one PR, skipped DeepSeek because the daily budget was exhausted, and recommended resolving a conflict in one worktree.

This gives you trust. You can wake up, read the digest, and understand exactly what happened.

Installation should be simple.

The user installs the runner on a remote machine. They run an init command. The system creates a config folder, a sample user manifest, a SQLite database, a logs folder, and a worktree root. Then the user adds projects. The system checks GitHub authentication, notification settings, provider credentials, and whether coding harnesses are available. Then it installs a systemd timer or cron entry.

The first milestone should not include autonomous coding.

The safest MVP is just the heartbeat runner, manifests, GitHub reading, worktree inspection, logging, and notifications. It should tell you what it would do before it does it.

The second milestone is the spec agent. It reads issues, drafts specs, calculates confidence, and asks you questions.

The third milestone is manually approved implementation. You label an issue as ready, and the system creates a worktree, writes tests, implements the change, runs checks, opens a PR, and generates a QA script.

The fourth milestone is the review ladder. The system detects PRs that need review, triggers review agents in order, applies fixes, and notifies you when ready.

Only after all of that should you add budget-aware autonomy and conservative auto-merge.

The final shape of the system is simple to describe.

It is a multi-project AI development runner that wakes up on a heartbeat. It reads a manifest. It checks what work is safe and useful. It syncs repositories. It improves issues into specs. It asks the user when judgment is needed. It creates isolated worktrees. It develops test-first. It reviews in stages from cheap to expensive. It watches budgets. It blocks risky changes. It writes logs. It sends notifications. And when a pull request is ready, it gives the human exactly what they need to decide.

The system’s job is not to replace the technical product manager.

The system’s job is to let the human act as a higher-level technical product manager.

You create direction. You approve specs. You answer the questions that require context. You review high-impact changes. You decide what merges.

The agents do the repetitive work: reading issues, preparing specs, creating branches, writing tests, implementing scoped changes, running checks, responding to reviews, updating docs, and preparing QA.

That is the balance.

The machine works while you sleep, but the human remains the source of judgment.
