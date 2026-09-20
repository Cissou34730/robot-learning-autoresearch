# Research postmortems

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Scientific strategy

**Current synthesis:** The human objective is at least 98% success, or 196/200
episodes, on the official 6-20 cm reach-and-hold distribution. The unchanged
transferred baseline remains the strongest measured lineage: it scored 150/160,
151/160, 155/160, and 159/160 on four earlier disjoint development panels
(615/640, 96.09%), then scored 157/160 on each of two further disjoint panels
in experiment 10 (314/320, 98.125%). This is promising development evidence
for the saved policy, but the second panel was measured after the policy had
already been selected on the first, and the official 200-episode result remains
unknown. Its earlier measured failures were concentrated at negative target
angles and smaller radii. Unchanged continuation beyond 100352 steps produced
strong training proxies but much worse measured policies at the two sampled
checkpoints, so the proxy trajectory does not establish further task progress.

**Lessons and limits:** Complete measured reach-and-hold success is more reliable
for policy selection than training reward or proxy success. Transferred full-radius
support, angle balancing, a 75/25 targeted sampler, a staged hard-radius sampler,
a hold-progress reward, and the sampled unchanged continuation checkpoints did
not improve the unchanged parent. The experiment-10 proxy peak at checkpoint
70656 (0.99 training success, -0.141 reward) measured 119/160 versus the
parent's 157/160, while the 120832-step endpoint measured 114/160; the parent
won every discordant episode in both comparisons. These results weaken the
tested interventions and trajectories without disproving every curriculum,
reward, control, or representation design. The current observation already
exposes joint state, end-effector error, and both inverse-kinematics branches,
while policy I/O maps that representation directly to physical actions.
Unmeasured checkpoints are not failed policies, development panels are not the
official assessment, and the repeated 157/160 result does not guarantee the
official outcome.

**Open questions:** The official 200-episode result and the causal mechanism of
the residual failures remain uncertain. The campaign has not established whether
another reward, control, representation, or training schedule can close any
remaining official gap. These are recorded uncertainties, not a prescribed
action list.

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

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 6

**Result:** The hold-progress reward did not improve the transferred policy.
The experiment is closed by restoring the unchanged working recipe and
preserving the existing working and best-known lineage. The human objective is
not demonstrated.

**Observed behavior:** The run completed 120,832 steps and produced 24
checkpoints. Training proxies were strong but variable: checkpoint-35840
reached 0.99 training success, checkpoint-75776 had the highest recorded mean
reward of 5.41199 with 0.98 training success, and the endpoint was 0.95
training success with mean reward 2.06649. On the disjoint research panel
5000-5159, the measured checkpoint-75776 achieved 118/160 (73.75%), while the
unchanged working parent achieved 159/160 (99.375%) under the same evaluation
context. The paired comparison had 0 challenger wins and 41 parent wins. The
challenger had 42 truncated failures and the parent had 1; challenger failure
diagnostics included maximum holds ranging from 0 to 96 steps, while the
parent's sole failure reached no hold.

**Hypothesis assessment:** The diagnostic hypothesis is contradicted under the
tested transferred recipe and measured checkpoint: the expected gain in
complete success and hold stability was absent, and task success declined
substantially despite improved training proxies. This is evidence against the
usefulness of this reward intervention and trajectory for the current decision,
not a causal disproof of every hold-specific reward design or an explanation
of all residual parent failures.

**Interpretation:** The same-panel parent control and paired outcomes make the
challenger's loss directly relevant to policy selection, while the disjoint
panel makes the parent's 159/160 result comparable to its prior development
measurements. The high proxy values are orthogonal process signals rather than
evidence of task progress. The parent remains the safest working and
best-known lineage, but development evidence is not the official verdict and
does not by itself establish the 98% objective.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-6/inventory.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-6-checkpoint-75776-160ep-seed5000-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-6-working-160ep-seed5000-543af51fd137.json`;
and `robot_learning/scenario/reward.py`.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 8

**Result:** Targeted hard-region training did not improve the transferred
working policy. The changed sampler is reverted, and the measured `working`
and unchanged `best_known` lineages are preserved. The human objective remains
undemonstrated.

**Observed behavior:** Training completed 120,832 steps and produced 24
checkpoints. The two selected proxy peaks, checkpoints 70656 and 75776, both
reported 0.92 training success; checkpoint 75776 had the better recorded mean
reward (-5.8437 versus -6.0370). On the fresh research panel with episodes
5160-5319, checkpoint 70656 achieved 152/160 (95.00%), checkpoint 75776
achieved 151/160 (94.375%), and the unchanged working policy achieved 156/160
(97.50%). The working policy won all four discordant episodes against
checkpoint 70656 and all five discordant episodes against checkpoint 75776.
Each challenger retained the parent's four failed episode identities and added
four or five failures; all recorded failures were truncated at 500 steps.
The research-evaluation artifacts do not include target geometry, so they do
not establish whether the targeted inner negative-angle failure rate itself
changed.

**Hypothesis assessment:** The diagnostic hypothesis is weakened under the
tested transferred recipe. The expected improvement or preservation of
complete reach-and-hold success was absent on a comparable fresh panel, and
the paired results favor the unchanged parent. The training-proxy peaks are
therefore an orthogonal process signal rather than evidence of task progress.
Because this panel lacks target geometry, the result does not distinguish a
failure to correct the intended hard region from a correction offset by new
failures elsewhere; it is evidence against this sampler and trajectory, not a
causal disproof of targeted exposure in general.

**Interpretation:** The measured parent is the safer working policy and remains
the strongest available lineage, but its 156/160 result and prior development
panels do not establish the official 196/200 objective. Reverting the sampler
avoids carrying forward a changed recipe with lower measured success. No
additional measurement round is warranted for this experiment because both
proxy-selected challengers lose to the same-panel control and no unmeasured
checkpoint has task evidence; the campaign should continue from the unchanged
lineage rather than request terminal assessment.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-8/inventory.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-8-checkpoint-70656-160ep-seed5160-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-8-checkpoint-75776-160ep-seed5160-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-8-working-160ep-seed5160-543af51fd137.json`;
and `robot_learning/scenario/training_environment.py`.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 9

**Result:** The staged hard-radius curriculum did not improve the transferred
working policy. The curriculum recipe is reverted, and the unchanged `working`
and `best_known` lineages are preserved. The human objective remains
undemonstrated.

**Observed behavior:** Training success reached 0.97 with mean reward -2.69066
at checkpoint-45056, then declined to 0.71-0.72 during the hard-target exposure
and recovered to 0.93 with mean reward -6.08460 at checkpoint-120832. On the
fresh research panel with episodes 5320-5479, checkpoint-45056 achieved 144/160
(90.00%) while the unchanged working policy achieved 154/160 (96.25%). The
paired comparison favored the parent in all 10 discordant episodes. The
challenger had 16 actual failures and the parent had 6; all six parent failure
identities were retained by the challenger, which added ten failures. Among
challenger failures, 12 were below -90 degrees and 8 had radius at or below
12 cm; the parent failures were all below -90 degrees and 3 had radius at or
below 12 cm. The remaining 23 checkpoints were not measured.

**Hypothesis assessment:** The diagnostic hypothesis is weakened under the
tested transferred recipe. The expected translation of the 0.97 training proxy
peak into improved complete reach-and-hold behavior was absent, and the
contradicting paired result shows lower task success than the unchanged parent.
The proxy peak and later recovery are orthogonal process signals rather than
evidence of task progress. This conclusion applies to the tested staged sampler,
parent, and trajectory; it does not causally disprove other curricula or explain
why the added failures appeared.

**Interpretation:** The same-panel control and paired outcomes make the measured
loss directly relevant to lineage selection, while the fresh panel provides
comparable development evidence. No additional measurement round is warranted:
the only measured challenger loses clearly to the parent, and the unmeasured
checkpoints have no task evidence that would justify selecting them. Reverting
the sampler preserves the strongest available measured policy for continued
development, but its development results remain below the official 196/200
criterion and do not justify terminal assessment.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-9/inventory.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-9-checkpoint-45056-160ep-seed5320-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-9-working-160ep-seed5320-543af51fd137.json`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-9-attempt-1.log`;
and `robot_learning/scenario/training_environment.py`.

## 2c25415c-e39b-4e30-8d28-bec3b3598906 / Experiment 10

**Result:** Continuing the unchanged method beyond the selected 100352-step
policy did not improve measured task behavior. The unchanged working lineage
repeated 157/160 success on a second disjoint development panel, supporting
closure with that lineage and terminal assessment.

**Observed behavior:** The run completed 120832 steps and produced 24
checkpoints. Training proxies were strong but unstable: checkpoint-70656 had
0.99 training success and -0.141 mean reward, while the endpoint had 0.90
training success and -5.124 mean reward. Only checkpoint-70656 and
checkpoint-120832 were measured from the continuation; the other 22 candidates
remain unmeasured. On episodes 5480-5639, checkpoint-70656 achieved 119/160
(74.375%) and checkpoint-120832 achieved 114/160 (71.25%), versus 157/160
(98.125%) for the unchanged working policy. The working policy won all 38 and
43 discordant episodes respectively. Its three failures on that panel and its
three failures on the disjoint episodes 5640-5799 all truncated at 500 steps.
The second working measurement also achieved 157/160 (98.125%), giving 314/320
successes across the two new panels.

**Hypothesis assessment:** The continuation hypothesis is contradicted for the
measured proxy-peak and endpoint checkpoints: neither produced complete
reach-and-hold progress, and both were substantially below the contemporaneous
working control. This conclusion is limited to the sampled checkpoints and
tested continuation trajectory; the 22 unmeasured checkpoints are not failed
policies. The independent episode coverage for the unchanged working policy
supports the interpretation that its 157/160 result is not specific to the
first panel, although the policy had already been selected before the second
panel was measured.

**Interpretation:** Task-success measurements, rather than the high training
proxies, identify the unchanged working lineage as the useful saved policy.
Two disjoint panels at 98.125% provide sufficient development evidence to
request the official assessment, while still leaving the official result
unknown. The continuation recipe adds no measured benefit, so no challenger is
retained and the unchanged recipe is kept.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-10/inventory.json`;
`research/training_logs/2c25415c-e39b-4e30-8d28-bec3b3598906/experiment-10-attempt-1.log`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-10-working-160ep-seed5480-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-10-working-160ep-seed5640-543af51fd137.json`;
`research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-10-checkpoint-70656-160ep-seed5480-543af51fd137.json`;
and `research/evaluations/2c25415c-e39b-4e30-8d28-bec3b3598906/evaluation-2c25415c-e39b-4e30-8d28-bec3b3598906-experiment-10-checkpoint-120832-160ep-seed5480-543af51fd137.json`.
