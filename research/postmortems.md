# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Improve full-angle reach-and-hold reliability by addressing the
negative-angle failure sector identified in the first baseline, while first
separating training-seed variation from representation and control effects.
The fixed evaluation and objective remain unchanged.

**Lessons and limits:** Experiment 1 reached 97.0% at checkpoint-100352, with
five of six failures never entering tolerance and concentrated between -122°
and -145°; this supports investigating that sector
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-1-checkpoint-100352-200ep-seed1-f1f33f3d10a8.json`).
The evidence is one training seed and does not establish whether the sector
problem is caused by sampling, policy capacity, control behavior, or
stochastic variation. Experiment 2's focused-sampling checkpoint-100352
solved all 21 evaluated sector episodes but succeeded on only 149 of 179
outside-sector episodes and accumulated 576 hold interruptions; its later
checkpoint fell to 18 of 21 in-sector and 137 of 179 outside-sector successes.
The accepted champion remained at 15 of 21 in-sector and 179 of 179
outside-sector successes, for 97.0% overall versus 85.0% and 77.5%
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-100352-200ep-seed1-fb234ea119ba.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-checkpoint-120832-200ep-seed1-fb234ea119ba.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-2-champion-200ep-seed1-fb234ea119ba.json`).
Experiment 3's added target radius and sine/cosine angle features also
regressed: checkpoint-100352 reached 157 of 200 successes, including 7 of 21
in-sector and 150 of 179 outside-sector, while checkpoint-120832 reached 166
of 200, including 8 of 21 in-sector and 158 of 179 outside-sector. The later
checkpoint accumulated 97 hold interruptions, mostly outside the difficult
sector, versus one for the accepted champion. These are single fresh training
seeds, so they do not isolate the underlying cause. Experiment 4's unchanged
fresh baseline replication was much worse: 59 of 200 at checkpoint-100352 and
89 of 200 at checkpoint-120832, versus 194 of 200 for the champion. Its
checkpoint-100352 failures included 136 non-reaches and 252 hold interruptions,
while the later checkpoint still had 110 non-reaches. This large difference
across baseline training seeds establishes substantial stochastic variation in
the learned outcome, although it does not explain the source of that variation
or establish that either tested intervention is beneficial
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-checkpoint-100352-200ep-seed1-da55aa2016a5.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-checkpoint-120832-200ep-seed1-da55aa2016a5.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-champion-200ep-seed1-da55aa2016a5.json`).

**Open questions:** Whether the champion's strong full-angle behavior is
reproducible, and whether the negative-angle failures arise from control
behavior, policy capacity, or training-seed variation, remain unresolved. It is
also uncertain whether late hold instability is a separate mechanism from
sector performance.

**Conditional next steps:** Keep the accepted lineage and do not promote the
experiment 4 replication or continue either the focused-sampling or tested
target-feature intervention on the present evidence. Further work should
distinguish representation, control, and stochastic effects using the accepted
lineage as the behavioral control and should preserve its full-angle and hold
behavior.

**Reconsider when:** A fresh baseline reliably reproduces the champion, or a
balanced intervention shows a reliable sector improvement without material
outside-sector or hold-stability regression. Evidence that characterizes the
seed-dependent outcomes sufficiently to separate them from intervention
effects would also justify revising the current interpretation.

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

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 3

**Result:** Explicit target-radius and sine/cosine target-angle features did
not improve reach-and-hold reliability; both measured checkpoints were well
below the accepted champion's 97.0%.

**Observed behavior:** Checkpoint-100352 succeeded on 157 of 200 episodes
(78.5%), with 24 non-reaches and 38 hold interruptions. In the difficult
-155 to -115 degree sector it succeeded on 7 of 21 episodes; outside the
sector it succeeded on 150 of 179 and recorded 36 hold interruptions.
Checkpoint-120832 improved to 166 of 200 (83.0%) but still succeeded on only
8 of 21 sector episodes and 158 of 179 outside-sector episodes, with 97 hold
interruptions overall, including 95 outside the sector. The accepted
champion succeeded on 194 of 200 (97.0%), including 15 of 21 sector and
179 of 179 outside-sector episodes, with one hold interruption.

**Interpretation:** The added target geometry did not address the persistent
negative-angle failures and introduced broad reach and hold regressions in
this fresh run. The evidence supports reverting the representation change and
retaining the accepted champion, while the single fresh seed leaves
representation-versus-stochastic causality unresolved.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-3-checkpoint-100352-200ep-seed1-9233771c95e7.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-3-checkpoint-120832-200ep-seed1-9233771c95e7.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-3-champion-200ep-seed1-9233771c95e7.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 4

**Result:** The fresh unchanged PPO replication did not reproduce the accepted
baseline: checkpoint-100352 reached 29.5% (59/200), and checkpoint-120832
reached 44.5% (89/200), versus 97.0% (194/200) for the champion.

**Observed behavior:** At checkpoint-100352, 136 episodes never reached
tolerance and the run accumulated 252 hold interruptions; success was 7/21 in
the -155 to -115 degree sector and 52/179 outside it. At checkpoint-120832,
110 episodes never reached tolerance, with 7 hold interruptions; success was
8/21 in-sector and 81/179 outside-sector. The champion had 5 non-reaches and
one hold interruption, with 15/21 in-sector and 179/179 outside-sector
successes.

**Interpretation:** The unchanged baseline outcome is strongly
training-seed-sensitive: the fresh replication failed broadly, not only in the
previously identified negative-angle sector. This makes stochastic variation a
major unresolved explanation for the regressions in experiments 2 and 3, so
those single-seed results cannot by themselves attribute all degradation to
their interventions. The replication is nevertheless not a viable candidate
and provides no basis to replace the accepted champion.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-4-champion-200ep-seed1-da55aa2016a5.json`.
