# Research postmortems

## Experiment 3

**Result:** Fresh PPO baseline reached 0.00% held-out research success across the measured checkpoints.

**Observed behavior:** The best measured checkpoint, `checkpoint-60416`, entered the 1 cm target band in 4% of episodes but completed 0/100 hold steps; other measured checkpoints never entered the band.

**What was learned / do NOT retry:** The baseline PPO lineage does not yet produce reliable reaching, and hold stability cannot be assessed until reaching improves; do not treat later checkpoints or reward improvement as evidence of task success.

## Experiment 4

**Result:** The transferred reach-shaping change produced 0.00% held-out research success.

**Observed behavior:** `checkpoint-120832` entered the 1 cm band in 4% of episodes and averaged 0.6 consecutive hold steps; the champion entered in 0% and averaged 0.1 steps.

**What was learned / do NOT retry:** The larger closeness scale gave only a small, non-task-level reaching signal and no completed holds; do not treat this numeric reach-shaping variant as a reliable improvement.
