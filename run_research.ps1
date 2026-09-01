# Token-efficient autonomous robot-learning loop.

param(
    [ValidateNotNullOrEmpty()]
    [string]$Model = "gpt-5.6-luna",

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

. "$PSScriptRoot\researcher_session.ps1"

# The single Researcher process boundary. It observes the process exit code and
# nothing else: the Researcher's own output stays visible and uninterpreted.
function Invoke-ResearcherSession {
    param(
        [Parameter(Mandatory)][string]$Prompt,
        [switch]$Continue
    )
    if ($Continue) {
        if (-not $script:ResearcherSessionId) {
            throw "There is no researcher session to continue for this phase."
        }
    }
    else {
        # Each bounded phase owns its session, so a retry resumes that phase and
        # never inherits whichever session last ran on this machine.
        $script:ResearcherSessionId = [guid]::NewGuid().ToString()
    }
    $sessionArgs = @(
        "--session-id", $script:ResearcherSessionId
        "--model", $model
        "--reasoning", $reasoning
    )
    if ($Continue) {
        $sessionArgs += "--resume"
    }
    uv run --group researcher python researcher_copilot.py @sessionArgs $Prompt
    # An invocation that never reached a conventional exit reports the absence
    # rather than an invented code.
    $script:ResearcherExitCode = if ($null -eq $LASTEXITCODE) {
        $null
    }
    else {
        [int]$LASTEXITCODE
    }
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

function Test-EvaluationRequest {
    $validationOutput = @(
        uv run python research/run_experiment.py --check-evaluation-request 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:EvaluationValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:EvaluationValidationFeedback
        return $false
    }
    return $true
}

# The three bounded phases below observe the same facts: what the process did,
# whether the deliverable exists, and whether the protected validator accepts it.
function Get-ProposalSessionStatus([string]$phase, [int]$attempt) {
    $present = Test-Path "research\proposal.json"
    $valid = $false
    $reason = "research/proposal.json was not created"
    if ($present) {
        $valid = Test-ResearchProposal
        $reason = if ($valid) { "" } else { $script:ProposalValidationFeedback }
    }
    New-ResearcherSessionStatus -Phase $phase -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable "research/proposal.json" `
        -Present $present -Valid $valid -Reason $reason
}

function Get-EvaluationSessionStatus([int]$attempt) {
    $present = Test-Path "research\evaluation_request.json"
    $valid = $false
    $reason = "research/evaluation_request.json was not created"
    if ($present) {
        $valid = Test-EvaluationRequest
        $reason = if ($valid) { "" } else { $script:EvaluationValidationFeedback }
    }
    New-ResearcherSessionStatus -Phase "evaluation design" -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable "research/evaluation_request.json" `
        -Present $present -Valid $valid -Reason $reason
}

function Get-LineageSessionStatus([int]$experiment, [int]$attempt) {
    $present = (Test-Path "research\postmortems.md") -and (
        Test-Path "research\proposal.json"
    )
    $valid = $false
    $reason = ""
    if (Test-LineageResearchMemory $experiment) {
        $valid = Test-ResearchProposal
        if (-not $valid) {
            $reason = $script:ProposalValidationFeedback
        }
    }
    else {
        $reason = $script:LineageValidationFeedback
    }
    New-ResearcherSessionStatus -Phase "lineage decision" -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable "research/postmortems.md and research/proposal.json" `
        -Present $present -Valid $valid -Reason $reason
}

try {
while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Status "GOAL REACHED - research loop finished." Green
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
        Write-Status "=== Resuming interrupted experiment: $recoveryCandidate ==="
        uv run python research/run_experiment.py --reuse-candidate $recoveryCandidate
        if ($LASTEXITCODE -eq 130) {
            Write-Status "=== Experiment paused again; progress remains saved ===" Yellow
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Resumed experiment failed. Its recovery state was preserved."
        }
        Update-ResearchBrief
        Write-Status "=== Resumed experiment complete ===" Green
        continue
    }

    if (Test-Path "research\RESTART_PENDING") {
        if (-not (Test-Path "research\proposal.json")) {
            throw "Interrupted experiment has no proposal to restart."
        }
        Write-Status "=== Restarting interrupted experiment from its beginning ==="
        uv run python research/run_experiment.py
        if ($LASTEXITCODE -eq 130) {
            Write-Status "=== Experiment paused again ===" Yellow
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Restarted experiment failed."
        }
        Update-ResearchBrief
        Write-Status "=== Restarted experiment complete ===" Green
        continue
    }

    $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    if ($null -ne $researchState.pending_final_benchmark) {
        Write-Status "=== Evaluating the committed accepted lineage on the final benchmark ==="
        uv run python research/run_experiment.py --evaluate-pending-final
        if ($LASTEXITCODE -ne 0) {
            throw "Final benchmark failed. The committed lineage remains pending for recovery."
        }
        Update-ResearchBrief
        Write-Status "=== Final benchmark complete ===" Green
        continue
    }

    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        $evaluationPlanExists = $null -ne $researchState.pending_evaluation_request.evaluation_plan
        if (-not $evaluationPlanExists) {
            Remove-Item "research\evaluation_request.json" -ErrorAction SilentlyContinue
            Write-Status "=== Researcher designing evaluation for experiment $($researchState.pending_evaluation_request.experiment) ==="
            $evaluationPrompt = @(
                "Current phase: design the research evaluation for experiment $($researchState.pending_evaluation_request.experiment). This is the complete task; do not wait for more input."
                "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                "Expected deliverable: research/evaluation_request.json for the current experiment, as defined by the protocol."
                "Do not start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the request."
            ) -join " "
            Invoke-ResearcherSession -Prompt $evaluationPrompt
            $evaluationStatus = Get-EvaluationSessionStatus 1
            Write-ResearcherSessionStatus $evaluationStatus
            if (-not $evaluationStatus.Complete) {
                $evaluationProblem = $evaluationStatus.Reason
                Write-Status "=== Evaluation request missing or invalid; retrying the same bounded task once ===" Yellow
                $evaluationRetryPrompt = @(
                    "Current phase: evaluation design for experiment $($researchState.pending_evaluation_request.experiment). The previous deliverable failed validation: $evaluationProblem. This is the complete task; do not wait for more input."
                    "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
                    "Expected deliverable: complete research/evaluation_request.json according to the protocol."
                    "Do not change phase, start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py."
                ) -join " "
                Invoke-ResearcherSession -Prompt $evaluationRetryPrompt -Continue
                $evaluationStatus = Get-EvaluationSessionStatus 2
                Write-ResearcherSessionStatus $evaluationStatus
                if (-not $evaluationStatus.Complete) {
                    throw "Researcher ended twice without a valid research/evaluation_request.json. Last validation error: $($evaluationStatus.Reason)"
                }
            }
        }
        else {
            Write-Status "=== Resuming the researcher's evaluation plan ==="
        }
        uv run python research/run_experiment.py --evaluate-pending
        if ($LASTEXITCODE -eq 130) {
            Write-Status "=== Requested evaluation paused; completed measurements were saved ===" Yellow
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Runner execution of the validated evaluation request failed. The researcher deliverable was already accepted, so the researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Requested evaluations complete ===" Green
        continue
    }

    if (Test-Path "research\BASELINE_PENDING") {
        Write-Status "=== Running fresh baseline training ==="
        @{
            baseline = $true
            change = "Fresh baseline"
            hypothesis = "Establish the initial baseline for the human-defined objective."
            class = "baseline"
            initialization = "fresh"
        } | ConvertTo-Json | Set-Content "research\proposal.json"

        uv run python research/run_experiment.py
        if ($LASTEXITCODE -eq 130) {
            Write-Status "=== Baseline interrupted cleanly; it remains pending ===" Yellow
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Baseline failed. The research loop stopped instead of silently continuing."
        }
        Update-ResearchBrief
        Write-Status "=== Baseline training complete; researcher evaluation comes next ===" Green
        continue
    }

    if ($null -ne $researchState.pending_researcher_decision) {
        Update-ResearchBrief
        Write-Status "=== Researcher resolving lineage for experiment $($researchState.pending_researcher_decision.experiment) ==="
        $decisionPrompt = @(
            "Current phase: close experiment $($researchState.pending_researcher_decision.experiment) and resolve its lineage. This is the complete task; do not wait for more input."
            "Read research/program.md, research/scenario.md, and research/brief.md."
            "Read the detailed evaluation artifacts referenced for this experiment in the brief."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json defined by the protocol."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        Invoke-ResearcherSession -Prompt $decisionPrompt
        $pendingExperiment = [int]$researchState.pending_researcher_decision.experiment
        $lineageStatus = Get-LineageSessionStatus $pendingExperiment 1
        Write-ResearcherSessionStatus $lineageStatus
        if (-not $lineageStatus.Complete) {
            $lineageProblem = $lineageStatus.Reason
            Write-Status "=== Lineage deliverable invalid; retrying the same bounded task once ===" Yellow
            $decisionRetryPrompt = @(
                "Current phase: close experiment $pendingExperiment and resolve its lineage. The previous deliverable failed validation: $lineageProblem. This is the complete task; do not wait for more input."
                "Read research/program.md, research/scenario.md, and research/brief.md."
                "Correct the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json according to the protocol."
                "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py."
            ) -join " "
            Invoke-ResearcherSession -Prompt $decisionRetryPrompt -Continue
            $lineageStatus = Get-LineageSessionStatus $pendingExperiment 2
            Write-ResearcherSessionStatus $lineageStatus
            if (-not $lineageStatus.Complete) {
                throw "Researcher ended twice without valid lineage deliverables for experiment $pendingExperiment. Last validation error: $($lineageStatus.Reason)"
            }
        }
        uv run python research/run_experiment.py
        if ($LASTEXITCODE -ne 0) {
            throw "Runner application of the validated lineage decision failed. The researcher deliverables were already accepted, so the researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Lineage decision finalized; requesting next hypothesis ===" Green
        continue
    }

    Update-ResearchBrief

    # Anchor the rollback baseline before the researcher can change or commit
    # science. An unfinished experiment keeps the anchor it already established.
    uv run python research/run_experiment.py --begin-hypothesis
    if ($LASTEXITCODE -ne 0) {
        throw "Could not establish the scientific parent of the next experiment."
    }

    Write-Status "=== Researcher forming next hypothesis ==="
    Write-Host "Model: $model, reasoning: $reasoning"
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $allocatedExperiment = [Math]::Max(
        [int]$researchState.last_allocated_experiment,
        [int]$researchState.last_experiment
    )
    $nextExperiment = $allocatedExperiment + 1
    $researchPrompt = @(
        "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending. This is the complete task; do not wait for more input."
        "Read research/program.md, research/scenario.md, research/brief.md, and research/last_train_summary.md."
        "Expected deliverables: any researcher-owned code or configuration changes required by the intervention and research/proposal.json for experiment $nextExperiment, as defined by the protocol."
        "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
        "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal."
    ) -join " "
    Invoke-ResearcherSession -Prompt $researchPrompt

    $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    if ($resultCountAfter -gt $resultCountBefore) {
        throw "The researcher executed an experiment during the new-hypothesis phase. The loop stopped without attempting a retry or another execution; restart it to continue from the persisted state."
    }

    # Observed before the runner's own bookkeeping, so a brief or commit failure
    # cannot swallow what the session did.
    $proposalStatus = Get-ProposalSessionStatus "new hypothesis" 1
    Write-ResearcherSessionStatus $proposalStatus
    Update-ResearchBrief
    Save-ResearchMemory
    if (-not $proposalStatus.Complete) {
        $proposalProblem = $proposalStatus.Reason
        Write-Status "=== Research proposal missing or invalid; retrying once with bounded context ===" Yellow
        $retryPrompt = @(
            "Current phase: prepare experiment $nextExperiment. The previous deliverable failed validation: $proposalProblem. This is the complete task; do not wait for more input."
            "Read research/program.md, research/scenario.md, research/brief.md, research/last_train_summary.md, and inspect the relevant repository state."
            "Preserve valid researcher-owned edits that belong to this unfinished experiment."
            "Expected deliverable: a corrected research/proposal.json for experiment $nextExperiment according to the protocol."
            "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
            "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py."
        ) -join " "
        Invoke-ResearcherSession -Prompt $retryPrompt -Continue

        $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
        if ($resultCountAfter -gt $resultCountBefore) {
            throw "The researcher executed an experiment during the new-hypothesis retry. The loop stopped without attempting another execution; restart it to continue from the persisted state."
        }

        $proposalStatus = Get-ProposalSessionStatus "new hypothesis" 2
        Write-ResearcherSessionStatus $proposalStatus
        Update-ResearchBrief
        Save-ResearchMemory

        if (-not $proposalStatus.Complete) {
            throw "Researcher ended twice without a proposal valid for the current phase. The loop stopped safely: $($proposalStatus.Reason)"
        }
    }
    uv run python research/run_experiment.py
    if ($LASTEXITCODE -eq 130) {
        Write-Status "=== Experiment interrupted cleanly; no model decision was made ===" Yellow
        break
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Experiment runner failed. The loop stopped safely."
    }
    Update-ResearchBrief
    Write-Status "=== Experiment session ended ===" Green
    Start-Sleep -Seconds 5
}
}
finally {
    $loopMutex.ReleaseMutex()
    $loopMutex.Dispose()
}
