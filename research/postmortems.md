# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve official-distribution reach-and-hold robustness beyond
the 98% development result, while making the baseline learning process reliable
enough that reward interventions are interpretable. The second fresh
replication recovered partway but not to the baseline range, so the next
investigation should examine training-process or optimization conditions before
another hold-focused reward change.

**Lessons and limits:** Experiment 5 was a fresh replication of the unchanged
PPO recipe with training seed 2, not a continuation or changed recipe. Its
100,352- and 120,832-step checkpoints both scored 74.5% on the same 200-episode
research panel, and the independent protected task-reference panel reported
74.5% for both as well. This is materially above experiment 4's 32.0% and
49.5% at the corresponding checkpoints, but well below experiment 1's 98.0%
and 97.0%. On the research diagnostics, 2 of 51 failed episodes had reached
tolerance and then interrupted at 100,352 steps, versus 17 of 51 at 120,832;
the remainder did not reach tolerance. The training proxy rose from 0.06 to
0.54, but it is not task success. The task-reference panel is independent of
research evaluation and is development evidence, not official confirmation.
Together these results provide partial evidence of training-process variance,
but do not establish that seed variance alone explains the baseline gap.

**Open questions:** Which training or optimization condition separates the
98%-range trajectory from the 74.5% and 32--49.5% trajectories, and can it be
made reliable without worsening the retained policy's residual hold failures?
The current evidence does not identify whether the relevant factor is
initialization, optimization trajectory, implementation behavior, or schedule.

**Conditional next steps:** Keep the retained 100,352-step baseline as working
and best-known and preserve its unchanged scientific recipe. If research
continues, inspect and test a training-process or optimization-schedule
intervention that targets reproducibility before adding reward complexity. A
future recovery toward the baseline range would support process variance,
whereas another low trajectory would justify prioritizing implementation
diagnostics; neither outcome should be inferred from the current training
proxy alone.

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
