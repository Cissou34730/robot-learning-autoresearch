# Observation of a bounded Researcher session, as three independent facts: the
# process outcome, the presence of the deliverable it was asked to produce, and
# that deliverable's validity. Nothing here reads what the Researcher printed,
# so it stays true whatever command invokes the Researcher.

function Write-Status {
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
    $exitText = if ($null -eq $Status.ExitCode) {
        "unavailable"
    }
    else {
        [string]$Status.ExitCode
    }
    if ($Status.Complete -and $exitText -eq "0") {
        # A completed phase still reports as one line, but the line says which
        # phase it closes so it is not read as a stray status message.
        Write-Status (
            "Researcher phase closed: $($Status.Phase), attempt $($Status.Attempt), " +
            "process=$exitText, $($Status.Deliverable)=$($Status.Validity)"
        ) Green
        return
    }
    $presence = if ($Status.Present) { "present" } else { "missing" }
    Write-Status "=== Researcher session - $($Status.Phase) - attempt $($Status.Attempt) ===" Yellow
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

function Test-LauncherSnapshotExcludedPath {
    param([Parameter(Mandatory)][string]$Path)

    $relative = ($Path -replace '\\', '/').TrimStart('/').ToLowerInvariant()
    $parts = @($relative.Split('/', [System.StringSplitOptions]::RemoveEmptyEntries))
    $excludedDirectories = @(
        ".git",
        ".copilot",
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
        "research/research_state.json",
        "research/results.jsonl",
        "research/experiments.md",
        "research/goal_reached",
        "research/recovery_pending",
        "research/restart_pending",
        "research/brief.md",
        "research/last_train_summary.md",
        "research/last_evaluation.json"
    )) {
        return $true
    }
    return (
        $relative.StartsWith("research/training_logs/") -or
        $relative.StartsWith("research/evaluations/") -or
        $relative.StartsWith("research/checkpoints/candidates/") -or
        $relative.StartsWith("research/checkpoints/retained/") -or
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
        foreach ($entry in Get-ChildItem -LiteralPath $directory.FullName -Force) {
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
        [string]$Root = $PSScriptRoot
    )

    return [pscustomobject]@{
        Head = Get-LauncherHeadIdentity -Root $Root
        Files = Get-LauncherProtectedFiles -Root $Root -Preliminary:$Preliminary
        Preliminary = [bool]$Preliminary
    }
}

function Assert-PITrustSnapshot {
    param(
        [Parameter(Mandatory)]$Snapshot,
        [string]$Root = $PSScriptRoot
    )

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
            "PI work changed repository content outside the AGENTS.md scientific " +
            "surface: $($paths -join ', '). Refusing to load mutable Runner or " +
            "adapter code."
        )
    }
}
