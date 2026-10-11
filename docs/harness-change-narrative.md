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
them. Acknowledgment is not a demand to resolve every failure or perform
another measurement. This revision is unmeasured. The old E15 reason does not
retrospectively become evidence that the PI explicitly accepted its four failures.

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
