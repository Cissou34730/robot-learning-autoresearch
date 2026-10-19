# OI-016 post-campaign RCA

**Date:** 2026-10-09  
**Campaign:** `79395c88-afcd-40f0-a644-16ca95368c28`  
**Compared with:** pre-repair campaign `1ae27a27-6880-4ca6-9d50-e6498e771cb7`  
**Repair assessed:** OI-016, commit `e0ffcd8`

## Executive conclusion

The OI-016 repair did not correct the targeted behavior. It changed the
wording of inquiry questions and handoffs, but it did not prevent the PI from
encoding a selected solution family inside the inquiry question, selecting
training first, or closing an inquiry after a single recipe-level negative
result.

The post-repair campaign therefore provides evidence that OI-016 was
**implemented but ineffective** in its tested form. It also consumed more
resources than the preceding full campaign without producing a goal-qualified
candidate.

This RCA does not establish that OI-016 directly caused the lower-performing
policies. Training recipes, algorithms and random outcomes changed between
campaigns. The established finding is that the repair failed to change the
scientific lifecycle behavior it was intended to change.

## Evidence scope

The post-repair campaign was based on a commit containing `e0ffcd8`, so the
campaign exercised the OI-016 contract and prompt changes. The analysis uses
the completed campaign records, durable brief, evaluation artifacts and
read-only Git history. No campaign was launched, resumed, reset, trained,
measured or evaluated during this analysis.

The campaign completed all 15 permitted inquiries:

| Metric | Pre-repair `1ae27a27` | Post-repair `79395c88` | Change |
|---|---:|---:|---:|
| Inquiries | 15 | 15 | No improvement |
| Training allocations | 14 | 17 | +21% |
| Requested training steps | 1.68M | 2.04M | +360k |
| Completed measurements | 19 | 27 | +42% |
| Training-first inquiries | 14/15 | 12/15 | Small improvement |
| Elapsed execution time | 2.62 h | 4.57 h | +74% |
| Goal-qualified candidate | None | None | No improvement |

The reduction from 14/15 to 12/15 training-first inquiries is not sufficient
to show a changed lifecycle. The two measurement-first inquiries did not
restore open-ended inquiry formation; both were already directed toward a
selected policy method.

## What the campaign did

The campaign complied with the formal language of OI-016. Inquiry questions
were written using unresolved-question syntax, and the PI repeatedly stated
that training was not mandatory. However, the questions still selected the
next solution family:

- I2: branch/limit-aware coverage;
- I3: explicit branch/trajectory representation;
- I4: velocity shaping or history representation;
- I5: branch/trajectory representation;
- I6-I7: action or control-interface changes;
- I8-I9: policy-side methods;
- I10: phase/history acquisition;
- I11: branch-conditioned trajectory design;
- I12: controller-imitation training;
- I14: acquisition/representation redesign;
- I15: a materially different acquisition method.

This is operation-shaped inquiry formation at the level of a method family,
even when no exact training run is named.

The operation sequence confirms the continued pattern:

| Inquiry group | Observed path |
|---|---|
| I1 | T1 -> M2 -> M3 |
| I2-I7 | One training intervention, usually followed by one diagnostic measurement |
| I8 | Continued training and stabilization-reward variant |
| I9 | Measurement, then controller-prior training |
| I10-I11 | Phase/history and branch-conditioned policy training |
| I12 | Measurement-only diagnostic |
| I13 | No new scientific operation |
| I14 | Four PPO variants and six measurements |
| I15 | SAC training and terminal measurement |

I13 is especially important. It opened and closed without a new scientific
operation, repackaging existing evidence as a new limited-negative inquiry.
This shows that inquiry count had become a count of method pivots rather than
a count of distinct unresolved questions being resolved.

## Performance trajectory

The campaign produced useful evidence, but its tested candidate routes were
mostly unsuccessful:

- T1: 93.75% on the 160-episode development panel;
- T2: 32.5%;
- T3: 18.75%;
- T4: 45.62%;
- T5: 67.5%;
- T6: 10.62%;
- T7: 18.75%;
- T8/T9/T10: 95.62%;
- T11: 0%;
- T12: 27.5%;
- T13: 31.88%;
- T14: 38.75%;
- T15: 97.5% on 160 episodes, then 95% on the 200-episode panel;
- T16: 96% on 200 episodes;
- T17: 84% on 200 episodes.

No candidate reached the 196/200 development threshold. The campaign also
correctly avoided a protected official assessment.

## Root-cause chain

### 1. The contract prohibits exact recipe questions, but not solution-family questions

The OI-016 contract says that an inquiry must not merely name a training run,
measurement, implementation or recipe. That rule blocks a narrow form of
precommitment but leaves a loophole: a PI can select an entire intervention
class and present it as an unresolved scientific question.

For example, “Can controller-imitation training transfer capability?” is
grammatically a question, but it still commits the inquiry to a selected
method family.

### 2. Verbatim handoff preserves the hidden operation choice

The prompt describes the selected question as verbatim handoff state. The
prompt also says that the question is not a commitment to an operation.
Those statements conflict when the question contains a method family.

The durable checkpoint then repeatedly directs the next session toward a
specific representation, control interface, trajectory design, or learning
method. The warning leaves the PI free in principle, but the durable handoff
continues to carry the selected route in practice.

### 3. Recipe-level negatives close broader unresolved inquiries

The campaign repeatedly used the following cycle:

1. select a solution family;
2. test one recipe from that family;
3. record a limited negative;
4. close the inquiry;
5. return to goal review;
6. open the next solution family as a new inquiry.

A failed recipe can be valid evidence without answering the broader
mechanistic question. The current closure rules do not require the PI to
show that the underlying distinction was resolved before closing the inquiry.

### 4. Goal review turns every redirect into another inquiry

When no inquiry is active, goal review can request official assessment or open
one new bounded inquiry. Since official assessment was correctly unjustified,
each recipe redirect required another inquiry. The combination of permissive
closure and operation-shaped questions therefore creates an inquiry
proliferation loop.

The 15-inquiry cap was reached without scientific exhaustion and without a
campaign-level conclusion.

### 5. The repair was advisory rather than structural

The implementation added prompt instructions to:

- restate the unresolved distinction;
- explain why the first operation is decision-relevant;
- treat training, measurement and implementation as peer options.

The PI can satisfy these instructions while still selecting training first and
while still embedding the next intervention family in the question. The
post-campaign records show that this is what happened.

## What is established and what is not

### Established

- OI-016 was present in the campaign's base commit.
- Twelve of fifteen inquiries began with training.
- Nearly every inquiry encoded a selected solution family.
- Most inquiries closed after one recipe or one narrow route.
- I13 closed without a new scientific operation.
- The campaign reached the 15-inquiry cap.
- The campaign used more training allocations, measurements, requested steps
  and elapsed runtime than the preceding full campaign.
- No candidate met the development threshold.
- OI-015 component comparison reporting worked technically: completed
  training records and the durable brief reported exact saved-component
  comparisons without false equivalence claims.

### Not established

- That OI-016 directly caused the poorer policy scores.
- That SAC, PPO, learned control, the direct-action interface or the physical
  system is generally inadequate.
- That all controller-imitation, branch-conditioned or representation methods
  are ineffective.
- That the campaign's lower candidate performance was caused by the prompt
  changes rather than by the different tested recipes and stochastic training
  outcomes.

## Why earlier OI progress was preserved

The post-repair campaign did not regress every lifecycle property:

- OI-015 observability remained active.
- Measurement and training remained peer instruments in the contract.
- No Runner scientific gate or measurement-first rule was introduced.
- Evidence interpretation stayed recipe-bounded in the recorded conclusions.
- No protected official assessment was requested prematurely.
- The inquiry cap paused at a completed boundary rather than fabricating a
  campaign conclusion.

The regression is specifically the coupling of inquiry identity, selected
method, durable handoff and closure.

## Corrective design requirement

The missing invariant is:

> An inquiry must represent the unresolved, decision-changing scientific
> distinction. A method or intervention is a current route within that
> inquiry, not the inquiry itself. A negative recipe result should normally
> change the route within the same inquiry unless it answers or invalidates
> the underlying distinction.

Any correction should preserve:

- the PI's authority to choose training, measurement or implementation;
- the Runner's non-judgment role;
- bounded positive, negative, limited and inconclusive closure;
- the distinction between a recipe result and a general method conclusion;
- OI-001 through OI-004 and OI-015 behavior.

## RCA status

**OI-016: implemented but ineffective in the tested form.**

The post-campaign evidence is sufficient to reopen the implementation design
discussion. No corrective code or contract change is included in this RCA.
