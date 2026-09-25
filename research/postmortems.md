# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The baseline learned a substantial reach-and-hold behavior,
but its remaining failures are structured rather than random hold noise. On both
disjoint research panels, checkpoint-100352 and checkpoint-120832 each succeeded
on 195/200 episodes, while the protected task-reference panel measured the
working checkpoint at 196/200. The detailed diagnostics place the repeated
failures in a narrow negative-angle sector around -128 to -155 degrees. They
include both episodes that never enter tolerance and episodes that enter for only
one to three steps. The baseline training distribution is also narrower than the
human distribution: `training_environment.py` trained only on radii 0.14--0.20 m,
whereas the task spans 0.06--0.20 m. This is an untested distribution-coverage
mechanism, not an established cause of the angular failure sector.

**Lessons and limits:** The measurements support the physical interpretation that
branch choice, configuration-dependent conditioning, approach dynamics, and
stabilization can create target-specific failures, but they do not identify the
causal controller mechanism. The late checkpoints usually reach tolerance and
then hold successfully; the failure sector is the limiting behavior observed
here. The failed research targets span roughly 0.10--0.17 m as well as a
near-0.14 m case, so radius coverage is plausible but not sufficient as an
explanation. Both disjoint research panels are 97.5%, below the 98% objective;
the protected panel is development evidence and neither panel is the official
final assessment.

**Open questions:** Whether broader radius coverage changes the negative-angle
failure sector or only improves inner-target behavior; whether the no-entry and
interrupted-hold failures share a mechanism; whether branch choice, approach
dynamics, or local stabilization is causal; whether a future policy can eliminate
the sector without sacrificing the rest of the target distribution; and how much
of the remaining error is intrinsic to the current observation and control
representation.

**Active inquiry:** Test whether the baseline's radius-limited training
distribution left insufficient experience for the configurations associated with
the repeated negative-angle failures. Continue the working policy while exposing
training to the complete 0.06--0.20 m radius range, then compare complete
reach-and-hold outcomes and failure diagnostics against the saved working
lineage on disjoint episodes. A reduction of both no-entry and interrupted-hold
failures without loss elsewhere would support a coverage mechanism; unchanged
angular failures would redirect attention to branch conditioning, approach
dynamics, or stabilization. The current working checkpoint remains a strong
near-objective baseline, not demonstrated objective attainment.

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
