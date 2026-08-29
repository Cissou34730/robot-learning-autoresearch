# Robot Learning Autoresearch

The human-defined goal is to reach a random target 6-20 cm away, remain within
1 cm for 2 seconds, and achieve at least 98% success over 200 official
evaluation episodes. The authoritative values live in
`robot_learning/benchmark/final_contract.py`; routine research settings cannot
redefine an official result.

The researcher owns the scientific decisions: learning method, checkpoints to
measure, evaluation plan, analysis, retained model lineages, and model/code
lineage. The runner only executes and records those decisions. It does not
automatically rank candidates, run a tournament, promote a model, or apply a
statistical gate.

Start the autonomous loop from PowerShell:

```powershell
.\run_research.ps1
```

The first run after an infrastructure change is an automatic unchanged
baseline. Training saves neutral checkpoints; the researcher subsequently asks
for the measurements that are useful to interpret them.

To discard all experimental history and model lineages while preserving the
current code, benchmark, parameters, and decision log, run:

```powershell
.\reset_research.ps1 -Force
```

The reset refuses to run if the Git working tree is not clean and commits the
new blank research state before preparing a fresh baseline.
