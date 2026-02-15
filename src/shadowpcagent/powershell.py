from __future__ import annotations


def build_inventory_and_dedupe_script() -> str:
    """Return a safe PowerShell script for inventory + duplicate analysis.

    The script is intentionally dry-run by default. It writes reports under
    $HOME/ShadowPCAgent-Reports and only moves files when -Apply is supplied.
    """

    return r'''param(
  [string]$ScanRoot = "$HOME",
  [string]$ReportRoot = "$HOME/ShadowPCAgent-Reports",
  [string[]]$ExcludePath = @(),
  [int]$MaxFiles = 0,
  [int]$ProgressEvery = 1000,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

$defaultExcludeFragments = @(
  "\\.git\\",
  "\\node_modules\\",
  "\\venv\\",
  "\\.venv\\",
  "\\__pycache__\\",
  "\\Windows\\",
  "\\Program Files\\",
  "\\Program Files (x86)\\",
  "\\ProgramData\\",
  "\\$Recycle.Bin\\",
  "\\System Volume Information\\",
  "\\ShadowPCAgent-Reports\\",
  "\\.gradle\\"
)

$excludeMatchers = @()
$excludeMatchers += $defaultExcludeFragments
$excludeMatchers += ($ExcludePath | Where-Object { $_ -and $_.Trim() -ne "" })

function Should-ExcludePath {
  param([string]$Path)

  foreach ($fragment in $excludeMatchers) {
    if ($Path -like "*$fragment*") {
      return $true
    }
  }
  return $false
}

Write-Host "==> Scan root: $ScanRoot"
Write-Host "==> Report root: $ReportRoot"

if (-not (Test-Path $ScanRoot)) {
  throw "Scan root does not exist: $ScanRoot"
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $ReportRoot "run-$ts"
$archiveDir = Join-Path $runDir "redundant-candidates"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

Write-Host "==> Gathering files"
$allFiles = Get-ChildItem -Path $ScanRoot -File -Recurse -ErrorAction SilentlyContinue
$files = $allFiles | Where-Object { -not (Should-ExcludePath -Path $_.FullName) }
if ($MaxFiles -gt 0) {
  $files = $files | Select-Object -First $MaxFiles
}

$inventory = $files | Select-Object FullName, Length, Extension, LastWriteTime
$inventoryPath = Join-Path $runDir "inventory.csv"
$inventory | Export-Csv -NoTypeInformation -Path $inventoryPath

Write-Host "==> Hashing files (can take time)"
$hashRows = New-Object System.Collections.Generic.List[object]
$processed = 0
foreach ($f in $files) {
  try {
    $h = Get-FileHash -Algorithm SHA256 -Path $f.FullName
    $hashRows.Add([PSCustomObject]@{
      FullName = $f.FullName
      Length = $f.Length
      Extension = $f.Extension
      Hash = $h.Hash
    }) | Out-Null
  } catch {
    Write-Warning "Failed to hash: $($f.FullName)"
  }

  $processed++
  if ($ProgressEvery -gt 0 -and ($processed % $ProgressEvery -eq 0)) {
    Write-Host "==> Progress: hashed $processed files"
  }
}

$hashPath = Join-Path $runDir "file-hashes.csv"
$hashRows | Export-Csv -NoTypeInformation -Path $hashPath

$dupes = $hashRows |
  Group-Object Hash |
  Where-Object { $_.Count -gt 1 }

$dupeCandidates = foreach ($group in $dupes) {
  $sorted = $group.Group | Sort-Object Length, FullName
  $keeper = $sorted[0]
  foreach ($item in $sorted[1..($sorted.Count - 1)]) {
    [PSCustomObject]@{
      Keep = $keeper.FullName
      Candidate = $item.FullName
      Hash = $item.Hash
      Length = $item.Length
    }
  }
}

$dupePath = Join-Path $runDir "duplicate-candidates.csv"
$dupeCandidates | Export-Csv -NoTypeInformation -Path $dupePath

Write-Host "==> Duplicate candidates: $($dupeCandidates.Count)"
Write-Host "==> Report: $runDir"

if (-not $Apply) {
  Write-Host "Dry run only. Re-run with -Apply to move duplicate candidates into: $archiveDir"
  exit 0
}

Write-Host "==> APPLY MODE: moving duplicate candidates"
foreach ($row in $dupeCandidates) {
  $src = $row.Candidate
  if (-not (Test-Path $src)) { continue }

  $hashPrefix = if ($row.Hash.Length -ge 12) { $row.Hash.Substring(0, 12) } else { $row.Hash }
  $safeName = ($src -replace "[:\\/]", "_")
  $baseName = "$hashPrefix`_$safeName"
  $dest = Join-Path $archiveDir $baseName
  $suffix = 1
  while (Test-Path $dest) {
    $dest = Join-Path $archiveDir ("{0}_{1}" -f $baseName, $suffix)
    $suffix++
  }

  Move-Item -Path $src -Destination $dest -Force
}

Write-Host "Done. Candidates moved to: $archiveDir"
'''
