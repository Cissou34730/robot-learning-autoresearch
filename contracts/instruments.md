# Scientific instruments

This document defines exact request formats, acceptance rules, and outputs.
It does not tell the PI when or whether to use an instrument.
`contracts/program.md` assigns scientific decisions to the PI.
`AGENTS.md` defines ownership and command authority.

## Operation request envelope

Write one JSON object to `pi_workspace/operation_request.json`.
The object must contain exactly one top-level operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

Measurement identities use `M#`. Training identities use `T#`.
Other event identities use `E#`.
Evidence references must identify completed operations.

## Instrument capabilities

The available interfaces have these capabilities:

- Inquiry operations record inquiry boundaries.
- Measurement operations record scientific measurements.
- `research_evaluation` and `task_reference` measure a learned candidate.
- `python_module` runs a PI-owned experiment or analysis. It does not require a learned candidate.
- Training operations produce candidates.
- Checkpoint operations save scientific session records.
- Model-role operations assign or retain candidates.
- Recipe restoration restores recorded PI-owned scientific work.
- Campaign conclusion requests the protected official assessment.

This list does not define a required sequence. It does not give preference to
an operation.

The current scientific session controls which operations the Runner accepts:

- During `startup`, the Runner accepts measurement, training, model role, recipe restoration, and checkpoint operations.
- During `goal_review`, the Runner accepts measurement, model role, inquiry open, and campaign conclusion operations.
- During `goal_review`, checkpoint becomes available only after the session opens an inquiry.
- During `inquiry`, the Runner accepts measurement, training, model role, recipe restoration, inquiry reframe, inquiry close, and checkpoint operations.

After an inquiry opens, reframes, or closes, the PI must submit a checkpoint
before another operation.

## Inquiry operations

Use this interface to open or reframe an inquiry:

```json
{
  "inquiry": {
    "action": {"type": "string"},
    "question": {"type": "string"},
    "goal_connection": {"type": "string"},
    "closure_condition": {"type": "string"},
    "rationale": {"type": "string"}
  }
}
```

Set `action` to `open` or `reframe`.
All other fields are required and must be non-empty.
The Runner accepts `open` only during goal review when no inquiry is active.
The Runner accepts `reframe` only during the active inquiry session.

Use this interface to close an inquiry:

```json
{
  "inquiry": {
    "action": {"type": "string"},
    "outcome": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `close`.
The `outcome` and `reason` fields are required and must be non-empty.
The Runner accepts `close` only during the active inquiry session.
Inquiry operations do not allocate a training identity.

## Measurement operation

```json
{
  "measurement": {
    "description": {"type": "string"},
    "rationale": {"type": "string"},
    "measurements": {"type": "array"},
    "paired_comparisons": {"type": "array"}
  }
}
```

The `description`, `rationale`, and `measurements` fields are required.
The `description` and `rationale` strings must be non-empty.
The `measurements` array must be non-empty.
The `paired_comparisons` field is optional.

A `research_evaluation` entry uses this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "episodes": {"type": "integer"},
  "seed": {"type": "integer"},
  "label": {"type": "string"}
}
```

Set `instrument` to `research_evaluation`.
The `candidate`, `episodes`, and `seed` fields are required.
The `label` field is optional.
The candidate value must be non-empty.
The episode count must be positive.
The seed must be non-negative.

The episode panel starts at `seed` and contains `episodes` consecutive episode seeds.
The Runner rejects overlap with protected benchmark evidence.

A `task_reference` entry uses this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "label": {"type": "string"}
}
```

Set `instrument` to `task_reference`.
The `candidate` field is required and must be non-empty.
The `label` field is optional.
This instrument uses its protected fixed panel.

A `python_module` entry runs one PI-owned Python module as a measurement.
It can characterize the embodied system, simulation, learning process, or
another scientific quantity. It does not require a learned candidate.

Use this interface:

```json
{
  "instrument": {"type": "string"},
  "module": {"type": "string"},
  "args": {"type": "array", "items": {"type": "string"}},
  "artifact": {"type": "string"},
  "label": {"type": "string"}
}
```

Set `instrument` to `python_module`.
The `module`, `args`, and `artifact` fields are required.
The `label` field is optional.
The module must be under `robot_learning.lab`, `robot_learning.scenario`, or
`robot_learning.training`.
The artifact must be a campaign JSON path under
`campaigns/evaluations/<current-campaign-id>/`.
`campaigns/brief.md` gives the exact evaluation root for the current campaign.

A paired-comparison entry uses this interface:

```json
{
  "candidate": {"type": "string"},
  "reference": {"type": "string"}
}
```

Both fields are required and must be non-empty.
Both candidates must appear in planned esearch_evaluation measurements that
use the same episode seeds.

The result keeps the accepted candidate artifacts, evaluator semantics, module
sources, PI-owned scientific changes, and effective parameters.
It also keeps reused-panel identities and paired-comparison integrity facts.

### Artifact contents metadata

A completed measurement record keeps compact result facts, the artifact path,
and the immutable artifact fingerprint.
`evaluation_artifact_contents` adds navigation metadata from the JSON artifact:

```json
{
  "scope": {"type": "string"},
  "truncated": {"type": "boolean"},
  "sections": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "path": {"type": "string"},
        "type": {"type": "string"},
        "entries": {"type": "integer"},
        "field_names": {"type": "array", "items": {"type": "string"}},
        "field_count": {"type": "integer"},
        "fields_omitted": {"type": "boolean"}
      }
    }
  }
}
```

The scope is `structure_only`.
The inventory contains no measurement values or scientific interpretation.
Paths use JSON Pointer syntax.
The empty pointer identifies the root.
Escaped tokens identify object members.
Object and array sections include their entry counts.

The inventory traverses object members breadth-first.
It does not expand array elements into individual paths.
When present, `field_names` contains the union of keys in actual object rows of
an array. It is not a schema inferred from one sample row.

The inventory has a bounded metadata size.
`truncated` identifies omitted sections or field names.
`fields_omitted` and `field_count` identify an array whose field list did not fit.
An untruncated inventory still describes structure, not the full evidence.
The full artifact remains unchanged at its recorded path.

This metadata applies to all measurement instruments.
It does not require a scenario-specific section or field.
Live feedback and the brief distinguish the reduced result summary from the
artifact contents. They also identify results with no recorded inventory.

## Training operation

```json
{
  "training": {
    "initialization": {"type": "string"},
    "parent": {"type": "string"},
    "seed": {"type": "integer"},
    "steps": {"type": "integer"},
    "description": {"type": "string"},
    "rationale": {"type": "string"}
  }
}
```

Set `initialization` to `fresh` or `transfer`.
The `seed`, `steps`, `description`, and `rationale` fields are required.
The seed must be non-negative.
The `description` and `rationale` strings must be non-empty.
The `steps` value must be a positive integer.

During startup, the PI can request any positive value up to the maintainer's
current allocation. The phase prompt shows this allocation.
During an inquiry, `steps` must equal the allocation.
The maintainer configures the allocation with launcher `-Timesteps` or Runner
`--timesteps`.
The PI must not raise the allocation.
The Runner rejects requests outside the session allocation contract during
validation, acceptance, and training dispatch.

For transfer training, `parent` is required and must be non-empty.
For fresh training, omit `parent`.

The Runner validates changed PI-owned sources and active parameters.
It executes the accepted seed and step count.
It archives all produced candidates.
It records the parent, scientific recipe, and learning-dynamics facts.
Completion does not assign working, best-known, or retained roles.

The learning algorithm can round actual completed steps up to its rollout
boundary. This does not authorize a different allocation.
Before dispatch, an accepted training request must still satisfy the current
session allocation contract.
A completed result can finish publication without a new training allocation.

## Scientific session record

The `checkpoint` operation saves the scientific session record.
It does not save policy weights.
A policy checkpoint is a separate training artifact.

```json
{
  "checkpoint": {
    "human_goal_connection": {"type": "string"},
    "current_goal_gap": {"type": "string"},
    "current_synthesis": {"type": "string"},
    "evidence_references": {
      "type": "array",
      "items": {"type": "string"}
    },
    "decision_frontier": {"type": "string"},
    "next_question": {"type": "string"},
    "completed_operations": {
      "type": "array",
      "items": {"type": "string"}
    },
    "candidates_and_roles": {"type": "string"},
    "next_direction_or_closure": {"type": "string"},
    "cumulative_resource_use": {"type": "string"}
  }
}
```

Every field is required.
All string fields must be non-empty.
`next_question` states the exact scientific question that the same PI carries
into the next fresh context.
Startup selects the first inquiry question.
An inquiry closure selects the question for the next inquiry.
If the same inquiry continues, the checkpoint repeats its current question.
The goal-review checkpoint repeats the question of the inquiry that it opened.
`completed_operations` must exactly match the active session's completed
operation identities.
Every evidence reference must identify a completed operation.
Artifact paths are operation outputs, not independent evidence references.
The accepted scientific session record ends the current scientific session.

## Model-role operation

```json
{
  "model_role": {
    "action": {"type": "string"},
    "candidate": {"type": "string"},
    "label": {"type": "string"},
    "reason": {"type": "string"},
    "evidence": {
      "type": "array",
      "items": {"type": "string"}
    }
  }
}
```

Set `action` to `set_working`, `set_best_known`, or `retain`.
The `candidate`, `reason`, and `evidence` fields are required.
The evidence array must be non-empty.
Each evidence item must identify a completed operation.

The `label` field is required only for retention.
The label must be non-empty and unique.
It must differ from the fixed role names.

The `retain` action archives the candidate under the requested label.
Each action updates only the requested role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Both fields are required and must be non-empty.
The operation restores the PI-owned scientific files and parameters from the
candidate's recorded recipe.
It removes PI-owned files that are absent from that recipe.
It verifies the result.
It does not assign a model role.

## Campaign conclusion

```json
{
  "campaign_conclusion": {
    "action": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Set `action` to `request_official_assessment`.
The `reason` field is required and must be non-empty.
The Runner accepts the request only during goal review when no inquiry is active.
The request also requires an explicit best-known candidate.
The Runner executes the protected official assessment and records its result.
No other campaign-conclusion action is supported.

## Scientific-model publication

Before other campaign work, `pi_workspace/scientific_model.md` must contain
substantive `Established facts`, `Physical consequences`, and `Unknowns` registers.
An analyst persona, not the PI, writes the model. The model states physical
consequences and the evidence that discriminates between them. It selects no
intervention. The PI reads the whole model at startup and selects the initial
direction.
After acceptance, the model remains fixed for the campaign.
Later checkpoints preserve or revise its consequential conclusions.
The Runner checks only that the file exists and that each required register
section is present and non-empty. It does not check scientific adequacy.
The PI alone is responsible for whether the model is scientifically sound.
