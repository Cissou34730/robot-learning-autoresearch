# Research postmortems

## 9f1de290-24cf-4a97-8dab-6026ac343493 / Scientific strategy

**Current synthesis:** The baseline learned a substantial reach-and-hold behavior,
but its remaining failures are structured rather than random hold noise. On the
first research panel, checkpoint-100352 and checkpoint-120832 each succeeded on
195/200 episodes, with identical binary outcomes. The protected task-reference
panel separated them: checkpoint-100352 achieved 196/200 (98.0%), while the final
checkpoint achieved 194/200 (97.0%). The detailed research diagnostics place the
proxy-peak failures in a narrow negative-angle sector around -128 to -150 degrees:
some episodes never enter tolerance and others enter for only one to three steps.
The final checkpoint does not remove this sector and has slightly larger residual
errors on the research panel.

**Lessons and limits:** The measurements support the physical interpretation that
branch choice, configuration-dependent conditioning, and stabilization can create
target-specific failures, but they do not identify the causal controller
mechanism. The late checkpoints usually reach tolerance and then hold
successfully; the failure sector is the limiting behavior observed here. One
research panel is 97.5%, below the 98% objective, while one independent
development panel is exactly 98.0%, so the available evidence does not yet make
official success an expectation. The panels are development evidence and neither
is the official final assessment.

**Open questions:** Whether the negative-angle failure sector is caused primarily
by branch or conditioning effects, approach dynamics, or local stabilization;
whether a future policy can eliminate the sector without sacrificing the rest of
the target distribution; and how much of the remaining error is intrinsic to
the current observation and control representation.

**Active inquiry:** Carry forward the distinction between broad reach-and-hold
competence and the reproducible negative-angle failure sector. This matters
because the human objective requires at least 196 successes on the official
panel, while both disjoint research panels produced 195/200 for the two viable
late checkpoints. Evidence that changes this inquiry would be a policy that
eliminates the repeated sector while preserving complete holds elsewhere; the
current evidence instead supports treating checkpoint-100352 as a strong
near-objective baseline, not as demonstrated objective attainment.

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
