# Maintainer utility and the standard way to run campaigns: run 1 to 5 campaign
# repositories in parallel on the current harness. Campaign repositories live
# under one root (default: sibling robot-learning-campaigns\campaign-1 .. -5);
# missing ones are initialized from an existing one. Resets each folder to the
# recipe, launches each launcher detached in its own window, then starts a
# detached monitor that stops a campaign cooperatively at an active-time or AIU
# cap and writes one report per campaign when all have ended. Caps act only
# through each launcher's -StopRequestPath; campaign agents never see them.
#
# Usage:
#   .\tools\run_parallel.ps1 -Count 3
#   .\tools\run_parallel.ps1 -Count 1 -MaxHours 4 -MaxAiu 80
#   .\tools\run_parallel.ps1 -CampaignRoots C:\a,C:\b -NoReset
[CmdletBinding(DefaultParameterSetName = "Count")]
param(
    [Parameter(Mandatory, ParameterSetName = "Count")][ValidateRange(1, 5)][int]$Count,
    [Parameter(ParameterSetName = "Count")]
    [string]$CampaignsRoot = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "robot-learning-campaigns"),
    [Parameter(Mandatory, ParameterSetName = "Roots")]
    [Parameter(Mandatory, ParameterSetName = "Monitor")][string[]]$CampaignRoots,
    [string]$RecipeRef = "baseline-distinct-episodes-v3-robot",
    [double]$MaxHours = 6,
    [double]$MaxAiu = 120,
    [string]$Provider = "github-copilot",
    [int]$PollSeconds = 60,
    [switch]$NoReset,
    [string]$ControlDirectory,
    [Parameter(Mandatory, ParameterSetName = "Monitor")][switch]$Monitor
)

$ErrorActionPreference = "Stop"
$harness = Split-Path -Parent $PSScriptRoot
. (Join-Path $harness "researcher_mutex.ps1")

function Get-CampaignAiu {
    param([string]$Root)
    $state = Get-Content (Join-Path $Root "runner\state\research_state.json") -Raw |
        ConvertFrom-Json
    $usage = Join-Path $Root "reports\session_usage\$($state.campaign.id).jsonl"
    if (-not (Test-Path $usage)) { return 0.0 }
    $total = 0.0
    foreach ($line in Get-Content $usage) {
        if (-not $line.Trim()) { continue }
        $row = $line | ConvertFrom-Json
        if ($null -ne $row.aiu) { $total += [double]$row.aiu }
    }
    return $total
}

function Test-LauncherRunning {
    param([string]$MutexName)
    $mutex = $null
    if ([System.Threading.Mutex]::TryOpenExisting($MutexName, [ref]$mutex)) {
        $mutex.Dispose()
        return $true
    }
    return $false
}

function Write-Event {
    param([string]$Text)
    $line = "{0:u} {1}" -f [DateTime]::UtcNow, $Text
    Write-Host $line
    Add-Content -Path (Join-Path $ControlDirectory "monitor.log") -Value $line
}

if ($Monitor) {
    # Lid closing can still force sleep; only the gaps it creates are excluded from active time.
    Add-Type -Namespace Native -Name Power -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetThreadExecutionState(uint flags);
'@
    [void][Native.Power]::SetThreadExecutionState([uint32]"0x80000001")
    $runs = foreach ($root in $CampaignRoots) {
        [pscustomobject]@{
            Root = $root
            Mutex = Get-WorktreeMutexName -Worktree $root
            Stop = Join-Path $ControlDirectory "$(Split-Path -Leaf $root).stop"
            Started = [DateTime]::UtcNow
            ActiveSeconds = 0.0
            Stopped = $null
            Finished = $false
        }
    }
    $last = [DateTime]::UtcNow
    while (@($runs | Where-Object { -not $_.Finished }).Count) {
        Start-Sleep -Seconds $PollSeconds
        $now = [DateTime]::UtcNow
        $gap = ($now - $last).TotalSeconds
        $last = $now
        if ($gap -gt 3 * $PollSeconds) {
            Write-Event ("paused {0:N0} s (sleep); not counted as active time" -f $gap)
            $gap = 0
        }
        foreach ($run in $runs | Where-Object { -not $_.Finished }) {
            $run.ActiveSeconds += $gap
            if (
                ($now - $run.Started).TotalSeconds -gt 120 -and
                -not (Test-LauncherRunning -MutexName $run.Mutex)
            ) {
                $run.Finished = $true
                Write-Event "launcher exited $($run.Root)"
                continue
            }
            if ($run.Stopped) { continue }
            try { $aiu = Get-CampaignAiu -Root $run.Root } catch { continue }
            $hours = $run.ActiveSeconds / 3600
            $reason = if ($hours -ge $MaxHours) { "active time {0:N2} h" -f $hours }
                elseif ($aiu -ge $MaxAiu) { "AIU {0:N1}" -f $aiu }
            if ($reason) {
                try {
                    [System.IO.File]::Open(
                        $run.Stop, [System.IO.FileMode]::CreateNew,
                        [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read
                    ).Dispose()
                } catch [System.IO.IOException] { }
                $run.Stopped = $reason
                Write-Event "stop $($run.Root): $reason"
            }
        }
    }
    $reports = Join-Path $ControlDirectory "reports"
    New-Item -ItemType Directory -Force -Path $reports | Out-Null
    Push-Location $harness
    try {
        foreach ($run in $runs) {
            try {
                $id = (Get-Content (Join-Path $run.Root "runner\state\research_state.json") -Raw |
                    ConvertFrom-Json).campaign.id.Substring(0, 8)
                $output = Join-Path $reports "$(Split-Path -Leaf $run.Root)-$id.html"
                & uv run python tools/campaign_report.py --repo $run.Root --output $output
                Write-Event "report $($run.Root): exit $LASTEXITCODE"
            }
            catch {
                Write-Event "report $($run.Root): $($_.Exception.Message)"
            }
        }
    }
    finally {
        Pop-Location
    }
    Write-Event "all campaigns ended"
    return
}

if ($PSCmdlet.ParameterSetName -eq "Count") {
    $existing = @(1..5 | ForEach-Object { Join-Path $CampaignsRoot "campaign-$_" } |
        Where-Object { Test-Path (Join-Path $_ ".git") })
    if (-not $existing) {
        throw "No campaign repository under $CampaignsRoot. Initialize campaign-1 with tools.initialize_campaign first."
    }
    $CampaignRoots = foreach ($index in 1..$Count) {
        $root = Join-Path $CampaignsRoot "campaign-$index"
        if (-not (Test-Path $root)) {
            # Git refuses folders it considers owned by another account unless listed here.
            $safe = $root.Replace("\", "/")
            if (-not (@(git config --global --get-all safe.directory) -contains $safe)) {
                git config --global --add safe.directory $safe
            }
            Push-Location $harness
            try {
                & uv run python -m tools.initialize_campaign --campaign-root $root `
                    --source-repository $existing[0] --recipe-ref $RecipeRef
                if ($LASTEXITCODE) { throw "Initialization failed for $root." }
            }
            finally {
                Pop-Location
            }
        }
        $root
    }
}
$roots = @($CampaignRoots | ForEach-Object { (Resolve-Path $_).ProviderPath })
if (@(git -C $harness status --porcelain --untracked-files=all).Count) {
    throw "The harness worktree has uncommitted changes; the launchers would refuse to start."
}
foreach ($root in $roots) {
    if (Test-LauncherRunning -MutexName (Get-WorktreeMutexName -Worktree $root)) {
        throw "A launcher already owns $root."
    }
}
if (-not $NoReset) {
    foreach ($root in $roots) {
        $global:LASTEXITCODE = 0
        & (Join-Path $harness "reset_research.ps1") -CampaignRoot $root -Mode Fresh `
            -Clean -RecipeRef $RecipeRef -Force
        if ($LASTEXITCODE) { throw "Reset failed for $root." }
    }
}

if (-not $ControlDirectory) {
    $ControlDirectory = Join-Path $env:TEMP (
        "robot-learning\parallel-" + [DateTime]::UtcNow.ToString("yyyyMMddTHHmmss")
    )
}
New-Item -ItemType Directory -Force -Path $ControlDirectory | Out-Null
# Detached PowerShell processes do not inherit this terminal's PATH additions (git, uv).
$pathFile = Join-Path $ControlDirectory "path.txt"
[System.IO.File]::WriteAllText($pathFile, $env:PATH)
Remove-Item Env:TUI_OBSERVATIONS, Env:TUI_TYPED_EVENTS -ErrorAction SilentlyContinue

foreach ($root in $roots) {
    $name = Split-Path -Leaf $root
    $command = (
        "`$env:PATH = Get-Content -Raw '$pathFile'; " +
        "Start-Transcript -Path '$(Join-Path $ControlDirectory "$name.log")' -Force; " +
        "& '$(Join-Path $harness "run_research.ps1")' -CampaignRoot '$root' " +
        "-Provider $Provider -StopRequestPath '$(Join-Path $ControlDirectory "$name.stop")'; " +
        "Stop-Transcript"
    )
    $process = Start-Process pwsh -WorkingDirectory $harness -PassThru -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $command
    )
    Write-Host ("{0:u} started {1} (pid {2})" -f [DateTime]::UtcNow, $root, $process.Id)
    Start-Sleep -Seconds 5
}

$monitorCommand = (
    "`$env:PATH = Get-Content -Raw '$pathFile'; " +
    "& '$PSCommandPath' -Monitor -ControlDirectory '$ControlDirectory' " +
    "-CampaignRoots '$($roots -join "','")' -MaxHours $MaxHours -MaxAiu $MaxAiu " +
    "-PollSeconds $PollSeconds"
)
$monitorProcess = Start-Process pwsh -WindowStyle Minimized -WorkingDirectory $harness -PassThru `
    -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $monitorCommand)
Write-Host "Monitor pid $($monitorProcess.Id). Control folder: $ControlDirectory"
Write-Host "Caps per campaign: $MaxHours h active time, $MaxAiu AIU."
