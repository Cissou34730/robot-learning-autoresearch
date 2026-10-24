# Starts the read-only autoresearch campaign report.
#
# The report never writes into the campaign; it only reads durable state,
# results and usage of the selected campaign root. Runner/PI launch behavior
# is untouched: run your campaign as before, then open this report beside it.
#
# Usage:
#   .\tools\run-report.ps1                     # default sibling campaign root
#   .\tools\run-report.ps1 -CampaignRoot D:\path\to\campaign
#   .\tools\run-report.ps1 -EventsPath D:\path\to\tui_observations.jsonl
#   .\tools\run-report.ps1 -Demo
[CmdletBinding()]
param(
    [string]$CampaignRoot = "",
    [string]$EventsPath = "",
    [switch]$Demo,
    [switch]$Light
)

$productRoot = Split-Path -Parent $PSScriptRoot

if (-not $CampaignRoot) {
    $sibling = Join-Path (Split-Path -Parent $productRoot) "robot-learning-campaigns"
    if (Test-Path $sibling) { $CampaignRoot = $sibling }
}

if (-not $CampaignRoot) {
    throw "No campaign root found. Pass -CampaignRoot or create the sibling robot-learning-campaigns folder."
}
if (-not (Test-Path -LiteralPath $CampaignRoot)) {
    throw "Campaign root does not exist: $CampaignRoot"
}

Write-Host "Campaign root: $CampaignRoot"

$arguments = @()
if ($CampaignRoot) { $arguments += @("--campaign-root", $CampaignRoot) }
if ($EventsPath) { $arguments += @("--events", $EventsPath) }
if ($Demo) { $arguments += "--demo" }
if ($Light) { $arguments += "--light" }

Push-Location $productRoot
try {
    & uv run python -m tui @arguments
}
finally {
    Pop-Location
}
