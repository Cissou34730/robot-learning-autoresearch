# Research postmortems

No experiments recorded.

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Scientific strategy

**Current synthesis:** The baseline learned useful reach-and-hold behavior, but checkpoint-100352 remains below the human objective at 455/480 successes (94.79%) across three disjoint research panels. The experiment-2 broadened-coverage checkpoints each achieved 151/160 (94.375%) on the new panel, while the parent achieved 152/160 (95.0%); neither improved on the parent. The fixed task-reference result is development evidence only and was part of checkpoint selection, not independent confirmation. The best available policy remains checkpoint-100352, with the objective still undemonstrated.

**Lessons and limits:** Training proxies did not reliably rank task behavior: the reward peak at checkpoint-86016 was the weakest measured candidate, late checkpoints separated on disjoint panels, and the broadened target-radius continuation did not improve the paired result. This weakens target coverage as a sufficient intervention under the tested transfer and training budget, but does not identify the cause of the residual failures or rule out other coverage strategies. The research panels are development evidence, not the official 200-episode assessment, and unmeasured checkpoints remain unmeasured rather than failed.

**Open questions:** The source of the remaining failures is unresolved, including whether a different learning intervention can improve the selected policy and how its performance would generalize to the held-out official panel. The official benchmark remains the only source of an objective-level verdict.

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Experiment 1

**Result:** The baseline produced a useful policy, with checkpoint-100352 the strongest measured candidate at 94.6875% pooled success on two disjoint research panels; it remains below the 98% campaign objective.

**Observed behavior:** Checkpoint-100352 achieved 151/160 successes on episodes 4200-4359 and 152/160 on the disjoint episodes 4400-4559. Checkpoint-120832 achieved 151/160 and 150/160 on those panels, and checkpoint-86016 achieved 149/160 on the first panel. On the fixed task-reference panel, the corresponding results were 98%, 97%, and 94%, respectively; that panel is reused development evidence and cannot confirm the selected checkpoint. The paired comparison on both research panels favored checkpoint-100352 by two discordant episodes.

**Hypothesis assessment:** The baseline question is partially answered: learning produced substantial reach-and-hold capability and checkpoint-100352 transferred best among the measured checkpoints, but the available evidence does not show the human objective has been met. Because this was a fresh baseline with no intervention-specific prediction, this assessment is descriptive and does not establish a causal training claim.

**Expected observation disposition:** not tested - the baseline question carried no intervention-specific expected observation.

**Interpretation:** The evidence supports selecting checkpoint-100352 as the working and best-known lineage for the next campaign decision. Its disjoint research performance is stable enough to preserve and continue from, but the gap to 98% is material; further training remains an ordinary next experiment rather than a conclusion that the objective is reached. Checkpoint-120832 is retained as a measured late-training alternative for future comparison, not as the preferred policy.

**Evidence inspected:** research/brief.md; research/research_state.json; research/results.jsonl; research/checkpoints/challengers/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/experiment-1/inventory.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-160ep-seed4400-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-160ep-seed4400-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/task-reference-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-100352-task-reference-v1.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/task-reference-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-1-checkpoint-120832-task-reference-v1.json
## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Experiment 2

**Result:** Broadening training targets from 14-20 cm to the full official 6-20 cm range did not improve the transferred policy on the new disjoint research panel.

**Observed behavior:** Checkpoints 105472 and 120832 each achieved 151/160 successes (94.375%) on episodes 4600-4759. The working parent achieved 152/160 (95.0%) on the identical panel. Each paired comparison had zero challenger wins and one discordant episode, a -0.625 percentage-point difference. The candidates' training proxies varied, including 1.0 training success at checkpoint-105472, but this did not translate into better measured task success.

**Hypothesis assessment:** The hypothesis is weakened: under continued transfer from checkpoint-100352 and the tested training budget, broadened target coverage did not exceed the parent's measured performance and both measured broadened-coverage checkpoints were below the expected improvement. This is evidence against this intervention in these conditions, not proof that target coverage cannot help with a different recipe or training process.

**Expected observation disposition:** weakened - both broadened-coverage candidates reached 151/160 on the new panel versus 152/160 for the parent, with zero challenger wins in each paired comparison.

**Interpretation:** The intervention should not replace the parent lineage. The existing checkpoint-100352 policy remains the strongest measured policy, with 455/480 pooled successes across three disjoint research panels, but this is development evidence below the 98% objective and does not establish official success. Reverting the broadened-coverage recipe preserves the strongest known scientific configuration for the next campaign decision.

**Evidence inspected:** research/brief.md; research/research_state.json; research/results.jsonl; research/checkpoints/challengers/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/experiment-2/inventory.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-checkpoint-105472-160ep-seed4600-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-checkpoint-120832-160ep-seed4600-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-working-160ep-seed4600-f48545f83637.json
