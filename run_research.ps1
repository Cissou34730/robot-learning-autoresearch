# Token-efficient autonomous robot-learning loop.

Set-Location $PSScriptRoot

$createdNew = $false
$loopMutex = [System.Threading.Mutex]::new(
    $true,
    "Local\RobotLearningAutoresearch",
    [ref]$createdNew
)
if (-not $createdNew) {
    $loopMutex.Dispose()
    throw "Another robot autoresearch loop is already running."
}

function Update-ResearchBrief {
    uv run python research/build_research_brief.py
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build the compact research brief."
    }
}

function Save-ResearchMemory {
    git add -- research/postmortems.md
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "record research postmortem"
    }
}

function Assert-BenchmarkIntegrity {
    $protected = @(
        "robot_learning/benchmark",
        "robot_learning/environments/reach_env.py",
        "robot_learning/evaluate.py",
        "robot_learning/robots",
        "robot_learning/training/algorithms.py",
        "robot_learning/training/normalization.py",
        "robot_learning/training/research_config.py",
        "research/run_experiment.py",
        "tests/benchmark"
    )
    $changes = git status --porcelain --untracked-files=all -- $protected
    if ($changes) {
        throw "The researcher modified protected benchmark files. Nothing was run.`n$changes"
    }
}

try {
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

        $runnerArguments = @("run", "python", "research/run_experiment.py")
        if (Test-Path "research\RECOVERY_PENDING") {
            $recoveryCandidate = (
                Get-Content "research\RECOVERY_PENDING" -Raw
            ).Trim()
            if (-not (Test-Path -LiteralPath $recoveryCandidate)) {
                throw "Recovery candidate is missing: $recoveryCandidate"
            }
            Write-Host "=== Reusing completed candidate: $recoveryCandidate ==="
            $runnerArguments += @("--reuse-candidate", $recoveryCandidate)
        }
        uv @runnerArguments
        if ($LASTEXITCODE -eq 130) {
            Write-Host "=== Baseline interrupted cleanly; it remains pending ==="
            break
        }
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
    Save-ResearchMemory
    Assert-BenchmarkIntegrity
    uv run python research/run_experiment.py
    if ($LASTEXITCODE -eq 130) {
        Write-Host "=== Experiment interrupted cleanly; no candidate accepted ==="
        break
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment runner failed. The loop stopped safely."
    }
    Update-ResearchBrief
    Write-Host "=== Experiment session ended at $(Get-Date -Format 'HH:mm:ss') ==="
    Start-Sleep -Seconds 5
}
}
finally {
    $loopMutex.ReleaseMutex()
    $loopMutex.Dispose()
}

