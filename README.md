# Robot Learning Autoresearch

The fixed goal is to reach a random target within 1 cm and hold for 2 seconds.
Every experiment tests one training hypothesis while the evaluator remains fixed.
Transfer runs receive 120,000 steps; fresh policies receive the runner-owned
cumulative budget already invested in the champion lineage so architecture and
algorithm changes are not structurally handicapped.
A candidate is promoted only by a significant paired improvement over the champion.

Start the autonomous loop from PowerShell:

```powershell
.\run_research.ps1
```

The first run after an infrastructure change is an automatic unchanged
baseline. Validated checkpoints are small and versioned under
`research/checkpoints/`; disposable candidates remain under `models/`.
