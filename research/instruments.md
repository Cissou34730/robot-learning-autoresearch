# Researcher instruments

This file defines the evidence sources and phase deliverables available to the
Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

`research/brief.md` is a generic index of the current campaign, pending
operation, inquiry, method lifecycle, model roles, a measurement / panel index
and the campaign laboratory index, all with repository-relative artifact paths.
It records identities and locations, not interpretations.
`research/postmortems.md` contains Researcher-authored scientific memory.
Detailed measurements are stored under `research/evaluations/`.

Use repository-relative paths directly. `jello` is available for JSON and JSONL
artifacts and uses Python expressions. The official benchmark result, when one
exists, is indexed by the brief and stored durably in
`research/research_state.json`.

## Model the robot and task

**Phase:** Preliminary campaign start, before baseline training or evidence.

Write `research/scientific_model.md` once per campaign, separating:

- **Established facts:** repository facts and constraints with their sources.
- **Physical consequences:** reasoned implications and stated assumptions.
- **Unknowns:** quantities or outcomes not established by available facts.

Treat approach, reaching, tolerance entry, settling and sustained completion as
coupled parts of the control problem. The launcher validates only that the file
exists and is non-empty. It becomes read-only before baseline training.

## Query training logs

```powershell
uv run python research/query_training_log.py --experiment <id> --from-step <start> --to-step <end>
```

The command prints preserved raw records for the inclusive timestep range.

## Modify the scientific system

The Researcher may modify only the surface listed in `AGENTS.md`. Saved policies
carry their own inference contract through `scenario/policy_io.py` and
`policy_runtime.pkl`. Preserve that export when changing training or checkpoint
code. Durable diagnostic tools belong under `research/lab/`; the Runner
publishes them separately from policy recipe identity.

Tests are human-owned. The Runner rejects test changes in scientific proposals.

## Baseline startup

The Runner trains experiment 1 from the unchanged current recipe for 120,000
steps. A Fresh reset may first import only the Researcher-owned recipe and
configuration from `-RecipeRef`; it imports no policy or evidence. Baseline
analysis may request measurements and then writes:

```json
{
  "baseline_decision": {
    "experiment": 1,
    "candidate": "<measured baseline checkpoint>",
    "reason": "<why this checkpoint establishes the baseline>"
  }
}
```

The selected baseline becomes both `working` and `best_known`. Before this
selection, baseline measurement rounds and `baseline_decision` are the only
legal operations. An inquiry starts only after `working` and `best_known` name
the same selected baseline.

## Open, reframe, or close an inquiry

**Phase:** Inquiry operation.

The Runner allocates a new inquiry identity and PI session. Open it with:

```json
{
  "inquiry": {
    "action": "open",
    "question": "<bounded scientific question>",
    "scope": "<evidence and system surface in scope>",
    "closure_condition": "<condition that answers, redirects, or stops the inquiry>"
  }
}
```

All statements are required and non-empty. The inquiry's PI session owns it
from allocation through measurements, method work, training, post-training
analysis, method decisions and maturity, across launcher restarts.

Reframe without changing inquiry or session identity:

```json
{
  "inquiry": {
    "action": "reframe",
    "question": "<revised question>",
    "scope": "<revised scope>",
    "closure_condition": "<revised closure condition>",
    "rationale": "<why evidence requires reframing>"
  }
}
```

Close only when the inquiry has no active method or its method is `promoted`,
`retained` or `abandoned`:

```json
{
  "inquiry": {
    "action": "close",
    "outcome": "<durable scientific outcome>"
  }
}
```

Closing clears the inquiry session. A later inquiry receives a new identity and
session while retaining current-campaign artifacts.

## Start an active method

**Phase:** Active inquiry, before the method's first training run.

```json
{
  "method": {
    "action": "start",
    "id": "<stable file-name-safe identifier>",
    "scientific_question": "<question developed by this method>",
    "rationale": "<why the method is worth developing>",
    "lifecycle": "<concept | development>"
  }
}
```

The method can exist without a candidate. It persists across iterations and
records its `lifecycle`, the scientific parent it started from
(`base_scientific_commit`), its current lineage when available, and its
iteration history. A failed training run is recorded as evidence and does not
discard the method.

| Lifecycle | Meaning |
| --- | --- |
| `concept`, `development` | Declared or iterating. Training, measurement, `retain` (with a current lineage) and `abandon` are available. |
| `mature` | A post-training `mature` decision ended the iteration. Measurement, training, `promote`, `retain` and `abandon` are available. |
| `promoted`, `retained`, `abandoned` | Final for this inquiry. The inquiry may measure, reframe or close. |

## Request measurements

**Phase:** Active inquiry or post-training analysis, including baseline
analysis.

During analysis, candidates from the current experiment and saved lineages may
be measured. Otherwise use saved `working`, `best_known`, `active_method`, or
retained lineages and omit `experiment`.

```json
{
  "experiment": "<current experiment integer; analysis only>",
  "question": "<question this round addresses>",
  "reason": "<why this evidence can change a decision>",
  "measurements": [
    {
      "instrument": "<research_evaluation | task_reference>",
      "candidate": "<available model>",
      "selection": "<why this model is informative>",
      "omitted_alternative": "<optional available model not measured>",
      "episodes": "<positive integer; research_evaluation only>",
      "seed": "<integer; research_evaluation only>",
      "label": "<optional string>"
    }
  ],
  "paired_comparisons": [
    {"candidate": "<measured model>", "reference": "<other measured model>"}
  ]
}
```

At least one measurement is required and at most three distinct models may be
named. `paired_comparisons` and `omitted_alternative` are optional. Each
measurement requires a non-empty `selection`.

`research_evaluation` uses the half-open panel `[seed, seed + episodes)`. A
panel may be reused identically or be disjoint from all recorded research
panels; partial overlap and overlap with protected benchmark episodes are
rejected. Reuse is reported explicitly. A paired comparison pools shared
episode identities only when evaluation semantics match, deduplicates repeated
coverage, and rejects conflicting deterministic outcomes.

`task_reference` is the fixed human-owned reference panel. Its seed and episodes
are not configurable. It remains separate from the terminal official benchmark.

Each completed round returns to the same inquiry session and requesting phase.
Submit a new request if another round is useful.

## Request method training

**Phase:** Active inquiry with a declared active method.

Configure researcher-owned code and `research/current_params.json`, then write:

```json
{
  "kind": "<training | continuation | replication>",
  "method_id": "<active_method.id>",
  "family": "<optional grouping label>",
  "initialization": "<fresh | transfer>",
  "investigation_design": {
    "evidence": [
      {"source": "<existing repository-relative file>", "observation": "<what was observed>"}
    ],
    "objective_link": "<connection to the campaign objective>",
    "initialization_reason": "<why fresh or why this parent>",
    "rationale": "<why this run informs the active method>",
    "expected_observation": "<observation that would change the next decision>",
    "predicted_behavioral_path": "<optional prediction>",
    "open_question": "<optional unresolved behavior>"
  },
  "change": "<scientific intervention; training only>",
  "training_parent": "<required for transfer>",
  "extends_lineage": "<true only for adjusted transfer training>",
  "training_seed": "<non-negative integer; required for replication>",
  "replication_of": "<current-campaign experiment; replication only>",
  "params": "<optional parameter overrides>"
}
```

`investigation_design` requires non-empty `evidence`, `objective_link`,
`initialization_reason`, `rationale`, and `expected_observation`, plus at least
one of `predicted_behavioral_path` or `open_question`. Neither form is
preferred. An optional `scientific_model` object may contain additional
non-empty statements. Evidence sources must exist inside the repository.

| Kind | Contract |
| --- | --- |
| `training` | A changed recipe. `change` and either a scientific code delta or non-empty `params` are required. Transfer also requires `training_parent`. |
| adjusted `training` | With transfer and `extends_lineage: true`, trains the current changed recipe from parent weights. |
| `continuation` | Requires transfer and `training_parent`; restores the parent's recipe, optionally adding `params`. Code changes and `change` are forbidden. |
| `replication` | Requires fresh initialization, `replication_of`, and explicit `training_seed`. Code changes, `params`, and `change` are forbidden. |

Eligible parents are `working`, `best_known`, `active_method`, and retained
lineage IDs exposed by the brief. Raw disposable candidates are not parents.
Experiment records distinguish requested `training_budget_steps` from actual
`completed_training_steps`; lineage `training_steps` is accumulated.

Runner recovery resumes an interrupted execution and does not create a
continuation. A replication groups variance evidence but does not replay old
code, configuration, or random trajectories.

## Decide a method

**Phase:** Post-training analysis after maintaining the postmortem, or an active
inquiry with an unresolved active method. This is the only method-transition
contract.

```json
{
  "method_decision": {
    "experiment": "<current experiment; post-training analysis only, omitted from the inquiry>",
    "action": "<continue | refine | mature | promote | retain | abandon>",
    "outcome": "<scientific interpretation of this decision>",
    "reason": "<why the evidence supports this action>",
    "candidate": "<continue, refine, mature: current candidate or available lineage>",
    "code": {
      "action": "<keep | revert | restore>",
      "reason": "<why this recipe action is correct>",
      "lineage": "<working | best_known | active_method | retained ID; restore only>"
    },
    "retained_id": "<retain only>",
    "best_known": {
      "candidate": "active_method",
      "reason": "<optional evidence-backed designation; promote only>"
    }
  }
}
```

`outcome`, `reason` and `code` are required.

| Action | Available when | Effect |
| --- | --- | --- |
| `continue`, `refine` | Pending post-training analysis. | `lifecycle` becomes `development`; the selected candidate or lineage becomes the method's current lineage (default `active_method` when one exists). |
| `mature` | Pending post-training analysis. | `lifecycle` becomes `mature` with the selected lineage; the iteration ends and the inquiry continues. |
| `promote` | The method is already `mature`, in either phase. | Requires compatible, fingerprint-bound paired evidence of the current method lineage against `working`, normally from a later inquiry measurement. `working` changes; `best_known` changes only when explicitly designated and measured. `lifecycle` becomes `promoted`. |
| `retain` | The method has a current lineage, in either phase. | Publishes that lineage under a unique file-name-safe `retained_id` without changing `working`. `lifecycle` becomes `retained`. |
| `abandon` | Any unresolved method, in either phase. | Requires code `revert` or `restore` and cannot restore `active_method`; the method lineage is released unless another role preserves it. `lifecycle` becomes `abandoned`. |

`promote` and `retain` operate on the method's current lineage, not on a
candidate of the pending experiment; select a new candidate first through
`continue`, `refine` or `mature`. A decision from the inquiry allocates no
experiment and writes no experiment-history row.

The code action controls the complete Researcher-owned recipe. `keep` keeps the
current recipe, `revert` restores the scientific parent (the method's
`base_scientific_commit` for `abandon` or an inquiry decision), and `restore`
restores the named eligible lineage recipe. While a decision publishes, the
state records it as `pending_method_decision`; the Runner publishes selected
artifacts before candidate cleanup and resumes an interrupted publication
idempotently.

## Maintain scientific memory

Maintain one revisable strategy section for the active campaign:

```markdown
## <Campaign ID> / Scientific strategy

**Current synthesis:** <interpretation of campaign evidence>

**Lessons and limits:** <findings, sources, scope and limits>

**Competing explanations:** <live causal alternatives>

**Decision frontier:** <unresolved distinction and discriminating evidence>
```

After each non-baseline training run, append or revise:

```markdown
## <Campaign ID> / Experiment <integer>

**Result:** <concise result>

**Observed behavior:** <factual observations>

**Hypothesis assessment:** <supported, weakened, contradicted, or inconclusive, with limits>

**Interpretation:** <scientific interpretation>

**Evidence inspected:** <artifact paths>
```

The postmortem informs the experiment's `method_decision`; training does not
force immediate inquiry closure.

## Conclude the campaign

**Phase:** Inquiry boundary, with no active inquiry or pending operation.

```json
{
  "campaign_conclusion": {
    "action": "<request_final_benchmark | no_further_experiment>",
    "reason": "<terminal rationale>"
  }
}
```

`request_final_benchmark` requires `best_known` and irreversibly submits that
frozen lineage to the human-owned benchmark. `no_further_experiment` ends
without assessment. Neither action creates an experiment. A conclusion cannot
resolve scientific changes, so the Researcher surface must match the operation
anchor.

## Official benchmark

The official benchmark is human-owned, separate from development and
`task_reference`, runs once, and is never exposed as evidence for a later
inquiry. Its verdict ends the campaign. Do not invoke benchmark modules
directly.
