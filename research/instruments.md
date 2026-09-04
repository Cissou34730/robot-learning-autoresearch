# Researcher instruments

This file defines the evidence sources and phase deliverables available to the Researcher. Path ownership is defined by `AGENTS.md`.

## Inspect evidence

Start with `research/brief.md`. It is the compact index and summary of the
current campaign's evidence, including current state, parameters, available
models, retained lineages and repository-relative artifact paths.

Use `research/postmortems.md` for previous observations and interpretations.
Inspect referenced evaluation, task-reference or other structured artifacts
only when additional detail is needed to resolve the current scientific
question. Inspect enough evidence to support the requested scientific decision,
but prefer targeted extraction of the required fields over loading a complete
artifact. Read a full artifact when its complete contents are genuinely needed
or a simple query cannot express the analysis.

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
instruments and request formats. Do not inspect instrument or Runner
implementation merely to discover how to use an operation already documented
here. Implementation inspection remains appropriate when the scientific
question requires understanding researcher-owned measurement or learning code.

For the official benchmark result, use `research/brief.md` under **Current
status -> Reported result**. Its durable metrics and artifact reference remain
in `research/research_state.json`.

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

`measurements` must contain at least one entry, and at most three distinct models. `paired_comparisons` is optional.

One evaluation request may measure at most three distinct models. Multiple measurements of the same model count as one. This includes different seeds, episode counts, labels, or instruments applied to the same model.

| Instrument            | Additional fields                                                       | Operation                                                          |
| --------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `research_evaluation` | `episodes`: positive integer; `seed`: integer; optional `label`: string | Runs the researcher-owned evaluator and writes one result artifact |
| `task_reference`      | Optional `label`: string                                                | Runs the fixed task-reference panel and writes one result artifact |

Add one entry per model. Using identical `research_evaluation` settings measures several candidates or the champion on a comparable panel.

A paired comparison uses the accumulated `research_evaluation` outcomes for the two named models. Both sides must have identical `(seed, episode)` sets.

`need_more_evidence` is optional. When present, it must be the JSON boolean
`true` or `false`. Set it to `true` to preserve completed measurements and open
another evaluation round; omit it or set it to `false` to proceed to experiment
closure.

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
  "training_seed": "<non-negative integer; optional except for replication>",
  "replication_of": "<positive current-campaign experiment integer; replication only>",
  "params": "<object; optional parameter overrides>"
}
```

| Kind | Meaning | Required or conditional fields |
| --- | --- | --- |
| `training` | Trains a scientific intervention. | `change` must be a non-empty description; the intervention must also be a researcher-owned code change or non-empty `params`. Transfer requires `training_parent`. |
| `continuation` | Trains the unchanged method further from an eligible lineage. | Requires `initialization: "transfer"` and `training_parent`. Code changes, parameter overrides and `change` are forbidden. |
| `replication` | Starts the current unchanged method from scratch and groups the run with an earlier experiment for replication evidence. | Requires `initialization: "fresh"`, a positive integer `replication_of` naming an existing experiment in the current campaign, and an explicit non-negative integer `training_seed`. Code changes, `params` and `change` are forbidden. |

`training_seed` is optional for ordinary training and continuation, and must be
a non-negative integer when present. `params` is optional for ordinary training
and is omitted for unchanged operations.

An eligible `training_parent` must be exposed by the brief as an active or retained lineage.

The automatic baseline trains the unchanged method from scratch for 120,000 steps.

Runner recovery resumes the interrupted experiment; it is not a continuation.

The current replication operation records the relationship through the positive
integer `replication_of`, which must name an existing experiment in the current
campaign. It groups the new run with the referenced experiment for replication
evidence; it does not restore that experiment’s code or configuration and does
not claim exact replay.

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
