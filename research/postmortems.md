# Research postmortems

No experiments recorded.

## 229ee49c-81d2-4d70-b9d1-83d2c786555a / Scientific strategy

**Current synthesis:** The unchanged baseline learned a strong reach-and-hold policy, but its measured performance is not uniformly above the 98% campaign objective. `checkpoint-100352` is the preferred lineage: it achieved 159/160 successes on the disjoint research panel, compared with 158/160 for the final `checkpoint-120832`, and is also the stronger training-success-proxy checkpoint. Late training therefore did not improve the measured policy.

**Lessons and limits:** Training reward and training success are useful for locating candidates but are not reliable task scores. The two candidates were tied at 151/160 on the original research panel, so that reused panel does not distinguish them; the fixed task-reference panel is also permanently reused and is not independent confirmation. Across the two distinct research panels, `checkpoint-100352` achieved 310/320 successes (96.875%), below the objective. Detailed diagnostics show residual behavior failures involving both failure to reach tolerance and interrupted holds. These results support selecting a useful working lineage, not declaring the human objective reached.

**Open questions:** It remains unknown whether a changed training intervention can reduce the residual reach and hold failures, and whether the selected policy will meet the objective on the separate official 200-episode assessment.

## 229ee49c-81d2-4d70-b9d1-83d2c786555a / Experiment 1

**Result:** The baseline produced a useful policy, with `checkpoint-100352` selected as the working and best-known lineage; no final benchmark is requested.

**Observed behavior:** The run completed 120,832 steps. The proxy peak at 100,352 steps had training success 0.97 and reward 117.32; the final checkpoint had training success 0.95 and reward 112.02. On the original research panel both achieved 151/160 (94.375%). On the disjoint panel, `checkpoint-100352` achieved 159/160 (99.375%) and `checkpoint-120832` achieved 158/160 (98.75%); the paired comparison favored 100352 by one net win over 320 episodes. The fixed task-reference panel scored 98% and 97%, respectively, but is reused rather than independent. Failure diagnostics include both missed tolerance and interrupted holds; the final checkpoint's disjoint failure reached tolerance but held for at most 5 steps with 244 interruptions.

**Hypothesis assessment:** Partially supported. The fresh baseline established substantial learned reach-and-hold capability, but the available development evidence does not establish robust attainment of the 98% objective. The disjoint panel distinguishes the earlier proxy peak from the final checkpoint, while the pooled distinct research-panel result for the selected checkpoint remains 310/320 (96.875%) and the official panel has not been run.

**Interpretation:** The earlier checkpoint is the most defensible saved policy because it is independently better on the disjoint comparison and late training slightly degraded measured behavior. The experiment made no researcher-owned code changes, so the scientific recipe should be kept. The selected policy should remain available for future development, but terminal assessment should not be used to resolve the remaining uncertainty; further training is the appropriate next experiment after closure.

**Evidence inspected:** `research/brief.md`; `research/results.jsonl`; `research/checkpoints/challengers/229ee49c-81d2-4d70-b9d1-83d2c786555a/experiment-1/inventory.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-100352-160ep-seed5000-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/229ee49c-81d2-4d70-b9d1-83d2c786555a/evaluation-229ee49c-81d2-4d70-b9d1-83d2c786555a-experiment-1-checkpoint-120832-160ep-seed5000-f48545f83637.json`.
