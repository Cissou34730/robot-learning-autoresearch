<#
.SYNOPSIS
Reset the current campaign, optionally restoring a scientific recipe first.
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -RecipeRef <git-ref> -Force
.EXAMPLE
.\reset_research.ps1 -Mode Fresh -Force
.EXAMPLE
.\reset_research.ps1 -Mode Baseline -BaselineRef <git-ref> -Force
.EXAMPLE
.\reset_research.ps1 -Recover <operation.json> -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory, ParameterSetName = "Reset")]
    [ValidateSet("Fresh", "Baseline")][string]$Mode,
    [Parameter(Mandatory, ParameterSetName = "Recover")][string]$Recover,
    [string]$RecipeRef,
    [string]$BaselineRef,
    [string]$TrainingLogSource = $PSScriptRoot,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $Force) {
    throw "Stop the campaign first and pass -Force to confirm the reset or recovery."
}
if ($Recover -and ($RecipeRef -or $BaselineRef -or $PSBoundParameters.ContainsKey("TrainingLogSource"))) {
    throw "Recovery accepts -Recover and -Force only."
}
if (-not $Recover -and $Mode -eq "Fresh" -and ($BaselineRef -or $PSBoundParameters.ContainsKey("TrainingLogSource"))) {
    throw "Fresh accepts optional -RecipeRef only; -BaselineRef and -TrainingLogSource are Baseline-only."
}
if ($Mode -eq "Baseline" -and (-not $BaselineRef -or $RecipeRef)) {
    throw "Baseline requires -BaselineRef and does not accept -RecipeRef."
}

# The launcher derives the same worktree-scoped name, so a loop running in this
# checkout is still excluded while another checkout stays free to run its own.
. "$PSScriptRoot\researcher_mutex.ps1"

$createdNew = $false
$campaignMutex = [System.Threading.Mutex]::new(
    $true,
    (Get-WorktreeMutexName -Worktree $PSScriptRoot),
    [ref]$createdNew
)
if (-not $createdNew) {
    $campaignMutex.Dispose()
    throw "Another robot autoresearch loop or reset is already running in this worktree."
}

try {
    if ($Recover) {
        $arguments = @("--recover", $Recover)
    }
    else {
        $arguments = @("--mode", $Mode.ToLowerInvariant())
        if ($RecipeRef) { $arguments += @("--recipe-ref", $RecipeRef) }
        if ($BaselineRef) { $arguments += @("--baseline-ref", $BaselineRef) }
        if ($Mode -eq "Baseline" -and $TrainingLogSource) {
            $arguments += @("--training-log-source", $TrainingLogSource)
        }
    }
    uv run python research/reset_campaign.py @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Research reset failed. Review the reported recovery information before retrying."
    }
}
finally {
    $campaignMutex.ReleaseMutex()
    $campaignMutex.Dispose()
}
