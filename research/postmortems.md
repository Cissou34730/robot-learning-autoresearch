# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The baseline learned a substantial reach-and-hold behavior,
but its remaining failures are structured rather than random hold noise. On the
disjoint 22000--22199 panel, the saved parent succeeded on 194/200 episodes
(97.0%), while the radius-expanded checkpoints at 105472 and 120832 each
succeeded on 193/200. On the independent telemetry panel, all three policies
succeeded on 197/200, but they failed on the same three target identities in the
negative-angle sector. Across the four distinct research panels, the parent
achieved 781/800 (97.6%) and each measured experiment-2 checkpoint achieved
390/400 (97.5%). The radius expansion did not produce a reproducible improvement.

**Lessons and limits:** The telemetry shows that every episode that entered
tolerance used the elbow-open branch at entry; it does not rule out earlier
branch transients or prove branch choice is causal. Failure episodes did not have
a consistent excess endpoint speed at entry, while their actuator commands were
at saturation for essentially the full truncated horizon and their minimum
planar Jacobian determinants were lower than the successful episodes in this
panel. These are mechanistic associations, not intervention evidence: the
conditioning minimum can be a consequence of the failed trajectory, and the
saturation count does not identify which joint or whether saturation caused the
loss of stabilization. The parent remains the strongest defensible working
policy, but its pooled development result is below the objective and no
development panel establishes the official result.

**Open questions:** Whether low-Jacobian configurations initiate the persistent
failure or arise from an already unstable trajectory; whether prolonged actuator
saturation is a controller limitation, a consequence of the target geometry, or
both; whether branch switching occurs before tolerance entry; and whether the
current observation and torque representation can support reliable local
stabilization without sacrificing the rest of the target distribution.

**Active inquiry:** Carry forward the unresolved negative-angle failures as a
conditioning-and-stabilization problem rather than a radius-coverage problem.
The common failure identities, persistent saturation, and conditioning
association justify testing a future policy that can arrest motion and maintain
the tolerance hold in these configurations. Evidence of reduced saturation and
failure-sector loss without regressions elsewhere would support that mechanism;
unchanged failures despite altered transient control would redirect attention to
observability or branch transients. Until such evidence exists, the campaign
should preserve the parent as the working and best-known policy without claiming
objective attainment.

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
