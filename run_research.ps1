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
        [Parameter(Mandatory)][string]$Phase,
        [switch]$Continue
    )
    if ($Continue) {
        if (-not $script:ResearcherSessionId) {
            throw "There is no researcher session to continue for this phase."
        }
    }
    else {
        # Each phase owns its session, so a retry resumes that phase and
        # never inherits whichever session last ran on this machine.
        $script:ResearcherSessionId = [guid]::NewGuid().ToString()
    }
    Write-Status "=== Researcher phase: $Phase ===" -Color Magenta -Label researcher
    Write-Status "Model: $model, reasoning: $reasoning" -Color Magenta -Label researcher
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
    $state = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    $campaignId = $state.campaign.id
    $headingPattern = if ($campaignId) {
        "(?m)^## $([regex]::Escape($campaignId)) / Experiment $experiment\b"
    }
    else {
        "(?m)^## Experiment $experiment\b"
    }
    if (-not ((Get-Content "research\postmortems.md" -Raw) -match $headingPattern)) {
        $script:LineageValidationFeedback = (
            "research/postmortems.md has no entry for the current campaign " +
            "and experiment $experiment"
        )
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

function Test-AnalysisDeliverable {
    $validationOutput = @(
        uv run python research/run_experiment.py --check-analysis-deliverable 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:AnalysisValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:AnalysisValidationFeedback
        return $false
    }
    return $true
}

# The phases below observe the same facts: what the process did,
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

function Get-AnalysisSessionStatus([int]$attempt) {
    $present = (Test-Path "research\evaluation_request.json") -or (Test-Path "research\proposal.json")
    $valid = $false
    $reason = "research/evaluation_request.json or research/proposal.json was not created"
    if ($present) {
        $valid = Test-AnalysisDeliverable
        $reason = if ($valid) { "" } else { $script:AnalysisValidationFeedback }
    }
    New-ResearcherSessionStatus -Phase "post-training analysis" -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable "research/evaluation_request.json or research/proposal.json" `
        -Present $present -Valid $valid -Reason $reason
}

try {
while ($true) {
    if (Test-Path "research\GOAL_REACHED") {
        Write-Status "GOAL REACHED - research loop finished." Green
        break
    }

    $terminalState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    if ($null -ne $terminalState.terminal_campaign_status) {
        Write-Status "Official assessment complete: $($terminalState.terminal_campaign_status). Research loop finished." Green
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

    if ($researchState.schema_version -eq 4 -and $null -ne $researchState.pending_analysis) {
        Update-ResearchBrief
        $analysisExperiment = [int]$researchState.pending_analysis.experiment
        if ($null -ne $researchState.pending_analysis.evaluation_plan) {
            Write-Status "=== Resuming the researcher's accepted measurement plan ==="
            uv run python research/run_experiment.py --evaluate-pending
            if ($LASTEXITCODE -eq 130) {
                Write-Status "=== Requested measurement paused; completed measurements were saved ===" Yellow
                break
            }
            if ($LASTEXITCODE -ne 0) {
                throw "Runner execution of the accepted measurement request failed. The researcher deliverable was already accepted, so the researcher phase is not reopened."
            }
            Update-ResearchBrief
            continue
        }
        Remove-Item "research\evaluation_request.json", "research\proposal.json" -ErrorAction SilentlyContinue
        $completedMeasurementCount = @($researchState.pending_analysis.requested_evaluations).Count +
            @($researchState.pending_analysis.partial_evaluations).Count +
            @($researchState.pending_analysis.task_reference_evaluations).Count +
            @($researchState.pending_analysis.partial_task_reference_evaluations).Count
        $analysisPhasePrompt = if ($completedMeasurementCount -gt 0) {
            "Current phase: post-training analysis for trained experiment $analysisExperiment. New measurement results are available."
        }
        else {
            "Current phase: initial post-training analysis for trained experiment $analysisExperiment."
        }
        $analysisPrompt = @(
            $analysisPhasePrompt
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
            "Assess progress toward a learned policy satisfying the human objective. Inspect available training and measurement evidence; assess the question actually tested, whether a baseline, changed recipe, continuation, or replication. Relate the result to the proposal's expected_observation and contradicting_observation when present, recording partial or unexpected signals and uncertainty. Scope causal claims to the evidence rather than requiring a causal explanation."
            "Task performance supports claims of policy progress; logs, code, and training/evaluation discrepancies may all guide investigation. Choose what best advances the human objective, not necessarily the incumbent's largest failure group or the current investigation."
            "Decide whether more evidence would help resolve lineage or choose a useful next action. State the question or uncertainty, then select measurements proportionate to the uncertainty and their cost, including exploratory characterization when useful. Reuse compatible existing evidence. Comparison and task-reference measurement are optional."
            "Current candidates and eligible saved lineages can be remeasured through the existing request flow. If the relevant quantity is not currently emitted, you may modify researcher-owned measurement instrumentation before requesting it. Additional measurement rounds are optional and available only in this post-training phase."
            "At closure, update the Scientific strategy with reusable findings, limits, and a provisional next direction if research continues. That direction may replace the current investigation and may be revised during preparation; closing does not require resolving every assumption of a future experiment."
            "Choose exactly one outcome: write research/evaluation_request.json for another measurement round, or append the experiment postmortem and write a closure-only research/proposal.json choosing working lineage, code action, retention, and optionally best known. Candidate-only measurement and closure without new measurements are valid. If best_known remains unchanged, omit the best_known field. Do not restate or reselect it."
            "Request terminal assessment of best_known through request_final_benchmark when it is more valuable now than further research, considering task evidence, uncertainty, available compute, and likely benefit of further work. Explain that choice. This ends the campaign after either goal_reached or goal_not_reached; the result cannot inform a later hypothesis."
            "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
        ) -join " "
        Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "post-training analysis"
        $analysisStatus = Get-AnalysisSessionStatus 1
        Write-ResearcherSessionStatus $analysisStatus
        if (-not $analysisStatus.Complete) {
            $analysisProblem = $analysisStatus.Reason
            Write-Status "=== Analysis deliverable missing or invalid; retrying the same phase once ===" Yellow
            $analysisRetryPrompt = @(
                "Current phase: post-training analysis for experiment $analysisExperiment. The previous deliverable failed validation: $analysisProblem."
                "The same Researcher session context remains available. Correct only the invalid or missing deliverable: a valid research/evaluation_request.json for another measurement round, or the required postmortem plus a closure-only research/proposal.json."
                "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
            ) -join " "
            Invoke-ResearcherSession -Prompt $analysisRetryPrompt -Phase "post-training analysis" -Continue
            $analysisStatus = Get-AnalysisSessionStatus 2
            Write-ResearcherSessionStatus $analysisStatus
            if (-not $analysisStatus.Complete) {
                throw "Researcher ended twice without a valid post-training analysis deliverable. Last validation error: $($analysisStatus.Reason)"
            }
        }
        if (Test-Path "research\evaluation_request.json") {
            uv run python research/run_experiment.py --evaluate-pending
        }
        else {
            uv run python research/run_experiment.py
        }
        if ($LASTEXITCODE -eq 130) {
            Write-Status "=== Analysis execution paused; completed work remains saved ===" Yellow
            break
        }
        if ($LASTEXITCODE -ne 0) {
            throw "Runner execution of the accepted analysis deliverable failed. The researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Post-training analysis outcome recorded ===" Green
        continue
    }

    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        $evaluationPlanExists = $null -ne $researchState.pending_evaluation_request.evaluation_plan
        if (-not $evaluationPlanExists) {
            Remove-Item "research\evaluation_request.json" -ErrorAction SilentlyContinue
            Write-Status "=== Researcher designing evaluation for experiment $($researchState.pending_evaluation_request.experiment) ==="
            $evaluationPrompt = @(
                "Current phase: design the research evaluation for experiment $($researchState.pending_evaluation_request.experiment). Do not exit without the required deliverable."
                "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
                "Use the brief and campaign artifacts as the scientific evidence; evaluation design normally requires no Git inspection."
                "Start from the brief and instrument contract; inspect additional evidence only when the scientific question requires it, preferring targeted extraction over full-artifact reads."
                'State the scientific question first. Use the request-level `reason` to explain why the measurements are useful and proportionate to the uncertainty, and how their possible outcomes could change the current interpretation, model/lineage decision, or next scientific direction. Reuse compatible existing evidence, avoid genuinely redundant measurements, and broaden the evaluation scope when it helps explain the result or choose what comes next. Comparison and task-reference measurement are optional and must be justified by the question, not phase convention.'
                "Expected deliverable: research/evaluation_request.json for the current experiment, using the contract in research/instruments.md."
                "Do not start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the request."
            ) -join " "
            Invoke-ResearcherSession -Prompt $evaluationPrompt -Phase "evaluation design"
            $evaluationStatus = Get-EvaluationSessionStatus 1
            Write-ResearcherSessionStatus $evaluationStatus
            if (-not $evaluationStatus.Complete) {
                $evaluationProblem = $evaluationStatus.Reason
                Write-Status "=== Evaluation request missing or invalid; retrying the same phase once ===" Yellow
                $evaluationRetryPrompt = @(
                    "Current phase: evaluation design for experiment $($researchState.pending_evaluation_request.experiment). The previous deliverable failed validation: $evaluationProblem. Do not exit without a corrected deliverable."
                    "The same Researcher session context remains available. Correct only the invalid or missing research/evaluation_request.json."
                    "Reread one relevant contract or state file only if the validator error indicates that current state changed or an exact field definition is needed."
                    "Expected deliverable: a complete research/evaluation_request.json."
                    "Do not change phase, start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py."
                ) -join " "
                Invoke-ResearcherSession -Prompt $evaluationRetryPrompt -Phase "evaluation design" -Continue
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
        Write-Status "=== Researcher resolving lineage and scientific recipe for experiment $($researchState.pending_researcher_decision.experiment) ==="
        $decisionPrompt = @(
            "Current phase: close experiment $($researchState.pending_researcher_decision.experiment) and resolve its lineage and scientific recipe. Do not exit without the required deliverables."
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
            "Inspect the detailed evidence referenced for this experiment as needed to support the postmortem and lineage decision, preferring targeted extraction over full-artifact reads."
            "Use campaign artifacts for scientific evidence; inspect read-only Git only if the current experiment's scientific recipe delta is needed to justify keep or revert."
            "In the postmortem and Scientific strategy, assess the question actually tested against the proposal's expected_observation and contradicting_observation when present. Identify partial or unexpected signals, distinguish observations from interpretations, and scope causal claims to the evidence. When the campaign continues, choose a provisional next direction for its expected contribution to the human objective; it may replace the current investigation."
            "Set request_final_benchmark to true only when terminal assessment is the highest-value next action according to available development evidence; explain why it is more valuable now than further research. A true value ends the campaign after either verdict and cannot provide feedback for another hypothesis."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json, using the contracts in research/instruments.md."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        Invoke-ResearcherSession -Prompt $decisionPrompt -Phase "lineage decision"
        $pendingExperiment = [int]$researchState.pending_researcher_decision.experiment
        $lineageStatus = Get-LineageSessionStatus $pendingExperiment 1
        Write-ResearcherSessionStatus $lineageStatus
        if (-not $lineageStatus.Complete) {
            $lineageProblem = $lineageStatus.Reason
            Write-Status "=== Lineage deliverable invalid; retrying the same phase once ===" Yellow
            $decisionRetryPrompt = @(
                "Current phase: close experiment $pendingExperiment and resolve its lineage and scientific recipe. The previous deliverable failed validation: $lineageProblem. Do not exit without corrected deliverables."
                "The same Researcher session context remains available. Correct only the invalid or missing experiment entry in research/postmortems.md and lineage-only research/proposal.json."
                "Reread one relevant contract or state file only if the validator error indicates that current state changed or an exact field definition is needed."
                "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py."
            ) -join " "
            Invoke-ResearcherSession -Prompt $decisionRetryPrompt -Phase "lineage decision" -Continue
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
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $allocatedExperiment = [Math]::Max(
        [int]$researchState.last_allocated_experiment,
        [int]$researchState.last_experiment
    )
    $nextExperiment = $allocatedExperiment + 1
    $researchPrompt = @(
        "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending. Do not exit without the required deliverable."
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
        "Start from the campaign objective and current scientific strategy and available evidence. State the scientific question, then choose the fitting operation among continuation, replication or training. For continuation, state a hypothesis about the learning trajectory or training budget; for replication, state a hypothesis about process variability; for training, describe the recipe change and predicted benefit. When causal attribution is the question, explain how the experiment distinguishes competing explanations."
        "Only then justify the parent and fresh-or-transfer initialization by their expected benefit for the question as well as semantic compatibility with the parent policy and learned representation; unchanged tensor dimensions alone do not establish compatibility."
        "Available evidence tools include checkpoint inventory and raw-log query, structured-artifact analysis, code inspection, lightweight local analysis, and focused researcher-owned tests."
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        "Code or configuration edits are required only when the selected operation calls for them."
        "Expected deliverable: research/proposal.json for experiment $nextExperiment, using the unchanged contract in research/instruments.md, plus any edits called for by the selected operation."
        "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
        "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal."
    ) -join " "
    Invoke-ResearcherSession -Prompt $researchPrompt -Phase "new hypothesis"

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
        Write-Status "=== Research proposal missing or invalid; retrying the same phase once ===" Yellow
        $retryPrompt = @(
            "Current phase: prepare experiment $nextExperiment. The previous deliverable failed validation: $proposalProblem. Do not exit without a corrected deliverable."
            "The same Researcher session context remains available. Correct only the invalid or missing research/proposal.json for experiment $nextExperiment, preserving valid researcher-owned edits that belong to this unfinished experiment."
            "Reread one relevant contract or state file only if the validator error indicates that current state changed or an exact field definition is needed."
            "Expected deliverable: a corrected research/proposal.json for experiment $nextExperiment."
            "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py."
        ) -join " "
        Invoke-ResearcherSession -Prompt $retryPrompt -Phase "new hypothesis" -Continue

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
