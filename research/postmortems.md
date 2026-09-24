# Research postmortems

## c1523389-1363-42a7-b973-1bc6847ac445 / Scientific strategy

**Current synthesis:** The baseline learned robust reach-and-hold behavior but
remains below reliable attainment of the human objective: `checkpoint-100352`
achieved 393/400 pooled research successes, while its independent second panel
was 97%. The fixed task-reference panel was 98%, but it is reused and is not
independent confirmation.

**Lessons and limits:** The residual failures are concentrated near angles
roughly -116 to -142 degrees, with the task-reference failures also at inner
radii of about 6.7-9.9 cm. The baseline training distribution began at 14 cm,
so the evidence identifies a coverage mismatch, but does not establish that it
caused the failures or that changing it will preserve broad performance.

**Open questions:** It remains unresolved whether greater exposure to the
observed inner-radius and angular failure region removes that failure pocket
without degrading the already learned reach-and-hold behavior.

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
