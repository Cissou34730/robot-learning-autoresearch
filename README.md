# Robot Learning Autoresearch

The fixed goal is to reach a random target within 1 cm and hold for 2 seconds.
Every experiment changes the training method while the evaluator and 120,000-step
budget remain fixed. A candidate is kept only when its held-out score improves.

Start the autonomous loop from PowerShell:

```powershell
.\run_research.ps1
```

The first run after an infrastructure change is an automatic unchanged
baseline. Validated checkpoints are small and versioned under
`research/checkpoints/`; disposable candidates remain under `models/`.
