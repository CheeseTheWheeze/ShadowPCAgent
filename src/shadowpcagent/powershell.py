from __future__ import annotations


def build_inventory_and_dedupe_script() -> str:
    """Return a safe PowerShell script for inventory + duplicate analysis.

    The script is intentionally dry-run by default. It writes reports under
    $HOME/ShadowPCAgent-Reports and only moves files when -Apply is supplied.
    """

    return r'''param(
  [string]$ScanRoot = "$HOME",
  [string]$ReportRoot = "$HOME/ShadowPCAgent-Reports",
  [string[]]$ExcludePath = @(
    "$HOME/ShadowPCAgent-Reports",
    "$HOME/.gradle",
    "$HOME/AppData/Local/Temp",
    "$HOME/AppData/Local/Microsoft/OneDrive",
    "C:/Windows",
    "C:/Program Files",
    "C:/Program Files (x86)",
    "C:/ProgramData",
    "C:/$Recycle.Bin",
    "C:/System Volume Information"
  ),
  [string[]]$ExcludeGlob = @("*/.git/*", "*/node_modules/*", "*/venv/*", "*/.venv/*", "*/__pycache__/*"),
  [string[]]$ExcludeRegex = @(),
  [string[]]$IncludeExtension = @(),
  [string[]]$IncludeGlob = @(),
  [int]$MaxFiles = 0,
  [int]$ProgressEvery = 500,
  [int]$HashConcurrency = 1,
  [string]$HashCachePath = "$HOME/ShadowPCAgent-Reports/hash-cache.csv",
  [switch]$DisableHashCache,
  [int]$HashRetryCount = 2,
  [int]$HashRetryDelayMs = 200,
  [int]$MoveRetryCount = 2,
  [int]$MoveRetryDelayMs = 200,
  [switch]$UseLongPathPrefix,
  [double]$RequirePreflightHeadroomGB = 2,
  [switch]$WhatIfApply,
  [switch]$Apply
)

$ErrorActionPreference = "Stop"

Write-Host "==> Scan root: $ScanRoot"
Write-Host "==> Report root: $ReportRoot"
Write-Host "==> Max files: $MaxFiles (0 means unlimited)"
Write-Host "==> Progress every: $ProgressEvery files"
Write-Host "==> Hash concurrency: $HashConcurrency"
Write-Host "==> Hash cache: $HashCachePath (disabled: $DisableHashCache)"

if (-not (Test-Path $ScanRoot)) {
  throw "Scan root does not exist: $ScanRoot"
}

if ($ProgressEvery -lt 1) { $ProgressEvery = 500 }
if ($HashConcurrency -lt 1) { $HashConcurrency = 1 }
if ($HashRetryCount -lt 0) { $HashRetryCount = 0 }
if ($MoveRetryCount -lt 0) { $MoveRetryCount = 0 }

function Normalize-Path {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) { return "" }

  try {
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
  } catch {
    $resolved = $Path
  }

  return ($resolved -replace "\\", "/").TrimEnd("/").ToLowerInvariant()
}

function Normalize-Pattern {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
  return ($Value -replace "\\", "/").ToLowerInvariant()
}

function Convert-ToLongPath {
  param([string]$Path)

  if (-not $UseLongPathPrefix -or [string]::IsNullOrWhiteSpace($Path)) {
    return $Path
  }

  if ($Path.StartsWith("\\\\?\\")) {
    return $Path
  }

  if ($Path.StartsWith("\\\\")) {
    return "\\\\?\\UNC\\" + $Path.TrimStart("\\")
  }

  return "\\\\?\\" + $Path
}

function Should-IncludePath {
  param(
    [object]$File,
    [string[]]$AllowedExtensions,
    [string[]]$AllowedGlobs
  )

  $hasExtFilters = $AllowedExtensions.Count -gt 0
  $hasGlobFilters = $AllowedGlobs.Count -gt 0

  if (-not $hasExtFilters -and -not $hasGlobFilters) {
    return $true
  }

  $matchesExt = $false
  if ($hasExtFilters) {
    foreach ($ext in $AllowedExtensions) {
      if ([string]::IsNullOrWhiteSpace($ext)) { continue }
      $normalizedExt = if ($ext.StartsWith(".")) { $ext.ToLowerInvariant() } else { ".{0}" -f $ext.ToLowerInvariant() }
      if ($File.Extension.ToLowerInvariant() -eq $normalizedExt) {
        $matchesExt = $true
        break
      }
    }
  }

  $matchesGlob = $false
  if ($hasGlobFilters) {
    $candidate = Normalize-Path -Path $File.FullName
    foreach ($pattern in $AllowedGlobs) {
      $normalizedPattern = Normalize-Pattern -Value $pattern
      if ([string]::IsNullOrWhiteSpace($normalizedPattern)) { continue }
      if ($candidate -like $normalizedPattern) {
        $matchesGlob = $true
        break
      }
    }
  }

  if ($hasExtFilters -and $hasGlobFilters) {
    return $matchesExt -or $matchesGlob
  }

  if ($hasExtFilters) { return $matchesExt }
  return $matchesGlob
}

function Should-ExcludePath {
  param(
    [string]$Candidate,
    [string[]]$ExcludedRoots,
    [string[]]$ExcludedGlobs,
    [string[]]$ExcludedRegexes
  )

  $normalizedCandidate = Normalize-Path -Path $Candidate
  if ([string]::IsNullOrWhiteSpace($normalizedCandidate)) {
    return $false
  }

  foreach ($root in $ExcludedRoots) {
    $normalizedRoot = Normalize-Path -Path $root
    if ([string]::IsNullOrWhiteSpace($normalizedRoot)) {
      continue
    }

    if ($normalizedCandidate.Equals($normalizedRoot) -or $normalizedCandidate.StartsWith("$normalizedRoot/")) {
      return $true
    }
  }

  foreach ($pattern in $ExcludedGlobs) {
    $normalizedPattern = Normalize-Pattern -Value $pattern
    if ([string]::IsNullOrWhiteSpace($normalizedPattern)) {
      continue
    }

    if ($normalizedCandidate -like $normalizedPattern) {
      return $true
    }
  }

  foreach ($regexPattern in $ExcludedRegexes) {
    if ([string]::IsNullOrWhiteSpace($regexPattern)) {
      continue
    }

    if ($normalizedCandidate -match $regexPattern) {
      return $true
    }
  }

  return $false
}

function Build-FileKey {
  param(
    [string]$Path,
    [long]$Length,
    [long]$LastWriteTimeUtcTicks
  )

  return "{0}|{1}|{2}" -f (Normalize-Path -Path $Path), $Length, $LastWriteTimeUtcTicks
}

function Invoke-WithRetry {
  param(
    [scriptblock]$Operation,
    [int]$RetryCount,
    [int]$DelayMs,
    [string]$OperationName,
    [string]$Path
  )

  for ($attempt = 0; $attempt -le $RetryCount; $attempt++) {
    try {
      return [PSCustomObject]@{
        Success = $true
        Value = (& $Operation)
        Attempts = ($attempt + 1)
        Error = $null
      }
    } catch {
      if ($attempt -eq $RetryCount) {
        return [PSCustomObject]@{
          Success = $false
          Value = $null
          Attempts = ($attempt + 1)
          Error = $_
        }
      }

      Start-Sleep -Milliseconds $DelayMs
    }
  }
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$runDir = Join-Path $ReportRoot "run-$ts"
$archiveDir = Join-Path $runDir "redundant-candidates"
New-Item -ItemType Directory -Path $runDir -Force | Out-Null
New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null

$excludeRoots = @($ExcludePath + $ReportRoot + $runDir)
Write-Host "==> Excluding $($excludeRoots.Count) configured root paths"

$selectionStats = [ordered]@{
  TotalEnumerated = 0
  ExcludedByInclude = 0
  ExcludedByPathRule = 0
  Selected = 0
  HashCandidates = 0
}

Write-Host "==> Gathering files"
$rawFiles = Get-ChildItem -Path $ScanRoot -File -Recurse -ErrorAction SilentlyContinue
$selectionStats.TotalEnumerated = @($rawFiles).Count

$filteredFiles = New-Object System.Collections.Generic.List[object]
foreach ($f in $rawFiles) {
  if (-not (Should-IncludePath -File $f -AllowedExtensions $IncludeExtension -AllowedGlobs $IncludeGlob)) {
    $selectionStats.ExcludedByInclude += 1
    continue
  }

  if (Should-ExcludePath -Candidate $f.FullName -ExcludedRoots $excludeRoots -ExcludedGlobs $ExcludeGlob -ExcludedRegexes $ExcludeRegex) {
    $selectionStats.ExcludedByPathRule += 1
    continue
  }

  $filteredFiles.Add($f)
}

$files = $filteredFiles
if ($MaxFiles -gt 0) {
  $files = $files | Select-Object -First $MaxFiles
}

$totalFiles = @($files).Count
$selectionStats.Selected = $totalFiles
Write-Host "==> Files selected: $totalFiles"

$selectionStatsPath = Join-Path $runDir "selection-stats.txt"
$selectionStats.GetEnumerator() | ForEach-Object { "{0}: {1}" -f $_.Key, $_.Value } | Set-Content -Path $selectionStatsPath

$inventory = $files | Select-Object FullName, Length, Extension, LastWriteTime
$inventoryPath = Join-Path $runDir "inventory.csv"
$inventory | Export-Csv -NoTypeInformation -Path $inventoryPath

$inventoryBySizePath = Join-Path $runDir "inventory-by-size.csv"
$inventory | Sort-Object Length -Descending, FullName | Export-Csv -NoTypeInformation -Path $inventoryBySizePath

$inventoryByExtPath = Join-Path $runDir "inventory-by-extension.csv"
$inventory |
  Group-Object Extension |
  Sort-Object Count -Descending, Name |
  Select-Object Name, Count |
  Export-Csv -NoTypeInformation -Path $inventoryByExtPath

$hashCandidates = $files |
  Group-Object Length, Extension |
  Where-Object { $_.Count -gt 1 } |
  ForEach-Object { $_.Group }

$selectionStats.HashCandidates = @($hashCandidates).Count
$hashCandidatesPath = Join-Path $runDir "hash-candidates.csv"
$hashCandidates | Select-Object FullName, Length, Extension, LastWriteTime | Export-Csv -NoTypeInformation -Path $hashCandidatesPath

$cacheByKey = @{}
$cacheHits = 0
$cacheMisses = 0

if (-not $DisableHashCache -and (Test-Path -LiteralPath $HashCachePath)) {
  Write-Host "==> Loading hash cache"
  try {
    $cacheRows = Import-Csv -Path $HashCachePath
    foreach ($row in $cacheRows) {
      $cacheByKey[$row.Key] = $row.Hash
    }
    Write-Host "Loaded cache rows: $($cacheByKey.Count)"
  } catch {
    Write-Warning "Could not load cache file, proceeding without cache: $HashCachePath"
  }
}

$failureRows = New-Object System.Collections.Generic.List[object]
$failuresPath = Join-Path $runDir "failures.csv"

Write-Host "==> Hashing files (can take time)"
$hashRows = New-Object System.Collections.Generic.List[object]
$filesToHash = New-Object System.Collections.Generic.List[object]

foreach ($f in $hashCandidates) {
  $ticks = $f.LastWriteTimeUtc.Ticks
  $fileKey = Build-FileKey -Path $f.FullName -Length $f.Length -LastWriteTimeUtcTicks $ticks

  if ($cacheByKey.ContainsKey($fileKey)) {
    $cacheHits += 1
    $hashRows.Add([PSCustomObject]@{
      FullName = $f.FullName
      Length = $f.Length
      Extension = $f.Extension
      Hash = $cacheByKey[$fileKey]
      LastWriteTimeUtcTicks = $ticks
      Key = $fileKey
      HashSource = "cache"
    })
  } else {
    $cacheMisses += 1
    $filesToHash.Add([PSCustomObject]@{
      FullName = $f.FullName
      Length = $f.Length
      Extension = $f.Extension
      LastWriteTimeUtcTicks = $ticks
      Key = $fileKey
    })
  }
}

Write-Host "Cache hits: $cacheHits"
Write-Host "Cache misses: $cacheMisses"
Write-Host "Hash candidates: $($hashCandidates.Count)"

$ps7Available = $PSVersionTable.PSVersion.Major -ge 7
$useParallelHash = $ps7Available -and $HashConcurrency -gt 1
if ($useParallelHash) {
  Write-Host "==> Using parallel hashing path"

  $batchSize = [Math]::Max($ProgressEvery, $HashConcurrency)
  $processed = 0

  while ($processed -lt $filesToHash.Count) {
    $batch = $filesToHash | Select-Object -Skip $processed -First $batchSize
    $batchRows = $batch | ForEach-Object -ThrottleLimit $HashConcurrency -Parallel {
      $resolved = Convert-ToLongPath -Path $_.FullName
      try {
        $h = Get-FileHash -Algorithm SHA256 -LiteralPath $resolved
        [PSCustomObject]@{
          FullName = $_.FullName
          Length = $_.Length
          Extension = $_.Extension
          Hash = $h.Hash
          LastWriteTimeUtcTicks = $_.LastWriteTimeUtcTicks
          Key = $_.Key
          HashSource = "computed_parallel"
          Attempts = 1
        }
      } catch {
        [PSCustomObject]@{
          FullName = $_.FullName
          Length = $_.Length
          Extension = $_.Extension
          Hash = $null
          LastWriteTimeUtcTicks = $_.LastWriteTimeUtcTicks
          Key = $_.Key
          HashSource = "failed_parallel"
          Attempts = 1
          ErrorType = $_.Exception.GetType().FullName
          ErrorMessage = $_.Exception.Message
        }
      }
    }

    foreach ($row in $batchRows) {
      if ($null -eq $row) { continue }
      if ([string]::IsNullOrWhiteSpace($row.Hash)) {
        $failureRows.Add([PSCustomObject]@{
          Timestamp = (Get-Date).ToString("o")
          Operation = "hash_parallel"
          Path = $row.FullName
          Attempts = $row.Attempts
          ExceptionType = $row.ErrorType
          Message = $row.ErrorMessage
        })
        continue
      }
      $hashRows.Add($row)
    }

    $processed += $batch.Count
    Write-Host "Hashed $processed / $($filesToHash.Count) files"
  }
} else {
  if ($HashConcurrency -gt 1 -and -not $ps7Available) {
    Write-Warning "Parallel hashing requested but PowerShell < 7 detected. Falling back to serial hashing."
  }

  $hashedCount = 0
  foreach ($f in $filesToHash) {
    $resolved = Convert-ToLongPath -Path $f.FullName
    $result = Invoke-WithRetry -RetryCount $HashRetryCount -DelayMs $HashRetryDelayMs -OperationName "hash" -Path $f.FullName -Operation {
      Get-FileHash -Algorithm SHA256 -LiteralPath $resolved
    }

    if (-not $result.Success) {
      $failureRows.Add([PSCustomObject]@{
        Timestamp = (Get-Date).ToString("o")
        Operation = "hash_serial"
        Path = $f.FullName
        Attempts = $result.Attempts
        ExceptionType = $result.Error.Exception.GetType().FullName
        Message = $result.Error.Exception.Message
      })
      continue
    }

    $hashedCount += 1
    if (($hashedCount % $ProgressEvery) -eq 0 -or $hashedCount -eq $filesToHash.Count) {
      Write-Host "Hashed $hashedCount / $($filesToHash.Count) files"
    }
    $hashRows.Add([PSCustomObject]@{
      FullName = $f.FullName
      Length = $f.Length
      Extension = $f.Extension
      Hash = $result.Value.Hash
      LastWriteTimeUtcTicks = $f.LastWriteTimeUtcTicks
      Key = $f.Key
      HashSource = "computed_serial"
      Attempts = $result.Attempts
    })
  }
}

$cacheStatsPath = Join-Path $runDir "cache-stats.txt"
@(
  "Cache hits: $cacheHits",
  "Cache misses: $cacheMisses",
  "Hash rows emitted: $($hashRows.Count)",
  "Failure rows emitted: $($failureRows.Count)",
  "Hash candidates: $($hashCandidates.Count)"
) | Set-Content -Path $cacheStatsPath

if (-not $DisableHashCache) {
  Write-Host "==> Writing hash cache"
  $cacheDir = Split-Path -Parent $HashCachePath
  if (-not [string]::IsNullOrWhiteSpace($cacheDir)) {
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
  }

  $cacheOut = $hashRows |
    Group-Object Key |
    ForEach-Object {
      $item = $_.Group | Select-Object -First 1
      [PSCustomObject]@{
        Key = $item.Key
        Hash = $item.Hash
      }
    }

  $cacheOut | Sort-Object Key | Export-Csv -NoTypeInformation -Path $HashCachePath
}

if ($failureRows.Count -gt 0) {
  $failureRows | Export-Csv -NoTypeInformation -Path $failuresPath
}

$hashPath = Join-Path $runDir "file-hashes.csv"
$hashRows |
  Sort-Object Hash, Length, FullName |
  Select-Object FullName, Length, Extension, Hash, HashSource, Attempts |
  Export-Csv -NoTypeInformation -Path $hashPath

$dupes = $hashRows |
  Group-Object Hash |
  Where-Object { $_.Count -gt 1 }

$dupeCandidates = foreach ($group in $dupes) {
  $sorted = $group.Group | Sort-Object Length, FullName
  $keeper = $sorted[0]
  if ($sorted.Count -gt 1) {
    foreach ($item in $sorted[1..($sorted.Count - 1)]) {
      [PSCustomObject]@{
        Keep = $keeper.FullName
        Candidate = $item.FullName
        Hash = $item.Hash
        Length = $item.Length
      }
    }
  }
}

$dupePath = Join-Path $runDir "duplicate-candidates.csv"
$dupeCandidates |
  Sort-Object Length -Descending, Hash, Candidate |
  Export-Csv -NoTypeInformation -Path $dupePath

Write-Host "==> Duplicate candidates: $($dupeCandidates.Count)"
Write-Host "==> Report: $runDir"
Write-Host "==> Share summary with this command: Get-Content -Path (Join-Path '$runDir' 'selection-stats.txt'); Get-Content -Path (Join-Path '$runDir' 'cache-stats.txt'); if (Test-Path (Join-Path '$runDir' 'failures.csv')) { Import-Csv (Join-Path '$runDir' 'failures.csv') | Group-Object ExceptionType | Sort-Object Count -Descending | Select-Object -First 10 }"

if (-not $Apply) {
  Write-Host "Dry run only. Re-run with -Apply to move duplicate candidates into: $archiveDir"
  exit 0
}

$bytesToMove = ($dupeCandidates | Measure-Object -Property Length -Sum).Sum
if ($null -eq $bytesToMove) { $bytesToMove = 0 }

$driveInfo = Get-PSDrive -Name ([IO.Path]::GetPathRoot($archiveDir).TrimEnd(':\\/')) -ErrorAction SilentlyContinue
$freeBytes = if ($null -eq $driveInfo) { 0 } else { [double]$driveInfo.Free }
$requiredHeadroomBytes = [double]$RequirePreflightHeadroomGB * 1GB

$preflightPath = Join-Path $runDir "apply-preflight.txt"
@(
  "Candidate count: $($dupeCandidates.Count)",
  "Bytes to move: $bytesToMove",
  "Archive free bytes: $freeBytes",
  "Required headroom bytes: $requiredHeadroomBytes",
  "WhatIfApply: $WhatIfApply"
) | Set-Content -Path $preflightPath

if (($freeBytes - $bytesToMove) -lt $requiredHeadroomBytes) {
  throw "Preflight failed: insufficient free space/headroom. See $preflightPath"
}

Write-Host "==> APPLY MODE: moving duplicate candidates"
$manifestPath = Join-Path $runDir "move-manifest.csv"
$manifestRows = New-Object System.Collections.Generic.List[object]

foreach ($row in $dupeCandidates) {
  $src = $row.Candidate
  if (-not (Test-Path -LiteralPath $src)) {
    $manifestRows.Add([PSCustomObject]@{
      Timestamp = (Get-Date).ToString("o")
      Source = $src
      Destination = ""
      Hash = $row.Hash
      Status = "skipped_missing"
    })
    continue
  }

  $pathHash = $row.Hash.Substring(0, 12)
  $safePath = ($src -replace "[:\\/]", "_")
  $baseName = "{0}_{1}" -f $pathHash, $safePath
  $dest = Join-Path $archiveDir $baseName

  $suffix = 1
  while (Test-Path -LiteralPath $dest) {
    $dest = Join-Path $archiveDir ("{0}-{1}" -f $baseName, $suffix)
    $suffix += 1
  }

  if ($WhatIfApply) {
    Write-Host "WhatIf apply: $src -> $dest"
    $manifestRows.Add([PSCustomObject]@{
      Timestamp = (Get-Date).ToString("o")
      Source = $src
      Destination = $dest
      Hash = $row.Hash
      Status = "whatif"
    })
    $manifestRows | Export-Csv -NoTypeInformation -Path $manifestPath
    continue
  }

  $srcResolved = Convert-ToLongPath -Path $src
  $moveResult = Invoke-WithRetry -RetryCount $MoveRetryCount -DelayMs $MoveRetryDelayMs -OperationName "move" -Path $src -Operation {
    Move-Item -LiteralPath $srcResolved -Destination $dest
  }

  if ($moveResult.Success) {
    Write-Host "Moved candidate: $src -> $dest"
    $manifestRows.Add([PSCustomObject]@{
      Timestamp = (Get-Date).ToString("o")
      Source = $src
      Destination = $dest
      Hash = $row.Hash
      Status = "moved"
    })
  } else {
    Write-Warning "Failed to move candidate: $src"
    $manifestRows.Add([PSCustomObject]@{
      Timestamp = (Get-Date).ToString("o")
      Source = $src
      Destination = $dest
      Hash = $row.Hash
      Status = "move_failed"
    })

    $failureRows.Add([PSCustomObject]@{
      Timestamp = (Get-Date).ToString("o")
      Operation = "move"
      Path = $src
      Attempts = $moveResult.Attempts
      ExceptionType = $moveResult.Error.Exception.GetType().FullName
      Message = $moveResult.Error.Exception.Message
    })
    $failureRows | Export-Csv -NoTypeInformation -Path $failuresPath
  }

  $manifestRows | Export-Csv -NoTypeInformation -Path $manifestPath
}

$rollbackScriptPath = Join-Path $runDir "rollback-moves.ps1"
$rollbackScript = @"
param(
  [string]`$ManifestPath = "$manifestPath"
)

`$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath `$ManifestPath)) {
  throw "Manifest not found: `$ManifestPath"
}

`$rows = Import-Csv -Path `$ManifestPath |
  Where-Object { `$_.Status -eq "moved" } |
  Sort-Object Timestamp -Descending

foreach (`$row in `$rows) {
  if ((Test-Path -LiteralPath `$row.Destination) -and -not (Test-Path -LiteralPath `$row.Source)) {
    Move-Item -LiteralPath `$row.Destination -Destination `$row.Source
    Write-Host "Rolled back: `$(`$row.Destination) -> `$(`$row.Source)"
  }
}
"@
$rollbackScript | Set-Content -Path $rollbackScriptPath

Write-Host "Move manifest: $manifestPath"
Write-Host "Rollback helper: $rollbackScriptPath"
Write-Host "Preflight report: $preflightPath"
if ($failureRows.Count -gt 0) {
  Write-Host "Failure report: $failuresPath"
}
Write-Host "Done. Candidates moved to: $archiveDir"
'''
