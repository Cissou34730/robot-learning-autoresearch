# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Determine whether the baseline's localized negative-angle blind spot is an exposure problem or a control/representation limitation. The targeted-exposure transfer in Experiment 2 did not resolve the wedge and introduced broad stability degradation, so the next useful intervention should not further narrow the training distribution.

**Lessons and limits:** Experiment 1 selected `checkpoint-100352` at 97.0%, with all six failures in the -122 to -145 degree sector; five never reached tolerance and one reached it only briefly. Experiment 2 retained the same six non-reaching episodes at 10,240, 20,480 and 90,112 steps despite 50% oversampling of the surrounding negative-angle sector, while success fell to 94.5% and 92.5% and hold interruptions increased from 38 to 278 and 312. This rejects insufficient angular exposure as a sufficient explanation for this transfer run, but the evidence remains one development panel and one stochastic training realization.

**Open questions:** Whether the persistent wedge is caused by control or observation representation limits, and whether the late hold regression is intrinsic to the unchanged method or stochastic. It remains unknown whether an unmodified replication would reproduce the baseline's 97.0% result.

**Conditional next steps:** After closure, inspect control/representation causes or run a fresh unchanged-method replication to distinguish method effects from initialization variance. Do not further narrow angular sampling; any continued training should first address the hold-stability regression and be judged against the restored baseline.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 1

**Result:** Fresh PPO baseline reached 97.0% on 200 development episodes, below the 98% objective threshold.
**Observed behavior:** Checkpoint-100352 had 6 failures, including five complete non-reaches concentrated at negative angles; checkpoint-86016 had 13 failures, while checkpoint-120832 fell to 96.5% with 245 hold interruptions.
**Interpretation:** The baseline learned effective reach-and-hold behavior, but late training did not reliably solve the difficult target sector or preserve the hold; checkpoint-100352 is the strongest measured lineage.
**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-86016-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-120832-200ep-seed1-f1f33f3d10a8.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 2

**Result:** The targeted angular-coverage transfer did not improve the measured policy and is closed without retaining its code or checkpoints.

**Observed behavior:** On the comparable 200-episode, seed-1 research panel, checkpoint-10240 scored 97.0%, checkpoint-20480 scored 94.5%, and checkpoint-90112 scored 92.5%. The same six negative-angle non-reaches persisted across all three measured checkpoints; later checkpoints added failures across other angles and showed worsening hold stability. Raw training success declined from 0.94 at 10,240 steps to 0.81 at 120,832 steps.

**Interpretation:** Oversampling the observed negative-angle sector was insufficient to remove the localized reach limitation and was associated with broad degradation during continued transfer training. The result supports reverting the intervention and investigating control/representation causes or replication rather than applying more distribution-specific oversampling. It does not establish whether the degradation is causal beyond this training realization.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-10240-200ep-seed1-c77f54f42212.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-20480-200ep-seed1-c77f54f42212.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-90112-200ep-seed1-c77f54f42212.json`, `research/checkpoints/challengers/90890200-b313-4f38-b010-de1eaaeb3d98/experiment-2/inventory.json`.
