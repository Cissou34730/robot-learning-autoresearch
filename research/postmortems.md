# Research postmortems

## c1523389-1363-42a7-b973-1bc6847ac445 / Scientific strategy

**Current synthesis:** The baseline learned the reach-and-hold behavior but did not
meet the human objective reliably. The strongest measured policy is
`checkpoint-100352`: it achieved 393/400 successes across two disjoint research
panels, while the late final checkpoint achieved 391/400. The independent second
panel put both policies at 97%, so the first-panel lead and the fixed
task-reference score are not independent confirmation of the objective.

**Lessons and limits:** The late training region is useful but has plateaued near,
not at, the 98% objective under the measured conditions. The paired comparison
favors `checkpoint-100352` by 2-0 discordant wins over the pooled panels, but the
small difference does not establish a causal explanation for the residual
failures. The 21 unmeasured checkpoints remain unmeasured rather than failed.

**Open questions:** A subsequent experiment must determine whether changing the
learning recipe or training target can remove the remaining failures without
losing the late-policy behavior. It is also unresolved whether the retained
late-plateau checkpoint is useful as a continuation alternative.

## c1523389-1363-42a7-b973-1bc6847ac445 / Experiment 1

**Result:** The fresh baseline produced a useful learned policy, but no measured
policy is ready for terminal assessment.

**Observed behavior:** `checkpoint-100352` scored 99.5% on the first 200-episode
research panel and 97.0% on the disjoint second panel, for 393/400 pooled
successes. `checkpoint-120832` scored 98.5% and 97.0%, for 391/400 pooled
successes. The paired comparison favored `checkpoint-100352` 2-0 over the
pooled 400 shared episodes. On the permanently reused task-reference panel,
the two policies scored 98.0% and 97.0%, respectively. `checkpoint-86016`
scored 95.0% on its research panel and 94.0% on the task-reference panel.

**Hypothesis assessment:** The baseline's learned-behavior expectation is
supported: late checkpoints substantially outperform the earlier reward-peak
candidate. The expectation that the first-panel lead would persist as
independent confirmation is weakened: the two late candidates tie at 97.0% on
the disjoint panel, and neither development panel declares the objective
reached. The fixed task-reference result is not independent evidence because
that panel is permanently reused.

**Interpretation:** `checkpoint-100352` is the best-supported working and
best-known lineage because it has the strongest pooled research result and the
paired lead, while remaining below the 98% objective on the independent panel.
The recipe is retained unchanged for provenance; further progress requires an
ordinary next experiment rather than more interpretation of this baseline.

**Evidence inspected:** `research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-200ep-seed10200-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-100352-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-120832-task-reference-v1.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/evaluation-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-200ep-seed10000-f48545f83637.json`;
`research/evaluations/c1523389-1363-42a7-b973-1bc6847ac445/task-reference-c1523389-1363-42a7-b973-1bc6847ac445-experiment-1-checkpoint-86016-task-reference-v1.json`;
`research/brief.md`.
