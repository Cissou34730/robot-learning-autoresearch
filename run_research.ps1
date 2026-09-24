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
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
            "Assess progress toward a learned policy satisfying the human objective, from the observed training and measurement evidence."
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
                "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
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
            "Close the experiment from the available evidence. Resolve the recipe action, the working lineage, retention, the optional best-known designation, and whether to request the official benchmark, as separate decisions."
            "Terminal assessment of the frozen best-known model is available, is irreversible, and ends the campaign."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json, using the contracts in research/instruments.md."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
        Invoke-ResearcherSession -Prompt $decisionPrompt -Phase "lineage decision" -Experiment $researchState.pending_researcher_decision.experiment
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
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
        "Review the campaign's evidence and rewrite the Scientific strategy as a short current synthesis that prescribes no next action."
        $(if ($budgetReached) {
                "Only two outcomes are legal in this phase: request the official final assessment of the standing best-known model, or conclude that no further experiment is warranted. Each is written as a campaign_conclusion in research/proposal.json."
            }
            else {
                "Decide the next scientifically useful action toward the human objective. Available preparation outcomes: continuation, training with fresh or transfer initialization, and replication; requesting the official final assessment of the standing best-known model; concluding that no further experiment is warranted; or, before any of these, a measurement round on saved lineages. A measurement round on saved lineages commits this phase to proposing an experiment: after it, concluding is no longer accepted here."
            })
        $(if ($budgetReached) {
                ""
            }
            else {
                "If you propose training, state the question or hypothesis, the evidence motivating it, the observation that would change the next decision, and the parent and initialization the question calls for."
            })
        $(if ($budgetReached) {
                ""
            }
            else {
                "Terminal assessment of the standing best-known model is available, is irreversible, and ends the campaign."
            })
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        $(if ($budgetReached) {
                ""
            }
            else {
                "Code or configuration edits are required only when the selected operation calls for them."
            })
        $(if ($budgetReached) {
                "Expected deliverable: research/proposal.json containing only a campaign_conclusion, using the contract in research/instruments.md."
            }
            else {
                "Expected deliverable: one research/proposal.json for experiment $nextExperiment that either proposes the selected operation or records a campaign conclusion, using the contract in research/instruments.md, plus any edits called for by the selected operation. Alternatively, write research/evaluation_request.json to measure saved lineages before deciding; the completed round returns to this phase with its results available. The request may name only saved lineages (working, best_known, or a retained ID); candidates of a not-yet-run experiment are not available."
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
                    "Only two outcomes are legal: request the official final assessment of the standing best-known model, or conclude that no further experiment is warranted. Each is written as a campaign_conclusion in research/proposal.json."
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
