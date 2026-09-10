# Research postmortems

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Scientific strategy

**Direction:** The broadened 6-20 cm radius recipe remains the strongest
development direction, while focused angle reweighting and the tested
geometry-feature representation are both deprioritized. Experiment 4's fresh
14-feature policy regressed broadly on the task-reference panel, so the
experiment-2 checkpoint-100352 policy and complete recipe should remain the
working and best-known lineage. A further experiment should require a concrete
geometry-aware control mechanism or an explicit preservation mechanism, not
another proxy-driven weighting or unvalidated representation expansion.

**Lessons and limits:** On the same 200-episode development task-reference
panel, experiment-2 checkpoint-100352 scored 98.5% (197/200). Experiment 3
scored 94.5%, 93.5%, and 94.5% at 100352, 105472, and 120832 steps. Experiment
4 scored only 58.0% (116/200) at 100352 and 57.5% (115/200) at 120832. At the
experiment-4 parent horizon, all three experiment-2 failures persisted and 81
new failures appeared; the failures covered both short and far radii and both
negative and nonnegative angles. The final checkpoint had 85 failures versus
84 at 100352, with 78 failures shared between the two checkpoints. Every
experiment-4 failure truncated at 500 steps. These are observations, not proof
that the three added features alone caused the regression: the run was fresh
and the task-reference panel was repeated. The high 0.21 training proxy at
120832 therefore did not support task progress, and proxy ranking remains
insufficient for task claims. All measurements are development evidence, not
official validation.

**Open questions:** Is the persistent approximately 1.0-1.2 cm truncation
behavior a geometry-specific control limitation, a representation limitation,
or partly a panel artifact? Can a concrete control change repair the residual
negative-angle cases while preserving the broadened-radius policy's behavior?
Does the retained 98.5% development result transfer to the separate official
panel? The fresh experiment-4 regression does not isolate representation from
optimization variance or establish a causal explanation for the failure.

**Conditional next steps:** Restore and retain the experiment-2 policy; do not
request terminal assessment from the experiment-4 result. Do not run another
angle-reweighting or feature-append experiment solely from the current
evidence. If a specific geometry-aware control intervention with a credible
preservation mechanism is identified, test it from the retained broadened-radius
lineage with the protected task unchanged. Otherwise, use the retained policy
for a deliberate panel-transfer investigation rather than treating 98.5% as
official confirmation. Terminal assessment should remain conditional on a
measured policy at least matching the parent while removing the residual
cluster without new broad regressions.

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

## 7ab511e1-b514-43a0-891b-e3e4cdaff4d8 / Experiment 4

**Result:** The added target-radius and periodic-angle observation features
were strongly contradicted on the development task-reference panel. Neither
measured checkpoint approached the experiment-2 parent, so the experiment-2
checkpoint-100352 policy remains working and best-known.

**Observed behavior:** The task-reference panel measured experiment-4
checkpoint-100352 at 58.0% (116/200) and checkpoint-120832 at 57.5%
(115/200). At 100352 steps, all three parent failures at episodes 84, 102,
and 175 persisted and 81 additional failures appeared. The failures spanned
39 targets below 14 cm and 45 targets at or above 14 cm, as well as 48
negative-angle and 36 nonnegative-angle targets. At 120832 steps there were
85 failures, including 40 short-radius and 45 far-radius cases; 78 failures
were shared with the 100352-step checkpoint. Every failure in both
measurements truncated at 500 steps. The training proxy nevertheless reached
0.21 at 120832 steps, matching the reported final proxy peak.

**Hypothesis assessment:** Contradicted under this fresh training run and
repeated development panel. The expected observation was at least 98.5%
success, removal of parent failures at episodes 84 and 102, and no added
far-target failures. Success instead fell to 58.0% and 57.5%, all parent
failures remained, and broad failures appeared across the task geometry. This
strongly weakens the tested representation recipe, but the fresh run and
single panel do not establish that the appended features alone caused the
regression.

**Interpretation:** The result is a broad failure of the tested fresh
representation recipe rather than a selective repair of the residual geometry
cluster. The discrepancy between the 0.21 training proxy and approximately
58% measured task success further confirms that the proxy cannot establish
policy progress here. Optimization variability, feature scaling or semantics,
and other fresh-run effects remain possible explanations; no one is isolated
by this experiment.

**Evidence inspected:** `research/results.jsonl`;
`research/brief.md`;
`research/training_logs/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/experiment-4-attempt-1.log`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-4-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-4-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/7ab511e1-b514-43a0-891b-e3e4cdaff4d8/task-reference-7ab511e1-b514-43a0-891b-e3e4cdaff4d8-experiment-2-checkpoint-100352-task-reference-v1.json`;
and `robot_learning/scenario/observations.py`.
