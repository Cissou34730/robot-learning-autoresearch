# Research postmortems

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Scientific strategy

**Current synthesis:** The working 100352-step PPO policy remains the strongest
supported lineage at 1077/1100 (97.9%) over six distinct research panels.
Experiment 4 changed only `HOLD_EXIT_FORFEIT_FRACTION`, from 0.0 to 0.5, while
the 0.06-0.20 m training-radius range and PPO configuration were unchanged.
That change did not improve complete reach-and-hold success: on the disjoint
8000-8199 panel, its 105472-step and 120832-step candidates scored 179/200
(89.5%) and 191/200 (95.5%), versus 197/200 (98.5%) for working. Working
therefore remains both the working and best-known lineage; the evidence still
does not establish objective-level performance under the official task.

**Lessons and limits:** The experiment-4 candidates had 21 and 9 failures,
respectively, versus 3 for working; every failure was a 500-step truncation.
The paired comparisons had zero wins for each changed-reward candidate and 18
and 6 wins for working. The proxy peak nevertheless reported training success
1.00, while the late checkpoint reported 0.97, so training proxies did not
predict a task improvement and reward totals are not comparable across the
changed reward. The frozen model establishes branch ambiguity, finite joint
limits, clipped 50 Hz torque control, and the 100-sample hold requirement, but
does not identify whether a policy shortfall is caused by branch selection,
actuation, or stabilization. The current experiment artifacts expose outcomes
and truncation, not that mechanism-level distinction; a later trajectory
measurement of branch, saturation, joint-limit margin, and hold interruption
could discriminate those possibilities before a new intervention. It cannot
change this closure decision because both tested candidates are inferior on the
disjoint paired panel. Development measurements remain non-final, and the fixed
task-reference panel is selection-contaminated.

**Open questions:** Whether a different intervention can resolve the remaining
negative-angle constrained transients remains unresolved. The relative
contributions of branch selection, torque saturation, post-entry hold
regulation, and late PPO degradation are also unresolved; the current
measurements do not establish that any one is sufficient. The available
evidence is sufficient to reject the experiment-4 reward change and preserve
working, but not to claim the official objective or to choose a mechanism-level
intervention without a decision-changing trajectory measurement.

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Experiment 1

**Result:** The fresh PPO baseline produced a useful but not yet objective-level
policy. Checkpoint-100352 is selected as working and best-known at this
closure; checkpoint-120832 is retained as a late-training comparison control.

**Observed behavior:** The effective recipe was PPO with tanh [64, 64] policy,
learning rate 0.0003, 1024-step rollouts, batch size 64, entropy coefficient
0.01, gamma 0.99, GAE lambda 0.95, one environment, and checkpoints every
5000 steps. Training proxy success rose from zero to 0.42 at 86016 steps and
0.97 at 100352, then remained around 0.94-0.95 through 120832 while reward
fell from 163.85 at 86016 to 112.02 at 120832. Checkpoint-100352 achieved
97/100 and 194/200 on the two research panels (291/300 pooled, 97%); its
failures included repeated no-reach cases and short holds concentrated near
angles about -122 to -148 degrees. It achieved 98% on the reused
task-reference-v1 panel. Checkpoint-120832 achieved 96/100 and 192/200 on the
research panels (288/300 pooled, 96%) and 97% on task-reference-v1, with
additional severe hold-interruption behavior on the measured panels.

**Hypothesis assessment:** Partially supported. The baseline established a
learned policy close to the human objective and showed that the late proxy
plateau corresponds to high task performance, but it did not establish the
98% objective. The disjoint research panel reproduced checkpoint-100352 at
97%, while checkpoint-120832 remained at 96%, so the one-success lead was
stable across the measured panels but is not evidence of a causal training
effect or official success.

**Interpretation:** Checkpoint-100352 is preferable to both the reward-peak
checkpoint-86016 and the later checkpoint-120832 for lineage purposes. The
repeated negative-angle failures, including task-reference failures at roughly
-116 to -128 degrees, show a real residual coverage problem rather than a
purely random isolated miss. The frozen model's full-angular task requirement
and its branch/joint-limit ambiguity make that geometry scientifically relevant,
but the measurements do not expose enough joint or actuator state to assign a
physical cause. The lower success and much larger interruption counts at
120832 argue against selecting the final checkpoint merely because it trained
longer. Since the best independent development result is 194/200, the evidence
does not justify an irreversible final-benchmark request expected to reach the
goal.

**Evidence inspected:** `research/current_params.json`;
`research/checkpoints/challengers/6d88dae6-5b36-4a77-8dbd-d65d20a64732/experiment-1/parameters.json`;
`research/checkpoints/challengers/6d88dae6-5b36-4a77-8dbd-d65d20a64732/experiment-1/inventory.json`;
`research/training_logs/6d88dae6-5b36-4a77-8dbd-d65d20a64732/experiment-1-attempt-1.log`;
the five `research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-*.json`
artifacts; and the three `research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/task-reference-*.json`
artifacts.

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Experiment 2

**Result:** Transfer training with the official 0.06-0.20 m target-radius
range did not demonstrate an improvement over the prior working lineage.
Checkpoint-105472 remains a useful measured alternative, but checkpoint-100352
remains working and best-known. The evidence does not justify a final-benchmark
request.

**Observed behavior:** Checkpoints 25600, 105472, and 120832 each scored
199/200 on the seed-5000 selection panel, with zero discordant outcomes among
the three pairwise comparisons. The selected checkpoint-105472 scored 195/200
on disjoint seed 6000, exactly matching checkpoint-100352 with zero discordant
episodes. The five shared failures were all negative-angle targets. For
checkpoint-105472, all ended on the open branch after one switch, with
99.6-100% saturated control and negative minimum joint-limit margin; three
were no-reach outcomes and two reached for only one hold step. Two failed
targets were below 14 cm and three were within the former 14-20 cm training
range.

**Hypothesis assessment:** Weakened. The expanded-radius transfer preserved
high success on the selection panel but did not reduce the shared failures on
the disjoint paired panel. Because the disjoint result was equal rather than
degraded, the intervention is not shown harmful; because the selected panel
was used for candidate selection and only one disjoint panel tested the
lineage, a smaller or panel-dependent coverage benefit is not ruled out.
The failures above the former radius floor also show that radius coverage
alone cannot explain the residual shortfall.

**Interpretation:** The frozen scientific model makes branch ambiguity,
joint-limit proximity, clipped torque control, and uninterrupted 2-second
stabilization physically relevant distinctions, but it does not assign policy
causation. The realized diagnostics show a common constrained transient
signature across the expanded-radius and prior policies, which weakens a
late-training-only explanation and does not support treating radius coverage
as the sufficient remedy. The working lineage is therefore preserved on its
broader independent evidence; the expanded-radius checkpoint is retained for
future comparison or targeted continuation. No additional saved-policy
measurement is expected to change this closure decision.

**Evidence inspected:** `research/brief.md`;
`research/current_params.json`;
`research/checkpoints/challengers/6d88dae6-5b36-4a77-8dbd-d65d20a64732/experiment-2/inventory.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-2-checkpoint-25600-200ep-seed5000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-2-checkpoint-105472-200ep-seed5000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-2-checkpoint-105472-200ep-seed6000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-2-working-200ep-seed6000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-2-checkpoint-120832-200ep-seed5000-4d866fbb9128.json`.

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Experiment 3

**Result:** The transferred joint-limit barrier did not improve the working
policy. Checkpoint-105472 and checkpoint-120832 each scored 196/200 on the
seed-7000 panel, versus 198/200 for working. Working remains the selected
working and best-known lineage; the barrier recipe is not retained.

**Observed behavior:** Each barrier candidate had four failures and working had
two. Both barrier candidates failed on the same working episodes 30 and 155,
while checkpoint-105472 additionally failed episodes 160 and 174 and
checkpoint-120832 additionally failed episodes 82 and 93. The paired
comparisons had zero candidate wins and two working wins for each candidate.
The proxy-peak barrier checkpoint had training success 1.00; the final
checkpoint had 0.96. The artifacts expose episode success, truncation, steps,
and reward totals, but reward totals cannot be compared across this reward
change.

**Hypothesis assessment:** Weakened. The barrier did not reduce the measured
failure count or improve paired outcomes; both candidates lost one percentage
point to working on the disjoint panel. This conclusion is scoped to the
transferred barrier recipe, its checkpoints, and the seed-7000 panel. It does
not disprove that another limit-aware or control-focused intervention could
help, and the development result does not establish the official objective.

**Interpretation:** The frozen model makes joint limits, two inverse-kinematic
branches, clipped torque control, and uninterrupted hold physically relevant,
but it cannot establish policy causation. The new paired measurements already
answer the closure question: the changed reward has no evidence of improving
the selected lineage and adds distinct failures, so another saved-policy panel
would not change the decision to keep working and revert the barrier recipe.

**Evidence inspected:** `research/brief.md`;
`research/scientific_model.md`;
`research/results.jsonl`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-3-checkpoint-105472-200ep-seed7000-7a148b2db3b3.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-3-checkpoint-120832-200ep-seed7000-7a148b2db3b3.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-3-working-200ep-seed7000-7a148b2db3b3.json`.

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Experiment 4

**Result:** The partial hold-credit forfeiture did not improve the working
lineage. Checkpoint-105472 scored 179/200 and checkpoint-120832 scored 191/200
on the disjoint seed-8000 panel, while working scored 197/200. Working remains
the selected working and best-known lineage, and the experiment-4 reward recipe
should be reverted.

**Observed behavior:** The only scientific change was increasing
`HOLD_EXIT_FORFEIT_FRACTION` from 0.0 to 0.5; the target-radius range and PPO
parameters were unchanged. The proxy-peak candidate had 1.00 training success
but 21/200 measured failures. The late candidate had 0.97 training success and
9/200 failures, while working had 3/200 failures. All measured failures were
500-step truncations. Paired comparisons gave 0 candidate wins versus 18
working wins for checkpoint-105472, and 0 versus 6 for checkpoint-120832.

**Hypothesis assessment:** Weakened. The prediction that partial forfeiture
would reduce hold-related failures or improve complete reach-and-hold success
was not supported on the disjoint panel; both candidates were worse than
working, including the late checkpoint where any benefit was expected to
survive. This conclusion is scoped to the tested reward change, checkpoints,
and panel; it does not identify the physical cause of the remaining failures
or disprove other control or stabilization interventions.

**Interpretation:** The model's branch ambiguity, joint limits, clipped
actuation, and sampled 100-step hold semantics make several failure mechanisms
physically plausible, but they do not establish what either policy did. The
experiment-4 outcome is already sufficient for the lineage decision: another
ordinary saved-policy panel could alter uncertainty about the size of the
regression but is not expected to make either inferior candidate preferable.
A future intervention should first use trajectory-level measurements if its
choice depends on separating branch selection, saturation, limit proximity,
and post-entry regulation. The development evidence remains below a justified
official-benchmark request.

**Evidence inspected:** `research/brief.md`;
`research/scientific_model.md`;
`research/results.jsonl`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-4-checkpoint-105472-200ep-seed8000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-4-checkpoint-120832-200ep-seed8000-4d866fbb9128.json`;
`research/evaluations/6d88dae6-5b36-4a77-8dbd-d65d20a64732/evaluation-6d88dae6-5b36-4a77-8dbd-d65d20a64732-experiment-4-working-200ep-seed8000-4d866fbb9128.json`.
