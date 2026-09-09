# Research postmortems

## 03a3c9ad-ec65-4780-bee5-ada9a02320a5 / Scientific strategy

**Direction:** Improve official-distribution reach-and-hold robustness beyond
the 98% development result, with particular attention to short-range
negative-angle hold stability. The targeted sampler did not improve the
measured residual failures, so the next experiment should test a different
hold-focused recipe or a gentler curriculum rather than repeat this sampler.

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
not independent held-out confirmation or the official benchmark.

**Open questions:** Can hold-aware reward or a gentler mixture/curriculum
improve the residual sector without trading away broad performance? Is the
late-training regression and the focused-sampler outcome specific to this
optimization trajectory? The present experiment did not isolate the sampling
mechanism from continuation variance because it had no unchanged-continuation
control.

**Conditional next steps:** Keep the measured 100,352-step baseline as the
working and best-known lineage, restore its scientific recipe, and run a new
ordinary experiment only with a distinct hold-focused intervention. Prefer
hold-aware shaping or a gentler curriculum; change direction toward
replication if the next intervention again harms the task-reference panel.

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
