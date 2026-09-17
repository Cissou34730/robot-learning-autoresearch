# Token-efficient autonomous robot-learning loop.

param(
    # Which Researcher runtime executes a phase. Both are supported and neither
    # is deprecated; Copilot stays the default so existing commands are unchanged.
    [ValidateSet("copilot", "opencode")]
    [string]$ResearcherBackend = "copilot",

    # Left unset so the backend's own default can be resolved below; a
    # provider-qualified id is only meaningful to the runtime that reads it.
    [ValidateNotNullOrEmpty()]
    [string]$Model,

    [ValidateSet("low", "medium", "high", "xhigh", "max")]
    [string]$Reasoning = "high",

    # 0 runs until the campaign reaches its own terminal state.
    [ValidateRange(0, [int]::MaxValue)]
    [int]$MaxExperiments = 15
)

Set-Location $PSScriptRoot

$backendDefaultModel = @{
    copilot  = "gpt-5.6-luna"
    opencode = "opencode-go/deepseek-v4.1-flash"
}
if (-not $Model) {
    $Model = $backendDefaultModel[$ResearcherBackend]
}
if ($ResearcherBackend -eq "opencode" -and $Reasoning -eq "max") {
    throw "The OpenCode runtime has no 'max' reasoning effort for these models. Use 'xhigh'."
}

# Node gained default TypeScript type stripping in 23.6; earlier versions need
# the experimental flag. Node is required only for the OpenCode backend.
function Get-OpenCodeNode {
    $node = Get-Command node -ErrorAction SilentlyContinue
    if (-not $node) {
        throw "The OpenCode runtime needs Node.js on PATH."
    }
    $version = (& node --version) -replace '^v', ''
    $parts = $version.Split('.')
    $major = [int]$parts[0]
    $minor = if ($parts.Length -gt 1) { [int]$parts[1] } else { 0 }
    $strip = if ($major -gt 23 -or ($major -eq 23 -and $minor -ge 6)) {
        @()
    }
    else {
        @('--experimental-strip-types')
    }
    return @{ Path = $node.Source; Strip = $strip }
}

function Get-OpenCodeServerExecutable {
    $command = Get-Command opencode -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $command) {
        throw "The OpenCode runtime needs the opencode CLI on PATH."
    }
    if ([System.IO.Path]::GetExtension($command.Source) -ieq ".exe") {
        return $command.Source
    }

    $volta = Get-Command volta -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($volta) {
        $packageEntry = (& $volta.Source which opencode).Trim()
        if ($LASTEXITCODE -eq 0 -and $packageEntry) {
            $candidate = Join-Path (Split-Path -Parent $packageEntry) `
                "node_modules\opencode-ai\bin\opencode.exe"
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }
    }

    throw "The OpenCode server executable could not be resolved behind $($command.Source)."
}

function Start-OpenCodeCampaignServer {
    $separator = $Model.IndexOf("/")
    if ($separator -le 0 -or $separator -eq ($Model.Length - 1)) {
        throw "OpenCode needs a provider-qualified model, received '$Model'."
    }
    $providerId = $Model.Substring(0, $separator)
    $modelId = $Model.Substring($separator + 1)
    $models = @{}
    $models[$modelId] = @{ options = @{ reasoningEffort = $Reasoning } }
    $providers = @{}
    $providers[$providerId] = @{ models = $models }
    $config = @{
        permission = @{ bash = "ask" }
        provider = $providers
    } | ConvertTo-Json -Depth 10 -Compress

    $listener = [System.Net.Sockets.TcpListener]::new(
        [System.Net.IPAddress]::Loopback,
        0
    )
    $listener.Start()
    $port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    $url = "http://127.0.0.1:$port"
    $executable = Get-OpenCodeServerExecutable

    $previousConfig = $env:OPENCODE_CONFIG_CONTENT
    try {
        $env:OPENCODE_CONFIG_CONTENT = $config
        $process = Start-Process -FilePath $executable -ArgumentList @(
            "serve",
            "--hostname=127.0.0.1",
            "--port=$port"
        ) -PassThru -NoNewWindow
    }
    finally {
        if ($null -eq $previousConfig) {
            Remove-Item Env:OPENCODE_CONFIG_CONTENT -ErrorAction SilentlyContinue
        }
        else {
            $env:OPENCODE_CONFIG_CONTENT = $previousConfig
        }
    }

    try {
        $ready = $false
        for ($attempt = 0; $attempt -lt 120; $attempt++) {
            if ($process.HasExited) {
                break
            }
            try {
                $response = Invoke-WebRequest -Uri "$url/path" -TimeoutSec 1 -UseBasicParsing
                if ($response.StatusCode -eq 200) {
                    $ready = $true
                    break
                }
            }
            catch {
            }
            [System.Threading.Thread]::Sleep(250)
        }
        if (-not $ready) {
            throw "The OpenCode campaign server did not become ready at $url."
        }
        Write-Status "OpenCode campaign server ready at $url" -Color DarkGray -Label researcher
        return @{ Process = $process; Url = $url }
    }
    catch {
        if (-not $process.HasExited) {
            $process.Kill()
            $process.WaitForExit()
        }
        $process.Dispose()
        throw
    }
}

function Stop-OpenCodeCampaignServer {
    if ($script:OpenCodeServerProcess) {
        if (-not $script:OpenCodeServerProcess.HasExited) {
            $script:OpenCodeServerProcess.Kill()
            $script:OpenCodeServerProcess.WaitForExit()
        }
        $script:OpenCodeServerProcess.Dispose()
        $script:OpenCodeServerProcess = $null
        $script:OpenCodeServerUrl = $null
    }
}

# Exclusion is per worktree: two checkouts own separate campaign artifacts, so
# only the same worktree must be serialized. The reset wrapper derives the same
# name from this same helper and still excludes a loop running here.
. "$PSScriptRoot\researcher_mutex.ps1"

$createdNew = $false
$loopMutex = [System.Threading.Mutex]::new(
    $true,
    (Get-WorktreeMutexName -Worktree $PSScriptRoot),
    [ref]$createdNew
)
if (-not $createdNew) {
    $loopMutex.Dispose()
    throw "Another robot autoresearch loop is already running in this worktree."
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
        [Parameter(Mandatory)][int]$Experiment,
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
        "--experiment", "$Experiment"
        "--phase", $Phase
        "--attempt", $(if ($Continue) { "2" } else { "1" })
    )
    if ($researchState.campaign.id) {
        $sessionArgs += @("--campaign-id", $researchState.campaign.id)
    }
    if ($Continue) {
        $sessionArgs += "--resume"
    }
    if ($ResearcherBackend -eq "opencode") {
        $entry = "researcher_opencode/src/main.ts"
        if (-not (Test-Path -LiteralPath $entry)) {
            throw "The OpenCode runtime entry point is missing: $entry"
        }
        $node = Get-OpenCodeNode
        if (-not $script:OpenCodeServerUrl) {
            throw "The OpenCode campaign server is not running."
        }
        $sessionArgs += @("--server-url", $script:OpenCodeServerUrl)
        $nodeArgs = @()
        $nodeArgs += $node.Strip
        $nodeArgs += $entry
        $nodeArgs += $sessionArgs
        $nodeArgs += $Prompt
        & $node.Path @nodeArgs
    }
    else {
        uv run --group researcher python researcher_copilot.py @sessionArgs $Prompt
    }
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
if ($ResearcherBackend -eq "opencode") {
    $openCodeServer = Start-OpenCodeCampaignServer
    $script:OpenCodeServerProcess = $openCodeServer.Process
    $script:OpenCodeServerUrl = $openCodeServer.Url
}
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
            "Assess progress toward a learned policy satisfying the human objective. Begin with the observed training and measurement evidence, including partial, unexpected, or orthogonal signals. Relate findings to the proposal's type-specific question and reasoning without treating prior expectations as policy-acceptance thresholds. Separate observations from interpretations and scope causal claims to the evidence."
            "Measured task performance is what supports a claim of policy progress; logs, code, and training/evaluation discrepancies guide the investigation."
            "Available evidence tools include checkpoint inventory and raw-log query, structured-artifact analysis, code inspection, lightweight local analysis, researcher measurement instrumentation, research measurement, task-reference measurement, and optional paired comparison. Evidence gathering may discover or refine the scientific question. If the quantity you need is not emitted, modify researcher-owned instrumentation before requesting it. Additional measurement rounds are optional and available only in this phase."
            "Choose exactly one outcome: write research/evaluation_request.json for another measurement round, or append the experiment postmortem and write a closure-only research/proposal.json choosing working lineage, code action, retention, and optionally best known. Candidate-only measurement and closure without new measurements are valid. Omit best_known when it is unchanged."
            'If you request measurements, each `selection` cites an observed signal or explicit uncertainty, states why measuring that model is useful, and names the next decision the result could change. Checkpoint position, order in a listing, and labels are descriptive context and not sufficient reasons on their own. Each `omitted_alternative` names an available model left outside the request, or is null only when every available model is requested.'
            "Further training is an ordinary next experiment after closure; do not prepare that proposal now."
            "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
        ) -join " "
        Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "post-training analysis" -Experiment $analysisExperiment
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
            Invoke-ResearcherSession -Prompt $analysisRetryPrompt -Phase "post-training analysis" -Experiment $analysisExperiment -Continue
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
                "Start from the campaign objective and available evidence. Inspection may formulate, refine, or answer the scientific question; targeted extraction and full-artifact inspection are both available."
                'State the scientific question and use the request-level `reason` to explain why the measurement round is useful.'
                'Every measurement requires a `selection` that cites an observed signal or explicit uncertainty, states why measuring that model is useful, and names the next decision the result could change. Checkpoint position, order in a listing, and labels are descriptive context and not sufficient reasons on their own. Each `omitted_alternative` names an available model left outside the request, or is null only when every available model is requested.'
                "Expected deliverable: research/evaluation_request.json for the current experiment, using the contract in research/instruments.md."
                "Do not start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the request."
            ) -join " "
            Invoke-ResearcherSession -Prompt $evaluationPrompt -Phase "evaluation design" -Experiment $researchState.pending_evaluation_request.experiment
            $evaluationStatus = Get-EvaluationSessionStatus 1
            Write-ResearcherSessionStatus $evaluationStatus
            if (-not $evaluationStatus.Complete) {
                $evaluationProblem = $evaluationStatus.Reason
                Write-Status "=== Evaluation request missing or invalid; retrying the same phase once ===" Yellow
                $evaluationRetryPrompt = @(
                    "Current phase: evaluation design for experiment $($researchState.pending_evaluation_request.experiment). The previous deliverable failed validation: $evaluationProblem. Do not exit without a corrected deliverable."
                    "The same Researcher session context remains available. Correct only the invalid or missing research/evaluation_request.json."
                    "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                    "Do not change phase, start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py."
                ) -join " "
                Invoke-ResearcherSession -Prompt $evaluationRetryPrompt -Phase "evaluation design" -Experiment $researchState.pending_evaluation_request.experiment -Continue
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
            "Use campaign artifacts for scientific evidence; inspect read-only Git only if the current experiment's scientific recipe delta is needed to justify keep or revert."
            "Assess progress toward a learned policy satisfying the human objective. Begin with observed behavior, then relate findings to the proposal's type-specific question and reasoning. Record partial and unexpected findings, separate observations from interpretations, and scope claims to the evidence."
            "Resolve investigation assessment, saved-policy usefulness, recipe action, working lineage, retention, optional best-known designation, and terminal readiness as distinct scientific decisions. A weakened prediction does not by itself reject a useful policy."
            "Record supported, weakened, and unresolved findings in the experiment entry without prescribing a continuation path. The campaign's Scientific strategy is rewritten in the next experiment-design phase, not here."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json, using the contracts in research/instruments.md."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        Invoke-ResearcherSession -Prompt $decisionPrompt -Phase "lineage decision" -Experiment $researchState.pending_researcher_decision.experiment
        $pendingExperiment = [int]$researchState.pending_researcher_decision.experiment
        $lineageStatus = Get-LineageSessionStatus $pendingExperiment 1
        Write-ResearcherSessionStatus $lineageStatus
        if (-not $lineageStatus.Complete) {
            $lineageProblem = $lineageStatus.Reason
            Write-Status "=== Lineage deliverable invalid; retrying the same phase once ===" Yellow
            $decisionRetryPrompt = @(
                "Current phase: close experiment $pendingExperiment and resolve its lineage and scientific recipe. The previous deliverable failed validation: $lineageProblem. Do not exit without corrected deliverables."
                "The same Researcher session context remains available. Correct only the invalid or missing experiment entry in research/postmortems.md and lineage-only research/proposal.json."
                "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py."
            ) -join " "
            Invoke-ResearcherSession -Prompt $decisionRetryPrompt -Phase "lineage decision" -Experiment $researchState.pending_researcher_decision.experiment -Continue
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

    $allocatedExperiment = [Math]::Max(
        [int]$researchState.last_allocated_experiment,
        [int]$researchState.last_experiment
    )
    if ($MaxExperiments -gt 0 -and $allocatedExperiment -ge $MaxExperiments) {
        Write-Status "Experiment budget reached: $allocatedExperiment of $MaxExperiments. Research loop finished." Green
        break
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
    $nextExperiment = $allocatedExperiment + 1
    $researchPrompt = @(
        "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending."
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
        "Start from the campaign objective and the whole campaign's evidence, then rewrite the Scientific strategy as provisional memory that prescribes no next action."
        "State the scientific question, decide whether the investigation is confirmatory, diagnostic, or exploratory, and choose the operation that best answers it. Define an intervention only when the selected investigation requires one. Available preparation operations: continuation, training with fresh or transfer initialization, and replication."
        "Justify the parent and fresh-or-transfer initialization by their expected benefit for the question as well as semantic compatibility with the parent policy and learned representation; unchanged tensor dimensions alone do not establish compatibility."
        "Available evidence tools include checkpoint inventory and raw-log query, structured-artifact analysis, code inspection, lightweight local analysis, and focused researcher-owned tests."
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        "Code or configuration edits are required only when the selected operation calls for them."
        "Expected deliverable: research/proposal.json for experiment $nextExperiment, using the contract in research/instruments.md, plus any edits called for by the selected operation."
        "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
        "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal."
    ) -join " "
    Invoke-ResearcherSession -Prompt $researchPrompt -Phase "new hypothesis" -Experiment $nextExperiment

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
            "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
            "Expected deliverable: a corrected research/proposal.json for experiment $nextExperiment."
            "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py."
        ) -join " "
        Invoke-ResearcherSession -Prompt $retryPrompt -Phase "new hypothesis" -Experiment $nextExperiment -Continue

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
    Write-Status "=== Experiment $nextExperiment session closed ===" Green
    Start-Sleep -Seconds 5
}
}
finally {
    Stop-OpenCodeCampaignServer
    $loopMutex.ReleaseMutex()
    $loopMutex.Dispose()
}
