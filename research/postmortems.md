# Research postmortems

## Experiment 1

**Result:** The baseline reached 57% success on the 100-episode research panel at checkpoint-120832.

**Observed behavior:** The policy acquired and held the target in 57 episodes, but failed the required hold in 43 episodes; successful episodes typically terminated after roughly 109-119 steps.

**What was learned / do NOT retry:** Later training was the strongest measured baseline state, but it remains far from the 98% objective. The result does not justify retaining an unmeasured or lower-scoring checkpoint as an alternative lineage, and the unchanged baseline code remains the valid code lineage.

## Experiment 2

**Result:** Continuing the unchanged accepted PPO method did not materially improve performance; the best measured checkpoints reached 58% success versus 57% for the champion.

**Observed behavior:** `checkpoint-25600` and `checkpoint-95232` each succeeded on 58/100 matched episodes, while the later `checkpoint-120832` returned to 57%. Failures remained dominated by episodes that never completed the 100-step hold.

**What was learned / do NOT retry:** More unchanged training is not supported as a useful convergence explanation at this budget. Select the later tied-best measured checkpoint, keep the unchanged code lineage, and do not retain an unmeasured or redundant alternative.
