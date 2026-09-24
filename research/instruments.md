# Researcher instruments

This file defines the evidence sources and phase deliverables available to the Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

`research/brief.md` indexes the current campaign state, parameters, available
models, retained lineages and repository-relative artifact paths.
`research/postmortems.md` records Researcher-authored observations and
interpretations. Referenced structured artifacts contain the detailed outputs
of completed measurements.

Artifact paths exposed by the brief and research contracts are relative to the
repository. Use them directly from the repository working directory; do not
reconstruct them as absolute paths.

`jello` is available through the researcher environment for JSON and JSONL
artifacts. Its expressions use Python syntax, not `jq` syntax. Researcher-owned
analysis tools and read-only implementation inspection are also available.
Inspection does not change the ownership permissions in `AGENTS.md`.

## Model the robot and task

**Phase:** Preliminary campaign start, before baseline training or campaign
evidence. Write `research/scientific_model.md` once per campaign. Separate these
three registers explicitly in the document:

- **Established facts:** What the robot, task, and implementation actually
  specify, with the relevant source or constraint identified. Do not treat
  anticipated training outcomes as observations.
- **Physical consequences:** Implications derived from those facts, with the
  reasoning and assumptions stated separately from the facts.
- **Unknowns:** Quantities, dynamics, limitations, or outcomes not established
  by the available facts; do not fill these gaps with invented measurements.

The deliverable must exist and contain non-whitespace content. The launcher
validates that requirement; it does not judge the scientific substance. The
model is read-only after this phase for the rest of the campaign, and a fresh
campaign reset removes it so the next Researcher writes a new one.

For the official benchmark result, use `research/brief.md` under **Current
status -> Reported result**. Its durable metrics and artifact reference remain
in `research/research_state.json`.

### Query Stable-Baselines3 logs

```powershell
uv run python research/query_training_log.py --experiment <id> --from-step <start> --to-step <end>
```

All arguments are required. Bounds are inclusive. Results preserve separate training attempts and are not aggregated.

Use `uv run` for lightweight analysis and focused checks on researcher-owned code. Persistent outputs must remain in researcher-owned paths.

## Modify the scientific system

Saved policies carry their own inference contract. `scenario/policy_io.py`
defines observation construction and mapping from policy outputs to physical
robot commands; use these same functions in training. The current checkpoint
writer in `training/checkpoint.py` exports this contract, the loader and
normalization into `policy_runtime.pkl` beside the weights. Preserve that export
when replacing training or checkpointing code. Resolve scientific dependencies
before export rather than importing mutable project code during inference.
Stateful observation or action preprocessing belongs in `PolicyIO`, with its
episode state cleared through the existing reset hook. Construct independent
mapping state for each environment and apply the saved mapping exactly once.
The Runner and evaluators use each artifact's contract, not the current model's
observation layout. Task mechanics and success measurement remain shared.

During experiment preparation, the Researcher may modify any researcher-owned scientific code or configuration permitted by `AGENTS.md`.

Tests are outside the Researcher's surface. The Researcher does not create,
modify or maintain test files, and it never repairs a test file on the Runner's
instruction. Any path under `tests/` in a proposal is rejected as a path the
Researcher does not own; such paths must be dropped from the proposal, because
they are not the Researcher's changes to make.

During post-training analysis and its optional refinement rounds, the Researcher
may modify researcher-owned measurement and analysis code before requesting
another measurement round. The existing request flow can measure current
candidates and eligible saved lineages. Changes affecting training apply to the
next experiment.

## Request measurements

**Phase:** Post-training analysis or experiment preparation.

During analysis, use this request for the current experiment's candidates or
eligible saved lineages, initially or in an optional refinement round while
closing the current trained experiment. During experiment preparation, a request
may measure only eligible saved lineages (`working`, `best_known`, or a retained
ID); it may not name the candidates of an experiment that has not run, because
those do not exist yet, and it must omit the `experiment` field. A completed
preparation round returns to preparation and is recorded under the upcoming
experiment. Researcher-owned instrumentation may be changed before submitting
the request.

`question` and `reason` are non-empty strings describing the request as a whole.
`measurements` selects the instruments and models to run. `paired_comparisons`
selects comparisons to compute from compatible measurements and is optional.

Write `research/evaluation_request.json`:

```json
{
  "experiment": "<current experiment integer; must be omitted during preparation>",
  "question": "<non-empty scientific question>",
  "reason": "<non-empty reason>",
  "measurements": [
    {
      "instrument": "<research_evaluation | task_reference>",
      "candidate": "<model exposed by the brief or listed in the candidate inventory>",
      "selection": "<why measuring this model is useful>",
      "omitted_alternative": "<optional: an available model left outside this request, or null>",
      "<instrument-specific fields>": "<documented values>"
    }
  ],
  "paired_comparisons": [
    {
      "candidate": "<measured model>",
      "reference": "<other measured model>"
    }
  ]
}
```

If the Researcher submits a measurement request, `measurements` must contain at
least one entry, and it may name at most three distinct models.
`paired_comparisons` is optional. These are request validation constraints; they
do not require a measurement request or limit an experiment or campaign.

Every measurement requires its own non-empty `selection` stating why measuring
that model is useful. Measurements of the same model may have different
selections. The Runner checks that `selection` is present, not whether its
reasoning is sound.

`omitted_alternative` is optional. When present it names an available model left
outside the entire request; the Runner checks only that the identifier is
available and is not measured in the same request.

A `research_evaluation` panel is the half-open episode interval
`[seed, seed + episodes)`. A request may reuse an identical panel or use a panel
disjoint from every recorded research panel; partial overlap is rejected.
Several measurements may share one identical panel. A panel overlapping the
protected benchmark episodes is rejected, and historical records remain readable.

Identical reuse is permitted and is accounted for: every reuse is reported with
its history so it cannot read as fresh evidence. The scientific consequence of
reuse is stated in `research/program.md`.

Within one request, multiple measurements of the same model count as one toward
the distinct-model limit. This includes different seeds, episode counts, labels,
or instruments applied to the same model.

### `research_evaluation`

- Ownership: researcher-owned evaluation code and instrumentation, changed with
  the research recipe.
- Settings: request-provided `episodes` (positive integer) and `seed` (integer);
  optional `label` (string).
- Measured task: the current researcher-owned task and environment mechanics.
- Outputs: per-episode success and any researcher-defined evidence the scenario
  evaluator emits.
- Artifact semantics: measurement identity covers the evaluator, environment and
  task mechanics, and instrumentation outside the saved artifact.

### `task_reference`

- Ownership: human-owned panel and evaluator, not changed with the research
  recipe.
- Settings: optional `label` (string); the fixed panel's episodes and seed are
  not request-configurable.
- Measured task: the protected original task, independent of researcher-owned
  environments and evaluation code.
- Outputs: per-episode success plus target geometry and outcomes.
- Artifact semantics: the panel is fixed and versioned, so measurements remain
  comparable across research changes. Panel definition is in
  `robot_learning/benchmark/reference_contract.py`; execution and reported
  quantities are in `robot_learning/benchmark/reference_evaluation.py`.

Add one entry per model and instrument.

A paired comparison uses the accumulated `research_evaluation` outcomes for the
two named models. It compares their shared recorded episode identities within
matching evaluation semantics; incompatible sides are rejected. Overlapping or
repeated episodes count once in pooled summaries. Summary `episodes` reports
distinct coverage; `episode_executions` and `repeated_episodes` report execution
count and repeated coverage separately. Conflicting outcomes for the same
deterministic episode are rejected. Pooled comparison uses success only;
per-episode `reward_total` is not comparable across a reward change.

Each completed measurement round returns to the phase that requested it: post-
training analysis for an analysis request, experiment preparation for a saved-
lineage preparation request. New requests do not use `need_more_evidence`;
closing is a separate closure proposal in the same phase. Legacy accepted
requests that contain it remain recoverable.

## Request training

**Phase:** Experiment preparation.

Configure researcher-owned code and `research/current_params.json` as needed,
then write one `research/proposal.json`. The common required fields are `kind`,
`family`, `initialization`, `reasoning`, and one of `hypothesis` or
`scientific_question`:

```json
{
  "kind": "<training | continuation | replication>",
  "family": "<non-empty hypothesis-family identifier>",
  "hypothesis": "<non-empty proposition the experiment tests>",
  "scientific_question": "<non-empty open question; use instead of hypothesis>",
  "initialization": "<fresh | transfer>",
  "reasoning": {
    "evidence": [
      {"source": "<existing repository-relative file>", "observation": "<what was observed there>"}
    ],
    "expected_observation": "<the observation that would change the next decision, and what it would change>",
    "initialization_reason": "<why fresh, or why transfer from this training_parent>",
    "objective_link": "<why this investigation is useful for the campaign objective given current evidence>",
    "scientific_model": {
      "observation": "<observed behavior or open question grounded in current campaign evidence>",
      "connection": "<section and specific fact, physical consequence or unknown in research/scientific_model.md, and why it matters or offers no useful distinction>",
      "alternatives": "<plausible competing explanations, including training or parameter explanations when relevant>",
      "diagnostic_decision": "<what measurement would change the intervention, if any, and why this training run is now more informative than requesting it>"
    }
  },
  "change": "<non-empty scientific intervention; training only>",
  "training_parent": "<string; required for transfer, otherwise omit>",
  "training_seed": "<non-negative integer; optional except for replication>",
  "replication_of": "<positive current-campaign experiment integer; replication only>",
  "params": "<object; optional parameter overrides>"
}
```

Exactly one of `hypothesis` or `scientific_question` is required; both are
accepted and neither changes how the experiment is run or validated. Additional
`reasoning` keys are accepted and recorded without validation.

| Kind | Meaning | Required or conditional fields |
| --- | --- | --- |
| `training` | Trains a changed scientific recipe for any investigation type. | `change` must be a non-empty description; the intervention must also be a researcher-owned code change or non-empty `params`. Transfer requires `training_parent`. |
| `training` with `extends_lineage: true` (adjusted continuation) | Continues an eligible lineage's training while changing the recipe. It starts from the parent's weights and trains the current worktree science plus `params`. The hypothesis is a prediction about how that adjustment changes continued training. | Requires `initialization: "transfer"`, `training_parent`, a non-empty `change`, and `extends_lineage: true`; a researcher-owned code change or non-empty `params` is still required. |
| `continuation` | Continues an eligible lineage's training on the selected recipe. Without `params` it is the unchanged recipe; with `params` it is the parent's restored recipe plus those overrides. The hypothesis is a prediction about continuing training: further progress, plateau, or degradation. | Requires `initialization: "transfer"` and `training_parent`. Code changes and `change` are forbidden. |
| `replication` | Starts the current unchanged method from scratch and groups the run with an earlier experiment for replication evidence. The hypothesis is a prediction about reproducibility or variance of the learning process. | Requires `initialization: "fresh"`, a positive integer `replication_of` naming an existing experiment in the current campaign, and an explicit non-negative integer `training_seed`. Code changes, `params` and `change` are forbidden. |

`training_seed` is optional for ordinary training and continuation, and must be
a non-negative integer when present. `params` is optional for ordinary training
and for `continuation`, where it adjusts the restored parent recipe; `params` is
not accepted for `replication`.

Experiment records distinguish `training_budget_steps` (requested) from
`completed_training_steps` (actually completed in that experiment). Rollout
boundaries may make the completed count exceed the request. A selected lineage's
`training_steps` instead records its accumulated training through the selected
checkpoint.

Every `reasoning` field required above must be non-empty content, and `evidence`
contains at least one source/observation pair. Cite inspected campaign artifacts,
logs, postmortems or code with precise observations; these are not restricted to
evaluation results. `source` is a file path without a line-number suffix or
fragment; put the relevant experiment, checkpoint, step range or code location in
`observation` as needed. In `scientific_model`, distinguish what the frozen model
establishes from what the current campaign observed. Identify the relevant
section of `research/scientific_model.md` and explain its relevance, or name a
model consideration and explain why it offers no useful distinction for this
question. Do not infer a policy's failure cause from the
model alone. If a feasible measurement on a saved lineage could change the
intervention, request that measurement before proposing training; otherwise
explain in `diagnostic_decision` why training directly is the better
discriminator (or why existing measurements already answer the question). This
does not privilege a physical intervention over training, parameter, or
learning-process investigations. The Runner checks the presence and shape of
this reasoning and the existence and confinement of evidence sources, not
scientific merit or whether a measurement would have been preferable. This
contract applies equally to training, continuation and replication, not to the
automatic baseline.

The campaign's Scientific strategy section must exist before submission. The
Runner validates its three labels and snapshots the section with `reasoning` in
the experiment record. Existing historical records without these fields remain
readable.

An eligible `training_parent` must be exposed by the brief as `working`,
`best_known`, or a retained lineage ID. Continuing a lineage and changing the
recipe are independent choices. A `training` proposal with
`initialization: "transfer"` sets `extends_lineage: true` to continue that
lineage while training the current worktree science and `params`; its record
names the extended lineage and records that the current science, not the
parent's recipe, was in effect. A `continuation` restores the parent's recipe
before training: without `params` it is the unchanged recipe, and with `params`
it applies those overrides on top of the restored recipe. Its record names the
extended lineage and records that the parent's recipe was restored.

### Training-parent eligibility and retention

Eligibility is a provenance invariant, not a preference about a form field. A
`training_parent` resolves only through `working`, `best_known`, or a retained
lineage ID because only those names carry a closure-produced record with all the
facts training and recovery require: the complete inference artifact (`model.zip`
and its preprocessing runtime), a `fingerprint` that still matches the bytes on
disk, a `scientific_commit` for restoring the recipe that produced the parent,
and the effective `parameters` in force when it was trained. A raw candidate
checkpoint has none of those records, so the Runner cannot name its recipe or
verify its identity and it cannot serve as a parent.

The usable-parent set is also the surviving-weights set. At closure,
`finalize_pending_v4_closure` removes `model.zip`, `vecnormalize.pkl`,
`replay_buffer.pkl` and `policy_runtime.pkl` from every candidate that is not
named `working` or `best_known` and is not explicitly retained. Retention is
therefore the only mechanism that turns a candidate into a future
`training_parent`; a candidate that receives no role can never be extended,
re-measured, or compared against later, and its removal is irreversible.
Retention has no budget.

The `reasoning` object contains the common and type-specific fields shown in the
schemas. `evidence` is a non-empty array of source/observation objects. Every
listed type-specific string, `initialization_reason`, and `objective_link` is
non-empty, except that `alternative` and `contradicting_observation` may be a
`not_applicable` object carrying a non-empty reason. An optional
`reasoning.confidence` of `strong`, `moderate` or `weak` qualifies a
confirmatory or diagnostic prediction only. Their scientific use is defined in
`research/program.md`.

The automatic baseline trains the unchanged method from scratch for 120,000 steps.

Runner recovery resumes the interrupted experiment; it is not a continuation.

The current replication operation records the relationship through the positive
integer `replication_of`, which must name an existing experiment in the current
campaign. It groups the new run with the referenced experiment for replication
evidence; it does not restore that experiment’s code or configuration and does
not claim exact replay.

A `replication_of` group therefore records related evidence. It does not
establish an exact reproduction of a previous learning trajectory. A fresh run
of a recipe previously exercised through transfer does not reproduce the
transferred learning trajectory; it tests whether the current recipe can learn
from fresh initialization. Scientific claims about replication must use that
narrower interpretation.

## Conclude the campaign

**Phase:** Experiment preparation.

Preparation may end without a new experiment. Write `research/proposal.json`
containing only a `campaign_conclusion` object:

```json
{
  "campaign_conclusion": {
    "action": "<request_final_benchmark | no_further_experiment>",
    "reason": "<non-empty reason for the decision>"
  }
}
```

`request_final_benchmark` submits the standing `best_known` lineage for the
official final assessment. It requires a designated best-known model and reuses
the closure decision of the same name: the official benchmark runs once and the
campaign ends after its verdict. Its `reason` is the terminal rationale for the
request. `no_further_experiment` records the Researcher's judgement that no
further experiment is warranted without requesting that assessment; it ends the
campaign. Neither outcome creates an experiment record,
an experiment-index row or an intervention count. A `campaign_conclusion` is
accepted only while no measurement, analysis, closure or official assessment is
pending; each pending phase requires its own deliverable.

A conclusion resolves no science, so it is accepted only while the researcher's
scientific surface matches the preparation anchor. Revert or resolve any
outstanding researcher-owned change first; unlike a training proposal or a lineage
decision, a conclusion neither publishes nor restores a recipe.

A preparation phase that has already executed a measurement round on saved
lineages may not conclude: it owes an experiment proposal. The round was
requested because its result would change the next decision, and in this phase
that decision is which experiment to prepare. Concluding is available from a
preparation phase that spends no measurement round, from experiment closure
through `request_final_benchmark`, and whenever no further experiment may be
prepared.

When the experiment budget is exhausted, no further training experiment may be
prepared, but a campaign conclusion remains legal regardless of any measurement
round already spent. The Runner commits the decision before
it publishes any terminal status, so an interrupted conclusion is resumed rather
than inherited as a published terminal state.

## Record the postmortem

**Phase:** Experiment closure.

In the same file, maintain one revisable section for the active campaign. It can
also be edited during experiment preparation. Revise the existing section in
place rather than appending another section with the same campaign heading.
The exact heading and labels are:

```markdown
## <Campaign ID> / Scientific strategy

**Current synthesis:** <present interpretation of relevant campaign evidence>

**Lessons and limits:** <reusable findings, source references and scope; or what remains unknown>

**Open questions:** <uncertainties not yet resolved>
```

All three labeled entries must contain text and may span multiple lines. Their
scientific meaning is defined in `research/program.md`. The Runner checks the
section's structure, associates the active campaign section with the proposal,
and displays it in the brief. It does not author scientific content. The legacy
`Direction` label remains readable as a synthesis, and historical experiment
entries and strategy sections remain readable.

Append to `research/postmortems.md`:

```markdown
## <Campaign ID> / Experiment <integer>

**Result:** <concise result>

**Observed behavior:** <factual observations>

**Hypothesis assessment:** <compare the original prediction with what was observed; state whether the hypothesis is supported, partially supported, weakened, contradicted, or inconclusive, and the limits of that conclusion>

**Interpretation:** <scientific interpretation>

**Evidence inspected:** <artifact paths from this experiment>
```

The heading format is `## <Campaign ID> / Experiment <integer>`, where `<Campaign ID>` is the current campaign UUID. This format allows experiments with the same number from different campaigns to be uniquely identified in the postmortem history.

Evidence references are Researcher-authored scientific content. The Runner does
not validate cited path tokens because naming an artifact cannot establish that
it was inspected or understood. An unmeasured checkpoint is unmeasured, not zero
success.
New non-baseline entries require a non-empty `Hypothesis assessment`. Its wording
and conclusion belong to the Researcher; the Runner checks only that it is
present. This assessment does not determine saved-policy usefulness, recipe,
lineage, retention, or the decision to request the official benchmark. Fresh
baselines are exempt, and historical entries remain readable.

## Resolve lineage

**Phase:** Post-training analysis, after the postmortem.

Write a lineage-only `research/proposal.json`:

```json
{
  "previous_result_decision": {
    "experiment": "<current experiment integer>",
    "continue_from": "<current checkpoint, working, best_known, or retained ID>",
    "reason": "<non-empty scientific reason>",
    "code": {
      "action": "<keep | revert | restore>",
      "reason": "<non-empty reason>",
      "lineage": "<working | best_known | retained lineage ID; restore only>"
    },
    "best_known": {
      "candidate": "<available model ID>",
      "reason": "<non-empty designation reason>"
    },
    "retain": [
      {
        "candidate": "<available non-active candidate>",
        "id": "<stable identifier>",
        "reason": "<non-empty reason>"
      }
    ],
    "remove_retained": [
      "<retained-lineage identifier>"
    ],
    "request_final_benchmark": "<boolean>",
    "terminal_reason": "<non-empty reason; required when request_final_benchmark is true>"
  }
}
```

`best_known`, `retain`, `remove_retained`, and `request_final_benchmark` are
optional. Omitted `best_known` preserves the existing best-known lineage; it does
not promote `continue_from`. This request selects the working model, chooses the
scientific recipe action, and manages retained lineages. Unretained model
artifacts are removed; their recorded history and measurements remain.

If `best_known` names the current best-known model, the designation is accepted
idempotently. If it names another available model, the Runner resolves that
model's recorded measurements from the current campaign state. A new designation
requires at least one recorded measurement for the selected model; the Runner
checks only that a measurement exists, not whether the evidence is scientifically
sufficient and not whether scores compare favorably.

Omitting `request_final_benchmark` or setting it to `false` allows the campaign
to proceed after closure. Setting it to `true` requests terminal assessment of
`best_known`; the Runner ends the campaign after either `goal_reached` or
`goal_not_reached`. The result is not available to a later hypothesis. The
scientific decision rule for requesting assessment is defined in
`research/program.md`.

When `request_final_benchmark` is `true`, `terminal_reason` is required and must
be non-empty. It is the terminal rationale for the irreversible request, distinct
from the working-lineage `reason`. The Runner validates only that it is present
and non-empty; it renders it back with the frozen model so the decision is
explicit rather than a bare flag. Omit `terminal_reason` when a final benchmark is
not requested.

`experiment` is an integer. `continue_from` and both `reason` values are
non-empty strings. The compatible field name `code.action` controls the complete
researcher-owned scientific recipe: researcher-owned source and
`research/current_params.json`. `keep` keeps the experiment's complete
scientific recipe; `revert` restores the scientific parent's complete recipe;
and `restore` restores the complete recipe associated with the explicitly named
eligible lineage. For `restore`, `code.lineage` is required; for `keep` and
`revert`, omit `code.lineage`. The exact currently valid parent and restore
identifiers are listed in `research/brief.md`. `best_known` requires exactly a
candidate string and reason string. The candidate must be an available model
identifier. When a new model is selected, the Runner resolves its recorded
measurements and stores those paths in the lineage. `retain` is an array of
candidate/id/reason objects, `remove_retained` is an array of unique retained IDs,
and `request_final_benchmark` is a boolean. `terminal_reason` is a non-empty
string required with a `true` request.

## Request the official benchmark

Set `request_final_benchmark` to `true` and give `terminal_reason` in
`previous_result_decision`.

When the request is accepted, the Runner emits a confirmation card and the brief
records a **Pending terminal assessment** section naming the frozen `best_known`
lineage — its candidate, artifact, origin experiment, accumulated training steps,
scientific commit and recorded measurements — together with the terminal reason.
The decision is irreversible, but the Runner does not add a reversal or a second
verdict: both `goal_reached` and `goal_not_reached` are legitimate campaign
outcomes.

After applying the lineage decision, the Runner assesses the frozen best-known
model and writes the terminal verdict to `research/brief.md`. The campaign ends
after either verdict. This operation does not produce evidence for another
hypothesis.
