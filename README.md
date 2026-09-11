# Robot Learning Autoresearch

The human-defined goal is to reach a random target 6-20 cm away, remain within
1 cm for 2 seconds, and achieve at least 98% success over 200 official
evaluation episodes. The authoritative values and execution live in
`robot_learning/benchmark/final_contract.py` and
`robot_learning/benchmark/final_benchmark.py`; routine research settings cannot
redefine an official result. The training environment may evolve through research
without changing the human-owned final benchmark.

The researcher owns the scientific decisions: learning method, checkpoints to
measure, post-training analysis, retained model lineages, and model/code lineage.
Training leads to analysis, which can request one or more development-measurement
rounds or close directly from logs and existing evidence. A closure chooses a
working lineage and may independently designate an evidence-backed best-known
model; continuing a promising working lineage does not make it best known. The
runner only executes and records those decisions. It does not automatically rank
candidates, run a tournament, promote a model, or apply a statistical gate.
Preparation may continue an unchanged lineage, train an intervention from fresh
or transferred initialization, or replicate an earlier operation. Code and
configuration edits are needed only when the chosen operation calls for them.
Repeated use of one development panel remains evidence from that panel, not
independent held-out confirmation.

Start the autonomous loop from PowerShell:

```powershell
.\run_research.ps1
```

The first run after an infrastructure change is an automatic unchanged baseline.
Training saves neutral checkpoints; the researcher then analyzes logs and
artifacts before deciding whether any development measurements are useful.

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
.\reset_research.ps1 -Mode Fresh -RecipeRef <verified-recipe-commit> -Force
.\reset_research.ps1 -Mode Baseline -BaselineRef <prepared-baseline-commit-or-tag> -Force
```

`Fresh` clears campaign history and models, preserving the current code and
parameters; baseline training starts on the next launch. With `-RecipeRef`, it
first restores the complete researcher-owned scientific code, tests and
configuration from the resolved commit, including deleting later scientific
files. It does not import a model, score, evidence, strategy, campaign identity
or experiment counter. `Baseline` restores the prepared baseline's scientific
code, tests, configuration, saved policy and evidence, preserving the current
harness; research resumes at experiment 2 without retraining the baseline.
Neither mode creates a branch or worktree.

Both require a clean Git working tree and hold the same machine-wide mutex as
the research launcher. A recipe reset commits restored science separately from
the new empty campaign state; all reset commits are pushed without rewriting
history. Recovery backups are stored through Git's resolved administrative path,
so reset works from both primary checkouts and linked worktrees. See
[reset details and baseline requirements](docs/reset-research.md).
Failed resets print a supported `-Recover <operation.json> -Force` command that
restores the exact recorded targets and publishes a rollback when required.

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

Selected version-4 working and best-known policies are published under
`research/checkpoints/retained/<campaign-id>/` before disposable challengers are
cleaned up. Their model, metadata and saved preprocessing runtime are versioned
with the campaign memory, so a clean clone can load every lineage named by
state. Working and best-known remain independent Researcher decisions; the
runner does not infer either role from a score.

Validation runs before compute is spent:

* a fresh campaign baseline is fully validated even when the worktree carries no
  uncommitted change, so an inconsistent starting point cannot consume training;
* an experiment with code changes is fully validated before training;
* a parameter-only experiment validates the proposal and the effective
  configuration only;
* a continuation, evaluation or lineage decision without code changes runs no
  validation suite.

Complete validation checks the syntax of changed Python files and runs
`ruff check` on them, parses changed JSON documents, verifies dependency
metadata against `uv.lock` with a non-mutating check when either changed, and
then runs:

```powershell
uv run pytest -q tests/benchmark tests/autoresearch tests/scenario tests/training
```

Harness regression coverage does not broaden campaign-time selection: ordinary
reward and parameter changes still run only the suites selected by the existing
ownership rules above.
