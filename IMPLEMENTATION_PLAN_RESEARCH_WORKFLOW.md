# Implementation plan: research progression, optional measurement, and independent lineages

## 1. Purpose and implementation boundary

Implement this plan in the repository containing this file. It completes the reasoning/memory work already present and implements the previously discussed workflow and lineage changes as one coherent release.

The objective is to help the Researcher build a policy that meets the human-defined task. The Researcher must be able to understand an experiment, pursue a promising model, change direction, request evidence, and compare models when that comparison serves its scientific decision.

The observed failure motivating this work is specific: after the restored baseline, eight of eleven experiments repeated unchanged fresh training. The proposals cited real evidence and contained populated reasoning fields, but the campaign repeatedly re-established training variability without investigating its mechanism or developing another lineage. The completed reasoning fields improved traceability; this campaign did not demonstrate an improvement in research effectiveness.

Treat the following as implementation requirements:

- The Researcher chooses the scientific action, the parent, the measurements, and whether to pursue or abandon a direction.
- The Runner validates execution contracts, executes requests, and preserves the decisions and their provenance.
- Continuing an unchanged method is a first-class operation. A scientific experiment need not change a parameter or a source file.
- Working on a model and claiming that it is the best known model are separate decisions.
- Understanding a completed training run is mandatory scientific work; launching another evaluation simulation is optional.
- The Researcher can request several measurement rounds within that analysis, each serving its question.
- Reused research/reference panels are development evidence. The official benchmark is a terminal assessment of a frozen model.
- Memory must expose observations, previous interpretations, and reusable lessons without turning an interpretation into a Runner verdict.
- The Researcher decides when evidence is sufficient and a direction is exhausted. Do not add mandatory stop-condition fields, replication quotas, fixed exploration cycles, automatic hypothesis rejection, or a Runner rule that tells the Researcher which scientific action to take.
- Keep the current model and reasoning configuration. Token optimization is outside this change.
- Keep the installed SB3, MuJoCo, and Gymnasium stack. Use the existing modules and storage mechanisms; do not introduce a framework, plugin system, registry, dependency injection, vector database, or separate strategy service.

Implementation does not authorize launching, resuming, or resetting any real campaign, modifying the live scientific intervention, running a real training job, evaluating a real campaign model, or running a real benchmark. Copilot must stop after software validation. Preserve the reference worktree and the current campaign artifacts. Run implementation tests only against temporary fixtures, stubbed training/evaluation processes, and temporary repositories.

At inspection time, this worktree was on `codex/research-reasoning-memory`, with completed experiment 12 and an unfinished proposal for experiment 13. `research/research_state.json`, `robot_learning/scenario/reward.py`, and `tests/scenario/test_reward.py` had uncommitted changes; ignored `research/proposal.json` also existed. These are interrupted-campaign state and scientific work. Leave them exactly where they are in the source worktree. Do not stash, commit, reset, clean, restore, copy, or delete them. They are not inputs to the harness implementation.

The inspected HEAD was `c252e7d`. The implementation steps below are technical work packages, not a renumbering of the three previously agreed remediation points:

| Agreed remediation point | Implementation coverage |
| --- | --- |
| Correct Point 1: useful reasoning and memory | Steps 4 and 5; preserve the existing evidence/parent reasoning contract and repair the information presented to the Researcher. |
| Point 2: understand before choosing measurements | Steps 2, 3, 5, and 6; analysis supports optional measurements, repeated investigation, and a distinct final assessment. |
| Point 3: pursue a working lineage independently of best known | Steps 1 and 3, with persistence/recovery/baseline compatibility in Steps 7 and 8. |

Keep the existing proportional validation policy during campaigns. Adding implementation regression tests must not make every scientific experiment run the full AutoResearch suite. The full-suite instruction in this plan applies to completing this harness implementation.

### Required Git branch and worktree setup

Do the implementation in a new sibling worktree. The source worktree must remain intact as the reasoning-memory reference and interrupted campaign record.

Use these exact identities:

- Source branch: `codex/research-reasoning-memory`
- Verified source commit: `c252e7d743abd5fc8b6b300ebf1ebad7f8b7feec`
- New branch: `codex/research-workflow-remediation`
- New worktree: `C:\Users\cyril.beurier\code\robot-learning-research-workflow-remediation`

Before creating anything, verify that the source branch still resolves to the verified source commit. If it does not, stop and report the new commit; do not silently choose another base. Verify that the target branch and worktree do not already exist. If either exists, inspect and report it; do not overwrite, delete, reset, or force-update it.

Create the new branch and worktree from the verified committed source state. Do not create the branch from the dirty working tree and do not use `origin/main`, `main`, or another branch as the base. Creating a worktree from the commit intentionally excludes all uncommitted and ignored campaign files listed above.

The implementation plan itself is currently untracked in the source worktree. After creating the new worktree, copy only `IMPLEMENTATION_PLAN_RESEARCH_WORKFLOW.md` from the source worktree to the new worktree root. Do not copy any other uncommitted or ignored file. Commit the plan as the first commit on the new branch and publish the branch:

```text
docs: add research workflow remediation plan
```

Push it with upstream tracking to `origin/codex/research-workflow-remediation`. This instruction explicitly authorizes creating the branch/worktree and committing and pushing this implementation branch. It does not authorize commits, pushes, stashes, resets, or cleanup in the source `codex/research-reasoning-memory` worktree.

After setup, run every inspection, edit, validation, commit, and push from the new worktree. At the start of the final report, include the new worktree path, branch name, base commit, and confirmation that the source worktree's pre-existing dirty files were left unchanged.

## 2. Verified implementation starting points

The following existing behavior must be changed deliberately rather than worked around in wording:

| Current location | Current behavior | Required consequence |
| --- | --- | --- |
| `research/program.md`, `Fixed cycle` | Training must be followed by evaluation, then a separate closure phase; phases cannot be skipped. | Replace the two post-training phases with one analysis phase that can request measurements or close the experiment. |
| `research/runner_protocol.py`, `requested_measurements()` | Every evaluation request requires at least one measurement. | Keep this requirement for an actual measurement request, but allow analysis to finish using a lineage decision without submitting an evaluation request. |
| `run_research.ps1` | `pending_evaluation_request` always causes an evaluation-design session; closure gets a separate session. | Dispatch one analysis session which may produce either an evaluation request or a closure decision. |
| `research/run_experiment.py`, `apply_previous_result_decision()` | Selecting a candidate copies it over `ACCEPTED_DIR` and updates the same state used for the champion. | Preserve working lineage and best-known lineage independently. |
| `research/runner_protocol.py`, `training_parent()` | `accepted` and retained IDs are training parents; evaluation calls the accepted artifact `champion`. | Expose the same role identifiers for training, evaluation, and lineage selection. |
| `research/run_experiment.py`, `execute_pending_evaluations()` | `measured[0]` becomes `candidate_metrics` and the apparent experiment score. | Record checkpoint-specific evidence. Do not turn the first measured checkpoint into the experiment's representative or best model. |
| `research/build_research_brief.py` | Displays accepted state prominently, five recent cards, then compressed memory. | Lead with the current result and working direction; expose all campaign experiments through a factual compact index. |
| `research/run_experiment.py` and `runner_repository.py` | The result is appended before closure; subsequent lineage decisions mostly update state. | Persist the completed decision into the authoritative experiment record and regenerate its derived views. |
| `research/program.md`, final benchmark paragraph | A failed official benchmark sends the Researcher back to research. | Finish the campaign after a completed official assessment, whether it succeeds or fails. |
| `research/instruments.md` | Already supports `training`, `continuation`, `replication`, log queries, and optional paired comparisons. | Preserve these capabilities and make their availability explicit in the appropriate phase prompts. |

Use these function names as navigation anchors, not fixed line numbers. Read their callers before changing signatures.

## 3. Target lifecycle and contract decisions

Implement this lifecycle:

```text
experiment preparation
    -> validated training / continuation / replication request
    -> Runner training and checkpoint preservation
    -> Researcher post-training analysis
         -> measurement request -> Runner measurements -> same analysis
         -> postmortem + lineage decision -> Runner closes experiment
    -> next experiment preparation

An explicit final-benchmark request at closure:
    -> Runner evaluates the frozen best-known artifact
    -> campaign finished, with success or failure recorded
```

Analysis may close an experiment without running any new measurement. An evaluation request always requests real measurements; do not represent this choice with a fake zero-episode evaluation or an empty measurement list.

Within analysis, the Researcher may inspect logs, inspect existing artifacts, perform lightweight local analysis, and modify researcher-owned measurement instrumentation. Preparing the next training intervention remains in experiment preparation. The global objective and available follow-ups remain visible across that handoff.

There are still two phase deliverable filenames. Reuse them:

- `research/evaluation_request.json`: request another measurement round for the open experiment.
- `research/proposal.json`: either the preparation proposal or, during analysis, the lineage-only closure decision.

Exactly one actionable deliverable may be submitted by an analysis session. The postmortem accompanies a closure decision. The Runner must reject conflicting deliverables before executing either one.

## 4. Step 1 — Separate working lineage and best-known lineage

### Objective

Make it possible to pursue a promising model without replacing the best-known model, and to return to a preserved model and its scientific recipe later.

### Files

- `research/runner_paths.py`
- `research/runner_repository.py`
- `research/runner_protocol.py`
- `research/run_experiment.py`
- `research/runner_execution.py`, only where parent metadata is consumed
- `tests/autoresearch/test_execution_contract.py`
- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_policy_runtime.py`, only for artifact-retention integration
- Add `tests/autoresearch/test_lineage_roles.py` for the role-specific invariants.

### State representation

Advance the campaign state schema from version 3 to version 4. Replace the authoritative `accepted_*` role fields with:

- `working_lineage`: a lineage record or `null`.
- `best_known_lineage`: a lineage record or `null`.
- Existing `retained_lineages`: reusable alternatives.

A lineage record contains the following facts, with nullable historical provenance only where explicitly allowed by the migration step:

| Field | Meaning |
| --- | --- |
| `artifact` | Canonical repository-relative path to the complete saved policy artifact. |
| `fingerprint` | Existing complete-artifact fingerprint, including runtime and normalization files. |
| `origin_experiment` | Experiment that trained this checkpoint. |
| `candidate` | Its original checkpoint name. |
| `parameters` | Effective configuration used to train it, not the current worktree configuration. |
| `scientific_commit` | Git revision preserving the scientific code, configuration, and scientific tests used by that training. |
| `training_steps` | Cumulative training transitions represented by this checkpoint. |
| `evaluation_artifacts` | References to measurements of this exact artifact. |
| `reason` | Researcher explanation for its role or retention. |

Store summaries per measurement/panel. Do not give a model a context-free success percentage or silently pool different instruments and evaluation semantics.

Reuse the existing campaign checkpoint archive paths. Working and best-known records may refer to the same artifact. They must not depend on a mutable `accepted` directory which is overwritten whenever the working lineage changes. Existing historical `accepted` paths remain readable; newly selected checkpoints can stay at their archived paths.

Use these identifiers in all new Researcher-facing contracts:

- `working`: the current working lineage.
- `best_known`: the current best-known lineage.
- Existing retained IDs.
- Current-experiment checkpoint names during analysis.

Resolve each identifier once to a concrete artifact and fingerprint when accepting a request. Changing a role later must not change the identity of an already accepted request or recorded measurement. If two identifiers resolve to the same fingerprint, display that they are the same model; do not describe them as independent contenders.

Historical `accepted` and `champion` identifiers are handled only by the compatibility path in Step 8. New documentation and new requests use `working` and `best_known`.

### Selection and persistence

1. Selecting a working lineage never replaces the best-known lineage implicitly.
2. Changing the best-known lineage requires a separate explicit selection and its supporting development evidence, described in Step 3 below.
3. Neither role is selected automatically by success ranking. The Runner executes the Researcher's choice.
4. The first baseline closure selects the working model. If the Researcher has measured a baseline candidate and designates it as best known, both roles initially refer to that candidate. If analysis closes without measurements, the working model exists and best known remains unset.
5. Keep all artifacts referenced by either role or by retained alternatives. Deduplicate cleanup by resolved path/fingerprint. Never remove model weights, runtime, normalization, or replay state still used by another role.
6. Selecting an early checkpoint records that checkpoint's actual steps plus its parent's steps. Do not record the entire experiment budget for an early checkpoint.
7. Preserve the existing policy-runtime isolation behavior for observations, action transformations, loader, and normalization.

### Scientific recipe provenance

A saved inference runtime is not the complete recipe needed to continue an old scientific direction. Preserve both:

1. After validation and effective parameter resolution, publish a scoped scientific commit before training starts if the scientific surface changed. Reuse `commit_paths()` and the existing commit/push policy. This commit contains scientific code/configuration/tests, not campaign memory or model artifacts. Record the resulting revision in the experiment and checkpoint metadata maintained by the Runner. If there is no scientific delta, reference the existing revision.
2. Keep `code_parent_commit` as the pre-intervention rollback anchor. Do not replace it with the new training revision.
3. At closure, preserve the trained recipe revision even when the worktree is reverted or evaluation instrumentation has since changed.
4. Extend the existing code decision with restoration by a known lineage ID, as specified in Step 3. Restore only the researcher-owned scientific surface, including its tests and configuration, from that lineage's recorded revision. Added/deleted scientific files must be handled. The Researcher never supplies an arbitrary Git revision.
5. Keep the model-parent decision and the next active code decision explicit. Transfer may intentionally apply a changed recipe to an older model. `continuation` means further training without a learning-method change; if returning to an old recipe is necessary, perform the lineage code restoration before accepting that continuation.
6. Preserve the separation between scientific commits and campaign-memory/artifact commits. A push failure must leave an identifiable pending operation rather than silently advance research.

This is a narrow use of the existing Git provenance functions, not a new code-versioning service.

### Software validation

- A candidate with lower measured success can become working while best known remains byte-identical.
- A measured candidate can become best known while a different working lineage is preserved.
- Working and best known may share one artifact safely.
- A retained model is selectable as working, best known, a training parent, and an evaluation candidate.
- Cleanup preserves both role artifacts and all explicitly retained artifacts.
- Selecting an intermediate checkpoint preserves the correct actual cumulative step count.
- A lineage records the recipe used for training even after instrumentation changes and a later revert.
- Restoring a lineage restores scientific code, parameters, and corresponding tests together, including additions/deletions, and preserves harness/task files.
- Incompatible policy interfaces still fail through the existing artifact/transfer contracts; do not hide incompatibility by adapting dimensions or silently starting fresh.

## 5. Step 2 — Implement post-training analysis with optional measurements

### Objective

Allow the Researcher to decide what evidence is useful before spending evaluation compute. Preserve complete analysis and lineage recording when no new simulation is requested.

### Files

- `research/run_experiment.py`
- `research/runner_protocol.py`
- `research/runner_repository.py`
- `run_research.ps1`
- `researcher_session.ps1`, only if its generic deliverable status interface requires adjustment
- `tests/autoresearch/test_researcher_session.py`
- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_execution_contract.py`
- Add `tests/autoresearch/test_post_training_analysis.py` for lifecycle behavior.

### State and dispatch

Use one persisted `pending_analysis` object in state version 4. It carries the existing experiment context: checkpoint inventory, training log references, original proposal/result, effective parameters, parent information, scientific revisions, completed measurement references, and any accepted measurement plan with its partial progress.

Replace the mutually exclusive `pending_evaluation_request` / `pending_researcher_decision` states for new operations. Both old states map into `pending_analysis` during explicit compatibility handling.

Implement these transitions:

1. Successful training creates `pending_analysis` and preserves all candidate artifacts and raw logs.
2. With no accepted execution plan, the launcher invokes the Researcher for post-training analysis.
3. A valid measurement request is frozen in `pending_analysis` and executed by the Runner.
4. Completed measurements are persisted and the execution plan is cleared. The experiment remains in `pending_analysis`; the next session may measure again or close.
5. A valid closure decision is applied, its postmortem/evidence is persisted, and `pending_analysis` is cleared only after completion is durable.
6. The next preparation session can then submit a continuation, an intervention, or a replication.

Add a Runner preflight `--check-analysis-deliverable` which checks the current phase, file exclusivity, and the appropriate existing request/closure validation. Use the same validation path during execution. PowerShell must not duplicate JSON validation rules.

The preflight reports whether the accepted deliverable is `measurement` or `closure`. File presence alone is insufficient. If both files contain actionable current-phase submissions, return a clear conflict error and execute neither. Consume/remove processed control files at the existing successful boundaries so the previous training proposal cannot look like a closure submission.

### Measurement request

Preserve `experiment`, `question`, `reason`, `measurements`, and optional `paired_comparisons`, including the existing instrument-specific schema and three-distinct-model limit.

For new requests, remove `need_more_evidence`: every completed measurement round returns to analysis. The choice to close is now the closure deliverable, not a boolean predicting whether the next round will be needed. Compatibility may read the old field in previously accepted pending plans, but new requests must follow the new documented schema.

`measurements` still requires at least one entry. The model catalog includes current candidates, working, best known, and retained lineages. No comparison or model is inserted automatically. Resolve and preserve the artifact identity, instrument identity, panel settings, and evaluation semantics with each measurement, using the existing fingerprints.

A measurement request's `question` states what is unknown; its `reason` explains what decision the requested information can inform and why existing evidence is insufficient for that decision. This is free scientific reasoning, not an enumerated list of permissible motivations.

### Evidence and closure without measurements

Extend postmortem evidence validation to accept existing current-campaign training logs, checkpoint metadata, the experiment's recorded training result, and completed evaluations. A closure based on logs must not fail because no evaluation artifact exists.

Validate that cited files exist and relate to the current experiment or explicitly identified parent evidence. Require at least one source belonging to the current experiment. Do not require every detailed artifact to be cited or opened, and do not require a particular log command to have been called.

Do not synthesize an evaluation score from reward/training success. Record `not evaluated` where appropriate. Missing metrics are not zero success.

Within analysis, preserve the existing ownership rule for measurement instrumentation. Analysis cannot silently edit the next training recipe. A needed training change belongs in the subsequent preparation proposal.

### Software validation

- Training -> closure from logs -> next preparation invokes no evaluator.
- Training -> candidate-only measurements -> analysis works without best-known evaluation.
- Analysis can perform two or more measurement rounds before closure.
- Completion of a measurement round never automatically requests another measurement or comparison.
- Conflicting deliverables fail before any execution or artifact cleanup.
- Missing/malformed deliverables get the existing bounded retry with the same phase and factual error.
- An execution failure resumes accepted execution, not Researcher proposal generation.
- Ctrl-C during measurement preserves completed artifacts and unfinished progress; restart resumes only the missing work.
- A closure can preserve an unmeasured working candidate, with metrics explicitly absent.

## 6. Step 3 — Make exploration and best-known selection independent decisions

### Objective

Let the Researcher pursue, retain, or abandon a scientific direction using available evidence, while making a best-known designation explicit and evidence-backed.

### Files

- `research/runner_protocol.py`, especially `plan_previous_result_decision()` and `training_parent()`
- `research/run_experiment.py`, especially closure planning/application
- `research/runner_repository.py`
- `tests/autoresearch/test_lineage_roles.py`
- `tests/autoresearch/test_research_protocol.py`

### New closure schema

Retain the `previous_result_decision` wrapper and the existing `continue_from` field for the working-lineage choice. The schema is:

```text
previous_result_decision:
  experiment: current experiment integer
  continue_from: available current checkpoint, working, best_known, or retained ID
  reason: non-empty explanation of the working-lineage choice
  code:
    action: keep | revert | restore
    reason: non-empty explanation
    lineage: required only for restore; working, best_known, or retained ID
  best_known: optional object
    candidate: available model ID
    reason: non-empty explanation of the designation
    evidence: non-empty list of existing development-evaluation artifact paths
  retain: optional existing list of {candidate, id, reason}
  remove_retained: optional existing list of retained IDs
  request_final_benchmark: optional boolean
```

Document exact JSON types and conditional fields in `instruments.md`. The block above is a schema description, not JSON to submit verbatim.

Resolve all IDs against the state and model inventory before applying any changes. For example, `code.lineage: working` references the pre-decision working recipe, not a newly assigned role.

Semantics:

- Omitted `best_known` preserves the existing best-known record; it does not promote `continue_from`.
- With no previous best known, a designation requires measured evidence for the proposed model but no invented comparison against a nonexistent reference.
- Replacing a different best-known artifact requires cited comparable development evidence for both models. Evidence may already exist; do not require a new simulation in that experiment.
- Check artifact identity, instrument, task/panel semantics, and compatible comparison settings using the existing metadata. Do not pool research and task-reference outcomes together.
- The Runner validates that the cited evidence actually concerns the two models. It does not impose a success delta, p-value, replication count, episode count, or automatic winner.
- A working-lineage decision may rely on training logs and candidate metadata alone. It must not create a best-known designation as a side effect.
- The Researcher may abandon the current candidate by selecting an existing working/best-known/retained lineage and choosing the appropriate code action.
- Selecting a working lineage does not commit the Researcher to a fixed number of future experiments. It can later continue, change method, branch, or abandon it.
- No mandatory condition-of-abandonment field, hypothesis-status enum, decision-if-confirmed field, or strategy-cycle object is introduced.

`training_parent` accepts `working`, `best_known`, and retained IDs. Keep `kind: continuation` with `initialization: transfer`; accept it with zero code/configuration changes. Keep ordinary interventions compatible with either fresh or transfer. Do not suggest that fresh alone isolates a causal effect or that additional training is scientifically invalid.

### Software validation

- Continuing the same recipe is accepted with no scientific changes.
- Fresh initialization and transfer with a coherent intervention remain accepted.
- Closing an unmeasured exploration cannot silently update best known.
- Best-known replacement can use compatible historical development measurements of unchanged artifact identities.
- Mismatched artifact or panel evidence is rejected; lack of a statistically significant improvement is not a Runner veto.
- Best-known selection and working selection can target different models in one closure.
- Restoration and role selection are resolved before applying mutations and remain restartable.
- Retained IDs cannot be removed while still referenced by working or best known; role artifacts survive any removal of a redundant retention label.

## 7. Step 4 — Repair the experiment record and rebuild useful memory

### Objective

Make the latest learning, previous results, and live research direction easy to use. Show repeated work factually without automatically deciding that it should stop.

### Files

- `research/runner_repository.py`
- `research/run_experiment.py`
- `research/build_research_brief.py`
- `research/runner_console.py`
- `research/runner_protocol.py`, for memory/evidence parsing only
- `tests/autoresearch/test_scientific_reasoning.py`
- `tests/autoresearch/test_research_context.py`
- `tests/autoresearch/test_console_presentation.py`
- `tests/autoresearch/test_campaign_boundary.py`

### Authoritative experiment records

1. Keep `results.jsonl` authoritative and `EXPERIMENTS.md` derived.
2. Maintain one current record per `(campaign_id, index)` for new-schema experiments. Add a narrow atomic record-update function which replaces that experiment's existing record or inserts it if absent. Preserve unrelated historical records. Do not introduce a general event store.
3. Save the original proposal reasoning and strategy snapshot without retrospectively editing them. Update lifecycle status, completed measurements, and closure decision as the experiment progresses.
4. Persist the final working choice, explicit best-known decision if any, code decision, postmortem reference, and role identities at closure. Cards must not keep saying `awaiting researcher analysis` after closure.
5. Preserve a candidate list with per-checkpoint steps, training facts, and measurement references. Remove the `measured[0]` assignment as the primary experiment result. Historical scalar summaries remain readable and are identified as legacy summaries, not reinterpreted as the selected model.
6. Show both checkpoint values where a run improves from one measured checkpoint to another. Do not replace the first-checkpoint problem with an automatic maximum-score selection.
7. Group replication facts by `replication_of`, displaying actual method/configuration provenance where available. A replication label groups experiments; it is not proof of recipe equivalence.

### Brief order and content

Generate these sections in this order:

1. **Current phase and latest event.** Current experiment, lifecycle status, and available next deliverables.
2. **Latest experiment.** Operation, parent, intervention, checkpoint progression, measurements by model/panel, and closed decision if available. During analysis, expose the complete current checkpoint inventory and raw-log paths.
3. **Working lineage.** ID, origin checkpoint/experiment, actual cumulative steps, scientific recipe reference, available measurements, and the Researcher's reason for pursuing it.
4. **Current scientific direction.** The Researcher-authored synthesis and links to the relevant historical findings.
5. **Campaign experiment index, newest first.** One compact factual row per experiment in this campaign: ID, operation/family, parent, intervention, measured checkpoints or no measurement, final action, and links to detail. Remove the hard-coded last-five-only scientific horizon.
6. **Repeated operations.** Factual groupings/counts for replications and repeated families, with per-checkpoint outcomes and links. Do not write `exhausted`, `failed strategy`, or a suggested next intervention on behalf of the Researcher.
7. **Reusable lineages.** Stable IDs and facts needed to select a parent or measure a retained model.
8. **Best-known model.** Artifact identity, provenance, development results with their panel identities, and the Researcher's designation reason. Mark explicitly when it is also the working model.
9. **Official report**, only when one exists; terminal campaign status is also visible at the top.

Do not enforce a line-count target. Keep rows concise and link detailed evidence rather than duplicating large histories. Do not truncate the current scientific synthesis mid-sentence. Do not copy every past postmortem verbatim into the brief. The complete experiment index and linked records make older work discoverable.

Remove the instruction that history should be read only when the brief identifies a genuine ambiguity. The Researcher decides which historical evidence is relevant. Expose source paths without directing it toward a specific diagnosis.

Repeated measurements of one immutable model on the same deterministic panel are repeated observations of the same cases, not additional independent evidence. Label the panel/instrument/seed/episode count and preserve that distinction in summaries. Do not pool duplicate episode identities to inflate sample size. No new campaign-wide cache is required for this change.

### Postmortem and scientific synthesis

Keep historical experiment entries as observations and interpretations made at that time. Preserve the existing `Result`, `Observed behavior`, `Interpretation`, and `Evidence inspected` headings.

Clarify that `Interpretation` includes what was learned, limits of that conclusion, and what it changes in the current direction. A lack of progress may lead the Researcher to revisit an earlier interpretation; the Runner does not assign a hypothesis status.

For the revisable scientific section, keep these four required headings:

- `Direction`
- `Lessons and limits`
- `Open questions`
- `Conditional next steps`

Read historical `Reconsider when` content as part of the synthesis, but cease requiring that heading in newly written sections. Do not replace it with a mandatory stop condition. The Researcher may naturally discuss reconsideration in its free-text strategy.

State explicitly that evidence can establish the existence of variability without identifying its cause, and that another replication is useful only if the Researcher can explain the additional scientific information it seeks. This is a distinction between questions, not a rule that bans replication or mandates continuation.

The existing proposal `reasoning` fields remain. Clarify `strategy_link` to explain how inspected prior results affect the current choice, including when the direction remains unchanged. Do not add a new required schema of strategic outcomes.

### Software validation

- Two measured checkpoints remain distinct, in training-step order, regardless of measurement-request order.
- A closed experiment has a final decision in both JSONL and generated Markdown.
- Record updates preserve original hypotheses and observations, and do not duplicate experiments after recovery.
- The brief exposes all current-campaign experiment IDs and links, with newest first.
- Older lessons remain reachable after more than five experiments.
- Researcher synthesis is faithfully shown as interpretation, including uncertainty; the Runner fabricates no scientific conclusions.
- A change of working lineage leaves best-known reporting unchanged unless explicitly designated.
- A change of best known updates its identity and evidence everywhere; no stale champion score remains.
- Unmeasured models render as unmeasured, not zero percent.
- Repeated identical-panel observations do not double the evidence count.
- Earlier campaigns do not enter the current campaign brief or aggregate statistics.

## 8. Step 5 — Make instructions and tool exposure match the implemented workflow

### Objective

Keep the overall research objective visible while making the next executable action unambiguous. The prompts must expose usable options rather than reward completion of an isolated paperwork task.

### Files

- `research/program.md`
- `research/instruments.md`
- `run_research.ps1`
- `AGENTS.md`, for role/path and command references affected by this change
- `README.md`, for the human-facing lifecycle summary
- `research/PROTOCOL_DECISIONS.md`
- `researcher_copilot.py`, only if an existing phase name or command guard must recognize the updated lifecycle; preserve model/tool permissions
- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_researcher_session.py`
- `tests/autoresearch/test_copilot_researcher.py`, only for affected dispatch/guard behavior

### `program.md`

- State that the campaign seeks a useful learned policy. Method attribution and training reproducibility are legitimate questions when they advance that effort, not universal prerequisites to developing a model.
- Replace the fixed evaluation/closure sequence with the lifecycle in Section 3.
- Explain working lineage versus best known, including further training of a promising but not yet superior model.
- Give continuation, intervention, and replication equal status; no fresh/transfer default and no mandatory mutation.
- Explain analysis before requesting simulations. Existing logs or measurements may be enough to continue a working lineage or abandon a candidate.
- Keep evidence obligations and revisable memory. Do not require mechanically opening every artifact or using every tool.
- Describe research and task-reference measurements as development evidence, and the official assessment as terminal.
- Remove `bounded task`, `This is the complete task`, and equivalent framing that makes the phase deliverable the scientific objective. Preserve clear operational ownership and the requirement to produce a valid phase deliverable.

### `instruments.md`

- Document exact updated request schemas, conditional fields, role IDs, the restoration action, and phase availability.
- Document that a measurement request returns to analysis and closure is a separate choice in that same phase.
- Give the log-query tool's actual invocation and output contract. Use a PowerShell-compatible single-line example: `uv run python research/query_training_log.py --experiment <id> --from-step <start> --to-step <end>`.
- Make saved-parent selection explicit. Distinguish continuing a recipe from applying a changed recipe to existing weights.
- Preserve the scientific scope of each instrument and clearly label development evidence versus terminal assessment.
- Do not put a candidate-versus-best-known measurement request in a default example. Use neutral placeholders and the field table; no instrument or model is preselected in the template.

### PowerShell prompts

Use the same substantive instructions for the initial phase and its retry. A retry adds the validation failure and preserves valid unfinished work.

**Experiment preparation prompt:**

- Current campaign/experiment and its global task context.
- Read the authoritative documents and current brief.
- Available actions: continue an unchanged method; change the method from a selected parent or fresh start; replicate to investigate training variability.
- Available evidence tools: training-log query, structured-artifact queries, code inspection, and lightweight local analysis.
- Deliverable: one valid preparation proposal, plus scientific edits only if the chosen operation requires them.
- Preserve execution prohibitions and the requirement to finish the deliverable rather than exit after diagnosis.

**Post-training analysis prompt:**

- Current experiment completed training; determine what happened and what scientific action follows.
- Available tools: checkpoint inventory and raw-log query, structured-artifact analysis, instrumentation edits, research measurement, task-reference measurement, and optional paired comparison.
- Available outcomes: another measurement request, or postmortem plus a closure decision that chooses working/code/retention and optionally best known.
- Candidate-only measurement and closure without new measurements are valid. No champion is automatically required.
- Describe further training as a valid next experiment after closure. Do not instruct the Researcher to produce the next training proposal in the current analysis response.
- Preserve the operational rule that the Runner executes training, measurements, Git mutations, and final assessment.

These compact lists expose capabilities by phase. Full syntax remains in `instruments.md`. Do not create a new tool registry or copy JSON schemas into PowerShell.

Remove the distinct `evaluation design` and `lineage decision` research-session prompts from normal version-4 execution; their responsibilities are represented in the analysis prompt. Keep actionable missing-deliverable retry messages and the existing stop-on-second-invalid-deliverable behavior.

Update `PROTOCOL_DECISIONS.md` with the reasons for these changes, the limitations observed after Point 1, the combined implementation scope, and the fact that scientific sufficiency remains a Researcher decision. Distinguish software checks from the future campaign's scientific validation.

### Software validation

- Prompt tests verify available actions, expected deliverables, and operational boundaries rather than exact prose or line counts.
- Preparation accepts unchanged continuation without demanding an intervention.
- Analysis exposes the log-query capability and both deliverable routes.
- Retry retains the same scientific capabilities instead of narrowing the task to evaluation by default.
- Existing execution guards still prevent Researcher calls to Runner/training/evaluation commands.
- Documentation examples validate against the actual request validators.

## 9. Step 6 — Keep the official benchmark out of the optimization loop

### Objective

Preserve a clear distinction between development measurements and the final task verdict. Returning a failed official verdict to an automatically continuing Researcher would allow that verdict to guide subsequent optimization.

### Files

- `research/run_experiment.py`, `execute_pending_final_benchmark()`
- `research/runner_protocol.py`
- `research/runner_repository.py`
- `run_research.ps1`
- `research/build_research_brief.py`
- `research/runner_console.py`
- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_researcher_session.py`
- `tests/autoresearch/test_execution_contract.py`

### Behavior

1. Keep the existing explicit `request_final_benchmark` closure request.
2. Resolve its target to the post-decision best-known artifact, not automatically the working artifact. Reject the request if no best-known model has been designated.
3. Freeze its fingerprint and preserve the existing runtime/task integrity checks.
4. Once an official evaluation completes, persist a terminal campaign assessment with the exact model identity and its verdict. Stop automatic research on both success and failure.
5. Keep `GOAL_REACHED` reserved for success. A completed-but-failed assessment must stop through persisted terminal campaign state without pretending the objective was reached.
6. An interrupted/failed evaluator process is an operational failure, not a completed scientific assessment; preserve retry/recovery of that execution.
7. Reject new research proposals for a terminal campaign. Human-initiated creation/reset of a campaign remains the way to resume research after final assessment.
8. Research and task-reference measurements remain optional development instruments. Do not change their seeds, task constants, distributions, or success semantics in this work.
9. Reusing a development panel is allowed; never label repeated exposure as independent validation. A new evaluation seed changes the sampled cases, not the training realization. Do not claim that fresh evaluation seeds establish reproducible training.

### Software validation

- An official success terminates the campaign and marks the goal reached.
- An official failure terminates the campaign without marking the goal reached.
- Restarting either completed campaign launches no Researcher session or training.
- Interrupted official execution resumes the same frozen artifact.
- The final target remains best known when working points to a different model.
- Existing benchmark semantics and runtime-isolation tests remain unchanged in meaning.

## 10. Step 7 — Make the combined workflow recoverable

### Objective

Preserve artifacts, accepted deliverables, and history across interruption at the new boundaries. This is part of making the lineage separation usable, not a redesign of process control.

### Files

- `research/run_experiment.py`
- `research/runner_repository.py`
- `research/runner_protocol.py`
- `run_research.ps1`
- `researcher_session.ps1`, if required by the updated deliverable route
- `tests/autoresearch/test_execution_contract.py`
- `tests/autoresearch/test_researcher_session.py`
- `tests/autoresearch/test_lineage_roles.py`

### Behavior

- Persist an accepted closure plan, resolved artifact IDs, and its application progress in the existing pending operation before applying copies/restoration/role changes. Use a narrow pending-operation record, not a generic transaction engine.
- Preserve source artifacts until role state, scientific changes, and result history are durable.
- A restart resumes an accepted measurement/closure execution instead of asking the Researcher to decide again.
- Clearing pending state and cleaning unreferenced candidates happen after the durable decision. Repeated execution must not add duplicate retention entries, rewrite a role to a missing artifact, or duplicate the experiment record.
- Keep the original scientific parent until closure application is complete. The newly recorded training recipe revision must not alter revert semantics.
- Validate paths and referenced artifacts before destructive cleanup. Continue using existing process-stop and atomic-write helpers.

### Software validation

Use fault injection in temporary repositories at: accepted plan persisted; scientific recipe committed; role state saved; history updated; commit/push failure; cleanup started. After restart, each case must preserve the selected models and produce one completed logical decision. Use a temporary local bare remote where Git publication behavior needs to be exercised.

No real campaign or remote branch is used for these tests.

## 11. Step 8 — Preserve prepared baselines and handle existing campaign state explicitly

### Objective

Allow the new harness to consume a prepared baseline without changing its trained policy, scientific recipe, parameters, or evidence. Implementing the harness must not itself migrate or reset the current campaign.

### Files

- `research/runner_repository.py`
- `research/runner_protocol.py`
- `research/run_experiment.py`, for an explicit maintenance entry point if needed
- `reset_research.ps1`
- `research/build_research_brief.py`
- `tests/autoresearch/test_reset_research.py`
- `tests/autoresearch/test_campaign_boundary.py`
- `tests/autoresearch/test_lineage_roles.py`
- `researcher_copilot.py` and `tests/autoresearch/test_copilot_researcher.py`, only to preserve the human-only boundary of the maintenance command

### Version 3 compatibility

- Provide an explicit human-only state migration operation, `--migrate-research-state`, in the existing Runner CLI. It is not a Researcher tool and must remain blocked by the Researcher command guard. Do not invoke it against this live worktree during implementation.
- Preflight the conversion without changing science or policy bytes. Back up the original state and preserve campaign ID, experiment counters, original records, measurements, and pending control files.
- Map the legacy accepted model to working. If it has recorded development measurements, initialize best known to the same model with a factual legacy-origin designation; do not invent stronger evidence or a new scientific decision. Leave best known null for an unmeasured legacy model.
- Map legacy `accepted` training-parent submissions to `working` and legacy `champion` references to the same pre-migration artifact. Perform this only for already-existing pending submissions/records; new requests use the documented new IDs.
- Convert legacy pending evaluation or closure state to `pending_analysis`, preserving accepted plans and partial measurements. Previously accepted closure submissions without `best_known` preserve the migrated best-known model; they must not acquire an implicit promotion.
- New-protocol validation must not require rewriting an already accepted old measurement plan during recovery. Interpret its recorded semantics and return to analysis after completion. Translate an unexecuted old control submission explicitly during migration, preserving its original content in the backup; validate it before any execution.
- Obtain recipe provenance only from verifiable recorded Git/artifact evidence. If an old recipe cannot be identified, record `scientific_commit: null`; the artifact remains usable through its saved runtime. Exact recipe restoration for that lineage returns a specific missing-provenance error instead of guessing a commit. Do not silently retrain, adapt, or discard it.
- An old completed official result is recorded as prior terminal-assessment exposure and the converted campaign is terminal. Do not automatically run further research using a revealed official result.
- Repeating the migration is a no-op after successful conversion. Validation-only commands must never migrate state implicitly.

### Reset compatibility

- `-Mode Fresh` continues to preserve the current scientific source/parameters and clear campaign artifacts. It creates a version-4 initial state with null working/best-known records and a pending baseline. Keep the current branch/worktree semantics.
- `-Mode Baseline -BaselineRef ...` accepts a valid measured closed experiment-1 baseline in supported old or new state format. It restores the exact scientific files/tests/configuration, policy/runtime, logs, and baseline evidence from that source, while retaining the current harness.
- Translate role metadata after restoring an old baseline, before finalizing the reset. Both roles identify the same measured baseline artifact; do not retrain or recompute its evidence.
- For a baseline restore, the selected source commit is an explicit verifiable scientific recipe revision. Record it for later restoration.
- Extend cleanup/restore lists for the new role references and terminal state; do not accidentally remove an artifact shared by roles before validating the baseline source.
- Preserve the script's existing safety checks and publication behavior. Do not add a new reset mode or change which parameters count as the human's initial recipe.

### Software validation

- Restore a version-3 measured baseline into the new harness and compare source files, scientific tests, policy/runtime/normalization bytes, effective parameters, and evidence with the source baseline.
- Restore a version-4 measured baseline with both roles referring to the same model.
- Fresh reset preserves scientific files and initializes only campaign state.
- State migration preserves pending measurements, current proposals, counters, and policy fingerprints.
- Unavailable recipe provenance does not become an invented revision.
- Migration and reset validation failures leave the original campaign intact.
- No compatibility operation launches training or a Researcher session.

## 12. Implementation order and review checkpoints

Implement the numbered steps in order, with the following dependency clarification: Step 3's closure schema completes the role mechanics from Step 1 and the analysis dispatcher from Step 2. Their intermediate code is not a campaign-ready release. Steps 4–8 complete the memory, prompts, terminal assessment, recovery, and compatibility integration.

The implementation can be organized into reviewable local changes covering:

1. role/provenance representation and artifact preservation;
2. unified analysis, closure schema, continuation, and history updates;
3. brief/memory/tool prompts and documentation;
4. terminal assessment, recovery, and baseline compatibility;
5. complete software verification and final review.

Do not run experimental campaigns between these partial changes. The scientific unit to evaluate is the completed workflow with the same prepared baseline and same Researcher model.

Before finalizing, search all callers/readers of `accepted_*`, `champion`, `pending_evaluation_request`, `pending_researcher_decision`, `need_more_evidence`, and `candidate_metrics`. Update active code to the new semantics and confine old names to documented compatibility/history handling. This includes console output, CLI checks, reset fixtures, and session validation. Do not perform unrelated cosmetic renaming.

## 13. Verification and completion criteria

Software tests protect execution, storage, and lifecycle invariants. They do not certify the Researcher's scientific reasoning. Copilot's validation scope ends with these software tests. The human will later launch and assess any campaign used to evaluate Researcher behavior. Do not launch a campaign, invoke the Researcher for behavioral validation, build a multi-snapshot LLM evaluation suite, demand particular hypotheses from the model, or introduce a model-grading service.

For implementation verification:

1. Run focused tests for each changed responsibility using `uv run pytest ...`.
2. Run `uv run ruff check` and formatting only on changed Python files. Parse modified PowerShell scripts using the PowerShell parser.
3. Run the full project test suite once after integration. Investigate failures against the intended new behavior. Replace obsolete tests that assert mandatory evaluation or merged accepted/champion roles with the relevant new invariant. Do not weaken unrelated scientific, task, artifact, or restoration tests merely to obtain green output.
4. All launcher/Runner integration tests must use temporary state/artifacts and stubbed training/evaluation. Do not start MuJoCo training or evaluate a real saved campaign policy as part of implementation validation.
5. Verify working-tree scope: the implementation must preserve the pre-existing unfinished scientific edits and all real campaign artifacts. Do not run the real reset script, migration command, campaign launcher, or benchmark as a validation shortcut.

The implementation should expose enough factual state for the human to inspect the following questions in a separately launched future campaign. These are acceptance questions for the human, not commands or tests for Copilot:

- Does the Researcher use the preceding experiments to revise or maintain a coherent direction, rather than repeat their conclusions indefinitely?
- Does it investigate training dynamics when its question concerns the learning process?
- Does it sometimes continue or retain a promising lineage without making an immediate best-known claim?
- Does it request measurements for identifiable decisions and reuse existing evidence when sufficient?
- Does the new workflow improve actual policy progress from the same baseline?

Do not use fewer tokens, fewer calls, more transfer requests, or fewer evaluations alone as proof of improvement. A well-justified fresh run or detailed evaluation can still be the correct scientific choice.

## 14. Required Copilot final report

Report:

- The resulting lifecycle and the two lineage roles in plain language.
- The files changed and the behavior each group implements.
- The exact new/changed deliverable fields and state compatibility behavior.
- Software tests run, their results, and any unresolved failure with its cause.
- Confirmation that real campaign state, models, existing scientific edits, and the reference worktree were preserved during implementation.
- How the human can prepare the same baseline for the future validation campaign, without executing that operation.
- Explicit confirmation that Copilot did not launch, resume, reset, train, evaluate, or benchmark a real campaign.
- Every intentional deviation from this plan, with the requirement, actual implementation, reason, and consequence. If a deviation would change Researcher authority, benchmark use, mandatory evaluations, lineage semantics, or campaign data, report it as unresolved rather than silently substituting a new design.
- Scientific effectiveness remains unproven until the human runs and reviews a later campaign. Do not run that campaign and do not describe passing software tests as proof that the reasoning bias is fixed.

Commit and push only when the human explicitly requests publication.
