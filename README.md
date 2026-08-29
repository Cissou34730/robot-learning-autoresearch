# Robot Learning Autoresearch

The human-defined goal is to reach a random target 6-20 cm away, remain within
1 cm for 2 seconds, and achieve at least 98% success over 200 official
evaluation episodes. The authoritative values and execution live in
`robot_learning/benchmark/final_contract.py` and
`robot_learning/benchmark/final_benchmark.py`; routine research settings cannot
redefine an official result. The training environment may evolve through research
without changing the human-owned final benchmark.

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

## Tests and validation

The runner is the execution component implemented by
`research/run_experiment.py` and launched by `run_research.ps1`. It executes and
records decisions; it never authors or modifies tests or learning code.

Tests are organized by repository domain:

| Directory | Covers | Owner |
| --- | --- | --- |
| `tests/benchmark/` | official task, official robot, benchmark contract, final goal verdict | human |
| `tests/autoresearch/` | the generic AutoResearch harness: proposals, execution lifecycle, persistence, lineage, protected paths, presentation, training-artifact contract | human |
| `tests/scenario/` | training environment, reward, observations, research evaluation | researcher |
| `tests/training/` | the currently active learning method and its configuration | researcher |

`tests/benchmark/` and `tests/autoresearch/` are immutable for the duration of a
campaign: a proposal that creates, modifies, renames or deletes a file under
either prefix is rejected before training. They also stay method-neutral, so
replacing the learning algorithm never requires touching them.

`tests/scenario/` and `tests/training/` belong to the researcher. Changes there
are ordinary research code: they appear in the experiment's `code_changes` and
follow the same Git code lineage as the implementation they validate. A
structural experiment is expected to update them; a parameter-only experiment
is not.

Validation runs before compute is spent:

* a fresh campaign baseline is fully validated even when the worktree carries no
  uncommitted change, so an inconsistent starting point cannot consume training;
* an experiment with code changes is fully validated before training;
* a parameter-only experiment validates the proposal and the effective
  configuration only;
* a continuation, evaluation or lineage decision without code changes reruns
  nothing.

Complete validation checks the syntax of changed Python files and runs
`ruff check` on them, parses changed JSON documents, verifies dependency
metadata against `uv.lock` with a non-mutating check when either changed, and
then runs:

```powershell
uv run pytest -q tests/benchmark tests/autoresearch tests/scenario tests/training
```
