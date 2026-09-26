# Research postmortems

## 3e3387d5-4eae-4e5e-a34b-c8dfa83788e5 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned strong but slightly
below-threshold reach-and-hold behavior. Checkpoint-100352 is the strongest
measured policy: it achieved 195/200 (97.5%) on research episodes 2000-2199
and 196/200 (98.0%) on the disjoint research episodes 2200-2399, for 391/400
(97.75%) pooled success. The fixed task-reference score of 98% is descriptive
only because that panel was used in selecting the checkpoint; it is not
independent confirmation. The official objective therefore remains unresolved.

**Lessons and limits:** Training proxies identified a useful selection region
but did not establish the objective: checkpoint-86016 measured 192/200 and
checkpoint-120832 measured 194/200 on the first research panel, both below
checkpoint-100352. The selected policy's four research-panel failures include
episodes that never reached the tolerance region, so residual failures are
real task failures rather than a rounding issue. Development panels do not
replace the fixed 200-episode official assessment.

**Open questions:** Whether the retained baseline can meet at least 196/200
on the official panel is unresolved, as is whether a changed training recipe
can eliminate the small but persistent residual failure rate.

## 3e3387d5-4eae-4e5e-a34b-c8dfa83788e5 / Experiment 1

**Result:** Checkpoint-100352 is retained as the working and best-known policy.
The baseline recipe is kept. No alternate candidate is retained.

**Observed behavior:** The selected checkpoint achieved 195/200 (97.5%) on
research panel episodes 2000-2199 and 196/200 (98.0%) on the fresh disjoint
panel episodes 2200-2399. Its pooled research result is 391/400 (97.75%).
Checkpoint-86016 scored 192/200 and checkpoint-120832 scored 194/200 on the
first research panel. Checkpoint-100352 scored 98% on the reused fixed
task-reference panel, but that result is not independent selection evidence.

**Hypothesis assessment:** This was a fresh baseline with no intervention
prediction; it establishes a strong near-threshold policy but does not
establish the official 98% objective.

**Interpretation:** The second disjoint research panel confirms stable,
near-threshold behavior and supports selecting checkpoint-100352 over the
other measured checkpoints. The policy is useful for future development, but
the 97.75% pooled development result and non-independent task-reference score
do not justify claiming objective success or bypassing the official benchmark.

**Evidence inspected:** `research/research_state.json`;
`research/checkpoints/challengers/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/experiment-1/inventory.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-1-checkpoint-100352-200ep-seed2000-f48545f83637.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-1-checkpoint-100352-200ep-seed2200-f48545f83637.json`
