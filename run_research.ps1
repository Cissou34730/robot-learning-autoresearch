# Goal-centered robot-learning research launcher.

param(
    [ValidateSet("copilot", "opencode")]
    [string]$PIBackend = "copilot",

    [ValidateNotNullOrEmpty()]
    [string]$Model,

    [ValidateSet("low", "medium", "high", "xhigh", "max")]
    [string]$Reasoning = "high",

    [ValidateRange(1, [int]::MaxValue)]
    [int]$MaxInquiries = 15,

    [string]$StopRequestPath,

    [ValidateRange(1, 3600)]
    [int]$StopTimeoutSeconds = 180
)

Set-Location $PSScriptRoot

$script:CampaignExitCode = 0
$script:CampaignStopRequested = $false
$script:StopDeadlineExceeded = $false
$script:MaxInquiriesExplicit = $PSBoundParameters.ContainsKey("MaxInquiries")
$script:StopDeadline = $null
$script:StopRequestPath = if ($StopRequestPath) {
    [System.IO.Path]::GetFullPath($StopRequestPath)
}
else {
    $null
}
$script:PISessionId = $null
$script:PISessionStateId = $null
$script:PISessionInvocation = 0
$script:PIExitCode = $null
$script:PITrustSnapshot = $null
$script:PITrustPreliminary = $false

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
    $Model = $backendDefaultModel[$PIBackend]
}
if ($PIBackend -eq "opencode" -and $Reasoning -eq "max") {
    throw "The OpenCode runtime has no 'max' reasoning effort for these models. Use 'xhigh'."
}

$piPersona = @(
    "You are the Principal Investigator responsible for leading this campaign toward a learned policy that satisfies the human goal, without lowering scientific standards or inventing certainty. You bring deep expertise in robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software, and you integrate these disciplines to understand and reshape the complete embodied learning system."
    "You set the scientific direction. Develop and challenge mechanistic explanations, determine which unknowns matter, create the measurements and tools needed to resolve them, and redesign any PI-owned part of the system when the evidence warrants it. Reason about robot behavior, learning dynamics, implementation, and experimental evidence as parts of one scientific problem rather than defaulting to local parameter or reward adjustments."
    "The human supplies the goal and protected boundary, not the research program. Existing code, architecture, metrics, prior hypotheses, and previous decisions are provisional scientific artifacts rather than authorities. Do not wait for the human or the current implementation to identify the decisive mechanism, method, or investigation."
) -join " "
$scientificModelUseGuidance = @(
    "Use research/scientific_model.md as the campaign's initial physical model. Test its interpretation against observed behavior and carry forward what the campaign learns; do not treat it as an intervention menu or a passive reference."
    "Use its physical consequences and unknowns to form competing mechanistic explanations. When an unresolved mechanism could change the scientific direction, seek evidence that discriminates between those explanations; when it cannot, state why it is not consequential."
) -join " "
$scientificModelPhaseObjective = @'
Construct the campaign's physical and scientific model before any training or campaign evidence exists. Work from first principles and the human-authored implementation to explain the robot as an embodied dynamical system: how its morphology, actuation, sensing, control loop, simulator, and task geometry jointly determine the behaviors that are possible, constrained, or scientifically uncertain.

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

The final output should be a compact but substantive Scientific model of the robot and task. It should explain how the complete coupled system works physically and scientifically, not merely list what files contain or imply a future intervention agenda.
'@

function Request-CampaignStop([string]$Message) {
    if ($script:CampaignStopRequested) {
        return $true
    }
    $script:CampaignStopRequested = $true
    $script:StopDeadline = [DateTime]::UtcNow.AddSeconds($StopTimeoutSeconds)
    Write-Status (
        "$Message; waiting up to $StopTimeoutSeconds seconds for cooperative shutdown."
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

function Enter-TrustedMutableInvocation {
    if (-not $script:PITrustSnapshot) {
        return
    }
    Assert-PITrustSnapshot -Snapshot $script:PITrustSnapshot
}

function Invoke-Runner {
    param([string[]]$Arguments = @())

    Enter-TrustedMutableInvocation
    $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $runnerArguments = @("run", "python", "research/run_experiment.py")
    $runnerArguments += $Arguments
    $exitCode = Invoke-CooperativeProcess -FilePath $uv.Source `
        -ArgumentList $runnerArguments -Operation "research runner"
    $script:PITrustSnapshot = New-PITrustSnapshot `
        -Preliminary:$script:PITrustPreliminary
    return $exitCode
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
        @("--experimental-strip-types")
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
    uv run python -c "import research.run_experiment"
    if ($LASTEXITCODE -ne 0) {
        throw "The research runtime is internally inconsistent. No PI session or Runner operation was started."
    }
}

Assert-ResearchRuntime
. "$PSScriptRoot\researcher_session.ps1"

function Invoke-PISession {
    param(
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)][string]$Phase,
        [switch]$Continue,
        [switch]$Preliminary
    )

    Enter-TrustedMutableInvocation
    $script:PITrustPreliminary = [bool]$Preliminary
    $script:PITrustSnapshot = New-PITrustSnapshot -Preliminary:$Preliminary

    if ($Preliminary) {
        if ($Continue -and -not $script:PISessionId) {
            throw "There is no active preliminary PI backend session to continue."
        }
        if (-not $Continue) {
            $script:PISessionId = [guid]::NewGuid().ToString()
            $script:PISessionInvocation = 1
        }
        else {
            $script:PISessionInvocation += 1
        }
    }
    else {
        if (-not $script:PISessionId) {
            throw "The active scientific session has no persisted backend session ID."
        }
        $script:PISessionInvocation += 1
    }
    $state = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    $displaySession = if ($Preliminary) {
        "campaign preparation"
    }
    elseif ($state.scientific_session.id) {
        "$($state.scientific_session.id) $($Phase -replace '_', ' ')"
    }
    else {
        ($Phase -replace '_', ' ')
    }
    Write-ConsoleCard `
        -Title "PI | $displaySession" `
        -Color Magenta
    $sessionArgs = @(
        "--session-id", $script:PISessionId
        "--model", $Model
        "--reasoning", $Reasoning
        "--phase", $Phase
        "--attempt", "$script:PISessionInvocation"
    )
    if ($state.campaign.id) {
        $sessionArgs += @("--campaign-id", $state.campaign.id)
    }
    if ($Preliminary -and $Continue) {
        $sessionArgs += "--resume"
    }
    elseif (-not $Preliminary) {
        $sessionArgs += "--resume-or-create"
    }
    if ($Preliminary) {
        $sessionArgs += "--preliminary"
    }

    if ($PIBackend -eq "opencode") {
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
        $script:PIExitCode = Invoke-CooperativeProcess `
            -FilePath $node.Path -ArgumentList $nodeArgs `
            -Operation "OpenCode PI"
    }
    else {
        $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
            Select-Object -First 1
        $copilotArgs = @(
            "run", "--group", "researcher", "python", "researcher_copilot.py"
        )
        $copilotArgs += $sessionArgs
        $copilotArgs += $Prompt
        $script:PIExitCode = Invoke-CooperativeProcess `
            -FilePath $uv.Source -ArgumentList $copilotArgs `
            -Operation "Copilot PI"
    }
}

function Update-ResearchBrief {
    Enter-TrustedMutableInvocation
    uv run python research/build_research_brief.py
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build the compact PI research brief."
    }
}

function Get-HumanGoalSummary {
    param([Parameter(Mandatory)]$State)

    $scenario = Get-Content "research\scenario.md" -Raw
    $successCriterionMatch = [regex]::Match(
        $scenario,
        '(?ms)^## Success criterion\s+(?<body>.*?)(?=^## |\z)'
    )
    $successCriterion = if ($State.human_goal.summary) {
        [string]$State.human_goal.summary
    }
    elseif ($successCriterionMatch.Success) {
        (($successCriterionMatch.Groups["body"].Value -replace '\s+', ' ').Trim())
    }
    else {
        ""
    }
    $officialScope = (
        "Official scope: the complete target distribution in " +
        "research/scenario.md, across its full radius and angular ranges, " +
        "with success requiring the complete uninterrupted in-tolerance hold."
    )
    if ($successCriterion) {
        return "$officialScope Campaign criterion: $successCriterion"
    }
    return "$officialScope The protected campaign criterion is defined there."
}

function Get-LatestSessionResult {
    param([Parameter(Mandatory)]$State)

    $session = $State.scientific_session
    if (-not $session -or -not $session.operation_ids -or $session.operation_ids.Count -eq 0) {
        return "No operation has completed in the current line of work."
    }
    $identifier = [string]$session.operation_ids[-1]
    $event = $State.operation_events |
        Where-Object { $_.id -eq $identifier -and $_.status -eq "completed" } |
        Select-Object -First 1
    if (-not $event) {
        return "There is no completed result for $identifier; the failed attempt is not evidence."
    }
    $result = $event.result
    if ($event.kind -eq "measurement") {
        $measurements = @($result.measurements | ForEach-Object {
            $metrics = $_.metrics
            $artifact = if ($metrics.evaluation_artifact) {
                [string]$metrics.evaluation_artifact
            }
            else {
                "none"
            }
            $facts = [ordered]@{}
            $metrics.PSObject.Properties |
                Where-Object {
                    $_.Name -notin @(
                        "episode_results",
                        "evaluation_artifact",
                        "evaluation_artifact_fingerprint",
                        "model_fingerprint"
                    )
                } |
                ForEach-Object { $facts[$_.Name] = $_.Value }
            $renderedFacts = $facts | ConvertTo-Json -Compress -Depth 100
            "$($_.label): artifact=$artifact; metrics=$renderedFacts"
        })
        $comparisons = @($result.paired_comparisons)
        $comparisonFact = if ($comparisons.Count -gt 0) {
            ($comparisons | ConvertTo-Json -Compress -Depth 100)
        }
        else {
            "none"
        }
        return (
            "Operation $identifier (measurement): $($measurements -join ' | '); " +
            "comparisons=$comparisonFact."
        )
    }
    if ($event.kind -eq "training") {
        $dynamics = @($result.learning_dynamics | ForEach-Object {
            (
                "$($_.candidate): steps=$($_.training_steps), " +
                "success=$($_.training_success), reward=$($_.ep_rew_mean)"
            )
        })
        $changed = @($result.mechanical_provenance.changed_files | ForEach-Object {
            [string]$_.path
        })
        $candidates = @($result.candidates)
        return (
            "Operation $identifier (training): candidates=$($candidates -join ', '); " +
            "learning dynamics=$($dynamics -join ' | '); provenance parent=" +
            "$($result.mechanical_provenance.code_parent_commit), changed=" +
            "$($changed -join ', ')."
        )
    }
    $fact = if ($result.summary) {
        [string]$result.summary
    }
    elseif ($result.status) {
        [string]$result.status
    }
    elseif ($result.outcome) {
        [string]$result.outcome
    }
    else {
        "completed"
    }
    return "Operation $identifier ($($event.kind)) recorded factual result: $fact."
}

function Get-CampaignResourceSummary {
    param([Parameter(Mandatory)]$State)

    $completed = @($State.operation_events | Where-Object { $_.status -eq "completed" })
    $measurements = @($completed | Where-Object { $_.kind -eq "measurement" }).Count
    $training = @($completed | Where-Object { $_.kind -eq "training" }).Count
    return (
        "inquiries $([int]$State.counters.inquiry)/$([int]$State.campaign.max_inquiries) | " +
        "sessions $([int]$State.counters.session) | measurements $measurements | " +
        "training $training | candidates $($State.candidates.PSObject.Properties.Count)"
    )
}

function Get-RequiredSessionSummaryTransition {
    param([Parameter(Mandatory)]$State)

    $session = $State.scientific_session
    if (-not $session) {
        return $null
    }
    if (
        $session.kind -eq "goal_review" -and
        $State.active_inquiry -and
        $State.active_inquiry.opened_in_session -eq $session.id
    ) {
        return [pscustomobject]@{
            Objective = (
                "Save the goal-review session summary after opening " +
                "$($State.active_inquiry.id)."
            )
            Inquiry = (
                "$($State.active_inquiry.id) has been opened, but it is not " +
                "actionable until this goal-review session ends and its fresh " +
                "inquiry session starts."
            )
            CheckpointGuidance = (
                "Use the checkpoint contract in research/instruments.md and " +
                "preserve the opened inquiry, its evidence basis, the observed " +
                "remaining goal gap, and the transition to its fresh session."
            )
        }
    }
    if (
        $session.kind -eq "inquiry" -and
        $session.operation_ids -and
        $session.operation_ids.Count -gt 0
    ) {
        $latestId = [string]$session.operation_ids[-1]
        $latest = $State.operation_events |
            Where-Object {
                $_.id -eq $latestId -and
                $_.status -eq "completed" -and
                $_.kind -eq "inquiry"
            } |
            Select-Object -First 1
        if ($latest -and $latest.result.action -in @("reframe", "close")) {
            $action = [string]$latest.result.action
            $inquiryId = if ($latest.inquiry_id) {
                [string]$latest.inquiry_id
            }
            else {
                "the inquiry"
            }
            return [pscustomobject]@{
                Objective = (
                    "Save the inquiry-session summary after the $action of " +
                    "$inquiryId."
                )
                Inquiry = if ($action -eq "close") {
                    (
                        "The close decision is complete. Preserve its outcome " +
                        "for goal review, which makes the next campaign-level decision."
                    )
                }
                else {
                    (
                        "The reframe decision is complete. Further scientific work " +
                        "belongs to the fresh inquiry session created after this summary."
                    )
                }
                CheckpointGuidance = if ($action -eq "close") {
                    (
                        "Use the checkpoint contract in research/instruments.md " +
                        "and preserve the evidence-supported inquiry outcome and " +
                        "observed remaining goal gap. Return the campaign to goal " +
                        "review rather than selecting another route here."
                    )
                }
                else {
                    (
                        "Use the checkpoint contract in research/instruments.md " +
                        "and preserve the reframe decision, its evidence basis, " +
                        "the observed remaining goal gap, and the transition to " +
                        "the fresh inquiry session."
                    )
                }
            }
        }
    }
    return $null
}

function New-ScientificSessionPrompt {
    param(
        [Parameter(Mandatory)]$State,
        [string]$ValidationError
    )

    $goal = Get-HumanGoalSummary -State $State
    $checkpoint = $State.pi_checkpoint
    $completedEvents = @(
        $State.operation_events | Where-Object { $_.status -eq "completed" }
    )
    $bestEvidence = if ($State.official_assessment) {
        [string]$State.official_assessment.summary
    }
    elseif ($checkpoint -and $checkpoint.evidence_references.Count -gt 0) {
        "The latest checkpoint cites: $($checkpoint.evidence_references -join ', ')."
    }
    elseif ($State.model_roles.best_known) {
        "The explicit best-known model is $($State.model_roles.best_known); inspect its referenced measurements in research/brief.md."
    }
    elseif ($completedEvents.Count -gt 0) {
        "Completed operation evidence exists in research/brief.md, but no best-known model has been assigned."
    }
    else {
        "No development operation has completed in this campaign."
    }
    $gap = if ($checkpoint -and $checkpoint.current_goal_gap) {
        [string]$checkpoint.current_goal_gap
    }
    else {
        "No PI-interpreted goal gap has been checkpointed yet."
    }
    $synthesis = if ($checkpoint -and $checkpoint.current_synthesis) {
        [string]$checkpoint.current_synthesis
    }
    else {
        "No durable PI synthesis has been recorded yet."
    }
    $frontier = if ($checkpoint -and $checkpoint.decision_frontier) {
        [string]$checkpoint.decision_frontier
    }
    else {
        "No durable decision frontier has been recorded yet."
    }
    $nextDirection = if ($checkpoint -and $checkpoint.next_direction_or_closure) {
        [string]$checkpoint.next_direction_or_closure
    }
    else {
        "No durable next-direction proposal has been recorded yet."
    }
    $transition = Get-RequiredSessionSummaryTransition -State $State
    $terminalGoalReview = (
        -not $transition -and
        $State.scientific_session.kind -eq "goal_review" -and
        -not $State.active_inquiry -and
        [int]$State.counters.inquiry -ge
            [int]$State.campaign.max_inquiries
    )
    $inquiry = if ($transition) {
        [string]$transition.Inquiry
    }
    elseif ($State.active_inquiry) {
        (
            "$($State.active_inquiry.id): $($State.active_inquiry.question) " +
            "Goal relevance: $($State.active_inquiry.goal_connection) " +
            "Closure condition: $($State.active_inquiry.closure_condition)"
        )
    }
    elseif ($State.scientific_session.kind -eq "startup") {
        "None. Establish and checkpoint the most credible initial scientific direction; inquiry selection follows in goal review."
    }
    elseif ($State.scientific_session.kind -eq "inquiry") {
        "The inquiry has closed. Preserve its outcome for goal review, which makes the next campaign-level decision."
    }
    elseif ($terminalGoalReview) {
        "None. Decide whether the evidence supports official assessment or a conclusion that no credible route remains."
    }
    else {
        "None. Decide whether the evidence supports official assessment, a bounded goal-linked inquiry, or a conclusion that no credible route remains."
    }
    $session = $State.scientific_session
    $correction = if ($ValidationError) {
        "The proposed action could not be accepted: $ValidationError Correct it without discarding valid scientific work."
    }
    else {
        ""
    }
    $objective = if ($transition) {
        [string]$transition.Objective
    }
    else {
        [string]$session.objective
    }
    $activeInquirySession = (
        -not $transition -and
        $session.kind -eq "inquiry" -and
        $State.active_inquiry
    )
    $goalReviewSession = (
        -not $transition -and
        $session.kind -eq "goal_review"
    )
    $actionGuidance = if ($transition) {
        @(
            "The sole legal next action is the checkpoint operation that saves the current session summary."
            "Do not request training, measurement, model-role changes, restoration, another inquiry change, or a campaign conclusion in this session."
            [string]$transition.CheckpointGuidance
        )
    }
    elseif ($terminalGoalReview) {
        @(
            "Make the terminal goal-level decision supported by the complete campaign evidence."
            "Use the campaign-conclusion contract in research/instruments.md to request official assessment or conclude that no credible route remains."
            "Do not request another inquiry."
        )
    }
    elseif ($activeInquirySession) {
        @(
            "Before choosing another action, determine whether the completed evidence now supplies the decision-relevant answer specified by the active inquiry's exact question and closure condition."
            "The inquiry is ready to close when the evidence is sufficient for the scientific decision it was opened to enable. Exhaustive certainty is not required; record remaining uncertainty when resolving it could no longer change that decision."
            "When the closure condition has been established, the question has been redirected or is no longer credible, or the actionable result has been produced, use the inquiry close contract now."
            "Closure records the evidence-supported outcome and remaining uncertainty before checkpointing. Preserve that result for goal review; do not select the next campaign route in the closing inquiry session."
            "Further inquiry work is justified by a named consequential uncertainty whose resolution could change the inquiry's answer. Reframe when that work belongs to a different question."
            "Select the next action according to the evidence needed to resolve the active inquiry's scientific decision in service of the human goal."
            "Existing PI-owned implementations have no privileged status; inspect, modify, or replace them when that is the most credible scientific action before submitting an operation."
            "When ready to act, use the matching contract in research/instruments.md to submit one scientific action."
        )
    }
    elseif ($goalReviewSession) {
        @(
            "Goal review makes the next campaign-level decision from the complete evidence and the human goal."
            "Use the previous checkpoint's decision frontier as context. Treat its next direction as a fallible proposal, not an instruction, and reconsider it independently rather than continuing it by default."
            "Describe the current goal gap as the observed shortfall across the official task and what remains unexplained, not as a proposed remedy."
            "Decide whether the evidence supports official assessment, one bounded goal-linked inquiry, or a conclusion that no credible route remains."
            "Existing PI-owned implementations have no privileged status; inspect, modify, or replace them when that is the most credible scientific action before submitting an operation."
            "When ready to act, use the matching contract in research/instruments.md to submit one scientific action."
        )
    }
    else {
        @(
            "Choose the operation whose result would most improve the next decision toward the human goal."
            "Existing PI-owned implementations have no privileged status; inspect, modify, or replace them when that is the most credible scientific action before submitting an operation."
            "When evidence resolves or redirects the active inquiry, record that decision explicitly rather than drifting to another question."
            "When the current line of work reaches a stable decision, preserve the synthesis, supporting evidence, remaining gap, and next direction in a checkpoint."
            "When ready to act, use the matching contract in research/instruments.md to submit one scientific action."
        )
    }

    $contextSections = if ($activeInquirySession) {
        @(
            "Human goal: $goal"
            "Active inquiry: $inquiry"
            "Decision frontier: $frontier"
            "Current scientific understanding: $synthesis"
            "Current evidence relative to the goal: $bestEvidence $(Get-LatestSessionResult -State $State)"
            "Current goal gap: $gap"
            "Current objective: $objective"
        )
    }
    elseif ($goalReviewSession) {
        @(
            "Human goal: $goal"
            "Current goal gap: $gap"
            "Current scientific understanding: $synthesis"
            "Current evidence relative to the goal: $bestEvidence $(Get-LatestSessionResult -State $State)"
            "Previous checkpoint context: Decision frontier: $frontier Proposed next direction or closure (non-binding): $nextDirection"
            "Active inquiry: $inquiry"
            "Current objective: $objective"
        )
    }
    else {
        @(
            "Human goal: $goal"
            "Current evidence relative to the goal: $bestEvidence $(Get-LatestSessionResult -State $State)"
            "Current scientific understanding: $synthesis"
            "Current goal gap: $gap"
            "Active inquiry: $inquiry"
            "Current objective: $objective"
        )
    }
    $sections = @(
        $contextSections
        $correction
        $piPersona
        $scientificModelUseGuidance
        "Direct every decision toward the human goal and distinguish evidence from conjecture."
        $actionGuidance
        "Begin with research/brief.md and the latest checkpoint. Consult research/scenario.md, research/scientific_model.md, and other evidence only as the scientific question requires."
    ) | Where-Object { $_ }
    return ($sections -join "`n`n")
}

function Test-OperationRequest {
    Enter-TrustedMutableInvocation
    $validationOutput = @(
        uv run python research/run_experiment.py --check-operation 2>&1
    )
    $exitCode = $LASTEXITCODE
    $script:OperationValidationFeedback = (
        $validationOutput | ForEach-Object { $_.ToString().Trim() }
    ) -join " "
    if ($exitCode -ne 0) {
        $validationReason = (
            $script:OperationValidationFeedback -replace '^OPERATION_INVALID:\s*', ''
        )
        Write-ConsoleCard -Title "OPERATION INVALID" `
            -Lines @($validationReason) -Color Red -BodyColor Red
        return $false
    }
    return $true
}

function Test-ScientificModelRegisters {
    param([Parameter(Mandatory)][string]$Content)

    $missing = @(
        "Established facts",
        "Physical consequences",
        "Unknowns"
    ) | Where-Object {
        $match = [regex]::Match(
            $Content,
            "(?ims)^#{1,6}\s+$([regex]::Escape($_))\s*`r?`n(?<body>.*?)(?=^#{1,6}\s+|\z)"
        )
        -not $match.Success -or -not $match.Groups["body"].Value.Trim()
    }
    if ($missing.Count -gt 0) {
        $script:ScientificModelValidationFeedback = (
            "research/scientific_model.md is missing required registers: " +
            ($missing -join ", ")
        )
        return $false
    }
    $script:ScientificModelValidationFeedback = ""
    return $true
}

function Test-ScientificModelDeliverable {
    Enter-TrustedMutableInvocation
    $validationOutput = @(
        uv run python research/run_experiment.py --check-scientific-model-deliverable 2>&1
    )
    if ($LASTEXITCODE -ne 0) {
        $script:ScientificModelValidationFeedback = (
            $validationOutput | ForEach-Object { $_.ToString().Trim() }
        ) -join " "
        return $false
    }
    $content = Get-Content "research\scientific_model.md" -Raw
    return Test-ScientificModelRegisters -Content $content
}

function Invoke-ScientificModelPhase {
    param([Parameter(Mandatory)]$State)

    $goal = Get-HumanGoalSummary -State $State
    $prompt = @(
        "Human goal: $goal"
        $piPersona
        "Current objective: $scientificModelPhaseObjective"
        "Base the model on research/scenario.md and the relevant human-authored implementation."
        "The document must contain substantive registers headed Established facts, Physical consequences, and Unknowns. Distinguish repository facts from reasoned implications and unresolved quantities."
        "Include only what is justified before campaign evidence exists. Write the result to research/scientific_model.md."
    ) -join "`n`n"

    $script:PISessionId = $null
    $script:PISessionInvocation = 0
    Invoke-PISession -Prompt $prompt -Phase "scientific model" -Preliminary
    if (Test-StopAfterOperation $script:PIExitCode "PI session") {
        return 130
    }
    if (-not (Test-ScientificModelDeliverable)) {
        $retry = @(
            "Human goal: $goal"
            "The scientific model could not be accepted: $script:ScientificModelValidationFeedback"
            "Correct research/scientific_model.md while preserving valid content and ensuring all three required registers are substantive."
        ) -join "`n`n"
        Invoke-PISession -Prompt $retry -Phase "scientific model" -Continue -Preliminary
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            return 130
        }
        if (-not (Test-ScientificModelDeliverable)) {
            throw "PI ended twice without a valid scientific model: $script:ScientificModelValidationFeedback"
        }
    }
    $exitCode = Invoke-Runner -Arguments @("--mark-scientific-model-ready")
    if (Test-StopAfterOperation $exitCode "research runner") {
        return 130
    }
    if ($exitCode -ne 0) {
        throw "The Runner could not publish the validated scientific model."
    }
    $script:PISessionId = $null
    $script:PISessionInvocation = 0
    return 0
}

function Invoke-PendingOperation {
    param([Parameter(Mandatory)]$State)

    $pending = $State.pending_operation
    if ($pending.failure) {
        Update-ResearchBrief
        if (
            -not $State.scientific_session -or
            $State.scientific_session.id -ne $pending.session_id
        ) {
            throw "The failed operation has no matching active scientific session."
        }
        if ($script:PISessionStateId -ne $State.scientific_session.id) {
            $script:PISessionStateId = $State.scientific_session.id
            $script:PISessionId = [string]$State.scientific_session.backend_session_id
            $script:PISessionInvocation = 0
        }
        $repairPrompt = @(
            (
                New-ScientificSessionPrompt -State $State
            )
            "The requested action $($pending.id) failed: $($pending.failure)"
            "Diagnose and correct the scientific implementation, or choose a different action if the failure changes the scientific decision."
        ) -join "`n`n"
        Invoke-PISession -Prompt $repairPrompt -Phase $State.scientific_session.kind `
            -Continue:$([bool]$script:PISessionId)
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            return 130
        }

        $request = Get-Content "research\operation_request.json" -Raw |
            ConvertFrom-Json
        $replacementRequested = -not $request._runner_accepted_operation
        if ($replacementRequested -and -not (Test-OperationRequest)) {
            $retryPrompt = @(
                (
                    New-ScientificSessionPrompt -State $State `
                        -ValidationError $script:OperationValidationFeedback
                )
                "Correct or replace the proposed action while preserving valid scientific work."
            ) -join "`n`n"
            Invoke-PISession -Prompt $retryPrompt -Phase $State.scientific_session.kind `
                -Continue
            if (Test-StopAfterOperation $script:PIExitCode "PI session") {
                return 130
            }
            $request = Get-Content "research\operation_request.json" -Raw |
                ConvertFrom-Json
            $replacementRequested = -not $request._runner_accepted_operation
            if ($replacementRequested -and -not (Test-OperationRequest)) {
                throw "PI ended twice without a valid replacement operation request: $script:OperationValidationFeedback"
            }
        }
        if ($replacementRequested) {
            $exitCode = Invoke-Runner
            if ($exitCode -ne 0) {
                return $exitCode
            }
            return 0
        }
        else {
            $exitCode = Invoke-Runner -Arguments @("--reaccept-pending")
            if ($exitCode -ne 0) {
                throw "The Runner could not reaccept the corrected operation."
            }
        }
    }
    $exitCode = Invoke-Runner -Arguments @("--execute-pending")
    if (Test-StopAfterOperation $exitCode "research runner") {
        return 130
    }
    if ($exitCode -ne 0) {
        $failed = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
        if ($failed.pending_operation.failure) {
            return 1
        }
        throw "The pending Runner operation failed without a recoverable transaction."
    }
    return 0
}

try {
    $backendExitCode = Invoke-Runner -Arguments @(
        "--validate-session-backend",
        "--backend-adapter", $PIBackend,
        "--backend-model", $Model,
        "--backend-reasoning", $Reasoning
    )
    if ($backendExitCode -ne 0) {
        throw (
            "Launcher backend descriptor must match the active bounded " +
            "scientific session until checkpoint."
        )
    }
    if ($script:MaxInquiriesExplicit) {
        $maxInquiryExitCode = Invoke-Runner -Arguments @(
            "--synchronize-max-inquiries", "$MaxInquiries"
        )
        if ($maxInquiryExitCode -ne 0) {
            throw (
                "Explicit launcher MaxInquiries must match the persisted campaign " +
                "setting after fresh/startup initialization."
            )
        }
    }

    $launchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
    $campaignAction = if (
        [int]$launchState.counters.session -eq 0 -and
        @($launchState.operation_events).Count -eq 0
    ) {
        "START"
    }
    else {
        "RESUME"
    }
    Write-Status (
        "$campaignAction | goal-centered research | " +
        (Get-CampaignResourceSummary -State $launchState)
    ) -Color White -Label campaign

    if ($PIBackend -eq "opencode") {
        $openCodeServer = Start-OpenCodeCampaignServer
        $script:OpenCodeServerProcess = $openCodeServer.Process
        $script:OpenCodeServerUrl = $openCodeServer.Url
    }

    :CampaignLoop while ($true) {
        if (Test-CampaignStopRequested) {
            $script:CampaignExitCode = 130
            break
        }

        $state = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json

        if ($state.scientific_model.status -eq "pending") {
            Write-Status "START | campaign preparation" -Color Magenta -Label session
            if ((Invoke-ScientificModelPhase -State $state) -eq 130) {
                break
            }
            Write-Status "END | campaign preparation" -Color Magenta -Label session
            Update-ResearchBrief
            continue
        }

        if ($state.pending_operation) {
            $pendingStatus = Invoke-PendingOperation -State $state
            if ($pendingStatus -eq 130) {
                break
            }
            if ($pendingStatus -eq 0) {
                Update-ResearchBrief
            }
            continue
        }

        if ($state.terminal_state) {
            if ($state.terminal_state.status -like "official_assessment_*") {
                $exitCode = Invoke-Runner -Arguments @("--run-official-assessment")
                if (Test-StopAfterOperation $exitCode "research runner") {
                    break
                }
                if ($exitCode -ne 0) {
                    throw "The official assessment failed; its request remains durable."
                }
                Update-ResearchBrief
                $state = Get-Content "research\research_state.json" -Raw |
                    ConvertFrom-Json
                break
            }
            break
        }

        if (-not $state.scientific_session) {
            $kind = if ($state.active_inquiry) {
                "inquiry"
            }
            elseif (
                [int]$state.counters.session -eq 0 -and
                $null -eq $state.pi_checkpoint
            ) {
                "startup"
            }
            else {
                "goal_review"
            }
            $objective = if ($kind -eq "startup") {
                "Establish and checkpoint the most credible first scientific direction toward the human goal from the scientific model and evidence produced in this session; inquiry selection follows in goal review."
            }
            elseif (
                $kind -eq "goal_review" -and
                [int]$state.counters.inquiry -ge
                    [int]$state.campaign.max_inquiries
            ) {
                "Decide whether to request official assessment or conclude that no credible route remains from the complete campaign evidence."
            }
            elseif ($kind -eq "goal_review") {
                "Decide whether to request official assessment, open one bounded goal-linked inquiry, or conclude that no credible route remains."
            }
            else {
                (
                    "Bring $($state.active_inquiry.id) to the decision required " +
                    "by its closure condition, and close it as soon as the " +
                    "evidence supplies that decision: " +
                    "$($state.active_inquiry.closure_condition)"
                )
            }
            $startArguments = @(
                "--start-session", $kind,
                "--session-objective", $objective,
                "--backend-session-id", ([guid]::NewGuid().ToString()),
                "--backend-adapter", $PIBackend,
                "--backend-model", $Model,
                "--backend-reasoning", $Reasoning
            )
            if ($script:MaxInquiriesExplicit) {
                $startArguments += @("--max-inquiries", "$MaxInquiries")
            }
            $exitCode = Invoke-Runner -Arguments $startArguments
            if (Test-StopAfterOperation $exitCode "research runner") {
                break
            }
            if ($exitCode -ne 0) {
                throw "The Runner could not start a bounded PI session."
            }
            $script:PISessionId = $null
            $script:PISessionStateId = $null
            $script:PISessionInvocation = 0
            Update-ResearchBrief
            continue
        }

        if (
            $script:PISessionStateId -ne $state.scientific_session.id -or
            $script:PISessionId -ne $state.scientific_session.backend_session_id
        ) {
            $script:PISessionStateId = $state.scientific_session.id
            $script:PISessionId = [string]$state.scientific_session.backend_session_id
            $script:PISessionInvocation = 0
        }
        Update-ResearchBrief

        $existingRequestProblem = ""
        if (Test-Path "research\operation_request.json" -PathType Leaf) {
            $exitCode = Invoke-Runner
            if (Test-StopAfterOperation $exitCode "research runner") {
                break
            }
            if ($exitCode -eq 0) {
                Update-ResearchBrief
                continue
            }
            $failed = Get-Content "research\research_state.json" -Raw |
                ConvertFrom-Json
            if ($failed.pending_operation.failure) {
                continue
            }
            [void](Test-OperationRequest)
            $existingRequestProblem = $script:OperationValidationFeedback
        }

        $prompt = New-ScientificSessionPrompt -State $state `
            -ValidationError $existingRequestProblem
        Invoke-PISession -Prompt $prompt -Phase $state.scientific_session.kind `
            -Continue:$([bool]$script:PISessionId)
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            break
        }

        if (-not (Test-OperationRequest)) {
            $retryPrompt = New-ScientificSessionPrompt -State $state `
                -ValidationError $script:OperationValidationFeedback
            Invoke-PISession -Prompt $retryPrompt -Phase $state.scientific_session.kind `
                -Continue
            if (Test-StopAfterOperation $script:PIExitCode "PI session") {
                break CampaignLoop
            }
            if (-not (Test-OperationRequest)) {
                throw "PI ended twice without a valid schema-6 operation request: $script:OperationValidationFeedback"
            }
        }

        $exitCode = Invoke-Runner
        if (Test-StopAfterOperation $exitCode "research runner") {
            break
        }
        if ($exitCode -eq 130) {
            break
        }
        if ($exitCode -ne 0) {
            $failed = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
            if (-not $failed.pending_operation.failure) {
                throw "The Runner operation failed without recoverable pending state."
            }
            continue
        }
        Update-ResearchBrief
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
