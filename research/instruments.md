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
  "addresses": "<expected_observation | exploratory; required during post-training analysis>",
  "question_revision": {
    "question": "<replacement experiment question>",
    "reason": "<why the frozen question is revised>",
    "evidence": [
      {"source": "<existing repository-relative file>", "observation": "<what was observed there>"}
    ]
  },
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

`addresses` is required for a post-training analysis request and omitted during
preparation. It states whether the request addresses the experiment's frozen
expected observation (`expected_observation`) or is deliberately exploratory
(`exploratory`). Both values are legal and the Runner records the address on the
completed round; it does not require an exploratory request to justify itself
against the frozen question.

`question_revision` is optional and only legal in a post-training analysis
request. When the experiment's frozen question no longer fits the evidence, it
replaces that question on the experiment's question ledger and appends the
revision, reason and evidence to the ledger's revision history. All three fields
must be non-empty, and the evidence array must contain at least one
source/observation pair. The ledger keeps every earlier question, so a revision
preserves provenance rather than rewriting history.

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

A measurement whose `candidate` is the current `working`, `best_known`, or a
retained lineage ID and whose `research_evaluation` panel exactly matches
another measurement's panel in the same request is the paired-comparison control
for that round. It does not count toward the three-model limit, which continues
to bound new-candidate exploration at three. A saved lineage measured on a panel
no other measurement in the request uses still counts toward the limit.

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

## Experiment question ledger

Each non-baseline experiment carries one persistent question ledger, created
from the proposal's hypothesis or scientific question, its expected observation
and its cited motivation, and frozen and persisted when training is accepted.
The ledger is identified by a fingerprint of the proposal and experiment; the
Runner validates that identity and the presence of the Researcher's fields but
never judges the evidence or conclusion.

The brief shows the frozen experiment question and expected observation before
the candidate metrics. Measurement rounds record whether they address the
expected observation or are exploratory and the ledger identity they belong to,
so the completed round's artifact references stay linked to the experiment's
original question. The Runner does not select covariates or compute
hypothesis-specific conclusions.

A measurement request may revise the frozen question through `question_revision`
(see "Request measurements"); the ledger keeps the earlier question and the
revision's reason and evidence. Closure records a Researcher-authored
disposition of the expected observation in the experiment postmortem (see
"Record the postmortem"); the disposition is attached to the ledger without
affecting policy usefulness, best-known designation or objective-level success.

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
    "objective_link": "<why this investigation is useful for the campaign objective given current evidence>"
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
`observation` as needed. The Runner checks file existence and confinement to this
repository, not the scientific conclusion or proof of inspection. This contract
applies equally to training, continuation and replication, not to the automatic
baseline.

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

**Phase:** Campaign action selection (experiment preparation), opened after every
experiment closure.

After a closure the Runner always opens this phase. It exposes the remaining
experiment capacity and lets the Researcher inspect the active-campaign evidence
and formulate the best available continuation before choosing exactly one of: a
next experiment; a saved-lineage measurement; terminal assessment of the frozen
best-known model; or the conclusion that no further experiment is warranted.
Preparation may end without a new experiment. Write `research/proposal.json`
containing only a `campaign_conclusion` object:

```json
{
  "campaign_conclusion": {
    "action": "request_final_benchmark",
    "terminal_expectation": {
      "expected_verdict": "<goal_reached | goal_not_reached | uncertain>",
      "reason": "<non-empty evidence-and-uncertainty rationale>"
    },
    "best_nonterminal_action_comparison": {
      "action": "<best feasible nonterminal action currently visible>",
      "evidence": "<the evidence or uncertainty that action would address>",
      "reason": "<why terminal assessment has greater expected decision value>"
    }
  }
}
```

```json
{
  "campaign_conclusion": {
    "action": "no_further_experiment",
    "reason": "<non-empty reason for the decision>",
    "best_nonterminal_action_comparison": {
      "action": "<best feasible nonterminal action currently visible>",
      "evidence": "<the evidence or uncertainty that action would address>",
      "reason": "<why terminal assessment has greater expected decision value>"
    }
  }
}
```

Every terminal choice carries a required `best_nonterminal_action_comparison`
object that identifies the best feasible nonterminal action the Researcher
currently sees — which may be training, replication, a saved-lineage measurement,
or another legal research action — states the evidence or uncertainty that action
would address, and explains why terminal assessment has greater expected decision
value. All three fields are non-empty. The Runner validates only the structure,
the referenced artifact identity, the remaining experiment capacity, and the
legal operation type; it does not rank the named action or judge its scientific
merit, and it does not require a changed recipe, an experiment targeting residual
failures, or any minimum experiment count.

`request_final_benchmark` submits the standing `best_known` lineage for the
official final assessment. It requires a designated best-known model: the
official benchmark runs once and the campaign ends after its verdict. Its
required `terminal_expectation` object carries the verdict the Researcher expects
and the evidence-and-uncertainty rationale behind it. All three
`expected_verdict` values are accepted. `no_further_experiment` records the
Researcher's judgement that no further experiment is warranted without requesting
that assessment; it ends the campaign. Neither outcome creates an experiment
record, an experiment-index row or an intervention count. A `campaign_conclusion`
is accepted only while no measurement, analysis, closure or official assessment
is pending; each pending phase requires its own deliverable.

A `campaign_conclusion` prepared while experiment capacity remains is a
**first-pass terminal proposal**. It does not run the official benchmark, does
not end the campaign, and is retained privately by the Runner for audit. The
Runner keeps the same pre-decision scientific state and opens a second,
independent action-selection session. That session receives the campaign
evidence and remaining capacity but not the first action, its rationale, or any
hash. It must author a full legal action-selection deliverable. A second
terminal proposal executes as the final pass; any experiment or measurement
proposal replaces the first decision. No alternative, portfolio, changed recipe
or mandatory experiment is required, and the final scientific choice remains
entirely with the Researcher. When the experiment budget is exhausted no further
experiment may be prepared, so the conclusion is final immediately and no
second-pass session is opened.

### Second-pass action selection

**Phase:** Action selection, opened by the Runner after a first-pass terminal
proposal recorded while experiment capacity remains.

The first-pass proposal is retained privately for audit and is never surfaced.
The Researcher receives the campaign evidence and remaining capacity and authors
the same normal action-selection deliverable as any preparation phase: a training
proposal, a saved-lineage `research/evaluation_request.json`, or a
`campaign_conclusion`, using the contracts in this file.

A terminal `campaign_conclusion` submitted from this second pass executes as the
final pass: `request_final_benchmark` runs the official assessment once and
`no_further_experiment` ends the campaign. A training or saved-lineage measurement
proposal replaces the retained first-pass decision and returns the campaign to
its normal preparation lifecycle.

A conclusion resolves no science, so it is accepted only while the researcher's
scientific surface matches the preparation anchor. Revert or resolve any
outstanding researcher-owned change first; unlike a training proposal or a lineage
decision, a conclusion neither publishes nor restores a recipe.

A preparation phase that has already executed a measurement round on saved
lineages may not conclude: it owes an experiment proposal. The round was
requested because its result would change the next decision, and in this phase
that decision is which experiment to prepare. Concluding is available from an
action-selection phase that spends no measurement round, and whenever no further
experiment may be prepared.

When the experiment budget is exhausted, no further training experiment may be
prepared, but a campaign conclusion remains legal regardless of any measurement
round already spent. The Runner commits the decision before
it publishes any terminal status, so an interrupted conclusion is resumed rather
than inherited as a published terminal state.

## Record the postmortem

**Phase:** Experiment closure.

In the same file, maintain one revisable section for the active campaign. It can
also be edited during experiment preparation. The exact heading and labels are:

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

**Expected observation disposition:** <one of `supported`, `weakened`, `contradicted`, `unresolved`, or `not tested`, followed by ` - ` and the cited evidence from this experiment>

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

New non-baseline closures also require `Expected observation disposition`: one
enumerated label followed by ` - ` and the cited evidence, for example
`supported - 199 of 200 episodes held`. The Runner validates that the label is
enumerated and that evidence is present; it does not judge the evidence or the
disposition. The field is compared against the experiment's frozen expected
observation and attached to its question ledger. It does not determine
saved-policy usefulness, recipe, lineage, retention, or the decision to request
the official benchmark. Fresh baselines are exempt.

## Resolve lineage

**Phase:** Post-training analysis, after the postmortem.

Write a lineage-only `research/proposal.json`:

```json
{
  "previous_result_decision": {
    "experiment": "<current experiment integer>",
    "continue_from": {
      "source": "<lineage_role | experiment_candidate | retained_lineage>",
      "expected_fingerprint": "<immutable artifact fingerprint>",
      "role": "<working | best_known; lineage_role only>",
      "designation_ordinal": "<current best_known tenure; lineage_role best_known only>",
      "experiment": "<current experiment integer; experiment_candidate only>",
      "checkpoint": "<candidate name; experiment_candidate only>",
      "id": "<stable retained ID; retained_lineage only>"
    },
    "reason": "<non-empty scientific reason>",
    "code": {
      "action": "<keep | revert | restore>",
      "reason": "<non-empty reason>",
      "lineage": {
        "source": "<lineage_role | retained_lineage>",
        "expected_fingerprint": "<immutable artifact fingerprint>",
        "role": "<working | best_known; lineage_role only>",
        "designation_ordinal": "<current best_known tenure; lineage_role best_known only>",
        "id": "<stable retained ID; retained_lineage only>"
      }
    },
    "best_known": {
      "selection": {
        "source": "<lineage_role | experiment_candidate | retained_lineage>",
        "expected_fingerprint": "<immutable artifact fingerprint>",
        "role": "<working | best_known; lineage_role only>",
        "designation_ordinal": "<current best_known tenure; lineage_role best_known only>",
        "experiment": "<current experiment integer; experiment_candidate only>",
        "checkpoint": "<candidate name; experiment_candidate only>",
        "id": "<stable retained ID; retained_lineage only>"
      },
      "reason": "<non-empty designation reason>"
    },
    "retain": [
      {
        "candidate": {
          "source": "<lineage_role | experiment_candidate | retained_lineage>",
          "expected_fingerprint": "<immutable artifact fingerprint>",
          "role": "<working | best_known; lineage_role only>",
          "designation_ordinal": "<current best_known tenure; lineage_role best_known only>",
          "experiment": "<current experiment integer; experiment_candidate only>",
          "checkpoint": "<candidate name; experiment_candidate only>",
          "id": "<stable retained ID; retained_lineage only>"
        },
        "id": "<stable identifier>",
        "reason": "<non-empty reason>"
      }
    ],
    "remove_retained": [
      "<retained-lineage identifier>"
    ],
    "confirm_transaction": "<transaction hash from the Runner's resolved preview>"
  }
}
```

Every model selection is a typed selection object, never a bare string. The
`source` names the selection namespace explicitly:

- `lineage_role` selects the current `working` or `best_known` tenure; a
  `best_known` selection also states the `designation_ordinal` of that tenure.
- `experiment_candidate` selects a checkpoint by its `experiment` and
  `checkpoint` name.
- `retained_lineage` selects a retained lineage by its stable `id`.

`expected_fingerprint` is the immutable artifact fingerprint the Researcher
believes it is selecting. The Runner resolves the complete transaction and
returns a persisted preview of the old and proposed role assignments, their
fingerprints, origins, effective parameters, and fingerprint-matched evidence.
Before any role changes it emits the transaction hash. The Researcher must
resubmit the same `previous_result_decision` with `confirm_transaction` set to
that exact hash, or submit a revised selection. A fingerprint that no longer
matches, a superseded `designation_ordinal`, a checkpoint from another
experiment, or a stale confirmation is deterministically rejected and requires a
fresh selection. The Runner validates identity and provenance only: it never
decides which model is scientifically preferable and never interprets the reason.

`best_known`, `retain`, and `remove_retained` are optional. Omitted `best_known`
preserves the existing best-known lineage; it does not promote `continue_from`.
This request selects the working model, chooses the scientific recipe action, and
manages retained lineages. It resolves only the completed experiment and never
terminates the campaign. Unretained model artifacts are removed; their recorded
history and measurements remain.

If `best_known` selects the current best-known model, the designation is accepted
idempotently. If it selects another available model, the Runner resolves that
model's recorded measurements from the current campaign state. A new designation
requires at least one recorded measurement for the selected model; the Runner
checks only that a measurement exists, not whether the evidence is scientifically
sufficient and not whether scores compare favorably.

Closure never requests terminal assessment. It resolves only the completed
experiment: the hypothesis assessment, the scientific recipe disposition, the
working lineage, the optional best-known designation, and retention. After every
closure the Runner opens the campaign action-selection phase, where terminal
assessment or a no-further-experiment conclusion is a separate, comparative
decision. The scientific decision rule for requesting assessment is defined in
`research/program.md`.

`experiment` is an integer. `continue_from` is a typed selection object and
both `reason` values are non-empty strings. The compatible field name
`code.action` controls the complete researcher-owned scientific recipe:
researcher-owned source and `research/current_params.json`. `keep` keeps the
experiment's complete scientific recipe; `revert` restores the scientific
parent's complete recipe; and `restore` restores the complete recipe associated
with the explicitly named eligible lineage. For `restore`, `code.lineage` is a
typed selection object restricted to `lineage_role` or `retained_lineage`; for
`keep` and `revert`, omit `code.lineage`. The exact currently valid lineage
identities and fingerprints are listed in `research/brief.md`. `best_known`
requires exactly a typed selection object and reason string; the selected model
must be available and its expected fingerprint must match. When a new model is
selected, the Runner resolves its recorded measurements and stores those paths
in the lineage. `retain` is an array of candidate/id/reason objects whose
candidate is a typed selection object, and `remove_retained` is an array of
unique retained IDs. `confirm_transaction` is the exact transaction hash the
Runner returned for the resolved selection; it is required before any role
changes. The Runner persists the resolved transaction with the closure so the
confirmed assignment is reproducible from the stored preview.

## Request the official benchmark

**Phase:** Campaign action selection (experiment preparation), after an
experiment closure.

Terminal assessment is a `campaign_conclusion` in `research/proposal.json`, never
a closure decision. Set `action` to `request_final_benchmark`, give
`terminal_expectation`, and record the required
`best_nonterminal_action_comparison`; the contract is in "Conclude the campaign"
above. While experiment capacity remains the request is a first-pass proposal: it
is retained privately and is not executed until a second, independent
action-selection pass proposes a terminal decision.

When the executed request is applied, the Runner emits a confirmation card and
the brief records a **Pending terminal assessment** section naming the frozen
`best_known` lineage — its candidate, artifact, origin experiment, accumulated training steps,
scientific commit and recorded measurements — together with the expected verdict
and the terminal reason. The expected verdict is also shown with the completed
official report, so the claimed verdict can be read against the measured one.
The decision is irreversible, but the Runner does not add a reversal or a second
verdict: both `goal_reached` and `goal_not_reached` are legitimate campaign
outcomes.

After applying the conclusion, the Runner assesses the frozen best-known model
and writes the terminal verdict to `research/brief.md`. The campaign ends after
either verdict. This operation does not produce evidence for another hypothesis.
