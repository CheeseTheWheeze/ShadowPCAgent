# Local Codex-Adjacent Setup (Windows + NVIDIA GPU)

This repository includes a helper script to:

1. Update your local repo to the newest `origin/main`.
2. Optionally auto-resolve local merge/rebase conflicts.
3. Install a strong local coding stack using Ollama + Aider.
4. Pull a recommended local coding model.

## Hardware profile this is tuned for
- GPU: ~20 GB VRAM (e.g. RTX A4500 20GB)
- CPU: high-core count (e.g. EPYC)
- RAM: ~28 GB

Recommended default model:
- `qwen2.5-coder:14b`

## Script location
- `scripts/update-main-and-setup-local-agent.ps1`

## Quick usage
From PowerShell (run as your normal user):

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
./scripts/update-main-and-setup-local-agent.ps1 -RepoPath "$PWD" -AutoResolveConflicts -InstallStack -PullModel
```

## Common modes
Update repo only:

```powershell
./scripts/update-main-and-setup-local-agent.ps1 -RepoPath "$PWD"
```

Update repo + install tools, but skip model pull:

```powershell
./scripts/update-main-and-setup-local-agent.ps1 -RepoPath "$PWD" -InstallStack
```

Use a smaller/faster model:

```powershell
./scripts/update-main-and-setup-local-agent.ps1 -RepoPath "$PWD" -InstallStack -PullModel -Model "qwen2.5-coder:7b"
```

## After setup
Use Aider with Ollama in your repo:

```powershell
$env:OLLAMA_API_BASE = "http://127.0.0.1:11434"
aider --model ollama/qwen2.5-coder:14b
```

You can also set these globally (User scope):

```powershell
setx OLLAMA_API_BASE "http://127.0.0.1:11434"
setx AIDER_MODEL "ollama/qwen2.5-coder:14b"
```

## Notes
- If you have uncommitted changes, the script will stash and re-apply them.
- If auto conflict resolution is enabled, it prefers remote (`theirs`) changes during rebase conflicts.
- If `winget` is unavailable, install tools manually and rerun with `-InstallStack:$false`.
