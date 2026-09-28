# Runner instruments

This document specifies strict schema-6 invocation and artifact contracts.
Ownership and command authority are defined in `AGENTS.md`.

## Operation request envelope

Each Runner round trip reads `research/operation_request.json`. The file is one
JSON object containing exactly one top-level operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

The Runner validates the request, assigns an operation identity, freezes its
inputs in `research/research_state.json`, executes it, records the completed
event in state and `research/results.jsonl`, updates `research/EXPERIMENTS.md`,
and removes the consumed request. A failed transaction remains in
`pending_operation`; reacceptance preserves the request and assigns a
superseding operation identity after implementation repair.

Measurement identities are `M#`, training identities are `T#`, and other event
identities are `E#`.

Operation availability is strict:

- `startup`: measurement, training, model role, recipe restoration, checkpoint;
- `goal_review`: inquiry open, campaign conclusion, checkpoint;
- `inquiry`: measurement, training, model role, recipe restoration, inquiry
  reframe or close, checkpoint.

Opening, reframing, and closing an inquiry require a checkpoint before another
operation. A checkpoint or terminal campaign conclusion clears the active
scientific session and its bounded backend-session identity.

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

Opening is accepted only in a goal-review session with no active inquiry and
while the persisted `max_inquiries` guard permits another identity. Reframing
and closing require the active inquiry's session. Inquiry operations allocate
no training identity.

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

Candidate artifacts, evaluator semantics, module sources, PI-owned scientific
changes, and effective parameters are frozen at acceptance. Completed
measurement artifacts are fingerprinted and recorded. Reused panels and paired
comparisons retain their existing identity and integrity checks.

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

The Runner validates PI-owned changed sources and active parameters, publishes
the exact scientific recipe, records the parent identity when present,
executes the requested seed and step count, archives all produced candidates,
and records learning-dynamics facts and mechanical provenance. Completion does
not assign working, best-known, or retained roles.

Interrupted execution resumes the accepted transaction and candidate location;
it does not allocate a second training identity.

## Durable checkpoint

```json
{
  "checkpoint": {
    "human_goal_connection": "<non-empty string>",
    "current_goal_gap": "<non-empty string>",
    "current_synthesis": "<non-empty string>",
    "evidence_references": ["M1", "research/evaluations/<campaign>/detail.json"],
    "decision_frontier": "<non-empty string>",
    "completed_operations": ["M1", "T1"],
    "candidates_and_roles": "<non-empty string>",
    "next_direction_or_closure": "<non-empty string>",
    "cumulative_resource_use": "<non-empty string>"
  }
}
```

`completed_operations` exactly matches the active session's completed operation
IDs. Each evidence reference is either a completed operation ID or an existing
repository-relative file. The Runner publishes the session's PI-owned
scientific surface, stores the checkpoint with its commit and session/inquiry
identity, and clears the active scientific session.

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

Evidence entries name completed operation IDs. The Runner publishes the
candidate under the campaign retained archive and updates only the requested
role.

## Recipe restoration

```json
{
  "restore_recipe": {
    "candidate": "<candidate ID or model role>",
    "reason": "<non-empty string>"
  }
}
```

The Runner resolves the candidate's recorded scientific commit, restores the
PI-owned scientific files and parameters represented by that recipe, removes
PI-owned files absent from it, verifies the result, and updates the active
session's scientific parent commit. It does not assign a model role.

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
request also requires an explicit best-known candidate. The Runner records the
terminal request, clears the scientific session, executes the protected
official assessment as a separate Runner-owned transition, and records its
passed or failed result. `no_credible_route` records the terminal state without
running an assessment.

## Scientific-model publication

Before any scientific session exists, the launcher validates
`research/scientific_model.md` for the `Established facts`, `Physical
consequences`, and `Unknowns` registers. The Runner commits the exact file,
records its commit in schema-6 state, and permits scientific sessions only
after publication.
