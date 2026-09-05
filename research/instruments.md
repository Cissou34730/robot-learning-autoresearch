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

Detailed artifacts remain valid sources of scientific evidence, including for
unsuccessful experiments. Inspect episode-level behavior, distributions,
failure modes, or any other detail when it may help explain a result or generate
a useful hypothesis.

When querying structured artifacts, prefer queries that answer a scientific
question over queries that only rediscover the artifact schema or reconfirm
summary values already available in `research/brief.md`. Schema inspection is
appropriate when needed to understand an unfamiliar artifact; once the relevant
structure is known, proceed directly to the scientific analysis rather than
repeatedly rediscovering it.

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

Saved policies carry their own inference contract. `scenario/policy_io.py`
defines observation construction and mapping from policy outputs to physical
robot commands; use these same functions in training. The current checkpoint
writer in `training/checkpoint.py` exports this contract, the loader and
normalization into `policy_runtime.pkl` beside the weights. Preserve that export
when replacing training or checkpointing code. Resolve scientific dependencies
before export rather than importing mutable project code during inference.
The Runner and evaluators use each artifact's contract, not the current model's
observation layout. Task mechanics and success measurement remain shared.

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

Configure researcher-owned code and `research/current_params.json` as needed, then write one `research/proposal.json`. The common required fields are `kind`, `family`, `hypothesis`, `initialization` and `reasoning`:

```json
{
  "kind": "<training | continuation | replication>",
  "family": "<non-empty hypothesis-family identifier>",
  "hypothesis": "<non-empty falsifiable hypothesis>",
  "initialization": "<fresh | transfer>",
  "reasoning": {
    "evidence": [
      {"source": "<existing repository-relative file>", "observation": "<what was observed there>"}
    ],
    "alternative": "<plausible competing explanation>",
    "expected_observation": "<observable result supporting the hypothesis>",
    "contradicting_observation": "<observable result weakening or contradicting it>",
    "initialization_reason": "<why fresh, or why transfer from this training_parent>",
    "strategy_link": "<how this experiment advances or revises the current direction>"
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
| `training` | Trains a scientific intervention. | `change` must be a non-empty description; the intervention must also be a researcher-owned code change or non-empty `params`. Transfer requires `training_parent`. |
| `continuation` | Trains the unchanged method further from an eligible lineage. | Requires `initialization: "transfer"` and `training_parent`. Code changes, parameter overrides and `change` are forbidden. |
| `replication` | Starts the current unchanged method from scratch and groups the run with an earlier experiment for replication evidence. | Requires `initialization: "fresh"`, a positive integer `replication_of` naming an existing experiment in the current campaign, and an explicit non-negative integer `training_seed`. Code changes, `params` and `change` are forbidden. |

`training_seed` is optional for ordinary training and continuation, and must be
a non-negative integer when present. `params` is optional for ordinary training
and is omitted for unchanged operations.

All `reasoning` strings must be non-empty; `evidence` contains at least one
source/observation pair. Cite inspected campaign artifacts, logs, postmortems or
code with precise observations; these are not restricted to evaluation results.
`source` is a file path without a line-number suffix or fragment; put the relevant
experiment, checkpoint, step range or code location in `observation` as needed.
The Runner checks file existence and confinement to this repository, not the
scientific conclusion or proof of inspection. This contract applies equally to
training, continuation and replication, not to the automatic baseline.

Maintain the campaign's Scientific strategy section before submitting. The
Runner requires its five entries below and snapshots it with `reasoning` in the
experiment record. Existing historical records without these fields remain
readable; a newly submitted proposal must satisfy this contract.

An eligible `training_parent` must be exposed by the brief as an active or retained lineage.
The active model's training identifier is `accepted`; retained parents use their
listed ID. The evaluation name `champion` is not a training-parent identifier.

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

**Direction:** <current research question and direction>

**Lessons and limits:** <reusable findings, source references and scope; or what remains unknown>

**Open questions:** <uncertainties not yet resolved>

**Conditional next steps:** <possible follow-ups depending on observations>

**Reconsider when:** <evidence that would justify revising or abandoning this direction>
```

Each entry must have content and may span multiple lines. This is researcher
interpretation, not a Runner verdict. Keep historical experiment entries intact;
revise this section as evidence changes. There is no cycle ID, experiment quota,
or obligation to execute the anticipated follow-ups. The brief displays this
campaign's section without generating conclusions or importing another campaign's
strategy. On adopting this protocol in an existing campaign, write the synthesis
from inspected history; the Runner does not fabricate one.

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
