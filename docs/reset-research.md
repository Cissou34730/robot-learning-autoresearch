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
schema-6 research history with a new campaign identity, a pending scientific
model, and no working or best-known candidate. This is not a restore from main
or from historical scientific code.

## Baseline

```powershell
.\reset_research.ps1 -Mode Baseline -BaselineRef <commit-or-tag> -Force
```

The Git reference must contain one prepared schema-6 candidate designated as
both working and best-known, with a ready scientific model and at least one
committed evaluation artifact. Keep a reference to that prepared state to
repeat comparisons.

Restores:

- the candidate's scientific recipe, limited to the researcher-owned scientific
  surface and `research/current_params.json`;
- the candidate inference artifact, including `policy_runtime.pkl`, from
  `research/checkpoints/candidates/` or `research/checkpoints/retained/`;
- committed candidate evaluation evidence under `research/evaluations/`;
- the scientific model used by the prepared source.

Preserves the current harness, protocol, instrument catalog, protected runtime,
protected evaluators/adapters, and human-owned tests. The robot assets and task
constants must match the baseline; a mismatch is refused before any cleanup.
The mode does not restore the entire `robot_learning` directory. Every source
artifact and restore target is validated before backup creation or cleanup;
protected, out-of-scope, misplaced checkpoint, and misplaced evaluation paths
are refused.

Legacy checkpoints without the executable runtime are refused. Prepare a
compatible baseline explicitly; see [policy migration](policy-runtime.md).
The reset checks baseline structure and required files, not policy performance;
normal runtime integrity checks still apply when a saved policy is loaded.

## Recovery

Every reset records its original HEAD, exact target manifest, pre-reset content
hashes, and commit/push progress under Git's administrative directory. If a
reset fails after backup creation, its error prints the exact recovery command:

```powershell
.\reset_research.ps1 -Recover <operation.json> -Force
```

Recovery validates that the operation belongs to the current repository and
worktree, verifies every backup hash, and restores only the recorded paths. If
the reset created a commit, recovery publishes an explicit rollback commit; it
never rewrites history or force-pushes. If publication is unavailable, the
rollback remains as a clean local commit and the command reports its hash. The
same recovery operation can be invoked again safely.

## Safety and Git

Both modes refuse dirty tracked/untracked files, detached HEAD and a missing
origin. Commit or resolve development edits first; `-Force` does not bypass
these checks. Existing file locks and linked cleanup targets are checked before
deletion. This is not a concurrency lock: keep the campaign stopped.

As with the previous reset script, a successful reset creates a commit and
pushes it to origin. A push failure leaves the local commit intact and reports
the failure; no force-push or history rewriting is performed. If the desired
state already matches Git, no redundant commit is created.

Versioned and ignored reset targets are included in the validated recovery
backup. The reset reports the backup location after success and an executable
recovery command after failure.
