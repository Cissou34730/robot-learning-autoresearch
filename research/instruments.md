# Researcher instruments

This file defines the evidence sources and phase deliverables available to the Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

Start with `research/brief.md`. It is the compact index and summary of the
current campaign's evidence, including current state, parameters, available
models, retained lineages and repository-relative artifact paths.

Use `research/postmortems.md` for previous observations and interpretations.
Inspect referenced evaluation, task-reference or other structured artifacts as
part of formulating or answering a scientific question. Targeted extraction and
full-artifact inspection are both available; choose the form that supports the
investigation.

Detailed artifacts remain valid sources of scientific evidence, including for
unsuccessful experiments. Inspect episode-level behavior, distributions,
failure modes, or any other detail when it may help explain a result or generate
a useful hypothesis.

When querying structured artifacts, distinguish schema discovery from scientific
analysis. Schema inspection may be necessary to understand an unfamiliar
artifact; repeated deterministic execution and repeated extraction of the same
fields should be recognized accurately rather than treated as new evidence.

Artifact paths exposed by the brief and research contracts are relative to the
repository. Use them directly from the repository working directory; do not
reconstruct them as absolute paths.

For targeted JSON or JSONL extraction, prefer the installed `jello` command
through the researcher environment rather than relying on a global executable:

```powershell
uv run --group researcher jello '_.metrics' -f <artifact.json>
```

Another existing researcher-owned analysis tool may be used when it better fits
the question. `research/instruments.md` is the operational contract for these
instruments and request formats, and a starting point for understanding them.
Inspect instrument, learning, measurement, or Runner implementations when useful
to understand behavior, assumptions, coverage, outputs, or limitations and decide
how to use a capability. Implementation inspection may help formulate the
scientific question as well as answer it. Human-owned implementations remain
read-only; inspection does not change execution or modification permissions.

For the official benchmark result, use `research/brief.md` under **Current
status -> Reported result**. Its durable metrics and artifact reference remain
in `research/research_state.json`.

Candidate training success and reward shown in the brief are training facts, not evaluation results. They cannot establish that a policy improved, but they are the intended basis for deciding which checkpoints to measure.

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

During post-training analysis and its optional refinement rounds, the Researcher
may modify researcher-owned measurement and analysis code before requesting
another measurement round. The existing request flow can measure current
candidates and eligible saved lineages. No diagnostic code change or particular
instrument is required. Changes affecting training apply to the next experiment.

## Request measurements

**Phase:** Post-training analysis.

Use this request during initial analysis or an optional refinement round while
closing the current trained experiment. Researcher-owned instrumentation may be
changed before submitting the request.

`question` and `reason` are non-empty strings describing the request as a whole.
`measurements` selects the instruments and models to run. `paired_comparisons`
selects comparisons to compute from compatible measurements and is optional.
The question may be confirmatory, diagnostic, exploratory, or descriptive.

Write `research/evaluation_request.json`:

```json
{
  "experiment": "<current experiment integer>",
  "question": "<non-empty scientific question>",
  "reason": "<non-empty reason>",
  "measurements": [
    {
      "instrument": "<research_evaluation | task_reference>",
      "candidate": "<model exposed by the brief>",
      "selection": "<non-empty reason measuring this model is useful for the scientific question>",
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

`measurements` must contain at least one entry, and at most three distinct models. `paired_comparisons` is optional.

Every measurement requires its own non-empty `selection`. The request-level
`reason` explains the round; `selection` explains why measuring that model is
useful for the scientific question. Measurements of the same model may have
different selections. It need not claim that the model is superior to every
alternative.

One evaluation request may measure at most three distinct models. Multiple
measurements of the same model count as one. This includes different seeds,
episode counts, labels, or instruments applied to the same model. This is an
operational limit, not a recommendation about which models are informative.

| Instrument            | Additional fields                                                       | Operation                                                          |
| --------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `research_evaluation` | `episodes`: positive integer; `seed`: integer; optional `label`: string | Runs the researcher-owned evaluator and writes one result artifact |
| `task_reference`      | Optional `label`: string                                                | Measures a saved policy on the protected original task using a fixed development panel distinct from the final benchmark |

Task-reference measurement is independent of researcher-owned environments and
evaluation code. It reports task success and per-episode target geometry and
outcomes. The panel definition is in
`robot_learning/benchmark/reference_contract.py`; its execution and reported
quantities are in `robot_learning/benchmark/reference_evaluation.py`.

Add one entry per model. Using identical `research_evaluation` settings measures several candidates or a selected lineage on a comparable panel.

A paired comparison uses the accumulated `research_evaluation` outcomes for the two named models. Both sides must cover identical recorded episode identities within matching evaluation semantics.
Compatible historical measurements may supply either or both sides when their
model fingerprints, evaluation semantics, instrument settings, and exact episode
identities match. Detailed diagnostic artifacts retain the same evaluation
identity. Legacy compatibility fields are ignored when records are read.
The same compatibility rule determines whether research-evaluation evidence can
support replacing `best_known`; task-reference evidence retains its exact panel
compatibility rule and remains optional.
Overlapping or repeated episodes count once in pooled summaries and paired
comparisons. Summary `episodes` reports distinct coverage; `episode_executions`
and `repeated_episodes` report execution count and repeated coverage separately.
Conflicting outcomes for the same deterministic episode are rejected.
Reusing the same development panel does not create independent confirmation.

The model fingerprint covers the complete saved artifact, including its policy
I/O, loader, and normalization state. Research-evaluation context identity covers
the current evaluator, environment/task mechanics, and measurement
instrumentation outside that artifact. Editing model-contained
policy I/O does not retroactively change the context of an existing measurement;
editing evaluator or environment semantics does. Training-only code, including
the reward, is excluded because it changes neither replay nor success. Pooled
comparison uses success only; per-episode `reward_total` in the detailed
artifacts is not comparable across a reward change.

Each completed measurement round returns to post-training analysis. New requests
do not use `need_more_evidence`; closing is a separate closure proposal in the
same phase. Legacy accepted requests that contain it remain recoverable.

## Request training

**Phase:** Experiment preparation.

Configure researcher-owned code and `research/current_params.json` as needed, then write one `research/proposal.json`. The common required fields are `kind`, `family`, `hypothesis`, `initialization` and `reasoning`:

```json
{
  "kind": "<training | continuation | replication>",
  "family": "<non-empty hypothesis-family identifier>",
  "hypothesis": "<non-empty falsifiable proposition or uncertainty to test or resolve>",
  "initialization": "<fresh | transfer>",
  "reasoning": {
    "evidence": [
      {"source": "<existing repository-relative file>", "observation": "<what was observed there>"}
    ],
    "alternative": "<plausible competing explanation or outcome>",
    "expected_observation": "<observation supporting the proposition or one diagnostic branch, and what would be learned>",
    "contradicting_observation": "<observation weakening the proposition, supporting an alternative, or revealing incomplete framing>",
    "initialization_reason": "<why fresh, or why transfer from this training_parent>",
    "strategy_link": "<how this experiment advances, revises, or rejects the current investigation>"
  },
  "change": "<non-empty scientific intervention; training only>",
  "training_parent": "<string; required for transfer, otherwise omit>",
  "training_seed": "<non-negative integer; optional except for replication>",
  "replication_of": "<positive current-campaign experiment integer; replication only>",
  "params": "<object; optional parameter overrides>"
}
```

| Kind | Meaning | Required or conditional fields |
| --- | --- | --- |
| `training` | Trains a changed scientific recipe. The hypothesis may predict its effect or use the change to resolve a structured diagnostic or exploratory uncertainty; it need not isolate a causal mechanism. | `change` must be a non-empty description; the intervention must also be a researcher-owned code change or non-empty `params`. Transfer requires `training_parent`. |
| `continuation` | Trains the unchanged method further from an eligible lineage. The hypothesis is a prediction about continuing training: further progress, plateau, or degradation. | Requires `initialization: "transfer"` and `training_parent`. Code changes, parameter overrides and `change` are forbidden. |
| `replication` | Starts the current unchanged method from scratch and groups the run with an earlier experiment for replication evidence. The hypothesis is a prediction about reproducibility or variance of the learning process. | Requires `initialization: "fresh"`, a positive integer `replication_of` naming an existing experiment in the current campaign, and an explicit non-negative integer `training_seed`. Code changes, `params` and `change` are forbidden. |

`training_seed` is optional for ordinary training and continuation, and must be
a non-negative integer when present. `params` is optional for ordinary training
and is omitted for unchanged operations.

Experiment records distinguish `training_budget_steps` (requested) from
`completed_training_steps` (actually completed in that experiment). Rollout
boundaries may make the completed count exceed the request. A selected lineage's
`training_steps` instead records its accumulated training through the selected
checkpoint.

All `reasoning` strings must be non-empty; `evidence` contains at least one
source/observation pair. Cite inspected campaign artifacts, logs, postmortems or
code with precise observations; these are not restricted to evaluation results.
`source` is a file path without a line-number suffix or fragment; put the relevant
experiment, checkpoint, step range or code location in `observation` as needed.
The Runner checks file existence and confinement to this repository, not the
scientific conclusion or proof of inspection. This contract applies equally to
training, continuation and replication, not to the automatic baseline.

The campaign's Scientific strategy section must exist before submission. The
Runner validates its four labels and snapshots the section with `reasoning` in
the experiment record. Existing historical records without these fields remain
readable.

An eligible `training_parent` must be exposed by the brief as `working`,
`best_known`, or a retained lineage ID. `continuation` continues the selected
recipe without a learning-method change. A `training` proposal may deliberately
apply a changed recipe to an existing parent with `initialization: "transfer"`.
Continuation, replication, and additional seeds remain available scientific
choices, not mandatory controls or gates for accepting a model.

The `reasoning` object contains the fields shown in the schema. `evidence` is a
non-empty array of source/observation objects. `alternative`,
`expected_observation`, `contradicting_observation`, `initialization_reason`, and
`strategy_link` are non-empty strings. Expected and contradicting observations
describe informative possibilities rather than binary acceptance criteria. Their
scientific use is defined in `research/program.md`.

The automatic baseline trains the unchanged method from scratch for 120,000 steps.

Runner recovery resumes the interrupted experiment; it is not a continuation.

The current replication operation records the relationship through the positive
integer `replication_of`, which must name an existing experiment in the current
campaign. It groups the new run with the referenced experiment for replication
evidence; it does not restore that experiment’s code or configuration and does
not claim exact replay.

## Record the postmortem

**Phase:** Experiment closure.

In the same file, maintain one revisable section for the active campaign. It can
also be edited during experiment preparation. The exact heading and labels are:

```markdown
## <Campaign ID> / Scientific strategy

**Direction:** <revisable question or approach that currently best serves the human objective>

**Lessons and limits:** <reusable findings, source references and scope; or what remains unknown>

**Open questions:** <uncertainties not yet resolved>

**Conditional next steps:** <plausible future options suggested by current evidence>
```

All four labeled entries must contain text and may span multiple lines. Their
scientific meaning is defined in `research/program.md`. The Runner checks the
section's structure, associates the active campaign section with the proposal,
and displays it in the brief. It does not author scientific content. Historical
experiment entries and strategy sections remain readable.

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
lineage, retention, or terminal-readiness decisions. Fresh baselines are exempt,
and historical entries remain readable.

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
    "request_final_benchmark": "<boolean>"
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

When `request_final_benchmark` is `true`, include the terminal rationale in the
existing `previous_result_decision.reason` field.

`experiment` is an integer. `continue_from` and both `reason` values are
non-empty strings. The compatible field name `code.action` controls the complete
researcher-owned scientific recipe: researcher-owned source, tests, and
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
and `request_final_benchmark` is a boolean.

## Request the official benchmark

Set `request_final_benchmark` to `true` in `previous_result_decision`.

After applying the lineage decision, the Runner assesses the frozen best-known
model and writes the terminal verdict to `research/brief.md`. The campaign ends
after either verdict. This operation does not produce evidence for another
hypothesis.
