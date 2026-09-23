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

External controllers must use the run-scoped cooperative request plus a
kill-on-close Windows Job Object described in
[the external stop contract](docs/external-campaign-stop.md).

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

### Human campaign report

Generate a read-only Markdown report, optionally comparing another worktree:

```powershell
uv run python tools/campaign_report.py
uv run python tools/campaign_report.py --compare ..\robot-learning-reference-campaing-1 --output reports\comparison.md
```

The report exposes checkpoint selection and unmeasured proxy peaks,
initialization and parent rationales, repeated hypothesis families, cited prior
evidence, lineage/recipe decisions, development-panel reuse and final requests.
These are facts for reviewing bias evolution, not an automatic quality score.
It does not inspect live processes or run a model, Git or a Researcher session.
Use `--repo <path>` or `--campaign-id <id>` to select other existing records.
Detailed scientific judgments remain the Researcher's recorded assessments.

Each launcher invocation records only aggregate tokens (input/cache/output),
AIU, tool counts by name and duration, with campaign/experiment/phase metadata,
in `reports/session_usage/<campaign-id>.jsonl`. No messages, tool arguments or
file contents are saved. Failed and interrupted invocations record available
usage; missing SDK values are unavailable, not zero. Accounting failure warns
without invalidating the scientific deliverable. Retries record separate usage
deltas even when they resume the same session. Input includes cache reads, so
the report never adds cache reads twice. Historical sessions cannot be recovered
from console summaries; their consumption is explicitly missing.

`reports/` is ignored by Git and never injected into Researcher context. Reset
leaves these campaign-scoped human records intact; copy this directory alongside
the campaign records if reports must be portable to another worktree or machine.
Generated reports contain only persisted common fields and recorded scientific
text: no scenario-specific diagnostic interpretation or new causal conclusions.

Stop the campaign, then choose a reset mode explicitly in the current branch:

```powershell
.\reset_research.ps1 -Mode Fresh -Force
.\reset_research.ps1 -Mode Fresh -Clean -Force
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
With `-Clean`, reset first discards staged and unstaged changes to campaign
paths and deletes all non-ignored untracked files in this worktree. This
cleanup is irreversible and happens before the reset backup; unrelated
tracked changes still stop the reset. Without `-Clean`, any dirty worktree
stops the reset as before.

Both require a clean Git working tree after any requested cleanup and hold the
same mutex as the research launcher, scoped to the worktree so a second
checkout never blocks. A recipe
reset commits restored science separately from
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

`tests/benchmark/` and `tests/autoresearch/` are immutable for the duration of a
campaign: a proposal that creates, modifies, renames or deletes a file under
either prefix is rejected before training. They also stay method-neutral, so
replacing the learning algorithm never requires touching them.

Scientific experiments do not carry researcher-maintained pytest suites. The
Runner validates their changed Python and JSON directly and retains protected
human-owned boundary checks.

Selected version-4 working and best-known policies are published under
`research/checkpoints/retained/<campaign-id>/` before disposable challengers are
cleaned up. Their model, metadata and saved preprocessing runtime are versioned
with the campaign memory, so a clean clone can load every lineage named by
state. Working and best-known remain independent Researcher decisions; the
runner does not infer either role from a score.

Validation runs before compute is spent:

* a fresh campaign baseline is fully validated even when the worktree carries no
  uncommitted change, so an inconsistent starting point cannot consume training;
* an experiment with code changes receives source validation and protected
  boundary checks before training;
* a parameter-only experiment validates the proposal and the effective
  configuration only;
* a continuation, evaluation or lineage decision without code changes reruns
  nothing.

Complete validation checks the syntax of changed Python files and runs
`ruff check` on them, parses changed JSON documents, verifies dependency
metadata against `uv.lock` with a non-mutating check when either changed, and
then runs:

```powershell
uv run pytest -q tests/benchmark tests/autoresearch
```

Harness regression coverage does not broaden campaign-time selection: ordinary
reward and parameter changes still run only the suites selected by the existing
ownership rules above.
