<#
.SYNOPSIS
Reset the current campaign, optionally restoring a scientific recipe first.
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -RecipeRef <git-ref> -Force
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -Force
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -Clean -Force
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -RecipeRef <git-ref> -Clean -Force
.EXAMPLE
.\reset_research.ps1 -Mode Baseline -BaselineRef <git-ref> -Force
#>
[CmdletBinding()]
param(
    [string]$CampaignRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "robot-learning-campaigns"),
    [Parameter(Mandatory)]
    [ValidateSet("Fresh", "Baseline")][string]$Mode,
    [string]$RecipeRef,
    [string]$BaselineRef,
    [switch]$Clean,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Push-Location -LiteralPath $PSScriptRoot
try {

if (-not $Force) {
    throw "Stop the campaign first and pass -Force to confirm the reset."
}
if ($Mode -eq "Fresh" -and $BaselineRef) {
    throw "Fresh accepts optional -RecipeRef only; -BaselineRef is Baseline-only."
}
if ($Mode -eq "Baseline" -and (-not $BaselineRef -or $RecipeRef)) {
    throw "Baseline requires -BaselineRef and does not accept -RecipeRef."
}

# The launcher derives the same worktree-scoped name, so a loop running in this
# checkout is still excluded while another checkout stays free to run its own.
. "$PSScriptRoot\researcher_mutex.ps1"
Set-ResearchPaths -HarnessRoot $PSScriptRoot -CampaignRoot $CampaignRoot
$CampaignRoot = (Get-Location).Path

$createdNew = $false
$campaignMutex = [System.Threading.Mutex]::new(
    $true,
    (Get-WorktreeMutexName -Worktree $CampaignRoot),
    [ref]$createdNew
)
if (-not $createdNew) {
    $campaignMutex.Dispose()
    throw "Another robot autoresearch loop or reset is already running in this worktree."
}

try {
    $arguments = @("--mode", $Mode.ToLowerInvariant())
    if ($RecipeRef) { $arguments += @("--recipe-ref", $RecipeRef) }
    if ($BaselineRef) { $arguments += @("--baseline-ref", $BaselineRef) }
    if ($Clean) { $arguments += "--clean" }
    uv run --project $PSScriptRoot python -m runner.reset_campaign @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Research reset failed. Review the reported error and starting commit before retrying."
    }
}
finally {
    $campaignMutex.ReleaseMutex()
    $campaignMutex.Dispose()
}
}
finally {
    Pop-Location
}
