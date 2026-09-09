# Research postmortems

## 3f02f914-505c-481f-b995-e040c009974f / Scientific strategy

**Direction:** Establish a reliable policy for the full 6-20 cm official target
distribution, then address the residual failures concentrated at near targets.
The baseline provides no intervention control, so no mechanism is eliminated yet;
it does show that a high training proxy alone is not sufficient to select a
robust late checkpoint.

**Lessons and limits:** The baseline task-reference panel measured
checkpoint-100352 and checkpoint-110592 at 196/200 successes (98%), while the
final checkpoint measured 194/200 (97%). The four failures shared by the first
two checkpoints were all truncated at 500 steps and had radii 6.7-9.9 cm with
angles -116 to -128 degrees. This is development-panel evidence, not official
benchmark evidence, and the repeated panel is not independent confirmation.
Training used radii 14-20 cm (`robot_learning/scenario/environment.py`) while
the reference task covers 6-20 cm, so the near-target pattern is consistent
with a training-distribution gap, but the baseline cannot establish causality.
Training success and reward are proxies: the log reached a 0.97 proxy at
100352 steps, fell to 0.93 at 110592, and ended at 0.95, without proving task
progress.

**Open questions:** Does training on the full official radial range remove the
near-target failures without sacrificing performance at 14-20 cm? Are the
additional final-checkpoint failures transient PPO drift or evidence of a
broader robustness problem? The current fixed panel is too small and repeated
to establish generalization or seed variance.

**Conditional next steps:** Use checkpoint-100352 as the working and best-known
policy for the next experiment. Prefer a targeted change that exposes training
to the missing 6-14 cm radial region, retaining the official task and hold
semantics; compare task success and the same failure geometry before attributing
an improvement to that change. If a later candidate clearly exceeds the
development threshold with no new concentrated failures, consider official
assessment; otherwise continue targeted robustness work.

## 3f02f914-505c-481f-b995-e040c009974f / Experiment 1

**Result:** The baseline reached the development threshold at checkpoints
100352 and 110592, but the final checkpoint regressed below it; checkpoint
100352 is selected as the working and best-known policy.

**Observed behavior:** The automatic baseline trained 120,832 steps. The
task-reference-v1 panel used 200 deterministic episodes with seed 7300:
checkpoint-100352 and checkpoint-110592 each achieved 98.0% (196/200), and
checkpoint-120832 achieved 97.0% (194/200). Checkpoints 100352 and 110592
failed on the same episodes (0, 10, 84, 102); each failure truncated at 500
steps. The final checkpoint retained those four failures and added episodes
121 and 152. The shared failures had target radii 6.7, 7.2, 9.9, and 9.4 cm
and angles from -128 to -116 degrees. The training log's proxy success rose
from 0 through 70,656 steps to 0.97 at 100,352, then varied between 0.93 and
0.96 through the end; these are training measurements, not task-reference
results.

**Hypothesis assessment:** The baseline proposal snapshot supplied no
intervention-specific `expected_observation` or `contradicting_observation`;
the relevant baseline expectation was to establish an initial measured policy
for the human-defined objective. That expectation is **partially supported**:
two intermediate checkpoints met 98% on the fixed development panel, but the
final checkpoint did not, and no checkpoint has official benchmark status.
The result is therefore insufficient to claim stable attainment of the 98%
campaign objective or to attribute the outcome to any scientific mechanism.

**Interpretation:** The best measured task behavior occurs before the final
training checkpoint, so selecting by training proxy and continuing unchanged
is not justified by this run. The concentration of failures below 10 cm is
consistent with the training environment's 14-20 cm radial range, making
full-range target exposure a useful next hypothesis. This is an interpretation
of one baseline and one repeated development panel, not a causal conclusion.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/3f02f914-505c-481f-b995-e040c009974f/experiment-1-attempt-1.log`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-110592-task-reference-v1.json`;
`research/evaluations/3f02f914-505c-481f-b995-e040c009974f/task-reference-3f02f914-505c-481f-b995-e040c009974f-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/checkpoints/challengers/3f02f914-505c-481f-b995-e040c009974f/experiment-1/inventory.json`;
`robot_learning/scenario/environment.py`;
`robot_learning/scenario/evaluation.py`.
