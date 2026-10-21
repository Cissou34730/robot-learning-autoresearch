# Scientific instruments

This document defines request formats, acceptance rules and outputs.
`contracts/program.md` defines the research lifecycle and the PI's decisions.
`contracts/authority.md` defines ownership and role permissions.

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

## Saved controller execution

Saved candidates include policy weights, normalization state when used, and the
executable runtime defined in `contracts/policy_runtime.py`.

Task-reference and official evaluations use protected environments, not the
PI-owned research environment. The protected environment calls the saved
`io.observe(data)` to construct each policy observation. The saved runtime
performs policy inference with its normalization state. The environment calls
`io.action(policy_action)`, then validates and clips the result before applying
it to the robot. It calls the optional `io.reset()` callback at each episode reset.

Controller logic affects protected evaluation only if the saved runtime executes
it. A runtime marker alone does not cause the protected environment to call
research-environment code. Research evaluation uses the PI-owned environment,
which can apply additional control logic outside the saved runtime. Identical
artifact fingerprints do not establish identical applied commands across these
environments.

## Scientific coding interface

`scientific_coding` delegates a bounded change to PI-owned source: a new
method, a measurement or analysis tool, or a repair. The coder and the
reviewer roles are defined in `contracts/authority.md`.

The PI session deadline is 30 minutes of active session time by default.
Coding and review count toward it. Waiting for Runner execution does not.

`scientific_coding` accepts:

- `intent`: the precise expected output of the bounded change;
- `allowed_paths`: exact repository-relative writable scientific files;
- `read_paths`: optional additional relevant scientific sources, contracts or
  the frozen `pi_workspace/scientific_model.md`;
- `source_context`: optional PI-selected requirements, caller context and errors;
- `session_handle`: optional returned native child identity for same-change
  corrections within this bounded context.

New calls require `intent` and `allowed_paths`. A correction supplies
`session_handle` and `intent`, with optional `source_context`. Omitted scope
fields reuse the stored binding; resubmitted scope fields must match it, and a
changed field is rejected with its name. A new scope requires a new call
without a handle. A handle is valid only within the current session.

Writes are limited to PI-owned files. Protected paths, directories, wildcard
scopes, operation requests and paths outside the repository are refused; the
rejection names the path and the reason. A new writable file does not require
an existing parent directory. Reads are limited to the selected files; the
frozen scientific model is read-only. A rejected read binding does not mean
that new-file creation is unavailable.

The coder and the reviewer receive the scenario and fixed excerpts of the
authority and instrument contracts. They do not receive the PI conversation:
state the relevant requirements in `intent` and `source_context`. The coder
reports missing or unclear requirements in its summary and unchecked scope.

### Review

After the coder's first handoff, an independent reviewer with high reasoning
receives the original request, the task context, the changed files and the
diff. The review checks coding defects and the equations, units, physical
assumptions, timing and measurement meaning of the changed code. It checks
whether the protocol and the reported quantities can answer the PI's stated
question. An untested scientific hypothesis is not a defect.

The reviewer returns exactly four fields:

```json
{
  "validation": {"type": "boolean"},
  "what_is_wrong": {"type": "string"},
  "why": {"type": "string"},
  "where": {"type": "string"}
}
```

The three explanation fields contain plain text, not nested finding records.
`validation` is false only for defects that the coder can repair within the
request; all three fields then explain the defect. A failed review goes
unchanged to the same coder, and the same reviewer checks the repair. A
correction review covers only the reported problems and errors introduced by
the repair. This repair loop does not return to the PI. A repair with no source
change followed by another failed review returns `needs_pi` with the reason and
the current changes. When `validation` is true, the explanation fields can
carry concerns, confounds or scientific choices for the PI.

### Coding result

The result contains:

- the session handle;
- the changed-file manifest and diff for the invocation, including repairs;
- the coder summary and unchecked scope;
- `review`: the four-field report, its `mode` (`initial` or `correction`),
  status, reviewer handle, models, reasoning and usage;
- `repair_history`: each forwarded review, the coder status and summary, and
  the follow-up review.

Large review output is stored in a file and returned as a path. Errors and
timeouts return partial changes when available. An unavailable or failed
review is reported as such, not as a completed review.

Review checks engineering and does not certify scientific validity. Inspect
the actual changes and the reported limitations before relying on them. The
coder executes nothing; measurements and analyses are separate operations.

## Source readers

`view` reads one exact permitted file. `glob` lists files by pattern. `rg`
searches content and returns matching lines, matching files or counts, with
pattern, glob, type, context and result-limit selectors. Both search tools
accept default, subdirectory or multiple `paths`. Searches skip reserved files
below a readable directory, and reject a reserved search root. Linked paths and
paths outside the repository are unavailable.

Results report output or traversal limits. A truncated result does not
establish that unreturned matches are absent. Use an exact-file read for
content beyond search-preview limits.

## Installed scientific API reference

`scientific_api_reference` reads definitions from the installed `mujoco`,
`gymnasium` and `stable_baselines3` libraries. It loads only those fixed library
roots. It does not call scientific functions or constructors, run supplied
code, inspect arbitrary paths or expose private attributes.

```json
{
  "library": {"type": "string"},
  "symbol": {"type": "string"},
  "action": {"type": "string"},
  "contains": {"type": "string"},
  "offset": {"type": "integer"},
  "limit": {"type": "integer"},
  "max_bytes": {"type": "integer"}
}
```

`library` selects one of the three installed libraries. `symbol` selects a
public dotted name relative to that library. An omitted symbol selects the
library root. Names imported from another library are not definition targets.

`action=members` returns public member names and their kinds. `contains`
filters names by a case-insensitive substring. `offset` and `limit` select
member rows. The result reports the matching count and `next_offset`.

`action=definition` returns the installed signature, documentation, available
Python source and native MuJoCo declaration. `offset` and `max_bytes` select
UTF-8 definition bytes. The result reports version, content fingerprint,
complete byte count and `next_offset`. Unavailable signatures and source are
explicit. A missing symbol returns `symbol_not_found`, not a guessed substitute.
Rejected lookups return a failed tool result with the library, symbol and reason.
Definition availability does not establish execution compatibility.

The PI, the coder and the reviewer can use this reader. It does not widen file
scopes or grant execution.

## JSON evidence interface

`artifact_evidence_query` reads JSON evidence. It resolves a
recorded artifact from a completed measurement operation in the active
campaign and verifies its recorded fingerprint. The PI supplies operation
identity, not an arbitrary filesystem path.

The interface supports:

- `discover`: inspect the structure under an optional prefix;
- `query`: select one path, with optional filtering, projection or aggregation;
- `batch`: apply related query specifications to the same verified artifact;
- `read`: retrieve the artifact's complete content through successive pages.
- `operations`: query compact operation metadata without opening artifacts;
- `metadata`: query one operation's record, artifact references, checkpoints,
  or accepted pending request.

`operations` does not take `operation_id`. Its default path selects operation
rows. `metadata` requires `operation_id`. Its paths are `/operation`, `/record`,
`/artifacts`, `/checkpoints`, and `/pending`. Its default path selects the operation summary.
The operation index includes an accepted pending operation.
Its status is `pending` or `failed_pending`, not completed evidence.
For that operation, `/pending/request` returns the exact wrapped accepted request.
`/pending/measurements` returns resolved invocations and declared outputs.
`/pending` also includes progress, failure, request fingerprint and completed-measurement count.
These fields remain available after an execution failure or context replacement.
They do not authorize artifact-content access to incomplete measurements.
Both actions support the query filters, selection, aggregates and pages.
They report `artifact_contents_inspected` as false. Recorded metadata is not
an inspection of measurement contents.

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

The tool validates the complete JSON syntax of an artifact before it selects
evidence. Query output and decoded values have explicit limits; an exhausted
limit is reported, not silently truncated.

Filtering uses a typed object with required `path` and `equals` fields.
`path` is relative to each selected row; `equals` can be null.
An array selected for filtering, projection or aggregation is expanded into
rows, with the expansion reported in the response. An explicit wildcard also
selects rows. A missing filter field is reported as `filter_field_absent`, not
as a valid zero-match result. Missing selected fields include bounded direct-field
hints. These hints are not a complete inventory.

Ordinary query pages default to small row and byte limits. `limit` selects the
row page size. Set `max_bytes` on the request, not inside `queries`.
All batch items share that byte limit for selected values.
Unsupported fields are rejected, not silently ignored.
Omit `select` for complete rows. A supplied pointer cannot be empty.
Artifact-content requests show the operation and artifact index in the console.
Explicit larger pages and complete original reads remain available.

For `read`, `offset` and `max_bytes` refer to original file bytes.
`encoding` selects readable UTF-8 or base64 for other byte encodings.
UTF-8 pages preserve line endings and do not split a character. The returned
`next_offset` and verified fingerprint identify continuation;
`expected_fingerprint` is required for a nonzero read offset. Joining pages
in offset order reconstructs the complete original content. Full retrieval
does not require parsing the entire artifact within the query limits.

## Training-log interface

`training_log_query` reads preserved training logs. It resolves them from the
active campaign and the training operation identity, not from a filesystem
path or command.

`discover` returns attempt identities, timestep coverage and available metric
names without metric record values. Omitting `action` selects this metadata mode.
`records` requests select attempts, timestep bounds and metric fields.
`raw` requests return preserved log text, including content outside parsed
training records. Complete logs and successive pages are supported. The PI
may request different subsets in separate calls without rerunning training.
The tool reports missing logs, empty selections, available continuation and
content identities explicitly.

`attempts` selects preserved attempt numbers. `records` uses optional
`from_step` and `to_step`, with `offset` and `limit` for selected
row pages. Nonzero row offsets require `expected_log_fingerprints` from the
previous response. Missing metrics are identified separately from zero.
The operation's status does not establish each attempt's outcome.
Record requests require either explicit `metrics` or `all_metrics: true`, not
both. Default row and byte pages are small. `max_bytes` bounds selected record
values as well as raw pages; the PI can explicitly increase it and continue.
Console output identifies operation, action and supplied selectors.

`raw` selects one attempt when multiple logs exist. Its `offset`, `max_bytes`,
`encoding` and `expected_fingerprint` use the same original-byte continuation
semantics as JSON `read`. Raw retrieval includes lines the metric parser
does not recognize and does not require parsing the complete log.

Preserved failure logs describe execution history, not scientific evidence.
Neither parsed metrics nor raw-log retrieval certifies development
performance or chooses a candidate. The PI interprets the returned data.

## Numeric summary tools

`training_series_statistics` computes a summary of one metric in one
preserved training log. It uses the same operation identity, attempt selection
and log fingerprint as `training_log_query`. The PI supplies:

- `operation_id` and the exact `metric` name;
- `attempt`, required when the operation has more than one log;
- optional inclusive `from_step` and `to_step` bounds;
- optional `checks`, at most 20.

The result gives the row count, the first and last values with their steps,
the minimum and maximum with their first step and the number of rows at that
value, the mean and the sample standard deviation. Rows without a finite value
are excluded and counted. A missing metric returns the available metric names.

Each check names a statistic (`min`, `max`, `mean`, `first` or `last`), a
comparison (`>=` or `<=`) and a threshold that the PI chooses. The result gives
the computed value and whether the comparison holds. A `min` or `max` check
also gives the number of rows that do not meet the comparison and the first and
last of their steps. Checks are optional.

`wilson_proportion_interval` returns the 95% Wilson score interval for
`successes` out of `trials`. The PI supplies both counts; the tool reads no
campaign files and does not verify the counts. The interval assumes
independent trials with one common success probability.

These tools compute numbers from the supplied data. They do not judge claims,
decide significance, certify development performance or choose a candidate.
The PI interprets the results.

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
Its episodes are deterministic: measuring the same saved artifact again
reproduces the recorded result and supplies no additional sample.
Its controller execution follows the saved-runtime contract under
[Saved controller execution](#saved-controller-execution), not the PI-owned
research environment.

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
  "label": {"type": "string"},
  "inputs": {
    "type": "object",
    "additionalProperties": {
      "type": "object",
      "properties": {
        "operation_id": {"type": "string"},
        "artifact_index": {"type": "integer"}
      },
      "required": ["operation_id", "artifact_index"],
      "additionalProperties": false
    }
  }
}
```

Set `instrument` to `python_module`.
The `module`, `args`, and `artifact` fields are required.
The `label` and `inputs` fields are optional.
Each `args` element is one literal module argument, not a full launch command.
Do not include the module name or launcher in `args`.
Pass a concrete output path in the arguments when the module requires it.
`artifact` declares the expected output. It does not substitute an argument.
Unresolved `{artifact}` tokens are rejected before acceptance.
The module must be under `robot_learning.lab`, `robot_learning.scenario`, or
`robot_learning.training`.
The artifact must be a campaign JSON path under
`campaigns/evaluations/<current-campaign-id>/`.
`campaigns/brief.md` gives the exact evaluation root for the current campaign.

`inputs` binds PI-selected names to recorded JSON artifacts from completed
measurements in the current campaign. Names must be identifiers.
Each argument placeholder `{input:NAME}` uses a declared name.
Every declared input must appear in the arguments.
The output artifact cannot overwrite a named input.
The Runner resolves the selected operation and artifact index, verifies the
recorded fingerprint, and replaces the placeholder with its canonical path.
Acceptance freezes the resolved identities. Execution checks them again before
the module runs. Results retain the input identities in their compact metadata.
Missing, changed, or unavailable inputs are errors. The Runner never chooses
another artifact, changes the module, or decides how the PI repairs the request.
Arguments without input placeholders remain unchanged.
Execution errors identify the accepted module arguments and declared output.
A successful module exit without that output is an operation failure.
Runner reports these facts without diagnosing the source or selecting a repair.

A paired-comparison entry uses this interface:

```json
{
  "candidate": {"type": "string"},
  "reference": {"type": "string"}
}
```

Both fields are required and must be non-empty.
Both candidates must appear in planned `research_evaluation` measurements that
use the same episode seeds.

The result keeps the accepted candidate artifacts, evaluator semantics, module
sources, PI-owned scientific changes, and effective parameters.
It also keeps reused-panel identities and paired-comparison integrity facts.

Under the same evaluation semantics or task-reference panel, an episode seed
identifies a deterministic episode for a saved artifact. When a
`research_evaluation` or `task_reference` measurement shares episodes with an
earlier completed measurement of the same saved artifact and instrument, its
result lists `repeats_earlier_measurements` with the earlier operation ID,
label and number of shared episodes. Shared episodes reproduce recorded
outcomes; they are not independent confirmation.

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
The full artifact remains unchanged at its recorded path in the local archive
`campaigns/evaluations/<current-campaign-id>/`.

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

The session context states the training allocation. During startup, `steps`
can be any positive value up to the allocation. During an inquiry, `steps` must
equal the allocation. The PI cannot change the allocation. Runner rejects
other values during validation, acceptance and training dispatch.

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
    "reason": {"type": "string"},
    "paths": {"type": "array", "items": {"type": "string"}}
  }
}
```

All fields are required. Candidate and reason must be non-empty. `paths` is a
non-empty list of distinct exact repository-relative scientific files, including
`robot_learning/training/current_params.json` for the recorded parameters.
The operation restores only those files from the candidate's recorded recipe.
It removes a selected file when absent from that recipe.
Unselected source files remain unchanged; campaign laboratory tools cannot
be selected. Directory and wildcard scopes are refused.
The Runner does not infer which code implements learning versus measurement.
When one source file contains both, restoring the whole file also restores both.
There is no automatic whole-recipe rollback.
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
The preliminary analyst writes the model. The model states physical
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
section is present and non-empty. It does not check scientific adequacy; the
PI judges the model's soundness when using it.
