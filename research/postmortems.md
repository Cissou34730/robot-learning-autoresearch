# Research postmortems

No experiments recorded.

## 229ee49c-81d2-4d70-b9d1-83d2c786555a / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned a strong but uneven reach-and-hold policy. The selected `checkpoint-100352` lineage achieved 310/320 successes (96.875%) across two distinct research panels and 159/160 on the disjoint panel, versus 158/160 for the final `checkpoint-120832`; late training did not improve measured behavior. The baseline trained on 14–20 cm targets, narrower than the official 6–20 cm radial distribution.

**Lessons and limits:** Training reward and training success locate candidates but are not task scores. The original research panel tied the two candidates at 151/160, and the task-reference panel is permanently reused rather than independent confirmation. Detailed diagnostics for the selected lineage show both missed tolerance and interrupted holds: 6 failures never reached tolerance and 3 reached it but failed the hold on seed 4200, while the seed-5000 panel had one missed-tolerance failure. These results support a useful working lineage, not attainment of the objective.

**Open questions:** It remains unknown whether full-range radial training improves performance on inner targets without degrading the established outer-target behavior, and whether the selected policy meets the objective on the separate official 200-episode assessment.

## 229ee49c-81d2-4d70-b9d1-83d2c786555a / Experiment 1

**Result:** The baseline produced a useful policy, with `checkpoint-100352` selected as the working and best-known lineage; no final benchmark is requested.

**Observed behavior:** The run completed 120,832 steps. The proxy peak at 100,352 steps had training success 0.97 and reward 117.32; the final checkpoint had training success 0.95 and reward 112.02. On the original research panel both achieved 151/160 (94.375%). On the disjoint panel, `checkpoint-100352` achieved 159/160 (99.375%) and `checkpoint-120832` achieved 158/160 (98.75%); the paired comparison favored 100352 by one net win over 320 episodes. The fixed task-reference panel scored 98% and 97%, respectively, but is reused rather than independent. Failure diagnostics include both missed tolerance and interrupted holds; the final checkpoint's disjoint failure reached tolerance but held for at most 5 steps with 244 interruptions.

**Hypothesis assessment:** Partially supported. The fresh baseline established substantial learned reach-and-hold capability, but the available development evidence does not establish robust attainment of the 98% objective. The disjoint panel distinguishes the earlier proxy peak from the final checkpoint, while the pooled distinct research-panel result for the selected checkpoint remains 310/320 (96.875%) and the official panel has not been run.

**Interpretation:** The earlier checkpoint is the most defensible saved policy because it is independently better on the disjoint comparison and late training slightly degraded measured behavior. The experiment made no researcher-owned code changes, so the scientific recipe should be kept. The selected policy should remain available for future development, but terminal assessment should not be used to resolve the remaining uncertainty; further training is the appropriate next experiment after closure.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/checkpoints/challengers/229ee49c-81d2-4d70-b9d1-83d2c786555a/experiment-1/inventory.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-100352-160ep-seed5000-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-120832-160ep-seed5000-f48545f83637.json`.
