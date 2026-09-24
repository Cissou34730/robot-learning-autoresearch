# Research postmortems

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Scientific strategy

**Current synthesis:** The working 100352-step PPO policy remains the best
supported lineage at 682/700 (97.4%) over four distinct research panels; the
retained 120832-step policy has 484/500 (96.8%). The experiment-2
105472-step candidate scored 199/200 on its selection panel and 195/200 on a
disjoint panel, exactly matching the prior working policy in a paired
comparison with zero discordant episodes. The selection-panel score is not
independent evidence, so the radius-expanded candidate does not justify
replacing the working or best-known lineage.

**Lessons and limits:** Expanding training radii from 0.14-0.20 m to the
official 0.06-0.20 m range produced no measured improvement over the prior
lineage. On the disjoint panel, both policies failed the same five
negative-angle episodes; the failures ended on the open branch after one
switch, with at least 99.6% saturated control and negative joint-limit
margin. Two episodes briefly reached the target for one hold step and three
did not reach, and three of the five failed targets were within the old
training range. The frozen model establishes branch ambiguity, joint limits,
clipped 50 Hz torque control, and the 100-sample hold requirement, but it does
not establish which of branch selection, actuation, or stabilization caused
the observed failures. The fixed task-reference panel remains
selection-contaminated and development measurements remain non-final.

**Open questions:** The radius-only explanation is weakened but not
eliminated; the shared branch-switch, saturation, and limit-margin signature
leaves branch choice, constrained transient control, and hold stabilization
unresolved. The measurements support retaining a reusable expanded-radius
candidate, but another saved-policy panel would not distinguish those causes
or change the present lineage decision.

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
