# Research postmortems

## 0d669090-7528-4cb1-a91e-dec56695ce02 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned useful reach-and-hold
behavior but remains below the 98% human objective. Continuing checkpoint-95232
with full 6-20 cm target-radius training produced checkpoint-105472 at 307/320
(95.94%) across two disjoint research panels, versus 304/320 (95.00%) for the
same-panel parent control. The candidate's 98.125% first-panel result was used
to select it and is not independent confirmation; its disjoint confirmation was
93.75%, with a paired advantage of 3 wins over 320 episodes.

**Lessons and limits:** Expanding radius coverage is partially supported as a
useful intervention, but the gain is modest and no development measurement
establishes the 98% objective. The final full-range checkpoint measured 153/160
on the first panel, so later training did not clearly preserve the best
behavior. Training reward and training success remain unreliable policy
rankings, and the fixed task-reference panel is reused development evidence
rather than independent confirmation. The selected full-range candidate is the
best measured current representative, but its official result is unknown.

**Open questions:** Whether the modest full-range improvement persists on the
official 200-episode panel and whether further training can reduce the
remaining failures are unresolved. The residual failure distribution and the
official benchmark result for the selected policy are also unknown.

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
