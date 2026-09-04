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

### Researcher runtime

The researcher runs on the GitHub Copilot SDK through `researcher_copilot.py`,
using your own GitHub Copilot entitlement. Prepare it once:

```powershell
uv sync
uv run --group researcher python -m copilot download-runtime
```

Sign in once with the Copilot CLI if you have never done so; the SDK reuses
those credentials. Model and reasoning effort stay launch-time choices:

```powershell
.\run_research.ps1 -Model gpt-5.6-luna -Reasoning high
```

An unavailable model is reported with the list of available ones rather than
silently replaced. The adapter streams the researcher's answer, prints one line
per changed file and per shell command, and stays quiet about reads and
searches. It reports what a session did; whether a phase is complete remains a
property of the deliverable and its protected validator.

Stop the campaign, then choose a reset mode explicitly in the current branch:

```powershell
.\reset_research.ps1 -Mode Fresh -Force
.\reset_research.ps1 -Mode Baseline -BaselineRef <prepared-baseline-commit-or-tag> -Force
```

`Fresh` clears campaign history and models, preserving the current code and
parameters; baseline training starts on the next launch. `Baseline` restores
the prepared baseline's scientific code, tests, configuration, saved policy and
evidence, preserving the current harness; research resumes at experiment 2
without retraining the baseline. Neither mode creates a branch or worktree.

Both require a clean Git working tree and commit/push the resulting reset state,
as before. See [reset details and baseline requirements](docs/reset-research.md).

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
