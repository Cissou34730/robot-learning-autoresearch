# Research postmortems

## ec8a0728-5e76-46b3-b705-73b0aa542d7b / Scientific strategy

**Current synthesis:** Experiment 2 produced three full-range-training checkpoints at 199/200 (99.5%) on a new disjoint research panel, exceeding the 98% objective threshold, while the unchanged parent also scored 199/200 on that same panel. Checkpoint-105472 is selected as the working and best-known policy because it reached the run's highest training success and tied the other measured experiment-2 checkpoints; this is strong development evidence, not an official assessment.

**Lessons and limits:** The full 6-20 cm training intervention preserved behavior and reached 199/200 for checkpoints 100352, 105472, and 120832, but it did not improve the paired parent on the seed-5000 panel; all four policies shared the same binary outcome pattern, including the failure at episode seed 5099. The panel is disjoint from the panel that selected the parent, while the fixed task-reference panel remains permanently reused and non-independent. The evidence supports the policy-level objective on development data but not a causal benefit from the intervention or official final performance.

**Open questions:** It remains unresolved whether the 199/200 result generalizes to the official final panel and what residual reach or hold condition causes the shared failure.

## ec8a0728-5e76-46b3-b705-73b0aa542d7b / Experiment 1

**Result:** The baseline learned a useful policy, with checkpoint-100352 selected as the strongest available working and best-known candidate at 94.5% on the disjoint research panel; the human objective is not yet supported.

**Observed behavior:** Training success rose from 0.42 at checkpoint-86016 to 0.97 at checkpoint-100352 and remained high through checkpoint-120832. On the first research panel, checkpoint-86016, checkpoint-95232, and checkpoint-120832 achieved 93.12%, 94.38%, and 94.38%, respectively. On the disjoint panel, checkpoint-95232, checkpoint-100352, and checkpoint-120832 achieved 94.0%, 94.5%, and 93.5%. The reused task-reference panel measured checkpoint-86016 at 94%, checkpoint-95232 at 96%, and checkpoint-120832 at 97%; this panel is not independent evidence.

**Hypothesis assessment:** Partially supported. The late training-success improvement corresponded to a substantial improvement in measured task behavior, and the training-success peak was marginally strongest on the disjoint panel. It did not produce the required 98% success, and the small pairwise margins do not establish a robust ranking beyond selecting checkpoint-100352 as the best available candidate.

**Interpretation:** The unchanged baseline recipe is capable of learning most of the task, but it has plateaued below the human objective under the observed late checkpoints. Closing preserves the strongest measured policy and nearby alternatives; it does not claim that the official objective has been reached.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/ec8a0728-5e76-46b3-b705-73b0aa542d7b/experiment-1/inventory.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-86016-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-95232-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-95232-200ep-seed4400-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-100352-200ep-seed4400-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-1-checkpoint-120832-200ep-seed4400-f48545f83637.json`; and the three corresponding task-reference artifacts listed in `research/brief.md`.

## ec8a0728-5e76-46b3-b705-73b0aa542d7b / Experiment 2

**Result:** Checkpoints 100352, 105472, and 120832 each achieved 199/200 (99.5%) on the new seed-5000 research panel; the unchanged best-known parent also achieved 199/200.

**Observed behavior:** The three experiment-2 policies and the parent had zero discordant episodes in each paired comparison and the same single failure at episode seed 5099. Checkpoint-105472 had the highest training success at 1.0; checkpoint-120832 was the final checkpoint at 0.94.

**Hypothesis assessment:** Partially supported. Full-range training produced policies meeting the 98% objective threshold on an independent development panel and did not regress relative to the parent, but it did not improve the parent on the paired panel. This supports the resulting policy's measured performance, not the intervention's predicted causal improvement, and does not establish official final performance.

**Interpretation:** Checkpoint-105472 is the strongest working and best-known designation because it combines the highest training-success proxy with tied top measured performance; the tie means the selection is practical rather than a demonstrated behavioral ranking. Checkpoints 100352 and 120832 remain useful retained alternatives for trajectory and end-of-run comparison.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/checkpoints/challengers/ec8a0728-5e76-46b3-b705-73b0aa542d7b/experiment-2/inventory.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-2-checkpoint-105472-200ep-seed5000-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-2-checkpoint-100352-200ep-seed5000-f48545f83637.json`; `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-2-checkpoint-120832-200ep-seed5000-f48545f83637.json`; and `research/evaluations/ec8a0728-5e76-46b3-b705-73b0aa542d7b/evaluation-ec8a0728-5e76-46b3-b705-73b0aa542d7b-experiment-2-best_known-200ep-seed5000-f48545f83637.json`.
