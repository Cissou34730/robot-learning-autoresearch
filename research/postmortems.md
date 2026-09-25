# Research postmortems

## 4b17531f-ff44-4b08-997f-e703fc28eb8e / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned competent reach-and-hold behavior, but the best characterized checkpoint remains below the 98% human objective on both disjoint research panels. Checkpoint-100352 is the strongest available policy, with 151/160 successes on each panel; checkpoint-120832 reached 151/160 and then 149/160. The fixed task-reference result of 98% for checkpoint-100352 is useful transfer evidence, but not independent confirmation because that panel was reused for selection.

**Lessons and limits:** Training success and reward identified a useful late-training region but did not establish the required task success; the reward peak at checkpoint-86016 was weaker than checkpoint-100352. The disjoint paired comparison favors checkpoint-100352 over checkpoint-120832 by 2-0 discordant wins, with pooled research success of 302/320 versus 300/320. These development measurements are not the official 200-episode assessment, and unmeasured checkpoints provide no additional evidence.

**Open questions:** It remains unresolved whether the residual failures can be reduced by continued optimization and whether the late decline reflects update magnitude, stochastic variation, or a plateau. The current measurements do not identify the cause or establish the best recipe for crossing the objective.

## 4b17531f-ff44-4b08-997f-e703fc28eb8e / Experiment 1

**Result:** The baseline produced a useful but not objective-satisfying policy; checkpoint-100352 is selected over the later final checkpoint.

**Observed behavior:** Checkpoint-100352 achieved 151/160 successes (94.375%) on both research panels, for 302/320 pooled successes. Checkpoint-120832 achieved 151/160 on the first panel and 149/160 on the disjoint panel, for 300/320 pooled successes. The fixed task-reference panel reported 98% for checkpoint-100352, 97% for checkpoint-120832, and 94% for checkpoint-86016, but it is reused development evidence. Training success peaked at 0.97 for checkpoint-100352; the reward peak at checkpoint-86016 did not correspond to the best measured behavior.

**Hypothesis assessment:** Partially supported. The fresh baseline clearly learned the task and established a strong late-training region, but the disjoint research evidence is below the 98% objective and does not support claiming that the objective has been reached. The late final checkpoint is slightly worse than checkpoint-100352 on the disjoint panel, although this comparison is based on 320 pooled research episodes rather than the official panel.

**Interpretation:** Checkpoint-100352 is the best-supported working and best-known lineage for subsequent development. Keeping the unchanged scientific recipe preserves the baseline for an ordinary next experiment; closure is appropriate because the lineage choice is resolved, while further training remains warranted to address the measured gap to the human objective.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/4b17531f-ff44-4b08-997f-e703fc28eb8e/experiment-1/inventory.json`; `research/evaluations/4b17531f-ff44-4b08-997f-e703fc28eb8e/evaluation-4b17531f-ff44-4b08-997f-e703fc28eb8e-experiment-1-checkpoint-100352-160ep-seed4200-f48545f83637.json`; `research/evaluations/4b17531f-ff44-4b08-997f-e703fc28eb8e/evaluation-4b17531f-ff44-4b08-997f-e703fc28eb8e-experiment-1-checkpoint-100352-160ep-seed4360-f48545f83637.json`; `research/evaluations/4b17531f-ff44-4b08-997f-e703fc28eb8e/evaluation-4b17531f-ff44-4b08-997f-e703fc28eb8e-experiment-1-checkpoint-120832-160ep-seed4200-f48545f83637.json`; `research/evaluations/4b17531f-ff44-4b08-997f-e703fc28eb8e/evaluation-4b17531f-ff44-4b08-997f-e703fc28eb8e-experiment-1-checkpoint-120832-160ep-seed4360-f48545f83637.json`; `research/evaluations/4b17531f-ff44-4b08-997f-e703fc28eb8e/task-reference-4b17531f-ff44-4b08-997f-e703fc28eb8e-experiment-1-checkpoint-100352-task-reference-v1.json`.
