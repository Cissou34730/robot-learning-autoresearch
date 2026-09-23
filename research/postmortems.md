# Research postmortems

## 7a8a9e3a-e0cc-4940-a747-cb7529b2da8c / Experiment 1

**Result:** The baseline learned a strong but not yet objective-satisfying policy. The best measured candidate was `checkpoint-100352` at 195/200 successes (97.5%) on the disjoint research panel, one success short of the 196/200 objective threshold.

**Observed behavior:** The disjoint research panel measured `checkpoint-90112` at 193/200 (96.5%), `checkpoint-100352` at 195/200 (97.5%), and `checkpoint-120832` at 194/200 (97.0%). Paired comparisons favored `checkpoint-100352` over `checkpoint-90112` by 1.0 percentage point and over `checkpoint-120832` by 0.5 percentage points. The fixed task-reference panel returned 93.0%, 98.0%, and 97.0%, respectively, but it is permanently reused and is not independent confirmation. The six failures for `checkpoint-100352` were 500-step truncations associated with failure to maintain the uninterrupted 100-step hold. Training success peaked at 0.97 at `checkpoint-100352` and fell to 0.95 at the final checkpoint.

**Hypothesis assessment:** The baseline hypothesis was to establish the initial performance of the unchanged method against the human-defined objective. It is partially supported: PPO learned reliable reach-and-hold behavior and produced a clear candidate for preservation, but the strongest disjoint result remains below the required 98% success. The measurements characterize development performance only and cannot establish the official result.

**Interpretation:** `checkpoint-100352` is the most useful saved policy because it is the strongest candidate on the disjoint panel and slightly outperforms the final checkpoint despite the later training. The unchanged scientific recipe should be kept. The residual failures indicate that future training can focus on uninterrupted hold robustness, but that is a subsequent experiment rather than part of this closure.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/research_state.json`; `research/checkpoints/challengers/7a8a9e3a-e0cc-4940-a747-cb7529b2da8c/experiment-1/inventory.json`; `research/evaluations/7a8a9e3a-e0cc-4940-a747-cb7529b2da8c/evaluation-7a8a9e3a-e0cc-4940-a747-cb7529b2da8c-experiment-1-checkpoint-90112-200ep-seed2000-f48545f83637.json`; `research/evaluations/7a8a9e3a-e0cc-4940-a747-cb7529b2da8c/evaluation-7a8a9e3a-e0cc-4940-a747-cb7529b2da8c-experiment-1-checkpoint-100352-200ep-seed2000-f48545f83637.json`; `research/evaluations/7a8a9e3a-e0cc-4940-a747-cb7529b2da8c/evaluation-7a8a9e3a-e0cc-4940-a747-cb7529b2da8c-experiment-1-checkpoint-120832-200ep-seed2000-f48545f83637.json`; `research/evaluations/7a8a9e3a-e0cc-4940-a747-cb7529b2da8c/task-reference-7a8a9e3a-e0cc-4940-a747-cb7529b2da8c-experiment-1-checkpoint-100352-task-reference-v1.json`.

## 7a8a9e3a-e0cc-4940-a747-cb7529b2da8c / Scientific strategy

**Current synthesis:** The unchanged PPO baseline reaches 97.5% on the strongest disjoint development measurement, with `checkpoint-100352` the strongest measured policy. Its failures are concentrated in completing the uninterrupted hold, while the human objective remains unestablished by development panels.

**Lessons and limits:** Training success and reward identify useful late checkpoints but do not replace task-success measurement; the final checkpoint was slightly worse than the proxy peak. In the detailed research artifact, two failures entered tolerance and then interrupted the hold, while three never reached tolerance. The research and fixed reference panels are development evidence, and the latter is reused, so neither establishes the official result or broader generalization.

**Open questions:** It remains unresolved whether the learned reach behavior can be made more stable during the required hold without trading away reach reliability. The official result for the selected policy is also unresolved.
