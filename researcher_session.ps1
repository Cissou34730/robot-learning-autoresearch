# Observation of a bounded Researcher session, as three independent facts: the
# process outcome, the presence of the deliverable it was asked to produce, and
# that deliverable's validity. Nothing here reads what the Researcher printed,
# so it stays true whatever command invokes the Researcher.

# ---------------------------------------------------------------------------
# One-way observation feed (read by the read-only terminal report).
# Failures are swallowed: presenting never alters launcher behavior.
# ---------------------------------------------------------------------------

function Get-TuiCampaignRoot {
    if ($script:TuiCampaignRoot) { return $script:TuiCampaignRoot }
    if ($CampaignRoot) { $script:TuiCampaignRoot = $CampaignRoot; return $CampaignRoot }
    if ($env:ROBOT_LEARNING_CAMPAIGN_ROOT) {
        $script:TuiCampaignRoot = $env:ROBOT_LEARNING_CAMPAIGN_ROOT
        return $env:ROBOT_LEARNING_CAMPAIGN_ROOT
    }
    $script:TuiCampaignRoot = (Get-Location).Path
    return $script:TuiCampaignRoot
}

function Get-TuiCampaignId {
    if ($script:TuiCampaignId) { return $script:TuiCampaignId }
    try {
        $statePath = Join-Path (Get-TuiCampaignRoot) "runner\state\research_state.json"
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $value = [string]$state.campaign.id
        if ($value) { $script:TuiCampaignId = $value }
        return $value
    }
    catch {
        return ""
    }
}

$script:ConsoleRenderingEnabled = $true

function Write-TuiObservation {
    param(
        [Parameter(Mandatory)][string]$Kind,
        [string]$Scope = "",
        [string]$Text = "",
        [hashtable]$Fields = @{}
    )
    try {
        $campaignId = Get-TuiCampaignId
        if (-not $campaignId) { return }
        $directory = Join-Path (Get-TuiCampaignRoot) "reports\tui_observations"
        $timestamp = (Get-Date).ToUniversalTime().ToString("o")
        $record = [ordered]@{
            campaign_id = $campaignId
            ts = $timestamp
            kind = $Kind
        }
        if ($Scope) { $record.scope = $Scope }
        if ($Text) { $record.text = $Text }
        foreach ($key in $Fields.Keys) { $record[$key] = $Fields[$key] }
        $payload = [ordered]@{}
        if ($Text) { $payload.text = $Text }
        if ($Scope) { $payload.scope = $Scope }
        foreach ($key in $Fields.Keys) { $payload[$key] = $Fields[$key] }
        $severity = if ($Scope -eq "error") { "error" } elseif ($Scope -eq "warning") { "warning" } else { "info" }
        $typed = [ordered]@{
            schema_version = 1
            event_id = [guid]::NewGuid().ToString()
            campaign_id = $campaignId
            ts = $timestamp
            kind = $Kind
            scope = $Scope
            severity = $severity
            operation_id = if ($Fields.ContainsKey("operation_id")) { $Fields["operation_id"] } else { "" }
            session_id = if ($Fields.ContainsKey("session_id")) { $Fields["session_id"] } else { "" }
            inquiry_id = if ($Fields.ContainsKey("inquiry_id")) { $Fields["inquiry_id"] } else { "" }
            payload = $payload
        }
        foreach ($sink in @(
            @{ Override = $env:TUI_OBSERVATIONS; Path = (Join-Path $directory "$campaignId.jsonl"); Record = $record },
            @{ Override = $env:TUI_TYPED_EVENTS; Path = (Join-Path $directory "$campaignId.events.jsonl"); Record = $typed }
        )) {
            # Failure or disabling of either transport must not disable the other.
            try {
                $override = $sink.Override
                if ($null -ne $override -and $override.Trim().ToLowerInvariant() -in @("", "0", "off", "none", "false")) {
                    continue
                }
                $path = if ($override) { $override } else { $sink.Path }
                $parent = Split-Path -Parent $path
                if ($parent -and -not (Test-Path -LiteralPath $parent)) {
                    New-Item -ItemType Directory -Path $parent -Force | Out-Null
                }
                $json = $sink.Record | ConvertTo-Json -Compress -Depth 10
                $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
                $stream = [IO.File]::Open(
                    $path, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite
                )
                try { $stream.Write($bytes, 0, $bytes.Length) }
                finally { $stream.Dispose() }
            }
            catch { }
        }
    }
    catch {
    }
}

function Write-Status {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan,
        [string]$Label = ""
    )
    if (-not $Label) {
        $Label = switch ($Color) { Green { "done" }; Yellow { "wait" }; default { "run" } }
    }
    $scope = switch ($Label) {
        "session" { "session" }; "done" { "success" }; "wait" { "warning" }; "error" { "error" }; default { "info" }
    }
    $text = $Message -replace '^===\s*|\s*===$', ''
    Write-TuiObservation -Kind console_line -Scope $scope -Text $text
    if ($script:ConsoleRenderingEnabled) {
        Write-ConsoleStatus -Message $Message -Color $Color -Label $Label
    }
}

function Write-ConsoleStatus {
    param(
        [Parameter(Mandatory)][string]$Message,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan,
        [string]$Label = ""
    )
    if (-not $Label) {
        $Label = switch ($Color) {
            Green { "done" }
            Yellow { "wait" }
            default { "run" }
        }
    }
    $text = $Message -replace '^===\s*|\s*===$', ''
    $timestamp = "[$(Get-Date -Format 'HH:mm:ss')]"
    $marker = "[$Label]"
    $redirected = try {
        [Console]::IsOutputRedirected
    }
    catch {
        $true
    }
    if ($redirected) {
        $text = ($text -replace '\s+', ' ').Trim()
        Write-Host "$timestamp $marker $text"
        return
    }
    $prefixLength = $timestamp.Length + $marker.Length + 2
    $width = try {
        [Math]::Max([Console]::WindowWidth, 40)
    }
    catch {
        100
    }
    $lineWidth = [Math]::Max($width - $prefixLength, 30)
    $words = @($text -split '\s+')
    $lines = [System.Collections.Generic.List[string]]::new()
    $current = ""
    foreach ($word in $words) {
        if (-not $current) {
            $current = $word
        }
        elseif (($current.Length + 1 + $word.Length) -le $lineWidth) {
            $current += " $word"
        }
        else {
            $lines.Add($current)
            $current = $word
        }
    }
    if ($current) {
        $lines.Add($current)
    }
    if ($lines.Count -eq 0) {
        $lines.Add("")
    }
    for ($index = 0; $index -lt $lines.Count; $index += 1) {
        if ($index -eq 0) {
            Write-Host "$timestamp " -ForegroundColor DarkGray -NoNewline
            Write-Host $marker -ForegroundColor $Color -NoNewline
            Write-Host " $($lines[$index])"
        }
        else {
            Write-Host (" " * $prefixLength) -NoNewline
            Write-Host $lines[$index]
        }
    }
}

function Write-Card {
    param(
        [Parameter(Mandatory)][string]$Title,
        [string[]]$Lines = @(),
        [ConsoleColor]$Color = [ConsoleColor]::Cyan,
        [ConsoleColor]$BodyColor = [ConsoleColor]::White
    )
    $scope = switch ($Color) {
        Magenta { "pi" }; Yellow { "warning" }; Red { "error" }; Green { "success" }; default { "info" }
    }
    $text = "=== $Title ==="
    if ($Lines.Count -gt 0) { $text += "`n" + ($Lines -join "`n") }
    Write-TuiObservation -Kind console_line -Scope $scope -Text $text
    if ($script:ConsoleRenderingEnabled) {
        Write-ConsoleCard -Title $Title -Lines $Lines -Color $Color -BodyColor $BodyColor
    }
}

function Write-ConsoleCard {
    param(
        [Parameter(Mandatory)][string]$Title,
        [string[]]$Lines = @(),
        [ConsoleColor]$Color = [ConsoleColor]::Cyan,
        [ConsoleColor]$BodyColor = [ConsoleColor]::White
    )
    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] " `
        -ForegroundColor DarkGray -NoNewline
    Write-Host "=== $Title ===" -ForegroundColor $Color
    foreach ($line in $Lines) {
        Write-Host "  $line" -ForegroundColor $BodyColor
    }
    Write-Host ""
}

function New-ResearcherSessionStatus {
    param(
        [Parameter(Mandatory)][string]$Phase,
        [Parameter(Mandatory)][int]$Attempt,
        [AllowNull()][object]$ExitCode,
        [Parameter(Mandatory)][string]$Deliverable,
        [bool]$Present,
        [bool]$Valid,
        [string]$Reason = ""
    )
    $validity = if (-not $Present) {
        "not run"
    }
    elseif ($Valid) {
        "valid"
    }
    else {
        "invalid"
    }
    [pscustomobject]@{
        Phase       = $Phase
        Attempt     = $Attempt
        ExitCode    = $ExitCode
        Deliverable = $Deliverable
        Present     = $Present
        Validity    = $validity
        Reason      = $Reason
        # The deliverable contract closes a bounded phase. The process's opinion
        # of its own success neither completes nor invalidates it.
        Complete    = ($Present -and $Valid)
    }
}

function Write-ResearcherSessionStatus {
    param([Parameter(Mandatory)][psobject]$Status)
    $exitText = if ($null -eq $Status.ExitCode) { "unavailable" } else { [string]$Status.ExitCode }
    if ($Status.Complete -and $exitText -eq "0") {
        $text = "Researcher phase closed: $($Status.Phase), attempt $($Status.Attempt), process=$exitText, $($Status.Deliverable)=$($Status.Validity)"
        $scope = "success"
    }
    else {
        $presence = if ($Status.Present) { "present" } else { "missing" }
        $text = "Researcher session - $($Status.Phase) - attempt $($Status.Attempt)`nProcess exit : $exitText`nDeliverable  : $($Status.Deliverable) ($presence)`nValidation   : $($Status.Validity)"
        if ($Status.Reason) { $text += "`nReason       : $($Status.Reason)" }
        $scope = "warning"
    }
    Write-TuiObservation -Kind console_line -Scope $scope -Text $text -Fields @{
        phase = $Status.Phase; attempt = $Status.Attempt; exit_code = $Status.ExitCode
        deliverable = $Status.Deliverable; present = $Status.Present; validity = $Status.Validity; reason = $Status.Reason
    }
    if ($script:ConsoleRenderingEnabled) {
        Write-ConsoleResearcherSessionStatus -Status $Status
    }
}

function Write-ConsoleResearcherSessionStatus {
    param([Parameter(Mandatory)][psobject]$Status)
    $exitText = if ($null -eq $Status.ExitCode) {
        "unavailable"
    }
    else {
        [string]$Status.ExitCode
    }
    if ($Status.Complete -and $exitText -eq "0") {
        # A completed phase still reports as one line, but the line says which
        # phase it closes so it is not read as a stray status message.
        Write-ConsoleStatus (
            "Researcher phase closed: $($Status.Phase), attempt $($Status.Attempt), " +
            "process=$exitText, $($Status.Deliverable)=$($Status.Validity)"
        ) Green
        return
    }
    $presence = if ($Status.Present) { "present" } else { "missing" }
    Write-ConsoleStatus "=== Researcher session - $($Status.Phase) - attempt $($Status.Attempt) ===" Yellow
    Write-Host "Process exit : $exitText"
    Write-Host "Deliverable  : $($Status.Deliverable) ($presence)"
    Write-Host "Validation   : $($Status.Validity)"
    if ($Status.Reason) {
        Write-Host "Reason       : $($Status.Reason)"
    }
}

function ConvertTo-RepositoryRelativePath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$Root
    )

    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $fullPath = [System.IO.Path]::GetFullPath($Path)
    return $fullPath.Substring($rootPath.Length).TrimStart('\', '/') -replace '\\', '/'
}

function Test-PIWritablePath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [switch]$Preliminary
    )

    $relative = ($Path -replace '\\', '/').TrimStart('/').ToLowerInvariant()
    if ($relative -in @(
        "robot_learning/scenario/__init__.py",
        "benchmark/adapters/final_benchmark.py",
        "benchmark/adapters/task_reference.py"
    )) {
        return $false
    }
    if ($Preliminary) {
        return $relative -eq "pi_workspace/scientific_model.md"
    }
    return (
        $relative -in @(
            "robot_learning/train.py",
            "robot_learning/evaluate.py",
            "robot_learning/play.py",
            "robot_learning/training/current_params.json",
            "pi_workspace/operation_request.json"
        ) -or
        $relative.StartsWith("robot_learning/scenario/") -or
        $relative.StartsWith("robot_learning/training/") -or
        $relative.StartsWith("robot_learning/lab/")
    )
}

function Test-LauncherSnapshotExcludedPath {
    param([Parameter(Mandatory)][string]$Path)

    $relative = ($Path -replace '\\', '/').TrimStart('/').ToLowerInvariant()
    $parts = @($relative.Split('/', [System.StringSplitOptions]::RemoveEmptyEntries))
    $excludedDirectories = @(
        ".git",
        ".copilot",
        ".py-git-probe",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".pyre",
        ".pytype",
        ".hypothesis",
        ".tox",
        ".nox",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "node_modules",
        "build",
        "dist",
        "wheels",
        "htmlcov",
        "reports"
    )
    foreach ($part in $parts) {
        if (
            $part -in $excludedDirectories -or
            $part.StartsWith(".pytest-") -or
            $part.EndsWith(".egg-info")
        ) {
            return $true
        }
    }
    if (
        $relative -eq ".coverage" -or
        $relative.StartsWith(".coverage.") -or
        $relative -eq "coverage.xml" -or
        $relative.EndsWith(".pyc")
    ) {
        return $true
    }
    if ($relative -in @(
        "runner/state/research_state.json",
        "campaigns/results.jsonl",
        "campaigns/experiments.md",
        "runner/state/goal_reached",
        "runner/state/recovery_pending",
        "runner/state/restart_pending",
        "campaigns/brief.md",
        "runner/state/last_train_summary.md",
        "runner/state/last_evaluation.json"
    )) {
        return $true
    }
    return (
        $relative.StartsWith("campaigns/training_logs/") -or
        $relative.StartsWith("campaigns/evaluations/") -or
        $relative.StartsWith("campaigns/checkpoints/candidates/") -or
        $relative.StartsWith("campaigns/checkpoints/retained/") -or
        $relative.StartsWith("models/candidates/")
    )
}

function Get-LauncherHeadIdentity {
    param([string]$Root = $PSScriptRoot)

    $output = @(& git -C $Root rev-parse --verify HEAD 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not resolve repository HEAD for the launcher trust snapshot."
    }
    $identity = ($output -join "`n").Trim()
    if (-not $identity) {
        throw "Repository HEAD is empty in the launcher trust snapshot."
    }
    return $identity
}

function Get-LauncherProtectedFiles {
    param(
        [switch]$Preliminary,
        [string]$Root = $PSScriptRoot
    )

    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $directories = [System.Collections.Generic.Queue[System.IO.DirectoryInfo]]::new()
    $directories.Enqueue([System.IO.DirectoryInfo]::new($rootPath))
    $files = @{}
    while ($directories.Count -gt 0) {
        $directory = $directories.Dequeue()
        foreach (
            $entry in Get-ChildItem -LiteralPath $directory.FullName -Force `
                -ErrorAction Stop
        ) {
            $relative = ConvertTo-RepositoryRelativePath `
                -Path $entry.FullName -Root $rootPath
            if (Test-LauncherSnapshotExcludedPath -Path $relative) {
                continue
            }
            $key = $relative.ToLowerInvariant()
            if ($entry.PSIsContainer) {
                if ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                    $target = @($entry.Target) -join "|"
                    $files[$key] = "link|$($entry.LinkType)|$target"
                    continue
                }
                $directories.Enqueue($entry)
                continue
            }
            if (Test-PIWritablePath -Path $relative -Preliminary:$Preliminary) {
                continue
            }
            if ($entry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
                $target = @($entry.Target) -join "|"
                $files[$key] = "link|$($entry.LinkType)|$target"
                continue
            }
            $hash = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash
            $files[$key] = "file|$hash"
        }
    }
    return $files
}

function New-PITrustSnapshot {
    param(
        [switch]$Preliminary,
        [string]$Root = $PSScriptRoot,
        [string]$HarnessRoot
    )

    return [pscustomobject]@{
        Head = Get-LauncherHeadIdentity -Root $Root
        Files = Get-LauncherProtectedFiles -Root $Root -Preliminary:$Preliminary
        Preliminary = [bool]$Preliminary
        HarnessRoot = $HarnessRoot
        HarnessSnapshot = if ($HarnessRoot -and $HarnessRoot -ne $Root) {
            New-PITrustSnapshot -Root $HarnessRoot -Preliminary:$Preliminary
        } else { $null }
    }
}

function Assert-PITrustSnapshot {
    param(
        [Parameter(Mandatory)]$Snapshot,
        [string]$Root = $PSScriptRoot
    )

    if ($Snapshot.HarnessSnapshot) {
        Assert-PITrustSnapshot -Snapshot $Snapshot.HarnessSnapshot -Root $Snapshot.HarnessRoot
    }
    $violations = [System.Collections.Generic.List[string]]::new()
    $head = Get-LauncherHeadIdentity -Root $Root
    if ($head -ne $Snapshot.Head) {
        $violations.Add("HEAD")
    }

    $current = Get-LauncherProtectedFiles -Root $Root `
        -Preliminary:$([bool]$Snapshot.Preliminary)
    foreach ($relative in $current.Keys) {
        if (
            -not $Snapshot.Files.ContainsKey($relative) -or
            $current[$relative] -ne $Snapshot.Files[$relative]
        ) {
            $violations.Add([string]$relative)
        }
    }
    foreach ($relative in $Snapshot.Files.Keys) {
        if (-not $current.ContainsKey($relative)) {
            $violations.Add([string]$relative)
        }
    }
    if ($violations.Count -gt 0) {
        $paths = @($violations | Sort-Object -Unique)
        throw (
            "PI work changed repository content outside the PI-owned paths " +
            "in contracts/authority.md: $($paths -join ', '). Refusing to load " +
            "mutable Runner or adapter code."
        )
    }
}
