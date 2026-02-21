[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$RepoPath = (Get-Location).Path,

    [Parameter(Mandatory = $false)]
    [switch]$AutoResolveConflicts,

    [Parameter(Mandatory = $false)]
    [switch]$InstallStack,

    [Parameter(Mandatory = $false)]
    [switch]$PullModel,

    [Parameter(Mandatory = $false)]
    [string]$Model = "qwen2.5-coder:14b"
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Test-Command {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Install-WithWinget {
    param(
        [string]$Id,
        [string]$Name
    )

    Write-Step "Installing $Name ($Id) via winget"
    winget install --id $Id --accept-package-agreements --accept-source-agreements --silent
}

if (-not (Test-Path -LiteralPath $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

Write-Step "Switching to repo path"
Set-Location -LiteralPath $RepoPath

if (-not (Test-Path -LiteralPath ".git")) {
    throw "Not a git repository: $RepoPath"
}

if (-not (Test-Command "git")) {
    throw "git is required but not found in PATH"
}

Write-Step "Fetching latest remote refs"
git fetch --prune origin

$stashCreated = $false
$stashName = "auto-stash-before-main-sync-$(Get-Date -Format yyyyMMdd-HHmmss)"
$hasWorktreeChanges = [bool](git status --porcelain)

if ($hasWorktreeChanges) {
    Write-Step "Stashing local uncommitted changes"
    git stash push -u -m $stashName | Out-Host
    $stashCreated = $true
}

Write-Step "Checking out local main"
git checkout main

Write-Step "Updating local main from origin/main"
try {
    git pull --rebase origin main
}
catch {
    if (-not $AutoResolveConflicts) {
        throw "Rebase conflict occurred. Re-run with -AutoResolveConflicts to auto-resolve by preferring remote changes."
    }

    Write-Step "Attempting auto conflict resolution (prefer remote/theirs)"
    $conflicts = git diff --name-only --diff-filter=U
    foreach ($file in $conflicts) {
        git checkout --theirs -- $file
        git add -- $file
    }
    git rebase --continue
}

if ($stashCreated) {
    Write-Step "Re-applying stashed local changes"
    try {
        git stash pop | Out-Host
    }
    catch {
        Write-Warning "Stash pop had conflicts. Resolve manually; stash entry may still exist."
    }
}

Write-Step "Repository sync complete"

if ($InstallStack) {
    if (-not (Test-Command "winget")) {
        throw "winget is required for -InstallStack but was not found"
    }

    if (-not (Test-Command "python")) {
        Install-WithWinget -Id "Python.Python.3.12" -Name "Python 3.12"
    }

    if (-not (Test-Command "ollama")) {
        Install-WithWinget -Id "Ollama.Ollama" -Name "Ollama"
    }

    if (-not (Test-Command "pipx")) {
        Write-Step "Installing pipx"
        python -m pip install --user pipx
        python -m pipx ensurepath
        $env:Path = "$HOME\\.local\\bin;$env:Path"
    }

    if (-not (Test-Command "aider")) {
        Write-Step "Installing Aider"
        pipx install aider-chat
    }

    Write-Step "Ensuring Ollama service is reachable"
    try {
        ollama list | Out-Null
    }
    catch {
        Write-Warning "Could not query Ollama yet. If needed, start it manually and rerun model pull."
    }

    Write-Step "Setting user-level env vars for Aider + Ollama"
    setx OLLAMA_API_BASE "http://127.0.0.1:11434" | Out-Null
    setx AIDER_MODEL "ollama/$Model" | Out-Null

    Write-Host "Installed local coding stack. Open a new shell to pick up persisted env vars."
}

if ($PullModel) {
    if (-not (Test-Command "ollama")) {
        throw "ollama not found; install stack first or install Ollama manually"
    }

    Write-Step "Pulling model: $Model"
    ollama pull $Model
}

Write-Host "`nDone." -ForegroundColor Green
Write-Host "Try: aider --model ollama/$Model" -ForegroundColor Yellow
