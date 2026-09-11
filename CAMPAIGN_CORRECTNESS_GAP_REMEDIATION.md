# Campaign Correctness Gap Remediation

## 1. Purpose

This document is the authoritative implementation plan for correcting the
remaining defects found after the campaign-correctness implementation ending at
commit `0fb7498` on branch `codex/campaign-correctness-remediation`.

The preceding implementation established the right overall model:

- selected lineages are published as durable Git artifacts;
- working and best-known remain Researcher decisions;
- unchanged continuation restores its selected parent's scientific recipe;
- compatible historical measurements can be reused by model identity;
- policy observation/action behavior travels with a saved model;
- proposals and postmortems record explicit scientific reasoning;
- the brief emphasizes the current experiment and scientific direction;
- Fresh recipe restoration is distinct from importing a trained baseline.

Do not redesign those decisions. This work repairs the remaining correctness,
recovery, measurement-identity, and memory-size gaps.

## 2. Worktree, branch, and campaign-artifact safety

Implement these corrections in the current branch. Do not create another
worktree and do not launch a campaign.

The checkout may contain interrupted-campaign files belonging to the human:

- `research/EXPERIMENTS.md`;
- `research/postmortems.md`;
- `research/research_state.json`;
- `research/results.jsonl`;
- untracked files under
  `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/`.

Before editing, record their path inventory and content hashes. After every
implementation commit and at final delivery, verify that their content is
unchanged. Do not stage, restore, delete, rewrite, migrate, or repair these live
campaign artifacts. Tests must redirect campaign paths to temporary fixtures.

Do not use `git add -A`, `git commit -a`, destructive checkout/reset commands,
or history rewriting. Stage only the implementation paths belonging to the
current commit.

Make and push a focused commit after each implementation step below. If a push
fails, stop and report the local commit; do not amend unrelated history or force
push.

Do not run training, evaluation, the autonomous research loop, the viewer, or
the final benchmark. Validation must use deterministic unit/integration
fixtures only.

## 3. Defects to repair

### 3.1 Reset backup path is invalid in a linked Git worktree

`research/reset_campaign.py` currently defines the backup root as
`ROOT / ".git" / "research-reset-backups"`. In a linked worktree, `.git` is a
file, not a directory. The reset therefore fails before creating its backup.
Existing tests use ordinary repositories or monkeypatch this path and do not
exercise the real worktree layout.

### 3.2 A backup exists, but recovery is not executable

On failure, reset reports only `recover from <path>`. No supported command
restores the pre-reset files or resumes/rolls back the recorded operation. Tests
prove only that copied files and `operation.json` exist. This is not sufficient
for a destructive operation that may already have created or pushed a commit.

### 3.3 Interrupted training does not freeze the complete accepted operation

`pending_training_operation` currently checks only experiment, kind, requested
parent, and code-parent commit on resume. It does not bind the complete accepted
proposal, effective configuration, seed, or exact Researcher-authored source
delta. On resume, validation reuses the old `researcher_changes` path list while
later publication recomputes the live scientific delta. A proposal edit or an
additional scientific edit can therefore enter the resumed execution without
the validation that accepted it.

### 3.4 Policy preprocessing reset runs more than once per episode

The scenario, reference, and final environments reset `policy_io`; their callers
then call `PolicyRuntime.reset()`, which resets the same `policy_io` again. The
current smoothing reset happens to be idempotent, but the generic saved-runtime
contract permits other stateful preprocessors. Training and evaluation must
have one unambiguous preprocessing reset per episode.

### 3.5 Model-contained code still contaminates evaluation-context identity

Observation and action preprocessing now travel inside `policy_runtime.pkl` and
are covered by the complete model fingerprint. Nevertheless,
`evaluation_semantics_fingerprint()` hashes the whole scenario package and
therefore also hashes the current source copies of `policy_io.py` and
`observations.py`. It additionally hashes algorithm/loading and normalization
source that is frozen into the runtime contract.

This creates false incompatibility: an old measurement can be rejected after a
policy-I/O source edit even though the measured model retains its own exact
policy I/O and the evaluation task itself is unchanged. Model identity and
evaluation-context identity must remain separate.

### 3.6 Derived experiment memory grows with every unmeasured checkpoint and
measurement artifact

`runner_repository.experiment_log_row()` currently emits one `unmeasured` item
for every unmeasured checkpoint. The campaign brief also enumerates every
historical detailed evaluation artifact. Both behaviors grow mechanically with
campaign length and distract from the latest experiment and revisable scientific
strategy. Detailed evidence must remain durable and discoverable without being
repeated in full in compact context.

### 3.7 Existing integration tests do not prove all advertised guarantees

The clean-clone integration test verifies artifact files and hashes but does not
actually load the saved runtime. Reset tests do not run from a linked worktree,
do not perform supported recovery, and do not test operation tampering during a
resume. There is no assertion that preprocessing reset occurs exactly once per
episode.

## 4. Step 1 — Make reset storage worktree-safe

### Objective

Resolve the reset-maintenance directory through Git itself. Never infer Git's
administrative directory from `<checkout>/.git`.

### Files

- `research/reset_campaign.py`
- `reset_research.ps1` only if its parameter or error surface must change
- `tests/autoresearch/test_reset_research.py`
- `README.md`
- `AGENTS.md`

### Required implementation

1. Replace the static `ROOT / ".git" / ...` backup location with a lazily
   resolved absolute Git administrative path.
2. Use a Git plumbing command such as
   `git rev-parse --path-format=absolute --git-path research-reset-backups`, or
   an equivalently direct Git-supported resolution. Do not parse the textual
   contents of `.git` manually.
3. Resolve and validate the path before any mutation. It must be inside the
   repository's actual Git administrative area, not inside the checkout and not
   an arbitrary caller-controlled location.
4. Preserve testability through a narrowly scoped injected/monkeypatched path
   resolver. Do not restore a global assumption that `.git` is a directory.
5. Keep the same machine-wide campaign mutex and current Fresh/Baseline
   semantics.

### Tests

Add a real temporary linked-worktree test:

1. create a temporary repository and bare remote;
2. create a linked worktree with `git worktree add`;
3. execute the reset entry point from that linked worktree;
4. prove the backup was created under the worktree's real Git administrative
   directory;
5. prove no directory was created beside or below the `.git` indirection file;
6. prove the working tree and remote end in the expected state.

Keep the ordinary-repository reset tests as well.

### Commit

`fix: resolve reset storage through the linked worktree git dir`

## 5. Step 2 — Make reset recovery real and testable

### Objective

A reset failure must leave either the completed reset or a supported way to
restore the exact pre-reset state. A copied directory plus a vague error message
is not an operational recovery contract.

### Files

- `research/reset_campaign.py`
- `reset_research.ps1`
- `tests/autoresearch/test_reset_research.py`
- `docs/reset-research.md`
- `README.md`
- `AGENTS.md`

### Required implementation

1. Extend `operation.json` so it records:
   - reset mode and resolved source commit;
   - original HEAD;
   - exact targeted paths;
   - which paths existed before reset;
   - pre-reset content hashes;
   - operation progress;
   - commits created by the reset;
   - whether each commit was successfully pushed.
2. Add one explicit human-only recovery command to `reset_research.ps1`. Keep it
   mutually exclusive with Fresh and Baseline. It must accept the path to a
   recorded reset operation and require `-Force`.
3. Recovery must validate the operation file and every path before writing.
   Reject an operation outside the resolved reset-maintenance root or for a
   different repository/worktree.
4. Restore every path that existed before reset and remove only targeted paths
   recorded as absent before reset. Never operate on an unrecorded path.
5. Do not rewrite Git history and do not force push. If reset commits were
   created, publish restoration as a new, explicit rollback commit. If pushing
   is unavailable, preserve the local recovery commit and report that exact
   state.
6. If no reset commit was created, restore the original clean worktree without
   manufacturing a commit.
7. Mark the operation recovered only after local files, Git state, and any
   required publication step are coherent.
8. On reset failure, print the exact recovery command, not merely a directory.
9. Re-running recovery must be idempotent: it may report that recovery is
   already complete, but it must not create another divergent state.

Do not add general transaction infrastructure. This recovery applies only to
the two existing campaign-reset modes.

### Tests

Inject failures at these boundaries in temporary repositories:

- before recipe restoration;
- after recipe restoration but before its commit;
- after the scientific commit;
- after campaign files are replaced;
- after the campaign reset commit;
- during each push.

For every boundary, execute the supported recovery command and verify:

- original scientific files and parameters are restored byte-for-byte;
- original campaign files and models are restored byte-for-byte;
- paths originally absent remain absent;
- the worktree is clean after successful recovery;
- remote history is coherent when publication is available;
- a second recovery call is harmless.

### Commit

`fix: make campaign reset failures explicitly recoverable`

## 6. Step 3 — Freeze the complete accepted training operation

### Objective

Runner recovery must execute exactly the proposal and scientific delta accepted
before interruption. It must neither reinterpret a changed live proposal nor
silently admit later source/configuration edits.

### Files

- `research/run_experiment.py`
- `research/runner_protocol.py`
- `research/runner_repository.py` if shared hashing helpers belong there
- `tests/autoresearch/test_execution_contract.py`
- `tests/autoresearch/test_scientific_reasoning.py`
- `research/PROTOCOL_DECISIONS.md`

### Required implementation

1. Canonicalize and deep-copy the accepted proposal before creating
   `pending_training_operation`.
2. Store a deterministic proposal fingerprint and the complete frozen proposal
   snapshot in the operation. The snapshot includes operation kind, hypothesis,
   reasoning, family, initialization, parent, seed, replication identity,
   parameter overrides, and change description when applicable.
3. Record the exact Researcher-authored scientific delta before Runner-managed
   restoration. For every changed path record:
   - normalized repository path;
   - whether it exists;
   - content fingerprint when it exists.
4. After an unchanged-continuation recipe restoration, separately record the
   exact restored recipe manifest and effective configuration fingerprint. Do
   not confuse this Runner-managed restoration with a Researcher intervention.
5. On every resume, select behavior from the frozen operation, not from mutable
   live proposal content. If `research/proposal.json` is present, it must match
   the frozen proposal exactly; otherwise reject it with a precise recovery
   error.
6. Verify the current scientific surface against the manifest appropriate to
   the saved progress state. Reject added, removed, or edited scientific paths
   that are not part of the frozen operation.
7. Validate and publish the same frozen delta. Never validate the saved path
   list and later publish a newly recomputed, wider delta.
8. Preserve existing restart behavior for an unchanged, untampered operation,
   including reuse of completed training and resume from a recoverable
   checkpoint.
9. Store operation progress only after the corresponding durable state exists.
10. Provide errors that identify whether the mismatch is in the proposal,
    Researcher delta, restored recipe, parameters, or parent artifact.

### Tests

Use temporary fixtures to prove:

- an unchanged interrupted continuation resumes successfully;
- changing only hypothesis or reasoning is rejected;
- changing seed, params, initialization, parent, or replication identity is
  rejected;
- adding a new researcher-owned source file after interruption is rejected;
- editing or deleting an accepted scientific file is rejected;
- changing `current_params.json` after interruption is rejected;
- Runner-managed historical recipe restoration is accepted and is not reported
  as a new Researcher intervention;
- the exact validated manifest is the one committed and trained;
- completed training is not repeated after a later recovery boundary.

### Commit

`fix: bind interrupted training recovery to its accepted operation`

## 7. Step 4 — Reset policy preprocessing exactly once per episode

### Objective

Training, research evaluation, task-reference evaluation, final evaluation, and
the viewer must all start each episode with the same clean model-I/O state. One
episode boundary must trigger one policy-I/O reset.

### Files

- `robot_learning/policy_runtime.py`
- environment/evaluator call sites only where required to establish one owner
- `tests/autoresearch/test_policy_runtime.py`
- focused benchmark/scenario tests that already cover episode reset behavior
- `research/PROTOCOL_DECISIONS.md`

### Required implementation

1. Choose one owner for policy-I/O episode reset and document that invariant in
   code. The environments already own the physical episode boundary and also
   serve training without a `PolicyRuntime`; preserving environment ownership is
   the minimal design unless repository evidence proves it unsafe.
2. Keep `PolicyRuntime.reset()` responsible for model recurrent state and the
   SB3 `episode_start` flag. Do not also reset the same I/O object if the
   environment already did so.
3. Ensure a newly exported runtime contains fresh preprocessing state. Do not
   rely on a double reset at first use.
4. Apply an action transform exactly once per action and reset its state exactly
   once per environment episode.
5. Preserve the current smoothing behavior numerically; this change repairs the
   generic contract and must not tune the intervention.
6. Preserve strict rejection of missing or mismatched runtime artifacts.

### Tests

Create a stateful test preprocessor whose reset increments a counter and whose
output exposes accidental duplicate reset/application. Verify for scenario,
task-reference, final-evaluation, and viewer-compatible execution paths:

- one reset per episode;
- one transform per action;
- no state sharing between two environments;
- deterministic behavior after repeated episode resets;
- the saved and reloaded runtime behaves identically to the training-side I/O.

### Commit

`fix: reset saved policy preprocessing once per episode`

## 8. Step 5 — Separate model identity from evaluation-context identity

### Objective

Historical evidence reuse must reject genuine evaluator/task changes while not
rejecting a measurement merely because the current source copy of behavior
already frozen into that model has changed.

### Files

- `research/runner_protocol.py`
- `research/runner_execution.py` only if artifact metadata needs an explicitly
  named context field
- `research/runner_repository.py` only for shared evidence metadata
- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_post_training_analysis.py`
- `research/instruments.md`
- `research/PROTOCOL_DECISIONS.md`

### Required implementation

1. Preserve complete model identity through the existing artifact fingerprint,
   which includes weights, metadata, normalization/replay files when present,
   and `policy_runtime.pkl`.
2. Define evaluation-context identity from code/data that changes how the Runner
   executes or interprets the evaluation task outside the saved model runtime.
3. Exclude source that is already frozen into and identified by the model
   runtime, at minimum:
   - `robot_learning/scenario/policy_io.py`;
   - `robot_learning/scenario/observations.py`;
   - runtime-frozen algorithm loading code;
   - runtime-frozen normalization code.
4. Continue to include actual researcher-owned evaluation/task semantics, such
   as the scenario environment mechanics, research evaluation implementation,
   reward-derived scientific evidence, and researcher instrumentation used by
   the measurement.
5. Keep protected task-reference identity separate and fixed by its panel
   contract.
6. Do not use path names alone to claim two models are equal. Model fingerprints
   remain mandatory.
7. Two historical research measurements are reusable/comparable only when:
   - their complete model identities are known;
   - their requested panel settings and episode identities match as required;
   - their evaluation-context identities match.
8. A change only to model-contained policy I/O must not invalidate the old
   model's old measurement. A change to actual evaluator/environment semantics
   must invalidate reuse.
9. Preserve clear mismatch diagnostics naming both source artifacts and the
   differing context identities.

Avoid dynamic import tracing, plugin systems, dependency graphs, or a new
framework. Use a small explicit distinction consistent with the current fixed
stack and saved-runtime contract.

### Tests

Verify that:

- editing `policy_io.py` does not change evaluation-context identity;
- editing `observations.py` does not change evaluation-context identity;
- two models with different saved action transforms can be measured and paired
  on one unchanged research panel;
- changing `scenario/evaluation.py` changes context identity;
- changing relevant environment success/task mechanics changes context identity;
- changing researcher-owned measurement instrumentation changes context
  identity;
- unrelated presentation, cache, tests, and training-only files remain excluded;
- incompatible contexts remain rejected with actionable feedback.

### Commit

`fix: separate saved model behavior from evaluation context identity`

## 9. Step 6 — Keep `EXPERIMENTS.md` and the brief compact without hiding evidence

### Objective

Preserve complete evidence in `results.jsonl`, postmortems, training logs, and
evaluation artifacts while keeping derived human/research context focused and
bounded. Do not synthesize conclusions or scores.

### Files

- `research/runner_repository.py`
- `research/build_research_brief.py`
- `tests/autoresearch/test_console_presentation.py`
- `tests/autoresearch/test_research_context.py`
- `research/PROTOCOL_DECISIONS.md`

### Required implementation

1. Keep one row per experiment in `research/EXPERIMENTS.md`.
2. Report measured checkpoints/panels factually, but do not append one textual
   `unmeasured` entry per unmeasured checkpoint.
3. Replace that repetition with one compact count, for example
   `3 measured; 19 unmeasured checkpoints`. Do not treat unmeasured as zero or
   infer model quality.
4. Preserve the selected working/best-known/code decisions and the Researcher's
   hypothesis assessment in each experiment row.
5. In `research/brief.md`, retain detailed evidence references for the current
   unresolved experiment and the evidence attached to reusable lineage roles.
6. Summarize older evidence by experiment/panel/count with links to the durable
   result or postmortem source rather than enumerating every historical artifact
   forever. The full exact artifact paths remain in `results.jsonl`, role
   records, postmortems, and evaluation directories.
7. Keep newest experiments first and keep the current scientific strategy near
   the top. Best-known remains lower in the brief and must reflect the actual
   current designation.
8. Do not introduce an arbitrary scientific ranking, fixed number of experiments
   per direction, automatic hypothesis exhaustion, or hidden evidence deletion.
9. `EXPERIMENTS.md` remains a derived view; `results.jsonl` remains authoritative.

### Tests

Build a synthetic campaign containing at least 25 experiments, many checkpoints,
multiple measurement rounds, retained lineages, and repeated panels. Verify:

- the latest experiment and strategy remain complete;
- unmeasured checkpoints are represented by counts, not one item each;
- historical detailed artifact paths remain recoverable from authoritative
  files;
- brief size does not grow with the number of individual unmeasured checkpoints
  or raw historical evidence artifacts;
- repeated use of one panel is still visibly repeated evidence, not independent
  confirmation;
- no score or assessment is fabricated.

Do not enforce a cosmetic line-width or an arbitrary maximum number of campaign
experiments. Bound repetition by grouping information according to its role.

### Commit

`fix: compact derived experiment memory without discarding evidence`

## 10. Step 7 — Complete the integration coverage

### Objective

Make the tests exercise the guarantees that previously existed only as file or
hash assertions.

### Files

- `tests/autoresearch/test_campaign_correctness_integration.py`
- the focused test files changed in Steps 1–6
- documentation only if testing exposes a genuine contract correction

### Required integration scenario

In temporary repositories and without real RL training:

1. start from a linked worktree;
2. perform Fresh reset from a historical RecipeRef;
3. create a deterministic fake experiment-1 artifact with a stateful runtime;
4. close it into durable working and best-known roles;
5. clone from the remote into a clean checkout;
6. actually load the saved runtime from the clone and execute at least one
   deterministic observation/prediction/action path;
7. change the scientific recipe;
8. request unchanged continuation from the older lineage;
9. interrupt at a persisted boundary and resume from the frozen operation;
10. prove the old complete recipe and exact parent artifact are used;
11. measure the continued model on a panel compatible with historical evidence;
12. reuse the earlier reference evidence by fingerprint;
13. close and publish the new lineage;
14. clone again and actually load every role named by state;
15. prove campaign memory, model files, runtime, parameters, and evidence bindings
    are coherent;
16. separately inject a reset failure and prove the supported recovery command
    restores the pre-reset state.

The fake trainer/evaluator may write deterministic fixture artifacts. It must not
invoke MuJoCo training, SB3 learning, a Researcher session, or any campaign
launcher loop.

### Validation commands

Run focused tests after each step. At the end, run once:

```powershell
uv run ruff check research robot_learning tests/autoresearch tests/scenario tests/training
uv run pytest -q tests/autoresearch tests/scenario tests/training
uv run pytest -q tests/benchmark
```

Do not repeatedly run the full suite after every small edit. Do not launch a
real campaign as validation.

### Commit

`test: cover worktree reset recovery and frozen campaign operations`

## 11. Final documentation and decision log

Update `research/PROTOCOL_DECISIONS.md` with factual decisions only:

- reset storage is resolved through the actual Git administrative directory;
- reset failure has a supported, path-confined recovery operation;
- interrupted training resumes only the exact frozen proposal and scientific
  manifest;
- policy-I/O state resets once per episode;
- saved model identity is distinct from evaluation-context identity;
- derived memory groups unmeasured checkpoints and historical evidence without
  deleting authoritative records.

Update README/AGENTS/instrument documentation only where the user-facing command
or contract changed. Do not duplicate detailed protocol prose across files.

Final documentation commit, if needed:

`docs: record remaining campaign correctness guarantees`

## 12. Final acceptance criteria

The work is complete only when all of the following are true:

1. Fresh and Baseline reset can create backups from both a primary checkout and
   a linked worktree.
2. A documented recovery command demonstrably restores a failed reset.
3. An interrupted experiment cannot resume after its proposal, parameters,
   seed, parent, or scientific delta has changed.
4. An untampered interrupted continuation resumes without repeating completed
   training.
5. Stateful policy preprocessing is applied once per action and reset once per
   episode in every execution path.
6. Model-contained observation/action changes no longer create a false
   evaluation-context mismatch.
7. Genuine evaluator/environment changes still invalidate historical reuse.
8. `EXPERIMENTS.md` and the brief remain compact in a long synthetic campaign
   while authoritative evidence remains complete.
9. A clean clone can actually load every working, best-known, and retained model
   named by state.
10. The interrupted real campaign files listed in Section 2 are byte-identical
    to their pre-implementation hashes.
11. No real campaign, training run, evaluation run, or final benchmark was
    launched.
12. Every implementation commit was pushed normally and no unrelated file was
    staged.

## 13. Required final report from Copilot

The final report must contain:

- branch and final commit;
- commits created and whether each was pushed;
- files changed per step;
- focused and final validation commands with exact results;
- proof that the live interrupted-campaign artifacts were preserved;
- proof that the linked-worktree reset path was exercised;
- proof that reset recovery was executed, not merely that a backup exists;
- proof that the clean-clone runtime was loaded;
- an explicit deviations section.

For every deviation, state the original requirement, the implemented behavior,
the reason, and the scientific or operational impact. If there are no
deviations, state `No deviations`. Do not silently weaken a requirement, alter
tests to match a defect, fabricate evidence metadata, or repair the live
interrupted campaign.
