# Research postmortems

## Experiment 1

**Result:** Fresh PPO baseline reached 0.0% held-out task success across all measured checkpoints.

**Observed behavior:** The policy almost never entered the 1 cm tolerance and never completed the 100-step hold; best target-entry rate was 4.0% at checkpoint-60416.

**What was learned / do NOT retry:** The unchanged baseline learns limited approach behavior but does not solve reaching or holding; later checkpoints did not improve completion, so do not treat additional unchanged baseline checkpoints as a solved lineage.
