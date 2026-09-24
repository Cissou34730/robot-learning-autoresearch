# Research postmortems

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Scientific strategy

**Current synthesis:** The working 100352-step PPO policy remains the strongest
supported lineage at 880/900 (97.8%) over five distinct research panels. The
expanded-radius transfer matched working on its disjoint panel, and the
joint-limit barrier did not improve it: both measured barrier checkpoints scored
196/200 on the new seed-7000 panel, while working scored 198/200. The evidence
therefore supports working as the current lineage and best-known designation,
but does not establish objective-level performance.

**Lessons and limits:** The barrier candidates shared working's failures at
episodes 30 and 155 and added distinct failures (episodes 160 and 174 for
checkpoint-105472; 82 and 93 for checkpoint-120832). These evaluation artifacts
report all failures as 500-step truncations; reward totals are not comparable
across the changed reward. Training proxies likewise did not predict an
improvement: the proxy-peak checkpoint reached 1.00, while the late checkpoint
fell to 0.96. The frozen model establishes branch ambiguity, finite joint
limits, clipped 50 Hz torque control, and the 100-sample hold requirement, but
does not identify whether the observed shortfall is caused by branch selection,
actuation, or stabilization. Realized measurements do show constrained
negative-angle transients with saturation, limit proximity, no-reach outcomes,
and interrupted holds, but these signatures do not establish a sufficient
cause. Development measurements remain non-final, and the fixed task-reference
panel is selection-contaminated.

**Open questions:** Whether a different intervention can resolve the remaining
negative-angle constrained transients remains unresolved. The relative
contributions of branch selection, torque saturation, post-entry hold
regulation, and late PPO degradation are also unresolved; the current
measurements do not establish that any one is sufficient. The available
evidence is sufficient to distinguish the current lineage choice from the
unresolved mechanism questions, but not to claim the official objective.

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
