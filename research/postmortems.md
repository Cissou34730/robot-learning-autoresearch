# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve official-distribution reach-and-hold robustness beyond
the 98% development result while first establishing whether the retained
baseline's performance is reproducible. Experiment 3's hold-exit forfeiture
caused broad degradation rather than a local hold improvement, so the next
experiment should prefer unchanged-baseline replication before another
hold-focused shaping change.

**Lessons and limits:** The fresh PPO baseline reached 98% on the 200-episode
research panel and 98% on the task-reference development panel at 100,352
steps, but experiment 2's 50% focused sampler did not improve the residual
behavior. On the compatible experiment-2 research panels, both targeted
checkpoints pooled 98.25% across two seeds, while the transferred working
policy also pooled 98.25%; the 100,352-step targeted model had 97.5% and 99.0%
by seed and retained the same failure identities as the working policy on
both panels. The task-reference panel was worse for the targeted checkpoints:
97.5% at 100,352 and 97.0% at 120,832 versus 98.0% for working. Failures still
included short-range negative-angle hold interruptions, and the 120,832-step
candidate did not remove them. Training proxy success was only 0.70 at
100,352 and 0.74 at 120,832, so proxy improvement is not evidence of task
progress. The research and task-reference panels are development evidence,
not independent held-out confirmation or the official benchmark. Experiment 3
tested a 0.5 hold-exit forfeiture by transfer from the retained policy. Its
30,720-step checkpoint reached 97% on both panels, while the 100,352- and
120,832-step checkpoints reached only 84% and 85%; the latter candidates added
many failures across the target geometry rather than reducing the four
short-range negative-angle baseline failures. This weakens this penalty
strength and transfer recipe under the tested budget, but does not isolate the
reward effect from optimization variance or reject all hold-aware shaping.

**Open questions:** How often does unchanged PPO training recover the
98%-level development policy from the current baseline recipe? If replication
is successful, can a weaker or more localized hold intervention improve the
known residual sector without broad regression? The current experiments do not
separate recipe effects from optimization trajectory variance.

**Conditional next steps:** Keep the measured 100,352-step baseline as the
working and best-known lineage and restore its scientific recipe. Prefer an
unchanged fresh replication next; if it recovers the baseline range, test a
smaller hold-aware shaping change, while a further failure would favor
investigating training-process variance over adding reward complexity.

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
