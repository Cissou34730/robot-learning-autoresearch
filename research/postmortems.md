# Research postmortems

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Scientific strategy

**Direction:** Treat the accepted champion as the active behavioral control while
separating training-seed variability from intervention effects in full-angle
reach-and-hold. Fresh replications establish that PPO outcomes vary widely, and
experiments 7 through 11 provide no basis to replace the champion with the
tested reward intervention or another fresh baseline.

**Lessons and limits:** Experiment 1 reached 97.0% at checkpoint-100352, while
the seven unchanged fresh replications reached 29.5%, 75.5%, 24.0%, 11.0%,
78.0%, 15.5% and 34.0% at that checkpoint (experiments 4, 5, 6, 8, 9, 10 and
11); experiments 10 and 11 rose only to 25.5% and 33.0%, respectively, at
checkpoint-120832. None reproduces the accepted 97.0% outcome, so the spread
supports substantial training-seed variation but does not identify its cause.
Experiment 11 failed broadly: it had 4/21 sector and 64/179 outside-sector
successes at checkpoint-100352, with 115 non-reaches and 345 hold
interruptions, then 4/21 and 62/179 successes at checkpoint-120832, with 114
non-reaches and 664 hold interruptions. Together with experiment 10's broad
failure, experiment 9's distinct late hold instability and experiment 8's broad
failure, this indicates that reach and hold reliability can vary independently
across training and checkpoint. Experiment 7's transfer with
`HOLD_EXIT_FORFEIT_FRACTION=0.5` reached 84.0% at checkpoint-100352 and 82.5%
at checkpoint-120832, with 1,226 and 987 hold interruptions, respectively,
versus the champion's 97.0% and one interruption. The evidence does not
establish the cause of seed variation, but it does not support that reward
intervention.
(`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-5-checkpoint-100352-200ep-seed1-da55aa2016a5.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-5-checkpoint-120832-200ep-seed1-da55aa2016a5.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-6-checkpoint-100352-200ep-seed1-da55aa2016a5.json`,
`research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-6-checkpoint-120832-200ep-seed1-da55aa2016a5.json`).

**Open questions:** What training-process factors produce the large
seed-dependent spread, whether the champion's strong full-angle behavior is
reproducible at or above the objective threshold, and whether the negative-angle
failures arise from control behavior, policy capacity, or stochastic variation
remain unresolved. It is also unknown whether checkpoint selection can
reliably avoid late hold instability.

**Conditional next steps:** Keep the accepted champion as the active lineage.
If research resumes, use seed-controlled comparisons of non-reach and
hold-interruption behavior rather than continuing the tested 0.5 hold-exit
forfeiture setting or attributing the remaining failures to that mechanism.

**Reconsider when:** Independent fresh runs reliably reproduce the champion, or
a balanced intervention shows a repeatable sector improvement without material
outside-sector or hold-stability regression. Evidence that characterizes the
seed-dependent outcomes sufficiently to separate them from intervention effects
or an official result above the objective threshold would also justify revising
the current interpretation. Experiment 9's relatively strong but still
sub-champion seed would warrant reconsideration only if comparable runs also
reduce its outside-sector failures and hold interruptions.

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

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 5

**Result:** The unchanged fresh PPO replication remained below the accepted
champion: checkpoint-100352 reached 75.5% (151/200), and checkpoint-120832
reached 74.0% (148/200), versus 97.0% (194/200) for the champion.

**Observed behavior:** At checkpoint-100352, success was 7/21 in the difficult
negative-angle sector and 144/179 outside it, with 49 non-reaches and no hold
interruptions. At checkpoint-120832, success was 7/21 in-sector and 141/179
outside-sector, with 36 non-reaches and 404 hold interruptions; all measured
hold interruptions were outside the sector. The champion had 15/21 in-sector
and 179/179 outside-sector successes, 5 non-reaches and one hold interruption.

**Interpretation:** This second unchanged replication supports the conclusion
that fresh PPO training is strongly seed-sensitive: seed 2 was substantially
better than experiment 4 but still did not reproduce the accepted lineage.
The late increase in hold interruptions, despite fewer non-reaches, suggests
that reach and hold reliability can vary independently during training. The
result does not identify the source of the stochastic variation or justify
promoting this candidate.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-5-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-5-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-5-champion-200ep-seed1-da55aa2016a5.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 6

**Result:** The third unchanged fresh PPO replication remained far below the
accepted champion: checkpoint-100352 reached 24.0% (48/200), and
checkpoint-120832 reached 25.5% (51/200), versus 97.0% (194/200) for the
champion.

**Observed behavior:** At checkpoint-100352, success was 2/21 in the
difficult negative-angle sector and 46/179 outside it, with 119 non-reaches
and 383 hold interruptions. At checkpoint-120832, success was 4/21 in-sector
and 47/179 outside-sector, with 103 non-reaches and 155 hold interruptions.
The champion comparison had 15/21 in-sector and 179/179 outside-sector
successes, 5 non-reaches and one hold interruption.

**Interpretation:** The third fresh unchanged run again failed to reproduce the
accepted lineage and failed broadly across the angular range, strengthening
the conclusion that fresh PPO outcomes are strongly seed-sensitive. The
checkpoint change also altered both non-reach and hold-interruption counts
without approaching champion reliability, so this candidate is not a viable
replacement and the result does not identify the source of the stochastic
variation.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-6-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-6-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-6-champion-200ep-seed1-da55aa2016a5.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 7

**Result:** The transferred hold-exit reward intervention remained below the
accepted champion: checkpoint-100352 reached 84.0% (168/200), checkpoint-120832
reached 82.5% (165/200), and the champion reached 97.0% (194/200).

**Observed behavior:** At checkpoint-100352, the candidate had 15 non-reaches
and 1,226 hold interruptions, with 10/21 successes in the difficult
negative-angle sector and 158/179 outside it. At checkpoint-120832, it had 14
non-reaches and 987 hold interruptions, with 11/21 sector successes and 154/179
outside-sector successes. The champion had 5 non-reaches, one hold interruption,
15/21 sector successes and 179/179 outside-sector successes.

**Interpretation:** Partially forfeiting accumulated hold-progress reward on an
exit did not reduce hold interruptions and substantially degraded both full-angle
success and sector performance in this transferred run. The intervention is not
a viable replacement for the accepted lineage; the evidence supports reverting
the reward change while leaving the broader source of training variability
unresolved.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-7-checkpoint-100352-200ep-seed1-91e28f1ae7b8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-7-checkpoint-120832-200ep-seed1-91e28f1ae7b8.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-7-champion-200ep-seed1-91e28f1ae7b8.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 8

**Result:** The fourth unchanged fresh PPO replication failed to reproduce the
accepted champion: checkpoint-100352 reached 11.0% (22/200), checkpoint-120832
reached 8.5% (17/200), and the champion reached 97.0% (194/200).

**Observed behavior:** At checkpoint-100352, the candidate succeeded on 0/21
targets in the difficult negative-angle sector and 22/179 outside it, with 171
non-reaches and 235 hold interruptions. At checkpoint-120832, it succeeded on
3/21 in-sector and 14/179 outside-sector targets, with 183 non-reaches and one
hold interruption. The champion comparison had 15/21 in-sector and 179/179
outside-sector successes, five non-reaches and one hold interruption.

**Interpretation:** This replication failed broadly across the angular range and
further supports strong seed-dependent PPO outcomes rather than isolating a
specific sector mechanism. The change from many hold interruptions to almost
none while non-reaches increased between checkpoints shows that checkpoint
behavior can vary within one run, but does not identify the training cause.
The candidate is not a viable replacement; the unchanged code is retained and
the accepted champion remains active.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-8-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-8-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-8-champion-200ep-seed1-da55aa2016a5.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 9

**Result:** The fifth unchanged fresh PPO replication remained below the
accepted champion: checkpoint-100352 reached 78.0% (156/200), checkpoint-120832
reached 72.5% (145/200), and the champion reached 97.0% (194/200).

**Observed behavior:** At checkpoint-100352, the candidate succeeded on 17/21
targets in the difficult negative-angle sector and 139/179 outside it, with 27
non-reaches and 611 hold interruptions. At checkpoint-120832, it succeeded on
14/21 in-sector and 131/179 outside-sector targets, with 37 non-reaches and 468
hold interruptions. The champion comparison had 15/21 in-sector and 179/179
outside-sector successes, five non-reaches and one hold interruption. The
paired comparisons favored the champion by 19.0 and 24.5 percentage points at
the two checkpoints.

**Interpretation:** This fresh run was substantially better than experiments 4,
6 and 8 at checkpoint-100352, but it still failed broadly outside the difficult
sector and had far more hold interruptions than the champion. Its late decline
and change in the balance of non-reaches versus hold interruptions further
support seed- and checkpoint-dependent reach-and-hold behavior without
identifying the training cause. The candidate is not a viable replacement; the
unchanged code remains appropriate and the accepted champion stays active.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-9-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-9-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-9-champion-200ep-seed1-da55aa2016a5.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 10

**Result:** The sixth unchanged fresh PPO replication did not reproduce the
accepted champion: checkpoint-100352 reached 15.5% (31/200), checkpoint-120832
reached 25.5% (51/200), and the champion reached 97.0% (194/200).

**Observed behavior:** At checkpoint-100352, the candidate succeeded on 3/21
targets in the difficult negative-angle sector and 28/179 outside it, with 166
non-reaches and 97 hold interruptions. At checkpoint-120832, it succeeded on
4/21 in-sector and 47/179 outside-sector targets, with 147 non-reaches and 8
hold interruptions. The champion comparison had 15/21 in-sector and 179/179
outside-sector successes, five non-reaches and one hold interruption.

**Interpretation:** This sixth unchanged fresh run failed broadly across the
angular range and remains far below the accepted lineage at both checkpoints.
The reduction in non-reaches and hold interruptions at the later checkpoint did
not approach champion reliability, so the result strengthens the evidence for
large seed- and checkpoint-dependent PPO variation without identifying its
cause. The candidate is not a viable replacement; the unchanged code remains
appropriate and the accepted champion stays active.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-10-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-10-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-10-champion-200ep-seed1-da55aa2016a5.json`.

## 90890200-b313-4f38-b010-de1eaaeb3d98 / Experiment 11

**Result:** The seventh unchanged fresh PPO replication did not reproduce the
accepted champion: checkpoint-100352 reached 34.0% (68/200), checkpoint-120832
reached 33.0% (66/200), and the champion reached 97.0% (194/200).

**Observed behavior:** At checkpoint-100352, the candidate succeeded on 4/21
targets in the difficult negative-angle sector and 64/179 outside it, with 115
non-reaches and 345 hold interruptions. At checkpoint-120832, it succeeded on
4/21 in-sector and 62/179 outside-sector targets, with 114 non-reaches and 664
hold interruptions. The champion comparison had 15/21 in-sector and 179/179
outside-sector successes, five non-reaches and one hold interruption.

**Interpretation:** This fresh run failed broadly across the angular range and
remained far below the accepted lineage at both checkpoints. The nearly
unchanged non-reach count alongside the late increase in hold interruptions
shows that checkpoint behavior can change the balance of failure modes without
approaching champion reliability. This strengthens the evidence for large
seed- and checkpoint-dependent PPO variation but does not identify its cause.
The candidate is not a viable replacement; the unchanged code remains
appropriate and the accepted champion stays active.

**Evidence inspected:** `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-11-checkpoint-100352-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-11-checkpoint-120832-200ep-seed1-da55aa2016a5.json`, `research/evaluations/90890200-b313-4f38-b010-de1eaaeb3d98/evaluation-90890200-b313-4f38-b010-de1eaaeb3d98-experiment-11-champion-200ep-seed1-da55aa2016a5.json`.
