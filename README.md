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
python -m shadowpcagent --task-file docs/plan.md --plan-only --json
python -m shadowpcagent "Validate draft" --apply-draft .shadowpcagent/drafts/draft-change-*.patch --dry-run-apply --json
python -m shadowpcagent "Plan only" --plan-only --json
python -m shadowpcagent "Apply draft" --apply-draft .shadowpcagent/drafts/draft-change-*.patch --approve-sensitive
```

Notes:

- GUI interactions are currently simulated (no real screen capture yet).
- Shell commands are allowlisted (default: `git`, `ls`, `pwd`).
- JSONL logs are written under `.shadowpcagent/logs`.
- Run summaries are written to `artifacts/run-summary.json`.
- Run history is appended to `artifacts/run-history.jsonl`.
- Edits default to draft-only; use `--apply` to write changes.
- Use `--config` to load allowlist/max-files defaults from JSON.
- Use `--apply-draft` to apply a generated draft patch (requires `--approve-sensitive`).
- Use `--dry-run-apply` to validate a patch without applying it.
- Use `--task-file` to load a task description from a file.

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

## Testing

Install development dependencies:

```bash
python -m pip install -e .[dev]
```

Run the test suite (one command):

```bash
python -m pytest
```

PowerShell quick copy/paste:

```powershell
python -m pip install -e .[dev]; python -m pytest
```

## Windows quickstart (download, run, push)

### Download / clone

```powershell
git clone https://github.com/<your-org>/ShadowPCAgent.git
cd ShadowPCAgent

# Confirm you're in the repo (should show README.md, pyproject.toml, src/, etc.)
Get-ChildItem
```

### Install + run (from the repo root)

```powershell
python -m pip install -e .[dev]
python -m shadowpcagent "Summarize the repo status"
```

### Run tests (from the repo root)

```powershell
python -m pytest
```

### Generate a PowerShell cleanup helper script

This prints a ready-to-run PowerShell script that inventories files,
finds duplicate-content candidates by SHA256 hash, and writes reports.
It is dry-run by default and only moves files if run with `-Apply`.

```powershell
python -m shadowpcagent --emit-powershell-cleanup-script > .\Run-InventoryAndDedupe.ps1
powershell -ExecutionPolicy Bypass -File .\Run-InventoryAndDedupe.ps1
```

To apply candidate moves after reviewing reports:

```powershell
powershell -ExecutionPolicy Bypass -File .\Run-InventoryAndDedupe.ps1 -Apply
```


If you see errors like "does not appear to be a Python project" or
"No module named pytest", you're likely in the wrong folder. Run:

```powershell
Get-Location
Get-ChildItem
```

Then `cd` back into the repo (the folder that contains `pyproject.toml`).

### Push changes

```powershell
git status -sb
git add .
git commit -m "Your message"
git push -u origin <your-branch>
```
