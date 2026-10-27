# Scientific instruments

This document defines the request formats, the acceptance rules and the
outputs. `contracts/program.md` defines the research process and your
decisions. `contracts/authority.md` defines the ownership and the permissions
of each role.

This file contains the request envelope, the operations that each session
accepts and the session record. Read a part below only when you use it:

- `contracts/instruments/measurement.md` - the measurement operation and the
  artifact contents metadata
- `contracts/instruments/training.md` - the training, role and recipe
  restoration operations
- `contracts/instruments/inquiry.md` - the inquiry operations and the request
  for the official assessment
- `contracts/instruments/coding.md` - the saved runtime and the scientific
  coding tool
- `contracts/instruments/readers.md` - the source readers, the installed
  library reference, the JSON evidence, the training logs and the numeric
  summary tools
- `contracts/instruments/scientific-model.md` - the publication of the
  scientific model

## Paths and evidence storage

Paths in requests and records are logical paths, relative to the repository.
The read tools find the storage location of each logical path. Read access does
not give write access.

The campaign keeps versions of the scientific code and of the operation
records. The raw measurement artifacts and the training logs stay in the local
campaign folder. Operation records keep their paths and fingerprints. The
evidence tools read and verify them.

## Operation request envelope

Call `submit_operation` with a `request` that contains one JSON operation
object. The call applies to the active campaign and session. The Runner
validates the request and executes it. The object must contain exactly one
top-level operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

The tool schema shows the exclusive wrappers and the structure of their
bodies. The Runner checks the structure. Then it validates the operation body
against the active state. A flat operation record with `kind` and body fields
is not a submission envelope. The errors identify missing wrappers, extra
top-level fields or a body that is not an object.

Measurement identities use `M#`. Training identities use `T#`. Other event
identities use `E#`. Evidence references must identify completed operations.

`submit_operation` returns one of these: a short factual result, or the exact
rejection or error. It also returns the operation identity when the operation
completed, and the changed state. The changed state contains:

- the session identity and kind
- the list of completed operations
- the roles
- the pending or final status
- the operation kinds that you can submit now
- a required `checkpoint`, if there is one

The result does not include complete artifact inventories and logs. Read them
through `artifact_evidence_query` and `training_log_query`. After a normal
result, continue in the same conversation. When you open, reframe or close an
inquiry, the `checkpoint` operation is the only next operation. A completed
`checkpoint` or a request for the official assessment ends the session. The
next session starts from the saved state.

When the Runner rejects a request, correct it in the same conversation. A
second rejected request ends the session.

`implementation_error` means that an accepted operation failed during its
execution. It does not diagnose a defect in the source code. Read the actual
error and the accepted invocation. Then decide if you correct the request or
change the source code. `artifact_evidence_query` with `action=metadata`, the
pending `operation_id` and `path=/pending` returns the exact request and its
resolved measurements.

- To change arguments, submit a replacement envelope.
- To change source code, use `scientific_coding`. Then submit
  `{"request": null}` to accept the same pending request again. `null` cannot
  change arguments.

An execution failure is history, not scientific evidence. After one of these
results, the session accepts no more requests or evidence queries:
`validation_fatal`, `controller_fatal`, a publication failure, an
interruption, a final result, or a result that requires recovery.

## Operations by session

The operation kinds have these purposes:

- Inquiry operations open, reframe and close inquiries.
- Measurement operations record scientific measurements.
- `research_evaluation` and `task_reference` measure a candidate.
- `python_module` runs an experiment or an analysis from a PI-owned module. It
  does not need a candidate.
- Training operations make candidates.
- The `checkpoint` operation saves the session record.
- Role operations (`model_role`) give a role to a candidate or keep a
  candidate under a label.
- Recipe restoration restores recorded PI-owned scientific work.
- `campaign_conclusion` requests the protected official assessment.

This list does not give a sequence or a priority. `scientific_coding` and the
evidence tools are tools, not operations. They are available in each PI
session.

The kind of the current session sets the operations that the Runner accepts:

- In a startup session, the Runner accepts measurement, training, role, recipe
  restoration and `checkpoint` operations.
- In a goal-review session, the Runner accepts measurement, role, inquiry open
  and `campaign_conclusion` operations.
- In a goal-review session, `checkpoint` is available only after you open an
  inquiry.
- In an inquiry session, the Runner accepts measurement, training, role, recipe
  restoration, inquiry reframe, inquiry close and `checkpoint` operations.

After you open, reframe or close an inquiry, you must submit a `checkpoint`
before any other operation. `contracts/glossary.md` shows the same rules in a
table.

## Session record

The `checkpoint` operation saves the session record. It does not save policy
weights. A training checkpoint is a different artifact that training makes.

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

Each field is required. Each string field must not be empty.

`current_goal_gap` gives the gap in numbers: the goal from
`contracts/scenario.md`, the measured result of the best candidate with the
panels that it combines, and the improvement that the campaign still needs.
When the goal is a success rate, include the estimated probability to reach it.
For example, use `success_rate_pass_probability` with recorded measurements, so
that each count comes from the record of the cited operation and candidate.

`next_question` depends on the kind of session:

- startup session, or inquiry session that closed its inquiry: the proposed
  question for the next goal-review session
- goal-review session: the exact question of the inquiry that you opened in
  this session
- inquiry session in which the inquiry stays active: the exact question of the
  active inquiry

`completed_operations` must be exactly the completed operation identities of
the active session. When you open, reframe or close an inquiry, the session
does not end. The prompt for the `checkpoint` gives the session identity and the
exact list of operations. The Runner rejects a list that is different and does
not change the session. Its error gives the session identity, the expected list
and the submitted list.

Each evidence reference must identify a completed operation. Artifact paths are
outputs of operations, not separate evidence references. The accepted session
record ends the current session.
