# Research postmortems

## Experiment 5

**Result:** Fresh PPO reached 57% held-out success at checkpoint-120832, the best measured checkpoint.

**Observed behavior:** The policy entered the target region in about 59%, but failed holds had median and upper-quantile progress of 0/100; failures were concentrated at 15-20 cm with no material left/right asymmetry.

**What was learned / do NOT retry:** Training improved reach acquisition but not sustained 100-step holding, and later checkpoints did not materially improve the measured result. Do not treat this baseline as meeting the objective or retry unchanged baseline search as the next intervention.
