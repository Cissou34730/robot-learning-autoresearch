# Research postmortems

## 0a384c0e-6049-41b0-b65f-51378059913c / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned substantial reach-and-hold
behavior late in training. Checkpoint-100352 is the strongest measured policy:
it achieved 94.375% on the first disjoint research panel, 98.0% on a second
disjoint research panel, and 98.0% on the reused task-reference panel.
Checkpoint-120832 was slightly weaker on the second disjoint panel and the
reference panel, while the earlier reward peak at checkpoint-86016 did not
produce better task success. This supports selecting checkpoint-100352 for the
official assessment, without treating development measurements as the official
verdict.

**Lessons and limits:** Training success and reward were useful trajectory
signals but were not acceptance criteria: reward peaked at checkpoint-86016,
where task success was 93.125%, and later checkpoints performed better on the
measured task. The two fresh research panels provide 360 distinct episodes:
checkpoint-100352 succeeded on 347 (96.39%) and checkpoint-120832 on 345
(95.83%). The second panel alone reached 98.0% for checkpoint-100352, but the
first did not, so the evidence supports progress and a small selection
preference rather than a generalization guarantee. The task-reference panel is
reused and selection-contaminated. Research-evaluation failures all ran to the
500-step limit, and the current diagnostics do not decompose reach from hold,
so residual-failure causes remain limited.

**Open questions:** The official 200-episode panel will determine whether the
selected frozen policy reaches the human objective. The measured failures are
consistent with a narrow geometric or hold-boundary weakness, but the available
research artifacts do not establish that cause.

## 0a384c0e-6049-41b0-b65f-51378059913c / Experiment 1

**Result:** The baseline produced a useful learned policy and a strongest
candidate, checkpoint-100352, but development evidence is mixed across panels.
Checkpoint-100352 is selected as working and best-known for terminal assessment;
checkpoint-120832 is retained as a measured alternative.

**Observed behavior:** Training ran to 120,832 steps with the unchanged PPO
recipe. Training success was 0 through 70,656 steps, then rose from 0.06 at
75,776, 0.17 at 80,896, 0.42 at 86,016, 0.71 at 90,112, and 0.93 at 95,232
to 0.97 at 100,352. It later varied between 0.93 and 0.95. Training reward
peaked at 163.85 at 86,016, then fell to 117.32 at 100,352 and 112.02 at
120,832.

On the first disjoint research panel, checkpoint-86016 reached 93.125% (149/160)
and both checkpoint-100352 and checkpoint-120832 reached 94.375% (151/160).
On the second disjoint research panel, checkpoint-100352 reached 98.0%
(196/200) and checkpoint-120832 reached 97.0% (194/200). Across the 360
distinct research episodes, the pooled results were 347/360 (96.39%) for
checkpoint-100352 and 345/360 (95.83%) for checkpoint-120832. The paired
comparison recorded 2 discordant wins for checkpoint-100352 and 0 for
checkpoint-120832. On the reused task-reference panel, the results were 98.0%
for checkpoint-100352 and 97.0% for checkpoint-120832; this panel is not
independent confirmation. Research-evaluation failures truncated at 500 steps;
the task-reference failures for checkpoint-100352 had final distances from
0.986 to 1.325 cm and were concentrated in a small negative-angle region.

**Hypothesis assessment:** Partially supported. The measurement question from
the baseline follow-up was whether late training gains transfer to complete
reach-and-hold behavior and whether the reward peak represents genuine task
progress. Late checkpoints clearly transferred substantial task competence,
and checkpoint-100352 reached 98.0% on one fresh 200-episode panel. However,
its 94.375% result on the other fresh panel prevents treating that as stable
98% performance. The reward-peak checkpoint was weaker on measured task
success, so its high reward was an orthogonal or incomplete proxy rather than
evidence of the best task policy. The second disjoint round supports a modest
preference for checkpoint-100352 over checkpoint-120832, but does not establish
a causal effect of stopping at that checkpoint.

**Interpretation:** The baseline made meaningful progress toward the human
objective and checkpoint-100352 is the best available frozen policy on
comparable measured behavior. The evidence is sufficient to resolve working
and best-known lineage, but not to claim that development panels have already
established the official 98% objective. Because the candidate reached 98.0% on
a disjoint 200-episode panel and was at least as good as the endpoint on all
comparable measurements, terminal assessment is more decision-relevant than
another development panel. Any future training would be an ordinary next
experiment rather than part of this closure.

**Evidence inspected:** `research/brief.md`;
`research/checkpoints/challengers/0a384c0e-6049-41b0-b65f-51378059913c/experiment-1/inventory.json`;
`research/checkpoints/challengers/0a384c0e-6049-41b0-b65f-51378059913c/experiment-1/parameters.json`;
`research/training_logs/0a384c0e-6049-41b0-b65f-51378059913c/experiment-1-attempt-1.log`;
the five `research/evaluations/0a384c0e-6049-41b0-b65f-51378059913c/evaluation-*.json`
artifacts for experiment 1; and the two
`research/evaluations/0a384c0e-6049-41b0-b65f-51378059913c/task-reference-*.json`
artifacts.
