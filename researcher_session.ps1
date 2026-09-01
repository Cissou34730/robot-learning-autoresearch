# Observation of a bounded Researcher session, as three independent facts: the
# process outcome, the presence of the deliverable it was asked to produce, and
# that deliverable's validity. Nothing here reads what the Researcher printed,
# so it stays true whatever command invokes the Researcher.

function Write-Status {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan,
        [string]$Label = ""
    )
    if (-not $Label) {
        $Label = switch ($Color) {
            Green { "done" }
            Yellow { "wait" }
            default { "run" }
        }
    }
    $text = $Message -replace '^===\s*|\s*===$', ''
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] " -ForegroundColor DarkGray -NoNewline
    Write-Host "[$Label]" -ForegroundColor $Color -NoNewline
    Write-Host " $text"
}

function New-ResearcherSessionStatus {
    param(
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][int]$Attempt,
        [AllowNull()][object]$ExitCode,
        [Parameter(Mandatory)][string]$Deliverable,
        [bool]$Present,
        [bool]$Valid,
        [string]$Reason = ""
    )
    $validity = if (-not $Present) {
        "not run"
    }
    elseif ($Valid) {
        "valid"
    }
    else {
        "invalid"
    }
    [pscustomobject]@{
        Phase       = $Phase
        Attempt     = $Attempt
        ExitCode    = $ExitCode
        Deliverable = $Deliverable
        Present     = $Present
        Validity    = $validity
        Reason      = $Reason
        # The deliverable contract closes a bounded phase. The process's opinion
        # of its own success neither completes nor invalidates it.
        Complete    = ($Present -and $Valid)
    }
}

function Write-ResearcherSessionStatus {
    param([Parameter(Mandatory)][psobject]$Status)
    $exitText = if ($null -eq $Status.ExitCode) {
        "unavailable"
    }
    else {
        [string]$Status.ExitCode
    }
    if ($Status.Complete -and $exitText -eq "0") {
        Write-Status (
            "Researcher session: $($Status.Phase), attempt $($Status.Attempt): " +
            "process=$exitText, $($Status.Deliverable)=$($Status.Validity)"
        ) Green
        return
    }
    $presence = if ($Status.Present) { "present" } else { "missing" }
    Write-Status "=== Researcher session - $($Status.Phase) - attempt $($Status.Attempt) ===" Yellow
    Write-Host "Process exit : $exitText"
    Write-Host "Deliverable  : $($Status.Deliverable) ($presence)"
    Write-Host "Validation   : $($Status.Validity)"
    if ($Status.Reason) {
        Write-Host "Reason       : $($Status.Reason)"
    }
}
