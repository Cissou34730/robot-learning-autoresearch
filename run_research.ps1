# Token-efficient autonomous robot-learning loop.

param(
    [ValidateNotNullOrEmpty()]
    [string]$Model = "github-copilot/gpt-5.6-luna",

    [ValidateSet("low", "medium", "high", "xhigh", "max")]
    [string]$Reasoning = "high"
)

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

function Assert-ResearchRuntime {
    uv run python -c "import robot_learning.train; import research.run_experiment" | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "The research runtime is internally inconsistent: robot_learning.train and research.run_experiment could not both be imported. No researcher session, training, evaluation or lineage decision was started."
    }
}

Assert-ResearchRuntime

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

function Test-LineageResearchMemory([int]$experiment) {
    if (-not (Test-Path "research\proposal.json")) {
        return $false
    }
    if (-not (Test-Path "research\postmortems.md")) {
        return $false
    }
    if (-not ((Get-Content "research\postmortems.md" -Raw) -match "(?m)^## Experiment $experiment\b")) {
        return $false
    }
    # The decision must name existing detailed evidence of this experiment.
    uv run python research/run_experiment.py --check-lineage-evidence $experiment | Out-Host
    return ($LASTEXITCODE -eq 0)
}

try {
while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Host "GOAL REACHED - research loop finished."
        break
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
    if ($null -ne $researchState.pending_final_benchmark) {
        Write-Host "=== Evaluating the committed accepted lineage on the final benchmark ==="
        uv run python research/run_experiment.py --evaluate-pending-final
        if ($LASTEXITCODE -ne 0) {
            throw "Final benchmark failed. The committed lineage remains pending for recovery."
        }
        Update-ResearchBrief
        Write-Host "=== Final benchmark complete ==="
        continue
    }

    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        $evaluationPlanExists = $null -ne $researchState.pending_evaluation_request.evaluation_plan
        if (-not $evaluationPlanExists) {
            Remove-Item "research\evaluation_request.json" -ErrorAction SilentlyContinue
            Write-Host "=== Researcher designing evaluation for experiment $($researchState.pending_evaluation_request.experiment) ==="
            $evaluationPrompt = @(
                "This is the complete evaluation-design task; do not wait for more input."
                "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                "Training is complete. Decide what evidence is necessary to understand this experiment, not merely which panels to rerun."
                "When useful you may inspect existing evidence, code, logs and artifacts, run a lightweight local analysis, change researcher-owned evaluation or instrumentation code, and request new measurements of already-saved policies. None of this is required every time."
                "Write research/evaluation_request.json using the experiment number, a question, a reason, and an evaluations list."
                "question states the concise scientific question these evaluations answer; reason states why this plan is useful and sufficient. Both are required and must be non-empty."
                "Each evaluation names candidate, episodes, seed, and a concise label."
                "Use only the evidence needed for the scientific decision. Do not start training, evaluation, or a new experiment."
            ) -join " "
            opencode run --model $model --variant $reasoning $evaluationPrompt
            if (-not (Test-Path "research\evaluation_request.json")) {
                Write-Host "=== Evaluation request missing; retrying the same bounded task once ==="
                $evaluationRetryPrompt = @(
                    "Complete the pending evaluation-design task now; this message is complete."
                    "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                    "Do not ask for more input and do not propose a new training experiment."
                    "You may still inspect existing evidence, analyse it locally, and change researcher-owned evaluation or instrumentation code before completing the plan."
                    "Then write research/evaluation_request.json with the pending experiment number, a non-empty question, a non-empty reason, and an evaluations list naming candidate, episodes and seed."
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
            change = "Fresh baseline"
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

    if ($null -ne $researchState.pending_researcher_decision) {
        Update-ResearchBrief
        Write-Host "=== Researcher resolving lineage for experiment $($researchState.pending_researcher_decision.experiment) ==="
        $decisionPrompt = @(
            "This is the complete lineage-resolution task; do not wait for more input."
            "Read research/program.md, research/scenario.md, and research/brief.md."
            "Before concluding, open the detailed evaluation artifacts the brief lists for this experiment and read them; run a lightweight local analysis when it helps. Historical artifacts from other experiments are optional."
            "Only then record the required postmortem for the pending experiment in research/postmortems.md, under '## Experiment <n>' with '**Result:**', '**Observed behavior:**', '**Interpretation:**' and '**Evidence inspected:**'."
            "'Evidence inspected' must list the repository-relative paths of the detailed evaluation artifacts of this experiment that your decision relies on; the runner rejects the decision otherwise."
            "Then write research/proposal.json containing only previous_result_decision for the pending experiment."
            "Decide the measured model lineage, code lineage, and retained alternatives."
            "Do not create the next scientific mutation, evaluation request, or training proposal. Do not run the runner."
        ) -join " "
        opencode run --model $model --variant $reasoning $decisionPrompt
        $pendingExperiment = [int]$researchState.pending_researcher_decision.experiment
        if (-not (Test-LineageResearchMemory $pendingExperiment)) {
            Write-Host "=== Lineage proposal or postmortem missing; retrying the same bounded task once ==="
            $decisionRetryPrompt = @(
                "Complete the pending lineage-resolution task now; this message is complete."
                "Read research/program.md, research/scenario.md, and research/brief.md."
                "Open and read the detailed evaluation artifacts the brief lists for experiment $pendingExperiment before concluding; this step is required."
                "Write the required Markdown postmortem entry for experiment $pendingExperiment in research/postmortems.md, under '## Experiment $pendingExperiment' with '**Result:**', '**Observed behavior:**', '**Interpretation:**' and '**Evidence inspected:**' listing the repository-relative artifact paths your decision relies on."
                "Write research/proposal.json containing only previous_result_decision; do not create an N+1 training proposal or run the runner."
            ) -join " "
            opencode run --model $model --variant $reasoning $decisionRetryPrompt
            if (-not (Test-LineageResearchMemory $pendingExperiment)) {
                throw "Researcher ended twice without both a lineage proposal and postmortem for experiment $pendingExperiment."
            }
        }
        uv run python research/run_experiment.py
        if ($LASTEXITCODE -ne 0) {
            throw "Lineage decision could not be finalized."
        }
        Update-ResearchBrief
        Write-Host "=== Lineage decision finalized; requesting next hypothesis ==="
        continue
    }

    Update-ResearchBrief

    Write-Host "=== Researcher forming next hypothesis at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="
    Write-Host "Model: $model, reasoning: $reasoning"
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $researchPrompt = @(
        "This is the complete research task; do not wait for more input."
        "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
        "Treat these compact files as a starting point, not the complete scientific evidence."
        "Before proposing another training experiment you may inspect existing detailed evaluation artifacts, code, logs and configuration, and run a lightweight local analysis. Do none of this when the available evidence already answers the question."
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
            "Read only research/program.md, research/scenario.md, research/brief.md, research/last_train_summary.md, and git status."
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
