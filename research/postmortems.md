# Research postmortems

## Experiment 1

**Result:** Fresh PPO reached 57% success at checkpoint-120832, only marginally above 56% at checkpoint-110592 and well below the 98% objective.

**Observed behavior:** The policy usually held once it entered tolerance, but failed mainly on 15-20 cm targets (37 failures at both late checkpoints); entry was about 59-63% and hold failures were rare.

**What was learned / do NOT retry:** The baseline's limiting behavior is long-range reach/generalization, not hold stability. Do not retry the unchanged baseline or select an earlier checkpoint as an improvement; retain the baseline code lineage for interpreting future changes.

## Experiment 2

**Result:** Increasing `CLOSENESS_LENGTH_SCALE` from 0.05 to 0.1 improved measured success from 61.0% for the champion to 64.5%, but remained far below the 98% objective.

**Observed behavior:** Target entry improved to 76.5%, while completed holds reached 64.5%; failures remained dominated by 15-20 cm targets (66 failures) rather than hold instability.

**What was learned / do NOT retry:** A broader exponential approach gradient is useful for long-range entry, but does not solve long-range reach/generalization. Keep this configuration lineage for attribution; do not treat the modest single-seed gain as goal completion or automatically retry the same numeric change.
