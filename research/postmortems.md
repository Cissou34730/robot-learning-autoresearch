# Research postmortems

## ec8a0728-5e76-46b3-b705-73b0aa542d7b / Scientific strategy

**Current synthesis:** The baseline learned most of the reach-and-hold behavior, but the strongest disjoint development result is 94.5%, below the 98% objective. Checkpoint-100352 is the best available policy, while nearby late-run checkpoints are comparable rather than clearly superior. The protected reference result is useful development evidence but is reused and not an official assessment.

**Lessons and limits:** The disjoint panel measured checkpoint-100352 at 189/200, checkpoint-95232 at 188/200, and checkpoint-120832 at 187/200; earlier measurements of the latter two were on reused episodes. The reference panel measured checkpoint-120832 at 97%, with failures concentrated toward inner targets, but that panel cannot establish independent or official performance. The evidence leaves both target-coverage effects and residual hold/reach failures uncertain.

**Open questions:** It remains unresolved whether exposure to the full official target-radius range improves inner-target robustness without degrading outer-target behavior, and whether that can close the remaining gap to 98%.

## ec8a0728-5e76-46b3-b705-73b0aa542d7b / Experiment 1

**Result:** The baseline learned a useful policy, with checkpoint-100352 selected as the strongest available working and best-known candidate at 94.5% on the disjoint research panel; the human objective is not yet supported.

**Observed behavior:** Training success rose from 0.42 at checkpoint-86016 to 0.97 at checkpoint-100352 and remained high through checkpoint-120832. On the first research panel, checkpoint-86016, checkpoint-95232, and checkpoint-120832 achieved 93.12%, 94.38%, and 94.38%, respectively. On the disjoint panel, checkpoint-95232, checkpoint-100352, and checkpoint-120832 achieved 94.0%, 94.5%, and 93.5%. The reused task-reference panel measured checkpoint-86016 at 94%, checkpoint-95232 at 96%, and checkpoint-120832 at 97%; this panel is not independent evidence.

**Hypothesis assessment:** Partially supported. The late training-success improvement corresponded to a substantial improvement in measured task behavior, and the training-success peak was marginally strongest on the disjoint panel. It did not produce the required 98% success, and the small pairwise margins do not establish a robust ranking beyond selecting checkpoint-100352 as the best available candidate.

**Interpretation:** The unchanged baseline recipe is capable of learning most of the task, but it has plateaued below the human objective under the observed late checkpoints. Closing preserves the strongest measured policy and nearby alternatives; it does not claim that the official objective has been reached.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/ec8a0728-5e76-46b3-b705-73b0aa542d7b/experiment-1/inventory.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-86016-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-95232-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-95232-200ep-seed4400-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-100352-200ep-seed4400-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-120832-200ep-seed4400-f48545f83637.json`; and the three corresponding task-reference artifacts listed in `research/brief.md`.
