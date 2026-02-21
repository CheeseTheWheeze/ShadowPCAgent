from shadowpcagent.powershell import build_inventory_and_dedupe_script


def test_cleanup_script_includes_controls_and_selection_logic() -> None:
    script = build_inventory_and_dedupe_script()
    assert "[string[]]$ExcludePath" in script
    assert "[string[]]$ExcludeGlob" in script
    assert "[string[]]$ExcludeRegex" in script
    assert "[string[]]$IncludeExtension" in script
    assert "[string[]]$IncludeGlob" in script
    assert "[int]$HashConcurrency = 1" in script
    assert "function Should-IncludePath" in script
    assert "selection-stats.txt" in script
    assert "hash-candidates.csv" in script


def test_cleanup_script_includes_parallel_hashing_cache_and_retries() -> None:
    script = build_inventory_and_dedupe_script()
    assert "$HashCachePath" in script
    assert "$useParallelHash" in script
    assert "ForEach-Object -ThrottleLimit $HashConcurrency -Parallel" in script
    assert "function Invoke-WithRetry" in script
    assert "HashRetryCount" in script
    assert "MoveRetryCount" in script
    assert "UseLongPathPrefix" in script


def test_cleanup_script_includes_preflight_manifest_rollback_and_failures() -> None:
    script = build_inventory_and_dedupe_script()
    assert "apply-preflight.txt" in script
    assert "WhatIfApply" in script
    assert "move-manifest.csv" in script
    assert "rollback-moves.ps1" in script
    assert "failures.csv" in script
    assert "Preflight failed: insufficient free space/headroom" in script


def test_cleanup_script_normalizes_selected_files_to_array_for_counting() -> None:
    script = build_inventory_and_dedupe_script()
    assert "$files = @($filteredFiles)" in script
    assert "$files = @($files | Select-Object -First $MaxFiles)" in script
    assert "$totalFiles = $files.Count" in script
