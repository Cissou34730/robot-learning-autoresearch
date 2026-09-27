# Token-efficient robot-learning research loop.

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
    [int]$MaxExperiments = 15,

    # Optional external control channel. The orchestrator owns this unique path
    # for one launcher invocation and raises the request by creating the file.
    [string]$StopRequestPath,

    [ValidateRange(1, 3600)]
    [int]$StopTimeoutSeconds = 180
)

Set-Location $PSScriptRoot

$script:CampaignExitCode = 0
$script:CampaignStopRequested = $false
$script:StopDeadlineExceeded = $false
$script:StopDeadline = $null
$script:StopRequestPath = if ($StopRequestPath) {
    [System.IO.Path]::GetFullPath($StopRequestPath)
}
elseif (-not $SessionId) {
    $null
}
if ($script:StopRequestPath) {
    $stopParent = Split-Path -Parent $script:StopRequestPath
    if (-not (Test-Path -LiteralPath $stopParent -PathType Container)) {
        throw "The stop-request parent directory does not exist: $stopParent"
    }
    if (Test-Path -LiteralPath $script:StopRequestPath -PathType Container) {
        throw "The stop-request path is a directory, not a file: $($script:StopRequestPath)"
    }
}

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

$researcherPersonaGuidance = @(
    "You are the principal investigator responsible for leading this campaign toward a learned policy that satisfies the human objective, without lowering scientific standards or inventing certainty. You bring deep expertise in robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software, and you integrate these disciplines to understand and reshape the complete embodied learning system."
    "You set the scientific direction. Develop and challenge mechanistic explanations, determine which unknowns matter, create the measurements and tools needed to resolve them, and redesign any Researcher-owned part of the system when the evidence warrants it. Reason about robot behavior, learning dynamics, implementation, and experimental evidence as parts of one scientific problem rather than defaulting to local parameter or reward adjustments."
    "The human supplies the objective and protected boundary, not the research program. Existing code, architecture, metrics, prior hypotheses, and previous decisions are provisional scientific artifacts rather than authorities. Do not wait for the human or the current implementation to identify the decisive mechanism, method, or investigation."
) -join " "
$scientificModelUseGuidance = "Use research/scientific_model.md as the campaign's initial physical model. Test its interpretation against observed behavior and carry forward what the campaign learns; do not treat it as an intervention menu."
$researchFreedomGuidance = "Everything in the researcher-owned surface is fully yours. Nothing there is sacred, preferred, required to remain recognizable, or exempt from replacement. You may inspect, create, rewrite, combine, or remove any researcher-owned scientific implementation or tool; existing files and module structure carry no scientific authority."
$scientificMemoryGuidance = "Maintain the Scientific strategy as a causal research map with four durable registers: current synthesis, lessons and limits, competing explanations, and the decision frontier. The frontier records the unresolved distinction and evidence that would discriminate or redirect it, not a candidate implementation."
$activeMethodGuidance = @(
    "An inquiry owns one principal-investigator session from its allocation and opening through measurements, method work, training, post-training analysis, method decisions, and maturity; closing the inquiry clears that session."
    "An active method is declared before its first training run and remains the same scientific program across training iterations. Its lifecycle is concept, development, mature, promoted, retained, or abandoned."
    "Its current lineage and iteration history are independent of the working, best-known, and retained roles. A training collapse is evidence and does not automatically discard the method."
    "Every method transition is one method_decision. A mature method has ended its training iteration and may be measured, promoted with compatible paired evidence against working, retained, or abandoned from the inquiry."
) -join " "
$investigationDesignGuidance = @(
    "Frame training through investigation_design. State either a predicted_behavioral_path or an open_question; neither form is preferred."
    "Connect the design to evidence, the objective, initialization, rationale, and an expected observation without assuming an incumbent-local intervention."
) -join " "
$laboratoryReuseGuidance = @(
    "The brief lists published research/lab files as available campaign artifacts."
    "Using an existing laboratory file, creating a new one, or using no laboratory artifact is a scientific choice."
) -join " "
$script:ResumeAnalysisSession = $false

function Request-CampaignStop([string]$message) {
    if ($script:CampaignStopRequested) {
        return $true
    }
    $script:CampaignStopRequested = $true
    $script:StopDeadline = [DateTime]::UtcNow.AddSeconds($StopTimeoutSeconds)
    Write-Status (
        "$message; waiting up to $StopTimeoutSeconds seconds " +
        "for cooperative shutdown."
    ) -Color Yellow -Label launcher
    return $true
}

function Test-CampaignStopRequested {
    if ($script:CampaignStopRequested) {
        return $true
    }
    if (
        $script:StopRequestPath -and
        (Test-Path -LiteralPath $script:StopRequestPath -PathType Leaf)
    ) {
        return Request-CampaignStop "External stop requested"
    }
    return $false
}

function Invoke-CooperativeProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$Operation
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.WorkingDirectory = $PSScriptRoot
    $startInfo.UseShellExecute = $false
    foreach ($argument in $ArgumentList) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    if ($script:StopRequestPath) {
        $startInfo.Environment["ROBOT_RESEARCH_STOP_REQUEST"] = $script:StopRequestPath
    }
    else {
        [void]$startInfo.Environment.Remove("ROBOT_RESEARCH_STOP_REQUEST")
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        if (-not $process.Start()) {
            throw "Could not start $Operation."
        }
        while (-not $process.WaitForExit(100)) {
            if (
                (Test-CampaignStopRequested) -and
                [DateTime]::UtcNow -ge $script:StopDeadline
            ) {
                $script:StopDeadlineExceeded = $true
                throw (
                    "The cooperative stop deadline expired while waiting for " +
                    "$Operation (PID $($process.Id))."
                )
            }
        }
        $process.WaitForExit()
        [void](Test-CampaignStopRequested)
        return [int]$process.ExitCode
    }
    finally {
        $process.Dispose()
    }
}

function Invoke-Runner {
    param([string[]]$Arguments = @())

    $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $runnerArguments = @("run", "python", "research/run_experiment.py")
    $runnerArguments += $Arguments
    return Invoke-CooperativeProcess -FilePath $uv.Source `
        -ArgumentList $runnerArguments -Operation "research runner"
}

function Invoke-InquiryAnchor {
    $exitCode = Invoke-Runner -Arguments @("--begin-inquiry")
    if (Test-StopAfterOperation $exitCode "research runner") {
        return 130
    }
    if ($exitCode -ne 0) {
        throw "Could not establish the scientific parent of the next experiment."
    }
    return 0
}

function Invoke-PreparationMeasurement {
    while ($true) {
        $script:researchState = Get-Content "research\research_state.json" -Raw |
            ConvertFrom-Json
        $pending = $script:researchState.pending_evaluation_request
        $repair = if ($pending) { $pending.implementation_error } else { $null }
        if ($repair) {
            $attempts = [int]$pending.implementation_repair_attempts
            if ($attempts -ge 2) {
                throw (
                    "The Researcher used both implementation repair attempts. " +
                    "The accepted measurement remains pending for maintainer review."
                )
            }
            $piSession = $script:researchState.inquiry_session
            if (-not $piSession -or -not $piSession.id) {
                throw "The inquiry has no persisted principal-investigator session identity."
            }
            $repairAttempt = $attempts + 1
            $repairPrompt = @(
                "Current phase: implementation repair, attempt $repairAttempt of 2."
                "The accepted preparation measurement did not execute because Researcher-owned code raised the runtime error below."
                "This produced no scientific evidence and does not challenge the relevance, question, or design of the accepted measurement."
                "Continue the same investigation. Diagnose the runtime failure from the code, repository context, and traceback, then correct only its implementation cause in Researcher-owned code."
                "Do not modify research/evaluation_request.json; the accepted request is frozen and will be retried unchanged."
                "Use AGENTS.md and the other repository context as factual constraints; the launcher does not diagnose the cause of the failure."
                "Runtime error from $($repair.causal_path): $($repair.error)"
                "Do not execute training or evaluation and do not invoke research/run_experiment.py; the launcher validates the repair and retries the measurement."
            ) -join " "
            Invoke-ResearcherSession -Prompt $repairPrompt `
                -Phase "principal investigator" -Experiment 0 `
                -SessionId $piSession.id -Continue
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                return 130
            }
            $runnerExitCode = Invoke-Runner -Arguments @(
                "--record-implementation-repair-attempt"
            )
            if (Test-StopAfterOperation $runnerExitCode "research runner") {
                return 130
            }
            if ($runnerExitCode -ne 0) {
                throw "Could not record the completed implementation repair attempt."
            }
            if (-not (Test-ImplementationRepair)) {
                Write-Status (
                    "=== Implementation repair invalid; resuming the same " +
                    "session once more ==="
                ) Yellow
                continue
            }
            $script:researchState = Get-Content "research\research_state.json" -Raw |
                ConvertFrom-Json
        }
        $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            return 130
        }
        if ($runnerExitCode -eq 3) {
            continue
        }
        return $runnerExitCode
    }
}

function Test-StopAfterOperation {
    param(
        [AllowNull()][Nullable[int]]$ExitCode,
        [Parameter(Mandatory)][string]$Operation
    )

    if (-not (Test-CampaignStopRequested)) {
        return $false
    }
    if ($null -eq $ExitCode -or $ExitCode -notin @(0, 130)) {
        throw (
            "$Operation exited with code $ExitCode instead of completing " +
            "cooperatively after the stop request."
        )
    }
    $script:CampaignExitCode = 130
    return $true
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
        ) -PassThru -WindowStyle Hidden
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
        throw "The research runtime is internally inconsistent: robot_learning.train and research.run_experiment could not both be imported. No researcher session, training, evaluation, or lifecycle decision was started."
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
        [string]$SessionId,
        [switch]$Continue,
        [switch]$ResumeOrCreate,
        [switch]$Preliminary
    )
    if ($Continue -and $ResumeOrCreate) {
        throw "A researcher session cannot be both strict-resume and resume-or-create."
    }
    if ($SessionId) {
        $script:ResearcherSessionId = $SessionId
        $script:ResearcherSessionPhase = $Phase
        $script:ResearcherSessionExperiment = $Experiment
    }
    if ($Continue) {
        if (-not $script:ResearcherSessionId) {
            throw "There is no researcher session to continue for this phase."
        }
        if (
            $script:ResearcherSessionPhase -ne $Phase -or
            $script:ResearcherSessionExperiment -ne $Experiment
        ) {
            throw "The active researcher session belongs to another phase."
        }
    }
    elseif ($ResumeOrCreate) {
        if (-not $script:ResearcherSessionId) {
            throw "There is no persisted researcher session identity to resume or create."
        }
        if (
            $script:ResearcherSessionPhase -ne $Phase -or
            $script:ResearcherSessionExperiment -ne $Experiment
        ) {
            throw "The persisted researcher session belongs to another phase."
        }
    }
    else {
        # Each phase owns its session, so a retry resumes that phase and
        # never inherits whichever session last ran on this machine.
        if (-not $SessionId) {
            $script:ResearcherSessionId = [guid]::NewGuid().ToString()
        }
        $script:ResearcherSessionPhase = $Phase
        $script:ResearcherSessionExperiment = $Experiment
    }
    Write-Status "=== Researcher phase: $Phase ===" -Color Magenta -Label researcher
    Write-Status "Model: $model, reasoning: $reasoning" -Color Magenta -Label researcher
    $sessionArgs = @(
        "--session-id", $script:ResearcherSessionId
        "--model", $model
        "--reasoning", $reasoning
        "--phase", $Phase
        "--attempt", $(if ($Continue) { "2" } else { "1" })
    )
    if ($Experiment -gt 0) {
        $sessionArgs += @("--experiment", "$Experiment")
    }
    if ($researchState.campaign.id) {
        $sessionArgs += @("--campaign-id", $researchState.campaign.id)
    }
    if ($Continue) {
        $sessionArgs += "--resume"
    }
    elseif ($ResumeOrCreate) {
        $sessionArgs += "--resume-or-create"
    }
    if ($Preliminary) {
        $sessionArgs += "--preliminary"
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
        $script:ResearcherExitCode = Invoke-CooperativeProcess `
            -FilePath $node.Path -ArgumentList $nodeArgs `
            -Operation "OpenCode researcher"
    }
    else {
        $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $copilotArgs = @(
            "run", "--group", "researcher", "python", "researcher_copilot.py"
        )
        $copilotArgs += $sessionArgs
        $copilotArgs += $Prompt
        $script:ResearcherExitCode = Invoke-CooperativeProcess `
            -FilePath $uv.Source -ArgumentList $copilotArgs `
            -Operation "Copilot researcher"
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
        git commit -m "camp: record research postmortem"
        if ($LASTEXITCODE -ne 0) {
            throw "Could not commit the research postmortem."
        }
        Push-CurrentCommit
    }
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

function Test-PreparationDeliverable {
    param([switch]$TrainingCapReached)

    $arguments = @("--check-preparation-deliverable")
    if ($TrainingCapReached) {
        $arguments += "--training-cap-reached"
    }
    $validationOutput = @(
        uv run python research/run_experiment.py @arguments 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:PreparationValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:PreparationValidationFeedback
        return $false
    }
    return $true
}

function Test-ScientificModelDeliverable {
    $validationOutput = @(
        uv run python research/run_experiment.py --check-scientific-model-deliverable 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:ScientificModelValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:ScientificModelValidationFeedback
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

function Test-ImplementationRepair {
    $validationOutput = @(
        uv run python research/run_experiment.py --complete-implementation-repair 2>&1
    )
    $validationExitCode = $LASTEXITCODE
    $script:ImplementationRepairFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($validationExitCode -ne 0) {
        Write-Host $script:ImplementationRepairFeedback
        return $false
    }
    return $true
}

# The phases below observe the same facts: what the process did,
# whether the deliverable exists, and whether the protected validator accepts it.
function Get-ProposalSessionStatus(
    [string]$phase,
    [int]$attempt,
    [switch]$TrainingCapReached
) {
    # Preparation accepts either a proposal or a saved-lineage measurement
    # request, so both files are observed before the deliverable is judged.
    $measurementPresent = Test-Path "research\evaluation_request.json"
    $present = $measurementPresent -or (Test-Path "research\proposal.json")
    $valid = $false
    $reason = "research/proposal.json or research/evaluation_request.json was not created"
    if ($present) {
        $valid = Test-PreparationDeliverable `
            -TrainingCapReached:$TrainingCapReached
        $reason = if ($valid) { "" } else { $script:PreparationValidationFeedback }
    }
    $deliverable = if ($measurementPresent) {
        "research/evaluation_request.json"
    }
    else {
        "research/proposal.json"
    }
    New-ResearcherSessionStatus -Phase $phase -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable $deliverable `
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

function Get-ScientificModelSessionStatus([int]$attempt) {
    $present = Test-Path "research\scientific_model.md" -PathType Leaf
    $valid = $false
    $reason = "research/scientific_model.md was not created"
    if ($present) {
        $valid = Test-ScientificModelDeliverable
        $reason = if ($valid) { "" } else { $script:ScientificModelValidationFeedback }
    }
    New-ResearcherSessionStatus -Phase "scientific model" -Attempt $attempt `
        -ExitCode $script:ResearcherExitCode `
        -Deliverable "research/scientific_model.md" `
        -Present $present -Valid $valid -Reason $reason
}

# The operations offered to the Researcher are derived from persisted state, so
# a prompt states the Runner's contract for the current state and nothing
# narrower. Unavailable operations carry the invariant that blocks them.
function New-LegalOperation([string]$Name, [bool]$Legal, [string]$Detail) {
    [pscustomobject]@{ Name = $Name; Legal = $Legal; Detail = $Detail }
}

function Get-InquiryOperations {
    param(
        [Parameter(Mandatory)]$State,
        [switch]$TrainingCapReached
    )
    $inquiry = $State.active_inquiry
    $method = $State.active_method
    $operations = @()
    if ($null -eq $inquiry) {
        $operations += New-LegalOperation "inquiry open" $true (
            "research/proposal.json with inquiry action open and non-empty " +
            "question, scope, and closure_condition; this inquiry's PI session " +
            "then owns it until close"
        )
        $operations += New-LegalOperation "campaign_conclusion" $true (
            "research/proposal.json with action request_final_benchmark, only " +
            "when you expect the designated best_known to return goal_reached, " +
            "or no_further_experiment"
        )
        $operations += New-LegalOperation "evaluation_request" $false (
            "measurement belongs to an open inquiry"
        )
        return $operations
    }
    $lifecycle = if ($null -ne $method) { [string]$method.lifecycle } else { "" }
    $hasLineage = $null -ne $method -and $null -ne $method.current_lineage
    $methodLineage = if ($hasLineage) { ", active_method" } else { "" }
    $operations += New-LegalOperation "evaluation_request" $true (
        "research/evaluation_request.json without experiment, measuring saved " +
        "lineages (working, best_known$methodLineage, or a retained ID) for the " +
        "inquiry question"
    )
    $operations += New-LegalOperation "inquiry reframe" $true (
        "research/proposal.json with revised question, scope, closure_condition, " +
        "and rationale; inquiry and PI session identity are unchanged"
    )
    $inquiryClose = (
        "research/proposal.json with inquiry action close and a durable outcome; " +
        "closing clears the PI session, after which another inquiry or " +
        "campaign_conclusion is legal"
    )
    if ($null -eq $method) {
        $operations += New-LegalOperation "method start" $true (
            "research/proposal.json declaring the inquiry's method with " +
            "lifecycle concept or development before its first training"
        )
        $operations += New-LegalOperation "inquiry close" $true $inquiryClose
        $operations += New-LegalOperation "training" $false (
            "training belongs to a declared active method"
        )
    }
    elseif ($lifecycle -in @("promoted", "retained", "abandoned")) {
        $operations += New-LegalOperation "inquiry close" $true $inquiryClose
        $operations += New-LegalOperation "training" $false (
            "method $($method.id) is $lifecycle; no further iteration belongs " +
            "to this inquiry"
        )
    }
    else {
        if ($TrainingCapReached) {
            $operations += New-LegalOperation "training" $false (
                "the training allocation cap is reached; allocating another " +
                "training experiment is the only operation this removes"
            )
        }
        else {
            $operations += New-LegalOperation "training" $true (
                "research/proposal.json with kind training, continuation, or " +
                "replication and method_id $($method.id)"
            )
        }
        if ($lifecycle -eq "mature") {
            $operations += New-LegalOperation "method_decision promote" $true (
                "research/proposal.json without experiment; requires compatible, " +
                "fingerprint-bound paired evidence of the current active_method " +
                "lineage against working, normally from an inquiry measurement " +
                "after maturity; working changes and best_known changes only " +
                "when explicitly designated"
            )
        }
        else {
            $operations += New-LegalOperation "method_decision promote" $false (
                "promotion requires a method already marked mature by a " +
                "post-training method_decision"
            )
        }
        if ($hasLineage) {
            $operations += New-LegalOperation "method_decision retain" $true (
                "research/proposal.json without experiment preserving the " +
                "current method lineage under a unique retained_id"
            )
        }
        else {
            $operations += New-LegalOperation "method_decision retain" $false (
                "retention requires a current method lineage"
            )
        }
        $operations += New-LegalOperation "method_decision abandon" $true (
            "research/proposal.json without experiment and with code revert or " +
            "restore; it cannot restore active_method"
        )
        $operations += New-LegalOperation "method_decision continue/refine/mature" $false (
            "these actions decide a training iteration and require pending " +
            "post-training analysis"
        )
        $operations += New-LegalOperation "inquiry close" $false (
            "the $lifecycle method must first be promoted, retained, or abandoned"
        )
    }
    $operations += New-LegalOperation "campaign_conclusion" $false (
        "the campaign may conclude only after the active inquiry is closed"
    )
    return $operations
}

function Get-AnalysisOperations {
    param([Parameter(Mandatory)]$State)
    $pending = $State.pending_analysis
    $experiment = [int]$pending.experiment
    $operations = @()
    $operations += New-LegalOperation "evaluation_request" $true (
        "research/evaluation_request.json with experiment $experiment for " +
        "another measurement round of its candidates or saved lineages"
    )
    if ($pending.baseline) {
        $operations += New-LegalOperation "baseline_decision" $true (
            "research/proposal.json with experiment $experiment, a measured " +
            "candidate, and a reason; the selection becomes both working and " +
            "best_known"
        )
        $operations += New-LegalOperation "inquiry open" $false (
            "an inquiry starts only after the selected baseline is designated " +
            "as both working and best_known"
        )
        return $operations
    }
    $method = $State.active_method
    $lifecycle = [string]$method.lifecycle
    $hasLineage = $null -ne $method.current_lineage
    $candidateRequirement = if ($hasLineage) {
        "candidate may be omitted to keep the current active_method lineage"
    }
    else {
        "candidate is required because the method has no current lineage"
    }
    $decision = (
        "research/proposal.json with method_decision experiment $experiment, " +
        "after the experiment postmortem; $candidateRequirement"
    )
    $operations += New-LegalOperation "method_decision continue" $true (
        "$decision; the method stays in development with the selected candidate " +
        "or available lineage"
    )
    $operations += New-LegalOperation "method_decision refine" $true (
        "$decision; the method stays in development with the selected candidate " +
        "or available lineage for a revised iteration"
    )
    $operations += New-LegalOperation "method_decision mature" $true (
        "$decision; the method becomes mature with the selected lineage and the " +
        "inquiry may then measure, promote, retain, or abandon it without training"
    )
    if ($lifecycle -eq "mature") {
        $operations += New-LegalOperation "method_decision promote" $true (
            "$decision; requires compatible, fingerprint-bound paired evidence " +
            "of the current active_method lineage against working"
        )
    }
    else {
        $operations += New-LegalOperation "method_decision promote" $false (
            "promotion requires a method already marked mature and paired " +
            "evidence against working, normally from a later inquiry measurement"
        )
    }
    if ($hasLineage) {
        $operations += New-LegalOperation "method_decision retain" $true (
            "$decision; preserves the method's current lineage under a unique " +
            "retained_id"
        )
    }
    else {
        $operations += New-LegalOperation "method_decision retain" $false (
            "retention preserves an existing current method lineage and this " +
            "method has none yet"
        )
    }
    $operations += New-LegalOperation "method_decision abandon" $true (
        "$decision; requires code revert or restore and cannot restore active_method"
    )
    return $operations
}

function Format-OperationContract($Operations) {
    $legal = @(
        $Operations | Where-Object { $_.Legal } |
            ForEach-Object { "$($_.Name): $($_.Detail)" }
    )
    $blocked = @(
        $Operations | Where-Object { -not $_.Legal } |
            ForEach-Object { "$($_.Name) ($($_.Detail))" }
    )
    $contract = "Legal operations from the current state: " + ($legal -join "; ") + "."
    if ($blocked.Count -gt 0) {
        $contract += " Not legal from the current state: " + ($blocked -join "; ") + "."
    }
    return $contract
}

try {
if ($ResearcherBackend -eq "opencode") {
    $openCodeServer = Start-OpenCodeCampaignServer
    $script:OpenCodeServerProcess = $openCodeServer.Process
    $script:OpenCodeServerUrl = $openCodeServer.Url
}
:CampaignLoop while ($true) {
    if (Test-CampaignStopRequested) {
        $script:CampaignExitCode = 130
        break
    }

    if (Test-Path "research\GOAL_REACHED") {
        Write-Status "GOAL REACHED - research loop finished." Green
        break
    }

    $terminalState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    if ($null -ne $terminalState.pending_inquiry_operation) {
        Write-Status "=== Resuming the pending inquiry operation ==="
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Inquiry operation publication failed. The pending outcome remains recoverable."
        }
        Update-ResearchBrief
        continue
    }
    if (
        $null -ne $terminalState.pending_baseline_decision -or
        $null -ne $terminalState.pending_method_decision
    ) {
        Write-Status "=== Resuming the pending decision publication ==="
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Decision publication failed. The pending decision remains recoverable."
        }
        Update-ResearchBrief
        continue
    }
    if ($null -ne $terminalState.pending_campaign_conclusion) {
        # Finish a conclusion before any terminal status is honored, so a
        # restart cannot exit on terminal state with the decision unpublished.
        Write-Status "=== Resuming the pending campaign conclusion ==="
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Campaign conclusion publication failed. The pending decision remains recoverable."
        }
        Update-ResearchBrief
        continue
    }
    if ($null -ne $terminalState.terminal_campaign_status) {
        if ($terminalState.terminal_campaign_status -eq "no_further_experiment") {
            Write-Status "Researcher concluded that no further experiment is warranted. Research loop finished." Green
        }
        else {
            Write-Status "Official assessment complete: $($terminalState.terminal_campaign_status). Research loop finished." Green
        }
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
        $runnerExitCode = Invoke-Runner -Arguments @(
            "--reuse-candidate", $recoveryCandidate
        )
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Experiment paused again; progress remains saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
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
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Experiment paused again ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Restarted experiment failed."
        }
        Update-ResearchBrief
        Write-Status "=== Restarted experiment complete ===" Green
        continue
    }
    if ($null -ne $terminalState.pending_training_operation) {
        if (-not (Test-Path "research\proposal.json")) {
            throw "Accepted training operation has no proposal to resume."
        }
        Write-Status "=== Resuming the accepted training operation ==="
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Accepted training operation remains pending after recovery failed."
        }
        Update-ResearchBrief
        continue
    }

    $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    $allocatedExperiment = [Math]::Max(
        [int]$researchState.last_allocated_experiment,
        [int]$researchState.last_experiment
    )
    $budgetReached = $MaxExperiments -gt 0 -and $allocatedExperiment -ge $MaxExperiments
    if ($null -ne $researchState.pending_final_benchmark) {
        Write-Status "=== Evaluating the committed accepted lineage on the final benchmark ==="
        $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending-final")
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Final benchmark failed. The committed lineage remains pending for recovery."
        }
        Update-ResearchBrief
        Write-Status "=== Final benchmark complete ===" Green
        continue
    }

    if ($null -ne $researchState.pending_analysis) {
        Update-ResearchBrief
        $analysisExperiment = [int]$researchState.pending_analysis.experiment
        $methodAnalysis = -not [bool]$researchState.pending_analysis.baseline
        $analysisInquirySession = $researchState.inquiry_session
        if ($methodAnalysis -and (-not $analysisInquirySession -or -not $analysisInquirySession.id)) {
            throw "Method analysis has no persisted inquiry PI session."
        }
        if ($null -ne $researchState.pending_analysis.evaluation_plan) {
            Write-Status "=== Resuming the researcher's accepted measurement plan ==="
            $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
            if (Test-StopAfterOperation $runnerExitCode "research runner") {
                break
            }
            if ($runnerExitCode -eq 130) {
                Write-Status "=== Requested measurement paused; completed measurements were saved ===" Yellow
                break
            }
            if ($runnerExitCode -ne 0) {
                throw "Runner execution of the accepted measurement request failed. The researcher deliverable was already accepted, so the researcher phase is not reopened."
            }
            Update-ResearchBrief
            if (
                $script:ResearcherSessionId -and
                $script:ResearcherSessionPhase -eq "post-training analysis" -and
                $script:ResearcherSessionExperiment -eq $analysisExperiment
            ) {
                $script:ResumeAnalysisSession = $true
            }
            continue
        }
        # Only a stale closure proposal is cleared here. The runner removes a
        # consumed evaluation request itself, so a legitimate preparation
        # measurement request is never silently discarded at this boundary.
        Remove-Item "research\proposal.json" -ErrorAction SilentlyContinue
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
        $resumeAnalysisSession = $methodAnalysis -or (
            $script:ResumeAnalysisSession -and
            $script:ResearcherSessionId -and
            $script:ResearcherSessionPhase -eq "post-training analysis" -and
            $script:ResearcherSessionExperiment -eq $analysisExperiment
        )
        $analysisContract = Format-OperationContract (
            Get-AnalysisOperations -State $researchState
        )
        $analysisPrompt = @(
            $analysisPhasePrompt
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
            $researcherPersonaGuidance
            $scientificModelUseGuidance
            $researchFreedomGuidance
            $scientificMemoryGuidance
            $(if ($methodAnalysis) { $activeMethodGuidance })
            $laboratoryReuseGuidance
            $(if ($resumeAnalysisSession) {
                    "The measurement you requested is complete. Continue the same investigation from its results and your existing session context."
                }
                else {
                    "Assess the trained policies and evidence against the human objective and the campaign's active inquiry."
                })
            $(if ($researchState.pending_analysis.baseline) {
                    "Before the initial baseline is selected, the only legal operations are a baseline measurement round and baseline_decision. No inquiry, method, training, or campaign conclusion exists until the selected baseline is designated as both working and best_known."
                }
                else {
                    "Choose exactly one outcome: another question-relative measurement round, or one method_decision for this experiment after appending its postmortem. Working comparison or promotion is never implicit."
                })
            $analysisContract
            $(if ($methodAnalysis -and $budgetReached) {
                    "The training allocation cap is reached. It removes only later training allocation; every method_decision above remains valid, and after the decision the inquiry can still measure, promote a mature method with evidence, retain, abandon, reframe, or close."
                })
            $(if ($methodAnalysis) {
                    "Further training is a later inquiry operation; do not prepare that proposal during analysis."
                })
            "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
        ) -join " "
        if ($methodAnalysis) {
            Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "principal investigator" -Experiment 0 -SessionId $analysisInquirySession.id -Continue
        }
        elseif ($resumeAnalysisSession) {
            Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "post-training analysis" -Experiment $analysisExperiment -Continue
        }
        else {
            Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "post-training analysis" -Experiment $analysisExperiment
        }
        $script:ResumeAnalysisSession = $false
        if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
            break
        }
        $analysisStatus = Get-AnalysisSessionStatus 1
        Write-ResearcherSessionStatus $analysisStatus
        if (-not $analysisStatus.Complete) {
            $analysisProblem = $analysisStatus.Reason
            Write-Status "=== Analysis deliverable missing or invalid; retrying the same phase once ===" Yellow
            $analysisRetryPrompt = @(
                "Current phase: post-training analysis for experiment $analysisExperiment. The previous deliverable failed validation: $analysisProblem."
                "The same Researcher session context remains available. Correct only the invalid or missing deliverable."
                $analysisContract
                $(if ($methodAnalysis) { $activeMethodGuidance })
                "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
            ) -join " "
            if ($methodAnalysis) {
                Invoke-ResearcherSession -Prompt $analysisRetryPrompt -Phase "principal investigator" -Experiment 0 -SessionId $analysisInquirySession.id -Continue
            }
            else {
                Invoke-ResearcherSession -Prompt $analysisRetryPrompt -Phase "post-training analysis" -Experiment $analysisExperiment -Continue
            }
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                break CampaignLoop
            }
            $analysisStatus = Get-AnalysisSessionStatus 2
            Write-ResearcherSessionStatus $analysisStatus
            if (-not $analysisStatus.Complete) {
                throw "Researcher ended twice without a valid post-training analysis deliverable. Last validation error: $($analysisStatus.Reason)"
            }
        }
        $analysisRequestedMeasurement = Test-Path "research\evaluation_request.json"
        if ($analysisRequestedMeasurement) {
            $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
        }
        else {
            $runnerExitCode = Invoke-Runner
        }
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Analysis execution paused; completed work remains saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Runner execution of the accepted analysis deliverable failed. The researcher phase is not reopened."
        }
        Update-ResearchBrief
        if ($analysisRequestedMeasurement -and -not $methodAnalysis) {
            $script:ResumeAnalysisSession = $true
        }
        Write-Status "=== Post-training analysis outcome recorded ===" Green
        continue
    }

    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        Write-Status "=== Resuming the researcher's inquiry measurement ==="
        $runnerExitCode = Invoke-PreparationMeasurement
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Inquiry measurement paused; completed measurements were saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Runner execution of the accepted inquiry measurement failed. The researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Inquiry measurement complete; returning to the inquiry ===" Green
        continue
    }

    if (Test-Path "research\BASELINE_PENDING") {
        if (-not (Test-Path "research\scientific_model.md" -PathType Leaf)) {
            # The maintainer-owned persona prompt for this phase. It is supplied
            # verbatim and is the single place to edit its wording.
            $scientificModelPhasePrompt = @'
You are the principal investigator responsible for leading this campaign toward a learned policy that satisfies the human objective, without lowering scientific standards or inventing certainty. You bring deep expertise in robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software, and you integrate these disciplines to understand the complete embodied learning system.

In this preliminary phase, construct the campaign's physical and scientific model before any training or campaign evidence exists. Work from first principles and the human-authored implementation to explain the robot as an embodied dynamical system: how its morphology, actuation, sensing, control loop, simulator, and task geometry jointly determine the behaviors that are possible, constrained, or scientifically uncertain.

Do not produce a component inventory or a repository summary. Build a scientific model of the system.

Analyze, from first principles and from the human-authored implementation:

* the robot morphology, degrees of freedom, geometry, reachable workspace, joint constraints, and relevant kinematic structure;
* the actuation model and how commanded actions produce physical motion over time;
* the important dynamic properties of the simulated robot, including timing, damping, inertia, control authority, and any other properties that materially affect behavior;
* the initial physical state and how it shapes the task the controller must solve;
* the geometry and physical requirements of the task;
* the coupled physical capabilities required for success, including reaching, trajectory control, convergence, stabilization, and any other relevant behaviors, together with physically justified interactions between them;
* the sensing and observation model: what physical state is observable, what is derived, what may be ambiguous, and what information is unavailable;
* the relationship between observation, control action, robot motion, and task outcome;
* alternative physical configurations or solutions available to the robot, such as multiple kinematic solutions where relevant;
* physical, kinematic, dynamic, control, or observability constraints that may create qualitatively different classes of behavior or failure;
* which physical quantities across the complete behavior would be scientifically meaningful for understanding the robot.

Treat approach, reaching, tolerance entry, settling, and sustained task completion as coupled parts of one embodied control process. A task-stage label such as non-reach or interrupted hold describes an observed outcome, not by itself its cause. When the implementation supports the conclusion, explain how changing one capability could alter another. Do not rank capabilities, unknowns, or measurable quantities as priorities for later research.

For each important conclusion, distinguish between:

1. **Established fact** — directly supported by the human-authored task, robot, simulator, environment, observation, control, or benchmark implementation.
2. **Physical or scientific consequence** — something that follows from those facts through robotics, control, or dynamical reasoning.
3. **Unknown** — something that cannot be determined from the implementation alone and would require observing actual robot behavior.

Do not infer current weaknesses, current failure modes, or likely causes of poor performance. Do not propose experiments, interventions, training changes, reward changes, hyperparameter changes, algorithm changes, or research directions.

### Strict evidence boundary

Do not inspect or use any artifact produced by a research campaign, training run, evaluation run, or Researcher.

In particular, do not read or use:

* campaign history;
* experiment records;
* postmortems;
* scientific strategy or synthesis;
* research briefs;
* training logs;
* checkpoints or checkpoint inventories;
* evaluation results;
* benchmark results from previous runs;
* lineage state;
* retained-model state;
* previous proposals;
* previous measurements;
* generated research analysis.

Do not use training outcomes or previous Researcher decisions to infer what matters physically.

You may inspect only the system intentionally defined by the human before the campaign begins: the robot model, simulator configuration, task and benchmark definition, environment mechanics, action interface, observation/sensing implementation, success semantics, fixed constraints, and other human-authored code necessary to understand the physical system.

If a file mixes human-defined system specification with campaign-generated state, use only the human-defined specification and ignore the generated state.

The final output should be a compact but substantive **Scientific model of the robot and task**. It should explain how the complete coupled system works physically and scientifically, not merely list what files contain or imply a future intervention agenda.
'@
            if (-not $scientificModelPhasePrompt.Trim() -or $scientificModelPhasePrompt -match "PLACEHOLDER") {
                throw "The scientific-model phase prompt is still a placeholder. The maintainer must supply it before starting a campaign."
            }
            $scientificModelPrompt = @(
                $scientificModelPhasePrompt
                "Read AGENTS.md and research/scenario.md, then inspect only the relevant human-authored robot, simulator, environment, observation, control, task, and benchmark implementation. Do not read research/program.md or research/instruments.md in this phase."
                "Write the final output to research/scientific_model.md."
            ) -join "`n`n"
            Invoke-ResearcherSession -Prompt $scientificModelPrompt -Phase "scientific model" -Experiment 1 -Preliminary
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                break CampaignLoop
            }
            $scientificModelStatus = Get-ScientificModelSessionStatus 1
            Write-ResearcherSessionStatus $scientificModelStatus
            if (-not $scientificModelStatus.Complete) {
                $scientificModelProblem = $scientificModelStatus.Reason
                Write-Status "=== Scientific model missing or invalid; retrying the same phase once ===" Yellow
                $scientificModelRetryPrompt = @(
                    "Current phase: scientific model. The previous deliverable failed validation: $scientificModelProblem."
                    "The same Researcher session context remains available. Correct only research/scientific_model.md, separating established facts, physical or scientific consequences, and unknowns."
                    "Do not run training, measurements, Git mutations, or research/run_experiment.py; the launcher validates the deliverable."
                ) -join " "
                Invoke-ResearcherSession -Prompt $scientificModelRetryPrompt -Phase "scientific model" -Experiment 1 -Continue -Preliminary
                if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                    break CampaignLoop
                }
                $scientificModelStatus = Get-ScientificModelSessionStatus 2
                Write-ResearcherSessionStatus $scientificModelStatus
                if (-not $scientificModelStatus.Complete) {
                    throw "Researcher ended twice without a valid research/scientific_model.md. Last validation error: $($scientificModelStatus.Reason)"
                }
            }
        }
        elseif (-not (Test-ScientificModelDeliverable)) {
            throw "The existing campaign scientific model is invalid. The maintainer must reset the campaign: $script:ScientificModelValidationFeedback"
        }
        Write-Status "=== Running fresh baseline training ==="
        @{
            baseline = $true
            change = "Fresh baseline"
            hypothesis = "Establish the initial baseline for the human-defined objective."
            class = "baseline"
            initialization = "fresh"
        } | ConvertTo-Json | Set-Content "research\proposal.json"

        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Baseline interrupted cleanly; it remains pending ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Baseline failed. The research loop stopped instead of silently continuing."
        }
        if (-not (Test-Path "research\scientific_model.md" -PathType Leaf)) {
            throw "Baseline completed without research/scientific_model.md. The maintainer must reset the campaign."
        }
        Update-ResearchBrief
        Write-Status "=== Baseline training complete; researcher evaluation comes next ===" Green
        continue
    }

    if ($budgetReached) {
        Write-Status "Training allocation cap reached: $allocatedExperiment of $MaxExperiments. Non-training inquiry operations remain available." Yellow
    }

    # Anchor the rollback baseline before the researcher can change or commit
    # science. An unfinished experiment keeps the anchor it already established.
    $runnerExitCode = Invoke-InquiryAnchor
    if ($runnerExitCode -eq 130) {
        break
    }
    $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json

    Update-ResearchBrief

    if (Test-Path "research\evaluation_request.json" -PathType Leaf) {
        if (Test-PreparationDeliverable -TrainingCapReached:$budgetReached) {
            Write-Status "=== Resuming the researcher's saved-lineage measurement request ==="
            $runnerExitCode = Invoke-PreparationMeasurement
            if ($runnerExitCode -eq 130) {
                Write-Status "=== Preparation measurement paused; completed measurements were saved ===" Yellow
                break
            }
            if ($runnerExitCode -ne 0) {
                throw "Runner execution of the accepted preparation measurement request failed. The researcher phase is not reopened."
            }
            Update-ResearchBrief
            Write-Status "=== Preparation measurement complete; the inquiry resumes with new evidence ===" Green
            continue
        }
        Write-Status "=== Existing preparation deliverable is invalid; returning it to the principal investigator ===" Yellow
    }

    Write-Status "=== Principal investigator advancing the inquiry ==="
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $nextExperiment = $allocatedExperiment + 1
    $piSession = $researchState.inquiry_session
    if (-not $piSession -or -not $piSession.id) {
        throw "The inquiry has no persisted principal-investigator session identity."
    }
    $resumePreparationSession = $piSession.status -in @("starting", "started")
    $hasPreparationEvidence = $null -ne $researchState.preparation_measurement
    $inquiryOperations = Get-InquiryOperations -State $researchState `
        -TrainingCapReached:$budgetReached
    $inquiryContract = Format-OperationContract $inquiryOperations
    $trainingLegal = @(
        $inquiryOperations | Where-Object { $_.Name -eq "training" -and $_.Legal }
    ).Count -gt 0
    $researchPrompt = @(
        $(if ($resumePreparationSession -and $hasPreparationEvidence) {
                "Current phase: continue the campaign's active inquiry. The measurement you requested is complete; continue from its results and your existing session context."
            }
            elseif ($resumePreparationSession) {
                "Current phase: continue as principal investigator for this inquiry identity. Reconsider the accumulated evidence before choosing the next operation."
            }
            else {
                "Current phase: define or conduct one bounded inquiry. No training analysis or measurement is pending."
            })
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
        $researcherPersonaGuidance
        $scientificModelUseGuidance
        $scientificMemoryGuidance
        $researchFreedomGuidance
        $activeMethodGuidance
        $(if ($trainingLegal) { $investigationDesignGuidance })
        $laboratoryReuseGuidance
        "Choose one scientifically justified operation; no operation is the default."
        $inquiryContract
        $(if ($budgetReached) {
                "The training allocation cap is reached. It removes only the allocation of another training experiment; every other operation listed as legal remains a valid scientific choice."
            })
        "Request the official final assessment only if you expect it to return goal_reached; it is a terminal verdict, not an instrument for resolving development uncertainty."
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        "Expected deliverable: exactly one legal operation above, written as research/evaluation_request.json or research/proposal.json according to research/instruments.md."
        "The phase is complete when that deliverable has been written. Closing an inquiry records its durable outcome, clears its PI session, starts no experiment, and does not end the campaign."
        "Do not start training, execute measurements, or invoke research/run_experiment.py; the launcher validates and executes the proposal or accepted measurement request."
    ) -join " "
    if ($piSession.status -eq "allocated") {
        $runnerExitCode = Invoke-Runner -Arguments @("--mark-inquiry-session-starting")
        if ($runnerExitCode -ne 0) {
            throw "Could not mark the inquiry session as starting."
        }
        $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
        $piSession = $researchState.inquiry_session
    }
    if ($piSession.status -eq "started") {
        Invoke-ResearcherSession -Prompt $researchPrompt -Phase "principal investigator" -Experiment 0 -SessionId $piSession.id -Continue
    }
    elseif ($piSession.status -eq "starting") {
        Invoke-ResearcherSession -Prompt $researchPrompt -Phase "principal investigator" -Experiment 0 -SessionId $piSession.id -ResumeOrCreate
    }
    else {
        throw "The inquiry PI session has an invalid persisted status."
    }
    if (
        $piSession.status -eq "starting" -and
        $script:ResearcherExitCode -in @(0, 5, 130)
    ) {
        $runnerExitCode = Invoke-Runner -Arguments @("--mark-inquiry-session-started")
        if ($runnerExitCode -ne 0) {
            throw "Could not mark the inquiry session as started."
        }
    }
    if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
        break
    }
    $runnerExitCode = Invoke-InquiryAnchor
    if ($runnerExitCode -eq 130) {
        break
    }

    $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    if ($resultCountAfter -gt $resultCountBefore) {
        throw "The researcher executed an experiment during the inquiry phase. The loop stopped without attempting a retry or another execution; restart it to continue from the persisted state."
    }

    # Observed before the runner's own bookkeeping, so a brief or commit failure
    # cannot swallow what the session did.
    $proposalStatus = Get-ProposalSessionStatus "principal investigator" 1 `
        -TrainingCapReached:$budgetReached
    Write-ResearcherSessionStatus $proposalStatus
    Update-ResearchBrief
    Save-ResearchMemory
    if (-not $proposalStatus.Complete) {
        $proposalProblem = $proposalStatus.Reason
        Write-Status "=== Research proposal missing or invalid; retrying the same phase once ===" Yellow
        $retryPrompt = @(
            "Current phase: continue the inquiry. The previous deliverable failed validation: $proposalProblem. Do not exit without a corrected deliverable."
            "The same principal-investigator session remains available. Correct only the invalid or missing research/proposal.json or research/evaluation_request.json, preserving valid researcher-owned edits."
            $activeMethodGuidance
            $(if ($trainingLegal) { $investigationDesignGuidance })
            $laboratoryReuseGuidance
            $inquiryContract
            "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
            "Expected deliverable: exactly one corrected legal operation above."
            "Do not start training, execute measurements, or invoke research/run_experiment.py."
        ) -join " "
        Invoke-ResearcherSession -Prompt $retryPrompt -Phase "principal investigator" -Experiment 0 -SessionId $piSession.id -Continue
        if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
            break CampaignLoop
        }
        $runnerExitCode = Invoke-InquiryAnchor
        if ($runnerExitCode -eq 130) {
            break CampaignLoop
        }

        $resultCountAfter = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
        if ($resultCountAfter -gt $resultCountBefore) {
            throw "The researcher executed an experiment during the inquiry retry. The loop stopped without attempting another execution; restart it to continue from the persisted state."
        }

        $proposalStatus = Get-ProposalSessionStatus "principal investigator" 2 `
            -TrainingCapReached:$budgetReached
        Write-ResearcherSessionStatus $proposalStatus
        Update-ResearchBrief
        Save-ResearchMemory

        if (-not $proposalStatus.Complete) {
            throw "Researcher ended twice without a proposal valid for the current phase. The loop stopped safely: $($proposalStatus.Reason)"
        }
    }
    if (Test-Path "research\evaluation_request.json") {
        # A saved-lineage measurement is executed before any proposal, then the
        # phase reopens with its results available for the parent decision.
        Write-Status "=== Executing the researcher's saved-lineage measurement request ==="
        $runnerExitCode = Invoke-PreparationMeasurement
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Preparation measurement paused; completed measurements were saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Runner execution of the accepted preparation measurement request failed. The researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Preparation measurement complete; the inquiry resumes with new evidence ===" Green
        continue
    }
    $runnerArguments = @()
    if ($budgetReached) {
        $runnerArguments += "--training-cap-reached"
    }
    $runnerExitCode = Invoke-Runner -Arguments $runnerArguments
    if (Test-StopAfterOperation $runnerExitCode "research runner") {
        break
    }
    if ($runnerExitCode -eq 130) {
        Write-Status "=== Experiment interrupted cleanly; no model decision was made ===" Yellow
        break
    }
    if ($runnerExitCode -ne 0) {
        throw "Experiment runner failed. The loop stopped safely."
    }
    Update-ResearchBrief
    $completedState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    if ([int]$completedState.last_experiment -gt $allocatedExperiment) {
        Write-Status "=== Experiment $nextExperiment training complete ===" Green
    }
    else {
        Write-Status "=== Inquiry operation recorded ===" Green
    }
    for ($delay = 0; $delay -lt 50; $delay++) {
        if (Test-CampaignStopRequested) {
            $script:CampaignExitCode = 130
            break CampaignLoop
        }
        Start-Sleep -Milliseconds 100
    }
}
}
catch {
    if ($script:StopDeadlineExceeded) {
        $script:CampaignExitCode = 124
        Write-Error $_
    }
    else {
        throw
    }
}
finally {
    try {
        Stop-OpenCodeCampaignServer
    }
    finally {
        $loopMutex.ReleaseMutex()
        $loopMutex.Dispose()
    }
}
if ($script:CampaignExitCode -ne 0) {
    exit $script:CampaignExitCode
}
