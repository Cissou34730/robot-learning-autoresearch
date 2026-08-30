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
    $script:LineageValidationFeedback = ""
    if (-not (Test-Path "research\proposal.json")) {
        $script:LineageValidationFeedback = "research/proposal.json was not created"
        return $false
    }
    if (-not (Test-Path "research\postmortems.md")) {
        $script:LineageValidationFeedback = "research/postmortems.md was not created"
        return $false
    }
    if (-not ((Get-Content "research\postmortems.md" -Raw) -match "(?m)^## Experiment $experiment\b")) {
        $script:LineageValidationFeedback = "research/postmortems.md has no entry for experiment $experiment"
        return $false
    }
    # The decision must name existing detailed evidence of this experiment.
    $validationOutput = @(
        uv run python research/run_experiment.py --check-lineage-evidence $experiment 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $validationOutput | ForEach-Object { Write-Host $_ }
    $script:LineageValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0 -and -not $script:LineageValidationFeedback) {
        $script:LineageValidationFeedback = "lineage evidence validation failed"
    }
    return ($validationExitCode -eq 0)
}

function Test-ResearchProposal {
    $validationOutput = @(
        uv run python research/run_experiment.py --check-proposal 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:ProposalValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:ProposalValidationFeedback
        return $false
    }
    return $true
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
                "Current phase: design the research evaluation for experiment $($researchState.pending_evaluation_request.experiment). This is the complete task; do not wait for more input."
                "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                "Expected deliverable: research/evaluation_request.json for the current experiment, as defined by the protocol."
                "Do not start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the request."
            ) -join " "
            opencode run --model $model --variant $reasoning $evaluationPrompt
            if (-not (Test-Path "research\evaluation_request.json")) {
                Write-Host "=== Evaluation request missing; retrying the same bounded task once ==="
                $evaluationRetryPrompt = @(
                    "Current phase: evaluation design for experiment $($researchState.pending_evaluation_request.experiment). The phase remains open because research/evaluation_request.json was not produced. This is the complete task; do not wait for more input."
                    "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                    "Expected deliverable: complete research/evaluation_request.json according to the protocol."
                    "Do not change phase, start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py."
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
            "Current phase: close experiment $($researchState.pending_researcher_decision.experiment) and resolve its lineage. This is the complete task; do not wait for more input."
            "Read research/program.md, research/scenario.md, and research/brief.md."
            "Read the detailed evaluation artifacts referenced for this experiment in the brief."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json defined by the protocol."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        opencode run --model $model --variant $reasoning $decisionPrompt
        $pendingExperiment = [int]$researchState.pending_researcher_decision.experiment
        $lineageReady = Test-LineageResearchMemory $pendingExperiment
        if ($lineageReady) {
            $lineageReady = Test-ResearchProposal
            if (-not $lineageReady) {
                $lineageProblem = $script:ProposalValidationFeedback
            }
        }
        else {
            $lineageProblem = $script:LineageValidationFeedback
        }
        if (-not $lineageReady) {
            Write-Host "=== Lineage deliverable invalid; retrying the same bounded task once ==="
            $decisionRetryPrompt = @(
                "Current phase: close experiment $pendingExperiment and resolve its lineage. The previous deliverable failed validation: $lineageProblem. This is the complete task; do not wait for more input."
                "Read research/program.md, research/scenario.md, and research/brief.md."
                "Correct the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json according to the protocol."
                "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py."
            ) -join " "
            opencode run --model $model --variant $reasoning $decisionRetryPrompt
            $lineageReady = Test-LineageResearchMemory $pendingExperiment
            if ($lineageReady) {
                $lineageReady = Test-ResearchProposal
                if (-not $lineageReady) {
                    $lineageProblem = $script:ProposalValidationFeedback
                }
            }
            else {
                $lineageProblem = $script:LineageValidationFeedback
            }
            if (-not $lineageReady) {
                throw "Researcher ended twice without valid lineage deliverables for experiment $pendingExperiment. Last validation error: $lineageProblem"
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
    $nextExperiment = [int]$researchState.last_experiment + 1
    $researchPrompt = @(
        "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending. This is the complete task; do not wait for more input."
        "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
        "Expected deliverables: any researcher-owned code or configuration changes required by the intervention and research/proposal.json for experiment $nextExperiment, as defined by the protocol."
        "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
        "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal."
    ) -join " "
    opencode run --model $model --variant $reasoning $researchPrompt

    $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    if ($resultCountAfter -gt $resultCountBefore) {
        throw "The researcher executed an experiment during the new-hypothesis phase. The loop stopped without attempting a retry or another execution; restart it to continue from the persisted state."
    }

    Update-ResearchBrief
    Save-ResearchMemory
    $proposalValid = $false
    if (Test-Path "research\proposal.json") {
        $proposalValid = Test-ResearchProposal
    }
    if (-not $proposalValid) {
        $proposalProblem = if (Test-Path "research\proposal.json") {
            $script:ProposalValidationFeedback
        }
        else {
            "research/proposal.json was not created"
        }
        Write-Host "=== Research proposal missing or invalid; retrying once with bounded context ==="
        $retryPrompt = @(
            "Current phase: prepare experiment $nextExperiment. The previous deliverable failed validation: $proposalProblem. This is the complete task; do not wait for more input."
            "Read research/program.md, research/scenario.md, research/brief.md, research/last_train_summary.md, and inspect the relevant repository state."
            "Preserve valid researcher-owned edits that belong to this unfinished experiment."
            "Expected deliverable: a corrected research/proposal.json for experiment $nextExperiment according to the protocol."
            "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
            "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py."
        ) -join " "
        opencode run --model $model --variant $reasoning $retryPrompt

        $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
        if ($resultCountAfter -gt $resultCountBefore) {
            throw "The researcher executed an experiment during the new-hypothesis retry. The loop stopped without attempting another execution; restart it to continue from the persisted state."
        }

        Update-ResearchBrief
        Save-ResearchMemory

        if (-not (Test-Path "research\proposal.json")) {
            throw "Researcher ended twice without creating research/proposal.json. The loop stopped safely."
        }
        if (-not (Test-ResearchProposal)) {
            throw "Researcher ended twice without a proposal valid for the current phase. The loop stopped safely: $script:ProposalValidationFeedback"
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
