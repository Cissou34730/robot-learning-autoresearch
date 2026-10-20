# Scientific instruments

This document defines exact request formats, acceptance rules, and outputs.
It does not tell the PI when or whether to use an instrument.
`contracts/program.md` assigns scientific decisions to the PI.
`AGENTS.md` defines ownership and command authority.

## Paths and persistence

Paths in requests and records are logical repository-relative paths, not
instructions to combine every path with the current working directory.
`robot_learning/`, `campaigns/`, `pi_workspace/`, `runner/state/`, `models/`,
reports and session data live in the local campaign repository. Contracts,
Runner implementation and protected evaluators live in the harness repository.
The existing read/search policy maps permitted contract reads to the harness;
this does not grant write access or access to reserved implementation files.

Scientific code and durable operation records are committed in campaign Git.
In the split layout, Runner never pushes those commits, even if a remote is
added. Raw measurements and training logs remain local and ignored. Harness
publication to GitHub is separate maintainer work. These storage choices do not
change operation payloads, PI authority or evidence semantics.

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

The SDK schema exposes the exclusive wrappers and their complete body structures.
Shared structural validation checks the request before dispatch.
Runner uses the same structural validation, then validates
the operation body against the active state. A flat operation record with
`kind` and body fields is not a submission envelope. Errors identify
missing wrappers, extra top-level fields, or a non-object body.

Measurement identities use `M#`. Training identities use `T#`.
Other event identities use `E#`.
Evidence references must identify completed operations.

`submit_operation` returns a compact factual result or the exact rejection/error,
operation identity when completed, and changed state: session identity and kind,
actual completed-operation list, roles, pending/terminal status,
currently permitted operation kinds, and required checkpoint transition.
Request and evidence checks still apply to these kinds.
Full artifact inventories and logs are not
attached to each completion. Detailed artifacts stay available through
`artifact_evidence_query`; preserved training logs through `training_log_query`.
Ordinary results continue in this same conversation,
without a new runtime or replayed phase prompt. Inquiry open/reframe/close makes
checkpoint the sole next operation. A completed checkpoint or terminal commitment
ends this context; the launcher creates the next bounded context when permitted.
The SDK process/client remains alive across those contexts.

Correct a rejected request in this conversation. Two rejected submissions stop
the bounded session, preserving the existing one-retry limit.
`implementation_error` means an accepted operation failed. It does not diagnose
a source defect. Inspect the actual error and accepted invocation before
deciding whether to correct the request or repair source.
Use `artifact_evidence_query` with `action=metadata`, the pending `operation_id`,
and `path=/pending` to retrieve its exact request and resolved measurements.
Changed arguments require a replacement envelope.
Use `scientific_coding` only when source repair is needed.
`{"request": null}` reaccepts the same request after source repair.
It cannot correct request arguments.
An execution failure is history, not scientific evidence. `validation_fatal`,
`controller_fatal`, publication failures, interruption, terminality and
recovery-required results prohibit further submission and evidence queries
in that context. The controller recovers existing accepted/completed
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

### Saved controller execution

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

Ordinary Copilot main PI sessions expose `scientific_coding` and
`submit_operation` alongside source readers, `artifact_evidence_query` and
`training_log_query`. They have no `apply_patch`, other file-write tools or
shell tools. `scientific_api_reference` reads installed library definitions
for PI and authorized coding/review children. The preliminary scientific-model
session retains its existing publication interface and does not expose coding.

The default Copilot PI deadline is 30 minutes of active session time.
Coding and review count toward that deadline. Runner execution waits are excluded.

`scientific_coding` accepts:

- `intent`: the precise expected output of the bounded change;
- `allowed_paths`: exact repository-relative writable scientific files;
- `read_paths`: optional additional relevant scientific sources, contracts,
  `AGENTS.md` or the frozen `pi_workspace/scientific_model.md`;
- `source_context`: optional PI-selected requirements, caller context and errors;
- `session_handle`: optional returned native child identity for same-change
  corrections within this bounded context.

New calls require `intent` and `allowed_paths`.
Corrections may supply only `intent` and `session_handle`, with optional
`source_context`. Omit scope fields to reuse the stored binding. Explicitly
resubmitted fields must resolve to the same binding; changed fields reject
with their names. A new scope requires a new PI-directed call without a handle.

Protected writes, directories, wildcard scopes, operation requests and arbitrary
filesystem paths are refused. New writable files are permitted even when their
parent directory does not exist. The frozen scientific model remains read-only,
and only explicitly selected files enter the coding read binding.
Coder and reviewer also receive fixed environment, scenario and operation-contract
text. This text does not expand file permissions or include the campaign conversation.
Rejections
identify the offending path and reason; a rejected read binding does not imply
new-file creation is unavailable. A continued child must keep the same writable,
readable scope. The SDK dispatches the registered native
coding subagent with the supplied objective and source context, rather than
creating a separate SDK session or passing the PI's campaign conversation.
Corrections are sent to that same native child.
Native handles are context-local, not resumable authority across a runtime
restart or a fresh scientific context. The handler resolves and validates the
SDK's model/tool configuration before dispatch; unavailable capabilities are
reported rather than falling back to manual coding sessions.

The default/main agent excludes file-write tools. The registered coder has
scoped `view`, `apply_patch` and `scientific_api_reference`. It cannot execute
code, delegate further or submit campaign operations. Hooks and permission
callbacks bind its calls to the authorized native child and file scope.
Main PI writes remain denied.
Permission callbacks use the native permission event's identity and current
file binding, not the arrival of a tool-start event. Unknown or stale identities
fail closed with a harness authorization error.
Native start instructions include the installed scientific API versions and
dependency restrictions.
Completion handling challenges an incomplete engineering handoff, not
scientific adequacy or research direction.
The stop hook applies to corrections as well as the initial invocation.
The handler waits for the stop handoff and native task idle state before
unlocking operation submission.

After the first completed handoff for an assignment, the handler starts an
independent native `scientific-reviewer` with high reasoning.
It receives the original request, supplied task context, actual changed files and diff.
The review prioritizes coding defects and checks equations, units, physical
assumptions, timing and measurement meaning in changed code.
It checks whether the protocol and reported quantities can answer the PI's
stated question and flags concrete confounds or missing conditions for the PI.
An untested scientific hypothesis is not itself a defect.
Corrections reuse that native reviewer. They provide the correction
intent and context, incremental changes and previous completed
review, without repeating the original request. The result identifies the review
`mode` as `initial` or `correction` and its `coding_session_handle`.
Correction reviews cover only the reported problems and errors introduced by the repair.

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
When `validation` is false, all three must explain the failed review.
The native coding handler sends that four-field report unchanged to the same coder.
It then sends the incremental repair and one previous review to the same reviewer.
Unchanged contracts and duplicate repair instructions are not resent for automatic corrections.
The handler does not return to the main PI between these engineering steps.
When `validation` is true, the handler returns the completed package.
A repair with no source changes and another failed review returns `needs_pi`.
The result includes an explicit reason and current source changes.
The whole PI session deadline still includes all coding and review.

A missing or non-idle stored reviewer rejects correction dispatch.
The handler does not create a replacement reviewer for that assignment.
Its exact read scope matches the coding binding.
Its tools are `view` and `scientific_api_reference`; writes, execution,
delegation and operation submission are denied.
The handler keeps operation submission locked until the coding handoff settles.
It verifies the reported reviewer model and reasoning, and reports unavailable or failed
review explicitly rather than treating it as a completed review.

The result returns the child handle, actual per-invocation changed-file manifest
and diff, coder summary and unchecked scope.
The manifest and diff include all repairs within that invocation.
`repair_history` records each forwarded review, coder status and follow-up review status.
Completed repairs also record the coder's summary and the next four-field review.
The handoff requires no verification module, argument template or execution proposal.
It performs no argument substitution and executes no code.
Measurement or analysis code is authored only when the PI explicitly requests it.
Large review output is offloaded with a file pointer. Errors and
timeouts return partial changes when available; cancellation preserves review output.
The `review` entry contains the four-field report and harness metadata:
status, reviewer handle, actual models/reasoning and per-invocation usage.
File permissions remain enforced by the existing binding, not by parsing `where`.
Scientific decisions remain with the PI. Review does not choose scientific
strategy or approve campaign conclusions.
The main PI reviews actual changed source and reported limitations before scientific reliance.
Scientific measurements remain separate PI-authorized operations executed by Runner.
No coding result certifies scientific validity. Native task lifecycle is
owned by Copilot SDK 1.0.19; operation acceptance and scientific execution
remain owned by the existing trusted controller and Runner.
Usage and changes are reported per invocation. SDK native-task lifetime totals
are labeled separately and must not be added again on each correction.
Reviewer usage has the separate `scientific_reviewer` role, configured model
and reasoning, and reported actual models. PI time excludes both delegated
coding and review time.

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
exact-file `view` and `apply_patch` binding described above, not repository search
tools. Their installed-library access uses the separate API reader below.

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

The active PI or its authorized native coding/review child can use this reader.
Coding and Runner locks still apply. It does not widen repository file scopes
or give either actor execution permissions.

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
Both actions support the existing query filters, selection, aggregates, and pages.
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

Large JSON artifacts use a temporary, fingerprint-verified file-backed view.
The tool validates the complete JSON syntax before it selects evidence.

Each request verifies the source fingerprint. The reader process keeps bounded
byte-span metadata for validated content. Successful validation uses the
fingerprint and runtime validation limits as its key. Container end offsets
use the fingerprint and start offset as their key. Concurrent requests share
validation and container scans. Neither cache retains snapshots or decoded trees.

It does not load the complete JSON tree. Query and output limits remain.
Decoded individual scalars and field indexes have explicit memory limits.
An exhausted limit is reported, not silently truncated input.
The temporary snapshot is removed after the request. Original-byte paging
continues to use the recorded source bytes, not the normalized snapshot.

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

`training_log_query` exposes the existing training-record parser as a
read-only custom tool. It resolves preserved logs using the active campaign
and training operation identity, not a filesystem path or command.

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
Raw measurement files remain in the fixed local archive
`campaigns/evaluations/<current-campaign-id>/`, which Git ignores.
Runner publishes compact operation facts, artifact paths and fingerprints,
not raw artifact contents. The evidence reader still verifies and reads those
local files. A Git checkout alone does not contain the full measurement data.
Publication failures retain Git's specific error and stop without re-execution.

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
When one source file contains both, restoring the whole file also restores both;
the PI uses scoped scientific coding to carry forward the intended measurement
capability before relying on it. There is no automatic whole-recipe rollback.
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
