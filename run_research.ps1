# Token-efficient autonomous RL research loop.
# Uses a fresh session for each experiment and escalates model capability only
# for structural work or recovery from an invalid run.

Set-Location $PSScriptRoot

function Update-ResearchBrief {
    uv run python research/build_research_brief.py
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build the compact research brief."
    }
}

while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Host "GOAL REACHED - research loop finished."
        break
    }

    Update-ResearchBrief

    $model = "github-copilot/gpt-5.6-luna"
    $reasoning = "medium"
    $state = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    $complexClasses = @(
        "reward structure",
        "observation representation",
        "training curriculum",
        "policy architecture and training schedule",
        "learning algorithm",
        "learning algorithm (e.g. PPO vs SAC)",
        "broader goal-preserving training-method changes"
    )
    $lastRow = Get-Content "research\EXPERIMENTS.md" |
        Where-Object { $_ -match '^\| \d+ \|' } |
        Select-Object -Last 1

    if (($complexClasses -contains [string]$state.hypothesis_class) -or
        ($lastRow -match '\| error \(')) {
        $model = "github-copilot/gpt-5.6-terra"
    }
    if ($env:RESEARCH_MODEL) {
        $model = $env:RESEARCH_MODEL
    }
    if ($env:RESEARCH_REASONING) {
        $reasoning = $env:RESEARCH_REASONING
    }

    Write-Host "=== New experiment at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    Write-Host "Model: $model, reasoning: $reasoning"
    opencode run --model $model --variant $reasoning "Read research/program.md and execute exactly one experiment following its protocol."

    Update-ResearchBrief
    Write-Host "=== Experiment session ended at $(Get-Date -Format 'HH:mm:ss') ==="
    Start-Sleep -Seconds 5
}
