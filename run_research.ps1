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
$script:PITrustBaseline = $null
$script:PITrustPreliminary = $false
$script:PIWorkPendingTrust = $false

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
    "Act as the Principal Investigator (PI) responsible for reaching the human goal without lowering scientific standards or inventing certainty."
    "Integrate robotics, reinforcement learning, control, simulation, system identification, experimental design, and scientific software into one causal view of the embodied learning system."
    "Set the scientific direction: challenge explanations, identify consequential unknowns, build or revise PI-owned tools and code, and interpret evidence in relation to the human goal."
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

function Test-PIWritablePath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [switch]$Preliminary
    )

    $relative = ($Path -replace '\\', '/').TrimStart([char[]]"./").ToLowerInvariant()
    if ($relative -in @(
        "robot_learning/scenario/__init__.py",
        "robot_learning/scenario/final_benchmark.py",
        "robot_learning/scenario/task_reference.py"
    )) {
        return $false
    }
    if ($Preliminary) {
        return $relative -eq "research/scientific_model.md"
    }
    return (
        $relative -in @(
            "robot_learning/train.py",
            "robot_learning/evaluate.py",
            "robot_learning/play.py",
            "research/current_params.json",
            "research/operation_request.json"
        ) -or
        $relative.StartsWith("robot_learning/scenario/") -or
        $relative.StartsWith("robot_learning/training/") -or
        $relative.StartsWith("research/lab/")
    )
}

function Get-WorktreeDeltaPaths {
    param([string]$Root = $PSScriptRoot)

    $tracked = @(& git -C $Root diff --name-only --no-renames HEAD --)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect tracked worktree changes before trusted execution."
    }
    $untracked = @(& git -C $Root ls-files --others --exclude-standard --)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect untracked worktree changes before trusted execution."
    }
    return @(
        $tracked + $untracked |
            ForEach-Object { ($_ -replace '\\', '/').Trim() } |
            Where-Object { $_ } |
            Sort-Object -Unique
    )
}

function Get-WorktreePathFingerprint {
    param(
        [Parameter(Mandatory)][string]$Path,
        [string]$Root = $PSScriptRoot
    )

    $fullPath = Join-Path $Root ($Path -replace '/', '\')
    $status = @(
        & git -C $Root status --porcelain=v1 --untracked-files=all -- $Path
    ) -join "`n"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not inspect worktree state for $Path."
    }
    if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
        $content = (Get-FileHash -LiteralPath $fullPath -Algorithm SHA256).Hash
        return "file|$status|$content"
    }
    if (Test-Path -LiteralPath $fullPath -PathType Container) {
        return "directory|$status"
    }
    return "missing|$status"
}

function New-PITrustBaseline {
    param(
        [switch]$Preliminary,
        [string]$Root = $PSScriptRoot
    )

    $baseline = @{}
    foreach ($relative in Get-WorktreeDeltaPaths -Root $Root) {
        if (-not (Test-PIWritablePath -Path $relative -Preliminary:$Preliminary)) {
            $baseline[$relative] = Get-WorktreePathFingerprint `
                -Path $relative -Root $Root
        }
    }
    return $baseline
}

function Assert-PIWorktreeTrust {
    param(
        [Parameter(Mandatory)][hashtable]$Baseline,
        [switch]$Preliminary,
        [string]$Root = $PSScriptRoot
    )

    $violations = [System.Collections.Generic.List[string]]::new()
    $current = @(
        Get-WorktreeDeltaPaths -Root $Root |
            Where-Object {
                -not (Test-PIWritablePath -Path $_ -Preliminary:$Preliminary)
            }
    )
    foreach ($relative in $current) {
        if (-not $Baseline.ContainsKey($relative)) {
            $violations.Add($relative)
            continue
        }
        $fingerprint = Get-WorktreePathFingerprint -Path $relative -Root $Root
        if ($fingerprint -ne $Baseline[$relative]) {
            $violations.Add($relative)
        }
    }
    foreach ($relative in $Baseline.Keys) {
        if ($relative -notin $current) {
            $violations.Add([string]$relative)
        }
    }
    if ($violations.Count -gt 0) {
        $paths = @($violations | Sort-Object -Unique)
        throw (
            "PI work changed paths outside the AGENTS.md scientific surface: " +
            "$($paths -join ', '). Refusing to load mutable Runner or adapter code."
        )
    }
}

function Enter-TrustedMutableInvocation {
    if (-not $script:PIWorkPendingTrust) {
        return
    }
    Assert-PIWorktreeTrust -Baseline $script:PITrustBaseline `
        -Preliminary:$script:PITrustPreliminary
    $script:PIWorkPendingTrust = $false
    $script:PITrustBaseline = $null
}

function Invoke-Runner {
    param([string[]]$Arguments = @())

    Enter-TrustedMutableInvocation
    $uv = Get-Command uv -CommandType Application -ErrorAction Stop |
        Select-Object -First 1
    $runnerArguments = @("run", "python", "research/run_experiment.py")
    $runnerArguments += $Arguments
    return Invoke-CooperativeProcess -FilePath $uv.Source `
        -ArgumentList $runnerArguments -Operation "research runner"
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
        Write-Status "OpenCode campaign server ready at $url" -Color DarkGray -Label pi
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
    $script:PITrustBaseline = New-PITrustBaseline -Preliminary:$Preliminary

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
    Write-Status "=== PI session: $Phase ===" -Color Magenta -Label pi
    Write-Status "Model: $Model, reasoning: $Reasoning" -Color Magenta -Label pi
    $sessionArgs = @(
        "--session-id", $script:PISessionId
        "--model", $Model
        "--reasoning", $Reasoning
        "--phase", $Phase
        "--attempt", "$script:PISessionInvocation"
    )
    $state = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
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

    try {
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
    finally {
        $script:PIWorkPendingTrust = $true
    }
}

function Update-ResearchBrief {
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
        return "No Runner operation has completed in this bounded session."
    }
    $identifier = [string]$session.operation_ids[-1]
    $event = $State.operation_events |
        Where-Object { $_.id -eq $identifier -and $_.status -eq "completed" } |
        Select-Object -First 1
    if (-not $event) {
        return "The session has no completed result for $identifier; failed attempts are execution history, not evidence."
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

function Get-AvailableOperations {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][int]$InquiryLimit
    )

    $session = $State.scientific_session
    if (-not $session) {
        return @()
    }
    if (
        ($session.kind -eq "goal_review" -and $null -ne $State.active_inquiry) -or
        ($session.kind -eq "inquiry" -and $null -eq $State.active_inquiry) -or
        (
            $session.kind -eq "inquiry" -and
            $session.operation_ids.Count -gt 0 -and
            (
                $State.operation_events |
                    Where-Object { $_.id -eq $session.operation_ids[-1] } |
                    Select-Object -First 1
            ).result.action -eq "reframe"
        )
    ) {
        return @(
            "checkpoint: preserve the goal-level or inquiry decision and end this bounded session"
        )
    }
    if ($session.kind -eq "startup") {
        return @(
            "measurement: execute a configured development evaluator or PI-owned Python diagnostic"
            "training: train from fresh initialization or an explicit saved parent"
            "model_role: explicitly set working, set best_known, or retain a candidate using completed-operation evidence"
            "restore_recipe: restore the PI-owned scientific surface from a named candidate"
            "checkpoint: preserve startup design and evidence, then enter campaign-level goal review"
        )
    }
    if ($session.kind -eq "goal_review") {
        $operations = @()
        if ([int]$State.counters.inquiry -lt $InquiryLimit) {
            $operations += "inquiry open: open one bounded, goal-linked inquiry"
        }
        $operations += @(
            "campaign_conclusion request_official_assessment: submit the explicit best-known model to the official assessment"
            "campaign_conclusion no_credible_route: conclude that no credible route remains"
            "checkpoint: preserve the goal review without making a terminal decision"
        )
        return $operations
    }
    return @(
        "measurement: execute a configured development evaluator or PI-owned Python diagnostic"
        "training: train from fresh initialization or an explicit saved parent"
        "inquiry reframe: materially revise the bounded question and closure condition"
        "inquiry close: record the durable outcome and return the campaign to goal review"
        "model_role: explicitly set working, set best_known, or retain a candidate using completed-operation evidence"
        "restore_recipe: restore the PI-owned scientific surface from a named candidate"
        "checkpoint: preserve the current synthesis and end this bounded session"
    )
}

function Get-ScientificSessionPhase {
    param([Parameter(Mandatory)]$State)

    $session = $State.scientific_session
    if ($session.kind -eq "inquiry" -and $null -eq $State.active_inquiry) {
        return "closed inquiry awaiting checkpoint"
    }
    return [string]$session.kind
}

function New-ScientificSessionPrompt {
    param(
        [Parameter(Mandatory)]$State,
        [Parameter(Mandatory)][int]$InquiryLimit,
        [string]$ValidationError
    )

    $goal = Get-HumanGoalSummary -State $State
    $checkpoint = $State.pi_checkpoint
    $completedEvents = @(
        $State.operation_events | Where-Object { $_.status -eq "completed" }
    )
    $failedEvents = @(
        $State.operation_events | Where-Object { $_.status -eq "failed" }
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
    $phase = Get-ScientificSessionPhase -State $State
    $inquiry = if ($State.active_inquiry) {
        (
            "$($State.active_inquiry.id): $($State.active_inquiry.question) " +
            "Goal relevance: $($State.active_inquiry.goal_connection) " +
            "Closure condition: $($State.active_inquiry.closure_condition)"
        )
    }
    elseif ($phase -eq "startup") {
        "None; this is the startup scientific-design session."
    }
    elseif ($phase -eq "closed inquiry awaiting checkpoint") {
        "The inquiry is closed; preserve its outcome in the required checkpoint."
    }
    else {
        "None; this is campaign-level goal review."
    }
    $session = $State.scientific_session
    $completedTraining = @(
        $completedEvents | Where-Object { $_.kind -eq "training" }
    ).Count
    $completedMeasurement = @(
        $completedEvents | Where-Object { $_.kind -eq "measurement" }
    ).Count
    $resourceSummary = (
        "$($State.counters.inquiry) of $InquiryLimit inquiry identities created; " +
        "$completedTraining completed training operations; " +
        "$completedMeasurement completed measurement operations; " +
        "$($completedEvents.Count) completed operations; " +
        "$($State.candidates.PSObject.Properties.Count) candidates."
    )
    $executionHistoryParts = @()
    if ($failedEvents.Count -gt 0) {
        $superseded = @(
            $failedEvents | Where-Object { $null -ne $_.superseded_by }
        ).Count
        $executionHistoryParts += (
            "Execution history (not evidence): $($failedEvents.Count) failed " +
            "attempts, including $superseded superseded attempts."
        )
    }
    if ($State.pending_operation -and $State.pending_operation.failure) {
        $executionHistoryParts += (
            "Pending operation " +
            "$($State.pending_operation.id) failed and awaits repair."
        )
    }
    $executionHistory = if ($executionHistoryParts.Count -gt 0) {
        ($executionHistoryParts -join " ") + " Inspect research/brief.md for factual errors."
    }
    else {
        "Execution history (not evidence): no failed attempts."
    }
    $operations = (Get-AvailableOperations -State $State -InquiryLimit $InquiryLimit) |
        ForEach-Object { "- $_" }
    $limitNote = if (
        $session.kind -eq "goal_review" -and
        [int]$State.counters.inquiry -ge $InquiryLimit
    ) {
        (
            "The unattended MaxInquiries guard is reached. It blocks only creation " +
            "of another inquiry; it is not evidence, a training cap, or a scientific judgment."
        )
    }
    else {
        ""
    }
    $correction = if ($ValidationError) {
        "Validation correction: $ValidationError Correct the request without discarding valid PI-owned work."
    }
    else {
        ""
    }

    $sections = @(
        "Human goal: $goal"
        "Factual evidence relative to the goal: $bestEvidence $(Get-LatestSessionResult -State $State)"
        "PI-interpreted gap: $gap"
        "PI checkpoint synthesis: $synthesis"
        "Session phase: $phase"
        "Active inquiry and relevance: $inquiry"
        "Bounded session objective: $($session.objective)"
        "Strategic resource summary: $resourceSummary"
        $executionHistory
        "Available operations:`n$($operations -join "`n")"
        $limitNote
        $correction
        $piPersona
        "The human goal is the only campaign objective. Science, novelty, and understanding do not justify continuation by themselves."
        "Choose the operation whose result would most improve the next decision toward the human goal."
        "Close or reframe the inquiry when its closure condition is met, evidence redirects it, or it is no longer a credible route. Do not silently drift."
        "Before ending this scientific session, write a durable checkpoint that records goal progress, the remaining obstacle, evidence references, completed operations, model roles, resource use, and the next inquiry or campaign decision."
        "A session may make multiple coherent Runner round trips. After measurement or training, interpret the factual result in this same backend session and choose the next operation or checkpoint."
        "You may inspect and modify the PI-owned scientific surface and build or revise PI-owned diagnostic tools before requesting their execution. The Runner invokes, validates, records, and recovers operations; it does not judge scientific adequacy."
        "Write exactly one request to research/operation_request.json using one strict schema-6 operation kind from research/instruments.md. Do not execute training, measurement, the Runner, the viewer, or the official assessment yourself."
        "Read research/brief.md and the latest checkpoint first. Open other sources only when needed: research/scenario.md for the protected goal, research/scientific_model.md for the physical reference, research/instruments.md for request schemas, research/program.md for lifecycle rationale, and AGENTS.md for ownership and command boundaries."
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
        "Factual evidence relative to the goal: no campaign operation has run; use only the human-authored system definition."
        "PI-interpreted gap: the campaign lacks a physical and scientific model of the robot and task."
        "Active inquiry and relevance: none; this is the dedicated preliminary PI session."
        "Bounded session objective: produce the campaign-start scientific model."
        "Strategic resource summary: zero inquiries, measurements, and training operations."
        "Available operation: write research/scientific_model.md; the launcher validates and publishes it."
        $piPersona
        "Construct the model from first principles and the human-authored robot, simulator, environment, observation, control, task, and benchmark implementation."
        "Do not use campaign-generated policies, measurements, checkpoints, prior PI decisions, or training outcomes."
        "The document must contain substantive registers headed Established facts, Physical consequences, and Unknowns. Distinguish repository facts from reasoned implications and unresolved quantities."
        "Treat approach, reaching, tolerance entry, settling, and sustained completion as one coupled embodied-control problem."
        "Read research/scenario.md first. Consult AGENTS.md for boundaries and inspect only relevant human-authored implementation; do not read research/program.md or research/instruments.md during this preliminary session."
        "Do not run training, measurements, the Runner, the viewer, Git mutations, or the official assessment."
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
            "The preliminary deliverable failed structural validation: $script:ScientificModelValidationFeedback"
            "Continue the same PI session and correct research/scientific_model.md. Preserve valid content and ensure all three required registers are substantive."
            "Do not run training, measurements, the Runner, the viewer, Git mutations, or the official assessment."
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
                New-ScientificSessionPrompt -State $State `
                    -InquiryLimit ([int]$State.campaign.max_inquiries)
            )
            "The accepted Runner operation $($pending.id) failed factually: $($pending.failure)"
            "Inspect the failure and correct only its PI-owned implementation cause when one exists. The accepted scientific request remains unchanged; do not replace research/operation_request.json."
        ) -join "`n`n"
        Invoke-PISession -Prompt $repairPrompt -Phase $State.scientific_session.kind `
            -Continue:$([bool]$script:PISessionId)
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            return 130
        }
        $exitCode = Invoke-Runner -Arguments @("--reaccept-pending")
        if ($exitCode -ne 0) {
            throw "The Runner could not reaccept the corrected operation."
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
    $maxInquiryExitCode = Invoke-Runner -Arguments @(
        "--synchronize-max-inquiries", "$MaxInquiries",
        "--backend-adapter", $PIBackend,
        "--backend-model", $Model,
        "--backend-reasoning", $Reasoning
    )
    if ($maxInquiryExitCode -ne 0) {
        throw (
            "Launcher MaxInquiries must match the persisted campaign setting " +
            "after fresh/startup initialization."
        )
    }

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
            Write-Status "=== Preliminary PI scientific-model session ===" -Color Magenta -Label pi
            if ((Invoke-ScientificModelPhase -State $state) -eq 130) {
                break
            }
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
                $assessmentAction = if ($state.official_assessment) {
                    "publishing recorded official assessment"
                }
                else {
                    "executing requested official assessment"
                }
                Write-Status "=== Runner $assessmentAction ===" -Color Cyan -Label runner
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
                Write-Status (
                    "Official assessment recorded: $($state.official_assessment.status). " +
                    "Research loop finished."
                ) -Color Green -Label runner
                break
            }
            Write-Status "PI concluded that no credible route remains. Research loop finished." -Color Green -Label pi
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
                "Design the initial scientific tools, observations, reward, training recipe, and measurements needed for the human goal, choose useful scientific operations, then checkpoint into campaign-level goal review."
            }
            elseif ($kind -eq "goal_review") {
                "Decide whether to request official assessment, open one bounded goal-linked inquiry, conclude that no credible route remains, or preserve a durable goal-review checkpoint."
            }
            else {
                (
                    "Advance $($state.active_inquiry.id) toward its closure condition: " +
                    "$($state.active_inquiry.closure_condition)"
                )
            }
            Write-Status "=== Starting bounded PI $kind session ===" -Color Magenta -Label pi
            $exitCode = Invoke-Runner -Arguments @(
                "--start-session", $kind,
                "--session-objective", $objective,
                "--backend-session-id", ([guid]::NewGuid().ToString()),
                "--backend-adapter", $PIBackend,
                "--backend-model", $Model,
                "--backend-reasoning", $Reasoning,
                "--max-inquiries", "$MaxInquiries"
            )
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
            Write-Status "=== Runner resuming the existing PI operation request ===" -Color Cyan -Label runner
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
                Write-Status "=== Runner operation failed; returning the factual error to the same PI session ===" -Color Yellow -Label runner
                continue
            }
            [void](Test-OperationRequest)
            $existingRequestProblem = $script:OperationValidationFeedback
        }

        $prompt = New-ScientificSessionPrompt -State $state `
            -InquiryLimit ([int]$state.campaign.max_inquiries) `
            -ValidationError $existingRequestProblem
        Invoke-PISession -Prompt $prompt -Phase $state.scientific_session.kind `
            -Continue:$([bool]$script:PISessionId)
        if (Test-StopAfterOperation $script:PIExitCode "PI session") {
            break
        }

        if (-not (Test-OperationRequest)) {
            $retryPrompt = New-ScientificSessionPrompt -State $state `
                -InquiryLimit ([int]$state.campaign.max_inquiries) `
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

        Write-Status "=== Runner executing PI-requested operation ===" -Color Cyan -Label runner
        $exitCode = Invoke-Runner
        if (Test-StopAfterOperation $exitCode "research runner") {
            break
        }
        if ($exitCode -eq 130) {
            Write-Status "=== Runner operation paused; transaction remains durable ===" -Color Yellow -Label runner
            break
        }
        if ($exitCode -ne 0) {
            $failed = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
            if (-not $failed.pending_operation.failure) {
                throw "The Runner operation failed without recoverable pending state."
            }
            Write-Status "=== Runner operation failed; returning the factual error to the same PI session ===" -Color Yellow -Label runner
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
