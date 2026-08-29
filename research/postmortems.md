# Research postmortems

## Experiment 1

**Result:** Fresh PPO reached 57% success at checkpoint-120832, only marginally above 56% at checkpoint-110592 and well below the 98% objective.

**Observed behavior:** The policy usually held once it entered tolerance, but failed mainly on 15-20 cm targets (37 failures at both late checkpoints); entry was about 59-63% and hold failures were rare.

**What was learned / do NOT retry:** The baseline's limiting behavior is long-range reach/generalization, not hold stability. Do not retry the unchanged baseline or select an earlier checkpoint as an improvement; retain the baseline code lineage for interpreting future changes.
