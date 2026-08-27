# Robot Learning Autoresearch

The robot advances through a persistent reach-and-hold curriculum. Every
experiment trains a copy of the currently accepted checkpoint. The candidate is
promoted only when held-out current-stage success improves without regressing on
earlier stages.

Start the autonomous loop from PowerShell:

```powershell
.\run_research.ps1
```

The first run after an infrastructure change is an automatic unchanged
baseline. Validated checkpoints are small and versioned under
`research/checkpoints/`; disposable candidates remain under `models/`.
