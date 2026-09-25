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
    [int]$MaxExperiments = 15,

    # Optional external control channel. The orchestrator owns this unique path
    # for one launcher invocation and raises the request by creating the file.
    [string]$StopRequestPath,

    [ValidateRange(1, 3600)]
    [int]$StopTimeoutSeconds = 180
)

Set-Location $PSScriptRoot

# Windows delivers Ctrl-C to every process sharing the console. Consume the
# first launcher event for cooperative shutdown; later events reach PowerShell.
if (-not ([System.Management.Automation.PSTypeName]'RobotResearchConsoleInterruptV2').Type) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Threading;

public static class RobotResearchConsoleInterruptV2
{
    private const uint CtrlCEvent = 0;
    private static readonly HandlerRoutine Handler = Handle;
    private static int installed;
    private static int interruptCount;

    [return: MarshalAs(UnmanagedType.Bool)]
    private delegate bool HandlerRoutine(uint controlType);

    [DllImport("Kernel32", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetConsoleCtrlHandler(
        HandlerRoutine handler,
        [MarshalAs(UnmanagedType.Bool)] bool add
    );

    private static bool Handle(uint controlType)
    {
        if (controlType != CtrlCEvent)
        {
            return false;
        }
        return Interlocked.Increment(ref interruptCount) == 1;
    }

    public static bool Install()
    {
        Interlocked.Exchange(ref interruptCount, 0);
        if (Interlocked.CompareExchange(ref installed, 1, 0) != 0)
        {
            return true;
        }
        if (SetConsoleCtrlHandler(Handler, true))
        {
            return true;
        }
        Interlocked.Exchange(ref installed, 0);
        return false;
    }

    public static bool IsRequested()
    {
        return Interlocked.CompareExchange(ref interruptCount, 0, 0) != 0;
    }

    public static bool IsEscalated()
    {
        return Interlocked.CompareExchange(ref interruptCount, 0, 0) > 1;
    }

    public static void Uninstall()
    {
        if (Interlocked.Exchange(ref installed, 0) != 0)
        {
            SetConsoleCtrlHandler(Handler, false);
        }
    }
}
'@
}

$script:CampaignExitCode = 0
$script:ImmediateEscalationExitCode = 125
$script:CampaignStopRequested = $false
$script:StopDeadlineExceeded = $false
$script:StopDeadline = $null
$script:StopRequestPath = if ($StopRequestPath) {
    [System.IO.Path]::GetFullPath($StopRequestPath)
}
else {
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

$scientificModelUseGuidance = "Use research/scientific_model.md as the campaign's physical reference when framing questions, interpreting observations, and designing analysis or measurements. Keep its coupled robot-task constraints visible, but do not treat its unknowns or listed quantities as ranked priorities or an intervention menu; current campaign evidence determines what remains relevant."
$researchFreedomGuidance = "Evidence gathering may discover or refine the scientific question. You may inspect code, logs, and artifacts, use existing tools, perform lightweight analysis, and create or modify researcher-owned analysis and measurement instrumentation. Existing evidence tools include research/query_training_log.py for preserved raw Stable-Baselines3 records; research/instruments.md documents its command. If the quantity you need is not emitted, modify researcher-owned instrumentation before requesting it."

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
    if ([RobotResearchConsoleInterruptV2]::IsRequested()) {
        return Request-CampaignStop "Console interrupt requested"
    }
    return $false
}

function Invoke-CooperativeProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$ArgumentList,
        [Parameter(Mandatory)][string]$Operation
    )

    if ([RobotResearchConsoleInterruptV2]::IsRequested()) {
        [void](Request-CampaignStop "Console interrupt requested")
        return 130
    }

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
        [switch]$Continue,
        [switch]$Preliminary
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

function Test-PreparationDeliverable {
    $validationOutput = @(
        uv run python research/run_experiment.py --check-preparation-deliverable 2>&1
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

# The phases below observe the same facts: what the process did,
# whether the deliverable exists, and whether the protected validator accepts it.
function Get-ProposalSessionStatus([string]$phase, [int]$attempt) {
    # Preparation accepts either a proposal or a saved-lineage measurement
    # request, so both files are observed before the deliverable is judged.
    $measurementPresent = Test-Path "research\evaluation_request.json"
    $present = $measurementPresent -or (Test-Path "research\proposal.json")
    $valid = $false
    $reason = "research/proposal.json or research/evaluation_request.json was not created"
    if ($present) {
        $valid = Test-PreparationDeliverable
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

[void][RobotResearchConsoleInterruptV2]::Install()

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
    if ($terminalState.schema_version -eq 4 -and $null -ne $terminalState.pending_campaign_conclusion) {
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

    $researchState = Get-Content "research\research_state.json" -Raw | ConvertFrom-Json
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

    if ($researchState.schema_version -eq 4 -and $null -ne $researchState.pending_analysis) {
        Update-ResearchBrief
        $analysisExperiment = [int]$researchState.pending_analysis.experiment
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
        $analysisPrompt = @(
            $analysisPhasePrompt
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
            $scientificModelUseGuidance
            "Assess progress toward a learned policy satisfying the human objective, from the observed training and measurement evidence."
            $researchFreedomGuidance
            "If updating the current campaign's Scientific strategy in research/postmortems.md, revise the existing section in place as fallible, non-binding memory of evidence, limits, and unresolved behavioral distinctions; do not turn it into a ranked agenda or candidate-code list, and do not append a second section with the same heading."
            "Choose exactly one outcome: write research/evaluation_request.json for another measurement round, or append the experiment postmortem and write a closure-only research/proposal.json choosing working lineage, code action, retention, and optionally best known."
            "If the lineage you are about to select scored well on a panel that was used to select it, that score is not independent evidence; confirming it requires a disjoint panel, and the fixed task-reference panel is a permanently reused one."
            "Further training is an ordinary next experiment after closure; do not prepare that proposal now."
            "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
        ) -join " "
        Invoke-ResearcherSession -Prompt $analysisPrompt -Phase "post-training analysis" -Experiment $analysisExperiment
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
                "The same Researcher session context remains available. Correct only the invalid or missing deliverable: a valid research/evaluation_request.json for another measurement round, or the required postmortem plus a closure-only research/proposal.json."
                "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
            ) -join " "
            Invoke-ResearcherSession -Prompt $analysisRetryPrompt -Phase "post-training analysis" -Experiment $analysisExperiment -Continue
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                break CampaignLoop
            }
            $analysisStatus = Get-AnalysisSessionStatus 2
            Write-ResearcherSessionStatus $analysisStatus
            if (-not $analysisStatus.Complete) {
                throw "Researcher ended twice without a valid post-training analysis deliverable. Last validation error: $($analysisStatus.Reason)"
            }
        }
        if (Test-Path "research\evaluation_request.json") {
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
        Write-Status "=== Post-training analysis outcome recorded ===" Green
        continue
    }

    if ($null -ne $researchState.pending_evaluation_request) {
        Update-ResearchBrief
        if ($researchState.schema_version -eq 4) {
            # A version-4 preparation measurement returns to experiment
            # preparation after execution; it never enters the legacy
            # evaluation-design phase.
            Write-Status "=== Resuming the researcher's preparation measurement ==="
            $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
            if (Test-StopAfterOperation $runnerExitCode "research runner") {
                break
            }
            if ($runnerExitCode -eq 130) {
                Write-Status "=== Preparation measurement paused; completed measurements were saved ===" Yellow
                break
            }
            if ($runnerExitCode -ne 0) {
                throw "Runner execution of the accepted preparation measurement request failed. The researcher phase is not reopened."
            }
            Update-ResearchBrief
            Write-Status "=== Preparation measurement complete; returning to preparation ===" Green
            continue
        }
        $evaluationPlanExists = $null -ne $researchState.pending_evaluation_request.evaluation_plan
        if (-not $evaluationPlanExists) {
            Remove-Item "research\evaluation_request.json" -ErrorAction SilentlyContinue
            Write-Status "=== Researcher designing evaluation for experiment $($researchState.pending_evaluation_request.experiment) ==="
            $evaluationPrompt = @(
                "Current phase: design the research evaluation for experiment $($researchState.pending_evaluation_request.experiment). Do not exit without the required deliverable."
                "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
                $scientificModelUseGuidance
                $researchFreedomGuidance
                "Expected deliverable: research/evaluation_request.json for the current experiment, using the contract in research/instruments.md."
                "Do not start training or evaluation, resolve lineage, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the request."
            ) -join " "
            Invoke-ResearcherSession -Prompt $evaluationPrompt -Phase "evaluation design" -Experiment $researchState.pending_evaluation_request.experiment
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                break
            }
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
                if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                    break CampaignLoop
                }
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
        $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Requested evaluation paused; completed measurements were saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Runner execution of the validated evaluation request failed. The researcher deliverable was already accepted, so the researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Requested evaluations complete ===" Green
        continue
    }

    if (Test-Path "research\BASELINE_PENDING") {
        if (-not (Test-Path "research\scientific_model.md" -PathType Leaf)) {
            # The maintainer-owned persona prompt for this phase. It is supplied
            # verbatim and is the single place to edit its wording.
            $scientificModelPhasePrompt = @'
You are an autonomous robotics research engineer specializing in robot learning, control, simulation, and reinforcement learning.

Your task is to build a scientific and physical understanding of the robot and the human-defined task before looking at any campaign history or training evidence.

Reason about the robot as an embodied dynamical system. Your objective is to understand how its physical structure, actuation, sensing, control loop, task geometry, and interaction with the simulator determine what behaviors are possible, difficult, ambiguous, or constrained.

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

Do not inspect or use any artifact produced by a research campaign, training run, evaluation run, or autonomous Researcher.

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

You may inspect only the system intentionally defined by the human before autonomous research begins: the robot model, simulator configuration, task and benchmark definition, environment mechanics, action interface, observation/sensing implementation, success semantics, fixed constraints, and other human-authored code necessary to understand the physical system.

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

    if ($null -ne $researchState.pending_researcher_decision) {
        Update-ResearchBrief
        $closingExperiment = [int]$researchState.pending_researcher_decision.experiment
        $baselineClosure = $researchState.schema_version -eq 4 -and $closingExperiment -eq 1
        Write-Status "=== Researcher resolving lineage and scientific recipe for experiment $closingExperiment ==="
        $decisionPrompt = @(
            "Current phase: close experiment $closingExperiment and resolve its lineage and scientific recipe. Do not exit without the required deliverables."
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
            $scientificModelUseGuidance
            "Use campaign artifacts for scientific evidence; inspect read-only Git only if the current experiment's scientific recipe delta is needed to justify keep or revert."
            $(if ($baselineClosure) {
                    "Close the experiment from the available evidence. Resolve the recipe action, the working lineage, retention, and the optional best-known designation. Because this is the baseline closure, request_final_benchmark must be false; terminal assessment becomes available after one completed post-baseline scientific operation."
                }
                else {
                    "Close the experiment from the available evidence. Resolve the recipe action, the working lineage, retention, the optional best-known designation, and whether to request the official benchmark, as separate decisions."
                    "Request the official benchmark only if you expect it to return goal_reached; it is a verdict you claim, not an instrument for resolving an uncertainty your development measurements left open, and no development panel ever declares the objective reached."
                })
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json, using the contracts in research/instruments.md."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        Invoke-ResearcherSession -Prompt $decisionPrompt -Phase "lineage decision" -Experiment $closingExperiment
        if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
            break
        }
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
            if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
                break CampaignLoop
            }
            $lineageStatus = Get-LineageSessionStatus $pendingExperiment 2
            Write-ResearcherSessionStatus $lineageStatus
            if (-not $lineageStatus.Complete) {
                throw "Researcher ended twice without valid lineage deliverables for experiment $pendingExperiment. Last validation error: $($lineageStatus.Reason)"
            }
        }
        $runnerExitCode = Invoke-Runner
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -ne 0) {
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
    $completedPreparationRounds = 0
    if ($null -ne $researchState.preparation_measurement -and $null -ne $researchState.preparation_measurement.rounds) {
        $completedPreparationRounds = @($researchState.preparation_measurement.rounds).Count
    }
    $finalAssessmentEligible = (
        $researchState.schema_version -ne 4 -or
        [int]$researchState.last_experiment -gt 1 -or
        $completedPreparationRounds -gt 0
    )
    $budgetReached = $MaxExperiments -gt 0 -and $allocatedExperiment -ge $MaxExperiments
    if ($budgetReached) {
        # The budget forbids allocating another training experiment, but the
        # campaign can still be concluded without one.
        Write-Status "Experiment budget reached: $allocatedExperiment of $MaxExperiments. Only a campaign conclusion may be prepared." Yellow
    }

    # Anchor the rollback baseline before the researcher can change or commit
    # science. An unfinished experiment keeps the anchor it already established.
    if ($budgetReached) {
        $runnerExitCode = Invoke-Runner -Arguments @("--begin-hypothesis", "--conclusion-only")
    }
    else {
        $runnerExitCode = Invoke-Runner -Arguments @("--begin-hypothesis")
    }
    if (Test-StopAfterOperation $runnerExitCode "research runner") {
        break
    }
    if ($runnerExitCode -ne 0) {
        throw "Could not establish the scientific parent of the next experiment."
    }

    # Refreshed after the anchor so a budget-exhausted phase brief reflects the
    # conclusion-only state it is actually in.
    Update-ResearchBrief

    Write-Status "=== Researcher forming next hypothesis ==="
    $resultCountBefore = @(Get-Content "research\results.jsonl" -ErrorAction SilentlyContinue).Count
    $nextExperiment = $allocatedExperiment + 1
    $researchPrompt = @(
        $(if ($budgetReached) {
                "Current phase: conclude the campaign. The experiment budget is exhausted; no further experiment may be prepared."
            }
            else {
                "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending."
            })
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, research/brief.md, and research/scientific_model.md."
        $scientificModelUseGuidance
        "Review the campaign's evidence and rewrite the Scientific strategy as short, fallible, non-binding memory of current observations, weakened explanations, limits, and unresolved behavioral distinctions. It prescribes no next action, ranks no uncertainty, and names no candidate code change."
        "Begin the next decision from the human objective and current campaign evidence. The Scientific strategy is revisable memory, not an authority, backlog, or obligation. The frozen scientific model remains the physical reference but does not prioritize the next action."
        $(if ($budgetReached) { "" } else { $researchFreedomGuidance })
        "For training or continuation, connect the proposed change to possible learned behavior and a complete-task comparison. No particular lever or established mechanism is required; see research/instruments.md for the proposal contract."
        $(if ($budgetReached) {
                $(if ($finalAssessmentEligible) {
                        "Only two outcomes are legal in this phase: request the official final assessment of the standing best-known model, or conclude that no further experiment is warranted. Each is written as a campaign_conclusion in research/proposal.json."
                    }
                    else {
                        "Only one outcome is legal in this phase: conclude that no further experiment is warranted through a campaign_conclusion in research/proposal.json. Final assessment is not available because no post-baseline scientific operation has completed."
                    })
            }
            elseif ($finalAssessmentEligible) {
                "Decide the next scientifically useful action toward the human objective. Available preparation outcomes, with no default or preference implied by their order: a measurement round on saved lineages; replication; continuation or training with fresh or transfer initialization; requesting the official final assessment of the standing best-known model; or concluding that no further experiment is warranted. After a measurement round, this phase reopens with its evidence and all of these outcomes remain available."
            }
            else {
                "Decide the next scientifically useful action toward the human objective. Available preparation outcomes, with no default or preference implied by their order: a measurement round on saved lineages; replication; continuation or training with fresh or transfer initialization; or concluding that no further experiment is warranted. Final assessment becomes available after one of those post-baseline scientific operations completes; a preparation measurement returns to this phase with its evidence."
            })
        $(if ($budgetReached -or -not $finalAssessmentEligible) {
                ""
            }
            else {
                "If you propose training, state the question or hypothesis, the evidence motivating it, the observation that would change the next decision, and the parent and initialization the question calls for."
            })
        $(if ($budgetReached) {
                ""
            }
            else {
                "Request the official final assessment only if you expect it to return goal_reached; it is a verdict you claim, not an instrument for resolving an uncertainty your development measurements left open, and no development panel ever declares the objective reached."
            })
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        $(if ($budgetReached) {
                ""
            }
            else {
                "The current implementation is a starting point, not a prescribed method. You have a total freedom in the researcher perimeter. You may change code, implementations, configuration values, anywhere in the researcher-owned scientific surface, including the reward, training environment, observations, action mapping, learning method, training procedure, evaluation, and instrumentation. You can add and remove, change and transform."
            })
        $(if ($budgetReached) {
                "Expected deliverable: research/proposal.json containing only a campaign_conclusion, using the contract in research/instruments.md."
            }
            else {
                "Expected deliverable: either research/evaluation_request.json to measure saved lineages before deciding, or one research/proposal.json for experiment $nextExperiment that proposes the selected operation or records a campaign conclusion, using the contracts in research/instruments.md. Include only edits called for by the selected operation. A completed measurement round returns to this phase with its results available. A preparation request may name only saved lineages (working, best_known, or a retained ID); candidates of a not-yet-run experiment are not available."
            })
        $(if ($budgetReached) {
                "The phase is incomplete until the campaign conclusion has been written. A campaign conclusion is recorded as a decision, never as an experiment."
            }
            else {
                "Do not exit after analysis or diagnosis: this phase is incomplete until one of the legal preparation deliverables has been written. A campaign conclusion is written through research/proposal.json and is recorded as a decision, never as an experiment."
            })
        $(if ($budgetReached) {
                "Do not start training or evaluation, or write a lineage decision; the launcher validates and executes the proposal."
            }
            else {
                "Do not start training, execute measurements, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal or accepted measurement request."
            })
    ) -join " "
    Invoke-ResearcherSession -Prompt $researchPrompt -Phase "new hypothesis" -Experiment $nextExperiment
    if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
        break
    }

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
            $(if ($budgetReached) {
                    "Current phase: conclude the campaign. The experiment budget is exhausted; no further experiment may be prepared. The previous deliverable failed validation: $proposalProblem. Do not exit without a corrected deliverable."
                    "The same Researcher session context remains available. Correct only the invalid or missing research/proposal.json, which must contain a campaign_conclusion, preserving valid researcher-owned edits that belong to this unfinished experiment."
                    $(if ($finalAssessmentEligible) {
                            "Only two outcomes are legal: request the official final assessment of the standing best-known model, or conclude that no further experiment is warranted. Each is written as a campaign_conclusion in research/proposal.json."
                        }
                        else {
                            "Only one outcome is legal: conclude that no further experiment is warranted through a campaign_conclusion in research/proposal.json. Final assessment is not available because no post-baseline scientific operation has completed."
                        })
                    "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                    "Expected deliverable: a corrected research/proposal.json containing only a campaign_conclusion."
                    "Do not start training, execute measurements, write a lineage decision, or invoke research/run_experiment.py."
                }
                else {
                    "Current phase: prepare experiment $nextExperiment. The previous deliverable failed validation: $proposalProblem. Do not exit without a corrected deliverable."
                    "The same Researcher session context remains available. Correct only the invalid or missing research/proposal.json for experiment $nextExperiment, or the invalid or missing saved-lineage research/evaluation_request.json, preserving valid researcher-owned edits that belong to this unfinished experiment."
                    "Reread relevant contract and state files as needed to resolve the validation error; reuse the existing context for everything else."
                    "Expected deliverable: a corrected research/proposal.json for experiment $nextExperiment, or a corrected saved-lineage research/evaluation_request.json."
                    "Do not start training, execute measurements, write a lineage decision, or invoke research/run_experiment.py."
                })
        ) -join " "
        Invoke-ResearcherSession -Prompt $retryPrompt -Phase "new hypothesis" -Experiment $nextExperiment -Continue
        if (Test-StopAfterOperation $script:ResearcherExitCode "researcher session") {
            break CampaignLoop
        }

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
    if (Test-Path "research\evaluation_request.json") {
        # A saved-lineage measurement is executed before any proposal, then the
        # phase reopens with its results available for the parent decision.
        Write-Status "=== Executing the researcher's saved-lineage measurement request ==="
        $runnerExitCode = Invoke-Runner -Arguments @("--evaluate-pending")
        if (Test-StopAfterOperation $runnerExitCode "research runner") {
            break
        }
        if ($runnerExitCode -eq 130) {
            Write-Status "=== Preparation measurement paused; completed measurements were saved ===" Yellow
            break
        }
        if ($runnerExitCode -ne 0) {
            throw "Runner execution of the accepted preparation measurement request failed. The researcher phase is not reopened."
        }
        Update-ResearchBrief
        Write-Status "=== Preparation measurement complete; the next hypothesis returns with new evidence ===" Green
        continue
    }
    $runnerExitCode = Invoke-Runner
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
    Write-Status "=== Experiment $nextExperiment session closed ===" Green
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
    elseif ([RobotResearchConsoleInterruptV2]::IsRequested()) {
        [void](Request-CampaignStop "Console interrupt requested")
        $script:CampaignExitCode = 130
    }
    else {
        throw
    }
}
finally {
    $reportedImmediateEscalation = [RobotResearchConsoleInterruptV2]::IsEscalated()
    if ($reportedImmediateEscalation) {
        [Console]::Error.WriteLine(
            "Additional console interrupt requested; escalating immediately."
        )
    }
    try {
        Stop-OpenCodeCampaignServer
    }
    finally {
        try {
            $loopMutex.ReleaseMutex()
            $loopMutex.Dispose()
        }
        finally {
            $immediateEscalation = [RobotResearchConsoleInterruptV2]::IsEscalated()
            if ($immediateEscalation -and -not $reportedImmediateEscalation) {
                [Console]::Error.WriteLine(
                    "Additional console interrupt requested; escalating immediately."
                )
            }
            [RobotResearchConsoleInterruptV2]::Uninstall()
            if ($immediateEscalation) {
                [Environment]::Exit($script:ImmediateEscalationExitCode)
            }
        }
    }
}
if ($script:CampaignExitCode -ne 0) {
    exit $script:CampaignExitCode
}
