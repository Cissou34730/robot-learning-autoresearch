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

function Push-CurrentCommit {
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "The commit was created locally but could not be pushed to origin."
    }
}

function Save-ResearchMemory {
    git add -- research/postmortems.md
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "record research postmortem"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not commit the research postmortem."
        }
        Push-CurrentCommit
    }
}

try {
while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Host "GOAL REACHED - research loop finished."
        break
    }

    $model = "github-copilot/gpt-5.6-luna"
    $reasoning = "medium"
    if ($env:RESEARCH_MODEL) {
        $model = $env:RESEARCH_MODEL
    }
    if ($env:RESEARCH_REASONING) {
        $reasoning = $env:RESEARCH_REASONING
    }

    if (Test-Path "research\RECOVERY_PENDING") {
        if (-not (Test-Path "research\proposal.json")) {
            throw "Interrupted experiment has no proposal to resume."
        }
        $recoveryCandidate = (
            Get-Content "research\RECOVERY_PENDING" -Raw
        ).Trim()
        if (-not (Test-Path -LiteralPath $recoveryCandidate)) {
            throw "Recovery candidate is missing: $recoveryCandidate"
        }
        Write-Host "=== Resuming interrupted experiment: $recoveryCandidate ==="
        uv run python research/run_experiment.py --reuse-candidate $recoveryCandidate
        if ($LASTEXITCODE -eq 130) {
            Write-Host "=== Experiment paused again; progress remains saved ==="
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Resumed experiment failed. Its recovery state was preserved."
        }
        Update-ResearchBrief
        Write-Host "=== Resumed experiment complete ==="
        continue
    }

    if (Test-Path "research\RESTART_PENDING") {
        if (-not (Test-Path "research\proposal.json")) {
            throw "Interrupted experiment has no proposal to restart."
        }
        Write-Host "=== Restarting interrupted experiment from its beginning ==="
        uv run python research/run_experiment.py
        if ($LASTEXITCODE -eq 130) {
            Write-Host "=== Experiment paused again ==="
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Restarted experiment failed."
        }
        Update-ResearchBrief
        Write-Host "=== Restarted experiment complete ==="
        continue
    }

    $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        $evaluationPlanExists = $null -ne $researchState.pending_evaluation_request.evaluation_plan
        if (-not $evaluationPlanExists) {
            Remove-Item "research\evaluation_request.json" -ErrorAction SilentlyContinue
            Write-Host "=== Researcher designing evaluations for experiment $($researchState.pending_evaluation_request.experiment) ==="
            $evaluationPrompt = @(
                "This is the complete evaluation-design task; do not wait for more input."
                "Read research/program.md, research/brief.md, research/last_train_summary.md, and research/current_params.json."
                "Training is complete. Decide which saved candidates need evaluation and which episode counts, seeds, comparisons, or diagnostics are useful for this experiment."
                "You may modify evaluation or diagnostic code when the hypothesis requires it, while preserving the human-defined objective."
                "Write research/evaluation_request.json using the experiment number and an evaluations list."
                "Each evaluation names candidate, episodes, seed, and a concise label."
                "Use only the evidence needed for the scientific decision. Do not start training, evaluation, or a new experiment."
            ) -join " "
            opencode run --model $model --variant $reasoning $evaluationPrompt
            if (-not (Test-Path "research\evaluation_request.json")) {
                Write-Host "=== Evaluation request missing; retrying the same bounded task once ==="
                $evaluationRetryPrompt = @(
                    "Complete the pending evaluation-design task now; this message is complete."
                    "Read only research/program.md, research/brief.md, research/last_train_summary.md, and research/current_params.json."
                    "Do not ask for more input and do not propose a new training experiment."
                    "Choose the useful saved candidates, episode counts, and seeds, then write research/evaluation_request.json with the pending experiment number and an evaluations list."
                    "Do not run evaluation or training yourself."
                ) -join " "
                opencode run --model $model --variant $reasoning $evaluationRetryPrompt
                if (-not (Test-Path "research\evaluation_request.json")) {
                    throw "Researcher ended twice without creating research/evaluation_request.json."
                }
            }
        }
        else {
            Write-Host "=== Resuming the researcher's evaluation plan ==="
        }
        uv run python research/run_experiment.py --evaluate-pending
        if ($LASTEXITCODE -eq 130) {
            Write-Host "=== Requested evaluation paused; completed measurements were saved ==="
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Requested evaluation failed."
        }
        Update-ResearchBrief
        Write-Host "=== Requested evaluations complete ==="
        continue
    }

    if (Test-Path "research\BASELINE_PENDING") {
        Write-Host "=== Running fresh baseline training ==="
        @{
            baseline = $true
            change = "Fresh PPO baseline"
            hypothesis = "Establish the initial baseline for the human-defined objective."
            class = "baseline"
            initialization = "fresh"
        } | ConvertTo-Json | Set-Content "research\proposal.json"

        uv run python research/run_experiment.py
        if ($LASTEXITCODE -eq 130) {
            Write-Host "=== Baseline interrupted cleanly; it remains pending ==="
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Baseline failed. The research loop stopped instead of silently continuing."
        }
        Update-ResearchBrief
        Write-Host "=== Baseline training complete; researcher evaluation comes next ==="
        continue
    }

    Update-ResearchBrief

    Write-Host "=== New experiment at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    Write-Host "Model: $model, reasoning: $reasoning"
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $researchPrompt = @(
        "This is the complete research task; do not wait for more input."
        "Read research/program.md, research/brief.md, research/last_train_summary.md, and research/current_params.json."
        "Treat these compact files as the complete default research context."
        "Do not read research/results.jsonl, research/EXPERIMENTS.md, research/postmortems.md, research/last_evaluation.json, research/run_experiment.py, or full logs unless the compact brief identifies one specific ambiguity that requires one of them."
        "Prepare exactly one protocol-compliant experiment and write research/proposal.json before exiting."
        "Do not launch training or the runner."
    ) -join " "
    opencode run --model $model --variant $reasoning $researchPrompt

    Update-ResearchBrief
    Save-ResearchMemory
    if (-not (Test-Path "research\proposal.json")) {
        $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
        if ($resultCountAfter -gt $resultCountBefore) {
            Write-Host "=== Experiment was already executed during the research session ==="
            continue
        }
        Write-Host "=== Researcher ended without a proposal; retrying once with bounded context ==="
        $retryPrompt = @(
            "The previous researcher session ended before writing research/proposal.json."
            "Complete that same single research task; do not begin a second hypothesis and do not wait for more input."
            "Read only research/program.md, research/brief.md, research/last_train_summary.md, research/current_params.json, and git status."
            "Use existing research edits, if any, only when they clearly belong to that unfinished experiment."
            "Write a valid research/proposal.json before exiting. Do not launch training or the runner."
        ) -join " "
        opencode run --model $model --variant $reasoning $retryPrompt
        Update-ResearchBrief
        Save-ResearchMemory

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
