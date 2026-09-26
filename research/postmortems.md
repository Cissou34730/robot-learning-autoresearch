# Research postmortems

No experiments recorded.

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Scientific strategy

**Current synthesis:** The baseline learned useful reach-and-hold behavior, but checkpoint-100352 remains below the human objective at 613/640 successes (95.78%) across four disjoint research panels. The broadened-coverage challengers reached 151/160 each versus 152/160 for their parent, and the partial hold-progress forfeiture challengers reached 142/160 and 140/160 versus 158/160 for the parent. The fixed task-reference result is reused development evidence, not independent confirmation. Checkpoint-100352 remains the strongest available policy.

**Lessons and limits:** Training proxies did not reliably rank task behavior, and neither broadened target coverage nor partial hold-progress forfeiture improved the paired result. Experiment-3 diagnostics show repeated hold interruptions in the weaker challengers, but parent failures also include episodes that never reached tolerance. The research panels are development evidence rather than the official 200-episode assessment, and unmeasured checkpoints remain unmeasured rather than failed.

**Open questions:** The role of fresh-training variance in producing a stronger policy, the cause of the remaining parent failures, and checkpoint-100352's generalization to the held-out official panel remain unresolved. The official benchmark remains the only source of an objective-level verdict.

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
**Evidence inspected:** research/brief.md; research/research_state.json; research/results.jsonl; research/checkpoints/challengers/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/experiment-2/inventory.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-checkpoint-105472-160ep-seed4600-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-checkpoint-120832-160ep-seed4600-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-2-working-160ep-seed4600-f48545f83637.json

## 5dd70b88-9f25-45f4-a3f7-ac764a7b7973 / Experiment 3

**Result:** Partial forfeiture of accumulated hold-progress reward did not improve complete reach-and-hold success; both measured intervention checkpoints were substantially worse than the unchanged parent.

**Observed behavior:** On the new disjoint episodes 4800-4959, checkpoint-105472 achieved 142/160 successes (88.75%) and checkpoint-120832 achieved 140/160 (87.5%), versus 158/160 (98.75%) for the working parent. The paired comparisons gave the parent all 16 discordant wins against checkpoint-105472 and all 18 discordant wins against checkpoint-120832. Detailed traces include repeated hold interruptions after first reaching tolerance, including interruption counts of 63, 16, 241, and 97 in representative failed trajectories.

**Hypothesis assessment:** The hypothesis is contradicted under the tested transfer recipe and `HOLD_EXIT_FORFEIT_FRACTION = 0.5`: neither the reward-peak checkpoint nor the late checkpoint exceeded the parent's 152/160 reference result, and both lost substantial complete-task success while showing hold interruptions. This is evidence against this intervention and setting in these conditions, not proof that other hold-reward designs cannot help.

**Expected observation disposition:** contradicted - on the new disjoint panel, checkpoint-105472 reached 142/160 and checkpoint-120832 reached 140/160 versus 158/160 for the parent; paired comparisons favored the parent 16-0 and 18-0 on discordant episodes, with repeated hold interruptions in challenger diagnostics.

**Interpretation:** The intervention should not be retained. The unchanged checkpoint-100352 lineage remains the strongest available policy, although its 613/640 pooled disjoint-panel result is still below the 98% human objective and does not replace the official assessment. Reverting the reward change preserves the parent recipe for any later campaign action; experiment-3 challenger artifacts have no demonstrated reuse value.

**Evidence inspected:** research/brief.md; research/research_state.json; research/results.jsonl; robot_learning/scenario/reward.py; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-3-checkpoint-105472-160ep-seed4800-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-3-checkpoint-120832-160ep-seed4800-f48545f83637.json; research/evaluations/5dd70b88-9f25-45f4-a3f7-ac764a7b7973/evaluation-5dd70b88-9f25-45f4-a3f7-ac764a7b7973-experiment-3-working-160ep-seed4800-f48545f83637.json
