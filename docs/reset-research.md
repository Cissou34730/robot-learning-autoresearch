# Reset in the current branch

Stop the campaign before resetting. `reset_research.ps1` requires both an
explicit `-Mode` and `-Force`; there is no default mode. It never creates a
branch or worktree, starts training, or changes the research loop.

## Fresh

```powershell
.\reset_research.ps1 -Mode Fresh -Force
```

Preserves the current code, parameters, tests, task and protocol decision log.
Removes campaign checkpoints, disposable candidates, evaluation artifacts,
training logs, stale requests and generated summaries. Initializes empty
research history with a new campaign identity and `BASELINE_PENDING`.
The next normal launch trains the baseline. This is not a restore from main
or from historical scientific code.

## Baseline

```powershell
.\reset_research.ps1 -Mode Baseline -BaselineRef <commit-or-tag> -Force
```

The Git reference must contain a completed, measured, closed experiment 1,
before experiment 2, with no pending operations, retained alternatives or final
benchmark result. Keep a reference to that prepared state to repeat comparisons.

Restores:

- researcher-owned scenario and training files, application entry points and
  their scientific tests, including removal of files absent from the baseline;
- scenario description and parameters;
- the accepted policy and all its associated files, including `policy_runtime.pkl`;
- baseline research state, history, postmortem, detailed evaluations and raw
  experiment-1 training logs.

Preserves the current harness, protocol, instrument catalog, protected runtime,
protected evaluators/adapters, and human-owned tests. The robot assets and task
constants must match the baseline; a mismatch is refused before any cleanup.
The mode does not restore the entire `robot_learning` directory.

The baseline campaign identity and its evidence stay together. Later campaign
data and pending controls are removed. The next launch starts experiment 2,
not another baseline training. Generated briefs are rebuilt by the launcher.

Legacy checkpoints without the executable runtime are refused. Prepare a
compatible baseline explicitly; see [policy migration](policy-runtime.md).
The reset checks baseline structure and required files, not policy performance;
normal runtime integrity checks still apply when a saved policy is loaded.

If the baseline's logs are not versioned, they must still exist under
`research/training_logs/<baseline-campaign-id>/`. By default they are read from
the current worktree **before** cleanup. To read them from an existing backup:

```powershell
.\reset_research.ps1 -Mode Baseline -BaselineRef <commit-or-tag> `
  -TrainingLogSource C:\path\to\saved-repository -Force
```

The logs are copied to temporary storage before cleanup and then versioned in
the reset commit. That resulting commit can serve as a self-contained prepared
baseline reference for subsequent resets. No new worktree is created.

## Safety and Git

Both modes refuse dirty tracked/untracked files, detached HEAD and a missing
origin. Commit or resolve development edits first; `-Force` does not bypass
these checks. Existing file locks and linked cleanup targets are checked before
deletion. This is not a concurrency lock: keep the campaign stopped.

As with the previous reset script, a successful reset creates a commit and
pushes it to origin. A push failure leaves the local commit intact and reports
the failure; no force-push or history rewriting is performed. If the desired
state already matches Git, no redundant commit is created.

Versioned files remain recoverable from Git. Removed ignored candidates,
requests and logs are not generally recoverable. Baseline logs copied to
temporary storage are retained there if an operation fails; the script prints
that location. The operation is not a transactional filesystem rollback.
