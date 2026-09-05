# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 1

**Result:** Fresh PPO baseline reached 97.0% on 200 development episodes, below the 98% objective threshold.
**Observed behavior:** Checkpoint-100352 had 6 failures, including five complete non-reaches concentrated at negative angles; checkpoint-86016 had 13 failures, while checkpoint-120832 fell to 96.5% with 245 hold interruptions.
**Interpretation:** The baseline learned effective reach-and-hold behavior, but late training did not reliably solve the difficult target sector or preserve the hold; checkpoint-100352 is the strongest measured lineage.
**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-86016-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-120832-200ep-seed1-f1f33f3d10a8.json`.
