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

    [ValidateRange(1, [int]::MaxValue)]
    [int]$Timesteps = 120000,

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
    "You are the Principal Investigator responsible for scientific direction toward the human goal defined in contracts/scenario.md. Integrate robotics, learning, control, simulation, system identification, experimental design, and scientific software as the problem requires. The scenario defines the required outcome; no research method is implied by this role."
    "You set the scientific direction. Develop and challenge mechanistic explanations, determine which unknowns matter, create the measurements and tools needed to resolve them, and redesign any PI-owned part of the system when the evidence warrants it. Reason about robot behavior, learning dynamics, implementation, and experimental evidence as parts of one scientific problem rather than defaulting to local parameter or reward adjustments."
    "The human supplies the goal and protected boundary, not the research program. Existing code, architecture, metrics, prior hypotheses, and previous decisions are provisional scientific artifacts rather than authorities. Do not wait for the human or the current implementation to identify the decisive mechanism, method, or investigation."
) -join " "
$modelAnalystPersona = @(
    "You are a robotics and simulation analyst with deep expertise in rigid-body dynamics, kinematics, actuation, sensing, control theory, system identification, and MuJoCo modeling. You build rigorous physical models of embodied systems. You derive every claim from the definitions of the system. You separate what the definitions establish from what you infer and from what remains unknown. A principal investigator will use your model as the scientific foundation of a research campaign. The principal investigator chooses the research. You supply the physical understanding."
) -join " "
$scientificModelUseGuidance = @(
    "Use pi_workspace/scientific_model.md as the campaign's initial physical model. Test its interpretation against observed behavior and carry forward what the campaign learns; do not treat it as an intervention menu or a passive reference."
    "Use its physical consequences and unknowns to form competing mechanistic explanations. When an unresolved mechanism could change the scientific direction, seek evidence that discriminates between those explanations; when it cannot, state why it is not consequential."
    "For every physical consequence that could matter to the campaign, state which scientific decision it could change and what observation or evidence would revise it. Do not preserve a consequence as background description without connecting it to a decision."
) -join " "
$startupPhaseObjective = @'
Establish the most credible initial scientific direction toward the human goal from the scientific model and available evidence. Use scientific work in this session to establish or refine that direction, including building or adapting reusable scientific tools and PI-owned methods where needed. These capabilities can support subsequent inquiries. Choose the first useful scientific action and explain why it advances the direction. Preserve the work actually performed, resulting understanding, remaining uncertainties and chosen next action in the scientific session record.
'@
$scientificModelPhaseObjective = @'
Construct the physical and scientific model of the robot and the task. The model exists before any training or campaign evidence.

Work from first principles and from the human-owned definitions of the robot, the simulator, and the task. Explain the robot as an embodied dynamical system. Show how its morphology, actuation, sensing, control loop, simulator, and task geometry together determine the behaviors that are possible, constrained, or scientifically uncertain.

Build a scientific model of the system. The model explains mechanisms. It gives the reasons behind the behavior, and it goes beyond a list of components or a summary of the repository.

Analyze, from first principles and from the human-owned definitions:

* the robot morphology, degrees of freedom, geometry, reachable workspace, joint constraints, and relevant kinematic structure.
* the actuation model, and how commanded actions produce physical motion over time.
* the dynamic properties of the simulated robot that materially affect behavior, including timing, damping, inertia, and control authority.
* the initial physical state, and how it shapes the task that the controller must solve.
* the geometry and physical requirements of the task.
* the coupled physical capabilities that success requires, including reaching, trajectory control, convergence, and stabilization, together with the physically justified interactions between them.
* the sensing and observation model: which physical state is observable, which is derived, which is ambiguous, and which is unavailable.
* the relation between observation, control action, robot motion, and task outcome.
* alternative physical configurations or solutions available to the robot, such as multiple kinematic solutions.
* the physical, kinematic, dynamic, control, and observability constraints that create qualitatively different classes of behavior or failure.
* the physical quantities, across the complete behavior, that are scientifically meaningful for understanding the robot.

For each consequential physical implication and each unknown, state:

1. The research decisions that it could change.
2. The assumptions on which that relevance depends.
3. The source references in the implementation or the contracts.
4. The observation or evidence that would support, weaken, or revise it.

The model states physical consequences and the evidence that discriminates between them. The principal investigator selects the interventions.

Finish with a substantive section with the heading `## Decision-relevant synthesis`. Select only the physical consequences and unknowns that are most likely to change the first campaign decisions. For each selected item, keep these four points in compact form: its decision relevance, its assumptions, its source references, and its discriminating evidence. The principal investigator receives this section as the handoff into startup. The section states consequences and discriminating evidence. The principal investigator selects the interventions.

The final output is a compact and substantive scientific model. It explains how the complete coupled system works physically and scientifically.
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
    $runnerArguments = @(
        "run", "python", "runner/run_experiment.py", "--timesteps", "$Timesteps"
    )
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
    uv run python -c "import runner.run_experiment"
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
    $state = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
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
            "run", "--group", "researcher", "python", "runner/copilot_adapter.py"
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
    uv run python runner/build_brief.py
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build the compact PI research brief."
    }
}

function Get-HumanGoalSummary {
    param([Parameter(Mandatory)]$State)

    if ($State.human_goal.summary) {
        return [string]$State.human_goal.summary
    }
    $scenario = Get-Content "contracts\scenario.md" -Raw
    $match = [regex]::Match(
        $scenario,
        '(?ms)^## Success criterion\s+(?<body>.*?)(?=^## |\z)'
    )
    if ($match.Success) {
        return (($match.Groups["body"].Value -replace '\s+', ' ').Trim())
    }
    return "The protected human goal is defined in contracts/scenario.md."
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
                        "evaluation_artifact_contents",
                        "model_fingerprint"
                    )
                } |
                ForEach-Object { $facts[$_.Name] = $_.Value }
            $renderedFacts = $facts | ConvertTo-Json -Compress -Depth 100
            $contents = $metrics.evaluation_artifact_contents
            $inventory = if ($null -eq $contents) {
                "no inventory recorded; contents remain in the referenced artifact"
            }
            else {
                if (
                    $contents -isnot [pscustomobject] -and
                    $contents -isnot [System.Collections.IDictionary]
                ) {
                    throw "Measurement artifact contents must be an object."
                }
                $scope = if ($contents.truncated) {
                    "limited structure-only inventory"
                }
                else {
                    "structure-only inventory; no measurement values"
                }
                "$scope`: $($contents | ConvertTo-Json -Compress -Depth 100)"
            }
            (
                "$($_.label): artifact=$artifact; " +
                "result summary (not the complete artifact)=$renderedFacts; " +
                "artifact contents=$inventory"
            )
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
                Inquiry = (
                    "The $action decision is complete. Further scientific work " +
                    "belongs to the fresh session created after this summary."
                )
            }
        }
    }
    return $null
}

function Test-InquiryCapPause {
    param([Parameter(Mandatory)]$State)

    return (
        -not $State.scientific_session -and
        -not $State.active_inquiry -and
        -not $State.pending_operation -and
        -not $State.terminal_state -and
        [int]$State.counters.inquiry -ge [int]$State.campaign.max_inquiries
    )
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
        "The latest scientific session record cites: $($checkpoint.evidence_references -join ', ')."
    }
    elseif ($State.model_roles.best_known) {
        "The explicit best-known model is $($State.model_roles.best_known); inspect its referenced measurements in campaigns/brief.md."
    }
    elseif ($completedEvents.Count -gt 0) {
        "Completed operation evidence exists in campaigns/brief.md, but no best-known model has been assigned."
    }
    else {
        "No development operation has completed in this campaign."
    }
    $gap = if ($checkpoint -and $checkpoint.current_goal_gap) {
        [string]$checkpoint.current_goal_gap
    }
    else {
        "No PI-interpreted goal gap has been recorded yet."
    }
    $synthesis = if ($checkpoint -and $checkpoint.current_synthesis) {
        [string]$checkpoint.current_synthesis
    }
    else {
        "No durable PI synthesis has been recorded yet."
    }
    $frontier = if ($checkpoint) {
        [string]$checkpoint.decision_frontier
    }
    else {
        "No scientific decision frontier has been recorded yet."
    }
    $transition = Get-RequiredSessionSummaryTransition -State $State
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
    elseif ($State.scientific_session.kind -eq "inquiry") {
        "The inquiry has closed. Preserve its outcome and the resulting campaign decision."
    }
    else {
        "None. Measurements and evidence-backed model-role assignments are available before choosing official assessment or one bounded goal-linked inquiry."
    }
    $session = $State.scientific_session
    $handoffContext = if ($session.kind -eq "goal_review" -and $checkpoint) {
        @(
            "Restored scientific handoff from the same PI's previous session. This is current scientific state, not another PI's opinion."
            "Previous session conclusion, verbatim:`n$([string]$checkpoint.current_synthesis)"
            "Question selected for the next inquiry, verbatim:`n$([string]$checkpoint.next_question)"
            "Continue from this state. Change it when new evidence, an implementation finding, or a concrete dead end changes the scientific situation. Record what changed and why."
            "A useful policy does not establish its proposed cause. A negative recipe result does not by itself invalidate the broader method. Distinguish the tested recipe's outcome from what it establishes about the explanation or method it was intended to investigate."
        )
    }
    elseif ($session.kind -eq "inquiry" -and $State.active_inquiry) {
        @(
            "Restored scientific handoff from the same PI's source session. This is current scientific state, not another PI's opinion."
            "Source session conclusion, verbatim:`n$([string]$State.active_inquiry.handoff_conclusion)"
            "Question selected by that session, verbatim:`n$([string]$State.active_inquiry.handoff_question)"
            "Continue from this state while you solve the active inquiry. Change it when new evidence, an implementation finding, or a concrete dead end changes the scientific situation. Record what changed and why."
            "A useful policy does not establish its proposed cause. A negative recipe result does not by itself invalidate the broader method. Distinguish the tested recipe's outcome from what it establishes about the explanation or method it was intended to investigate."
        )
    }
    else {
        @()
    }
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
    $decisionGuidance = if ($transition) {
        @()
    }
    else {
        @(
            "Decide in this order. State the unresolved scientific distinction. Choose the operation whose result would most improve the next decision toward the human goal. Explain how that result would change the direction. Checkpoint when the line of work reaches a stable decision."
            "contracts/program.md defines what the scientific session record must preserve, including the meanings of current_synthesis, decision_frontier and next_question. Apply those meanings to the current state shown above."
            if ($session.kind -eq "goal_review") {
                "In goal review, next_question must exactly match the question of the inquiry opened in this session."
            }
            elseif ($session.kind -eq "inquiry" -and $State.active_inquiry) {
                "While the inquiry remains active, next_question must exactly match its current question."
            }
            "Existing PI-owned implementations have no privileged status; inspect, modify, or replace them when that is the most credible scientific action before submitting an operation."
            if ($session.kind -ne "startup") {
                "When evidence resolves or redirects the active inquiry, record that decision explicitly rather than drifting to another question."
            }
        )
    }
    $legalOperations = if ($transition) {
        @(
            "The sole legal next action is the checkpoint operation that saves the scientific session record."
            "Do not request training, measurement, model-role changes, restoration, another inquiry change, or a campaign conclusion in this session."
            if ($session.kind -eq "goal_review") {
                "Set next_question exactly to the question of the inquiry opened in this session."
            }
            elseif ($session.kind -eq "inquiry" -and $State.active_inquiry) {
                "Set next_question exactly to the current active inquiry question."
            }
            elseif ($session.kind -eq "inquiry") {
                "Set next_question to the exact scientific question that the same PI must carry into the next inquiry. Preserve the leading mechanism, its priority, and the evidence that can discriminate it."
            }
        )
    }
    else {
        @("Use only the operation kinds listed as available in campaigns/brief.md.")
    }
    $startupHandoffGuidance = if ($session.kind -eq "startup") {
        $modelHandoff = "The decision-relevant synthesis is in campaigns/brief.md under 'Initial scientific model'."
        $modelPath = Join-Path (Get-Location) "pi_workspace\scientific_model.md"
        if (Test-Path -LiteralPath $modelPath -PathType Leaf) {
            $modelText = Get-Content -LiteralPath $modelPath -Raw
            $selectedSynthesis = [regex]::Match(
                $modelText,
                "(?ms)^## Decision-relevant synthesis\s+(.*?)(?=^## |\z)"
            ).Groups[1].Value.Trim()
            if ($selectedSynthesis) {
                $modelHandoff = "Decision-relevant synthesis from the initial scientific model:`n$selectedSynthesis"
            }
        }
        @(
            "Before selecting the first action, read pi_workspace/scientific_model.md as the initial physical model and contracts/program.md as the lifecycle contract."
            $modelHandoff
            "From this synthesis, select the scientific distinction or capability question that should determine the initial direction. State which findings would change that decision, and how the first action follows. Treat the model as revisable in light of evidence. Do not require a measurement only to restate the model."
        )
    }
    else {
        @()
    }

    $trainingAllocation = if ($transition -or $session.kind -eq "goal_review") {
        ""
    }
    elseif ($session.kind -eq "startup") {
        "Training ceiling: $Timesteps requested steps per run."
    }
    else {
        "Maintainer training allocation: $Timesteps steps per run."
    }
    $sourceGuidance = if ($session.kind -eq "startup") {
        "Begin with pi_workspace/scientific_model.md, campaigns/brief.md and the latest scientific session record. Consult contracts/scenario.md and other evidence as needed."
    }
    else {
        "Begin with campaigns/brief.md and the latest scientific session record. Consult contracts/scenario.md, pi_workspace/scientific_model.md, and other evidence only as the scientific question requires."
    }
    $submissionGuidance = if ($transition) {
        "Use the scientific session record contract in contracts/instruments.md and preserve the transition decision, evidence, remaining goal gap, and next direction."
    }
    else {
        "When ready to act, use the matching contract in contracts/instruments.md to submit one scientific action."
    }

    $sections = @(
        $piPersona
        "Human goal: $goal"
        "The essential task conditions and protected boundaries are defined in contracts/scenario.md."
        $handoffContext
        $startupHandoffGuidance
        $scientificModelUseGuidance
        "Current scientific understanding: $synthesis"
        "Completed evidence relative to the goal and its recorded interpretive limits: $bestEvidence $(Get-LatestSessionResult -State $State)"
        "Current goal gap: $gap"
        "Scientific decision frontier: $frontier"
        if ($session.kind -ne "startup") {
            "Active inquiry: $inquiry"
        }
        "Current objective: $objective"
        "Direct every decision toward the human goal and distinguish evidence from conjecture."
        $decisionGuidance
        $legalOperations
        $trainingAllocation
        $correction
        $sourceGuidance
        $submissionGuidance
    ) | Where-Object { $_ }
    return ($sections -join "`n`n")
}

function Test-OperationRequest {
    Enter-TrustedMutableInvocation
    $validationOutput = @(
        uv run python runner/run_experiment.py --timesteps $Timesteps --check-operation 2>&1
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

function Test-ScientificModelDeliverable {
    Enter-TrustedMutableInvocation
    $validationOutput = @(
        uv run python runner/run_experiment.py --check-scientific-model-deliverable 2>&1
    )
    if ($LASTEXITCODE -ne 0) {
        $script:ScientificModelValidationFeedback = (
            $validationOutput | ForEach-Object { $_.ToString().Trim() }
        ) -join " "
        return $false
    }
    $script:ScientificModelValidationFeedback = ""
    return $true
}

function Invoke-ScientificModelPhase {
    param([Parameter(Mandatory)]$State)

    $goal = Get-HumanGoalSummary -State $State
    $prompt = @(
        $modelAnalystPersona
        "Human goal: $goal"
        "Current objective: $scientificModelPhaseObjective"
        "Base the model on contracts/scenario.md and on the human-owned definitions of the robot, the simulator, and the task."
        "The document has four registers, with these headings: Established facts, Physical consequences, Unknowns, and Decision-relevant synthesis. Write each register as a level-two heading (##). Put all its content under that heading. Use level-three headings (###) for topics inside a register. Mark each statement as a repository fact, a reasoned implication, or an unresolved quantity. Keep source references for later verification."
        "Include only what is justified before campaign evidence exists. Write the result to pi_workspace/scientific_model.md."
    ) -join "`n`n"

    $script:PISessionId = $null
    $script:PISessionInvocation = 0
    Invoke-PISession -Prompt $prompt -Phase "scientific model" -Preliminary
    if (Test-StopAfterOperation $script:PIExitCode "PI session") {
        return 130
    }
    if (-not (Test-ScientificModelDeliverable)) {
        $retry = @(
            $modelAnalystPersona
            "Human goal: $goal"
            "The scientific model could not be accepted: $script:ScientificModelValidationFeedback"
            "Correct pi_workspace/scientific_model.md. Keep the valid content. Make all four required registers substantive and source-recoverable. Make the synthesis decision-relevant. Each register is a level-two heading (##) with its content directly under it. Move topic sections inside a register and change their headings to level three (###)."
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

function Stop-OnPublicationFailure {
    param([Parameter(Mandatory)]$State)

    $pending = $State.pending_operation
    if ($pending -and $pending.progress -in @("result_ready", "completed")) {
        throw (
            "Execution completed for $($pending.id), but publication failed. " +
            "Its artifacts and pending transaction are preserved. Correct the " +
            "publication error, then resume this campaign; do not reaccept " +
            "the operation or retrain."
        )
    }
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
            "An execution failure or a training collapse is not a scientific result about the method under investigation. Distinguish the failed run's outcome from what it establishes about the explanation or method it was intended to investigate."
            "Diagnose and correct the scientific implementation, or choose a different action if the failure changes the scientific decision."
        ) -join "`n`n"
        Invoke-PISession -Prompt $repairPrompt -Phase $State.scientific_session.kind `
            -Continue:$([bool]$script:PISessionId)
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            return 130
        }

        $request = Get-Content "pi_workspace\operation_request.json" -Raw |
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
            $request = Get-Content "pi_workspace\operation_request.json" -Raw |
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
        $failed = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
        Stop-OnPublicationFailure -State $failed
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
                "Explicit launcher MaxInquiries may change only during fresh " +
                "initialization or as an increase at an inquiry-cap pause."
            )
        }
    }

    $launchState = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
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

        $state = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json

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
                $state = Get-Content "runner\state\research_state.json" -Raw |
                    ConvertFrom-Json
                break
            }
            break
        }

        if (Test-InquiryCapPause -State $state) {
            Write-Status (
                "PAUSE | inquiry creation cap reached | " +
                "scientific state preserved; no campaign conclusion | " +
                "resume with an explicit higher -MaxInquiries"
            ) -Color Yellow -Label campaign
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
                $startupPhaseObjective
            }
            elseif ($kind -eq "goal_review") {
                "Use the completed evidence to update the scientific direction toward the human goal. Request measurements when they resolve an uncertainty or develop the method. Then choose one outcome: request the official assessment, or open one bounded goal-linked inquiry."
            }
            else {
                (
                    "Advance $($state.active_inquiry.id) toward an evidence-supported " +
                    "answer to its scientific question: $($state.active_inquiry.question)"
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
        if (Test-Path "pi_workspace\operation_request.json" -PathType Leaf) {
            $exitCode = Invoke-Runner
            if (Test-StopAfterOperation $exitCode "research runner") {
                break
            }
            if ($exitCode -eq 0) {
                Update-ResearchBrief
                continue
            }
            $failed = Get-Content "runner\state\research_state.json" -Raw |
                ConvertFrom-Json
            Stop-OnPublicationFailure -State $failed
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
            $failed = Get-Content "runner\state\research_state.json" -Raw | ConvertFrom-Json
            Stop-OnPublicationFailure -State $failed
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
