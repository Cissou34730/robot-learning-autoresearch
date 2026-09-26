# Research postmortems

No experiments recorded.

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Scientific strategy

**Current synthesis:** The baseline learned useful reach-and-hold behavior, but checkpoint-100352 achieved 303/320 successes (94.6875%) across two disjoint research panels, below the human objective. Its 98% fixed task-reference result is development evidence only and was part of checkpoint selection, not independent confirmation. Checkpoint-120832 was slightly weaker at 301/320 (94.0625%), while checkpoint-86016 reached 149/160 (93.125%). The best available policy is therefore checkpoint-100352, with the objective still undemonstrated.

**Lessons and limits:** Training proxies did not reliably rank task behavior: the reward peak at checkpoint-86016 was the weakest measured candidate, and late checkpoints separated on the disjoint panel (152/160 versus 150/160). The training environment sampled only 14-20 cm targets, whereas the official task spans 6-20 cm, so the source of the residual failures is unresolved. The 320 research episodes are not the official 200-episode assessment, and unmeasured checkpoints remain unmeasured rather than failed.

**Open questions:** It remains unresolved whether target-radius coverage accounts for a meaningful share of the residual failures, whether transfer from checkpoint-100352 can improve performance under that coverage, and how any improvement would generalize to the held-out official panel. The official benchmark remains the only source of an objective-level verdict.

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Experiment 1

**Result:** The baseline produced a useful policy, with checkpoint-100352 the strongest measured candidate at 94.6875% pooled success on two disjoint research panels; it remains below the 98% campaign objective.

**Observed behavior:** Checkpoint-100352 achieved 151/160 successes on episodes 4200-4359 and 152/160 on the disjoint episodes 4400-4559. Checkpoint-120832 achieved 151/160 and 150/160 on those panels, and checkpoint-86016 achieved 149/160 on the first panel. On the fixed task-reference panel, the corresponding results were 98%, 97%, and 94%, respectively; that panel is reused development evidence and cannot confirm the selected checkpoint. The paired comparison on both research panels favored checkpoint-100352 by two discordant episodes.

**Hypothesis assessment:** The baseline question is partially answered: learning produced substantial reach-and-hold capability and checkpoint-100352 transferred best among the measured checkpoints, but the available evidence does not show the human objective has been met. Because this was a fresh baseline with no intervention-specific prediction, this assessment is descriptive and does not establish a causal training claim.

**Expected observation disposition:** not tested - the baseline question carried no intervention-specific expected observation.

**Interpretation:** The evidence supports selecting checkpoint-100352 as the working and best-known lineage for the next campaign decision. Its disjoint research performance is stable enough to preserve and continue from, but the gap to 98% is material; further training remains an ordinary next experiment rather than a conclusion that the objective is reached. Checkpoint-120832 is retained as a measured late-training alternative for future comparison, not as the preferred policy.

**Evidence inspected:** research/brief.md; research/research_state.json; research/results.jsonl; research/checkpoints/challengers/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/experiment-1/inventory.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-160ep-seed4400-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-160ep-seed4400-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/task-reference-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-task-reference-v1.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/task-reference-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-task-reference-v1.json
