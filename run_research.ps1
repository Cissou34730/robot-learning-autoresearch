# Goal-centered robot-learning research launcher.

param(
    [string]$CampaignRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) "robot-learning-campaigns"),

    [ValidateNotNullOrEmpty()]
    [string]$Model,

    [ValidateSet("github-copilot", "opencode", "opencode-go")]
    [string]$Provider,

    [switch]$ListModels,

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

Push-Location -LiteralPath $PSScriptRoot
try {

if ($ListModels) {
    $listingArgs = @(
        "run", "--no-sync", "--group", "researcher", "python",
        "runner\copilot\copilot_adapter.py", "--list-models"
    )
    if ($Provider) {
        $listingArgs += @("--provider", $Provider)
    }
    & uv @listingArgs
    exit $LASTEXITCODE
}

$harnessChanges = @(git -C $PSScriptRoot status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0) {
    throw "Could not read the harness Git status. No campaign was started."
}
if ($harnessChanges.Count -gt 0) {
    throw (
        "The harness worktree has uncommitted changes. Commit or discard them before launching a campaign. No campaign was started.`n" +
        ($harnessChanges -join "`n")
    )
}

. "$PSScriptRoot\researcher_mutex.ps1"
Set-ResearchPaths -HarnessRoot $PSScriptRoot -CampaignRoot $CampaignRoot
$CampaignRoot = (Get-Location).Path

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

if (-not $Model) {
    $Model = if (-not $Provider -or $Provider -eq "github-copilot") {
        "gpt-6-luna"
    }
    else {
        # One OpenCode key covers Zen and Go; the free Zen model is the default for both.
        "opencode/deepseek-v4.1-flash-free"
    }
}
elseif ($Provider) {
    if ($Model.Contains("/")) {
        if ($Model.Split("/", 2)[0] -ne $Provider) {
            throw "The model prefix and selected provider do not match."
        }
    }
    elseif ($Provider -ne "github-copilot") {
        $Model = "$Provider/$Model"
    }
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

function Write-CooperativeProcessOutput {
    param([string]$Text, [bool]$ErrorStream)
    if ($ErrorStream) {
        [Console]::Error.Write($Text)
    }
    else {
        [Console]::Out.Write($Text)
    }
}

function Invoke-CooperativeProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$Operation,
        [string]$InputText,
        [switch]$CaptureOutput,
        [switch]$StreamOutput
    )

    if ($CaptureOutput -and $StreamOutput) {
        throw "Choose silent capture or live streaming, not both."
    }
    $redirectOutput = $CaptureOutput -or $StreamOutput
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.WorkingDirectory = $CampaignRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardInput = $PSBoundParameters.ContainsKey("InputText")
    $startInfo.RedirectStandardOutput = $redirectOutput
    $startInfo.RedirectStandardError = $redirectOutput
    if ($startInfo.RedirectStandardInput) {
        $startInfo.StandardInputEncoding = [System.Text.UTF8Encoding]::new($false)
    }
    if ($redirectOutput) {
        $startInfo.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false)
        $startInfo.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
        $startInfo.Environment["PYTHONIOENCODING"] = "utf-8"
        if ($StreamOutput) {
            $startInfo.Environment["PYTHONUNBUFFERED"] = "1"
        }
    }
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
        $pipes = @()
        if ($redirectOutput) {
            foreach ($reader in @($process.StandardOutput, $process.StandardError)) {
                $pipe = [pscustomobject]@{
                    Reader = $reader
                    Buffer = [char[]]::new(4096)
                    Read = $null
                    Closed = $false
                    ErrorStream = ($pipes.Count -eq 1)
                    Text = [System.Text.StringBuilder]::new()
                }
                $pipe.Read = $reader.ReadAsync($pipe.Buffer, 0, $pipe.Buffer.Length)
                $pipes += $pipe
            }
        }
        $inputWrite = $null
        if ($startInfo.RedirectStandardInput) {
            $process.StandardInput.AutoFlush = $true
            $inputWrite = $process.StandardInput.WriteAsync($InputText)
        }
        do {
            $progress = $false
            foreach ($pipe in $pipes) {
                # Drain both pipes concurrently, including unterminated progress lines.
                for ($batch = 0; $batch -lt 8 -and -not $pipe.Closed -and $pipe.Read.IsCompleted; $batch++) {
                    $count = $pipe.Read.GetAwaiter().GetResult()
                    if ($count -eq 0) {
                        $pipe.Closed = $true
                        break
                    }
                    $text = [string]::new($pipe.Buffer, 0, $count)
                    if ($StreamOutput) {
                        Write-CooperativeProcessOutput -Text $text -ErrorStream $pipe.ErrorStream
                    }
                    [void]$pipe.Text.Append($text)
                    if ($StreamOutput -and $pipe.Text.Length -gt 16384) {
                        [void]$pipe.Text.Remove(0, $pipe.Text.Length - 16384)
                    }
                    $pipe.Read = $pipe.Reader.ReadAsync($pipe.Buffer, 0, $pipe.Buffer.Length)
                    $progress = $true
                }
            }
            if ($inputWrite -and $inputWrite.IsCompleted) {
                [void]$inputWrite.GetAwaiter().GetResult()
                $process.StandardInput.Close()
                $inputWrite = $null
                $progress = $true
            }
            $exited = $process.WaitForExit($(if ($progress) { 0 } else { 100 }))
            if (
                (Test-CampaignStopRequested) -and
                [DateTime]::UtcNow -ge $script:StopDeadline
            ) {
                $script:StopDeadlineExceeded = $true
                if (-not $exited) {
                    $process.Kill($true)
                }
                $process.WaitForExit()
                throw (
                    "The cooperative stop deadline expired while waiting for " +
                    "$Operation (PID $($process.Id))."
                )
            }
        } while (
            -not $exited -or $inputWrite -or
            @($pipes | Where-Object { -not $_.Closed }).Count -gt 0
        )
        $process.WaitForExit()
        if ($redirectOutput) {
            $script:ProcessStdout = $pipes[0].Text.ToString()
            $script:ProcessStderr = $pipes[1].Text.ToString()
            $script:ProcessOutput = $script:ProcessStdout + $script:ProcessStderr
        }
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
    Assert-PITrustSnapshot -Snapshot $script:PITrustSnapshot -Root $CampaignRoot
}

function Invoke-Runner {
    param(
        [string[]]$Arguments = @(),
        [string]$InputText,
        [switch]$CaptureOutput,
        [switch]$StreamOutput
    )

    Enter-TrustedMutableInvocation
    $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $runnerArguments = @(
        "run", "--project", $PSScriptRoot, "python", "-m",
        "runner.run_experiment", "--timesteps", "$Timesteps"
    )
    $runnerArguments += $Arguments
    $processOptions = @{}
    if ($PSBoundParameters.ContainsKey("InputText")) {
        $processOptions.InputText = $InputText
    }
    $exitCode = Invoke-CooperativeProcess -FilePath $uv.Source `
        -ArgumentList $runnerArguments -Operation "research runner" `
        -CaptureOutput:$CaptureOutput -StreamOutput:$StreamOutput @processOptions
    $script:PITrustSnapshot = New-PITrustSnapshot `
        -Preliminary:$script:PITrustPreliminary -Root $CampaignRoot -HarnessRoot $PSScriptRoot
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

$createdNew = $false
$loopMutex = [System.Threading.Mutex]::new(
    $true,
    (Get-WorktreeMutexName -Worktree $CampaignRoot),
    [ref]$createdNew
)
if (-not $createdNew) {
    $loopMutex.Dispose()
    throw "Another robot autoresearch loop is already running in this worktree."
}

function Assert-ResearchRuntime {
    uv run --project $PSScriptRoot python -c "import runner.run_experiment"
    if ($LASTEXITCODE -ne 0) {
        throw "The research runtime is internally inconsistent. No PI session or Runner operation was started."
    }
}

Assert-ResearchRuntime
. "$PSScriptRoot\researcher_session.ps1"
. "$PSScriptRoot\runner\copilot\copilot_controller.ps1"

function Invoke-PISession {
    param(
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)][string]$Phase,
        [switch]$Continue,
        [switch]$Preliminary
    )

    Enter-TrustedMutableInvocation
    $script:PITrustPreliminary = [bool]$Preliminary
    $script:PITrustSnapshot = New-PITrustSnapshot -Preliminary:$Preliminary `
        -Root $CampaignRoot -HarnessRoot $PSScriptRoot

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

    $script:PIExitCode = Invoke-PersistentCopilotSession `
        -SessionArguments $sessionArgs -Prompt $Prompt -State $state `
        -Preliminary:$Preliminary
}

function Update-ResearchBrief {
    Enter-TrustedMutableInvocation
    uv run --project $PSScriptRoot python -m runner.build_brief
    if ($LASTEXITCODE -ne 0) {
        throw "Could not build the compact PI research brief."
    }
}

function Get-HumanGoalSummary {
    param([Parameter(Mandatory)]$State)

    if ($State.human_goal.summary) {
        return [string]$State.human_goal.summary
    }
    $scenario = Get-Content (Join-Path $PSScriptRoot "contracts\scenario.md") -Raw
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
            (
                "$($_.label): artifact=$artifact; " +
                "result summary (not the complete artifact)=$renderedFacts"
            )
        })
        $comparisons = @($result.paired_comparisons | ForEach-Object {
            $comparison = [ordered]@{}
            $_.PSObject.Properties |
                Where-Object { $_.Name -ne "shared_episode_seeds" } |
                ForEach-Object { $comparison[$_.Name] = $_.Value }
            $comparison
        })
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
        $savedFact = ""
        if ($result.saved_component_comparisons) {
            $exact = @(
                $result.saved_component_comparisons.comparisons |
                    Where-Object { @($_.exact_component_matches).Count -gt 0 } |
                    ForEach-Object {
                        (
                            "$($_.operation): " +
                            "$(@($_.exact_component_matches).Count)/" +
                            "$($_.corresponding_checkpoint_count) corresponding " +
                            "checkpoints; runtime files " +
                            "$($_.runtime.equal)/$($_.runtime.compared)"
                        )
                    }
            )
            $summary = if ($exact.Count -gt 0) {
                $exact -join " | "
            }
            else {
                "no exact checkpoint matches"
            }
            $savedFact = (
                " Exact saved-component comparison=$summary. " +
                "This reports serialized equality only; realization of an " +
                "intended intervention is not determined."
            )
        }
        return (
            "Operation $identifier (training): candidates=$($candidates -join ', '); " +
            "learning dynamics=$($dynamics -join ' | '); provenance parent=" +
            "$($result.mechanical_provenance.code_parent_commit), changed=" +
            "$($changed -join ', ').$savedFact"
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
        "inquiries $([int]$State.counters.inquiry) | " +
        "sessions $([int]$State.counters.session) | measurements $measurements | " +
        "training $training | candidates $(@($State.candidates.PSObject.Properties).Count)"
    )
}

function Get-RunnerOperationAvailability {
    param([Parameter(Mandatory)]$State)

    $exitCode = Invoke-Runner -Arguments @("--operation-state-input") `
        -InputText (ConvertTo-Json -InputObject $State -Depth 100 -Compress) `
        -CaptureOutput
    if ($exitCode -ne 0) {
        throw "Runner operation-state lookup failed: $($script:ProcessOutput)"
    }
    $availability = ConvertFrom-Json -InputObject $script:ProcessStdout -ErrorAction Stop
    if ($null -eq $availability -or
        $availability.PSObject.Properties.Name -notcontains "allowed_operations") {
        throw "Runner operation-state response is missing allowed_operations."
    }
    return $availability
}

function Get-RequiredSessionSummaryTransition {
    param([Parameter(Mandatory)]$State, $Availability)

    if (-not $Availability) {
        $Availability = Get-RunnerOperationAvailability -State $State
    }
    if (-not $Availability.checkpoint_required) {
        return $null
    }
    return [pscustomobject]@{
        Objective = "Save the scientific session record. $($Availability.checkpoint_reason)"
        Inquiry = [string]$Availability.checkpoint_reason
    }
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
    $availability = Get-RunnerOperationAvailability -State $State
    $transition = Get-RequiredSessionSummaryTransition -State $State -Availability $availability
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
            "Restored scientific handoff from the same PI's previous session. This is current scientific state, not another PI's opinion. The current scientific understanding below is that session's synthesis, verbatim."
            "Proposed question for this goal review, verbatim:`n$([string]$checkpoint.next_question)"
            "Continue from the completed evidence, but treat inherited interpretations, research constraints, priorities and proposed next actions as revisable scientific judgments. Correct an unsupported interpretation or a question already settled by available evidence, and record the correction and its basis."
        )
    }
    elseif ($session.kind -eq "inquiry" -and $State.active_inquiry) {
        @(
            if ([string]$State.active_inquiry.handoff_conclusion -ne $synthesis) {
                "Synthesis from the goal review that opened the active inquiry, verbatim:`n$([string]$State.active_inquiry.handoff_conclusion)"
            }
            "Continue the bounded work from completed evidence."
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
            if ($session.kind -eq "goal_review") {
                "Compare the strongest candidate's prospects on the official panel with the prospects of further bounded work. Use completed evidence and its limits for both choices. Explain why the chosen action is preferable now."
                "Neither an untested variant nor a candidate near the threshold justifies a choice by itself. Compare the evidence for each."
                "When judging a candidate's prospects on the official panel, consider whether the episodes behind its development result were also used to select it or design its changes; such a result tends to overstate its performance on new episodes."
            }
            else {
                "State the unresolved distinction or the development step the operation addresses, and how its outcome could produce or select a better candidate."
            }
            "Review completed evidence, the relevant learning trajectory, and unmeasured candidate artifacts. Training facts can nominate checkpoints for development measurement, but they do not establish development performance. The terminal checkpoint has no privileged status."
            "Interpret training proxies in the context of the exposure and runtime that produced them. Select checkpoints relevant to the decision when that context changes. Proxy rank alone does not determine which artifacts deserve measurement."
            "Choose the artifact and operation whose result would most improve the next decision toward the human goal."
            "Update the case for the research direction using results accumulated across inquiries. Limit method claims to what the tested implementation exercised. A negative result does not disprove the method. Compare a proposed method with the implementation already tested, using source changes, recorded runtime and saved-component comparisons when available; a new description does not establish a new method. Repeated work can be useful. State what additional evidence it supplies."
            "Candidate selection compares complete artifacts. A mechanism test distinguishes a causal explanation from consequential alternatives; choose it when that explanation would change the next direction. Keep an unexplained candidate difference at artifact level, and treat planned discriminating evidence that failed or remains unavailable as unresolved."
            if ($session.kind -ne "goal_review") {
                "Unresolved causes need not block inquiry closure. Preserve their consequences for the next decision. Closure itself justifies neither continuing the broader direction nor requesting assessment."
            }
            if ($session.kind -eq "goal_review") {
                "For a measurement, explain how its possible outcomes would affect the campaign-level choice."
                "Record the chosen assessment or inquiry and its evidence-based reason."
                "Preserve relevant residual failures, counterevidence and uncertainty in the chosen operation's reason."
            }
            else {
                "Explain how the decision-relevant possible outcomes of the selected operation would affect the direction."
                "Choose a diagnostic when its possible outcomes would lead to different next actions. When completed evidence already locates a defect, repairing it is a valid next action."
                "Checkpoint when the session's deliverable is complete or useful intermediate work is ready to preserve. Record supported findings, limitations and remaining work even if no research direction is settled."
                if ($session.kind -eq "inquiry") {
                    "The inquiry may remain active across sessions. Its closure condition and unresolved mechanisms do not require further work before checkpointing."
                }
            }
            "contracts/program.md defines what the scientific session record must preserve, including the meanings of current_synthesis and decision_frontier. contracts/instruments.md defines next_question for each session kind."
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
            "The current scientific session is $($session.id). It remains active until the Runner accepts this checkpoint."
            "Opening, reframing or closing an inquiry does not end this scientific session."
            "Set completed_operations exactly to: $(ConvertTo-Json -InputObject @($session.operation_ids) -Compress)"
            "Do not request training, measurement, model-role changes, restoration, another inquiry change, or a campaign conclusion in this session."
            if ($session.kind -eq "goal_review") {
                "Set next_question exactly to the question of the inquiry opened in this session."
            }
            elseif ($session.kind -eq "inquiry" -and $State.active_inquiry) {
                "Set next_question exactly to the current active inquiry question."
            }
            elseif ($session.kind -eq "inquiry") {
                "Set next_question to the proposed scientific question for the next goal review. Goal review may revise or decline it using completed evidence already available."
            }
        )
    }
    else {
        @(
            "Currently permitted operation kinds: $($availability.allowed_operations -join ', '). Request and evidence checks still apply."
        )
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
        "Training allocation: up to $Timesteps requested steps per run."
    }
    else {
        "Training allocation: $Timesteps steps per run."
    }
    $sourceGuidance = if ($session.kind -eq "startup") {
        "Begin with pi_workspace/scientific_model.md and campaigns/brief.md. Consult contracts/scenario.md and other evidence as needed."
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
    $submissionGuidance += " Call submit_operation with the request object. Results and changed state return directly to this conversation. Continue within this context until checkpoint or terminal commitment ends it."

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
        uv run --project $PSScriptRoot python -m runner.run_experiment --timesteps $Timesteps --check-operation 2>&1
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
        uv run --project $PSScriptRoot python -m runner.run_experiment --check-scientific-model-deliverable 2>&1
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
        "Code under robot_learning/ is the current recipe. Its rewards, training environments and observation construction are design choices, not properties of the robot; label any statement drawn from them as such."
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
    Stop-OnPublicationFailure -State $State
    if ($pending.failure) {
        Update-ResearchBrief
        if (
            -not $State.scientific_session -or
            $State.scientific_session.id -ne $pending.session_id
        ) {
            throw "The failed operation has no matching active scientific session."
        }
        $script:PISessionStateId = $State.scientific_session.id
        $script:PISessionId = [string]$State.scientific_session.backend_session_id
        $script:PISessionInvocation = 0
        $repairPrompt = @(
            (New-ScientificSessionPrompt -State $State)
            "The requested action $($pending.id) failed: $($pending.failure)"
            "This is execution history, not scientific evidence. Diagnose and correct the scientific implementation or choose another action. Call submit_operation with request=null to reaccept the corrected pending action, or supply a replacement request."
        ) -join "`n`n"
        Invoke-PISession -Prompt $repairPrompt -Phase $State.scientific_session.kind
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            return 130
        }
        Assert-CopilotSessionOutcome
        return 0
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
        "--backend-adapter", "copilot",
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
        (Get-CampaignResourceSummary -State $launchState) +
        " | inquiry cap $([int]$launchState.campaign.max_inquiries)"
    ) -Color White -Label campaign

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
                "Use the completed evidence to update the scientific direction toward the human goal. Correct inherited interpretations, constraints or proposed questions when existing evidence warrants it. Request measurements when they resolve an uncertainty or develop the method. Compare the two outcomes as contracts/program.md 'Goal review' defines and choose one: request the official assessment, whose pass or fail result ends this campaign, or open one bounded goal-linked inquiry."
            }
            else {
                (
                    "Advance $($state.active_inquiry.id) with a session-sized deliverable, " +
                    "not necessarily a complete answer to the inquiry. Choose the deliverable " +
                    "from completed evidence and the remaining scientific question. " +
                    "Checkpoint supported findings, limitations and remaining work when " +
                    "that deliverable is complete or useful intermediate work is ready to preserve. " +
                    "The inquiry may remain active across sessions. Close it when completed " +
                    "evidence warrants closure."
                )
            }
            $startArguments = @(
                "--start-session", $kind,
                "--session-objective", $objective,
                "--backend-session-id", ([guid]::NewGuid().ToString()),
                "--backend-adapter", "copilot",
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
        Assert-CopilotSessionOutcome
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
        Stop-PersistentCopilotRuntime
    }
    finally {
        $loopMutex.ReleaseMutex()
        $loopMutex.Dispose()
    }
}
if ($script:CampaignExitCode -ne 0) {
    exit $script:CampaignExitCode
}
}
finally {
    Pop-Location
}
