# Scientific instruments

This document specifies exact request shapes, acceptance conditions, and
outputs. It does not recommend when or whether to use an instrument.
Scientific decisions belong to the PI under `research/program.md`; ownership
and command authority are defined in `AGENTS.md`.

## Operation request envelope

Write `research/operation_request.json` as one JSON object containing exactly
one top-level operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

Measurement identities are `M#`, training identities are `T#`, and other event
identities are `E#`. Only completed identities may be cited as evidence.

Accepted operations depend on the current scientific session:

- `startup`: measurement, training, model role, recipe restoration, checkpoint;
- `goal_review`: inquiry open or campaign conclusion; checkpoint becomes
  available only after that session opens the inquiry;
- `inquiry`: measurement, training, model role, recipe restoration, inquiry
  reframe or close, checkpoint.

Opening, reframing, and closing an inquiry require a checkpoint before another
operation.

## Inquiry operations

Open and reframe use this interface:

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

`action` is `open` or `reframe`. All other fields are required and non-empty.
Opening is accepted only in a goal-review session with no active inquiry.
Reframing requires the active inquiry's session.

Close uses this interface:

```json
{
  "inquiry": {
    "action": {"type": "string"},
    "outcome": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

`action` is `close`. `outcome` and `reason` are required and non-empty. Closing
requires the active inquiry's session. Inquiry operations allocate no training
identity.

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

`description`, `rationale`, and `measurements` are required.
`paired_comparisons` is optional. The strings are non-empty and
`measurements` is non-empty.

A `research_evaluation` entry has this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "episodes": {"type": "integer"},
  "seed": {"type": "integer"},
  "label": {"type": "string"}
}
```

`instrument` is `research_evaluation`. `candidate`, `episodes`, and `seed` are
required; `label` is optional. The candidate is non-empty, the episode count is
positive, and the seed is non-negative. The episode panel is the half-open
interval beginning at `seed` and containing `episodes` consecutive episode
seeds. The Runner rejects overlap with protected benchmark evidence.

A `task_reference` entry has this interface:

```json
{
  "instrument": {"type": "string"},
  "candidate": {"type": "string"},
  "label": {"type": "string"}
}
```

`instrument` is `task_reference`. `candidate` is required and non-empty;
`label` is optional. The instrument uses its protected fixed panel.

A `python_module` entry has this interface:

```json
{
  "instrument": {"type": "string"},
  "module": {"type": "string"},
  "args": {"type": "array", "items": {"type": "string"}},
  "artifact": {"type": "string"},
  "label": {"type": "string"}
}
```

`instrument` is `python_module`. `module`, `args`, and `artifact` are required;
`label` is optional. The module is under `research.lab` or
`robot_learning.scenario`. The artifact is a campaign-scoped JSON path under
`research/evaluations/`.

A paired-comparison entry has this interface:

```json
{
  "candidate": {"type": "string"},
  "reference": {"type": "string"}
}
```

Both fields are required and non-empty. Both candidates must have planned
`research_evaluation` measurements with shared episode seeds.

The accepted candidate artifacts, evaluator semantics, module sources,
PI-owned scientific changes, effective parameters, reused-panel identities,
and paired-comparison integrity facts remain attached to the result.

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

`initialization` is `fresh` or `transfer`. `seed`, `steps`, `description`, and
`rationale` are required. The seed is non-negative, the step count is positive,
and the strings are non-empty. `parent` is required and non-empty for transfer
training and is omitted for fresh training.

The operation validates PI-owned changed sources and active parameters,
executes the requested seed and step count, archives all produced candidates,
and records the parent, scientific recipe, and learning-dynamics facts.
Completion does not assign working, best-known, or retained roles.

## Durable checkpoint

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

Every field is required. String fields are non-empty. `completed_operations`
exactly matches the active session's completed operation IDs. Every evidence
reference is a completed operation identity. Artifact paths are outputs of
those operations, not independent evidence references. An accepted checkpoint
ends the current scientific session.

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

`action` is `set_working`, `set_best_known`, or `retain`. `candidate`, `reason`,
and `evidence` are required. The evidence array is non-empty and names
completed operation identities. `label` is required only for retention and
must be non-empty, unique, and distinct from the fixed role names.

Retention archives the candidate under the requested label. Each action
updates only the requested role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

Both fields are required and non-empty. The operation restores the PI-owned
scientific files and parameters represented by the candidate's recorded recipe,
removes PI-owned files absent from that recipe, and verifies the result. It does
not assign a model role.

## Campaign conclusion

```json
{
  "campaign_conclusion": {
    "action": {"type": "string"},
    "reason": {"type": "string"}
  }
}
```

`action` is `request_official_assessment` or `no_credible_route`. `reason` is
required and non-empty. Both actions require a goal-review session and no
active inquiry. An assessment request also requires an explicit best-known
candidate. It executes the protected official assessment and records its
result. `no_credible_route` records the terminal state without running an
assessment.

## Scientific-model publication

Before other campaign work, `research/scientific_model.md` must contain
substantive `Established facts`, `Physical consequences`, and `Unknowns`
registers. Once accepted, it remains fixed for the campaign.
