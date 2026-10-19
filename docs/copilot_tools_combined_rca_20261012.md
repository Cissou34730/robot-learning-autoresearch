# Copilot tools: combined RCA and maintainer decisions

Date: 2026-10-12.

Maintainer-only analysis of campaign
`fedcc0f3-5435-4aa3-b839-d2c108082481`. This document reconciles the
operation-format RCA with the broader workflow, input-path and evidence-access
RCA. It records corrections to their claims, approved implementation scope,
and the rejected proposal.

## Authority and scope

Keep the custom tools. Repair their contracts and evidence access.

Runner enforces mechanical contracts, executes PI-authorized operations, and
returns factual results. Runner must not initiate or coordinate PI coding,
diagnosis, debugging, repair decisions, or scientific interpretation. This
boundary is immutable. Efficiency goals do not weaken it.

The PI retains scientific intent, coding delegation, diagnosis, review, repair
decisions, and acceptance of scientific changes. Coding children remain scoped
authors without execution authority.

Maintenance is harness-only. It does not repair, restore or remove PI-authored
code, including the historical fallback implementations discussed below.
No campaign launch, reset, resume, training, measurement, evaluation, operation
replacement, or campaign-state repair is authorized by this implementation.

## Evidence and limits

Sources:

- repository snapshot `059d23b7d8ca22a501dea16744139d54a3f64521`;
- `reports\session_usage\fedcc0f3-5435-4aa3-b839-d2c108082481.jsonl`;
- `runner\state\research_state.json` and completed-operation metadata;
- the 24 recorded parent SDK journals under
  `%USERPROFILE%\.copilot\session-state\<session-id>\events.jsonl`;
- current harness and instrument contracts;
- selected historical source for M54 and its PI-owned repair.

The source inspection and inert reproductions did not execute campaign
operations or inspect the human-owned test suite.

| Recorded activity | Campaign value |
|---|---:|
| PI usage | 187.046177 AIU |
| Scientific-coder usage | 70.917101 AIU |
| Total usage | 257.963278 AIU |
| Cumulative input tokens, including cached input | 45,735,479 |
| Output tokens | 559,746 |
| Cached share of input tokens | 90.54% |
| Completed coding invocations | 33 |
| Completed measurement operations | 46 |
| Failed measurement operations | 16 |
| Parent contexts | 24 |
| Parent context compactions | 9 |

The PI accounts for 72.5% of recorded AIU. This proportion does not establish
how much work delegation displaced. It does not prove a before/after cost or
reliability regression. Campaign duration, scientific work and failure chains
were not controlled.

## Confirmed findings

### 1. Operation structure depends on remembered documentation

Tracker: OI-029.

`OperationSubmissionParams.request` exposes an unrestricted dictionary or null.
The SDK accepts objects that Runner's envelope validator rejects.
The seven operation wrappers exist in the instrument contract and Runner
validation, but not in the model-facing structural schema.

S23 journal `6924510b-6255-4336-8a79-68f593b2a6e8` establishes this sequence:

| Local time | Observation |
|---|---|
| Before 20:02:49 | Five submissions use valid operation wrappers. |
| 20:02:49-20:03:25 | Context compaction reduces approximately 175,000 tokens to 51,000. |
| 20:03:34 | The PI rereads instrument lines 1-240. |
| 20:03:41 | The PI submits flat `kind`, `description`, `measurements` and `rationale` fields. |
| 20:03:49 | The retry removes `kind` but still omits the `measurement` wrapper. |
| 20:03:51 | The second rejection closes the context with `validation_fatal`. |

The measurement envelope starts at instrument line 348. The compaction
summary references the contract but does not preserve the envelope structure.
Compaction is a strong contributor, not a proven exclusive cause.

The generic rejection lists operation names without identifying the missing
wrapper. Accepted history also uses a flat record format, unlike the submission
envelope. Those representations must not be interchangeable.

Repair the SDK structural schema using the same operation-key authority as
Runner. Return specific wrapper and field errors. Keep stateful and scientific
request validation with Runner. Do not silently normalize invalid proposals,
invent scientific content, or increase the rejection allowance.

The tool's documented stop conditions must include `validation_fatal` and
`controller_fatal`. Post-fatal evidence denials are consequences of closure,
not independent query-engine failures.

### 2. Coding corrections reconstruct an already stored binding

Tracker: OI-030.

Four known-handle corrections were rejected after the submitted read list
changed. The harness stores the immutable binding but requires callers to
resupply it exactly.

During M54 repair, the first correction supplied the intended repair but
shortened the read scope. The next call restored scope and accidentally
restored the original implementation intent. The child returned without
making the required repair. The PI detected this and requested a fresh child.

Allow a correction to supply its current-context handle and intent alone.
Reuse and revalidate the stored binding. Explicitly changed scope fields
must still reject with field-specific errors. Unknown, stale, foreign-context,
non-idle and unauthorized handles remain rejected. A new scope requires a
new PI-directed coding call, not an implicit scope expansion.

### 3. One malformed input caused ten failed measurements

Tracker: OI-031.

M31-M40 repeat a missing-file failure. The first submitted T2 filename
omits the campaign UUID component `4aa3`. The recorded M30 artifact includes
that component. The malformed string therefore precedes Runner transport.

The earliest malformed submission is in journal
`ff746525-1e0d-4779-8cd9-0ff23e3c90e2`, line 597, at 18:31:21 local.
Subsequent coding intents attribute the failure to archive visibility,
mounting, separators and transport. They add fallback paths, embedded
snapshots and an alias for the malformed name.

These are not ten independent coding failures. One unsupported diagnosis
propagated through repeated authoring and execution. Automating that loop
would not correct its premise.

The approved direction is authoritative operation/artifact references and
compact operation/checkpoint lookup. Resolve the selected identity without
requiring the PI to transcribe long filenames. Keep input-resolution errors
distinct from errors inside executed code. Do not classify every
`FileNotFoundError` as an input mistake or choose substitute evidence.

No repair of the existing PI-owned fallbacks is authorized.

### 4. Selective JSON access fails above the whole-artifact ceiling

Tracker: OI-032; query ergonomics remain related to OI-018.

Artifact fingerprint calculation already streams the input. JSON selection
still requires a full parsed document within a 32 MiB ceiling. It rejects a
small-field query when the original artifact exceeds that ceiling.

Fifteen requests hit this limit. Recorded failing artifact sizes include
38,704,733, 38,704,885, 38,704,889, 46,322,796 and 77,838,375 bytes.
Original-byte paging remains available, but is not selective JSON analysis.

Provide bounded selective access for actual campaign-sized artifacts while
preserving fingerprint checks, explicit continuation and output budgets.
Streaming selection or a fingerprint-bound index requires a separately
specified implementation batch. Do not silently truncate the input, disable
integrity checks, or require the PI to retrieve the entire artifact first.

The existing query API supports complete objects and wildcard selection.
Twenty desired fields do not inherently require twenty query specifications.
Column projections are a possible extension, not an established prerequisite.

### 5. Context cost spans the complete workflow

Tracker: OI-008 and OI-026; metadata access is tracked by OI-031.

| Parent tool | Recorded output characters |
|---|---:|
| `view` | 5,184,012 |
| `rg` | 1,594,121 |
| `glob` | 434,747 |
| JSON evidence | 2,489,979 |
| Coding handoffs | 542,410 |

Parent reads include the instruments document 38 times, brief 29 times and
scientific model 25 times. These are characters and read counts, not token or
cost attribution. Many initial reads are expected across 24 fresh contexts.

Large history searches and repeated full reads within one context are useful
targets. Removing necessary scientific context is not an approved remedy.
The current coding result already includes a manifest, diff and check
proposals. Improve that interface rather than adding a duplicate review layer.

## Corrections to earlier RCA claims

| Earlier claim | Reconciled result |
|---|---|
| Six JSON argument-validation failures | Four schema failures and two expected closed-context denials. |
| Eighty-one JSON discovery calls | Ninety-one attempts, of which eighty-one returned `discovered`. |
| PI's cost share proves workload was not displaced | Not established without equivalent-work comparison. |
| Reader must use twenty selectors for twenty related fields | Complete-object selection already exists. |
| Coding result lacks a review package | Manifest, diff and proposals already exist; checks remain unexecuted. |
| All query failures arise from invalid arguments | Fifteen requests also hit the whole-artifact size ceiling. |
| Most failed measurements are independent coder mistakes | Ten share the malformed M31 input chain. |

Training-log queries comprise 20 discoveries and 15 record queries, with no
recorded failures. JSON query limits of 98,304 selected bytes and 16 batch
items remain correctly declared and enforced.

M54 omitted a required `success_threshold` argument in a PI-authored check.
The child read the correct source and the PI reviewed it. Parent and child
both used `gpt-5.6-luna` with high reasoning effort. Installed package versions
match the locked stack. Compatibility execution detected the authoring error
before training. M55 and M56 completed after PI-directed repair.

Handoff-format validation cannot certify arbitrary Python calls or scientific
correctness. Do not add generic mathematical validators, another reviewing
agent, or maintainer repairs to PI code as a substitute.

OI-027/OI-028 repaired outcome reporting and publication classification.
They were not repairs to request generation, artifact access or coding
coordination. Their implementation checks do not establish campaign effects.

## Rejected proposal: Runner-controlled engineering loop

The broader RCA proposed this loop: the PI approves intent and verification
scope, then a trusted Runner-controlled system coordinates code authoring,
checks and repairs before returning final source and execution evidence.
It proposed fingerprint-bound evidence and no unrestricted coder shell.

The maintainer explicitly rejected this proposal on 2026-10-12:

> Runner must not interfere with PI jobs, this is immutable and stonger rule
> of the repo.

> so if I understood correctly the loop I will not approve it.

Disposition: **withdrawn and excluded from implementation**.

The proposal transfers PI debugging and repair coordination to Runner.
Limits, fingerprints and a restricted shell do not correct that authority
violation. It must not return under a different name or as a later
cost-optimization stage. Runner remains a mechanical executor, not a
coordinator of PI work.

## Approved implementation sequence

The maintainer authorized documentation and implementation after rejecting
the Runner-controlled loop.

| Batch | Scope | Acceptance boundary |
|---|---|---|
| 1 | Operation envelopes, structural errors, fatal-condition guidance and handle-only coding corrections | SDK and Runner share envelope structure; valid scientific bodies remain unchanged; stored correction scope cannot expand; existing retry and lifecycle guards remain. |
| 2 | Authoritative artifact references and compact operation/checkpoint lookup | PI selects evidence; routine identity lookup avoids long filename transcription and raw-history searches; Runner never chooses substitute evidence. |
| 3 | Large-artifact selective access | Small selections work on campaign-sized inputs with integrity and bounded output; existing original-byte retrieval remains. |
| Observation | Equivalent-work comparison | Compare model, reasoning, source and task settings before claiming cost or reliability gains. No campaign execution or new benchmark framework is authorized here. |

Batch 1 starts with this document. Later batches require their concrete
interface and storage choices to be recorded before implementation.
Do not bundle new agents, scientific gates, auto-repair loops, dependency
changes, generic column-projection APIs or PI-source changes.

Use proportional inert reproductions and touched-file checks. Preserve campaign
state, scientific sources, raw measurements, models and operation history.
Implementation evidence belongs in the tracker and below. It is not proof of
scientific effectiveness or authority to restart the campaign.

## Implementation record

Batch 1: **implemented / campaign effect unmeasured**.

- `runner\protocol.py` supplies the seven exclusive wrapper variants and a
  shared, state-independent envelope validator.
- `submit_operation` exposes those variants in its actual SDK schema and
  validates structure before dispatch. Invalid flat requests do not reach
  Runner or consume Runner's rejection allowance. Operation bodies are not
  rewritten. Full body and stateful validation remain with Runner.
- Structural errors identify a missing wrapper, extra top-level fields,
  multiple wrappers or a non-object body. Stop guidance includes both
  `validation_fatal` and `controller_fatal`.
- `scientific_coding` accepts handle-only corrections with an intent.
  It revalidates the retained binding. Explicit changes identify their
  fields and reject. Initial calls still require writable files and a scoped
  verification module. Native idle, parent identity, context-local authority
  and concurrency checks remain.
- `AGENTS.md` records immutable Runner noninterference.
  `contracts\instruments.md` describes the updated parameter mechanics.

Validation passed 112 inert assertions through the installed SDK's actual
tool handlers. Fake channels and native-task endpoints exercised parameter
rejection, unchanged payload transport, null reacceptance transport, idempotence,
fatal stops, scope preservation, changed-field rejection, foreign and stale
handles, non-idle children and initial dispatch. No native model or Runner
operation was invoked. Mocked authoring wrote no scientific files.

Both changed harness modules compile. Touched-file lint introduces no findings
relative to HEAD; the adapter's seven existing findings remain.
Campaign state, results, generated history, brief and request-file presence
remain unchanged. No human tests were inspected or executed.

The SDK factory preserves the wrapper schema. No live provider invocation or
new campaign observation establishes model adherence after compaction.
OI-031/OI-032 are mandatory remaining implementation batches, not deferred
proposals. The maintainer required completion of both before another campaign.
The discarded engineering loop remains excluded, regardless of cost observations.

Batch 2: **implemented / campaign effect unmeasured**.

The existing evidence tool adds `operations` and `metadata`. Both use the
existing query engine and limits. Metadata exposes the selected operation,
its full record, indexed artifact identities, and origin-bound checkpoints.
It explicitly reports that artifact contents were not inspected.
The generated brief points to these interfaces instead of routine raw-history
searches. The existing campaign brief is not regenerated during maintenance.

`python_module` gains optional named `inputs`. Each reference contains only
the chosen operation ID and artifact index. `{input:NAME}` arguments use these
names. Acceptance resolves and fingerprints the exact selections. Execution
checks the frozen inputs before launching the module. Compact result metadata
retains these identities. Recovery reuses already sealed outputs without
executing them again. Literal arguments keep their existing behavior.

Request, pending-state, execution and recovery validation share the new
mechanics. Unavailable, changed, undeclared, unused or malformed references
reject explicitly. No filename fallback, substitute evidence, automatic
diagnosis, or PI-source correction is added.
The output cannot overwrite a declared input.

Batch 3: **implemented / campaign effect unmeasured**.

The in-memory ceiling is now a parse-mode threshold, not an artifact-size
rejection. Larger sources use one temporary UTF-8 snapshot and a read-only
memory map. The original-byte fingerprint binds the snapshot to the recorded
artifact. Full syntax validation includes unselected content and invalid
suffixes. Temporary resources close on success and failure.

The private `runner\json_artifact_view.py` helper supplies lazy objects, arrays
and scalars. The existing query engine keeps its JSON Pointer, filter,
selection, aggregate, pagination, batch and output-budget behavior.
Only selected output is materialized. Large complete selections report the
existing byte-budget continuation. Explicit scalar and field-index limits
bound decoding. Original-byte reads remain unchanged. No persistent index,
package installation, alternate scientific query engine or generic projection
API is added.

Controlled validation passed 482 assertions. It covers complete JSON syntax,
duplicate keys, escaped pointers, UTF encodings, scalar types, query parity,
filters, aggregates, pagination, byte budgets, snapshot cleanup, fingerprint
failures and named inputs. Exact shallow and deep selections also matched
ordinary JSON decoding on recorded 38,704,733-, 46,322,796- and
77,838,375-byte artifacts. These were read-only checks, not campaign operations.

Large-file parsing uses the adapter's existing worker-thread pattern.
Reader authorization still occurs before dispatch. Parsing does not block
the SDK event loop or add permission to query from a coding child.
The installed SDK's actual handler passed inert checks for result transport,
event-loop responsiveness, foreign-session rejection and child rejection.
Additional targeted checks cover stored input bindings, wide-object budgets,
unused metadata selectors and output/input collision rejection.

All approved interface and evidence-access batches are implemented.
Equivalent-work cost and campaign-effect comparisons remain observations,
not authority to execute a campaign. The rejected engineering loop remains
excluded. No claim of universal model adherence or scientific correctness
follows from these implementation checks.
