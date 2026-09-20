# Research postmortems

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Scientific strategy

**Current synthesis:** The campaign objective remains at least 98% success,
or 196/200 episodes, on the official 6-20 cm reach-and-hold distribution. The
fresh PPO baseline learned substantial task behavior: checkpoint-100352 achieved
150/160 and 151/160 on two disjoint panels (301/320 pooled, 94.06%), and the
unchanged working lineage achieved 155/160 (96.88%) on the latest panel. The
full-radius and angle-balanced training-support changes did not improve the
transferred parent. The fresh periodic-observation and fresh unchanged-baseline
runs learned slowly enough to provide no measured replacement policy. The
current reward combines distance and step costs with a one-time terminal bonus;
the measured failures are truncated episodes, including failures with long
partial holds. Measured task outcome, rather than training proxy success or
checkpoint position, remains the strongest evidence of policy usefulness. The
best development evidence is below the objective and is not an official verdict.

**Lessons and limits:** Available baseline failures are concentrated in the
-180 to -90 degree target sector, with many also inside 14 cm, but neither
tested support intervention removed that pattern. The angle-balanced challengers
added failures outside the intended sector. Later checkpoints on the baseline
trajectory regressed from the selected 100352-step policy, so proxy peaks and
recovery do not identify a useful saved policy. These results weaken the tested
support recipes and fresh periodic recipe under their tested conditions; they
do not disprove other reward, control, schedule, curriculum, or representation
treatments. The measured parent uses the same 11-dimensional observation and
physical action mapping throughout the current lineage. Unmeasured checkpoints
remain unmeasured, and independent development panels remain distinct from the
official assessment.

**Open questions:** It remains uncertain whether explicit reward credit for
maintaining target tolerance can reduce the residual truncated failures without
disrupting the learned reach behavior. It is also unknown whether a different
control, reward, schedule, curriculum, or representation treatment can close
the remaining gap, whether the periodic representation could help when trained
adequately, and how much fresh-seed variability reflects the learning process.
The transfer value of learned outer-radius behavior and the official result of
the best development policy remain unknown. These questions record uncertainty
and do not prescribe an experiment order.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 1

**Result:** The baseline produced a useful learned policy but did not yet
demonstrate the human objective. Checkpoint-100352 is selected as the working
and best-known policy for the next experiment.

**Observed behavior:** Training-time success increased from 0.00 at early
checkpoints to 0.86 at checkpoint-95232 and 0.91 at checkpoint-100352, while
training reward improved from -440.877 at 5120 steps to -4.767 at 100352
steps. The best recorded training reward was -4.658 at checkpoint-105472, then
the proxies fluctuated: training success was 0.90 at 110592, 0.89 at 115712,
and 0.91 at 120832. On research episodes, checkpoint-100352 achieved 150/160
(93.75%) on seeds 4200-4359 and 151/160 (94.375%) on disjoint seeds
4360-4519. Checkpoint-105472 achieved 148/160 and 149/160; checkpoint-110592
achieved 146/160; and checkpoint-120832 achieved 134/160 (83.75%) on the first
panel. Paired comparisons favored checkpoint-100352 over checkpoint-105472 by
4-0 discordant outcomes across 320 shared episodes, and over checkpoint-110592
by 5-0 on the second panel. Every recorded failure used all 500 control steps
and was truncated rather than successfully completing the hold.

**Hypothesis assessment:** The automatic baseline hypothesis was to establish
an initial baseline, so it supplied no type-specific confirmatory or diagnostic
prediction to test. It is supported as a baseline characterization and
partially supports progress toward the objective: the learned policy reaches
approximately 94% on two disjoint development panels. The evidence weakens any
assumption that the final checkpoint or training proxies identify the best
policy. It does not establish the 98% objective or explain why later training
regressed.

**Interpretation:** Checkpoint-100352 is the best available measured artifact
and its result is reproducible across the two independent research panels, so
it is the appropriate lineage for continued development. The evidence is
strong enough to close this baseline without another measurement round, but
not to request the terminal benchmark. Selecting this policy does not imply
that the baseline recipe caused the observed peak or that its development
success will equal the official result.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-1/inventory.json`;
and the six artifacts under
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/` for checkpoints
100352, 105472, 110592, and 120832 on seeds 4200 and 4360.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 2

**Result:** Expanding the training target-radius support to the official 6-20 cm
range produced a useful but not improved policy checkpoint, so the experiment's
scientific recipe is reverted to the parent and the existing baseline remains
working and best-known. The campaign objective is not demonstrated.

**Observed behavior:** The training trace improved from 0.75 success and -8.94
reward at 1,024 steps to a proxy peak of 0.99 and -2.70 at 30,720 steps. The
proxy then degraded through 0.83 success and -9.55 reward at 90,112 steps before
recovering to 0.96 and -6.11 at 115,712; it ended at 0.92 and -7.47 at 120,832.
On research panel 4520, checkpoint-30720 achieved 154/160 (96.25%) versus the
parent's 155/160 (96.875%); the challenger had the parent's five failed episode
identities plus episode 4527. On disjoint panel 4680, both achieved 150/160
(93.75%); eight failed episode identities were shared, while each policy had two
panel-specific failures. The paired comparisons therefore favored the parent by
one discordant episode on panel 4520 and by one net episode across both panels.
The later proxy-recovery checkpoint-115712 achieved only 61.25% (98/160), with
62 failures, so proxy recovery did not indicate useful saved-policy behavior.
The measured failures in these artifacts were truncated at 500 steps. The
research-evaluation records contain success, reward and step outcomes but no
target geometry, so this round does not directly establish whether inner-radius
or negative-angle rates changed.

**Hypothesis assessment:** The radius-support proposition is weakened under the
tested transferred recipe. The early proxy peak produced near-parent measured
performance on two disjoint panels, but did not improve pooled success or
systematically remove residual failures, and the later proxy recovery was
strongly contradicted by its poor measurement. This is evidence against the
usefulness of this intervention and training trajectory for the present
decision, not a causal disproof of every possible radius curriculum or a claim
that the parent would meet the official 98% criterion.

**Interpretation:** The parent is the safer working policy because it matches or
slightly exceeds the changed recipe on comparable independent development panels
and remains the strongest measured lineage. The early checkpoint is not retained:
its measured behavior is comparable rather than superior, while its recipe did
not resolve the residual problem. The large gap between training proxies and
saved-policy measurements reinforces that checkpoint selection must use measured
task success; neither development evidence nor the training log is an official
verdict.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-2/inventory.json`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-2-attempt-1.log`;
and the five experiment-2 artifacts under
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/` for checkpoint-30720,
checkpoint-115712 and `working` on seeds 4520 and 4680.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 3

**Result:** Equalizing training exposure to the negative-angle sector did not
improve the transferred parent on the fresh development panel. The changed
recipe is reverted, and the existing `working` and `best_known` lineage is
preserved. The campaign objective remains not demonstrated by development
measurements.

**Observed behavior:** The training proxy peaked early at 0.968 success and
-3.74 reward at checkpoint-5120, was 0.95 and -4.63 at checkpoint-25600, then
declined to 0.90 and -8.88 at checkpoint-90112 before a partial endpoint
recovery to 0.92 and -8.51 at checkpoint-120832. On the disjoint research panel
with seed 4840, checkpoint-5120 achieved 152/160 (95.00%), checkpoint-25600
achieved 149/160 (93.125%), and the unchanged parent achieved 155/160
(96.875%). Paired comparisons favored the parent by 3 and 6 discordant
episodes, with neither challenger winning a discordant episode. The parent had
3 failures in the -180 to -90 degree sector and 2 in the complementary sector;
the challengers had 4/4 and 4/7 respectively. Failure diagnostics also showed
inner-radius failures for the parent and both challengers, so the angle
intervention did not isolate the residual to its intended sector.

**Hypothesis assessment:** The diagnostic hypothesis is weakened under the tested
transferred recipe. The measured challengers did not reduce negative-sector
failures or improve pooled task success, and they introduced additional
complementary-sector failures on the shared panel, matching the proposal's
contradicting observation. The result is evidence against this equal-exposure
intervention and trajectory, not a causal disproof of all angular curricula or
of representation and control explanations.

**Interpretation:** The fresh-panel comparison is directly relevant and
comparable because all three policies used the same research-evaluation context
and episode panel; the parent also has prior disjoint-panel evidence. The early
training-proxy peaks did not translate into saved-policy task gains, reinforcing
that measured reach-and-hold success should select the lineage. The parent is
therefore the safer working policy, but its 96.875% result is still below the
98% objective and is development evidence rather than an official verdict.
Unmeasured experiment-3 checkpoints remain unmeasured and do not count as
failures.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-3-attempt-1.log`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-3/inventory.json`;
`robot_learning/scenario/training_environment.py`; and the three experiment-3
artifacts under
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/` for checkpoint-5120,
checkpoint-25600 and `working` on seed 4840.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 4

**Result:** The fresh periodic target-angle representation did not produce a
candidate supported for continued use. The experiment is closed by restoring
the measured `working` lineage and reverting the 13-dimensional observation
recipe. The campaign objective remains unproven.

**Observed behavior:** The run completed 120,832 steps from fresh
initialization and produced 24 checkpoints. Training success was 0.00 through
90,112 steps, then 0.01 at 95,232 and 100,352, 0.02 at 105,472, 0.05 at
110,592, 0.12 at 115,712, and 0.17 at 120,832. Training reward improved from
-488.75 at 5,120 steps to -26.97 at the endpoint. All 24 checkpoints have zero
recorded task measurements, so there are no experiment-4 success rates,
failure-sector counts, or hold diagnostics to report. The unchanged parent has
the latest measured result of 155/160 (96.875%) on the experiment-3 panel, while
the baseline parent evidence pooled 301/320 (94.06%) across two disjoint
panels; neither is an official 200-episode assessment.

**Hypothesis assessment:** The exploratory question is inconclusive for task
behavior because the sought reach-and-hold measurements were not collected.
The observed training dynamics weaken the usefulness of this fresh
periodic-observation recipe in the tested conditions: its endpoint proxy
remained substantially below the parent-era proxy, and no checkpoint provides
evidence to replace the current lineage. This does not contradict periodic
representations in general or establish a causal failure of the two added
features, because an unmeasured checkpoint is not a failed policy and the
training proxy is not the task outcome.

**Interpretation:** The strongest evidence for progress remains the measured
working parent, not the current experiment's training proxies. Restoring that
parent preserves the best available learned behavior and avoids selecting an
unmeasured challenger. The experiment does not justify terminal assessment:
the best-known development result remains below the objective and experiment 4
adds no task evidence that would change that decision.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-4/inventory.json`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-4/checkpoint-120832/artifact.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-3-working-160ep-seed4840-543af51fd137.json`;
and `robot_learning/scenario/observations.py`.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 5

**Result:** The fresh unchanged-baseline replication supplied no measured
challenger and did not demonstrate the human objective. The experiment is
closed with the measured `working` and `best_known` lineage preserved.

**Observed behavior:** The seed-2 run completed 120,832 steps and produced 24
checkpoints, all with zero task measurements. Training success was 0.00 through
80,896 steps, then reached 0.01 at 86,016 and 90,112, 0.06 at 95,232, 0.08 at
100,352, 0.16 at 105,472, 0.30 at 110,592, 0.43 at 115,712, and 0.57 at
120,832. Training reward improved from -494.12 at 5,120 steps to -15.19 at
120,832, while mean episode length decreased from 500 to 349 steps. The
selected baseline checkpoint from experiment 1 remains the strongest measured
development policy at 155/160 on its latest disjoint panel; experiment 5 has no
episode success, failure geometry, or hold diagnostic to compare with it.

**Hypothesis assessment:** The diagnostic replication hypothesis is weakened
under this fresh seed. The run shows partial learning in its training proxies,
but it does not reproduce the selected baseline's useful training trajectory or
provide a comparable measured peak, matching the proposal's contradicting
branch more closely than its expected observation. The task-performance part is
inconclusive rather than contradicted because all checkpoints are unmeasured:
training proxies are not task success, and an unmeasured checkpoint is not a
failed policy. This is evidence about the tested fresh restart, not a causal
disproof of the unchanged baseline recipe or of all fresh initializations.

**Interpretation:** Fresh baseline learning is variable under the two observed
runs, and this seed-2 trajectory does not justify spending another measurement
round on its unmeasured checkpoints or promoting it over the measured parent.
The improving proxy is an orthogonal process signal, not evidence of progress
toward the 98% task objective. The existing measured lineage remains the best
available policy at 155/160 (96.875%), below the official 196/200 requirement,
so terminal assessment is not requested.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-5/inventory.json`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-5-attempt-1.log`;
`research/postmortems.md`; and the experiment-1 measurement artifacts referenced
by the campaign brief.
