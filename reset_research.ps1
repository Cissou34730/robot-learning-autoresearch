<#
.SYNOPSIS
Reset the current branch, either fresh or from a prepared baseline.
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -Force
.EXAMPLE
.\reset_research.ps1 -Mode Baseline -BaselineRef my-baseline -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet("Fresh", "Baseline")][string]$Mode,
    [string]$BaselineRef,
    [string]$TrainingLogSource = $PSScriptRoot,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-ResetGit([string[]]$Arguments) {
    $output = & git @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed." }
    return $output
}

function Push-CurrentCommit {
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "The reset commit was created locally but could not be pushed to origin."
    }
}

if (-not $Force) {
    throw "Stop the campaign first. This replaces its state and models in the current branch. Specify -Mode Fresh or -Mode Baseline and -Force to confirm."
}
if (($Mode -eq "Baseline" -and -not $BaselineRef) -or
    ($Mode -eq "Fresh" -and ($BaselineRef -or $PSBoundParameters.ContainsKey("TrainingLogSource")))) {
    throw "Baseline requires -BaselineRef. Fresh accepts neither -BaselineRef nor -TrainingLogSource."
}
Invoke-ResetGit @("symbolic-ref", "--quiet", "--short", "HEAD") | Out-Null
Invoke-ResetGit @("remote", "get-url", "origin") | Out-Null

$dirty = git status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) {
    throw "Could not inspect the Git working tree."
}
if ($dirty) {
    throw "The working tree is not clean. Commit or resolve its changes before resetting research."
}

$workspaceRoot = (Resolve-Path -LiteralPath $PSScriptRoot).Path

function Get-ResetPath([string]$relativePath) {
    $path = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $relativePath))
    $prefix = $workspaceRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe reset path: $relativePath"
    }
    # Do not traverse a junction/symlink into another workspace during cleanup.
    $cursor = $path
    while ($cursor -ne $workspaceRoot) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -Force -LiteralPath $cursor).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Reset refuses linked paths: $cursor"
            }
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $path
}

function Remove-ResetPath([string]$relativePath) {
    $path = Get-ResetPath $relativePath
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

$ephemeralPaths = @(
    "research\GOAL_REACHED",
    "research\RECOVERY_PENDING",
    "research\RESTART_PENDING",
    "research\proposal.json",
    "research\evaluation_request.json",
    "research\training_logs",
    "research\evaluations",
    "research\last_train_summary.md",
    "research\last_evaluation.json",
    "research\brief.md"
)
$resetPaths = @(
    "research/EXPERIMENTS.md", "research/results.jsonl", "research/postmortems.md",
    "research/archive.md", "research/research_state.json", "research/BASELINE_PENDING",
    "research/checkpoints"
) + $ephemeralPaths
$cleanupPaths = @("models/candidates", "research/checkpoints", "research/BASELINE_PENDING") + $ephemeralPaths
$resetPaths += "models/candidates"
$restorePaths = @()
$sourceLogs = @()
$versionedLogs = @()
$logBackup = $null
$baseCommit = (Invoke-ResetGit @("rev-parse", "HEAD")).Trim()

if ($Mode -eq "Baseline") {
    $baselineCommit = (Invoke-ResetGit @("rev-parse", "--verify", "--end-of-options", "$BaselineRef^{commit}")).Trim()
    function Read-BaselineJson([string]$Path) {
        return ((Invoke-ResetGit @("show", "${baselineCommit}:$Path")) -join "`n" | ConvertFrom-Json)
    }
    $state = Read-BaselineJson "research/research_state.json"
    if ($state.last_experiment -ne 1 -or $state.last_allocated_experiment -ne 1 -or
        $null -eq $state.accepted_metrics -or $state.accepted_artifact -ne "research/checkpoints/accepted" -or
        $state.pending_evaluation_request -or $state.pending_researcher_decision -or
        $state.pending_scientific_parent -or $state.pending_final_benchmark -or
        $state.official_metrics -or @($state.retained_lineages).Count -gt 0) {
        throw "BaselineRef must be a closed, measured baseline before experiment 2, without pending operations or retained alternatives."
    }
    $campaignId = [string]$state.campaign.id
    $parsedId = [guid]::Empty
    if (-not [guid]::TryParse($campaignId, [ref]$parsedId)) { throw "Baseline has no valid campaign UUID." }
    if ($state.campaign_experiment_counters -and $state.campaign_experiment_counters.$campaignId -gt 1) {
        throw "Baseline contains later experiment allocations."
    }
    $baselineFiles = @(Invoke-ResetGit @("ls-tree", "-r", "--name-only", $baselineCommit))
    $currentFiles = @(Invoke-ResetGit @("ls-files"))
    $required = @(
        "research/checkpoints/accepted/model.zip", "research/checkpoints/accepted/artifact.json",
        "research/checkpoints/accepted/policy_runtime.pkl", "robot_learning/scenario/policy_io.py",
        "research/current_params.json", "research/results.jsonl", "research/postmortems.md", "research/scenario.md"
    ) + @($state.accepted_evaluations)
    if (@($state.accepted_evaluations).Count -eq 0) { throw "Baseline has no completed evaluation evidence." }
    foreach ($path in $required) {
        Get-ResetPath $path | Out-Null
        if ($path -notin $baselineFiles) {
            throw "BaselineRef is missing $path. Legacy policies must be explicitly migrated before preparing a baseline."
        }
    }
    foreach ($path in $state.accepted_evaluations) {
        if (-not $path.StartsWith("research/evaluations/$campaignId/")) { throw "Baseline evidence is outside its campaign." }
    }
    if ("research/BASELINE_PENDING" -in $baselineFiles -or
        -not (Read-BaselineJson "research/checkpoints/accepted/artifact.json").completed) {
        throw "Baseline training is not complete."
    }
    Read-BaselineJson "research/current_params.json" | Out-Null
    $records = @(Invoke-ResetGit @("show", "${baselineCommit}:research/results.jsonl") |
        Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.campaign_id -eq $campaignId })
    if ($records.Count -eq 0 -or @($records | Where-Object { $_.index -ne 1 }).Count -gt 0) {
        throw "Baseline history must contain only experiment 1 in its active campaign."
    }

    # Scientific files and their tests travel together. Never restore the entire
    # robot_learning tree: that would undo the current protected runtime/evaluators.
    $scientificPrefixes = @("robot_learning/scenario/", "robot_learning/training/", "tests/scenario/", "tests/training/")
    $scientificFiles = @("robot_learning/train.py", "robot_learning/evaluate.py", "robot_learning/play.py",
        "research/scenario.md", "research/current_params.json")
    $protectedAdapters = @("robot_learning/scenario/__init__.py", "robot_learning/scenario/final_benchmark.py", "robot_learning/scenario/task_reference.py")
    $allFiles = @($baselineFiles + $currentFiles | Sort-Object -Unique)
    $restorePaths = @($allFiles | Where-Object {
        $file = $_
        $file -notin $protectedAdapters -and ($file -in $scientificFiles -or
            @($scientificPrefixes | Where-Object { $file.StartsWith($_) }).Count -gt 0)
    })
    # Reusing evidence is meaningful only for the same human-defined task.
    $taskPaths = @($allFiles | Where-Object {
        $_.StartsWith("robot_learning/robots/") -or $_ -in @(
            "robot_learning/benchmark/final_contract.py", "robot_learning/benchmark/reference_contract.py", "robot_learning/benchmark/spec.py")
    })
    if ($taskPaths.Count -gt 0 -and (Invoke-ResetGit (@("diff", "--name-only", $baselineCommit, "HEAD", "--") + $taskPaths))) {
        throw "The human-defined task differs from this baseline. Use a baseline prepared for the current task."
    }
    $evidencePaths = @($baselineFiles | Where-Object { $_.StartsWith("research/evaluations/$campaignId/") })
    $statePaths = @("research/research_state.json", "research/results.jsonl", "research/EXPERIMENTS.md",
        "research/postmortems.md", "research/archive.md", "research/checkpoints")
    $restorePaths += @($statePaths | Where-Object {
        $prefix = $_
        @($allFiles | Where-Object { $_ -eq $prefix -or $_.StartsWith("$prefix/") }).Count -gt 0
    }) + $evidencePaths
    $logRelative = "research/training_logs/$campaignId"
    $versionedLogs = @($baselineFiles | Where-Object { $_ -match "^$logRelative/experiment-1-attempt-\d+\.log$" })
    if ($versionedLogs.Count -eq 0) {
        $logDirectory = Join-Path $TrainingLogSource $logRelative
        if (Test-Path -LiteralPath $logDirectory) {
            $sourceLogs = @(Get-ChildItem -LiteralPath $logDirectory -File |
                Where-Object { $_.Name -match '^experiment-1-attempt-\d+\.log$' })
        }
        if ($sourceLogs.Count -eq 0) { throw "Baseline training logs are missing from $logDirectory. Supply -TrainingLogSource if needed." }
    }
    $restorePaths += $versionedLogs
    # Git cannot safely materialize repository links as reset targets.
    if (@(Invoke-ResetGit (@("ls-tree", "-r", $baselineCommit, "--") + $restorePaths) |
        Where-Object { $_ -match '^(120000|160000) ' }).Count -gt 0) {
        throw "Baseline contains symlinks or submodules in the restoration surface."
    }
}

# Validate every target (including ignored descendants) and detect existing file
# locks before deleting anything. The campaign must remain stopped throughout.
foreach ($relative in @($cleanupPaths + $resetPaths + $restorePaths | Sort-Object -Unique)) {
    $path = Get-ResetPath $relative
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $items = @(Get-Item -Force -LiteralPath $path)
    if ($items[0].PSIsContainer) { $items += @(Get-ChildItem -Force -Recurse -LiteralPath $path) }
    foreach ($item in $items) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reset refuses linked paths: $($item.FullName)" }
        if (-not $item.PSIsContainer) {
            $handle = [IO.File]::Open($item.FullName, 'Open', 'Read', 'None')
            $handle.Dispose()
        }
    }
}

if ($sourceLogs.Count -gt 0) {
    $logBackup = Join-Path ([IO.Path]::GetTempPath()) ("research-reset-logs-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $logBackup | Out-Null
    foreach ($log in $sourceLogs) {
        $target = Join-Path $logBackup $log.Name
        Copy-Item -LiteralPath $log.FullName -Destination $target
        if ((Get-FileHash -LiteralPath $log.FullName).Hash -ne (Get-FileHash -LiteralPath $target).Hash) {
            throw "Baseline log changed while copying. Backup retained at $logBackup"
        }
    }
    Write-Host "Baseline log backup (retained if reset fails): $logBackup"
}
$cleanupPaths | ForEach-Object { Remove-ResetPath $_ }

if ($Mode -eq "Fresh") {

# Generate new campaign identity before reset
$campaignId = [guid]::NewGuid().ToString()
$startedAt = [System.DateTime]::UtcNow.ToString("o")

[ordered]@{
    schema_version = 3
    accepted_artifact = "research/checkpoints/accepted"
    accepted_metrics = $null
    accepted_parameters = $null
    accepted_training_steps = 0
    campaign = [ordered]@{
        id = $campaignId
        started_at = $startedAt
        base_commit = $baseCommit
    }
    retained_lineages = @()
    last_experiment = 0
    last_allocated_experiment = 0
    pending_scientific_parent = $null
    last_verdict = "baseline pending after research reset"
    official_metrics = $null
} | ConvertTo-Json | Set-Content -LiteralPath "research\research_state.json"

@(
    "# Experiment log",
    "",
    "| # | Date | Change | Hypothesis | Candidate success | Seeds passed | Verdict |",
    "|---:|---|---|---|---:|---:|---|"
) | Set-Content -LiteralPath "research\EXPERIMENTS.md"

@("# Research postmortems", "", "No experiments recorded.") |
    Set-Content -LiteralPath "research\postmortems.md"
@("# Research archive", "", "No archived experiments.") |
    Set-Content -LiteralPath "research\archive.md"
Set-Content -LiteralPath "research\results.jsonl" -Value $null
Set-Content -LiteralPath "research\BASELINE_PENDING" -Value "Fresh baseline pending after explicit research reset."
}
else {
    Invoke-ResetGit (@("restore", "--source=$baselineCommit", "--staged", "--worktree", "--") + $restorePaths) | Out-Null
    if ($logBackup) {
        $targetLogs = Get-ResetPath $logRelative
        New-Item -ItemType Directory -Path $targetLogs -Force | Out-Null
        Get-ChildItem -LiteralPath $logBackup -File | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $targetLogs $_.Name)
        }
        # Freeze ignored source logs in Git; subsequent resets need only BaselineRef.
        Invoke-ResetGit @("add", "-f", "--", $logRelative) | Out-Null
    }
}
$stageable = @()
foreach ($relativePath in $resetPaths) {
    if ((Test-Path -LiteralPath $relativePath) -or (git ls-files -- $relativePath)) {
        $stageable += $relativePath
    }
}
if ($stageable.Count -gt 0) {
    # Only the explicit reset-state paths are staged. Baseline logs were rebuilt
    # above and must be included even though normal live logs are ignored.
    git add -A -f -- $stageable
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stage the reset state."
    }
}
git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    $message = if ($Mode -eq "Fresh") { "reset research experiment state: fresh" } else { "reset research experiment state: baseline $baselineCommit" }
    git commit -m $message
    if ($LASTEXITCODE -ne 0) {
        throw "The reset state was prepared but could not be committed."
    }
    Push-CurrentCommit
}
elseif ($LASTEXITCODE -ne 0) {
    throw "Could not inspect the staged reset state."
}

$remainingChanges = git status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) {
    throw "Could not verify the Git working tree after the reset."
}
if ($remainingChanges) {
    throw "Research state was reset, but the Git working tree is not clean."
}

Write-Host "=== Research state reset ==="
if ($logBackup) {
    # Exact directory created above, never a computed campaign or workspace root.
    $resolvedBackup = (Resolve-Path -LiteralPath $logBackup).Path
    if ($resolvedBackup -ne [IO.Path]::GetFullPath($logBackup) -or
        (Split-Path -Parent $resolvedBackup).TrimEnd('\', '/') -ne ([IO.Path]::GetTempPath()).TrimEnd('\', '/') -or
        (Get-Item -LiteralPath $resolvedBackup).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Unsafe temporary log cleanup path; backup retained at $logBackup"
    }
    Remove-Item -LiteralPath $logBackup -Recurse -Force
}
if ($Mode -eq "Fresh") {
    Write-Host "The current code and parameters were preserved. A fresh baseline is pending."
}
else {
    Write-Host "Prepared baseline restored from $baselineCommit in the current branch."
    Write-Host "The current harness was preserved. Baseline evidence is restored; the next experiment is 2."
}
Write-Host "No training was launched."
