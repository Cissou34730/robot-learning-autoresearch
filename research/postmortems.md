# Research postmortems

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Scientific strategy

**Current synthesis:** The working 100352-step PPO policy remains the strongest
development lineage at 487/500 (97.4%) across three distinct research panels;
the retained 120832-step policy has 484/500 (96.8%). The latest 200-episode
panel gave both 196/200, but the same four negative-angle episodes failed for
both policies. Their trajectories all ended with one open-branch switch,
99-100% saturated control, and negative joint-limit margin; the working policy
briefly reached one target before losing its one-step hold, while the other
three were no-reach outcomes. Three targets were inside 12.4 cm, below the
current 14 cm training-radius floor.

**Lessons and limits:** The realized diagnostics make the residual shortfall
consistent with a training-coverage and limit/actuation interaction, while the
matched core signature across the lineages weakens a late-training-specific
explanation.
The frozen model establishes the full-angle, 6-20 cm official distribution,
branch ambiguity, joint limits, and clipped 50 Hz torque control, but it does
not by itself establish that radius coverage caused these failures. Development
measurements remain non-final, and the fixed task-reference panel is
selection-contaminated.

**Open questions:** Whether exposing the policy to the official inner-radius
range improves the negative-angle reach failures without harming already
covered targets remains unresolved; the 18.4 cm failure also leaves a possible
branch or actuation limitation.

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
