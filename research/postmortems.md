# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve official-distribution reach-and-hold robustness beyond
the 98% development result, using the stable late trajectory from the
2048-step-rollout recipe as the working platform for a targeted improvement of
the remaining localized hold failures.

**Lessons and limits:** Experiment 7 changed only PPO `n_steps` from 1024 to
2048 while transferring the retained experiment-1 policy. Its task-reference
score was 96% at 36,864 steps and 98% at both 100,352 and 120,832 steps; the
research panel scored the final checkpoint 98% and 98.5% on two seeds. The late
research failures preserved the incumbent's four short-range negative-angle
cases, with three reaching tolerance but holding for only a few steps. The
final candidate tied the incumbent with zero discordant episodes across 400
compatible research episodes, so it is a useful stable working policy but not
evidence for replacing best-known. The high training proxy (0.99 early and
0.96 at the end) still did not predict the early measured score. The
2048-step result supports rollout/update-frequency stability under this
transferred recipe and development panels, but does not establish a general
causal explanation or official success; fresh-seed variability and the
representation/runtime contribution remain unresolved.

**Open questions:** Can a hold-aware intervention remove the four localized
short-range negative-angle failures without recreating the broad late
degradation seen in experiments 3 and 6? Is the stable 2048-step trajectory
reproducible beyond the measured seeds, and does it preserve the same behavior
when the reward is changed?

**Conditional next steps:** Continue from experiment 7 checkpoint-120832 with
the 2048-step rollout recipe and test a narrowly scoped hold-specific reward
change, measuring both the research and task-reference panels. If that
intervention broadens failures or loses late stability, restore the unchanged
experiment-1 best-known lineage and prioritize representation/runtime or
training-process diagnostics. Do not request the official benchmark until a
candidate has evidence beyond this development-panel tie and the remaining
failures are addressed.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 4

**Result:** The fresh unchanged PPO replication did not reproduce the retained
98% development policy. The retained experiment-1 checkpoint remains the
strongest measured policy and the replication produces no reusable challenger.

**Observed behavior:** This was a fresh replication with seed 1, not a changed
recipe, continuation, or transfer. The training proxy was 0 through 90,112
steps, then rose to 0.13 at 120,832; this proxy trajectory is not task
success. Research evaluation on the same 200-episode seed-7300 panel scored
32.0% at 90,112, 30.5% at 95,232, 32.0% at 100,352, 31.0% at 105,472, and
49.5% at 120,832. The independent task-reference development panel scored
32.0% at 100,352 and 49.5% at 120,832. At 100,352, 136 research episodes
failed, with only 16 failed episodes reaching tolerance and all of those
experiencing an interruption; at 120,832, 101 failed, with only five failed
episodes reaching tolerance. The failures span the target geometry and are
not the baseline's four short-range negative-angle hold failures. The late
increase from 32.0% to 49.5% is a partial improvement, but neither checkpoint
approaches 98%.

**Hypothesis assessment:** **Contradicted under the tested conditions.** The
expected recovery of the baseline development range and similar residual
failure sector did not occur at any measured late checkpoint. The result
supports the alternative that the retained 98% checkpoint is not reliably
produced by this recipe under the tested fresh seed, but it does not establish
which training-process factor caused the divergence or prove that the recipe
cannot recover with another seed or schedule.

**Interpretation:** The replication establishes substantial process
variability relevant to policy progress: the retained baseline cannot be
treated as a reproducible consequence of the unchanged recipe based on the
current evidence. The independent task-reference agreement and broad
reach-failure pattern make further measurement of the remaining unmeasured
checkpoints unlikely to change the lineage decision. This run should not
motivate another reward intervention yet, because its failure is not a
localized hold deficit and the proxy improvement did not predict task success.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/postmortems.md`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-90112-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-95232-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-105472-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-4-checkpoint-120832-task-reference-v1.json`;
`research/query_training_log.py`;
`robot_learning/scenario/evaluation.py`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/reward.py`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 6

**Result:** The lower-learning-rate transfer did not preserve the retained
baseline's late performance. The retained experiment-1 checkpoint remains the
strongest measured policy and no challenger is retained.

**Observed behavior:** This was a changed-recipe transfer from the retained
working checkpoint, changing only PPO learning rate from 0.0003 to 0.0001.
Research evaluation and the independent task-reference panel both scored
checkpoint-35840 at 97.5%, then scored checkpoints 100352 and 120832 at 91.0%.
The early checkpoint had five failures, all short negative-angle targets. Each
late checkpoint had 18 failures, predominantly short-range; research
diagnostics classified 12 late failures as reaching tolerance without
completing the hold. The training proxy reached 1.0 at 35840 and ended at 0.97,
while task success declined.

**Hypothesis assessment:** **Contradicted under the tested conditions.** The
expected late preservation at or above 98% and avoidance of late regression did
not occur. The early 97.5% result is a partial, below-target signal, and the
agreement between independent instruments confirms the observed degradation on
their development panels. This does not establish that learning rate caused
the regression in isolation, nor does it explain the divergence among fresh
replications; the conclusion is limited to this transferred policy, parameter
change, budget, and development panel.

**Interpretation:** Reducing the update magnitude was not a useful remedy for
late policy drift in this run. The mismatch between training proxy and measured
task success recurs, so proxy metrics should not select a lineage. Since the
candidate is below the retained policy at both late checkpoints and the late
failure pattern is broader than the baseline's localized failures, more
measurement of this candidate is unlikely to change the lineage decision.
Implementation and policy-runtime behavior should be inspected before another
reward intervention or optimization schedule change.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`;
`research/postmortems.md`;
`research/query_training_log.py`;
`robot_learning/train.py`;
`robot_learning/scenario/evaluation.py`;
`robot_learning/scenario/environment.py`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-35840-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-35840-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-6-checkpoint-120832-task-reference-v1.json`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 5

**Result:** The second fresh unchanged-recipe replication partially recovered
from experiment 4's failure but did not reproduce the retained baseline or meet
the human objective. The retained experiment-1 checkpoint remains the strongest
measured policy and no challenger is retained.

**Observed behavior:** This was a fresh replication with training seed 2, not a
changed recipe, continuation, or transfer. The training proxy was 0 through
86,016 steps, reached 0.06 at 100,352 and 0.54 at 120,832, and the recorded
training reward rose from 114.5 to 169.9 over those measured checkpoints.
Research evaluation scored both checkpoints at 74.5% (149/200 successes and
51 failures). The protected task-reference panel independently scored both at
74.5%. Research diagnostics classified 2 of the 51 failures as reaching
tolerance before an interrupted hold at 100,352 steps and 17 as doing so at
120,832; the other failures never reached tolerance. The task-reference
failures span the sampled radius and angle ranges rather than matching the
retained baseline's four localized short-range negative-angle failures.
Compatible paired comparisons strongly favored the retained working policy:
49 wins to 2 at 100,352 and 47 wins to 0 at 120,832.

**Hypothesis assessment:** **Inconclusive with a partial, unexpected signal.**
The prediction's recovery branch (at least 90% success) was not observed, so
seed 2 did not recover near the baseline range. The prediction's broad-failure
branch (below 60% at both late checkpoints, like experiment 4) was also not
observed. The intermediate 74.5% result, agreement between independent
instruments, and change from mostly unreached failures to more interrupted
holds provide partial evidence that fresh training trajectories vary, but do
not support a seed-only explanation or identify the responsible training
condition. The conclusion is limited to the tested unchanged recipe, seeds and
budget; these are development measurements, not an official benchmark result.

**Interpretation:** Experiment 5 makes process variance practically relevant:
the unchanged recipe can produce substantially different policies, yet the
second fresh run still does not reliably reach the human objective. Additional
measurement of the two already measured checkpoints is unlikely to change the
working-lineage decision, because both instruments agree and paired comparisons
decisively favor the retained baseline. Training proxy and reward improved
without reaching the objective, so they should not substitute for task
measurement. A useful next experiment remains through a controlled
training-process or optimization investigation before another reward
intervention.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/postmortems.md`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-5-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-5-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-5-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-5-checkpoint-120832-task-reference-v1.json`;
`research/query_training_log.py`;
`robot_learning/scenario/evaluation.py`;
`robot_learning/benchmark/reference_evaluation.py`;
`robot_learning/benchmark/reference_contract.py`;
`research/current_params.json`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 1

**Result:** Fresh baseline reached the 98% development target at 100,352
steps, but the final checkpoint regressed to 97%; the earlier checkpoint is
selected as working and best-known.

**Observed behavior:** The 100,352-step checkpoint succeeded on 196/200
episodes in both the research evaluation and task-reference panel. Its four
failures were the same across instruments and were concentrated at short
negative-angle targets; all truncated at 500 steps. Research diagnostics show
near-tolerance reach followed by interrupted holding. The 120,832-step
checkpoint succeeded on 194/200 episodes, retaining the same four failures and
adding failures at approximately 10 cm, -132 degrees and 17.9 cm, 169 degrees.
The paired research comparison favored the earlier checkpoint 2-0 among two
discordant episodes. The run was a fresh baseline with no changed recipe or
continuation.

**Hypothesis assessment:** Partially supported as a baseline-establishment
test: it demonstrated near-objective task performance and identified a
measured behavioral peak, but it did not establish official 98% success and
the final checkpoint did not sustain the peak. These are development-panel
measurements from one evaluation seed, not an official result or evidence
about learning-process reproducibility.

**Interpretation:** `checkpoint-100352` is the strongest measured policy in
this experiment, and the repeated hard-sector failures provide a concrete
target for the next recipe rather than a reason to select the later
checkpoint. The late regression is an observed checkpoint difference; its
cause is not established.

**Evidence inspected:** `research/results.jsonl`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-1-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/evaluation.py`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 2

**Result:** The focused training-target sampler did not produce a better
measured policy. The transferred working checkpoint remains selected.

**Observed behavior:** The 100,352-step targeted checkpoint scored 97.5% and
99.0% on the two 200-episode research panels, and the 120,832-step checkpoint
scored 98.0% and 98.5%; both pooled to 98.25%. Paired comparisons found no
discordant episodes between the 100,352-step candidate and working, while the
120,832-step candidate had one win and one loss across two discordant episodes.
On the fixed task-reference panel, working scored 98.0%, the targeted
100,352-step checkpoint 97.5%, and the targeted 120,832-step checkpoint 97.0%.
The targeted 100,352-step model retained the working model's five failures on
the seed-7300 research panel and two failures on seed 9100; failures continued
to include the short-range negative-angle sector and interrupted holds.

**Hypothesis assessment:** **Contradicted under the tested conditions.** The
expected reduction in hard-sector failures was not observed, and the
task-reference result declined below the baseline for both measured targeted
checkpoints. The pooled research score did remain 98.25% across two seeds, so
the intervention did not broadly collapse research-panel performance; this
partial preservation does not support the predicted local improvement. The
result weakens this 50% focused-sampling recipe, but does not establish that
all targeted exposure or hold-focused methods cannot work. The comparison also
does not isolate sampling from continuation or optimization variance.

**Interpretation:** More measurement of the two available targeted
checkpoints is unlikely to resolve the lineage decision: both instruments
agree that neither beats the retained working policy, and the task-reference
panel favors working. Restore the baseline recipe and retain the measured
100,352-step policy; a scientifically useful path remains through a distinct
hold-aware or gentler curriculum intervention.

**Evidence inspected:** `research/results.jsonl`;
`research/postmortems.md`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-100352-200ep-seed7300-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-100352-200ep-seed9100-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-120832-200ep-seed7300-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-120832-200ep-seed9100-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-working-200ep-seed7300-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-working-200ep-seed9100-499fb506b46b.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-2-working-task-reference-v1.json`;
`robot_learning/scenario/environment.py`;
`research/query_training_log.py`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 3

**Result:** The 0.5 hold-exit forfeiture intervention was contradicted under
the tested transfer and PPO budget. The retained working policy remains the
working and best-known lineage.

**Observed behavior:** The 30,720-step candidate scored 97% on both the
research evaluation and the task-reference panel. The 100,352- and
120,832-step candidates scored 84% and 85% on both panels, respectively. On
the task-reference panel, the retained policy had four failures, all in the
short-range negative-angle sector. The 100,352-step candidate retained two of
those failures but added 30 new failures; the 120,832-step candidate retained
three and added 27 new failures. Research diagnostics likewise showed many
new interrupted or unreached episodes at the later checkpoints. The apparent
late training proxy success of 0.93 and 0.98 did not correspond to task
performance.

**Hypothesis assessment:** **Contradicted under the tested conditions.** The
expected reduction in interrupted holds and preservation of at least 98%
broad development performance were not observed. The intervention did not
improve the targeted sector and produced broad panel degradation at the
checkpoints selected for comparison. The measurements establish a poor
candidate recipe under this transfer and budget; they do not by themselves
separate the reward change from optimization trajectory variance or rule out
different, weaker hold-aware interventions.

**Interpretation:** The independent research and task-reference measurements
agree that additional measurement of the late checkpoints is unlikely to
change the lineage decision. The early 97% result also does not meet the
development target or show targeted improvement. Revert the changed reward
recipe and use an unchanged-baseline replication to measure process
variability before investing in another shaping intervention.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-30720-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-30720-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-3-checkpoint-120832-task-reference-v1.json`;
`robot_learning/scenario/reward.py`.

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Experiment 7

**Result:** The 2048-step PPO rollout transfer produced a late-stable
challenger. It becomes the working lineage with its recipe kept; the
experiment-1 checkpoint remains best-known because the compatible comparison
was a tie rather than an improvement.

**Observed behavior:** This was a changed-recipe transfer from the retained
experiment-1 checkpoint, changing only PPO `n_steps` from 1024 to 2048. The
training proxy was 0.99 at 36,864 steps, 0.98 at 100,352, and 0.96 at
120,832. Research evaluation scored 96.0% at 36,864, then 98.0% at 100,352
and 120,832 on seed 7300, and 98.5% at 120,832 on seed 9100. The independent
task-reference panel scored 96.0% early and 98.0% at both late checkpoints.
At the late seed-7300 research checkpoint, the four failures were the same
short-range negative-angle cases as the incumbent (approximately 6.7--9.9 cm
and -116--128 degrees); three reached tolerance but held for only 2--3 steps.
The final candidate and incumbent had zero discordant episodes across 400
compatible research episodes. The final development results remain
non-official.

**Hypothesis assessment:** **Supported under the tested conditions, with
limits.** The expected preservation of at least 98% late success and the
incumbent's localized failure pattern occurred, while the broad late
degradation seen after the lower learning rate did not. The 96.0% early
measurement is a partial negative signal, and the exact paired tie provides
stability rather than improvement evidence. This does not prove that rollout
length alone caused the difference or establish performance across fresh
training seeds, and the human objective has not been officially assessed.

**Interpretation:** Increasing rollout length is a useful process intervention
for this transferred recipe: it supplied a stable late working checkpoint
without changing the saved policy I/O, normalization, task mechanics, or
runtime contract. The independent task-reference agreement and the unchanged
localized failures make another measurement round unlikely to change the
lineage decision. The stable late platform makes a narrowly scoped hold-aware
reward experiment more informative than another unisolated optimizer change,
but proxy success must not select the next policy.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`;
`research/training_logs/03a3c9ad-ec65-4780-bee5-ada9a02320a5/experiment-7-attempt-1.log`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-36864-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-100352-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-120832-200ep-seed7300-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/evaluation-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-120832-200ep-seed9100-6ba3ba6d7654.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/03a3c9ad-ec65-4780-bee5-ada9a02320a5/task-reference-03a3c9ad-ec65-4780-bee5-ada9a02320a5-experiment-7-checkpoint-120832-task-reference-v1.json`;
`robot_learning/train.py`; `robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`; `robot_learning/scenario/policy_io.py`;
`robot_learning/policy_runtime.py`.
