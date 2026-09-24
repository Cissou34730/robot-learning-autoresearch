# Research postmortems

## 6d88dae6-5b36-4a77-8dbd-d65d20a64732 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong reach-and-hold
policy, but current evidence remains below the 98% campaign objective. The
checkpoint at 100352 steps is the most useful policy: it achieved 97% on each
of two research panels covering 300 distinct episodes, whereas the later
120832-step checkpoint achieved 96% on both panels and showed substantially more
hold interruptions. The 98% result for checkpoint-100352 on the fixed
task-reference panel is not independent confirmation because that panel was
used in selecting the candidate. The remaining failures are concentrated in a
negative-angle sector, with both no-reach and short-hold outcomes; this is
consistent with an orientation-specific control problem, but the available
measurements do not identify branch, joint-limit, saturation, or dynamic
stabilization as its cause.

**Lessons and limits:** Training reward and proxy success were useful for
locating candidates but did not rank final behavior reliably: the reward peak
at checkpoint-86016 measured 96%, and the later proxy plateau did not improve
the selected policy. The disjoint research panel reproduced the 100352-step
policy's 97% result and its advantage over checkpoint-120832, supporting the
working-lineage choice but not the official objective. In the frozen scientific
model, full-angle sampling, inverse-kinematic branch ambiguity, and
torque-driven 50 Hz control make orientation, posture, and stabilization
plausible distinctions; the model alone cannot establish which occurred in a
failed episode. The task-reference panel is fixed and permanently reused, so
its 196/200 result is development evidence rather than independent confirmation.

**Open questions:** Whether the negative-angle failures arise from an
inadmissible or poorly selected inverse-kinematic branch, a joint-limit or
actuation limitation, or learned feedback that fails to stabilize remains
unresolved. It is also unresolved whether targeted training or a changed
measurement instrumentation would improve this sector without repeating the
late-checkpoint instability.

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
