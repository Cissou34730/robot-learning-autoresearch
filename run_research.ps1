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
        "robot_learning/benchmark/spec.py",
        "robot_learning/environments/reach_env.py",
        "robot_learning/robots",
        "research/run_experiment.py",
        "run_research.ps1",
        "tests/benchmark/test_task_contract.py"
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
        Write-Host "=== Running fresh final-goal baseline ==="
        @{
            baseline = $true
            change = "Fresh PPO baseline"
            hypothesis = "Establish the initial fixed-evaluator baseline."
            class = "baseline"
            initialization = "fresh"
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
    if ($env:RESEARCH_MODEL) {
        $model = $env:RESEARCH_MODEL
    }
    if ($env:RESEARCH_REASONING) {
        $reasoning = $env:RESEARCH_REASONING
    }

    Write-Host "=== New experiment at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    Write-Host "Model: $model, reasoning: $reasoning"
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $researchPrompt = @"
Read research/program.md, research/brief.md, research/last_train_summary.md, and
research/current_params.json. Treat these compact files as the complete default
research context. Do not read research/results.jsonl, research/EXPERIMENTS.md,
research/postmortems.md, research/last_evaluation.json, research/run_experiment.py,
or full logs unless the compact brief identifies one specific ambiguity that
requires one of them. Prepare exactly one protocol-compliant experiment and
write research/proposal.json before exiting. Do not launch training or the runner.
"@
    opencode run --model $model --variant $reasoning $researchPrompt

    Update-ResearchBrief
    Save-ResearchMemory
    Assert-BenchmarkIntegrity
    if (-not (Test-Path "research\proposal.json")) {
        $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
        if ($resultCountAfter -gt $resultCountBefore) {
            Write-Host "=== Experiment was already executed during the research session ==="
            continue
        }
        Write-Host "=== Researcher ended without a proposal; retrying once with bounded context ==="
        $retryPrompt = @"
The previous researcher session ended before writing research/proposal.json.
Complete that same single research task; do not begin a second hypothesis.
Read only research/program.md, research/brief.md, research/last_train_summary.md,
research/current_params.json, and git status. Use existing research-surface edits,
if any, only when they clearly belong to that unfinished experiment. Write a
valid research/proposal.json before exiting. Do not launch training or the runner.
"@
        opencode run --model $model --variant $reasoning $retryPrompt
        Update-ResearchBrief
        Save-ResearchMemory
        Assert-BenchmarkIntegrity

        if (-not (Test-Path "research\proposal.json")) {
            $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
            if ($resultCountAfter -gt $resultCountBefore) {
                Write-Host "=== Experiment was already executed during the research session ==="
                continue
            }
            throw "Researcher ended twice without creating research/proposal.json. The loop stopped safely."
        }
    }
    uv run python research/run_experiment.py
    if ($LASTEXITCODE -eq 130) {
        Write-Host "=== Experiment interrupted cleanly; no model decision was made ==="
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
