# Research postmortems

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Scientific strategy

**Current synthesis:** PPO has learned a strong but variable reach-and-hold
policy. The standing `best_known` lineage scored 965/1000 (96.5%) across the
first five disjoint research panels and 196/200 (98.0%) on the new disjoint
panel, for 1161/1200 (96.75%) pooled across six panels. This is independent
confirmation of one objective-level development result, but not a stable
demonstration of the 98% objective. Full-radius target training, full hold-exit
forfeiture, explicit hold progress in a fresh observation, and the increased
discount factor all failed to improve the retained lineage.

**Lessons and limits:** Direct task success, not training proxies, governs
comparisons. The gamma 0.995 transfer produced 73.0%, 74.5%, and 93.5% on its
measured checkpoints versus 98.0% for the same-panel control, so the tested
longer-horizon credit-assignment change should not remain active. Residual
failures include both no-reach episodes and interrupted holds; the tested
interventions do not isolate a remaining cause. Development panels, including
the reused 98% task-reference panel, cannot establish the official result.

**Open questions:** The cause of the standing lineage's remaining no-reach and
interrupted-hold failures remains unresolved, as does whether it meets the
official fixed-panel objective. Other learning-method changes remain possible,
but the tested gamma intervention is not a useful continuation.

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

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 2

**Result:** Full-radius target training produced a useful but still
sub-threshold policy; `checkpoint-105472` is selected as the experiment-2
working lineage, while the prior `checkpoint-100352` remains best known.

**Observed behavior:** The pre-peak `checkpoint-95232`, proxy-peak
`checkpoint-105472`, and final `checkpoint-120832` each achieved 190/200
(95.0%) on the disjoint research panel covering episodes 4600–4799. The
same-panel `best_known` control achieved 191/200 (95.5%); each paired
comparison had zero challenger wins and one control win. These results remain
below the official threshold of 196/200. The experiment changed training
radius sampling from 0.14–0.20 m to 0.06–0.20 m without changing official task
mechanics or PPO hyperparameters.

**Hypothesis assessment:** Weakened. The prediction that full-radius transfer
would materially raise direct success above the established baseline was not
supported: all three measured checkpoints tied at 95.0% and were slightly
below the same-panel control. The result does not prove that radius coverage
has no effect because the comparison has one 200-episode panel and no
component-level control, but it weakens radius coverage as the primary
explanation for the remaining failures.

**Interpretation:** `checkpoint-105472` is a measured, reusable working policy
for the current full-radius recipe, but it is not a better-supported
best-known policy than `checkpoint-100352`. The new disjoint panel confirms
that the intervention did not reach the human objective; the fixed
task-reference panel is not independent confirmation, and no terminal
assessment is requested by this closure.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/8f4d116e-7b66-4ca1-ab31-5915330bf310/experiment-2/inventory.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-95232-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-105472-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-checkpoint-120832-200ep-seed4600-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-2-best_known-200ep-seed4600-f48545f83637.json`.

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 3

**Result:** Full hold-exit forfeiture weakened the transferred policy rather
than improving it. `best_known` remains both the working and best-known
lineage; the experiment-3 reward change should be reverted.

**Observed behavior:** On the disjoint research panel covering episodes
4800-4999, `checkpoint-90112` scored 194/200 (97.0%),
`checkpoint-105472` scored 182/200 (91.0%), and `checkpoint-120832` scored
185/200 (92.5%). The same-panel `best_known` control scored 197/200 (98.5%).
The paired comparisons gave the control 3, 15, and 12 discordant wins over
the three experiment-3 checkpoints, with no challenger wins. The detailed
`checkpoint-90112` artifact records four no-reach failures and two interrupted
holds, so the targeted reward change did not remove the hold failures and also
did not preserve the control's reach reliability.

**Hypothesis assessment:** Weakened. The prediction that full hold-progress
forfeiture would improve direct success and hold stability without harming
reach was not supported on the new panel: the strongest checkpoint was 1.5
percentage points below the control, and later checkpoints were substantially
worse. This is evidence against retaining the intervention as the current
recipe, not proof that every possible hold-related reward design is ineffective.

**Interpretation:** The disjoint 4800-4999 result provides independent
development evidence for the existing best-known policy, but its 197/200
score does not replace the earlier 189/200, 189/200, and 191/200 results or
constitute the official verdict. The experiment has a clear lineage decision,
so no additional measurement is needed to decide this intervention: restore
the best-known recipe and leave future work to a separately prepared
experiment focused on the remaining no-reach failures. No terminal assessment
is requested in this closure because the pooled development evidence remains
below the objective and further scientific development remains useful.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/research_state.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-3-checkpoint-90112-200ep-seed4800-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-3-best_known-200ep-seed4800-f48545f83637.json`.

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 4

**Result:** Adding normalized accumulated hold progress to the observation
produced a substantially worse policy than the retained best-known lineage.
The intervention should be closed and its fresh 12-feature recipe should not
remain active.

**Observed behavior:** On the new disjoint episodes 5000-5199, the measured
challenger checkpoints scored 106/200 (53.0%), 108/200 (54.0%), and 113/200
(56.5%) at 100352, 105472, and 120832 steps. The same-panel best-known
control scored 199/200 (99.5%), with paired comparisons giving it 93, 91, and
87 discordant wins over the three challengers. The challengers frequently
timed out at 500 steps or failed to complete the uninterrupted hold. The final
checkpoint's training reward rose to 140.10 and its training-success proxy was
only 0.05, so those proxies did not indicate useful official-task behavior.

**Hypothesis assessment:** Contradicted under the tested fresh-training
conditions. Explicitly observing normalized hold progress did not improve
uninterrupted reach-and-hold reliability or preserve reach performance; every
measured challenger was far below the same-panel control. This is strong
evidence against retaining this representation recipe, but one fresh run does
not establish that all alternative representations or optimization methods are
ineffective.

**Interpretation:** The saved experiment-4 candidates are not reusable
policies relative to the existing lineage, and the panel provides enough
evidence for closure without another measurement round. The best-known policy's
199/200 result is independent of its prior selection panels because episodes
5000-5199 are new, but it remains development evidence rather than an official
verdict. Restore the best-known complete recipe and artifact; any further
training is a separate post-closure experiment.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/research_state.json`;
`research/checkpoints/challengers/8f4d116e-7b66-4ca1-ab31-5915330bf310/experiment-4/inventory.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-4-checkpoint-100352-200ep-seed5000-765f20eb658a.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-4-checkpoint-105472-200ep-seed5000-765f20eb658a.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-4-checkpoint-120832-200ep-seed5000-765f20eb658a.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-4-best_known-200ep-seed5000-765f20eb658a.json`.

## 8f4d116e-7b66-4ca1-ab31-5915330bf310 / Experiment 5

**Result:** Increasing PPO gamma from 0.99 to 0.995 did not produce a useful
challenger. The existing `best_known` lineage remains the working and
best-known policy, and the gamma change should be reverted.

**Observed behavior:** On the new research panel covering episodes 5200-5399,
the gamma-0.995 checkpoints scored 146/200 (73.0%) at 70656 steps, 149/200
(74.5%) at 100352 steps, and 187/200 (93.5%) at 120832 steps. The same-panel
`best_known` control scored 196/200 (98.0%). Paired comparisons gave the
control 51, 47, and 10 discordant wins over the three challengers, with only
one challenger win at 70656 and one at 120832. The final challenger was closer
to the control but still below the objective and below the control.

**Hypothesis assessment:** Contradicted under the tested transferred
gamma-0.995 conditions. The longer discount horizon did not improve direct
reach-and-hold success or preserve the parent's reliability across the late
trajectory; every measured challenger underperformed its same-panel control.
This rejects this intervention as the current recipe, but does not establish
that all discounting or learning-method alternatives are ineffective.

**Interpretation:** The new 5200-5399 panel is disjoint from the panels used to
select `best_known`, so its 196/200 result is independent development evidence
for the standing lineage. However, the lineage's pooled six-panel result is
1161/1200 (96.75%), and the fixed task-reference panel remains reused
development evidence. The experiment therefore closes with the prior lineage
and recipe restored; further training or another learning-method investigation
is a separate post-closure decision.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/research_state.json`;
`research/checkpoints/challengers/8f4d116e-7b66-4ca1-ab31-5915330bf310/experiment-5/inventory.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-5-checkpoint-70656-200ep-seed5200-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-5-checkpoint-100352-200ep-seed5200-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-5-checkpoint-120832-200ep-seed5200-f48545f83637.json`;
`research/evaluations/8f4d116e-7b66-4ca1-ab31-5915330bf310/evaluation-8f4d116e-7b66-4ca1-ab31-5915330bf310-experiment-5-best_known-200ep-seed5200-f48545f83637.json`.
