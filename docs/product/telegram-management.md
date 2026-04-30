Now imagine the system is already installed.

The user has done the first setup on a remote VPS. They connected GitHub. They added the provider keys. They configured the basic model budgets. They connected Telegram. They ran the first doctor command to check that the server can reach GitHub, can send Telegram messages, can access the configured models, and can see the worktree folder.

After that first setup, the user almost never needs to SSH into the server again.

From this point on, Telegram becomes the control room.

The user wakes up in the morning and opens Telegram. There is a message from the agent:

“Good morning. Last heartbeat completed. Three projects checked. Two issues need clarification. One PR is ready for QA. No budget problems. No dirty worktrees.”

Below the message are simple buttons:

“View projects.”

“View blocked work.”

“Create issue.”

“Add project.”

“Review ready PRs.”

“Change today’s priorities.”

The user taps “View projects.”

The agent replies with a short list:

“CoMapeo Cloud App: high priority. Two active issues. One PR in review.”

“EDT Website Migration: medium priority. One spec waiting for approval.”

“Docs Support Bot: low priority today. Maintenance checks passed.”

The user is traveling, away from the computer, and remembers a new feature idea. Instead of opening GitHub, they send a Telegram voice message:

“Add an issue to the CoMapeo Cloud App. I want users to be able to upload different public data layers, style them in the browser, and export them as an offline map package that can be imported into CoMapeo.”

The Telegram bot receives the audio. The system transcribes it. Then it tries to understand three things.

First, which project is this about?

Second, is this ready to become a GitHub issue?

Third, does it need a brainstorming session before becoming a formal spec?

In this case, the project is probably clear: CoMapeo Cloud App. But the feature is big. It touches upload, styling, export, offline map packages, and CoMapeo compatibility. So the agent does not immediately create a vague GitHub issue. It starts a short product conversation.

It replies:

“I think this is for CoMapeo Cloud App. This sounds like a medium-to-large feature, not a small issue. I suggest turning it into a parent issue with smaller implementation tasks.

Before I create it, I need three decisions.

One: should users export only the selected layers, or selected layers plus default country catalog layers?

Two: should styling be basic at first, like color, opacity, and labels, or should it support advanced style rules?

Three: is the first target CoMapeo Mobile, CoMapeo Desktop, or both?”

The user can reply by voice or text.

They say:

“Start simple. Selected layers only. Basic styling. First make sure it works with CoMapeo Mobile. Desktop can come later.”

The agent now has enough product direction. It creates a draft issue spec in its internal state. Then it sends back a summary:

“Here is the proposed issue.

Title: Export selected styled layers as an offline map package for CoMapeo Mobile.

Goal: allow users to upload public data layers, apply basic styling in the browser, select layers, and export them as an offline map package that can be imported into CoMapeo Mobile.

Non-goals: advanced style rules, automatic country catalog export, CoMapeo Desktop-specific behavior.

Suggested split:

Define export format and compatibility checks.

Add basic style controls.

Add selected-layer export flow.

Add tests and QA script.

Update documentation.

Confidence: 0.84.

Create this GitHub issue?”

The user taps “Create issue.”

The system creates the GitHub issue in the right repository. It adds labels like spec-ready, medium-risk, and agent-candidate. It links the Telegram conversation as an internal decision artifact, but it does not expose private Telegram messages unless configured to do so. It writes a clean public issue description in GitHub.

From the user’s perspective, they had an idea while walking, sent one voice message, answered three questions, and the system created a well-scoped GitHub issue.

Now imagine another situation.

The user wants to add a new project to the automation system.

They send a Telegram message:

“Add the repository awana-digital/edt-next as a new project. Medium priority. It should run docs checks weekly and never auto-merge.”

The agent checks whether it has access to the repo. It checks GitHub. It detects the default branch. It looks for package files, test commands, docs commands, and existing agent instruction files. If the repository already has .agent/project.yaml, it reads it. If not, it proposes one.

It replies:

“I found the repository. Default branch is main. I found a Next.js project with package scripts for lint and build. I did not find .agent/project.yaml.

Suggested project configuration:
Priority: medium.
Auto-merge: disabled.
Required checks: lint, build.
Maintenance: weekly docs/build check.
Protected paths: .github/workflows, infra, auth, content/migrations.
Notifications: normal digest only.

Should I add this project to the user manifest and open a PR adding .agent/project.yaml to the repo?”

The user taps “Yes.”

The system updates the global user manifest on the server. Then it creates a first branch in the new repository with the proposed project manifest. It opens a PR so the repo itself contains its own automation policy. Since this is a configuration change, and the user said never auto-merge, it waits for human review.

Again, the user did not SSH into the server. They did not edit YAML manually. They used Telegram as a management interface.

Now imagine the user wants to change priorities.

They send:

“For today, focus on the EDT Website Migration and ignore low-priority maintenance unless it is security related.”

The agent understands this as a temporary override, not a permanent manifest change. It writes a temporary priority rule:

“Until tomorrow morning, EDT Website Migration is top priority. Low-priority maintenance is paused except security-related checks.”

It replies:

“Temporary priority override set until tomorrow at 8 AM. I will focus on EDT Website Migration and only run low-priority maintenance if it is security related.”

This is important because not every Telegram command should permanently change the manifest. Some commands are durable configuration changes. Others are temporary operating instructions.

The Telegram interface should understand that difference.

A permanent command is something like:

“Add this repo.”

“Change this project’s default priority to high.”

“Set DeepSeek monthly limit to thirty dollars.”

“Never auto-merge this project.”

A temporary command is something like:

“Pause this project today.”

“Focus on this issue tonight.”

“Do not spend paid model budget until Monday.”

“Only do docs tasks while I am traveling.”

The system should always make that distinction clear before changing long-term configuration.

Now imagine the user wants to create a maintenance task.

They send a voice message:

“For the docs support bot, every Monday, check if the docs index builds correctly and if any links are broken. If it fails, create an issue, but don’t fix automatically.”

The agent finds the project. It recognizes this as a recurring maintenance task. It proposes the manifest change:

“Project: Docs Support Bot.

New maintenance task:
Run weekly on Monday.
Commands:

build docs index.

check links.
If it fails: create GitHub issue.
Auto-fix: disabled.
Risk: low.

Apply this configuration?”

The user says yes.

The system updates the project manifest, opens a configuration PR if the manifest lives in the repo, and stores the new maintenance rule. On the next Monday heartbeat, the task runs automatically. If it fails, the system opens a GitHub issue with the logs, likely cause, and suggested next steps.

Now imagine the user wants to approve a spec.

The agent sends:

“I prepared a spec for issue 47 in EDT Website Migration: migrate WordPress publications into Markdown. Confidence: 0.79. I do not recommend auto-development yet because translation structure and media handling are not fully decided.

Open questions:
One: should old blog posts be migrated?
Two: should offline deployment pages be kept?
Three: should images be downloaded and stored locally?”

The user replies by voice:

“Skip blog for now. Skip offline deploy pages. Yes, download images and store them locally.”

The agent updates the spec and replies:

“Spec updated. Confidence is now 0.88. Risk is medium. I can prepare the implementation plan, but this should not auto-merge because it affects content migration. Start development?”

The user taps “Start development.”

That single tap moves the issue from spec-ready to implementation-candidate. At the next heartbeat, or immediately if the system supports manual dispatch, it creates a worktree and starts the test-first implementation loop.

Now imagine the user wants to check what happened overnight.

They type:

“Status.”

The agent replies with a clear digest:

“Overnight summary.

CoMapeo Cloud App:
Issue 123 moved from spec drafting to implementation.
PR 130 passed CodeRabbit and Greptile. Waiting for Gemini review.

EDT Website Migration:
Issue 47 needs your answer about image storage.
No development started.

Docs Support Bot:
Weekly maintenance passed.
No action needed.

Budget:
Gemini available.
OpenAI daily budget 70 percent remaining.
DeepSeek not used today.

Blocked:
One dirty worktree in old branch agent/118-layer-picker. I paused that task.”

The user can then ask:

“Why is issue 118 dirty?”

The agent replies:

“The worktree has uncommitted changes and generated files after a failed rebase. I did not stash or overwrite them. Options:

show summary,

create a patch backup,

ask an agent to inspect,

mark abandoned,

notify me later.”

The user taps “show summary.”

This is the pattern: Telegram gives the user operational control without hiding risk.

Now imagine a PR is ready.

The agent messages:

“PR 130 is ready for human QA.

Project: CoMapeo Cloud App.
Change: export selected styled layers as SMP.
Risk: high, because this affects user-facing offline map exports.
Automated checks passed.
Review ladder passed: CodeRabbit, Greptile, Gemini, Codex, DeepSeek.
Auto-merge disabled because risk is high.

QA script:

Open the app.

Upload a GeoJSON layer.

Style it with a color and opacity.

Select only that layer.

Export as SMP.

Import into CoMapeo Mobile.

Confirm the selected layer appears offline.

Confirm unselected layers are not included.

Actions:
Open PR.
Mark QA passed.
Ask for changes.
Pause.”

The user taps “Open PR” if they are at a computer. Or if they already tested it, they tap “Mark QA passed.” The system can then either merge, if allowed, or remind the user to merge manually.

For high-impact work, Telegram does not become a dangerous “merge everything” remote control. It becomes a decision assistant. It summarizes what happened, explains the risk, and asks for explicit human judgment.

Now let’s describe the whole user experience in one flow.

The user sets up the system once on a VPS. They connect GitHub, providers, coding harnesses, and Telegram. After that, Telegram becomes the main interface.

They can add projects.

They can remove or pause projects.

They can change priorities.

They can set model budgets.

They can create issues by text or voice.

They can brainstorm specs with the agent.

They can answer follow-up questions.

They can approve or reject specs.

They can start development.

They can pause work.

They can ask for status.

They can inspect blockers.

They can configure maintenance tasks.

They can approve QA.

They can decide whether a PR is ready to merge.

They can do all this while walking, traveling, or lying in bed, without opening the terminal.

But the system still keeps the serious state in GitHub, manifests, logs, and the database. Telegram is the interface. It is not the source of truth.

The source of truth remains:

the user manifest for global configuration,

the project manifest for repo-specific policy,

GitHub for issues and PRs,

SQLite for runtime state,

and logs for auditability.

Telegram is the conversational control layer on top.

The agent should be smart, but also humble. When it is confident, it acts. When it is not confident, it asks. When a change is temporary, it says so. When a change is permanent, it asks for confirmation. When a task is risky, it refuses to auto-merge. When a worktree is dirty, it stops. When budget is low, it changes behavior.

This makes Telegram powerful without making it reckless.

The best version of the system feels like having a technical project manager, release coordinator, and junior development team available through voice messages.

You say:

“Add this idea to the right project.”

It figures out the project, asks a few questions, and creates a clean GitHub issue.

You say:

“Focus on the website migration tonight.”

It changes the priority for the next heartbeats.

You say:

“Add weekly dependency checks to this repo.”

It updates the manifest and starts tracking it.

You say:

“What needs me?”

It tells you only the decisions that require your judgment.

That is the key experience.

The human does not manage agents by watching logs all day.

The human manages direction.

The system manages execution.
