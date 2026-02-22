param(
    [string]$RepoPath,
    [switch]$Install,
    [switch]$Dev,
    [switch]$UseVenv
)

$scriptPath = Join-Path $PSScriptRoot "scripts\Launch-ShadowOverlay.ps1"
if (-not (Test-Path $scriptPath)) {
    throw "Could not find launcher script at '$scriptPath'. Ensure you are in the ShadowPCAgent repo root."
}

& $scriptPath -RepoPath $RepoPath -Install:$Install -Dev:$Dev -UseVenv:$UseVenv
