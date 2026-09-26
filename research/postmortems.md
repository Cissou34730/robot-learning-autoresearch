# Research postmortems

## 3e3387d5-4eae-4e5e-a34b-c8dfa83788e5 / Scientific strategy

**Current synthesis:** The PPO baseline learned strong, stable, near-threshold
reach-and-hold behavior: checkpoint-100352 achieved 391/400 (97.75%) across
two disjoint research panels. Its 98% task-reference result is descriptive
only because that panel was used for selection, so the official objective
remains unresolved.

**Lessons and limits:** Checkpoint-100352 outperformed the measured earlier and
later checkpoints, but its residual research-panel failures are genuine task
failures, including episodes that never reached tolerance. The baseline trains
on 14-20 cm targets although the official distribution spans 6-20 cm.
Development measurements do not replace the fixed 200-episode official
assessment.

**Open questions:** The evidence does not establish the official verdict or
whether broader training-radius coverage changes the residual failure rate.

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
