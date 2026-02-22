param(
    [string]$RepoPath,
    [switch]$Install,
    [switch]$Dev,
    [switch]$UseVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
    param([string]$InputPath)

    if ($InputPath) {
        return (Resolve-Path -Path $InputPath).Path
    }

    if ($PSScriptRoot) {
        $fromScript = Resolve-Path (Join-Path $PSScriptRoot "..") -ErrorAction SilentlyContinue
        if ($fromScript -and (Test-Path (Join-Path $fromScript.Path "pyproject.toml"))) {
            return $fromScript.Path
        }
    }

    $cwd = (Get-Location).Path
    if (Test-Path (Join-Path $cwd "pyproject.toml")) {
        return $cwd
    }

    throw "Could not find repo root. Pass -RepoPath to the ShadowPCAgent folder containing pyproject.toml."
}

$repo = Resolve-RepoPath -InputPath $RepoPath

if (-not (Test-Path (Join-Path $repo "pyproject.toml"))) {
    throw "pyproject.toml not found at '$repo'."
}

Set-Location $repo

if ($UseVenv) {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
    }
    .\.venv\Scripts\Activate.ps1
}

if ($Install) {
    python -m pip install -U pip
    if ($Dev) {
        python -m pip install -e .[dev]
    }
    else {
        python -m pip install -e .
    }
}

$env:PYTHONPATH = (Join-Path $repo "src")
Write-Host "Launching ShadowPCAgent GUI from $repo" -ForegroundColor Green
python -m shadowpcagent.gui
