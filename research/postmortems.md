# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Test whether the baseline's localized negative-angle blind spot is caused by insufficient exposure during training. Experiment 2 will transfer the selected 97.0% checkpoint and oversample the observed -150 to -110 degree sector while retaining uniform full-angle samples and the existing far-target radius range.

**Lessons and limits:** Experiment 1 selected `checkpoint-100352` at 97.0%, with all six failures in the -122 to -145 degree sector; five never reached tolerance and one reached it only briefly. The later `checkpoint-120832` also showed a hold-stability regression. These observations come from one 200-episode, seed-1 development panel, so they identify a targeted failure mode but do not establish reproducibility or causality.

**Open questions:** Whether targeted angular exposure improves the negative-angle reach failures without reducing positive-sector performance or hold stability; whether the remaining failures are instead caused by dynamics, control, or representation limits; and whether the selected transfer lineage is more effective than relearning from scratch.

**Conditional next steps:** If the targeted transfer removes the negative-sector failures and preserves broad performance, measure its best checkpoint across comparable panels and consider replication. If the wedge remains unsolved, inspect control/representation causes rather than further narrowing the sampling distribution. If overall or hold performance regresses, revert the intervention and test a less distribution-specific method or replication.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 1

**Result:** Fresh PPO baseline reached 97.0% on 200 development episodes, below the 98% objective threshold.
**Observed behavior:** Checkpoint-100352 had 6 failures, including five complete non-reaches concentrated at negative angles; checkpoint-86016 had 13 failures, while checkpoint-120832 fell to 96.5% with 245 hold interruptions.
**Interpretation:** The baseline learned effective reach-and-hold behavior, but late training did not reliably solve the difficult target sector or preserve the hold; checkpoint-100352 is the strongest measured lineage.
**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-86016-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-120832-200ep-seed1-f1f33f3d10a8.json`.
