# Research postmortems

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Scientific strategy

**Direction:** The broadened 6-20 cm radius recipe remains the strongest
development direction, but experiment 3 weakens angle reweighting as the next
intervention. The experiment-2 checkpoint-100352 policy and complete recipe are
restored as the working and best-known lineage. A further experiment should
address geometry-aware control or representation, or provide a concrete
mechanism for preserving the previously successful behavior, rather than
adding another proxy-driven angular weighting.

**Lessons and limits:** On the same 200-episode development task-reference
panel, experiment-2 checkpoint-100352 scored 98.5% (197/200), while experiment
3 scored 94.5% (189/200) at 100352 steps, 93.5% (187/200) at the proxy peak,
and 94.5% (189/200) at 120832 steps. The experiment-3 policies retained the
parent failures at episodes 84 and 102 in all three measurements; the
episode-175 failure was absent at 100352 and 120832 but new failures appeared
at negative, near-zero, and positive angles, including far targets around
18.5-19.8 cm. Thus the expected repair of the negative-angle sector, at-least
parent success, and no material far-target regression were not observed. The
contradicting pattern was observed: residual failures persisted and overall
success fell materially. The 105472 proxy peak was the weakest measured
candidate, while the final proxy decline had the same measured score as
100352, so proxy ranking and late-proxy behavior remain insufficient for task
claims. These are observations from one transfer run and one repeated
development panel; they weaken the tested recipe but do not isolate angular
reweighting as the causal source of degradation. All measurements remain
development evidence, not official validation.

**Open questions:** Is the persistent approximately 1.0-1.2 cm truncation
behavior a geometry-specific control or representation limitation that needs a
different intervention? Can a concrete geometry-aware change repair the
negative-angle cases while preserving the parent's far-target behavior? Are
some of the newly appearing failures panel-specific, and does the retained
98.5% development result transfer to the separate official panel? The single
transfer run cannot distinguish those explanations or establish a causal
effect of angle sampling.

**Conditional next steps:** Do not pursue another angle-reweighting run solely
from this evidence. If a specific geometry-aware control intervention is
identified, test it from the retained broadened-radius lineage with the
protected task unchanged. A representation intervention should instead use
fresh initialization when its input semantics are not compatible with the
retained policy, while using that policy as the behavioral comparator. Terminal
assessment becomes reasonable only if measured performance at least matches the
parent while removing the residual cluster without new far-target losses. If no
such concrete intervention is available, retain the experiment-2 policy and
investigate panel variability or evaluation transfer rather than treating the
current scores as official confirmation.

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

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Experiment 3

**Result:** The focused negative-angle training distribution did not improve
the selected policy on the development panel. The experiment-2
checkpoint-100352 working policy remains the strongest measured candidate, so
the experiment-3 recipe and candidates should not replace it.

**Observed behavior:** The task-reference panel measured checkpoint-100352 at
94.5% (189/200), checkpoint-105472 at 93.5% (187/200), and checkpoint-120832
at 94.5% (189/200). The parent failures at episodes 84 and 102 persisted in
all three measurements. New failures included short-radius targets at angles
near -46, -34, -20, -3, and -100 degrees, positive-angle targets, and
far-radius targets at approximately 18.5-19.8 cm. The 105472-step checkpoint
had the highest training proxy at 0.98, while the proxy was 0.95 at 100352
and 0.93 at 120832; the two latter checkpoints had equal task success.
Every measured failure truncated at 500 steps rather than completing the hold.

**Hypothesis assessment:** Contradicted under this transfer run and
development panel. The expected observation was that focused angular coverage
would remove or materially reduce the prior negative-angle failures, reach at
least the parent's 98.5%, and avoid material far-target regression. None of
those conditions held: the original sector failures persisted, total success
fell by four to five percentage points, and new failures appeared in other
angles and at far radii. This weakens the targeted-coverage hypothesis for
the tested recipe, but the single run and fixed panel do not prove that angle
reweighting alone caused the degradation.

**Interpretation:** The intervention produced broad behavioral regression
rather than selective repair of the observed failure sector. The unexpected
appearance of failures outside that sector, together with the poor proxy-ranked
checkpoint and equal scores at 100352 and 120832, further shows that training
proxy dynamics do not identify task progress here. A geometry-specific control
limitation, optimization variability, or panel effects remain plausible
alternatives.

**Evidence inspected:** `research/results.jsonl`;
`research/research_state.json`;
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-3-attempt-1.log`;
the experiment-3 checkpoint inventory under
`research/checkpoints/challengers/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-3/`;
the three experiment-3 task-reference artifacts under
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/`; and
`robot_learning/scenario/environment.py`.
