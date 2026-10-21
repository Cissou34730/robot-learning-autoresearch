# Scientific instruments

This document defines request formats, acceptance rules and outputs.
`contracts/program.md` defines the research lifecycle and the PI's decisions.
`contracts/authority.md` defines ownership and role permissions.

This file contains the request envelope, the operations that each session
accepts and the scientific session record. Read a part below only when you use
it:

- `contracts/instruments/measurement.md` - measurement operation and artifact
  contents metadata;
- `contracts/instruments/training.md` - training, model-role and
  recipe-restoration operations;
- `contracts/instruments/inquiry.md` - inquiry operations and campaign
  conclusion;
- `contracts/instruments/coding.md` - saved controller execution and the
  scientific coding interface;
- `contracts/instruments/readers.md` - source readers, installed API
  reference, JSON evidence, training logs and numeric summary tools;
- `contracts/instruments/scientific-model.md` - scientific-model publication.

## Paths and evidence storage

Paths in requests and records are logical repository-relative paths. The read
tools resolve each logical path to its storage location. Read access does not
grant write access.

Scientific code and operation records are versioned with the campaign. Raw
measurement artifacts and training logs stay in the local campaign folder.
Operation records keep their paths and fingerprints, and the evidence tools
read and verify them.

## Operation request envelope

Call `submit_operation` with a `request` containing one JSON operation object.
The call is bound to the active campaign and session. Runner validates the
request and executes it. The object must contain exactly one top-level
operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

The tool schema shows the exclusive wrappers and their body structures. Runner
checks the structure, then validates the operation body against the active
state. A flat operation record with `kind` and body fields is not a submission
envelope. Errors identify missing wrappers, extra top-level fields or a
non-object body.

Measurement identities use `M#`. Training identities use `T#`.
Other event identities use `E#`.
Evidence references must identify completed operations.

`submit_operation` returns a compact factual result or the exact rejection or
error, the operation identity when completed, and the changed state: session
identity and kind, completed-operation list, model roles, pending or terminal
status, currently permitted operation kinds and any required checkpoint.
Complete artifact inventories and logs are not attached; read them through
`artifact_evidence_query` and `training_log_query`. Ordinary results continue
in the same conversation. Opening, reframing or closing an inquiry makes the
checkpoint the only next operation. A completed checkpoint or terminal
commitment ends the session; the next session starts from durable state.

Correct a rejected request in the same conversation. A second rejected
submission ends the session.

`implementation_error` means that an accepted operation failed during
execution. It does not diagnose a source defect. Inspect the actual error and
the accepted invocation, then decide whether to correct the request or change
the source. `artifact_evidence_query` with `action=metadata`, the pending
`operation_id` and `path=/pending` returns the exact request and its resolved
measurements.

- To change arguments, submit a replacement envelope.
- To change source, use `scientific_coding`, then submit `{"request": null}`
  to reaccept the same pending request. `null` cannot change arguments.

An execution failure is history, not scientific evidence. After
`validation_fatal`, `controller_fatal`, a publication failure, an interruption,
a terminal result or a recovery-required result, the session accepts no further
submissions or evidence queries.

## Operations by session

The operation kinds have these purposes:

- Inquiry operations open, reframe and close inquiries.
- Measurement operations record scientific measurements.
- `research_evaluation` and `task_reference` measure a learned candidate.
- `python_module` runs a PI-owned experiment or analysis. It does not require a learned candidate.
- Training operations produce candidates.
- Checkpoint operations save scientific session records.
- Model-role operations assign or retain candidates.
- Recipe restoration restores recorded PI-owned scientific work.
- Campaign conclusion requests the protected official assessment.

This list does not define a sequence or a preference. `scientific_coding` and
the evidence readers are tools, not operations; they are available in every PI
session.

The current scientific session controls which operations the Runner accepts:

- During `startup`, the Runner accepts measurement, training, model role, recipe restoration, and checkpoint operations.
- During `goal_review`, the Runner accepts measurement, model role, inquiry open, and campaign conclusion operations.
- During `goal_review`, checkpoint becomes available only after the session opens an inquiry.
- During `inquiry`, the Runner accepts measurement, training, model role, recipe restoration, inquiry reframe, inquiry close, and checkpoint operations.

After an inquiry opens, reframes, or closes, the PI must submit a checkpoint
before another operation.

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
`current_goal_gap` states the gap in numbers: the goal from
`contracts/scenario.md`, the best candidate's measured result with the panels it
combines, and the improvement still needed. When the goal is a success rate,
include the estimated probability of reaching it, for example from
`success_rate_pass_probability`.
`next_question` depends on the session kind:

- startup, or an inquiry session that closed its inquiry: the proposed question
  for the next goal review;
- goal review: the exact question of the inquiry opened in that session;
- an inquiry session whose inquiry stays active: the exact active question.

`completed_operations` must exactly match the active session's completed
operation identities.
Opening, reframing or closing an inquiry does not end the active scientific session.
The checkpoint transition prompt supplies the session identity and exact operation list.
The Runner rejects a mismatched list without changing the session.
Its error reports the session identity, expected list and submitted list.
Every evidence reference must identify a completed operation.
Artifact paths are operation outputs, not independent evidence references.
The accepted scientific session record ends the current scientific session.
