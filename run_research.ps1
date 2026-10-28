# Thin maintainer entry point. The campaign launcher is the Python module
# runner.launcher; pass its options (see `.\run_research.ps1 --help`), e.g.:
#   .\run_research.ps1 --campaign-root ..\robot-learning-campaigns\campaign-2
# Watch the campaign with campaign_tui.ps1.
& uv run --project $PSScriptRoot --group researcher python -m runner.launcher @args
exit $LASTEXITCODE
