# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Improve full-angle reach-and-hold reliability by addressing the
negative-angle failure sector identified in the first baseline, while keeping
the fixed evaluation and objective unchanged.

**Lessons and limits:** Experiment 1 reached 97.0% at checkpoint-100352, with
five of six failures never entering tolerance and concentrated between -122°
and -145°; this supports testing training exposure to that sector
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`).
The evidence is one training seed and does not establish whether the sector
problem is caused by sampling, policy capacity, or stochastic variation.

**Open questions:** Whether targeted angular exposure improves the difficult
sector without reducing reliability elsewhere, and whether the isolated hold
interruptions seen at checkpoint-120832 are a separate late-training effect.

**Conditional next steps:** If experiment 2 reduces negative-sector non-reaches
while preserving other angles, measure its best checkpoint against the accepted
baseline. If those failures persist, investigate representation or control
behavior rather than increasing sampling pressure; if hold interruptions remain
the dominant failures, test a separate hold-stability intervention.

**Reconsider when:** A comparable trained policy still fails predominantly in
the same sector despite focused exposure, or focused exposure causes material
regressions outside that sector.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 1

**Result:** Fresh PPO baseline reached 97.0% on 200 development episodes, below the 98% objective threshold.
**Observed behavior:** Checkpoint-100352 had 6 failures, including five complete non-reaches concentrated at negative angles; checkpoint-86016 had 13 failures, while checkpoint-120832 fell to 96.5% with 245 hold interruptions.
**Interpretation:** The baseline learned effective reach-and-hold behavior, but late training did not reliably solve the difficult target sector or preserve the hold; checkpoint-100352 is the strongest measured lineage.
**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-86016-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-120832-200ep-seed1-f1f33f3d10a8.json`.
