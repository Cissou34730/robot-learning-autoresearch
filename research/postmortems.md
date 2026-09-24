# Research postmortems

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong reach-and-hold
policy, but the best candidate has not yet demonstrated the 98% objective on
independent development panels. `checkpoint-100352` is the strongest measured
policy: it achieved 189/200 (94.5%) on each of two disjoint research panels,
while nearby late checkpoints were no better. Its 196/200 (98%) task-reference
result is encouraging but comes from the fixed panel used for selection and is
not independent confirmation. Further development should target the remaining
failure cases rather than treating the training reward plateau or the
task-reference score as objective attainment.

**Lessons and limits:** Direct task success, not training reward, determined the
lineage choice. The late proxy peak transferred to stable but sub-threshold
research success, and continued training to `checkpoint-120832` did not improve
it (188/200 and 187/200 on the two research panels). Pairwise differences were
small, so the evidence supports selecting `checkpoint-100352` without claiming
that the baseline recipe or its late-checkpoint ordering is causally optimal.
The research panels provide 400 distinct episodes for the selected model; the
fixed task-reference panel remains development evidence only, and the official
200-episode assessment is still unmeasured.

**Open questions:** Which scientific intervention can reduce the residual
reach-or-hold failures without sacrificing the broad angular and radial
coverage learned by the baseline remains unresolved. The current measurements
do not identify whether those failures are best addressed by reward shaping,
training distribution, or another learning-method change.

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 1

**Result:** The baseline produced a useful policy, with
`checkpoint-100352` the strongest and most stable measured candidate, but the
independent research evidence remains below the 98% objective.

**Observed behavior:** `checkpoint-100352` achieved 189/200 (94.5%) on both
research panels (episodes 4200-4399 and 4400-4599), for 378/400 pooled
successes. `checkpoint-115712` achieved 188/200 on the second panel;
`checkpoint-120832` achieved 188/200 and 187/200 on the two panels; and
`checkpoint-86016` achieved 187/200. The fixed task-reference panel gave
`checkpoint-100352` 196/200 (98%), versus 194/200 for `checkpoint-120832` and
188/200 for `checkpoint-86016`. Pairwise comparisons on shared research
episodes favored `checkpoint-100352` over `checkpoint-120832` by 3-0
discordant outcomes pooled across both panels, but only three episodes were
discordant. The detailed evaluation for the selected checkpoint includes
episodes that timed out or interrupted the required 100-step hold.

**Hypothesis assessment:** Partially supported. The baseline successfully
established substantial task competence and a reproducible late-checkpoint
plateau, but the two disjoint research panels both measured 94.5%, not the
98% objective. The task-reference 98% result cannot independently confirm the
policy because that fixed panel was reused for selection, and development
measurements cannot declare the official objective reached.

**Interpretation:** `checkpoint-100352` is the evidence-backed working and
best-known lineage for the next experiment. The unchanged scientific recipe is
worth preserving because it produced the strongest available policy, while
additional training alone is not supported by the measured decline at
`checkpoint-120832`. No unmeasured checkpoint is treated as a failed policy,
and no unmeasured alternative is retained because it has no demonstrated
future advantage over the selected lineage.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-200ep-seed4200-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-200ep-seed4400-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/task-reference-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-1-checkpoint-100352-task-reference-v1.json`.
