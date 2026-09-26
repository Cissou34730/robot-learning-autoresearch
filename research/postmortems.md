# Research postmortems

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned useful reach-and-hold
behavior late in training but remains below the 98% human objective on all
development measurements. Among the measured late checkpoints, checkpoint-95232
is the strongest on the pooled disjoint research panels at 301/320 (94.06%),
slightly ahead of checkpoint-120832 at 300/320 (93.75%). The fixed
task-reference panel gives 96% and 97% respectively, but it is reused and
therefore is not independent confirmation.

**Lessons and limits:** Training reward and training success identify the
learning transition but do not rank the final policies reliably: checkpoint-86016
had the highest training reward yet was weaker behaviorally. The disjoint
research panel supports selecting checkpoint-95232 over the final checkpoint,
while the reused task-reference result leaves a small unresolved difference.
These development measurements do not establish the official result; the
98%-success objective remains unconfirmed.

**Open questions:** Whether further training or a changed scientific recipe can
close the remaining gap to 98% is unresolved. The official benchmark result for
the selected policy is also unknown.

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Experiment 1

**Result:** The fresh baseline produced a useful but sub-target learned policy.
Checkpoint-95232 is selected as both the working and best-known lineage;
checkpoint-120832 is retained as an alternative.

**Observed behavior:** Checkpoint-86016, the training-reward peak, achieved
149/160 (93.125%) on the first research panel and 94% on the reused
task-reference panel. Checkpoint-95232 achieved 151/160 (94.375%) and
150/160 (93.75%) on the two disjoint research panels, plus 96% on the reused
task-reference panel. Checkpoint-120832 achieved 151/160 (94.375%) and
149/160 (93.125%) on those research panels, plus 97% on the reused reference
panel. The pooled paired comparison on 320 research episodes favored
checkpoint-95232 by 2 discordant wins to 1 for checkpoint-120832. No measured
policy reached 98%, and none of these development panels is the official
assessment.

**Hypothesis assessment:** Supported as an initial baseline characterization:
the unchanged method learned substantial task behavior and exposed a late
plateau, but it did not satisfy the human objective. The evidence supports
checkpoint-95232 over checkpoint-120832 for the current lineage decision only
within the measured research coverage; the small difference and the reused
reference-panel advantage for checkpoint-120832 limit the strength of that
conclusion.

**Interpretation:** Later training did not improve the selected policy's
generalized research performance, so checkpoint-95232 is the most defensible
working and best-known policy. Retaining checkpoint-120832 preserves the
alternative suggested by the fixed reference panel for future comparison or
continuation without treating that reused score as independent confirmation.
The scientific recipe is unchanged because this experiment tested only the
baseline.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-1/inventory.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-95232-160ep-seed4200-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-95232-160ep-seed4360-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-120832-160ep-seed4360-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/task-reference-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-95232-task-reference-v1.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/task-reference-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-1-checkpoint-120832-task-reference-v1.json`
