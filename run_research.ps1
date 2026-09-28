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
    "Act as the Principal Investigator (PI) accountable for evidence-based progress toward the human goal."
    "Integrate robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software into one causal view of the embodied learning system."
    "Set the scientific direction: form and challenge explanations, identify consequential unknowns, design discriminating evidence, and interpret results in relation to the human goal."
) -join " "

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
    Write-Status "MESSAGE | $displaySession" -Color Magenta -Label pi
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

    if ($State.human_goal.summary) {
        return [string]$State.human_goal.summary
    }
    $scenario = Get-Content "research\scenario.md" -Raw
    $match = [regex]::Match(
        $scenario,
        '(?ms)^## Success criterion\s+(?<body>.*?)(?=^## |\z)'
    )
    if ($match.Success) {
        return (($match.Groups["body"].Value -replace '\s+', ' ').Trim())
    }
    return "The protected human goal is defined in research/scenario.md."
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
        $measurements = @($result.measurements | Select-Object -First 6 | ForEach-Object {
            $metrics = $_.metrics
            $artifact = if ($metrics.evaluation_artifact) {
                [string]$metrics.evaluation_artifact
            }
            else {
                "none"
            }
            $facts = @(
                $metrics.PSObject.Properties |
                    Where-Object {
                        $_.Name -notin @(
                            "episode_results",
                            "evaluation_artifact",
                            "evaluation_artifact_fingerprint",
                            "model_fingerprint"
                        ) -and
                        ($null -eq $_.Value -or $_.Value -is [ValueType] -or $_.Value -is [string])
                    } |
                    Select-Object -First 8 |
                    ForEach-Object { "$($_.Name)=$($_.Value)" }
            )
            "$($_.label): artifact=$artifact; metrics=$($facts -join ', ')"
        })
        $comparisons = @($result.paired_comparisons)
        $comparisonFact = if ($comparisons.Count -gt 0) {
            ($comparisons | ConvertTo-Json -Compress -Depth 5)
        }
        else {
            "none"
        }
        if ($comparisonFact.Length -gt 600) {
            $comparisonFact = $comparisonFact.Substring(0, 599) + "…"
        }
        return (
            "Operation $identifier (measurement): $($measurements -join ' | '); " +
            "comparisons=$comparisonFact."
        )
    }
    if ($event.kind -eq "training") {
        $dynamics = @($result.learning_dynamics | Select-Object -First 8 | ForEach-Object {
            (
                "$($_.candidate): steps=$($_.training_steps), " +
                "success=$($_.training_success), reward=$($_.ep_rew_mean)"
            )
        })
        $changed = @($result.mechanical_provenance.changed_files | Select-Object -First 12 | ForEach-Object {
            [string]$_.path
        })
        $candidates = @($result.candidates | Select-Object -First 12)
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
    $inquiry = if ($State.active_inquiry) {
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
        "The inquiry has closed. Preserve its outcome and the resulting campaign decision."
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

    $sections = @(
        "Human goal: $goal"
        "Current evidence relative to the goal: $bestEvidence $(Get-LatestSessionResult -State $State)"
        "Current scientific understanding: $synthesis"
        "Current goal gap: $gap"
        "Active inquiry: $inquiry"
        "Current objective: $($session.objective)"
        $correction
        $piPersona
        "Direct every decision toward the human goal and distinguish evidence from conjecture."
        "Choose the operation whose result would most improve the next decision toward the human goal."
        "When evidence resolves or redirects the active inquiry, record that decision explicitly rather than drifting to another question."
        "When the current line of work reaches a stable decision, preserve the synthesis, supporting evidence, remaining gap, and next direction in a checkpoint."
        "Begin with research/brief.md and the latest checkpoint. Consult research/scenario.md, research/scientific_model.md, and other evidence only as the scientific question requires."
        "When ready to act, use the matching contract in research/instruments.md to submit one scientific action."
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
        Write-Host $script:OperationValidationFeedback
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
        "Objective: establish a scientific model of the robot and task that can ground later decisions toward the human goal."
        $piPersona
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
            elseif ($kind -eq "goal_review") {
                "Decide whether to request official assessment, open one bounded goal-linked inquiry, or conclude that no credible route remains."
            }
            else {
                (
                    "Advance $($state.active_inquiry.id) toward its closure condition: " +
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
