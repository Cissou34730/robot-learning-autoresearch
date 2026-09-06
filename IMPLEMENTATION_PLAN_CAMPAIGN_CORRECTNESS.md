# Implementation plan: durable scientific lineages, usable evidence, and recipe-based campaign restart

## 1. Purpose, authority, and limits of this implementation

This is the follow-up implementation plan for the campaign run after `IMPLEMENTATION_PLAN_RESEARCH_WORKFLOW.md`. Implement this document in full, in the order below. The previous document explains the existing workflow; this document supersedes its conflicting requirements and repairs incomplete implementation. Do not reimplement the whole lifecycle.

The human's objective is a learned robot policy meeting the task in `research/scenario.md`. The Researcher chooses how to investigate, train, measure, continue, retain, or abandon a scientific direction. The Runner executes those choices and preserves their integrity. The Runner must not choose the scientific winner, mandate a comparison, impose a number of experiments per direction, or require a new training intervention when unchanged continuation is appropriate.

The recent campaign showed improvements in the Researcher's behavior and in the harness workflow: hypotheses followed earlier observations, several experiments transferred from an existing policy, measurements addressed behavioral questions, and poor interventions were abandoned. Preserve these methodological and harness gains when correcting the remaining defects. This does not mean preserving the campaign's trained models, scientific interventions, parameters, or experiment-6 smoothing in the next campaign. The remaining defects concern preservation of models and recipes when explicitly selected, expression of scientifically valid comparisons and closures, incomplete feedback on hypotheses, and residual instructional bias.

The human will restart the next campaign by restoring the complete scientific recipe that previously produced a 97% checkpoint, then training a new baseline from scratch. This is recipe restoration, not import of that trained checkpoint, its campaign history, or its evaluations. No particular success percentage is guaranteed by restoring a recipe.

The implementation must make the following possible:

1. A selected working, best-known, or retained policy survives a new checkout of Git history, with its inference runtime and training provenance.
2. Continuing an older lineage uses its actual recipe, parameters, weights, and normalization state.
3. A policy carries the preprocessing needed to reproduce its behavior under any compatible evaluator.
4. Historical measurements of a saved model remain discoverable and usable when technically comparable.
5. A Researcher can close an experiment by selecting a working model without making a best-known claim.
6. The recorded analysis explicitly revisits the predicted outcome of the experiment.
7. Fresh recipe restoration starts at experiment 1 with newly generated evidence.

Use the existing Python, SB3, MuJoCo, Gymnasium, Git, and PowerShell stack. Keep orchestration, execution, protocol validation, and repository persistence in their existing modules. One small reset helper is specified below to remove duplicated Python-state logic from PowerShell. Do not introduce a plugin system, registry, generic experiment framework, database, or new LLM service.

Software validation is part of implementation. Launching a real campaign, a Researcher session, baseline training, model evaluation, or an official benchmark is not. The human performs campaign validation later. Test subprocesses and Git operations must target temporary fixtures and temporary repositories. Short deterministic environment steps and serialization tests are permitted; real training is not a validation shortcut.

Keep the configured Researcher model, reasoning effort, training budget, checkpoint frequency, validation-suite selection policy, and final task unchanged. Token optimization and redesign of `query_training_log.py` are deferred. Do not restore the historical recipe into the development checkout as part of implementing this plan.

## 2. Starting point, branch, dirty files, and required commits

### Verified starting point

- Existing worktree: `C:\Users\cyril.beurier\code\robot-learning-reasoning-memory`.
- Existing branch: `codex/research-workflow-remediation`.
- Inspected HEAD: `5871fe2` (`experiment 6 scientific recipe`). Resolve this abbreviation to its full commit before recording the implementation base.
- New implementation branch: `codex/campaign-correctness-remediation`.
- Implementation stays in this same worktree. Do not create another worktree.

First read `AGENTS.md`, this plan, `research/program.md`, `research/instruments.md`, and the previous implementation plan. Record the actual HEAD, branch, working-tree status, and relevant existing ignored phase files. If another implementation has changed the starting code, inspect its diff and report the discrepancy before choosing a different base. Do not silently build on another campaign or an unrelated branch.

At inspection, the following interrupted-campaign changes were present:

- Modified `research/EXPERIMENTS.md`, `research/postmortems.md`, `research/research_state.json`, and `research/results.jsonl`.
- Three untracked experiment-6 evaluation JSON files under campaign `90890200-b313-4f38-b010-de1eaaeb3d98`.
- Ignored campaign files, including phase deliverables and challenger artifacts, may also be present.

These belong to the human. Create the new branch with an ordinary branch switch from the verified committed base; leave these changes in place. Record their hashes and inventory before implementation, and verify them after implementation. Do not stage, restore, stash, delete, migrate, or reset them. Tests must redirect all state and filesystem paths into fixtures. If an unexpected dirty file overlaps an implementation file, preserve its exact content and report the overlap before overwriting it. Do not use a broad `git add -A` or `git commit -a` in this checkout.

The live committed scientific recipe includes the experiment-6 smoothing intervention. During harness implementation, preserve its behavior long enough for Step 4 to repair and test the general saved-policy preprocessing contract; do not tune or remove it incidentally. This is an implementation-time preservation rule only. After development, the human's `Fresh -RecipeRef` reset replaces the complete scientific surface with the historical 97%-baseline recipe. Because that recipe has no smoothing intervention, the reset must remove experiment-6 smoothing before the new experiment 1 is trained.

### Commit and push policy

The implementation agent is explicitly authorized and required to create the new branch, commit its changes regularly, and push each commit. This instruction applies to the implementation branch, not the interrupted campaign's uncommitted artifacts.

1. Create `codex/campaign-correctness-remediation` in the current worktree. If that branch already exists, inspect it; do not overwrite or force-update it.
2. Commit this plan alone as the first implementation commit: `docs: record campaign correctness implementation plan`.
3. Push the branch with upstream tracking to `origin`.
4. After every numbered implementation step, run its focused checks, commit that step's implementation/tests/documentation, and push. The suggested commit subjects appear below. A large step may use several coherent commits.
5. Stage explicit implementation paths or selected hunks. Inspect the staged diff before committing, particularly around files under `research/`.
6. Do not squash the implementation into one final commit. Keep the sequence visible for review. Do not rewrite the campaign's existing commits.
7. If a push fails, retain the local commit and report the Git state. Do not force-push or merge remote campaign history automatically.

This document authorizes future implementation commits. Merely drafting this document does not launch any of those operations.

## 3. Verified defects and their consequences

Use function names as navigation anchors; line numbers will change.

| Location | Verified behavior | Required repair |
| --- | --- | --- |
| `runner_protocol._v4_lineage_record`, `plan_v4_previous_result_decision` | New v4 role records retain candidate paths under `research/checkpoints/challengers/`. | Materialize selected/retained artifacts at durable Git-tracked paths before closing. |
| `run_experiment.apply_pending_v4_closure` | Assigns role records but does not perform the copies that the legacy closure path performs. | Implement durable materialization in the v4 path, including restart and push failure handling. |
| `.gitignore`, `runner_repository.RUNNER_MEMORY_PREFIXES` | Challengers are ignored; accepted and retained paths are tracked. | Keep disposable challengers ignored; persist chosen artifacts through the tracked archive. Checking the legacy path is not proof that v4 persists models. |
| `runner_protocol.training_parent`, `run_experiment.run_training_experiment` | Resolves an old parent model and step count while loading current worktree configuration. | An unchanged continuation must restore the selected parent's complete recipe before effective configuration is loaded. |
| `runner_protocol.validate_paired_comparison_plan` | Checks requested/partial panels in the open experiment, ignoring compatible historical measurements. | Resolve historical evidence by immutable model identity and measurement settings. |
| `_development_evidence_catalog`, `_validated_designation_evidence` | Best-known closure requires fingerprints that old imported evidence metadata lacks. | Distinguish unavailable provenance from a true identity mismatch; new records must be complete and historical imports must be validated honestly. |
| `scenario/environment.py`, `scenario/policy_io.py` | Smoothing is implemented after `policy_io.action()` in the environment; exported action mapping remains identity. | Move policy preprocessing into the exported policy I/O contract and apply it exactly once. |
| `runner_repository.experiment_log_row` | Reads legacy experiment-wide score fields, producing `-` for v4 measurements. | Render per-model/panel facts and the actual closure decision from v4 records. |
| `run_research.ps1`, `program.md` | Active preparation still says `This is the complete task` and foregrounds intervention changes. | Expose continuation/intervention/replication without requiring mutation; preserve deliverable completion. |
| `instruments.md` | Closure example omits supported `code.action: restore`; best-known evidence requirements are incompletely described. | Document the exact implemented schema and evidence rules. |
| `reset_research.ps1` | Fresh preserves current science; Baseline restores old models/evidence and duplicates migration/fingerprint logic. | Add an explicit recipe source to Fresh, share provenance/state logic, and preserve the distinct existing Baseline capability. |

The recent training-log tool was used repeatedly. Do not describe it as unused. Improving broad/repeated extraction requests is a separate future improvement. Preserve the instrument and its phase visibility without mandating calls or changing its output in this implementation.

## 4. Step 1 — Persist v4 lineages as complete Git artifacts

### Objective and context

A state JSON that points to ignored model files is not durable persistence. A locally runnable lineage must also be recoverable from its published Git commit. The current v4 path fails this invariant even though the legacy accepted-model path satisfies it.

### Files

- `research/runner_repository.py`: artifact copy, memory paths, commit/publication, role references.
- `research/runner_paths.py`: reuse `campaign_retained_root()`.
- `research/runner_protocol.py`: v4 closure plan and lineage record construction.
- `research/run_experiment.py`: serialized closure plan, application, recovery, cleanup.
- `tests/autoresearch/test_lineage_roles.py`, `test_post_training_analysis.py`, `test_execution_contract.py`.
- `AGENTS.md`, only the artifact-location description affected by this change.

### Required implementation

1. Use the existing Git-tracked `research/checkpoints/retained/<campaign-id>/` archive for new durable v4 policies. Give each newly materialized policy a stable physical directory derived from its source experiment, checkpoint, and complete fingerprint. Retained user-facing IDs remain labels in state; they need not be directory names.
2. Copy weights, `artifact.json`, `policy_runtime.pkl`, and any saved normalization/replay files using the existing complete-artifact contract. Do not copy only weights or rename the internal files.
3. Resolve working, best-known, explicit retentions, and pre-decision role aliases before mutations. Deduplicate copies when several references point to the same immutable artifact.
4. Include source, destination, expected fingerprint, and resulting role records in `pending_closure_operation`. Build and validate the full plan before copying, restoring code, updating state, or cleaning artifacts.
5. Copy into a temporary sibling directory, verify completeness and fingerprint, then publish to the final directory. If that destination already exists and matches exactly, reuse it on retry. If it differs, fail without overwriting either artifact.
6. Update current role/retention records and closure result records to durable paths. Preserve original experiment/checkpoint identity and the training recipe revision. Resolve measurement association by fingerprint; moving identical files must not invalidate their evidence.
7. Do not rewrite immutable detailed evaluation JSON merely because its historical `model` string names the original challenger path. The measurement binding introduced in Step 3 resolves the model identity.
8. Commit and push scientific code separately from campaign memory/artifacts. Only after publication may cleanup remove unretained candidate weights. A failed push or Ctrl-C must leave the pending operation recoverable without another Researcher decision.
9. Persist cleanup completion and clearing of the pending operation so reloading the published state is coherent. Recovery must handle interruption after each boundary: plan, copy, role/result write, local commit, push, cleanup, and pending-operation clearance.
10. Correct `_v4_lineage_record()` when an existing role is selected: preserve its original `candidate` checkpoint identifier instead of replacing it with the alias `working` or `best_known`. Preserve its original scientific commit and parameters.
11. Record actual cumulative transitions: parent transitions plus the selected checkpoint's actual transitions. An intermediate checkpoint at 100,352 is not a 120,000-step endpoint.
12. Preserve old accepted/retained paths as readable. If a previously selected v4 role still points to an ignored challenger directory that exists, the next valid closure may materialize it through the same mechanism. Do not fabricate missing weights or repair the live campaign during development.

### Software validation

- Close fixtures with different working and best-known candidates plus an explicit retained alternative. Push to a temporary bare remote, clone it into a new temporary directory, and verify all referenced runtime/model/stat files and fingerprints.
- Verify roles sharing one artifact survive changing one role, removing a redundant retention label, and candidate cleanup.
- Force failure at each publication boundary; retry from disk and verify no duplicate record, overwritten artifact, lost role, or premature deletion.
- Test legacy accepted-path reuse and a current v4 challenger-backed role becoming durable.
- Check original checkpoint name and actual transition count survive repeated selections.
- A counterfeit or incomplete artifact fails before state mutation.

Commit/push: `fix: persist selected v4 lineages and recover closure publication`.

## 5. Step 2 — Continue an older model with its complete scientific recipe

### Objective and context

The selected parent's weights and its recipe are distinct persisted facts. Ordinary transfer can intentionally apply a changed recipe to those weights. An unchanged continuation must use the parent's recipe, even when the active checkout contains another experiment's science.

### Files

- `research/runner_protocol.py`: `training_parent`, `plan_lineage_restore`, preparation/continuation validation.
- `research/runner_repository.py`: scientific surface restoration and recipe provenance.
- `research/run_experiment.py`: preparation acceptance and configuration-loading order.
- `research/runner_execution.py`: only parent metadata/configuration handoff where needed.
- `tests/autoresearch/test_lineage_roles.py`, `test_research_protocol.py`, `test_execution_contract.py`.

### Required implementation

1. Reuse the existing lineage record: artifact identity, `scientific_commit`, effective `parameters`, original checkpoint, and cumulative steps. Resolve `training_parent` once at proposal acceptance and freeze this identity for execution/recovery.
2. Validate an unchanged continuation against the Researcher-authored delta first. It must contain no parameter override or scientific edit. Do not classify the Runner's subsequent restoration of the old recipe as a Researcher intervention. The scientific restoration set must include `research/current_params.json`: the current `is_researcher_owned()` code-prefix predicate and parameter-only classification are separate, so using that predicate alone would omit the JSON.
3. Plan restoration through the current authoritative scientific ownership rules. Restore scientific source, runtime configuration, associated scientific tests, and added/deleted scientific files together. Preserve harness files, dependencies, protected task files, and all campaign memory.
4. Restore the parent's recorded effective runtime parameters as well as its code revision. Do not assume that the currently checked-out JSON equals the effective parameters recorded for the selected model.
5. Apply the validated restoration before loading effective training configuration and before importing/reusing scientific modules for execution. Account for Python module caching: use the existing fresh training/validation subprocesses after restoration rather than executing already-imported stale science.
6. Preserve two distinct revisions: the pre-operation code anchor needed to recover or revert this operation, and the recipe revision actually used for the continuation. Do not silently replace one with the other.
7. Resume the selected model and normalization through the existing training artifact interface. Preserve existing SB3 continuation behavior; do not silently start fresh or substitute another model when incompatible.
8. For ordinary `kind: training` with transfer, preserve the Researcher's intentional current intervention. Do not automatically overwrite those edits with the parent's recipe. Model-parent provenance and training-recipe provenance must remain separately recorded.
9. A parent with unavailable scientific provenance must produce an actionable preflight error before training. Do not guess a commit from the current HEAD or from a scientific interpretation in the postmortem.
10. Make restoration restartable using existing pending-operation bookkeeping. A retry must not rerun completed training or lose the pre-restoration state.
11. Keep `code.action: restore` at closure available and documented; automatic recipe restoration for unchanged continuation must also work when that earlier closure chose to keep different code.
12. Preserve replication's current documented meaning: it runs the current recipe fresh and links the earlier experiment. Do not silently change replication into historical recipe replay in this step.

### Software validation

- In a temporary repository, create recipe A and incompatible current recipe B with different reward, observation source, JSON, scientific tests, and an added/deleted file. Continue parent A; intercept the training subprocess and assert it receives A's complete recipe and parameters, without executing training.
- Verify the human-owned harness/task bytes remain B's current versions.
- Transfer an ordinary intervention B onto parent A and verify B is preserved intentionally.
- Test no-op continuation from the current recipe, aliases sharing a model, and unavailable provenance.
- Interrupt between restoration and process dispatch; recover using the frozen parent exactly once.
- Tests must inspect files/configuration consumed by execution, not only whether a restoration helper was called.

Commit/push: `fix: restore the complete parent recipe for unchanged continuation`.

## 6. Step 3 — Bind measurements to models and reuse compatible historical evidence

### Objective and context

Experiments 2, 4, and 5 encountered refusals to compare a new candidate with an already-measured working model. The final closure exposed missing identity metadata in imported baseline evidence. The same model may be referred to by different role names and filesystem locations; those names are not sufficient scientific identity.

### Files

- `research/runner_protocol.py`: `_development_evidence_catalog`, `resolved_measurement_models`, `validate_paired_comparison_plan`, `_validated_designation_evidence`, best-known planning.
- `research/run_experiment.py`: measurement acceptance, completed measurement persistence, comparison inputs.
- `research/runner_repository.py`: measurement records and canonical evidence references.
- `research/runner_execution.py`: `requested_paired_comparisons` and its input loading.
- `research/build_research_brief.py`, `research/runner_console.py`: available evidence and actionable validation feedback.
- `tests/autoresearch/test_lineage_roles.py`, `test_post_training_analysis.py`, `test_execution_contract.py`, `test_research_protocol.py`.

### One evidence resolution path

1. Extend the existing development-evidence catalog; do not build a separate database/cache service. Use it for paired comparison planning, comparison execution, and best-known evidence validation.
2. Every new completed measurement must durably identify its complete model fingerprint, instrument, detailed artifact path, requested settings, and evaluation semantics or fixed panel identity. Persist this binding in the result/pending record, not just a transient model alias.
3. Resolve the same model across checkpoint names, retained IDs, `working`, and `best_known` by fingerprint. A later role change must not retarget an accepted request or old measurement.
4. Inspect current-campaign historical records and completed rounds in the open experiment. Load detailed per-episode outcomes only for the evidence actually needed by the requested comparison.
5. A paired comparison requires the same instrument and compatible evaluation semantics, and exactly matching episode identities for each panel being compared. Identical sample counts alone are insufficient. Do not pool research and task-reference results.
6. The requested candidate's new panel may match an existing reference panel even when that reference also has other historical panels. Additional unrelated reference panels must not invalidate the useful match. Report exactly which common panels and source artifacts were used; never silently compare partial/nonmatching episode sets.
7. If multiple byte-identical measurements describe the same deterministic model/panel, count that panel once. Conflicting outcomes for the same claimed identity are an integrity error to report, not observations to average.
8. Validation and execution must use the same resolved evidence plan. Freeze its model identities and source artifacts with the accepted request. Do not validate history and then execute from current-experiment-only lists.
9. Preserve the existing measurement request schema and at-least-one-measurement rule for an actual request. Optional paired comparisons may use existing evidence on either side. Do not add a comparison-only phase or automatically request a reference measurement. A closure may already cite historical comparable evidence without a new measurement request.
10. Do not change the default seed, episode budget, task-reference panel, or final benchmark. Preserve the current conservative evaluation-semantics fingerprint. A source change affecting that fingerprint remains a potential measurement-context change; do not silently declare old and new research evaluations interchangeable.
11. Explain incompatible semantics in feedback by naming both measurement contexts and their source artifacts. The Researcher can choose compatible measurements, pursue a working lineage without a best-known claim, or revise its reasoning. The Runner must not force a new panel.

### Best-known selection and error reporting

1. Omitted `best_known` preserves it. Selecting `continue_from` must never imply replacement.
2. Initial designation requires development evidence for the chosen model. Replacement of a different incumbent requires cited compatible evidence for both identities. Existing evidence is sufficient; a new simulation or a numerical improvement threshold is not required by the Runner.
3. Researcher-defined secondary diagnostics may motivate a designation between equally successful models when their measurements are comparable. The Runner checks identity and comparability, not whether stability is the right tie-breaker.
4. Recognize valid evidence for a model even when the latest role record did not yet copy every historical measurement path. Derive association from the catalog's verified fingerprint binding, not membership in an accidentally incomplete role-local list alone.
5. Distinguish missing identity metadata, missing artifact files, true fingerprint mismatch, incompatible instrument, and incompatible panel semantics. Return precise recoverable errors before applying a closure.
6. For missing legacy metadata, do not assign the incumbent's fingerprint simply because its checkpoint name resembles a filename. Preserve old results as readable historical evidence; verification or explicit maintenance is required before using unverifiable evidence for designation. Step 7 handles the existing Baseline import path.
7. The developer must not repair or re-close the current real experiment as part of testing. Use fixtures reproducing the failure and validate that a new Fresh campaign writes sufficient identity from experiment 1 onward.

### Software validation

- New candidate measurement plus historical working evidence succeeds without remeasuring working; spy on evaluator calls to prove this.
- Reference alias changes and relocation to the durable archive do not invalidate evidence.
- A reference with multiple panels can supply the exact matching requested panel; unrelated panels are not pooled.
- Wrong model, mismatched seeds/episode identities, semantics changes, and mixed instruments fail before execution/closure.
- Best-known replacement accepts compatible historical evidence, rejects unrelated citations, and does not impose a success delta.
- Missing legacy identity is reported as unavailable provenance rather than a false claim that weights differ.
- Round recovery neither duplicates simulations nor inflates sample size from repeated identical panels.

Commit/push: `fix: resolve historical evaluation evidence by immutable model identity`.

## 7. Step 4 — Make stateful policy preprocessing travel with the model

### Objective and context

The experiment-6 smoother changes physical commands in the mutable training/research environment. The exported `policy_io` action is still identity. As a result, research evaluation can apply current smoothing to an older model, while a task-reference or official evaluation omits the newer policy's smoothing. Model-runtime isolation is incomplete for this intervention.

This step uses smoothing as the concrete regression case for the general rule that stateful observation/action preprocessing must travel with the saved policy. It does not make smoothing part of the future baseline or the permanent harness. The later recipe reset deliberately removes this scientific intervention while retaining the corrected generic runtime contract and its human-owned regression coverage.

### Files

- `robot_learning/scenario/environment.py`, `robot_learning/scenario/policy_io.py`.
- `robot_learning/training/checkpoint.py`, only if export wiring needs correction.
- `robot_learning/policy_runtime.py`, only if the existing `PolicyIO.action/reset` contract needs a correctness fix.
- `tests/scenario/test_environment.py`, related researcher-owned scientific tests.
- `tests/autoresearch/test_policy_runtime.py`; short boundary checks in `tests/benchmark/` if necessary to verify their existing runtime calls.

### Required implementation

1. Use the existing `PolicyIO` action and reset hooks for stateful policy preprocessing. Move the current smoother into the researcher-owned policy I/O implementation. Do not introduce a new action framework.
2. Preserve its exact current numerical behavior: first action handling, coefficient, ordering of clipping versus smoothing, previous-action state, and reset between episodes. Do not tune the coefficient.
3. Give each environment/runtime its own preprocessing state. Training environments must not share previous actions. Exported artifacts must begin each episode with reset preprocessing state.
4. Training and research evaluation apply the configured policy action mapping exactly once. Research evaluation of a saved older model uses that model's own mapping, not a second transformation from current scenario code.
5. Export the complete preprocessing with each model. The existing task-reference and final evaluators already consume `runtime.io.action/reset`; preserve that interface and their physical task semantics.
6. Resolve scientific dependencies before serialization. A later edit to current scenario modules must not change a previously exported runtime.
7. Do not modify the bytes of existing campaign models to claim that they now contain this smoother. Old evidence and models retain their recorded semantics. New artifacts carry the corrected implementation.
8. Document the general rule for researcher-owned preprocessing in `instruments.md`, without prescribing smoothing, a network architecture, dimensions, or a scientific intervention.

### Software validation

- Use a deterministic synthetic action sequence to verify equality between training preprocessing and reloaded exported preprocessing over multiple episodes.
- Use two environments/runtimes simultaneously to verify independent state.
- Serialize identity and stateful mappings, modify current scenario code, and confirm each artifact keeps its own behavior.
- Verify research, task-reference, and official environment consumers apply the mapping once. Use fixture policies/short controlled steps, never a real campaign panel.
- Verify normalization, observation construction, and existing runtime integrity checks still pass.
- Keep these as implementation regression tests under existing validation ownership; do not add automatic full-suite validation to every scientific intervention.

Commit/push: `fix: preserve stateful policy action mapping in saved runtimes`.

## 8. Step 5 — Close the hypothesis loop and make scientific memory usable

### Objective and context

Preparation already requires `reasoning.expected_observation`, `contradicting_observation`, evidence, alternative, initialization rationale, and strategy link. The missing part is a clear return to those predictions after training. More required words in a proposal alone do not establish learning from experiments.

### Files

- `research/runner_protocol.py`: postmortem parsing/validation.
- `research/run_experiment.py`: snapshot the assessment into the closed result.
- `research/runner_repository.py`: result update and `experiment_log_row`.
- `research/build_research_brief.py`, `research/runner_console.py`.
- `tests/autoresearch/test_scientific_reasoning.py`, `test_research_context.py`, `test_console_presentation.py`, `test_post_training_analysis.py`.

### Required contract and memory behavior

1. Keep the existing preparation JSON reasoning fields; do not add a duplicate numeric expected-gain field. Predictions can concern task success, behavior, learning dynamics, or what another training segment would reveal. Do not demand a fabricated percentage improvement.
2. Add one required `**Hypothesis assessment:**` heading to new non-baseline postmortems, alongside existing Result, Observed behavior, Interpretation, and Evidence inspected. Its text must address the original prediction, what was actually observed, whether that supports/partly supports/contradicts/leaves unresolved the hypothesis, and the limits of that conclusion.
3. This is a Researcher-authored conclusion. Validate presence/non-empty content, not scientific correctness with keywords or a scoring model. Do not add an automatic hypothesis-status decision, mandatory abandonment condition, or quota. Baselines have no intervention hypothesis to test and are exempt; old entries remain readable.
4. At closure, store the assessment text in the experiment's authoritative record as `hypothesis_assessment`. Preserve the original preparation reasoning/strategy snapshot unchanged. Do not require the Researcher to duplicate its assessment in both Markdown and JSON.
5. Keep `Interpretation` for other observations, competing explanations, and implications for future work. The assessment must not exclude unexpected evidence or turn one failed intervention into proof against its whole hypothesis family.
6. The revisable Scientific strategy continues to contain Direction, Lessons and limits, Open questions, and Conditional next steps. It may reconsider an earlier lesson, deepen a lineage over several experiments, or abandon it. No fixed sequence or number of experiments is imposed.
7. Update `EXPERIMENTS.md` for v4 with concise columns covering experiment, operation/parent, intervention, measured checkpoint/panel results (or unmeasured), hypothesis assessment, and final working/best-known/code decision. Remove dependence on obsolete `candidate_success_percent` and `candidate_seeds_passed` for new records.
8. Show per-checkpoint results with instrument/panel identity. Never fill a single representative experiment score with the first or maximum checkpoint score. Do not convert training reward into task success.
9. In the brief, retain current/latest facts first, then working direction and the complete reverse-chronological experiment index, with best known lower down. Add the latest hypothesis assessment and links to relevant postmortem entries. Preserve source attribution and uncertainty.
10. Keep older experience accessible through all-campaign index rows and source links. Do not copy every raw diagnostic or all old postmortems into the prompt, and do not impose a line-count target.
11. Repeated use of the same development panel must remain visibly the same panel, not independent confirmation. Display facts without labeling a hypothesis exhausted or prescribing the next experiment.
12. Regenerate derived history from `results.jsonl` after updates, closure, recovery, and reset. Do not maintain a separate PowerShell version of the table formatter.

### Software validation

- A new non-baseline closure missing assessment gets a clear validation message; baselines and old completed entries remain readable.
- Supported, contradicted, mixed, and inconclusive free-text assessments are faithfully persisted/rendered, without a Runner choice about lineage.
- Two measured checkpoints keep distinct settings/results regardless of request order. An unmeasured candidate stays unmeasured.
- Closed rows show actual decisions and assessments, not stale `awaiting analysis` or legacy placeholders.
- All current-campaign experiments remain discoverable after many entries, and revisions of the strategy do not rewrite prior predictions.
- Retry/upsert does not duplicate an experiment or its postmortem snapshot.

Commit/push: `feat: record hypothesis assessments and render usable campaign memory`.

## 9. Step 6 — Align instructions with scientific freedom and actual capabilities

### Objective and context

Continuation already exists in the schema. Its absence in two observed campaigns is a signal to remove contradictory framing, not grounds to force the next run to be a continuation. Preserve valid deliverables and operational boundaries while describing available choices accurately.

### Files

- `research/program.md`, `research/instruments.md`.
- `run_research.ps1`, including initial and retry prompts.
- `AGENTS.md`, only operational wording that contradicts the updated behavior.
- `README.md`, for lifecycle and maintenance descriptions.
- `tests/autoresearch/test_research_protocol.py`, `test_researcher_session.py`, `test_research_context.py`.

### Required changes

1. Remove `This is the complete task`, `bounded task`, and equivalent scientific framing from Researcher-facing messages. Preserve phase identity, allowed actions, required deliverable, and the instruction not to exit without it. A phase remains an operational boundary.
2. Preparation must expose continuation, intervention with fresh/transfer initialization, and replication as available operations. Say that code/configuration edits are required only when the selected operation calls for them. Do not imply a new parameter change is required each cycle.
3. Explain that fresh training does not by itself prove causality, and that further training from an existing policy is a legitimate research action. Do not mandate a paired training control, replication, or extra seed before continuing or accepting a model.
4. State the distinction between working and best known in terms of their roles: working identifies the line of investigation being pursued; best known records an explicit evidence-backed designation. Neither forces indefinite loyalty to a model or immediate competition after every run.
5. Analysis first interprets completed training and existing evidence. It can close without new simulation, request candidate-only measurement, or request comparisons when useful. Instrumentation and further rounds remain choices serving the Researcher's question.
6. Ask analysis to revisit the original expected/contradicting observations and update lessons and conditional next steps. Mechanistic investigation remains possible through existing logs, code inspection, instrumentation, and measurements; do not prescribe a diagnostic list, a failure sector, or an action sequence.
7. Keep phase tools visible with compact capability names and point to full syntax in `instruments.md`. Preserve log queries, structured artifact inspection, code inspection, lightweight analysis, scientific instrumentation, research evaluation, task reference, and optional comparison. Do not mandate using each tool.
8. Initial/retry prompts must expose the same capabilities and deliverable contract. Retries add the actual validation error and preserve valid unfinished work. Do not reintroduce an intervention requirement through the retry path.
9. Correct the closure schema in `instruments.md`: `code.action` includes `restore`, with `code.lineage` required only for that action; best-known evidence can cite compatible historical measurements for both models; omission preserves best known. State exact field types and conditional requirements.
10. Correct residual documentation drift: the scientific strategy has four required entries, not five; final assessment evaluates the frozen best-known model, not whichever model was selected as working.
11. Describe research/task-reference panels as development measurements. Repeated use informs development and is not independent held-out confirmation. The final benchmark remains the terminal assessment of a frozen policy; its result does not become a routine next-hypothesis input.
12. Avoid contradictory language banning use of a development panel for research while offering it as a research instrument. Protect its definition; distinguish using development evidence from changing the task or claiming independent final validation.
13. Keep environment/setup command guidance in `AGENTS.md` and exact instrument invocations in `instruments.md`. Keep phase prompts focused on current work and deliverables.

### Software validation

- Inspect generated preparation and analysis prompts, initial and retry, through existing session tests. Assert operational deliverables and continuation/measurement choices remain available without requiring a particular scientific decision.
- JSON examples/field tables match validator-accepted fixture requests for continuation, restore, historical comparison, working-only closure, and best-known designation.
- Preserve execution guards and phase dispatch. Do not run the Researcher to validate prompt quality.

Commit/push: `docs: align research phases with continuation and evidence-backed decisions`.

## 10. Step 7 — Refactor reset for recipe restoration followed by fresh experiment 1

### Objective and human workflow

The human wants to restore the complete recipe that produced the prior strong baseline, discard the current campaign state, and let the next ordinary launch train experiment 1 from scratch. Restoring a recipe must not import an old trained model, baseline analysis, or 97% designation.

Keep the existing mandatory `-Mode Fresh|Baseline` interface. Add an optional `-RecipeRef <git-ref>` valid only with `-Mode Fresh`:

```powershell
# Human commands after implementation; do not execute on this live checkout.
.\reset_research.ps1 -Mode Fresh -RecipeRef <verified-recipe-commit> -Force
.\reset_research.ps1 -Mode Fresh -Force
.\reset_research.ps1 -Mode Baseline -BaselineRef <prepared-baseline-commit> -Force
```

The first restores scientific recipe then clears campaign state. The second retains its existing meaning: clear campaign state and preserve current science. The third retains its distinct existing ability to reuse a trained baseline; it is not the selected next-campaign workflow. Do not add another worktree, automatically train a baseline, or silently use main/master as a source.

### Files

- `reset_research.ps1`: public parameters, PowerShell entry point, human-facing result.
- Add `research/reset_campaign.py`: a narrow human-only reset implementation using existing repository/protocol helpers.
- `research/runner_repository.py`, `runner_protocol.py`: reuse common scientific restoration, fingerprint/state validation, and derived history helpers.
- `research/runner_paths.py`, only if the existing path helpers need an additional durable artifact path.
- `researcher_copilot.py`, only to add the maintenance helper to existing script/module execution guards; corresponding focused guard tests in `tests/autoresearch/test_copilot_researcher.py`.
- `README.md`, `AGENTS.md`, `research/PROTOCOL_DECISIONS.md`.
- `tests/autoresearch/test_reset_research.py`, `test_lineage_roles.py`, `test_campaign_boundary.py`.

### Refactoring boundary

Keep PowerShell as the existing human command, forwarding validated arguments through `uv run` to one Python reset entry point. Move reset state serialization, artifact identity, recipe path planning, and history generation into Python so they use the same implementation as the Runner. Preserve existing filesystem confinement, dirty-tree refusal, file-lock handling, and commit/push behavior. Enforce stopped-campaign exclusion through the same named mutex used by `run_research.ps1` (`Local\RobotLearningAutoresearch`); the PowerShell wrapper acquires and holds it for the maintenance operation and releases it in `finally`. Do not rename or redesign the campaign lock. Do not implement a second fingerprint or scientific surface definition in the wrapper.

This helper is maintenance code and human-owned. Add `research/reset_campaign.py` to the explicit protected Runner paths and its script/module invocations to existing execution guards, with a focused test. It is not a new Researcher instrument. Resolve its configuration without importing/executing historical researcher modules during reset planning. Use subprocess validation after restoration when runtime imports are required.

### Fresh with a recipe source

1. Resolve the explicit ref to one immutable commit and report it. Validate argument combinations before mutation: RecipeRef is Fresh-only; BaselineRef and TrainingLogSource remain Baseline-only. Preserve `-Force` and clean-worktree requirements.
2. Determine the complete scientific restoration set using the same ownership and added/deleted file handling used for parent restoration in Step 2. Include reward, environment/training science, observations, policy I/O, trainer, training configuration, and researcher-owned tests.
3. Never restore the whole repository or the source's harness. Keep current dependencies, protected task/robot definitions, protocol documents, and maintenance implementation. Validate task compatibility before destructive work.
4. Verify referenced files and configuration are available. Compare actual effective configuration against historical artifact metadata when supplied as evidence of the chosen recipe; do not treat that artifact as a model to import.
5. Complete a read-only preflight before deleting anything: resolved source, file restoration/deletion set, current campaign status, target path confinement, reparse-point checks, relevant locks, writable outputs, and available Git provenance.
6. Protect the operation with the existing campaign exclusion mechanism. A running campaign causes refusal before mutation. Do not kill a campaign or delete its lock as a workaround.
7. Make a recoverable operation-specific backup of the exact files/state being replaced and record progress before destructive work. Confine all temporary/backup paths to the explicitly validated maintenance location. A mid-reset error must report how to recover; a reset must never silently leave old models associated with a new campaign ID.
8. Restore the recipe and its tests, including deletion of files introduced after that recipe within the scientific surface. Preserve human-owned implementation changes from this development branch.
   For the selected historical recipe, this explicitly removes the experiment-6 smoothing from `scenario/environment.py` and `scenario/policy_io.py`. Do not preserve it, reapply it, or translate it into a baseline default. Preserve the generic human-owned artifact/runtime mechanism and AutoResearch regression tests implemented in Step 4.
9. Initialize a new UUID and native v4 empty state using shared code: no working, no best known, no retained lineages, no pending analysis/measurement/closure/final request, no official result, and reset experiment allocation counters. Write `BASELINE_PENDING` so the next normal launch allocates experiment 1.
10. Clear current active campaign results, postmortems/strategy, evaluation artifacts, checkpoint roles/candidates, stale proposals/requests, training logs/recovery markers, and derived summaries according to the validated reset target set. Do not delete unrelated worktrees, environments, developer tools, or other project files.
11. Record the recipe source revision as human maintenance provenance, distinct from model lineage. Do not copy any source baseline role, score, evidence, selected checkpoint, campaign UUID, or experiment numbering into the new state.
12. Regenerate derived history with the shared Python renderer. Commit scientific restoration separately from the campaign reset state, and push each commit in accordance with the project's Git convention. Preserve a recoverable reset operation across failures; report local commit/push state accurately.
13. Finish with a factual description: source recipe revision, new campaign ID, fresh baseline pending, next experiment 1, and no training launched. Do not claim the future model will achieve exactly 97%.

### Historical recipe used in this discussion

`c46ec8951612b03c8906045803e33f5f98f2cae7` is the verified historical baseline closure commit, selecting `checkpoint-100352` at 97% on a 200-episode research panel with seed 1. Its artifact records fresh training with seed 0 and these effective runtime settings:

| Section | Values |
| --- | --- |
| Algorithm | `ppo` |
| Policy | `[64, 64]`, `tanh` |
| PPO | `n_steps=1024`, `batch_size=64`, `gamma=0.99`, `learning_rate=0.0003`, `gae_lambda=0.95`, `ent_coef=0.01` |
| Training | `n_envs=1`, `checkpoint_every_steps=5000`, requested budget 120,000 |

The reward constants at this revision are `PROGRESS_COEFFICIENT=10.0`, `CLOSENESS_COEFFICIENT=4.0`, `CLOSENESS_LENGTH_SCALE=0.05`, `ACTION_COST_COEFFICIENT=0.01`, `HOLD_PROGRESS_BONUS=50.0`, `HOLD_PROGRESS_EXPONENT=1.0`, `HOLD_EXIT_FORFEIT_FRACTION=0.0`, `OUTSIDE_BAND_WIDTH=0.01`, `OUTSIDE_BAND_PENALTY=0.1`, and `HOLD_COMPLETE_BONUS=50.0`. Restore their source implementation, not just these numbers.

These values are historical provenance, not new defaults to hard-code. A read-only diff during plan preparation found no differences between `fef60b8ab90c0c04c4f00d8a676e05527d74dfd8` (pre-training reset) and `c46ec8951612b03c8906045803e33f5f98f2cae7` under `robot_learning/`, `tests/scenario/`, `tests/training/`, or `research/current_params.json`. The selected artifact's effective runtime configuration matches the table. Recheck this provenance before presenting the human command; no restoration or live model evaluation is needed to verify it. If an unexpected difference is found, report it rather than silently selecting another recipe.

### Existing trained-baseline mode

1. Preserve Baseline mode's advertised purpose; do not remove it because the human currently chooses recipe restoration.
2. It must consume the durable v4 role paths produced by Step 1, validate complete model/runtime/normalization files, actual checkpoint steps, recipe provenance, and measurement identity before replacing the current campaign.
3. Reuse shared migration/state helpers. Remove PowerShell's separate fingerprint, partial role migration, and experiment-table implementation.
4. A legacy baseline may be imported only when its model/evidence binding can be verified from its preserved artifact and historical records. If identity cannot be established, refuse before mutation with a specific reason. Never infer identity solely from a checkpoint name, assign fingerprints to unrelated evidence, or rerun evaluation silently.
5. Preserve original measurement semantics and payloads; mark unsupported historical metadata explicitly. Do not manufacture compatible settings to satisfy best-known validation.
6. Fresh recipe restoration must never depend on any of these trained-baseline metadata requirements. A valid scientific source with no saved policy or evaluations is sufficient for RecipeRef.

### Software validation

All tests below execute reset only in temporary repositories with temporary bare remotes and stubbed campaign processes.

- Recipe A to current B: restore A's scientific code/config/tests and remove B-only scientific files, while B's harness/task files remain byte-identical.
- Fresh with RecipeRef yields empty v4 campaign state and a pending fresh experiment 1; no model, old score, strategy, evaluation, UUID, or experiment counter is imported.
- Fresh without RecipeRef preserves all current science exactly.
- A recipe commit without trained artifacts is accepted. A missing ref, invalid JSON, incompatible task, dirty tree, running campaign, locked file, or unsafe reparse target fails before destructive work.
- Simulated failure during restoration, state publication, commit, and push retains a usable recovery record/backup and never advertises a successful reset.
- Stub the next launcher dispatch to verify it selects the fresh-baseline path for experiment 1 and receives the restored configuration. Do not execute training.
- Baseline mode can reuse a newly published v4 fixture from a clean clone, including actual intermediate-checkpoint steps and evidence identity. An unverifiable legacy baseline fails before replacing the current state.
- No path outside the temporary repository/explicit backup scope is changed or deleted.

Commit/push: `feat: restore a scientific recipe before fresh campaign reset`.

## 11. Step 8 — Integration, protocol decision log, and final delivery

### Files

- `research/PROTOCOL_DECISIONS.md`: append dated decisions and reasons.
- `README.md`, `AGENTS.md`: reconcile operational ownership, saved artifact locations, reset commands, and validation scope.
- Relevant tests already listed, with at most narrowly focused additions under existing domain directories.

### Decision log content

Record the actual decisions, their scope, and the campaign evidence motivating them:

1. v4 selected/retained models must be Git-durable; ignored challenger references were insufficient.
2. Unchanged continuation restores the selected parent's complete recipe; ordinary transfer may intentionally apply changed science.
3. Historical evaluation reuse is identity/settings-based; comparison remains a Researcher choice.
4. Policy preprocessing is part of the saved inference contract, including per-episode state/reset.
5. New experiment postmortems revisit original predictions explicitly, with Researcher-owned conclusions.
6. Working and best-known decisions stay independent; comparable secondary diagnostics may support a reasoned designation without a Runner ranking formula.
7. Fresh RecipeRef reset restores science and starts experiment 1 without importing a trained baseline or its evidence.
8. Prompt cleanup exposes scientific options and preserves deliverable requirements.
9. Training-log query usage is confirmed; improving its targeting/output efficiency is deferred.

Do not claim these changes prove improved RL convergence. The human will judge that in a later campaign. Do not revise past campaign conclusions to make implementation appear successful.

### Required integration tests and checks

1. Run focused tests after each step with `uv run pytest <affected paths>`. Use the installed environment; do not install a new stack or change dependencies to hide failures.
2. Run syntax/lint/format checks on touched Python files and parse the PowerShell entry point. Avoid repository-wide formatting.
3. Run the complete project test suite once after integration; fix relevant failures and rerun only as necessary. Do not silently skip or weaken assertions for artifact integrity, task semantics, real executed restoration paths, or Git durability.
4. Include one temporary-repository integration path: recipe reset -> simulated fresh training output -> analysis closure -> published working/best-known artifacts -> changed recipe -> continuation from old parent -> historical comparison -> closure -> reload from a clean clone. Stub expensive processes. Assert file contents and persisted records, not only mocked call counts.
5. Test reload/recovery around accepted execution and closure publication; do not regenerate Researcher decisions after an accepted operation fails.
   Previously accepted persisted execution/closure plans must remain recoverable under their accepted contract. Do not retroactively demand a new hypothesis-assessment heading to resume an already accepted closure. New submissions use the updated requirements; completed historical records remain readable. Test this with fixtures, without migrating the interrupted real campaign.
6. Keep campaign-time validation selection unchanged. New harness regression tests do not create a new full-suite trigger for every reward or parameter change.
7. Compare the pre-existing dirty campaign files and ignored phase deliverables against the initial inventory/hashes. Restore none of them. Report any external change observed during development rather than attributing it to this implementation without evidence.
8. Confirm implementation Git commits contain only intended source/tests/docs and temporary fixtures are not committed. Push the last implementation commit.

Commit/push: `test: verify campaign restoration evidence and lineage persistence end to end` (include final documentation/decision-log corrections or commit them separately).

## 12. Coverage and handoff requirements

| Agreed topic | Covered here |
| --- | --- |
| New lineages missing from Git | Step 1; verify the active v4 path through a clean clone. |
| Old-parent continuation mixes recipes | Step 2. |
| Paired comparison cannot use existing evidence | Step 3. |
| Best-known closure conflicts with identity/measurement metadata | Steps 3 and 7, without weakening comparability. |
| Stateful action preprocessing missing from saved model | Step 4. |
| Prediction versus observed result not explicit | Step 5. |
| History rows lack v4 outcomes / memory too weak | Step 5. |
| Working vs best-known and continuation still poorly exposed | Steps 3 and 6. |
| Residual phase framing and incomplete schemas | Step 6. |
| Recipe-only restart and existing reset compatibility | Step 7. |
| Reasoned mechanistic analysis / scientist chooses measurements | Steps 5 and 6 through existing capabilities, without a new compulsory instrument. |
| Broad/repeated training-log queries | Deferred, not part of implementation. |

The final Copilot report must contain:

- Worktree, new branch, base revision, and all implementation commits with their push status.
- A completion table for Steps 1-8 with affected files and actual software checks/results.
- The verified recipe source and any difference between baseline training code and its later closure commit; distinguish recorded recipe equality from a guarantee of reproducing 97%.
- The exact human command for recipe restoration after the human resolves their dirty campaign state, but do not execute it.
- Confirmation that no real campaign, training, model evaluation, benchmark, or live reset was launched, and the status of pre-existing campaign changes.
- An explicit deviations section: each deviation, the original requirement, what differs, why, and its effect. If none, say none. Do not silently replace a decided behavior with a preferred architecture. An unresolved conflict affecting scientific behavior must be reported, not hidden by weakening tests or fabricating metadata.
- Any remaining software blocker and any separately deferred item. The log-query improvement belongs to the deferred list.

No success claim about the Researcher's strategy or final policy quality belongs in the implementation report. Those are evaluated by the human in the next campaign, using the newly restored recipe and the existing Researcher model.
