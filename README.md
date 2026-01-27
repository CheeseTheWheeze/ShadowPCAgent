# ShadowPCAgent

ShadowPCAgent is a draft repository for building a fully autonomous coding + GUI interaction agent. It focuses on:

- **Code autonomy**: understand, plan, edit, test, and validate arbitrary codebases.
- **GUI autonomy**: detect UI elements, respond quickly, and operate keyboard/mouse at a high level.
- **Safety**: generate drafts/diffs for sensitive changes before applying them.

## Prototype quickstart

This repository now includes a minimal runnable prototype that demonstrates the
planning and safety workflow.

```bash
python -m pip install -e .
python -m shadowpcagent "Summarize the repo status"
python -m shadowpcagent "Update production credentials" --json
python -m shadowpcagent "Update production credentials" --approve-sensitive
python -m shadowpcagent "List the repo status" --command "git status -sb"
python -m shadowpcagent "Draft a note" --draft-note "Capture next steps"
python -m shadowpcagent "Draft an edit" --edit-file README.md --find "ShadowPCAgent" --replace "ShadowPCAgent (Draft)" --json
python -m shadowpcagent "Plan only" --plan-only --json
python -m shadowpcagent "Apply draft" --apply-draft .shadowpcagent/drafts/draft-change-*.patch
```

Notes:

- GUI interactions are currently simulated (no real screen capture yet).
- Shell commands are allowlisted (default: `git`, `ls`, `pwd`).
- JSONL logs are written under `.shadowpcagent/logs`.
- Edits default to draft-only; use `--apply` to write changes.
- Use `--config` to load allowlist/max-files defaults from JSON.
- Use `--apply-draft` to apply a generated draft patch.

## Repository map

- `docs/architecture.md` — end-to-end system architecture and component boundaries.
- `docs/plan.md` — detailed delivery plan and milestones.
- `docs/safety.md` — sensitive-change policy, diff/approval flow, and guardrails.
- `docs/gui-interaction.md` — perception/action stack for GUI automation.
- `docs/code-intelligence.md` — repository analysis, editing, and test strategy.
- `docs/operations.md` — logging, auditing, and operational controls.
- `docs/roadmap.md` — phased rollout timeline and acceptance criteria.

## Draft status

This is a **first draft**. Expect revisions once:

- platform targets are finalized (OS, UI frameworks),
- security boundaries are clarified,
- performance targets are set,
- implementation constraints are confirmed.
