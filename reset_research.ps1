[CmdletBinding()]
param(
    [switch]$Force
)

# Reset only the experimental state. It intentionally preserves the current
# robot, benchmark implementation, learning code, parameters, and decision log.

Set-Location $PSScriptRoot

function Push-CurrentCommit {
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "The reset commit was created locally but could not be pushed to origin."
    }
}

if (-not $Force) {
    throw "This clears the active research history and model lineages. Run .\reset_research.ps1 -Force to confirm."
}

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
    return $path
}

function Remove-ResetPath([string]$relativePath) {
    $path = Get-ResetPath $relativePath
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

Remove-ResetPath "models\candidates"
Remove-ResetPath "research\checkpoints"

$ephemeralPaths = @(
    "research\GOAL_REACHED",
    "research\RECOVERY_PENDING",
    "research\RESTART_PENDING",
    "research\proposal.json",
    "research\evaluation_request.json",
    "research\training_logs",
    "research\last_evaluation.json",
    "research\brief.md"
)
$ephemeralPaths | ForEach-Object { Remove-ResetPath $_ }

# Generate new campaign identity before reset
$campaignId = [guid]::NewGuid().ToString()
$baseCommit = git rev-parse HEAD 2>$null
if ($LASTEXITCODE -ne 0 -or -not $baseCommit) {
    throw "Could not resolve the campaign base commit."
}
$baseCommit = $baseCommit.Trim()
$startedAt = [System.DateTime]::UtcNow.ToString("o")

[ordered]@{
    schema_version = 3
    accepted_artifact = "research\checkpoints\accepted"
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

$resetPaths = @(
    "research\EXPERIMENTS.md",
    "research\results.jsonl",
    "research\postmortems.md",
    "research\archive.md",
    "research\research_state.json",
    "research\BASELINE_PENDING",
    "research\checkpoints"
) + $ephemeralPaths
$stageable = @()
foreach ($relativePath in $resetPaths) {
    if ((Test-Path -LiteralPath $relativePath) -or (git ls-files -- $relativePath)) {
        $stageable += $relativePath
    }
}
if ($stageable.Count -gt 0) {
    git add -A -- $stageable
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stage the reset state."
    }
}
git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    git commit -m "reset research experiment state"
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
Write-Host "The current code and parameters were preserved. A fresh baseline is pending."
