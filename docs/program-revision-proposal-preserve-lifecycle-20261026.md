# Proposal: improve PI decisions within the existing lifecycle

Date: 26 October 2026

Status: proposal only. The active contracts and runtime remain unchanged.

Baseline: `harness` at `3135b37b478b7607c57032073c2f5a2c2048bad3`.

## Intent and scope

Revise three passages in `contracts/program.md` to improve scientific decisions
within the existing lifecycle. Keep every lifecycle transition, permission,
instrument and record format.

The human defines the scenario and final benchmark. Runner executes accepted
operations. The PI owns scientific direction, implementation choices,
interpretation and the decision to request final assessment.

This is a separate alternative to the
[25 October proposal](program-revision-proposal-20261025.md). That document
remains unchanged. Its architectural changes are not prerequisites for this
proposal.

The proposal contains maintainer reasoning and three replacement passages.
Only the passages marked as campaign-facing text would enter the program.
Everything else in the active program stays as written.

## What the existing design already provides

The program already permits training, measurement and implementation within an
inquiry. It permits inconclusive closure and revision of inherited judgments.
It distinguishes candidate comparisons from causal explanations. It also
requires evidence for consequential conclusions.

These are useful foundations. The proposed changes clarify how the PI uses
them. They do not introduce a new research process.

| Existing element | Treatment |
|---|---|
| Preliminary analyst and initial physical model | Keep the analyst, publication rules and immutable initial document. |
| Five-level hierarchy | Keep human goal, campaign, inquiry, scientific session and operation. |
| Startup and goal review | Keep their purposes and permitted operations. Goal review still chooses an inquiry or official assessment. |
| Inquiry opening, reframing and closing | Keep their checkpoint requirements and fresh-session transitions. |
| Bounded scientific sessions | Keep session deliverables, intermediate checkpoints and continuation of active inquiries. |
| Scientific session record | Keep every required field and its meaning, including numerical goal-gap reporting. |
| Evolving scientific understanding | Keep corrections in `current_synthesis` and unresolved distinctions in `decision_frontier`. |
| Coding and execution | Keep delegated coding, independent engineering review and Runner execution. |
| Training and candidates | Keep allocation rules, candidate creation, restoration and explicit model roles. |
| Final assessment | Keep PI selection, the protected benchmark and terminal pass or fail. |
| Context and recovery | Keep current routing, durable state, publication and recovery behavior. |

The frozen initial model preserves provenance. The existing session records
already allow the PI to revise its conclusions. No new notebook or writable
scientific-model surface is proposed.

## Evidence and limits

Three observations motivate the edits, with different levels of confidence.

1. **A textual tension exists.** The inquiry introduction says the PI revises
   understanding "before choosing an intervention". The next paragraph makes
   training, measurement and implementation peer options. The two instructions
   can suggest different orders of work. This establishes ambiguity, not its
   contribution to a particular campaign failure.
2. **A consequential experimental assumption failed.** In campaign `efd58acc`,
   T10 combined a policy transformation, changed normalization and further
   training. M32 later examined the effects before learning. Independent replay
   produced 32/32 successes for the original policy and 0/32 after projection
   alone on the same fresh development episodes. The failure existed before
   additional learning. M32 also demonstrates that the current lifecycle can
   execute the relevant diagnostic.
3. **Cautious interpretation did not ensure a useful next experiment.** The
   review found limited conclusions after incompatible transfers in T7–T10.
   Those limits were often acknowledged. Better instructions for selecting the
   next development step might help, but their benefit remains untested.

The 64 inquiry/checkpoint operations in that campaign do not prove that the
lifecycle caused failure. They are not a justification for removing it here.
Different training seeds and changing task definitions also prevent a causal
comparison of the three campaigns' prompts.

The evidence supports a bounded instruction experiment. It does not establish
that these edits will improve final success or solve every PI failure.

Sources:

- Current [program](../contracts/program.md), especially Inquiry work and
  Bounded scientific sessions.
- Current [instrument contract](../contracts/instruments.md), including the
  unchanged session permissions and checkpoint fields.
- Current [measurement contract](../contracts/instruments/measurement.md),
  including the existing `python_module` instrument.
- Local [PI root-cause review](C:/Users/cyril.beurier/.codex/visualizations/2026/10/24/01a16fda-cf1c-7870-ac7c-4fc5f949f985/pi-rca/PI-root-cause-review.md),
  findings 2–4 and the independent replay files linked there. This local audit
  link is not a portable repository artifact. The archived campaign evidence
  includes `efd58acc` at campaign commit `6f02da08`, T10 and M32.

## Change 1: remove the implied diagnosis-first sequence

**Target:** replace the first paragraph under `Inquiry work`, from
"An inquiry is a temporary question or obstacle" through
"No intervention category is privileged in advance."

**Reason:** preserve the connection between experiments and the scientific
model without suggesting that understanding must improve before an
intervention can supply evidence. The current program already grants that
freedom elsewhere. This edit makes those instructions agree.

**Campaign-facing replacement:**

```text
An inquiry is a temporary question or obstacle whose resolution can change the
route toward the human goal. Within it, choose supported scientific actions
that can produce evidence or implementation changes needed for the next
decision. Connect observed outcomes to the scientific model. Test
consequential explanations and revise the campaign's understanding as evidence
changes it. An intervention can supply the evidence needed to revise an
explanation. An unresolved explanation does not prevent development when the
proposed work can advance the inquiry. Set aside unknowns that cannot affect
the direction. No intervention category is privileged in advance.
```

**Expected effect:** the PI can explain why an intervention is the appropriate
next experiment without first inventing a completed diagnosis.

**Risk and limit:** the PI could treat this as permission to ignore evidence.
The surrounding requirements for discriminating evidence, supported conclusions
and goal connection stay intact. This edit does not relax them.

## Change 2: examine assumptions that can invalidate an experiment

**Target:** replace the two-sentence paragraph under `Scientific identity`
that begins "When requesting a diagnostic" and ends
"when those conditions do not hold."

**Reason:** the current instruction covers diagnostic conditions and limits on
conclusions. Extend that principle to the implementation assumptions of a
costly experiment. T10 provides a concrete case where examining one assumption
earlier could have changed the plan. This does not establish that every
experiment needs another measurement.

**Campaign-facing replacement:**

```text
Before a costly experiment, identify assumptions whose failure would prevent
the result from answering the intended question. Use existing evidence to
assess them. For transferred policies, changes to observations, actions or
normalization can change behavior before further learning. When this matters
to the decision, consider measuring that effect before training.

Choose an additional check when its possible results can change the plan and
justify its implementation and execution effort. Existing evidence may be
sufficient. If you proceed with an unresolved assumption, preserve it and
limit the resulting claim accordingly. When requesting a diagnostic, state
the conditions needed for it to answer your question. Limit conclusions when
those conditions do not hold.
```

**Expected effect:** the PI considers whether an experiment tests its intended
method or mainly tests recovery from an incompatible implementation.

**Risk and limit:** extra diagnostics can delay useful development. The text
makes their value conditional and includes their implementation cost. It
requires no fixed diagnostic, extra operation, matched comparison or universal
measurement-before-training sequence.

Existing source inspection, completed evidence and Runner measurements support
this instruction. It grants no direct execution or editing authority. It does
not request shorter training allocations or use measurement to bypass training
and candidate rules.

## Change 3: strengthen the reason for the next development step

**Target:** replace the two paragraphs under `Inquiry work` that begin
"Choose among developing the method" and end
"State what additional evidence it supplies."

**Reason:** the current program correctly prevents an unsuccessful
implementation from disproving a whole method. It also already asks the PI to
justify its next action. This edit makes that justification more specific:
which limitation or opportunity does the next action address?

This is the least certain of the three changes. It strengthens an existing
instruction rather than supplying a missing permission. The current system
prompt already identifies time and AI usage as campaign outcomes. The edit
connects effort to the local choice without adding budgets or reporting fields.

**Campaign-facing replacement:**

```text
Choose among developing the method, investigating a consequential failure,
and changing direction. Explain why the chosen action can advance the human
goal from the current evidence. For method development, identify the specific
limitation or opportunity that the next implementation addresses. A promising
change need not already have a measured benefit.

Compare the proposed method with the implementation already tested. Use source
changes, recorded runtime and saved-component comparisons when available.
A new description does not establish a new method. An inconclusive result
alone does not justify another attempt or abandonment of the method.
When repeating work, state what additional evidence or development it can
provide. Consider implementation and execution effort when choosing between
useful actions. Record the reason in the existing rationale and scientific
session record fields.
```

**Expected effect:** a limitation on a conclusion leads to a specific,
defensible next action. It does not become an automatic reason to continue
the method or abandon it.

**Risk and limit:** demanding certainty could suppress exploration. The draft
explicitly permits work without a previously measured benefit. Its explanation
belongs in the existing fields. It requires no additional report or checkpoint.

## Adoption footprint

If adopted, apply only these three replacements to `contracts/program.md`.
Retain every other paragraph, including the lifecycle and context sections.

No runtime, launcher, authority, instrument schema or state migration change
is required. The current system prompt already supplies the program's content.
The coding-contract excerpt boundaries are unaffected.

Changes to short-pilot limits, direct PI editing, optional review, candidate
packaging or persistent memory are outside this proposal. None is required to
try these instructions. The separate policy-boundary issue from the RCA also
remains outside this revision.

## How to evaluate the proposal

Review the wording against the existing contracts before adoption. The PI must
still use the same operations, handoffs, permissions and record fields.
Check whether the new passages create pressure for unnecessary diagnostics or
duplicate explanations.

For a subsequent experiment, keep the runtime and lifecycle fixed. Compare the
current program with the proposed wording using the same development evidence,
model settings, starting candidates and resource settings. Use separate arms
for the edits when attribution matters. Change 3 needs particular scrutiny
because much of its intent already exists in the program.

Useful decision cases include:

- a policy transfer with a consequential, untested assumption about behavior
  before learning
- an intervention that can advance an inquiry despite unresolved causes
- an inconclusive implementation result with several possible next actions
- a case where existing evidence already answers the implementation question

Judge whether the selected action addresses the evidence and remaining goal
gap. Inspect what actually executes and what the result supports. Do not score
the PI for repeating the new wording or selecting a prescribed method.

Track useful experimental results, implementation and measurement effort,
unsupported conclusions, and unnecessary diagnostic work. Follow with repeated
complete campaigns under matched task definitions and training-seed sets before
claiming improved final performance. A single successful campaign is insufficient
to attribute improvement to these instructions.

This document creates no evaluation infrastructure and starts no campaign.
For the proposal itself, document and reference review are sufficient. Do not
add automated tests for its wording or structure.
