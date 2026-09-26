# Research postmortems

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Scientific strategy

**Current synthesis:** PPO learned useful reach-and-hold behavior but remains
below the 98% human objective. Full 6-20 cm target-radius transfer produced
the strongest lineage, checkpoint-105472, with 621/640 (97.03%) pooled
successes across four disjoint research panels; its same-panel parent
control achieved 304/320 (95.00%) on the first two panels. The later
reduced-learning-rate continuation scored 144/160, 145/160, and 148/160,
while the saved parent scored 157/160 on that new panel. A fresh
full-radius replication reached only 114/160 (71.25%) at its best measured
checkpoint, versus 157/160 for the saved parent on the same panel.

**Lessons and limits:** Full-radius training is supported as a modest
improvement, not as a solution. The reduced-rate continuation was worse than
its parent at every measured checkpoint, so that tested optimization change
did not improve retention. training reward and training success do not reliably rank policies,
development panels do not establish the official result, and detailed
failures include both missed reaches and interrupted holds. The replication
also shows substantial fresh-initialization variability, so the strong
transferred lineage is not reliably reproduced by the tested recipe and seed.

**Open questions:** The official benchmark result remains unknown, and the
cause of the fresh-initialization variability remains unresolved. Further
training is an ordinary next experiment after this closure, not part of this
experiment-4 decision.

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

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Experiment 2

**Result:** Full official-radius training partially improved measured behavior.
Checkpoint-105472 is selected as the working and best-known lineage; the
full-range recipe is kept, and the prior baseline working lineage is retained
as a comparator.

**Observed behavior:** Checkpoint-105472 achieved 157/160 (98.125%) on the
selection panel and 150/160 (93.75%) on the disjoint confirmation panel. The
pre-intervention working control achieved 155/160 (96.875%) and 149/160
(93.125%) on those same panels. The pooled candidate result was 307/320
(95.9375%) versus 304/320 (95.0%) for the control, with 4 candidate wins and
1 control win among 5 discordant paired episodes. The final checkpoint-120832
achieved 153/160 (95.625%) on the first panel. No measured result establishes
the 98% official objective.

**Hypothesis assessment:** Partially supported. Full 6-20 cm target-radius
training produced a small, consistent paired improvement over the parent
across the two disjoint experiment-2 panels, and the second panel confirms that
the selected candidate is not supported only by its first-panel score.
However, the confirmation score was 93.75%, the aggregate remains below 98%,
and this evidence cannot establish official-task success or isolate which
target radii account for the change.

**Interpretation:** The intervention is useful enough to preserve as the
current recipe and checkpoint-105472 is the strongest measured current
representative. The result is an incremental improvement rather than a
solution to the human objective. Retaining the prior checkpoint-95232 lineage
preserves a clean baseline-policy comparator for future work; the reused
task-reference scores do not provide independent confirmation.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-2/inventory.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-2-checkpoint-105472-160ep-seed4520-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-2-checkpoint-105472-160ep-seed4680-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-2-working-160ep-seed4520-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-2-working-160ep-seed4680-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-2-checkpoint-120832-160ep-seed4520-f48545f83637.json`

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Experiment 3

**Result:** Reduced-learning-rate continuation did not produce a reusable
challenger. The existing best-known checkpoint-105472 remains both working
and best-known, and the parent recipe is restored.

**Observed behavior:** On the disjoint research panel at episodes 4840-4999,
checkpoint-100352 achieved 144/160 (90.00%), checkpoint-105472 achieved
145/160 (90.625%), and checkpoint-120832 achieved 148/160 (92.50%). The
best-known parent achieved 157/160 (98.125%) on the same panel. Each challenger
lost every discordant paired episode: 13, 12, and 9 parent wins respectively.
The measured candidates remained below the 98% threshold and the saved parent;
these development results do not establish the official 200-episode result.

**Hypothesis assessment:** Contradicted under the tested continuation. Lowering
the PPO learning rate did not preserve the prior 105472-step behavioral peak
and did not improve generalization on the disjoint panel. The conclusion is
limited to this transferred run, learning-rate change, and measured
checkpoints; it does not disprove other ways of improving optimization
stability.

**Interpretation:** The disjoint control provides independent development
evidence that the prior best-known lineage is preferable to all three measured
challengers. The continuation should be closed without retaining a challenger,
and the scientific recipe should revert to the parent recipe. The parent’s
98.125% score is strong development evidence but is not the official result.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/results.jsonl`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-3/inventory.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-3/checkpoint-100352/artifact.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-3/checkpoint-105472/artifact.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-3/checkpoint-120832/artifact.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-3-checkpoint-100352-160ep-seed4840-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-3-checkpoint-105472-160ep-seed4840-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-3-checkpoint-120832-160ep-seed4840-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-3-best_known-160ep-seed4840-f48545f83637.json`

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Experiment 4

**Result:** The fresh full-radius replication did not produce a reusable
challenger. The existing checkpoint-105472 lineage remains both working and
best-known, and the unchanged full-radius recipe is retained.

**Observed behavior:** On the new disjoint research panel at episodes
5000-5159, the fresh candidates achieved 104/160 (65.00%) at checkpoint-105472,
110/160 (68.75%) at checkpoint-110592, and 114/160 (71.25%) at
checkpoint-120832. The saved best-known policy achieved 157/160 (98.125%) on
the same panel and won 54, 48, and 44 of the discordant paired episodes against
those candidates, respectively. The fresh run therefore remained far below the
existing lineage at every measured checkpoint. The best-known panel is
disjoint from the panels used to select that lineage (4520-4839 and 4840-4999)
and provides independent development evidence, but it is not the official
200-episode assessment.

**Hypothesis assessment:** Contradicted under the tested fresh initialization,
training seed, checkpoints, and research panel. The unchanged full-radius
recipe did not reproduce the useful behavior of experiment 2 in this run and
did not produce a policy approaching the 98% objective. This does not disprove
the recipe under other random seeds or explain the source of the large
fresh-initialization variance.

**Interpretation:** The experiment provides evidence that the strong transferred
lineage is not reliably reproduced from scratch by this tested recipe and
seed. It does not justify replacing the existing best-known policy with any
experiment-4 candidate. Across the available disjoint panels, the saved
best-known policy is the strongest measured development artifact, while its
official-task status remains unresolved because only the final benchmark can
declare the objective.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/0d669090-7528-4cb1-a91e-dec56695ce02/experiment-4/inventory.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-4-checkpoint-105472-160ep-seed5000-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-4-checkpoint-110592-160ep-seed5000-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-4-checkpoint-120832-160ep-seed5000-f48545f83637.json`;
`research/evaluations/0d669090-7528-4cb1-a91e-dec56695ce02/evaluation-0d669090-7528-4cb1-a91e-dec56695ce02-experiment-4-best_known-160ep-seed5000-f48545f83637.json`.
