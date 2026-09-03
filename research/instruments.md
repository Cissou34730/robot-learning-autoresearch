# Researcher instruments

This file defines the evidence sources and Runner operations available to the Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

Read:

* `research/brief.md` for current state, parameters, available models, retained lineages and artifact paths;
* `research/postmortems.md` for previous observations and interpretations;
* every JSON or JSONL artifact referenced by the brief, history or candidate metadata, including evaluation results, task-reference results, inventories and parameters.

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

`measurements` must contain at least one entry. `paired_comparisons` is optional.

| Instrument            | Additional fields                                                       | Operation                                                          |
| --------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `research_evaluation` | `episodes`: positive integer; `seed`: integer; optional `label`: string | Runs the researcher-owned evaluator and writes one result artifact |
| `task_reference`      | Optional `label`: string                                                | Runs the fixed task-reference panel and writes one result artifact |

Add one entry per model. Using identical `research_evaluation` settings measures several candidates or the champion on a comparable panel.

A paired comparison uses the accumulated `research_evaluation` outcomes for the two named models. Both sides must have identical `(seed, episode)` sets.

Set `need_more_evidence` to `true` to preserve completed measurements and open another evaluation round. Set it to `false` to proceed to experiment closure.

## Request training

**Phase:** Experiment preparation.

Configure researcher-owned code and `research/current_params.json` as needed, then write one `research/proposal.json`:

```json
{
  "kind": "<training | continuation | replication>",
  "family": "<non-empty hypothesis-family identifier>",
  "hypothesis": "<non-empty falsifiable hypothesis>",
  "change": "<non-empty description of the requested operation>",
  "initialization": "<fresh | transfer>",
  "training_parent": "<string; required for transfer or continuation, otherwise omit>",
  "training_seed": "<integer; optional except for replication>",
  "replication_of": "<positive experiment integer; replication only, otherwise omit>",
  "params": "<object; training only, otherwise omit>"
}
```

| Kind           | Meaning                                                                                        | Requirements                                                                                                      |
| -------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `training`     | Trains a scientific intervention                                                               | Requires a researcher-owned code change or `params`; transfer requires `training_parent`                          |
| `continuation` | Trains an unchanged method further                                                             | Requires `initialization: "transfer"` and an eligible `training_parent`                                           |
| `replication`  | Starts the current unchanged method from scratch and groups the run with an earlier experiment | Requires `initialization: "fresh"`, `replication_of` and `training_seed`; code changes and `params` are forbidden |

For `continuation` and `replication`, `change` describes the requested operation; it does not imply a method change.

An eligible `training_parent` must be exposed by the brief as an active or retained lineage.

The automatic baseline trains the unchanged method from scratch for 120,000 steps.

Runner recovery resumes the interrupted experiment; it is not a continuation.

The current replication operation records the relationship through `replication_of`. It does not restore the referenced experiment’s code or configuration.

The Runner validates and executes the accepted proposal. Training and Runner operations are not launched directly by the Researcher.

## Record the postmortem

**Phase:** Experiment closure.

Append to `research/postmortems.md`:

```markdown
## Experiment <integer>

**Result:** <concise result>

**Observed behavior:** <factual observations>

**Interpretation:** <scientific interpretation>

**Evidence inspected:** <artifact paths from this experiment>
```

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
