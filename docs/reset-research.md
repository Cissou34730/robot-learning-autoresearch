# Reset the local campaign repository

Stop the campaign before resetting. `reset_research.ps1` requires both an
explicit `-Mode` and `-Force`; there is no default mode. It never creates a
branch or worktree, starts training, or changes the research loop.

Run the script from the harness repository. `-CampaignRoot <path>` selects an
independent campaign repository; the default is
`robot-learning-campaigns\campaign-1` beside the harness. Resets change and commit files only in that
campaign repository. They do not reset or copy the harness.
The reset script restores the calling terminal's original folder on success
or failure, so it can be followed by a relative launcher command:

```powershell
.\reset_research.ps1 -Mode Fresh -Clean -RecipeRef baseline-distinct-episodes-v3-robot -Force ; .\run_research.ps1
```

`-Clean` discards eligible uncommitted campaign changes before reset; it does
not bypass ownership checks. Do not use it just to resume a stopped campaign.
The semicolon separates commands; it is not a success-only condition. If reset
fails, inspect that failure before authorizing launch.

References resolve in campaign Git. Initialize a new campaign repository once
with `tools.initialize_campaign` and its required destination/source arguments;
see the [complete setup command](../README.md#initialize-a-campaign-repository-once).
Imported recipes carry a versioned task contract so incompatible robot/task
definitions are refused before cleanup.

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

To restore the baseline v3 scientific recipe as well:

```powershell
.\reset_research.ps1 -Mode Fresh -RecipeRef baseline-distinct-episodes-v3-robot -Force
```

This tag is a recipe, not a prepared trained model, so use Fresh rather than
Baseline mode. It lives in the campaign repository after initialization. The
scientific model starts pending and is prepared on the next authorized launch.

## Baseline

```powershell
.\reset_research.ps1 -Mode Baseline -BaselineRef <commit-or-tag> -Force
```

The Git reference must contain one prepared schema-6 candidate designated as
both working and best-known, with a ready scientific model. Completed
measurement records for its evaluation artifacts must exist in that reference
or retained versioned schema-6 state references. The lookup matches the exact
selected candidate and artifact paths and does not accept other schemas.
This permits reuse of an imported
baseline whose new campaign starts with empty operation history.
Those raw artifacts must
also exist in the local archive and match their recorded fingerprints.
Keep both the prepared Git reference and local archive to repeat comparisons.
A Git-only checkout cannot supply raw measurement data.

Restores:

- the candidate's scientific recipe, limited to the researcher-owned scientific
  surface and `robot_learning/training/current_params.json`;
- the candidate inference artifact, including `policy_runtime.pkl`, from
  `campaigns/checkpoints/candidates/` or `campaigns/checkpoints/retained/`;
- candidate evaluation evidence from the validated local archive under
  `campaigns/evaluations/`. Git does not track these files, so the reset holds
  them in a temporary folder while it clears the campaign, then deletes that
  folder;
- the scientific model used by the prepared source.

Preserves the current harness, protocol, instrument catalog, protected runtime,
protected evaluators/adapters, and human-owned tests. The robot assets and task
constants must match the baseline; a mismatch is refused before any cleanup.
The mode does not restore the entire `robot_learning` directory. Every source
artifact and restore target is validated before cleanup;
protected, out-of-scope, misplaced checkpoint, and misplaced evaluation paths
are refused.

Legacy checkpoints without the executable runtime are refused. Prepare a
compatible baseline explicitly; see [policy migration](policy-runtime.md).
The reset checks baseline structure and required files, not policy performance;
normal runtime integrity checks still apply when a saved policy is loaded.

## Failure

No separate reset backup is kept. Campaign state is versioned in Git, so a
failed reset reports the commit it started from. Use Git to return to that
commit if required. Ignored local measurement files outside the restored
baseline are not recoverable after cleanup.

## Safety and Git

Both modes refuse dirty tracked/untracked files and detached HEAD.
An independent campaign repository does not need an origin remote.
Commit or resolve development edits first; `-Force` does not bypass
these checks. Existing file locks and linked cleanup targets are checked before
deletion. The script also holds the same per-campaign mutex as the launcher,
but keep the campaign stopped before requesting reset.

A successful reset creates local campaign commits and never pushes in split
mode, even if a remote was added accidentally. Harness commits are published
separately by the maintainer. Legacy single-folder mode retains its origin
publication behavior. If the desired state already matches Git, no redundant
commit is created.

Raw measurements remain local and ignored during reset publication. Reset never
force-adds `campaigns/evaluations/` to Git.
