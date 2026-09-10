# Research postmortems

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Scientific strategy

**Direction:** Broadening training radii below 14 cm is retained as a promising
but incomplete direction. The experiment-2 checkpoint-100352 is the practical
parent for a focused follow-up on the remaining negative-angle failures,
especially the short-radius cases, rather than a speculative method change.
The evidence does not establish that radius coverage alone caused the gain or
that the training-proxy decline caused task degradation.

**Lessons and limits:** On the identical 200-episode development
task-reference panel, experiment-2 checkpoint-100352 scored 98.5% (197/200),
checkpoint-105472 scored 98% (196/200), and checkpoint-120832 scored 98.5%
(197/200). Relative to the experiment-1 parent checkpoint-100352 at 98%
(196/200), the experiment-2 parent-horizon policy repaired two prior failures
(episodes 0 and 10), retained failures at episodes 84 and 102, and added one
failure at episode 175. The remaining failures were all negative-angle targets:
9.9 and 9.4 cm at about -123 and -128 degrees, plus an 18.2 cm target at about
-155 degrees. Thus the expected short-radius improvement and at-least-parent
overall success were observed, while the no-material-far-target-regression
condition was only partially met. This supports the broadened recipe as useful
under the tested transfer and run conditions, not a causal claim about the
radius distribution. The proxy peak at 105472 was not the strongest measured
policy, and the final proxy decline to 0.94 did not lower total task success
relative to checkpoint-100352; proxy ranking and late-proxy behavior therefore
remain insufficient for task claims. All measurements are development-panel
evidence, not the official result.

**Open questions:** Can targeted training coverage or another intervention
remove the persistent negative-angle failures without trading away far-target
success? Is the episode-175 failure a genuine far-target geometry weakness or
panel-specific variability? Does the 98.5% development result transfer to the
separate official panel? The single transfer run and fixed panel do not isolate
the causal contribution of radius broadening from continued training.

**Conditional next steps:** Continue from experiment-2 checkpoint-100352 with
the broadened-radius recipe and target the observed negative-angle/radius
region, while keeping the protected task unchanged. If a focused development
measurement removes the residual failures without a new far-target loss,
terminal assessment becomes reasonable; if the same cluster persists, pursue
geometry-aware coverage or control changes rather than further proxy-driven
checkpoint selection. Do not treat the current development score as official
confirmation.

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Experiment 1

**Result:** The fresh PPO baseline produced a near-target policy. The measured
checkpoint-100352 is the best available candidate at 98% on the protected
development panel, but the experiment does not itself establish the official
objective.

**Observed behavior:** Training success rose from 0 through 70,656 steps to
0.93 at 95,232 and 0.97 at 100,352, then ended at 0.95 at 120,832
(`research/results.jsonl` and
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1-attempt-1.log`).
The task-reference measurements scored checkpoint-95232 at 96% (192/200),
checkpoint-100352 at 98% (196/200), and checkpoint-120832 at 97% (194/200).
The four checkpoint-100352 failures were episodes 0, 10, 84, and 102; their
target radii were 6.7, 7.2, 9.9, and 9.4 cm and their target angles were
-116.4, -125.4, -122.9, and -127.9 degrees. All four truncated rather than
completing the hold. The later checkpoint retained those four failures and
added failures at approximately -132.4 and 169.1 degrees.

**Hypothesis assessment:** Partially supported. The baseline's implicit
expected observation—that the highest training-proxy checkpoint would be a
strong task candidate—matched the ranking of the three measured checkpoints,
and that checkpoint reached the 98% development-panel threshold. The
contradicting signal is that the final checkpoint fell to 97% despite similar
training success, and that four failures remained clustered in a short-radius
sector. These results show checkpoint selection and a near-target outcome, not
that the proxy caused task progress, that late training caused the decline, or
that the policy reaches 98% on the official panel.

**Interpretation:** The baseline demonstrates substantial learned reach-and-hold
behavior and identifies checkpoint-100352 as the practical parent for the next
investigation. The residual failures are consistent with insufficient training
coverage below 14 cm and with a geometry-specific weakness, but the fixed
200-episode panel and single training run cannot distinguish those explanations
or support causal attribution.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1-attempt-1.log`;
`research/checkpoints/challengers/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-1/inventory.json`;
the three task-reference artifacts under
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/`; and
`robot_learning/scenario/environment.py`.

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Experiment 2

**Result:** Broadening training target radii from 14-20 cm to 6-20 cm produced
a partial improvement on the fixed development panel. The
parent-horizon checkpoint-100352 is the strongest measured experiment-2
candidate at 98.5% (197/200), but it still has three negative-angle failures
and does not establish the official objective.

**Observed behavior:** Checkpoint-100352 repaired experiment-1 parent failures
at episodes 0 and 10, retained failures at episodes 84 and 102, and added a
failure at episode 175 (9.9, 9.4, and 18.2 cm; approximately -123, -128, and
-155 degrees); all three episodes truncated at 500 steps. Checkpoint-105472
failed at episodes 0, 84, 102, and 175 for 98%, while checkpoint-120832 had
the same three failures as checkpoint-100352 for 98.5%. The training log
peaked at 1.0 success at 105472 steps and ended at 0.94, but the measured
task ranking favored checkpoint-100352 and checkpoint-120832.

**Hypothesis assessment:** Partially supported. The expected observation was
partly present: short-radius failures decreased from four to two at the
parent-horizon checkpoint, and overall success exceeded the parent's 98% on
the same development panel. The contradicting observation was also partly
present: one far-target failure appeared, and the negative-angle cluster
persisted. The result is consistent with a useful broadened-coverage recipe
under this transfer run, but the single run and fixed panel cannot attribute
the change specifically to radius coverage or establish generalization to the
official task.

**Interpretation:** The intervention likely moved the residual error pattern
from an exclusively short-radius cluster toward a persistent negative-angle
weakness with one far-radius case. That makes targeted geometry/angle coverage
a stronger next investigation than more proxy-ranked checkpoint selection.
The equal task score of checkpoint-120832 despite its lower training proxy
also weakens any claim that the late proxy decline directly caused task
degradation.

**Evidence inspected:** `research/results.jsonl`;
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-2-attempt-1.log`;
`research/checkpoints/challengers/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-2/inventory.json`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-2-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-2-checkpoint-105472-task-reference-v1.json`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-2-checkpoint-120832-task-reference-v1.json`;
and `robot_learning/scenario/environment.py`.
