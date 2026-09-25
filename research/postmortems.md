# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The learned parent has substantial reach-and-hold
competence but remains a near-objective policy rather than an established
98% solution. On the fresh 24000--24199 panel it achieved 196/200, while the
matched-duration and final experiment-3 challengers achieved 176/200 and
186/200. The challengers never beat the parent on a discordant episode and
introduced failures across a much broader angle range than the parent's four
no-entry failures. The reward intervention therefore did not solve the
negative-angle limitation and degraded complete-task behavior.
Across five distinct development panels the parent is 977/1000 (97.7%), which
is strong evidence of a near-objective lineage but not an official result.

**Lessons and limits:** The experiment weakens the explanation that cheap
actions and retained partial hold credit were the main cause of the failures.
For checkpoint-100352, 20 of 24 failures entered tolerance but never completed
100 uninterrupted steps; for checkpoint-120832, 11 of 14 had that pattern,
whereas all four parent failures were no-entry cases. The paired comparison
supports rejecting this reward recipe for the active lineage, but it does not
isolate action cost from hold-credit forfeiture or from continuation and
optimization effects. Development panels remain non-official, and the parent
has not established the human objective on the final benchmark.

**Open questions:** Whether the persistent no-entry cases arise from
configuration-dependent conditioning, an unobserved branch transient, or a
limitation of the policy's state and action representation; whether the
conditioning signature is causal or a consequence of the failed trajectory;
and whether the same mechanism can be changed without sacrificing the broad
reach-and-hold behavior.

**Active inquiry:** Determine whether the remaining negative-angle no-entry
failures are caused by the controller's information and control representation
in poorly conditioned configurations, or by branch-transition dynamics that
the current policy cannot stabilize. Evidence that distinguishes these
mechanisms must improve paired complete-task outcomes without broad
regression; persistent no-entry failures or another broad hold regression
would redirect the inquiry toward the task geometry and its controller
interaction rather than reward shaping.

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
