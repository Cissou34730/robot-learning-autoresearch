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

Open:

```json
{
  "inquiry": {
    "action": "open",
    "question": "<non-empty string>",
    "goal_connection": "<non-empty string>",
    "closure_condition": "<non-empty string>",
    "rationale": "<non-empty string>"
  }
}
```

Reframe:

```json
{
  "inquiry": {
    "action": "reframe",
    "question": "<non-empty string>",
    "goal_connection": "<non-empty string>",
    "closure_condition": "<non-empty string>",
    "rationale": "<non-empty string>"
  }
}
```

Close:

```json
{
  "inquiry": {
    "action": "close",
    "outcome": "<non-empty string>",
    "reason": "<non-empty string>"
  }
}
```

Opening is accepted only in a goal-review session with no active inquiry.
Reframing and closing require the active inquiry's session. Inquiry operations
allocate no training identity.

## Measurement operation

```json
{
  "measurement": {
    "description": "<non-empty string>",
    "rationale": "<non-empty string>",
    "measurements": [
      {
        "instrument": "research_evaluation",
        "candidate": "<candidate ID or model role>",
        "episodes": 100,
        "seed": 1000,
        "label": "<optional string>"
      },
      {
        "instrument": "task_reference",
        "candidate": "<candidate ID or model role>",
        "label": "<optional string>"
      },
      {
        "instrument": "python_module",
        "module": "research.lab.example",
        "args": ["--output", "research/evaluations/<campaign>/example.json"],
        "artifact": "research/evaluations/<campaign>/example.json",
        "label": "<optional string>"
      }
    ],
    "paired_comparisons": [
      {"candidate": "<measured candidate>", "reference": "<measured candidate>"}
    ]
  }
}
```

`measurements` is non-empty. `research_evaluation` accepts a positive episode
count and non-negative seed. `task_reference` uses its protected fixed panel.
`python_module` modules are limited to `research.lab` or
`robot_learning.scenario`; their declared JSON artifact is campaign-scoped
under `research/evaluations/`.

The accepted candidate artifacts, evaluator semantics, module sources,
PI-owned scientific changes, and effective parameters remain attached to the
result. Reused panels and paired comparisons retain their identity and
integrity checks.

## Training operation

Fresh initialization:

```json
{
  "training": {
    "initialization": "fresh",
    "seed": 7,
    "steps": 120000,
    "description": "<non-empty string>",
    "rationale": "<non-empty string>"
  }
}
```

Transfer initialization:

```json
{
  "training": {
    "initialization": "transfer",
    "parent": "<candidate ID or model role>",
    "seed": 7,
    "steps": 120000,
    "description": "<non-empty string>",
    "rationale": "<non-empty string>"
  }
}
```

The operation validates PI-owned changed sources and active parameters,
executes the requested seed and step count, archives all produced candidates,
and records the parent, scientific recipe, and learning-dynamics facts.
Completion does not assign working, best-known, or retained roles.

## Durable checkpoint

```json
{
  "checkpoint": {
    "human_goal_connection": "<non-empty string>",
    "current_goal_gap": "<non-empty string>",
    "current_synthesis": "<non-empty string>",
    "evidence_references": ["M1"],
    "decision_frontier": "<non-empty string>",
    "completed_operations": ["M1", "T1"],
    "candidates_and_roles": "<non-empty string>",
    "next_direction_or_closure": "<non-empty string>",
    "cumulative_resource_use": "<non-empty string>"
  }
}
```

`completed_operations` exactly matches the active session's completed operation
IDs. Every evidence reference is a completed operation identity. Artifact paths
are outputs of those operations, not independent evidence references. An
accepted checkpoint ends the current scientific session.

## Model-role operation

Working:

```json
{
  "model_role": {
    "action": "set_working",
    "candidate": "<candidate ID or model role>",
    "reason": "<non-empty string>",
    "evidence": ["<completed operation ID>"]
  }
}
```

Best-known uses the same shape with `"action": "set_best_known"`.

Retention adds a label:

```json
{
  "model_role": {
    "action": "retain",
    "candidate": "<candidate ID or model role>",
    "label": "<unique non-empty label>",
    "reason": "<non-empty string>",
    "evidence": ["<completed operation ID>"]
  }
}
```

Evidence entries name completed operation IDs. Retention archives the candidate
under the requested label and updates only the requested role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": "<candidate ID or model role>",
    "reason": "<non-empty string>"
  }
}
```

The operation restores the PI-owned scientific files and parameters represented
by the candidate's recorded recipe, removes PI-owned files absent from that
recipe, and verifies the result. It does not assign a model role.

## Campaign conclusion

Official assessment request:

```json
{
  "campaign_conclusion": {
    "action": "request_official_assessment",
    "reason": "<non-empty string>"
  }
}
```

No-route conclusion:

```json
{
  "campaign_conclusion": {
    "action": "no_credible_route",
    "reason": "<non-empty string>"
  }
}
```

Both forms require a goal-review session and no active inquiry. The assessment
request also requires an explicit best-known candidate. It executes the
protected official assessment and records its passed or failed result.
`no_credible_route` records the terminal state without running an assessment.

## Scientific-model publication

Before other campaign work, `research/scientific_model.md` must contain
substantive `Established facts`, `Physical consequences`, and `Unknowns`
registers. Once accepted, it remains fixed for the campaign.
