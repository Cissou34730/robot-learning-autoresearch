# Replays one Researcher decision against a frozen campaign state, so a prompt
# change can be attributed by holding the evidence constant.
#
# The Runner commits only settled states: no commit in history carries a pending
# decision. The frozen state therefore has to be captured from disk while a real
# campaign is paused at that decision, then replayed from that capture.
#
# Typical use:
#   .\reset_research.ps1 -Mode Fresh -Force
#   .\run_research.ps1                                # Ctrl-C once experiment 1
#                                                     # has trained, before the
#                                                     # analysis phase closes
#   .\replay_decision.ps1 -Capture -Name exp1
#   git checkout -b replay/prompt-decision-test
#   .\replay_decision.ps1 -Snapshot .replay/exp1 -Variant 68e179e^ -Label before -ExpectedBranch replay/prompt-decision-test
#   .\replay_decision.ps1 -Snapshot .replay/exp1 -Variant HEAD      -Label after  -ExpectedBranch replay/prompt-decision-test
#
# TRIALS HARD-RESET THE WORKING TREE. Run them only on a throwaway branch: a
# Researcher session that ignores its instructions can commit and mutate
# campaign artifacts, and the reset is what contains that.

[CmdletBinding(DefaultParameterSetName = "Run")]
param(
    # Freeze the campaign state currently on disk into a snapshot directory.
    [Parameter(ParameterSetName = "Capture", Mandatory)]
    [switch]$Capture,

    [Parameter(ParameterSetName = "Capture", Mandatory)]
    [string]$Name,

    [Parameter(ParameterSetName = "Capture")]
    [string]$CaptureRoot = ".replay",

    # Snapshot directory produced by -Capture.
    [Parameter(ParameterSetName = "Run", Mandatory)]
    [string]$Snapshot,

    # Commit supplying the harness under test: prompts, program.md, brief builder.
    [Parameter(ParameterSetName = "Run", Mandatory)]
    [string]$Variant,

    # Guards against running on a branch that holds work.
    [Parameter(ParameterSetName = "Run", Mandatory)]
    [string]$ExpectedBranch,

    [Parameter(ParameterSetName = "Run")]
    [ValidateRange(1, 1000)]
    [int]$Trials = 10,

    [Parameter(ParameterSetName = "Run")]
    [string]$Label = "",

    [Parameter(ParameterSetName = "Run")]
    [string]$ResultLog = "replay_results.jsonl",

    [Parameter(ParameterSetName = "Run")]
    [ValidateNotNullOrEmpty()]
    [string]$Model = "gpt-5.6-luna",

    [Parameter(ParameterSetName = "Run")]
    [ValidateSet("low", "medium", "high", "xhigh", "max")]
    [string]$Reasoning = "high",

    # Summarize an existing result log without running trials.
    [Parameter(ParameterSetName = "Tally", Mandatory)]
    [switch]$Tally,

    [Parameter(ParameterSetName = "Tally")]
    [string]$TallyLog = "replay_results.jsonl"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Campaign evidence, captured from disk because most of it is untracked.
$EvidenceFiles = @(
    "research/research_state.json"
    "research/results.jsonl"
    "research/postmortems.md"
    "research/EXPERIMENTS.md"
    "research/archive.md"
    "research/current_params.json"
)
$EvidenceDirectories = @(
    "research/training_logs"
    "research/evaluations"
    "research/checkpoints"
    "models/candidates"
)

# Restored from the variant: everything that shapes what the Researcher is told.
$HarnessPaths = @(
    "AGENTS.md"
    "run_research.ps1"
    "researcher_session.ps1"
    "researcher_copilot.py"
    "research/program.md"
    "research/instruments.md"
    "research/scenario.md"
    "research/build_research_brief.py"
    "research/runner_protocol.py"
)

# Produced per trial and never tracked, so a reset cannot clear them.
$DeliverablePaths = @(
    "research/brief.md"
    "research/proposal.json"
    "research/evaluation_request.json"
)

function Write-Step {
    param([string]$Message, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] " -ForegroundColor DarkGray -NoNewline
    Write-Host $Message -ForegroundColor $Color
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments)][string[]]$Arguments)
    $output = & git --no-pager @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed: $($output -join ' ')"
    }
    return $output
}

function Get-BlobAtRef {
    param([string]$Ref, [string]$Path)
    $text = & git --no-pager show "${Ref}:${Path}" 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $null
    }
    return ($text -join "`n")
}

function Read-JsonFile {
    param([string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

# The launcher chooses the phase from whichever pending field is set, and so
# does the replay, rather than assuming a lifecycle version.
function Resolve-PendingPhase {
    param([psobject]$State)
    if ($null -ne $State.pending_analysis) {
        return "post-training analysis"
    }
    if ($null -ne $State.pending_researcher_decision) {
        return "lineage decision"
    }
    return $null
}

function Get-PendingExperiment {
    param([psobject]$State, [string]$Phase)
    if ($Phase -eq "post-training analysis") {
        return [int]$State.pending_analysis.experiment
    }
    return [int]$State.pending_researcher_decision.experiment
}

function Invoke-Capture {
    $statePath = "research/research_state.json"
    if (-not (Test-Path $statePath)) {
        throw "No research/research_state.json on disk to capture."
    }
    $state = Read-JsonFile $statePath
    $phase = Resolve-PendingPhase -State $state
    if (-not $phase) {
        throw "The campaign on disk has no pending analysis or lineage decision, so there is no decision to freeze. Run the experiment's training first, and capture before the Researcher session runs."
    }

    $destination = Join-Path $CaptureRoot $Name
    if (Test-Path $destination) {
        throw "Snapshot '$destination' already exists. Choose another -Name or delete it."
    }
    New-Item -ItemType Directory -Path $destination -Force | Out-Null

    foreach ($file in $EvidenceFiles) {
        if (Test-Path $file) {
            $target = Join-Path $destination $file
            New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
            Copy-Item -LiteralPath $file -Destination $target -Force
        }
    }
    foreach ($directory in $EvidenceDirectories) {
        if (Test-Path $directory) {
            $target = Join-Path $destination $directory
            New-Item -ItemType Directory -Path (Split-Path $target) -Force | Out-Null
            Copy-Item -LiteralPath $directory -Destination $target -Recurse -Force
        }
    }

    [ordered]@{
        captured_at = (Get-Date).ToUniversalTime().ToString("o")
        phase       = $phase
        experiment  = (Get-PendingExperiment -State $state -Phase $phase)
        head_commit = (& git --no-pager rev-parse HEAD).Trim()
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination "snapshot.json") -Encoding utf8

    $size = [math]::Round(
        ((Get-ChildItem -LiteralPath $destination -Recurse -File |
            Measure-Object -Property Length -Sum).Sum / 1MB), 1)
    Write-Step "Captured '$phase' for experiment $(Get-PendingExperiment -State $state -Phase $phase) into $destination ($size MB)." Green
}

# The prompt text lives inside the launcher, so the variant's own wording is
# extracted rather than duplicated here, where it would silently drift.
function Get-PhasePrompt {
    param([string]$Ref, [string]$Phase, [psobject]$State)
    $source = Get-BlobAtRef -Ref $Ref -Path "run_research.ps1"
    if (-not $source) {
        throw "Could not read run_research.ps1 at $Ref."
    }

    if ($Phase -eq "lineage decision") {
        $pattern = '(?ms)^\s*\$decisionPrompt\s*=\s*@\(.*?^\s*\)\s*-join\s*" "'
        $promptName = "decisionPrompt"
        $researchState = $State
    }
    else {
        # $analysisPhasePrompt is chosen just above $analysisPrompt and feeds it,
        # so both assignments are taken as one block.
        $pattern = '(?ms)^\s*\$analysisPhasePrompt\s*=\s*if\s*\(.*?^\s*\$analysisPrompt\s*=\s*@\(.*?^\s*\)\s*-join\s*" "'
        $promptName = "analysisPrompt"
        $analysisExperiment = [int]$State.pending_analysis.experiment
        # Mirrors the launcher's own count of measurements already completed.
        $completedMeasurementCount =
            @($State.pending_analysis.requested_evaluations).Count +
            @($State.pending_analysis.partial_evaluations).Count +
            @($State.pending_analysis.task_reference_evaluations).Count +
            @($State.pending_analysis.partial_task_reference_evaluations).Count
    }

    $match = [regex]::Match($source, $pattern)
    if (-not $match.Success) {
        throw "Could not locate the '$Phase' prompt in run_research.ps1 at $Ref."
    }
    # This evaluates repository content from $Ref by design, so the prompt under
    # test is exactly what that commit would have sent.
    $builder = [scriptblock]::Create($match.Value + "`n`$$promptName")
    $prompt = & $builder
    if (-not $prompt) {
        throw "The '$Phase' prompt at $Ref evaluated to nothing."
    }
    return $prompt
}

function Reset-ReplayTree {
    param([string]$StartCommit)
    Invoke-Git reset --hard $StartCommit | Out-Null
    foreach ($path in $DeliverablePaths) {
        Remove-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    }
}

function Set-ReplayState {
    param([string]$SnapshotDirectory, [string]$VariantRef)
    foreach ($path in $HarnessPaths) {
        if (Get-BlobAtRef -Ref $VariantRef -Path $path) {
            Invoke-Git checkout $VariantRef -- $path | Out-Null
        }
    }
    foreach ($file in $EvidenceFiles) {
        $source = Join-Path $SnapshotDirectory $file
        if (Test-Path $source) {
            New-Item -ItemType Directory -Path (Split-Path $file) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $file -Force
        }
    }
    foreach ($directory in $EvidenceDirectories) {
        $source = Join-Path $SnapshotDirectory $directory
        if (Test-Path $source) {
            if (Test-Path $directory) {
                Remove-Item -LiteralPath $directory -Recurse -Force
            }
            New-Item -ItemType Directory -Path (Split-Path $directory) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $directory -Recurse -Force
        }
    }
    # The brief is generated, not stored, so the frozen evidence is rebuilt
    # through the variant's own builder exactly as the launcher would.
    uv run python research/build_research_brief.py | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "The variant's brief builder could not read the snapshot evidence."
    }
    $briefLines = @(Get-Content "research/brief.md").Count
    $experiments = if (Test-Path "research/results.jsonl") {
        @(Get-Content "research/results.jsonl").Count
    }
    else { 0 }
    Write-Step "  state restored: $experiments recorded experiments, brief rebuilt to $briefLines lines" DarkCyan
}

function Read-DecisionOutcome {
    $result = [ordered]@{
        outcome                 = "no_deliverable"
        request_final_benchmark = $null
        working_candidate       = $null
        reason                  = $null
        parse_error             = $null
    }
    if (Test-Path "research/evaluation_request.json") {
        $result.outcome = "more_measurement"
        return [pscustomobject]$result
    }
    if (-not (Test-Path "research/proposal.json")) {
        return [pscustomobject]$result
    }
    try {
        $proposal = Get-Content "research/proposal.json" -Raw | ConvertFrom-Json
    }
    catch {
        $result.outcome = "unparsable_proposal"
        $result.parse_error = $_.Exception.Message
        return [pscustomobject]$result
    }
    $decision = $proposal.previous_result_decision
    $requested = if ($null -eq $decision) { $null } else { $decision.request_final_benchmark }
    $result.request_final_benchmark = $requested
    $result.outcome = if ($requested -eq $true) { "requested_benchmark" } else { "closed_and_continued" }
    if ($null -ne $decision) {
        $result.working_candidate = $decision.working_lineage.candidate
        $result.reason = $decision.working_lineage.reason
    }
    return [pscustomobject]$result
}

function Write-Tally {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Step "No result log at $Path." Yellow
        return
    }
    $records = @(Get-Content -LiteralPath $Path | ForEach-Object { $_ | ConvertFrom-Json })
    Write-Step "=== $Path ($($records.Count) trials) ===" Magenta
    foreach ($group in ($records | Group-Object label)) {
        $counts = $group.Group | Group-Object outcome |
            ForEach-Object { "$($_.Name)=$($_.Count)" }
        Write-Host "  $($group.Name): $($counts -join ' ') of $($group.Group.Count)"
    }
}

if ($Capture) {
    Invoke-Capture
    return
}

if ($Tally) {
    Write-Tally -Path $TallyLog
    return
}

$branch = (& git --no-pager rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne $ExpectedBranch) {
    throw "Refusing to run: HEAD is on '$branch' but -ExpectedBranch is '$ExpectedBranch'. Each trial hard-resets the working tree."
}
if (@(& git --no-pager status --porcelain).Count -ne 0) {
    throw "Refusing to run: the working tree is not clean. Commit or discard changes first, because each trial hard-resets the tree."
}

if (-not (Test-Path (Join-Path $Snapshot "snapshot.json"))) {
    throw "Snapshot '$Snapshot' has no snapshot.json. Produce it with -Capture."
}
$snapshotMeta = Read-JsonFile (Join-Path $Snapshot "snapshot.json")
$snapshotState = Read-JsonFile (Join-Path $Snapshot "research/research_state.json")
$phase = Resolve-PendingPhase -State $snapshotState
if (-not $phase) {
    throw "Snapshot '$Snapshot' carries no pending decision."
}

$startCommit = (& git --no-pager rev-parse HEAD).Trim()
$variantCommit = (& git --no-pager rev-parse $Variant).Trim()
if (-not $Label) {
    $Label = $variantCommit.Substring(0, 10)
}
$snapshotFull = (Resolve-Path $Snapshot).Path

Write-Step "Branch     : $branch (restore point $($startCommit.Substring(0,10)))"
Write-Step "Snapshot   : $Snapshot - '$phase' for experiment $($snapshotMeta.experiment)"
Write-Step "Variant    : $($variantCommit.Substring(0,10)) - label '$Label'"
Write-Step "Trials     : $Trials"
Write-Step "Result log : $ResultLog"

$prompt = Get-PhasePrompt -Ref $Variant -Phase $phase -State $snapshotState
Write-Step "Prompt resolved from the variant ($($prompt.Length) characters)."
Write-Host "  $($prompt.Substring(0, [Math]::Min(140, $prompt.Length)))..." -ForegroundColor DarkGray

$running = [ordered]@{}
$sweepStarted = Get-Date

try {
    for ($trial = 1; $trial -le $Trials; $trial++) {
        Write-Step "=== Trial $trial of $Trials - label '$Label' - $phase ===" Magenta
        Reset-ReplayTree -StartCommit $startCommit
        Set-ReplayState -SnapshotDirectory $snapshotFull -VariantRef $Variant

        $sessionId = [guid]::NewGuid().ToString()
        Write-Step "  researcher session $($sessionId.Substring(0,8)) starting ($Model, $Reasoning)" DarkCyan
        $trialStarted = Get-Date
        uv run --group researcher python researcher_copilot.py `
            --session-id $sessionId --model $Model --reasoning $Reasoning $prompt
        $exitCode = if ($null -eq $LASTEXITCODE) { $null } else { [int]$LASTEXITCODE }
        $elapsed = [int]((Get-Date) - $trialStarted).TotalSeconds

        $outcome = Read-DecisionOutcome
        [ordered]@{
            timestamp               = (Get-Date).ToUniversalTime().ToString("o")
            label                   = $Label
            phase                   = $phase
            variant_commit          = $variantCommit
            snapshot                = $Snapshot
            experiment              = $snapshotMeta.experiment
            trial                   = $trial
            session_id              = $sessionId
            model                   = $Model
            reasoning               = $Reasoning
            exit_code               = $exitCode
            outcome                 = $outcome.outcome
            request_final_benchmark = $outcome.request_final_benchmark
            working_candidate       = $outcome.working_candidate
            reason                  = $outcome.reason
            parse_error             = $outcome.parse_error
        } | ConvertTo-Json -Compress -Depth 6 |
            Add-Content -LiteralPath $ResultLog -Encoding utf8

        if (-not $running.Contains($outcome.outcome)) {
            $running[$outcome.outcome] = 0
        }
        $running[$outcome.outcome]++
        $colour = if ($outcome.outcome -eq "requested_benchmark") { "Green" } else { "Cyan" }
        Write-Step "  trial ${trial} result: $($outcome.outcome) in ${elapsed}s (exit $exitCode)" $colour
        if ($outcome.working_candidate) {
            Write-Host "    working candidate: $($outcome.working_candidate)" -ForegroundColor DarkGray
        }
        $tally = ($running.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join " "
        Write-Step "  running total after $trial of ${Trials}: $tally" DarkCyan
    }
}
finally {
    Write-Step "Restoring the working tree to $($startCommit.Substring(0,10))." Yellow
    Reset-ReplayTree -StartCommit $startCommit
    Write-Step "Sweep '$Label' took $([int]((Get-Date) - $sweepStarted).TotalMinutes) minutes." Yellow
}

Write-Tally -Path $ResultLog
