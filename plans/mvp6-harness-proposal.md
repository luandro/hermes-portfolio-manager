# MVP 6 Harness Proposal -- Superseded

**Status: superseded.** The normative design lives in `docs/mvps/mvp6-spec.md`
and `docs/mvps/mvp6-progress.md`. This file is kept only as a pointer.

The earlier draft of this proposal defined a competing `harnesses.yaml` schema
(`defaults` + `project_overrides`), forge-specific provider switching via
`zai_usage.sh`, a different tool surface (`harness_list`, `harness_explain`,
`cancel`), and a renamed skill folder. Those choices conflict with the
progress doc's harness-agnostic runner contract and with MVP 6's spec
(which requires `apply_review_fixes` for MVP 7 to call).

The pieces worth keeping have been folded into:

- `config/harnesses.yaml.example` -- realistic forge / codex / claude-code
  entries using the progress-doc schema (`harnesses: [array]` with argv
  `command`, `env_passthrough`, `required_checks`, `checks{}`).

Out of scope for MVP 6 (deferred):

- Provider / model selection and usage-check polling.
- API key loading from server-side secrets.
- `forge update && forge workspace sync` post-run (operator-side, not plugin).
- Kilo invocation details (TBD).

If a future MVP needs provider switching or budget tracking, design it then;
do not retrofit MVP 6.
