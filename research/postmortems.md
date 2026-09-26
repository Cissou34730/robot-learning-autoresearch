# Research postmortems

## 3e3387d5-4eae-4e5e-a34b-c8dfa83788e5 / Scientific strategy

**Current synthesis:** PPO checkpoint-100352 remains the strongest saved policy,
with 391/400 (97.75%) across two disjoint research panels. On the latest
disjoint panel it and all three measured full-radius transfer checkpoints
scored 191/200 (95.5%), so the policy is consistently near threshold in
development measurements but its official result is unresolved.

**Lessons and limits:** The selected policy outperformed the measured earlier
and later baseline checkpoints. Expanding training from 14-20 cm to the full
6-20 cm range produced no aggregate, radius-bin, or paired improvement in one
transfer run; the matched outcomes were 58/60 at 6-10 cm, 56/56 at 10-14 cm,
56/59 at 14-18 cm, and 21/25 at 18-20 cm. This weakens that intervention without
establishing that every radius-focused method is ineffective. Development
measurements do not substitute for the fixed official panel.

**Open questions:** The official 200-episode verdict and the cause of the
remaining task failures are unresolved. The evidence also does not establish
whether an untested intervention could improve the standing policy.

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

## 3e3387d5-4eae-4e5e-a34b-c8dfa83788e5 / Experiment 2

**Result:** The radius-coverage transfer intervention is not selected. The
experiment-1 checkpoint-100352 lineage remains the working and best-known
policy, the experiment-2 recipe is reverted, and no experiment-2 candidate is
retained.

**Observed behavior:** On the fresh disjoint research panel covering episodes
2400-2599, checkpoint-100352, checkpoint-105472, and checkpoint-120832 each
scored 191/200 (95.5%). The best-known baseline control also scored 191/200.
Each paired comparison had zero discordant episodes and zero net wins. The
same result held in every reported radius bin: 58/60 at 6-10 cm, 56/56 at
10-14 cm, 56/59 at 14-18 cm, and 21/25 at 18-20 cm. The transfer run's
training-success peak at checkpoint-105472 was 1.0, but it did not correspond
to better measured task success.

**Hypothesis assessment:** Weakened. Broadening the training target-radius
range did not improve aggregate reach-and-hold success, did not improve any
radius bin on this panel, and did not beat the matched baseline control.
Because this is one transfer run and one development panel, the result does
not rule out other radius-focused interventions or establish the official
benchmark result.

**Expected observation disposition:** contradicted - The expected improvement
to at least 196/200 without regression was not observed: all three transfer
checkpoints and the independent baseline control scored 191/200, with zero
paired discordance.

**Interpretation:** The intervention did not provide a useful improvement over
the retained policy under the tested conditions. The matched control shows
that the lower 95.5% score is shared panel behavior rather than evidence of a
transfer-specific degradation. The baseline remains a strong near-threshold
policy, but its development measurements do not establish the 98% official
objective.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/experiment-2/inventory.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-2-checkpoint-100352-200ep-seed2400-f48545f83637.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-2-checkpoint-105472-200ep-seed2400-f48545f83637.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-2-checkpoint-120832-200ep-seed2400-f48545f83637.json`;
`research/evaluations/3e3387d5-4eae-4e5e-a34b-c8dfa83788e5/evaluation-3e3387d5-4eae-4e5e-a34b-c8dfa83788e5-experiment-2-best_known-200ep-seed2400-f48545f83637.json`
