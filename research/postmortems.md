# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve official-distribution reach-and-hold robustness beyond
the 98% development result, but first make the baseline learning process
reliable enough that reward interventions are interpretable. The fresh
replication did not recover the retained policy, so the immediate direction is
training-process variance rather than another hold-focused reward change.

**Lessons and limits:** Experiment 4 used the unchanged PPO recipe from fresh
initialization with training seed 1, directly testing reproducibility rather
than a changed recipe or continuation. Its training proxy stayed at 0 through
90,112 steps and reached only 0.13 by 120,832 steps. On the identical
200-episode research panel, measured checkpoints scored 32.0% at 90,112,
30.5% at 95,232, 32.0% at 100,352, 31.0% at 105,472, and 49.5% at 120,832;
the protected task-reference panel independently reported 32.0% and 49.5% at
the two measured checkpoints. The final improvement is an unexpected partial
signal, but it remains far below the retained baseline's 98%. At 100,352
steps, 136 of 200 research episodes failed and most were reach failures across
the target geometry; at 120,832, 101 failed, with only five of those failures
ever entering tolerance and then interrupting the hold. This differs from the
baseline's four localized short-range negative-angle hold interruptions.
Agreement between the two instruments makes an evaluator-specific explanation
less likely, but this single replication does not identify whether the source
is initialization, optimization trajectory, or another training-process
factor. Development panels are not held-out confirmation or the official
benchmark.

**Open questions:** What training-process condition determines whether the
unchanged recipe reaches the 98% development range, and can that condition be
made reliable without sacrificing the retained policy's residual hold
behavior? The current evidence does not distinguish seed variance from a
trajectory or optimization failure, and training reward/proxy success is not
an adequate substitute for task measurement.

**Conditional next steps:** Keep the retained 100,352-step baseline as working
and best-known and keep its unchanged scientific recipe. Experiment 5 should
run a second fresh replication with a distinct seed under the same recipe and
budget: recovery toward the baseline range would support seed or trajectory
variance, while another broad reach failure would weaken a seed-only explanation
and favor investigating the training implementation or optimization schedule
before adding reward complexity.

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
