# Starts the autoresearch operator console (or the read-only article report).
#
# Default: the multi-campaign console (issue #68). It shows one tab per
# installed campaign folder plus a Commands tab; campaigns only run when a
# command is submitted, and Ctrl+Q stops the console-owned campaigns.
#
# Legacy single-campaign report options (-CampaignRoot/-EventsPath/-Demo)
# open the read-only report exactly as before; it never writes into the
# campaign and only reads durable state, results and usage.
#
# Usage:
#   .\tools\run-report.ps1                     # console (commands + campaigns)
#   .\tools\run-report.ps1 -Console            # console explicitly
#   .\tools\run-report.ps1 -CampaignRoot D:\path\to\campaign   # legacy report
#   .\tools\run-report.ps1 -EventsPath D:\path\to\tui_observations.jsonl
#   .\tools\run-report.ps1 -Demo
[CmdletBinding()]
param(
    [string]$CampaignRoot = "",
    [string]$EventsPath = "",
    [switch]$Demo,
    [switch]$Console,
    [switch]$ReadOnly,
    [switch]$Light
)

$productRoot = Split-Path -Parent $PSScriptRoot

$arguments = @()
if ($Console -or (-not $CampaignRoot -and -not $EventsPath -and -not $Demo -and -not $ReadOnly)) {
    # Console mode discovers every installed campaign folder beside the harness.
    if ($Light) { $arguments += "--light" }
    Push-Location $productRoot
    try {
        & uv run python -m tui @arguments
    }
    finally {
        Pop-Location
    }
    return
}

if (-not $CampaignRoot -and -not $Demo) {
    $sibling = Join-Path (Split-Path -Parent $productRoot) "robot-learning-campaigns\campaign-1"
    if (Test-Path $sibling) { $CampaignRoot = $sibling }
}

if (-not $CampaignRoot -and -not $Demo) {
    throw "No campaign root found. Pass -CampaignRoot or create robot-learning-campaigns\campaign-1 beside the harness."
}
if ($CampaignRoot -and -not (Test-Path -LiteralPath $CampaignRoot)) {
    throw "Campaign root does not exist: $CampaignRoot"
}

Write-Host "Campaign root: $CampaignRoot"

if ($EventsPath) { $arguments += @("--events", $EventsPath) }
if ($CampaignRoot) { $arguments += @("--campaign-root", $CampaignRoot) }
if ($ReadOnly -or (-not $Demo -and -not $EventsPath)) { $arguments += "--read-only" }
if ($Demo) { $arguments += "--demo" }
if ($Light) { $arguments += "--light" }

Push-Location $productRoot
try {
    & uv run python -m tui @arguments
}
finally {
    Pop-Location
}
