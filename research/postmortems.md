# Research postmortems

## Experiment 1

**Result:** The baseline reached 57% success on the 100-episode research panel at checkpoint-120832.

**Observed behavior:** The policy acquired and held the target in 57 episodes, but failed the required hold in 43 episodes; successful episodes typically terminated after roughly 109-119 steps.

**What was learned / do NOT retry:** Later training was the strongest measured baseline state, but it remains far from the 98% objective. The result does not justify retaining an unmeasured or lower-scoring checkpoint as an alternative lineage, and the unchanged baseline code remains the valid code lineage.
