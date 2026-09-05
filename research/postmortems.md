# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Improve full-angle reach-and-hold reliability by addressing the
negative-angle failure sector identified in the first baseline, while keeping
the fixed evaluation and objective unchanged. Experiment 2 indicates that
focused training exposure alone is not a safe solution because its sector gain
came with large regressions elsewhere.

**Lessons and limits:** Experiment 1 reached 97.0% at checkpoint-100352, with
five of six failures never entering tolerance and concentrated between -122°
and -145°; this supports testing training exposure to that sector
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`).
The evidence is one training seed and does not establish whether the sector
problem is caused by sampling, policy capacity, or stochastic variation.
Experiment 2's focused-sampling checkpoint-100352 solved all 21 sampled
episodes in the -155 to -115 degree sector, but succeeded on only 149 of 179
episodes outside it and accumulated 576 hold interruptions; checkpoint-120832
fell to 18 of 21 in-sector and 137 of 179 outside-sector successes. The
uniformly evaluated champion remained at 15 of 21 in-sector and 179 of 179
outside-sector successes, for 97.0% overall versus 85.0% and 77.5% for the
focused checkpoints
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-100352-200ep-seed1-fb234ea119ba.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-120832-200ep-seed1-fb234ea119ba.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-champion-200ep-seed1-fb234ea119ba.json`).
This remains one fresh training seed, but the paired comparisons show a
substantial and consistent overall regression rather than a marginal
measurement fluctuation.

**Open questions:** Whether the negative-angle failures arise from policy
representation or control behavior, and whether hold instability is a
separate late-training effect rather than a consequence of sector exposure.

**Conditional next steps:** Do not increase the focused-sampling pressure.
Investigate representation or control behavior for the persistent difficult
sector, while treating hold stability as a separate mechanism; any future
intervention must preserve the strong non-focused behavior demonstrated by the
accepted lineage.

**Reconsider when:** A balanced intervention demonstrates a sector improvement
without the material outside-sector and hold-stability regressions seen here,
or when additional evidence shows that the apparent sector effect was
training-seed variation.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 1

**Result:** Fresh PPO baseline reached 97.0% on 200 development episodes, below the 98% objective threshold.
**Observed behavior:** Checkpoint-100352 had 6 failures, including five complete non-reaches concentrated at negative angles; checkpoint-86016 had 13 failures, while checkpoint-120832 fell to 96.5% with 245 hold interruptions.
**Interpretation:** The baseline learned effective reach-and-hold behavior, but late training did not reliably solve the difficult target sector or preserve the hold; checkpoint-100352 is the strongest measured lineage.
**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-86016-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-120832-200ep-seed1-f1f33f3d10a8.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 2

**Result:** Focused negative-angle training did not improve the uniformly
evaluated policy overall: its best measured checkpoint reached 85.0%, below the
97.0% accepted champion, and the later checkpoint reached 77.5%.

**Observed behavior:** At checkpoint-100352, all 21 evaluated targets in the
focused -155 to -115 degree sector succeeded, but only 149 of 179 targets
outside the sector succeeded; the run had 30 failures, 17 non-reaches and 576
hold interruptions. At checkpoint-120832, focused-sector success was 18/21 and
outside-sector success was 137/179, with 45 failures, 21 non-reaches and 393
hold interruptions. The champion had 15/21 focused-sector successes, 179/179
outside-sector successes and only one hold interruption.

**Interpretation:** Extra exposure can temporarily remove the targeted
non-reach failures, but this fresh run traded that local gain for severe
full-angle and hold-stability regressions. The intervention therefore does not
support continuing the focused-sampling code; the sector issue should be
treated as a representation, control, or seed-sensitive problem rather than
addressed by more of the same sampling pressure.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-100352-200ep-seed1-fb234ea119ba.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-120832-200ep-seed1-fb234ea119ba.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-champion-200ep-seed1-fb234ea119ba.json`.
