# Researcher instruments

This file defines the evidence sources and Runner operations available to the Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

Read:

* `research/brief.md` for current state, parameters, available models, retained lineages and artifact paths;
* `research/postmortems.md` for previous observations and interpretations;
* every JSON or JSONL artifact referenced by the brief or history, including evaluation results, task-reference results, inventories and parameters. Use jello to extract relevant fields without loading complete artifacts;
* the detailed researcher-evaluation artifacts under `research/evaluations/` and the detailed task-reference artifacts named by the brief or history;
* `research/brief.md` under **Current status -> Reported result** for the official benchmark result, with its durable metrics and artifact reference in `research/research_state.json`.

Candidate training success and reward shown in the brief are training facts, not evaluation results.

### Query Stable-Baselines3 logs

```bash
uv run python research/query_training_log.py \
  --experiment <positive-integer> \
  --from-step <nonnegative-integer> \
  --to-step <integer-at-least-from-step>
```

All arguments are required. Bounds are inclusive. Results preserve separate training attempts and are not aggregated.

Use `uv run` for lightweight analysis and focused checks on researcher-owned code. Persistent outputs must remain in researcher-owned paths.

## Modify the scientific system

During experiment preparation, the Researcher may modify any researcher-owned scientific code or configuration permitted by `AGENTS.md`.

During evaluation, the Researcher may modify researcher-owned measurement and analysis code before requesting another measurement round. Changes affecting training apply to the next experiment.

## Runner operations

The Runner validates and executes the accepted request for the current phase. It
allocates experiment identity, records compact results in
`research/results.jsonl`, derives `research/EXPERIMENTS.md`, and updates
`research/brief.md`. It owns training, evaluation, lineage decisions and the
official benchmark; the Researcher writes only the phase deliverable.

## Request measurements

**Phase:** Research evaluation.

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
      "<instrument-specific fields>": "<documented values>"
    }
  ],
  "paired_comparisons": [
    {
      "candidate": "<measured model>",
      "reference": "<other measured model>"
    }
  ],
  "need_more_evidence": "<boolean>"
}
```

`measurements` must contain at least one entry, and at most three distinct models. `paired_comparisons` is optional.

One evaluation request may measure at most three distinct models. Multiple measurements of the same model count as one. This includes different seeds, episode counts, labels, or instruments applied to the same model.

| Instrument            | Additional fields                                                       | Operation                                                          |
| --------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `research_evaluation` | `episodes`: positive integer; `seed`: integer; optional `label`: string | Runs the researcher-owned evaluator and writes one result artifact |
| `task_reference`      | Optional `label`: string                                                | Runs the fixed task-reference panel and writes one result artifact |

Add one entry per model. Using identical `research_evaluation` settings measures several candidates or the champion on a comparable panel.

A paired comparison uses the accumulated `research_evaluation` outcomes for the two named models. Both sides must have identical `(seed, episode)` sets.

Set `need_more_evidence` to `true` to preserve completed measurements and open another evaluation round. Set it to `false` to proceed to experiment closure.

## Request training

**Phase:** Experiment preparation.

Configure researcher-owned code and `research/current_params.json` as needed, then write one `research/proposal.json`. The common required fields are `kind`, `family`, `hypothesis` and `initialization`:

```json
{
  "kind": "<training | continuation | replication>",
  "family": "<non-empty hypothesis-family identifier>",
  "hypothesis": "<non-empty falsifiable hypothesis>",
  "initialization": "<fresh | transfer>",
  "change": "<non-empty scientific intervention; training only>",
  "training_parent": "<string; required for transfer, otherwise omit>",
  "training_seed": "<integer; optional except for replication>",
  "replication_of": "<positive experiment integer; replication only>",
  "params": "<object; optional parameter overrides>"
}
```

| Kind | Meaning | Required or conditional fields |
| --- | --- | --- |
| `training` | Trains a scientific intervention. | `change` must be a non-empty description; the intervention must also be a researcher-owned code change or non-empty `params`. Transfer requires `training_parent`. |
| `continuation` | Trains the unchanged method further from an eligible lineage. | Requires `initialization: "transfer"` and `training_parent`. Code changes and parameter overrides are forbidden. `change` is omitted; if supplied, it is a non-empty operation note and never describes a method mutation. |
| `replication` | Starts the current unchanged method from scratch and groups the run with an earlier experiment for replication evidence. | Requires `initialization: "fresh"`, a positive integer `replication_of` and an explicit integer `training_seed`. Code changes and `params` are forbidden. `change` is omitted; if supplied, it is a non-empty operation note and never describes a method mutation. |

`training_seed` is optional for ordinary training and continuation. `params` is
optional for ordinary training and is omitted for unchanged operations.

An eligible `training_parent` must be exposed by the brief as an active or retained lineage.

The automatic baseline trains the unchanged method from scratch for 120,000 steps.

Runner recovery resumes the interrupted experiment; it is not a continuation.

The current replication operation records the relationship through the positive
integer `replication_of`. It groups the new run with the referenced experiment
for replication evidence; it does not restore that experiment’s code or
configuration and does not claim exact replay.

The Runner validates and executes the accepted proposal. Training and Runner operations are not launched directly by the Researcher.

## Record the postmortem

**Phase:** Experiment closure.

Append to `research/postmortems.md`:

```markdown
## <Campaign ID> / Experiment <integer>

**Result:** <concise result>

**Observed behavior:** <factual observations>

**Interpretation:** <scientific interpretation>

**Evidence inspected:** <artifact paths from this experiment>
```

The heading format is `## <Campaign ID> / Experiment <integer>`, where `<Campaign ID>` is the current campaign UUID. This format allows experiments with the same number from different campaigns to be uniquely identified in the postmortem history.

At least one referenced artifact must exist and belong to the experiment.

## Resolve lineage

**Phase:** Experiment closure after the postmortem.

Write a lineage-only `research/proposal.json`:

```json
{
  "previous_result_decision": {
    "experiment": "<current experiment integer>",
    "continue_from": "<candidate or champion exposed by the brief>",
    "reason": "<non-empty scientific reason>",
    "code": {
      "action": "<keep | revert>",
      "reason": "<non-empty reason>"
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

`retain`, `remove_retained` and `request_final_benchmark` are optional.

This request selects the active model, keeps or reverts the experiment’s code, and manages retained lineages. Unretained model artifacts are removed; their recorded history and measurements remain.

## Request the official benchmark

Set `request_final_benchmark` to `true` in `previous_result_decision`.

After applying the lineage decision, the Runner benchmarks the selected model. Read the verdict in `research/brief.md` under **Current status → Reported result**.
