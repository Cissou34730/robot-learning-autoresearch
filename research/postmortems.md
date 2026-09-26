# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The learned parent has substantial reach-and-hold
competence but remains a near-objective policy rather than an established
98% solution. It achieved 1752/1800 across nine distinct research panels.
The reward intervention produced 176/200 and 186/200 challengers, and the
periodic-observation intervention produced 41/200 and 53/200 challengers;
neither intervention produced a paired win over the parent. Experiment 5's
two action-headroom checkpoints each achieved 391/400 on two fresh panels,
versus 390/400 for the parent on those same panels. The gain was one rescued
episode on the first panel and zero on the second, while the recurring failure
identities remained.

**Lessons and limits:** Radius expansion did not remove the shared
negative-angle failure identities, and reward changes regressed complete task
behavior. The corrected experiment-5 evaluator shows that the 0.9 map removes
physical command saturation, but the five failures on episodes 28000-28199
are shared by the parent and both headroom checkpoints. The candidates also
have slightly lower minimum Jacobian determinants and later entry on average,
so the absence of saturation does not make the trajectories recoverable.
The one-episode pooled gain is not reproduced on the second panel, and the
100352- and 105472-step candidates add no distinguishable task outcome.
Saturation is therefore a marker or contributor at most, not an established
sufficient cause. Adding sine/cosine encodings to the wrapped branch errors
caused severe broad degradation in a fresh policy, rejecting that tested recipe
without proving that all observation changes are unhelpful. Development panels
remain non-official, and the parent has not established the human objective on
the final benchmark.

**Open questions:** Which configuration-dependent mechanism creates the
repeatable negative-angle failures despite unchanged task mechanics: branch
transition, poor local conditioning, insufficient stabilization, or an
interaction among them. It is also unresolved whether a policy can preserve
the parent's broad approach and hold behavior while changing only that
failure-sector behavior.

**Active inquiry:** The persistent failure sector is more consistent with a
configuration- or branch-dependent control limitation than with actuator
clipping alone: eliminating measured physical saturation did not remove the
shared failures, and continued headroom training added no further benefit.
Evidence that changes the failure identities while preserving complete
reach-and-hold behavior would support a conditioning or branch-transition
explanation; repeated shared failures under such controls would require
revising that interpretation rather than treating saturation as causal.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 1

**Result:** The baseline produced a reproducible near-objective policy but did not
demonstrate the 98% objective. Checkpoint-100352 is selected as the working and
best-known lineage; checkpoint-120832 is retained as a measured alternative.

**Observed behavior:** Checkpoint-100352 and checkpoint-120832 each achieved
195/200 (97.5%) on both disjoint research panels, for 390/400 pooled successes
per model. Their paired comparison had zero discordant wins across the 400
shared episode identities. The same five target situations in the second panel
formed a narrow sector near -131 to -155 degrees: two never entered tolerance,
and three reached it for only one or two steps. The protected task-reference
panel measured checkpoint-100352 at 196/200 and checkpoint-120832 at 194/200;
the former is exactly at the threshold on that development panel, but the
disjoint research results do not reproduce 98%.

**Hypothesis assessment:** The hypothesis that the proxy-peak checkpoint would
reproducibly meet the complete objective is weakened: it reproducibly exhibits
strong reach-and-hold behavior, but both independent research panels remain one
episode below the 98% threshold. The hypothesis that it is preferable to the
final checkpoint is inconclusive on paired outcomes, although checkpoint-100352
has the stronger protected-panel result and no evidence favors the final
checkpoint. These conclusions are limited to this deterministic task,
observation contract, and measured checkpoints.

**Interpretation:** The failure pattern is stable across checkpoints and research
panels, making it more consistent with a target-geometry or controller
interaction than with training-proxy noise. The measurements do not establish
whether branch selection, Jacobian conditioning, approach velocity, or local
stabilization is causal. Selecting checkpoint-100352 preserves the strongest
available development result without claiming that the official objective has
been reached; retaining checkpoint-120832 preserves a nearly identical late
policy for future comparison.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-200ep-seed20000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-200ep-seed20000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-200ep-seed21000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-200ep-seed21000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/task-reference-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/task-reference-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-1-checkpoint-120832-task-reference-v1.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 2

**Result:** Expanding training target radii from 0.14--0.20 m to the complete
0.06--0.20 m range did not improve the measured policy lineage. The parent
achieved 194/200 on the first disjoint panel and 197/200 on the telemetry panel;
both measured continuation checkpoints achieved 193/200 and 197/200,
respectively. The parent remains working and best-known. The radius-expanded
checkpoints are retained as measured alternatives, and the scientific recipe is
reverted to the parent recipe.

**Observed behavior:** The first disjoint panel preserved the negative-angle
failure sector, with both no-entry and interrupted-hold failures. On the
telemetry panel, all three policies failed on the same episodes (35, 67, and
150), all near -144 to -153 degrees. Every episode that entered tolerance was
closer to the elbow-open inverse-kinematic branch than the folded branch at
entry. Failure episodes had no consistent excess endpoint speed at entry, but
they remained actuator-saturated for about 499 of 500 control steps and showed
lower minimum planar Jacobian determinants than successful episodes in the same
panel.

**Hypothesis assessment:** The hypothesis that complete radius coverage would
reduce the recurring negative-angle failures is weakened. The continuation did
not improve the independent panel, pooled performance was 97.5% versus 97.6%
for the parent, and the common failure identities persisted. The evidence does
not establish that radius coverage has no benefit outside this failure sector.
The telemetry weakens branch-entry and entry-speed explanations as sole causes
and makes prolonged saturation in poorly conditioned trajectories a more useful
working explanation, but the association is not causal and does not identify a
single sufficient mechanism.

**Interpretation:** The intervention answered the radius question without
solving the task. The stable target identities across policies indicate a
shared geometry/controller interaction rather than random checkpoint noise.
Selecting the parent preserves the strongest accumulated development evidence;
retaining both continuation checkpoints preserves distinct policies whose
trajectory variants may be useful for future paired work without treating their
98.5% telemetry-panel result as independent objective attainment.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-working-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-105472-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-120832-200ep-seed22000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-working-200ep-seed23000-a27165d6de57.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-105472-200ep-seed23000-a27165d6de57.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-2-checkpoint-120832-200ep-seed23000-a27165d6de57.json`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 3

**Result:** Stronger action regularization and full hold-credit forfeiture did
not improve stabilization. On the paired 24000--24199 panel, the working
parent achieved 196/200, while experiment-3 checkpoint-100352 achieved
176/200 and checkpoint-120832 achieved 186/200. The parent remains working and
best-known; the experiment-3 reward recipe is rejected and the parent recipe
is restored. Both measured challengers are retained as negative controls for
future mechanism comparisons.

**Observed behavior:** The parent lost four episodes, all by failing to enter
tolerance. The 100352-step challenger lost 24 episodes: four no-entry failures
and 20 failures that entered tolerance but never sustained 100 uninterrupted
steps. The 120832-step challenger lost 14 episodes: three no-entry failures
and 11 incomplete holds. The challengers' failures extended beyond the
recurring negative-angle sector, and paired comparisons recorded zero
challenger wins against the parent.

**Hypothesis assessment:** The hypothesis that stronger action regularization
combined with full hold-credit forfeiture would reduce interrupted holds while
preserving broad reach-and-hold behavior is contradicted on this panel. The
intervention produced a large complete-task regression and more incomplete
holds, not the predicted stabilization. Because both reward terms changed
together and the policies were continued through learning, the measurements
reject the recipe as a useful intervention but do not identify which term or
learning interaction caused the regression.

**Interpretation:** The evidence does not support continuing reward shaping as
the primary explanation for the failure sector. The parent is the most
defensible lineage for subsequent work, while the two measured challengers
remain useful negative controls. The next scientific distinction is between
conditioning, branch-transition behavior, and the information or control
representation; no official objective attainment is claimed.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/checkpoints/challengers/9f1de290-24cf-4a97-8dab-6026ac343493/experiment-3/parameters.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-working-200ep-seed24000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-checkpoint-100352-200ep-seed24000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-3-checkpoint-120832-200ep-seed24000-48e4acc98c39.json`;
`robot_learning/scenario/reward.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 4

**Result:** Adding sine/cosine encodings of the four inverse-kinematic
branch-angle errors to the existing observation produced a severe complete-task
regression. The 100352-step and 120832-step candidates achieved 41/200
(20.5%) and 53/200 (26.5%) on the disjoint episodes 25000--25199 panel, while
the paired working parent achieved 196/200 (98.0%). The parent won every
discordant episode: 155 for the proxy-peak candidate and 143 for the final
candidate. The working lineage remains selected and best-known; the periodic
recipe is rejected and reverted. Both measured candidates are retained as
negative controls for the representation investigation.

**Observed behavior:** The periodic candidates did not merely preserve the
known no-entry sector. They failed on a broad set of targets where the parent
completed reach and hold, with many failures never entering tolerance and
additional trajectories entering briefly or failing to hold. Their late
checkpoint improved from 20.5% to 26.5% but remained far below the parent, so
continued training did not recover the parent's behavior within this run.

**Hypothesis assessment:** The hypothesis that periodic branch-error features
would remove negative-angle no-entry failures while preserving broad behavior
is contradicted on the paired panel. The result rejects this observation
recipe as a useful intervention and strongly weakens the claim that scalar
wrapped branch errors are the primary actionable cause. Because the policy was
trained fresh with a changed observation dimension, the result does not
identify whether optimization, feature interactions, branch selection, or
physical control dynamics caused the regression.

**Interpretation:** The parent is the only defensible continuation: it retains
the broadest measured reach-and-hold behavior and is exactly at the 98.0%
threshold on this development panel, without establishing the official
objective. The experiment rules out a broad periodic augmentation as a safe
next step, but leaves configuration-dependent control, branch-transition
dynamics, conditioning, and saturation as competing explanations. Retaining
the two measured challengers preserves a sharply negative representation
control for later mechanism comparisons without treating it as a viable
training parent.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/scientific_model.md`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-working-200ep-seed25000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-checkpoint-100352-200ep-seed25000-48e4acc98c39.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-4-checkpoint-120832-200ep-seed25000-48e4acc98c39.json`;
`robot_learning/scenario/observations.py`.

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Experiment 5

**Result:** The stateless 0.9 action-headroom map did not produce a reliable
complete-task improvement. Both measured checkpoints achieved 391/400 over
the two fresh panels, compared with 390/400 for the parent on the same
episodes. The experiment-5 recipe is reverted, the parent remains working
and best-known, and both measured headroom checkpoints are retained as
controlled alternatives.

**Observed behavior:** On episodes 27000-27199, each headroom checkpoint
rescued the parent's failure at episode 27089 and shared the parent's other
four failures. On episodes 28000-28199, the parent and both headroom
checkpoints shared all five failures: 28018, 28030, 28145, 28171, and 28194.
The corrected evaluator measured zero physical saturation steps for both
headroom checkpoints, while the parent averaged 119.3 saturation steps per
episode and its failures averaged 498.6. The headroom failures still had
near-zero minimum Jacobian determinants, delayed entry when entry occurred,
and incomplete holds. The 100352- and 105472-step checkpoints had the same
complete-task outcomes; continued adaptation did not add evidence.

**Hypothesis assessment:** The hypothesis is weakened. The intervention
successfully changed the physical command regime and removed the measured
actuator saturation signature without broad success collapse, but the expected
failure-sector recovery was not reproducible: it occurred once on the first
panel and not at all on the second. The shared failures under zero measured
saturation reject saturation as a sufficient causal explanation. The evidence
does not establish whether saturation contributes upstream to the trajectory
or is only a consequence or marker of poor conditioning.

**Interpretation:** Reducing command authority alone does not solve the
repeatable negative-angle failures. The unchanged failure identities despite
the changed physical command regime redirect the scientific inquiry toward
configuration-dependent conditioning, branch-transition behavior, and local
stabilization. The parent is the safer working lineage because the headroom
mapping adds no reliable task benefit, while both checkpoints remain useful
controlled alternatives for later comparisons.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-100352-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-105472-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-working-200ep-seed27000-6f556e2004f1.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-100352-200ep-seed28000-238ccfe3776f.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-checkpoint-105472-200ep-seed28000-238ccfe3776f.json`;
`research/evaluations/9f1de290-24cf-4a97-8dab-6026ac343493/evaluation-9f1de290-24cf-4a97-8dab-6026ac343493-experiment-5-working-200ep-seed28000-238ccfe3776f.json`;
`robot_learning/scenario/policy_io.py`;
`robot_learning/scenario/evaluation.py`.
