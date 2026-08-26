# Token-efficient autonomous robot-learning loop.

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

    if (Test-Path "research\BASELINE_PENDING") {
        Write-Host "=== Running automatic curriculum baseline ==="
        @{
            baseline = $true
            change = "Unchanged control using the transfer checkpoint and current curriculum"
            hypothesis = "Establish the fixed-evaluator baseline for the current curriculum."
            class = "baseline"
            initialization = "transfer"
        } | ConvertTo-Json | Set-Content "research\proposal.json"

        uv run python research/run_experiment.py
        if ($LASTEXITCODE -ne 0) {
            throw "Baseline failed. The research loop stopped instead of silently continuing."
        }
        Update-ResearchBrief
        Write-Host "=== Baseline complete ==="
        continue
    }

    Update-ResearchBrief

    $model = "github-copilot/gpt-5.6-luna"
    $reasoning = "medium"
    $lastRow = Get-Content "research\EXPERIMENTS.md" |
        Where-Object { $_ -match '^\| \d+ \|' } |
        Select-Object -Last 1

    if ($lastRow -match '\| error \(') {
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
