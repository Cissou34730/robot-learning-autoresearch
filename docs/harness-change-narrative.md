# Harness change narrative

This document is the curated explanation of how the research harness evolved:
what failed, what was tried, what campaign evidence changed the diagnosis, what
was reverted or superseded, and why the current design and backlog have their
present form.

It complements, but does not duplicate:

- [`harness-experiment-log.md`](harness-experiment-log.md), the compact live
  tracker and current source of issue status;
- [`archive/harness-experiment-log-legacy.md`](archive/harness-experiment-log-legacy.md),
  the complete chronological record retained as source material and audit
  history;
- dedicated RCAs and campaign reports, which hold detailed evidence.

## Documentation decision

The former experiment log grew to 3,257 lines because it simultaneously acted
as a status register, chronological diary, RCA store, implementation ledger,
campaign report and backlog. It preserved information but did not make the
current state, unresolved findings or decision history reliably discoverable.

The adopted structure has three layers:

1. **Live tracker:** concise current truth, stable OI identifiers, status,
   evidence boundary and next action.
2. **Curated narrative:** thematic history of failures, attempted repairs,
   campaign observations, reversals and current conclusions.
3. **Chronological archive:** the untouched detailed sequence used to verify
   provenance and recover details omitted by curation.

No layer replaces campaign artifacts as scientific evidence. Documentation
describes decisions and observations; it does not upgrade correlation into
causation or implementation checks into scientific validation.

## What the narrative must preserve

The narrative must not describe only the successful path. For each meaningful
change stream, it preserves:

- the observed failure and the evidence that established it;
- the initial diagnosis, including uncertainty;
- each materially different attempted repair;
- campaign observations after the repair;
- whether the observation tested the repair or merely occurred after it;
- failures caused by implementation or runtime incompatibility, distinguished
  from failures of a scientific method;
- reversals, withdrawals and superseding decisions, with their reasons;
- the current conclusion and the uncertainty that remains;
- the associated OI identifiers, campaigns, RCAs and significant commits.

The following terms are not interchangeable:

| Term | Meaning |
|---|---|
| **Implemented** | The code, contract or wording change exists. |
| **Observed** | Intended behavior appeared in campaign evidence. |
| **Effective** | The original bounded defect did not recur under relevant evidence. |
| **Causally established** | A comparison isolated the change sufficiently to support attribution. |
| **Superseded** | Later reasoning or design replaced the earlier approach; the earlier evidence is not erased. |
| **Withdrawn** | The maintainer chose not to pursue the approach; this does not mean it was experimentally disproven. |
| **Reverted** | The implementation was removed; the motivation and resulting evidence remain part of the history. |
| **Failed implementation** | Execution did not test the intended scientific proposition. |
| **Negative scientific result** | A valid implementation produced evidence against the tested method or bounded claim. |

## Narrative organization

The history is organized by decision stream rather than date. Chronology is
retained within each stream.

### 1. Project framing and authority boundaries

Explain the transition to the present three-role harness:

- the Human owns the goal;
- the PI owns science, interpretation and training decisions;
- the Runner is a mechanical operator and gatekeeper without scientific
  judgment;
- scientific freedom applies inside the PI-owned surface;
- campaign execution remains under maintainer control.

Preserve changes that corrected role confusion, ownership boundaries, invalid
terminal outcomes and accidental Runner judgment.

### 2. Startup and initial scientific direction

Cover startup action selection, scientific-model handoff, baseline-first
behavior, physical investigation before training, shorter startup requests and
the still-open 120,000-step budget review. Also cover the scientific-model
prompt's robot neutrality: the preliminary analyst must derive consequential
capabilities from the human-owned robot and task rather than receive
scenario-specific capability categories from the harness.

Distinguish:

- a valid PI decision to train first;
- training selected because prompt structure or inherited framing made it the
  implicit default;
- scientific coupling between the model, first action and later inquiry;
- cost questions that do not invalidate the scientific choice.

Primary tracker ownership: OI-001, OI-006 and OI-021.

### 3. Inquiry semantics, closure and progression

Cover the sequence from success-shaped closure through bounded positive,
negative, limited and inconclusive closure; method-specific inquiry questions;
checkpoint continuation; recipe-switch coupling; redundant inquiry opening;
and revisable goal-review handoff.

Preserve why:

- indefinite inquiries were unacceptable;
- closing after every failed recipe was also inadequate;
- prohibiting method-specific questions was rejected;
- requiring a minimum number of operations would be another mechanical proxy;
- the current repair keeps bounded inquiry while making inherited judgments
  revisable.

Primary tracker ownership: OI-002, OI-004 and OI-016.

### 4. Evidence inspection, interpretation and experimental realization

Cover reduced summaries versus full artifacts, nested evidence discoverability,
the M30 false-missing claim, T10/I12 intended-versus-implemented mismatch,
component observability and the distinction between artifact comparison and
causal attribution.

Preserve separately:

- evidence existed but was not discoverable;
- evidence was discoverable but not inspected;
- evidence was inspected but interpreted incorrectly;
- the implementation did not instantiate the intended method;
- multiple factors changed, preventing single-cause attribution.

Primary tracker ownership: OI-003, OI-014, OI-015 and OI-017.

#### OI-014: candidate improvement is not mechanism identification

The read-only `89a6354a` RCA found that the selected comparisons could rank
candidates without distinguishing the causal explanations used to choose the
next direction. T6 measured 103/200 against T4's 186/200. Comparing the actual
recipes corrected an earlier interpretation of the changed-file manifest:
T6's observation values and reward remained equivalent to T4's. Its controller
combined branch selection, position correction, damping and blending with
retraining. The measured collapse did not isolate those causes, and the
artifact lacked branch, correction and trajectory diagnostics.

T7 differed from T4's scientific recipe only by the action filter, but it also
added training with a different seed and selected a new learned checkpoint.
Its paired result, 196/200 against 185/200 with eleven wins and no losses,
establishes candidate improvement, not an isolated filter effect.
The official pass remains valid.

The initial approved repair moved attribution guidance from reporting alone to
comparison design. The program and ordinary scientific prompts distinguish
candidate selection from mechanism testing. When a causal explanation would
change the next direction, the PI selects evidence that distinguishes it from
consequential alternatives. Otherwise, the cause may remain unresolved without
blocking closure or assessment. Existing instruments already support seeds,
transfer parents, paired panels, recipe restoration and laboratory measurements.
No new instrument, compulsory control, one-factor rule, repeated training,
budget change or Runner adequacy judgment was added.
The later `f917968b` comparison exposed a connected direction/commitment defect.
The corrective revision below replaces the blanket closure/assessment
exemption while retaining the distinction between candidate and mechanism claims.
No campaign was launched, resumed, reset or mutated.

#### Coding author and main PI reviewer: approved first step

In stopped campaign `bfd9e63d`, M5 kept mutable simulator-array history.
M6 copied only the initialization value and left the loop alias intact.
The PI accepted a nonzero first-step maximum and passed invalid speed claims
to I2. These are implementation and review failures, not scientific evidence
against the method. This repair does not change that campaign's code or record.

The approved generic mechanism separates coding authorship from main-PI
review. The `scientific_coding` SDK tool creates a narrow child conversation
using the existing client and campaign model/reasoning. Main-selected exact
file scopes, explicit source context and child instructions replace automatic
inheritance of the campaign conversation. The child uses scoped source reads
and patches, cannot submit operations, and authors a proportionate executable
laboratory check for the existing `python_module` instrument. The main PI gets
the actual per-invocation changes and diff, proposed check and unchecked scope.
It must inspect the implementation and check rather than accept assurances.
Only Runner executes the reviewed scientific check.

Ordinary main sessions retain source/evidence readers and operation-request
patches, but lose shell tools and direct scientific-source writes. The
preliminary analyst retains its current publication contract and has no coding
tool. The child has no shell, nested delegation, memory, skills, embedding
retrieval or automatic repository-instruction discovery. The permissions are
tool-level controls, not an operating-system sandbox.

Persistent child handles support same-change corrections across the existing
adapter restart boundary. Scope bindings contain identities and file lists,
not conversation contents. Child errors, timeouts and cancellation require
review of partial edits; child cleanup precedes adapter-owned runtime shutdown.
Durable existing usage rows identify the coding role and parent session, with
separate tokens/AIU/tools and non-overlapping durations.

Step 1 is implemented but scientifically unmeasured. Inert maintainer checks
do not establish that PI review will catch future faulty measurements. No
scenario-specific safeguard, reviewer agent, validity certificate, new
lifecycle phase, schema migration or scientific acceptance gate was added.
At step 1, the request-file handoff and per-invocation SDK runtime lifecycle remained intact.
Structured operation submission and persistent runtime belong to the separately
approved step 2, after review and publication of this change. Engineering
instructions stay in the coding tool and child, not the program or repeated
scientific prompts.

#### Structured submission and persistent runtime: approved second step

Step 2 removes request-file authoring from ordinary Copilot main sessions.
`submit_operation` accepts the existing instrument envelope; it does not expose
Runner arguments or arbitrary exchange paths. The mutex-owning PowerShell
launcher authenticates one local channel and checks campaign/session binding,
trusted mutable snapshots, stopped/terminal state and the existing transaction
before submission. Runner's existing schema-6 validator checks stdin without
changing the exchange file; only a validated request reaches the established
acceptance, publication, execution and finalization path.

The handler waits for Runner without model polls. Compact factual results,
exact errors and changed state return directly into that same SDK conversation,
including the actual operation list and mandatory checkpoint transitions.
Rejected requests retain one retry. Failed PI implementations retain source
repair/replacement authority. Publication failure stops rather than reaccepting
an already executed operation. Live repeated tool-call identities return their
cached response; channel loss stops submission. A resumed controller recovers
existing pending/completed state, and SDK resume disables automatic pending-work
replay in both main resume paths. The existing resume prompt supplies actual
durable Runner metadata, so an unfinished old call is not the next action.
Validation capture stays silent; execution stdout/stderr stream live through
concurrent asynchronous UTF-8 reads, with bounded error tails and no repeated
log dump at completion. No new scientific lifecycle, state migration, fingerprint scheme,
automatic scientific-content repair or validity judgment was introduced.

One launcher-owned SDK process/client remains alive, including across preliminary
publication and checkpoint-bounded contexts. Each checkpoint ends the current
context; the existing launcher starts a fresh UUID-bound context from durable
state, not a campaign-long conversation. Ordinary operation results do not replay
the full phase prompt. Usage is recorded once per logical bounded invocation:
Runner waiting and separately charged coding time are excluded from PI active
duration. Scoped coding and preliminary publication permissions remain.
OpenCode explicitly retains its legacy interface, not a second tool protocol.

This implementation is scientifically unmeasured. Only inert fake SDK/controller,
an output-only harmless pipe-process fixture, AST/import and whitespace checks
were run; no SDK/model session, Runner operation,
campaign reset or science/runtime service was started. Stopped campaign
`bfd9e63d` evidence and state remain unchanged. Parent review and publication are
separate from any subsequently authorized fresh campaign.

#### Startup transport failure and descendant search access

The maintainer subsequently authorized one fresh reset and visible-console
launch. Campaign `5de5e4a0` published its scientific model, then stopped in S1
after two valid training proposals were rejected with `OPERATION_VALID:
training`. No training or measurement completed. Preparation and startup
consumed 4.893137 AIU; the failure produced no scientific evidence.

The validator was not the cause. The new asynchronous stdin writer returned
an uncaptured completion value into PowerShell's success stream. The process
helper therefore returned an array containing that value and exit code zero,
instead of the intended scalar integer. The controller treated it as failure.
Earlier inert checks asserted nonzero exits and mocked scalar controller
responses; they did not verify the successful process return's exact type.
The correction discards the write completion. Harmless checks now require
scalar Int32 success and failure exits across empty, small and large stdin,
both silent capture and live streaming. The existing Unicode, concurrent-pipe
and error-tail checks remain successful.

The false rejection prompted broad searches for request examples. Root
searches exposed reserved documentation and Runner-state paths, although
direct documentation searches were denied. This descendant-access hole
predated the two SDK commits: approving a readable parent directory did not
restrict built-in search traversal. A search must apply the shared phase-aware
read policy before reading files or returning their paths. Redacting results
after reading forbidden content is not the repair. This distinct defect is
OI-023; OI-011's original bounded closure remains historical.

#### Approved integrated runtime and evidence revision

The maintainer approved replacing manual coding-session management with native
Copilot subagents, using SDK 1.0.19. Native lifecycle hooks carry narrow coding
context, engineering verification instructions and the installed MuJoCo,
Gymnasium and Stable-Baselines3 API versions. They do not judge scientific
adequacy. The main PI still reviews the actual source changes and proposed
executable laboratory check; only Runner executes it.

Corrections use the same native child with an unchanged exact-file binding.
Handles belong to the current bounded context, not a separately resumable SDK
session. The stop hook validates the engineering handoff, and the adapter
confirms native task idle state before unlocking operation submission.
Timeouts and cancellation preserve actual partial changes for review.
Usage and diffs are per invocation; native task-lifetime totals are labeled
separately rather than added again on each correction.

Copilot is the selected agent runtime, not a drop-in model-provider interface.
Scientific operations, evidence resolution and parsing remain ordinary harness
functions, exposed through SDK wrappers. OpenCode keeps its legacy interfaces,
without equivalent native-subagent or custom-tool capabilities.

The evidence decision is one JSON-query interface, retaining the existing
campaign-scoped, fingerprint-verified `artifact_evidence_query`, plus a
training-log-specific interface reusing the existing parser. The unused
`jello` dependency is removed rather than exposing general Python execution or
recreating that library. The PI may select fields, records, summaries, raw
content or the complete artifact. Successive subset requests and full-content
continuation must be explicit. Context economy is a capability, not a
restriction on what evidence the PI may request.

Trusted search overrides keep the existing `rg` and `glob` names. They prune
reserved descendants before traversal and give ripgrep only permitted files.
Directory `view` and preliminary shell traversal are denied; exact permitted
file reads remain. Linked aliases cannot bypass that boundary. Search previews
and evidence pages explicitly distinguish partial content from complete retrieval.

Sixty-seven assertions included real, harmless SDK-native reads, freeform
patches, permission propagation, same-child correction and cancellation.
Sixty-eight no-model policy checks cover pruning, authority boundaries and
explicit long-line preview disclosure.
Nineteen evidence fixture groups cover selected records, original bytes,
continuation, fingerprint mismatch and error states. These checks establish
implementation behavior, not scientific effectiveness.
Five real registered SDK tool dispatches additionally verify JSON/log raw
access, selection and fingerprint-bound record continuation without model
inference or Runner execution.

No intermediate campaign was run. Background engineering mechanics belong
in tool and subagent instructions. Program changes state scientific ownership and
inspection freedom, not another verification ritual. The stopped campaign,
its published model and its evidence are preserved. A future reset or launch
requires separate authorization.

#### Observed query/context failures and scoped restoration correction

The stopped `0d39d52c` campaign demonstrated working evidence access without
reliable ergonomics. The PI repeated array-selector mistakes in fresh contexts,
retrieved complete parsed learning trajectories and large episode arrays, and
accumulated 123,500 current SDK tokens in its last context. These observations
support OI-018/OI-008 correction; they do not isolate the causal cost of any
single tool or instruction. The maintainer chose to keep the custom engine,
not reopen a parallel jello interface.

The approved repair makes equality filters typed, preserves null comparisons,
expands selected arrays into rows with explicit reporting, and distinguishes
missing filter fields from valid zero matches. Small default row and byte pages
retain explicit complete retrieval. Training-log discovery returns identities,
coverage and metric names without record values; record queries require metric
selection or explicit all-metrics access. Console lines expose the selectors.

Operation completions no longer repeat evidence-access invitations or include
full artifact inventories and complete paired-seed arrays. Factual outcomes,
comparison counts, provenance pointers and state-transition metadata remain.
Detailed data is still returned when the PI explicitly requests it. The
persistent client and checkpoint-bounded conversation lifecycle are unchanged.

E12 also exposed a restoration-scope defect: restoring T1's complete recipe
rolled back the environment and evaluator, removing diagnostics subsequently
requested by M10. There is no robot-independent way for Runner to infer and
merge the scientific meaning of intertwined environment code. Restoration
therefore now requires an exact file selection, including the recorded
configuration. Unselected files remain intact, and campaign laboratory files
cannot be restored as a learning recipe. If the PI selects a shared
learning/instrumentation file, it carries the intended measurement capability
forward through scientific coding rather than relying on an automatic merge.
This prevents implicit blanket rollback; it does not certify diagnostic
completeness or prohibit intentional scientific redesign.

Targeted harmless fixtures and registered SDK tool dispatch verify these
mechanics, including null filters and preserved unselected measurement bytes.
The campaign report preserves the stopped observation separately from this
implemented/unmeasured revision. The maintainer authorized publication followed
by one fresh v3 recipe reset and visible-console campaign; that authorization
does not establish scientific improvement or authorize unrelated issue repairs.

#### Selected scientific-model context rejected at startup

Campaign `180ced98` tried to create a laboratory characterization tool before
training. Both coding requests selected the frozen scientific model for
read-only context. The coding allowlist excluded that file and returned only
a generic exact-scope error. The PI first changed path separators, then
incorrectly attributed the rejection to the absent laboratory directory and
switched to baseline training. Neither coding request dispatched a child.

This restriction and diagnostic originated in `eb04314`, the first coding
implementation, and survived the native migration. New laboratory files
were supported; the missing parent was not the cause. Earlier implementation
checks missed this startup context selection.

The approved repair permits the explicitly selected frozen model as read-only
coding context, retains protected-write and exact-file boundaries, and names
the offending path and reason on rejection. The coding interface explicitly
states that new writable files do not require an existing parent directory.
Thirty-seven harmless assertions reproduce both actual request representations,
confirm they fail under the prior allowlist, and verify corrected bindings,
selected child reads, protected writes and exact rejection feedback. The 68
existing no-model policy checks also pass; no new model inference was required.
The maintainer stopped the campaign; the repair does not authorize resumption,
reset or further scientific execution. Scientific effects remain unmeasured.

### 5. Assessment readiness, model roles and acceptance-gate drift

Cover counterevidence loss, premature readiness conclusions, best-known role
assignment, official assessment decisions, and PI-selected preferences that
became inherited acceptance gates.

Preserve the distinction between:

- the protected official success threshold;
- development evidence used by the PI to decide whether assessment is useful;
- research preferences selected during a campaign;
- accidental requirements not present in the human goal or immutable
  contracts.

Scenario-specific examples, populations and diagnostic labels remain in their
campaign RCA rather than becoming generic harness instructions.

Primary tracker ownership: OI-005 and OI-019. OI-020 is withdrawn.

#### OI-005 decision history: from caution to a two-sided comparison

Earlier failures exposed counterevidence loss and narrow development evidence
being promoted to readiness. The three-sentence block in `e4736da` responded
with caution about residual failures and favorable scores. The maintainer
withdrew it in `b275861`; its effect was never established. The withdrawal is
not evidence that preserving counterevidence was wrong.

Later campaigns showed why caution alone was incomplete. `58dcd817` and
`896c230a` requested assessment while imagining useful work after failure.
`79395c88` and `339736e0` never assessed: self-selected development gates,
relative-role misconceptions and unresolved mechanisms repeatedly justified
deferral. The latter campaign still produced useful diagnostic evidence.
Its length therefore cannot establish that continued work was pointless.
The following success in `ec7f3d3a` did not close both failure directions.
The older `06656182` reason also contained a partial productivity comparison,
contrary to the earlier oversimplification that no comparison existed.

On 11 October, independent parent and Opus 5.5/high RCAs were reconciled.
The adopted repair replaces one-sided readiness caution with a goal-level
comparison: commit the strongest evidence-backed candidate to a terminal
assessment, or pursue bounded work whose expected contribution warrants the
delay. It preserves contrary evidence and relative best-known semantics.
The program owns the principle and ordinary goal-review prompts route to it.
There is no new threshold, mandatory measurement, automatic assessment or
Runner adequacy judgment.

Implementation is not demonstrated effectiveness. The maintainer authorized
a fresh v3 campaign after publication to observe actual decision reasons.
OI-005 remains implemented/unmeasured at publication; OI-019 and OI-021 remain
outside this repair. The
[reconciled RCA](oi005_assessment_decision_rca_20261011.md) preserves the case
evidence, differences between the independent analyses and rejected approaches.

That authorized campaign, `89a6354a`, passed officially at 196/200 with T7.
It first stopped after the PI twice omitted accepted S3 operations from its
session summary. The assistant corrected only that metadata under the original
autopilot authorization; the scientific content and accepted evidence were
unchanged, and the same campaign continued without another reset.
Its final reason recognized terminality and weighed further mechanism work
against commitment, rather than treating a failed assessment as a route to
another inquiry. However the preceding handoff still used development-threshold
and closure wording as triggers, and the final reason omitted four residual
failures preserved in the checkpoint. OI-005 is therefore implemented/observed,
not closed. The passing verdict is not a causal validation of the repair.
Recorded campaign use was 77.03 AIU and about 84m32s reset-to-end wall time;
the interruption and maintainer-assistant metadata correction remain part of that
history, not hidden from the successful outcome.

The subsequent approved OI-005 revision moves the decision-record obligation
from the program into ordinary goal-review prompts. The PI must preserve
relevant limitations in its operation reason and explain commitment despite
them. Acknowledgment was not a demand to resolve every failure or perform
another measurement. The later campaign preserved more limitations but still
showed defective commitment reasoning. The old E15 reason does not
retrospectively become evidence that the PI explicitly accepted its four failures.

#### Connected direction and commitment correction

Parent and independent read-only RCAs compared the previous passing campaign
`89a6354a` with `f917968b`, which failed at 193/200 using unchanged T3.
Both launched with the same v3 recipe, PI model, reasoning and training
allocation. T1 learning sources, parameters, seed and all 24 saved training
proxy snapshots matched. This does not establish complete learned-state
equality or isolate a harness effect.

| Recorded use | Previous `89a6354a` | Latest `f917968b` |
|---|---|---|
| Completed training steps | 845,824 | 1,087,488 |
| Inquiries / checkpoints | 3 / 7 | 9 / 19 |
| Direct development episode executions | 2,000 | 3,680 |
| Distinct direct development panels | 7 | 1 reused |
| AIU / PI time | 77.03 / 29m02s | 156.47 / 54m09s |

The latest campaign gained characterization and more limited causal claims,
but did not improve T3 after six completed training alternatives. Most added
cost was inquiry work. M6 failed execution, M7/M8 contained invalid
characterization implementations, and M9 corrected them. Those repairs do not
all constitute scientific progress. The regulation direction persisted across
promptly closed inquiries, increasingly focusing on four no-entry failures
while omitting five failed holds. E33 called T3 unlikely to meet the criterion;
E43 later committed it because alternatives were worse and no better route
emerged. Relative selection strengthened without improving T3's capability.

The older negative-recipe safeguard came from `8166e2f`, before OI-014/OI-015
registration, and was present in both campaigns. `ade304d` added the
closure/assessment exemption. Their permissive interaction is a plausible
contributor, not an isolated cause. The approved correction replaces blanket
permissions with accumulated direction review under OI-014 and a distinct
candidate-prospect comparison under OI-005. Important rules appear directly in
ordinary PI prompts, not merely as references. Unresolved causes can survive
closure, but closure justifies neither continuing a direction nor assessment.
Scientific possibility alone does not justify another variant.

A narrow OI-004 clarification contextualizes training proxies by exposure and
runtime. T10's two 100% proxies were visible but omitted from M14, as were all
full-radius-stage checkpoints. Their superiority remains unknown. T3's measured
terminal artifact beat its earlier 100%-proxy artifact, so this is not proof of
terminal preference. The original bounded OI-004 closure remains historical.

The raw-versus-applied-command diagnostic and incomplete residual accounting
remain scientific-code/evidence corrections, not generic scenario instructions.
No OI-015 mismatch, old access defect or original OI-002/OI-016 boundary defect
is reopened. No new instrument, readiness threshold, mandatory repetition,
complete-explanation requirement or Runner scientific judgment was added.
The corrective wording is implemented/unmeasured. No campaign was launched,
resumed, reset or mutated by this revision.

#### Capped continuation and the approved OI-005/OI-014 adjustment

Campaign `90563aac` closed 15 inquiries but never requested assessment.
Its best development result remained 153/160 after another 162.310939 AIU.
Development-threshold deferral and nominally new methods repeatedly supported
continuation. T3/T7/T8 and T2/T9 matched saved learning components at all 24
corresponding checkpoints. Packaged runtimes differed, so this does not prove
complete artifact equivalence. T7 to T8 also had no scientific-source delta.
This supports a continuation regression concern, not exclusive prompt causality.

The maintainer approved a bounded adjustment to the implemented repairs.
OI-005 removes the additional assessment-only burden from the program and
ordinary prompts. The PI compares candidate prospects with the expected
contribution and cost of further work. A below-goal development result does
not prohibit assessment. An untested variant or unresolved cause does not
justify another inquiry by itself.

OI-014 connects method claims to the implementation already tested, including
source changes, recorded runtime and available saved-component comparisons.
A new description does not establish a new method. Repetition remains useful
when it supplies additional evidence. The Runner does not decide novelty or
scientific necessity. This is not the unimplemented OI-024 submission safeguard.
Both adjustments remain implemented/unmeasured, with unchanged terminality
and inquiry-cap rules.

### 6. Context delivery, cost and evidence tooling

Cover brief growth, prompt replay, SDK output, session cost, artifact-query
access, repeated wildcard traversal, batching, projections, aggregation and
console observability.

Preserve separate measures for:

- AIU and token cost;
- tool-call count and returned context;
- wall-clock training and CPU cost;
- campaign length and number of inquiries;
- scientific usefulness of retrieved evidence.

Primary tracker ownership: OI-008, OI-011, OI-017 and OI-018.

#### Brief replay and strict query feedback

The earlier OI-008 repair compacted completion replies but left a separate
growth source in `build_brief.py`. The paused `90563aac` state rendered a
172,738-byte brief. It replayed every checkpoint's metadata, all operation
details, structural inventories and resolved failure traces.

The approved adjustment preserves the current goal, scientific model,
checkpoint, roles and session. It indexes all training operations, measured
checkpoints, source provenance and exact saved-component comparisons.
Current-work and latest-checkpoint references select the included event facts.
Paired outcome summaries remain, but complete seed panels do not repeat.
Full checkpoint metadata and history remain in archived artifacts and
`campaigns/results.jsonl`. `campaigns/EXPERIMENTS.md` supplies a chronological
index. The existing query tools retain artifact discovery and complete reads.
The same stopped state now renders 24,989 bytes, an 85.53% reduction.
This check demonstrates delivery reduction, not lower campaign cost or better
scientific judgment. Existing campaign evidence was not rewritten.

OI-018 retains strict rejection rather than accepting unsupported nested
`max_bytes`. The field controls one top-level selected-value budget shared by
the batch. Schema and tool guidance now state that location. A specific
validation error explains the correction. Console output identifies artifact
index on starts and failures, so the two M31 calls no longer appear identical.
An actual registered SDK dispatch rejects the malformed batch before its
handler runs. The corrected request succeeds with its provenance and
continuation intact. Earlier null-filter and selected-log behavior remains.
Query-error rates and total context cost still require campaign observation.

### 7. Operational resilience and publication

Cover bounded runtime shutdown, Git publication, completed-operation recovery,
campaign pause boundaries, independent frozen-policy publication proposals and
the rejection of scientific exhaustion as a Runner-created terminal outcome.

Keep operational correctness separate from scientific effectiveness.

Primary tracker ownership: OI-009, OI-010, OI-012 and OI-013, together with
closed operational repairs that no longer require OI tracking.

#### OI-009: a newly observed checkpoint failure

Campaign `89a6354a` exposed a concrete handoff failure. The inquiry closed,
but its scientific session still needed a checkpoint covering training,
measurement and closure. The PI instead submitted only the closure operation,
then inferred a fresh session and submitted an empty list. The correct list
remained in Runner state. Generic rejection feedback did not supply it.
The campaign needed an external metadata correction before continuing.

The relevant boundary wording and exact-list check predate OI-005.
This establishes a newly observed failure, not a proven OI-005 regression.
The bounded repair adds current-session and exact-list context at checkpoint
transitions, expected/submitted values in rejection feedback, and documentation
of accepted-request consumption. It preserves strict validation and the retry
limit. It does not automatically change PI scientific content.

The repair is implemented/unmeasured, with no new campaign or replay.
The [RCA](oi005_assessment_decision_rca_20261011.md#approved-post-campaign-interface-repair-oi-009-and-oi-005)
preserves the provenance, failure sequence, approved scope and evidence limits.

## Entry format for each decision stream

Each curated section should use the following structure:

1. **Original failure**
2. **Evidence and affected campaigns**
3. **Diagnosis at the time**
4. **Attempted repair**
5. **Subsequent observation**
6. **Reversal or superseding decision**
7. **Current conclusion**
8. **Remaining uncertainty and tracker ownership**
9. **Source links**

The text should be explanatory prose, not another issue table or copied
timeline. Dates are used to order changes inside a stream, not as the primary
information architecture.

## Curation method

The legacy archive will be curated incrementally:

1. Inventory each legacy heading and assign it to one decision stream.
2. Identify duplicated descriptions and retain one narrative account with
   source links.
3. Extract all failure, reversal, withdrawal and supersession statements.
4. Cross-check each extracted finding against the live OI register.
5. Register any unresolved finding that lacks an owner before declaring the
   stream complete.
6. Preserve campaign IDs, important commits and RCA links needed to verify the
   narrative.
7. Leave the archive unchanged.

Completion means every substantive legacy entry is represented by a curated
decision stream or explicitly classified as routine implementation detail that
remains available only in the archive. It does not mean every legacy paragraph
is copied.

## Current curation status

The documentation structure is adopted, but full thematic curation of the
legacy archive is **pending**. Campaign `ec7f3d3a` closed OI-003 and OI-016
without an expensive replay. OI-015 remains implemented but unmeasured because
its historical T10/I12 semantic mismatch was not exercised by that campaign.
OI-020 was withdrawn after review showed that it improperly generalized a
scenario-specific RCA symptom. OI-021 now owns the confirmed
scenario-specific scientific-model prompt, whose impact must be documented
before repair.

No claim should be made that the historical narrative is complete until all
legacy headings have been inventoried and reconciled against the tracker.
