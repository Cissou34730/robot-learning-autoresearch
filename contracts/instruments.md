# Scientific instruments

This document defines exact request formats, acceptance rules, and outputs.
It does not tell the PI when or whether to use an instrument.
`contracts/program.md` assigns scientific decisions to the PI.
`AGENTS.md` defines ownership and command authority.

## Operation request envelope

In ordinary Copilot sessions, call `submit_operation` with a `request` containing
one JSON operation object. The payload formats below are unchanged. The trusted
launcher binds the call to the active campaign and bounded session, validates
with Runner's existing schema-6 acceptance checks, and executes through Runner.
No model-supplied Runner arguments or exchange paths are accepted.
The object must contain exactly one top-level operation kind:

```text
inquiry | measurement | training | checkpoint | model_role |
restore_recipe | campaign_conclusion
```

Measurement identities use `M#`. Training identities use `T#`.
Other event identities use `E#`.
Evidence references must identify completed operations.

`submit_operation` returns a compact factual result or the exact rejection/error,
operation identity when completed, and changed state: session identity and kind,
actual completed-operation list, roles, resource counts, pending/terminal status,
and required checkpoint transition. Detailed artifacts stay available through
`artifact_evidence_query`; preserved training logs through `training_log_query`.
Ordinary results continue in this same conversation,
without a new runtime or replayed phase prompt. Inquiry open/reframe/close makes
checkpoint the sole next operation. A completed checkpoint or terminal commitment
ends this context; the launcher creates the next bounded context when permitted.
The SDK process/client remains alive across those contexts.

Correct a rejected request in this conversation. Two rejected submissions stop
the bounded session, preserving the existing one-retry limit. Implementation
errors retain the PI's repair authority: diagnose, use `scientific_coding` for
source repair, review actual changes, and submit a replacement envelope or
`{"request": null}` to reaccept the failed pending operation after repair.
An execution failure is history, not scientific evidence. Publication failures,
interruption, terminality and recovery-required results prohibit further
submission in that context. The controller recovers existing accepted/completed
transactions after channel loss; it does not blindly replay a tool call or
fabricate checkpoint content. Main SDK resumes explicitly disable automatic
unfinished-work continuation; the existing resume prompt includes current
durable Runner metadata. Validation capture is silent. Execution stdout/stderr
stream live, without a second log dump; only bounded tails are retained for
useful error feedback. Runner waiting uses no model polls and is excluded
from PI active duration; coding usage remains separate.
Stop requests remain cooperative. If the launcher deadline expires, it stops
only its owned process tree and preserves the existing transaction for recovery.

Copilot main PI sessions never author the exchange file.
The optional OpenCode backend retains its existing file-based interface:
write one operation object to `pi_workspace/operation_request.json`.
For this legacy interface, the Runner replaces an accepted proposal with an acceptance marker.
The Runner removes that marker after it finalizes the operation.
The request file can therefore be absent after an accepted operation completes.
Create the next proposal at the same path when the previous request is absent.
Do not update or delete a previous request without checking that it exists.
A rejected proposal remains available for correction.

## Scientific coding interface

Ordinary Copilot main PI sessions expose `scientific_coding` and
`submit_operation` alongside source readers, `artifact_evidence_query` and
`training_log_query`. They have no `apply_patch`, other file-write tools or
shell tools. The preliminary scientific-model session retains its existing
publication interface and does not expose coding.

`scientific_coding` accepts:

- `intent`: the bounded scientific change;
- `allowed_paths`: exact repository-relative writable scientific files;
- `read_paths`: optional additional relevant scientific or contract files;
- `source_context`: optional source context selected by the main PI;
- `verification_path`: a Python module file under `robot_learning/lab/`,
  included in `allowed_paths`;
- `session_handle`: optional returned native child identity for same-change
  corrections within this bounded context.

Protected paths, directories, wildcard scopes, operation requests and arbitrary
filesystem paths are refused. A continued child must keep the same writable,
readable and verification scope. The SDK dispatches the registered native
coding subagent with the supplied objective and source context, rather than
creating a separate SDK session or passing the PI's campaign conversation.
Corrections are sent to that same native child.
Native handles are context-local, not resumable authority across a runtime
restart or a fresh scientific context. The handler resolves and validates the
SDK's model/tool configuration before dispatch; unavailable capabilities are
reported rather than falling back to manual coding sessions.

The default/main agent excludes file-write tools. The registered coder has
scoped `view` and `apply_patch` only; it cannot execute code, delegate further
or submit campaign operations. Hooks and permission callbacks bind its calls
to the authorized native child and file scope. Native start instructions
include the installed scientific API versions and dependency restrictions.
Completion handling challenges an incomplete engineering handoff, not
scientific adequacy or research direction.
The stop hook applies to corrections as well as the initial invocation.
The handler waits for the stop handoff and native task idle state before
unlocking operation submission.

The result returns the child handle, actual per-invocation changed-file manifest
and diff, verification module, proposed `python_module` entry and unchecked
scope. Large review output is offloaded with a file pointer. Errors and timeouts
return partial changes when available; cancellation preserves review output.
The proposed check is not executed by this tool. The main PI reviews the actual
changed source and executable check before scientific reliance or submission.
Runner executes the reviewed check through the existing measurement instrument.
No coding result certifies scientific validity. Native task lifecycle is
owned by Copilot SDK 1.0.19; operation acceptance and scientific execution
remain owned by the existing trusted controller and Runner.
Usage and changes are reported per invocation. SDK native-task lifetime totals
are labeled separately and must not be added again on each correction.

## Source readers

Copilot `view` reads exact permitted files. Directory enumeration uses `glob`.
The trusted `rg` and `glob` interfaces apply the same phase-aware read policy
to descendants before reading content or returning paths. A readable parent
does not authorize reserved descendants. Linked paths and outside-repository
aliases are unavailable. Explicitly reserved search roots are rejected;
reserved descendants of readable roots are pruned.

Both search interfaces accept default, subdirectory or multiple `paths`.
`glob` selects file paths by pattern. `rg` accepts content, matching-file or
count output, with pattern, glob, type, context and result-limit selectors.
Results report output or traversal limits explicitly. A truncated result does
not establish that unreturned matches are absent. Exact-file reads remain
available for content that exceeds search-preview limits.

The preliminary analyst retains exact permitted shell file reads, but shell
traversal and wildcard readers are denied. Coding children have only the
exact-file `view` and `apply_patch` binding described above, not search tools.

## JSON evidence interface

`artifact_evidence_query` is the single JSON evidence tool. It resolves a
recorded artifact from a completed measurement operation in the active
campaign and verifies its recorded fingerprint. The PI supplies operation
identity, not an arbitrary filesystem path.

The interface supports:

- `discover`: inspect the structure under an optional prefix;
- `query`: select one path, with optional filtering, projection or aggregation;
- `batch`: apply related query specifications to the same verified artifact;
- `read`: retrieve the artifact's complete content through successive pages.

The PI selects the requested scope. A complete artifact is permitted;
selected fields, summaries and repeated requests for different subsets are
also permitted. Query output is selected before it enters the conversation.
The tool does not execute Python query expressions or interpret the science.

Discovery and query output report truncation and exhausted limits explicitly.
Read and query pages identify their offsets and continuation. Content identity
must remain stable across a continuation; a mismatched identity is an error,
not a page from a different artifact. Partial output is not complete evidence
and does not establish that unreturned fields or records are absent.

For `query` and each `batch` specification, `offset` counts selected records
after filtering and projection, or distinct values for `value_counts`.
`limit` controls the page size. The returned `next_offset` retrieves the
remaining selection. Oversized individual objects remain available through
`read` even when they cannot fit in a query page.

For `read`, `offset` and `max_bytes` refer to original file bytes.
`encoding` selects readable UTF-8 or base64 for other byte encodings.
UTF-8 pages preserve line endings and do not split a character. The returned
`next_offset` and verified fingerprint identify continuation;
`expected_fingerprint` is required for a nonzero read offset. Joining pages
in offset order reconstructs the complete original content. Full retrieval
does not require parsing the entire artifact within the query budget.

## Training-log interface

`training_log_query` exposes the existing training-record parser as a
read-only custom tool. It resolves preserved logs using the active campaign
and training operation identity, not a filesystem path or command.

`records` requests select attempts, timestep bounds and metric fields.
`raw` requests return preserved log text, including content outside parsed
training records. Complete logs and successive pages are supported. The PI
may request different subsets in separate calls without rerunning training.
The tool reports missing logs, empty selections, available continuation and
content identities explicitly.

`attempts` selects preserved attempt numbers. `records` uses optional
`from_step`, `to_step` and `metrics`, with `offset` and `limit` for selected
row pages. Nonzero row offsets require `expected_log_fingerprints` from the
previous response. Missing metrics are identified separately from zero.
The operation's status does not establish each attempt's outcome.

`raw` selects one attempt when multiple logs exist. Its `offset`, `max_bytes`,
`encoding` and `expected_fingerprint` use the same original-byte continuation
semantics as JSON `read`. Raw retrieval includes lines the metric parser
does not recognize and does not require parsing the complete log.

Preserved failure logs describe execution history, not scientific evidence.
Neither parsed metrics nor raw-log retrieval certifies development
performance or chooses a candidate. The PI interprets the returned data.

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

Candidate archival also records versioned SHA-256 fingerprints for identifiable
serialized learned-state components. For the supported Stable-Baselines3 ZIP
format these components are the policy, optimizer, additional tensor state and
normalization file. The executable policy runtime is fingerprinted separately.
Unsupported formats and unavailable optional components remain explicit; they
do not prevent normal candidate archival.

The completed training result contains an optional
`saved_component_comparisons` object with these field types:

| Field | Type |
|---|---|
| `schema_version` | integer |
| `scope` | string |
| `current_context` | object |
| `current_context.parent` | string or null |
| `current_context.seed` | integer |
| `current_context.requested_steps` | integer |
| `comparisons` | array |
| `comparisons[].operation` | string |
| `comparisons[].context` | object |
| `comparisons[].current_checkpoint_count` | integer |
| `comparisons[].prior_checkpoint_count` | integer |
| `comparisons[].corresponding_checkpoint_count` | integer |
| `comparisons[].step_sets_equal` | boolean |
| `comparisons[].components` | object |
| `comparisons[].runtime` | object |
| `comparisons[].exact_component_matches` | array |

Component and runtime entries contain integer `compared` and `equal` counts.
Exact-match entries contain integer `training_steps` and string `candidate` and
`prior_candidate` identities. Comparisons use corresponding saved training-step
counts from earlier completed candidates in the same campaign. They report
exact serialized-component equality only. They do not declare semantic policy
equivalence, intervention activation, scientific independence, or candidate
adequacy. The complete-artifact integrity fingerprint remains unchanged.

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
After startup or inquiry closure, `next_question` states the proposed question
for the next goal review. Goal review may revise or decline that proposal
before opening an inquiry. The goal-review checkpoint repeats the exact
question of the inquiry opened in that session. If the same inquiry continues,
the checkpoint repeats its current active question.
`completed_operations` must exactly match the active session's completed
operation identities.
Opening, reframing or closing an inquiry does not end the active scientific session.
The checkpoint transition prompt supplies the session identity and exact operation list.
The Runner rejects a mismatched list without changing the session.
Its error reports the session identity, expected list and submitted list.
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
substantive `Established facts`, `Physical consequences`, `Unknowns`, and
`Decision-relevant synthesis` registers.
Each register is a level-two heading (`##`) with its content under it. Topics
inside a register use level-three headings (`###`).
An analyst persona, not the PI, writes the model. The model states physical
consequences and the evidence that discriminates between them. It selects no
intervention.
The synthesis is the final register. It selects the consequences and unknowns
most likely to change the first campaign decisions. For each selected item, it
keeps the decision relevance, the assumptions, the source references, and the
discriminating evidence. Startup receives this register as the handoff. The PI
also reads the whole model at startup and selects the initial direction.
After acceptance, the model remains fixed for the campaign.
Later checkpoints preserve or revise its consequential conclusions.
The Runner checks only that the file exists and that each required register
section is present and non-empty. It does not check scientific adequacy.
The PI alone is responsible for whether the model is scientifically sound.
