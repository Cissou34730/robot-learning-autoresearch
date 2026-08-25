# Autonomous RL research loop.
# Runs one fresh opencode session per experiment until research/GOAL_REACHED exists.

Set-Location $PSScriptRoot

while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Host "GOAL REACHED - research loop finished."
        break
    }
    if (Test-Path "research\STAGNATED") {
        Write-Host "STAGNATED - no progress in recent experiments; research loop finished."
        Write-Host "Read research\STAGNATED for the diagnosis and recommended next steps."
        break
    }

    Write-Host "=== New experiment starting at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    opencode run "Read research/program.md and execute exactly one experiment following its protocol."

    Write-Host "=== Experiment session ended at $(Get-Date -Format 'HH:mm:ss') ==="
    Start-Sleep -Seconds 5
}
