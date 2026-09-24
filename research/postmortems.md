# Research postmortems

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Scientific strategy

**Current synthesis:** The unchanged PPO recipe remains the strongest learned policy: experiment-2 `checkpoint-100352` achieved 97.5% on the disjoint 1,000-episode research panel, and the retained parent control achieved 97.4% on the new experiment-3 panel. The experiment-3 reduced-learning-rate, zero-entropy transfer recipe instead scored 89.5% and 90.0% on its measured checkpoints, so it did not improve the policy or establish the 98% objective.

**Lessons and limits:** Training success and reward are proxies rather than task outcomes; experiment 3 reached a 0.98 proxy at 100352 steps while task success was only 89.5%, and its final 0.96 proxy checkpoint scored 90.0%. The adjusted run's paired comparisons strongly favored the unchanged parent, but changing learning rate and entropy together does not identify which parameter caused the degradation. The selection-panel score is not independent evidence, the task-reference panel is permanently reused, and no development result predicts the official verdict.

**Open questions:** It remains unresolved whether another intervention can close the residual gap above the best-known policy's 97.5% disjoint-panel performance, and the official benchmark result is unknown.

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Experiment 1

**Result:** The fresh baseline learned a strong training-time proxy but did not produce task evidence for the human objective. `checkpoint-100352` is selected as the working lineage; no best-known model or final benchmark is designated.

**Observed behavior:** The run produced 24 checkpoints through 120,832 steps. Training success was 0 through 70,656 steps, rose to 0.06 at 75,776, 0.17 at 80,896, 0.42 at 86,016, 0.71 at 90,112, and 0.93 at 95,232. It peaked at 0.97 at 100,352, then varied from 0.93 to 0.95 through the final checkpoint. Training reward peaked earlier around 86,016 steps and was lower at the selected checkpoint and at the final checkpoint. All candidate evaluation lists are empty; the brief records zero research-evaluation and task-reference episodes.

**Hypothesis assessment:** The baseline hypothesis is partially supported as a learning-progression result: PPO learned the training proxy from an initially unsuccessful policy to approximately 0.97. It is inconclusive for the human objective because no research or task-reference measurement was recorded, and training proxies cannot establish the required 98% episode success.

**Interpretation:** The run demonstrates that the unchanged recipe can learn the shaped training task, with a late plateau and mild regression after the proxy peak. The selected checkpoint is a practical working artifact for subsequent development, but selecting it is based only on a non-authoritative proxy and must not be presented as independent task validation.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1/inventory.json`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1/parameters.json`; `research/training_logs/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1-attempt-1.log`.

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Experiment 2

**Result:** The unchanged fresh PPO recipe produced a strong learned policy, with `checkpoint-100352` reaching 97.5% on a disjoint 1,000-episode research panel. It is selected as both the working lineage and the campaign's best-known model; the recipe is kept for future development.

**Observed behavior:** The training-success proxy reached 0.97 at `checkpoint-100352`, while the reward peak occurred earlier at `checkpoint-86016`; the final checkpoint reached a 0.95 proxy. On the first research panel, the three candidates scored 96.0% (`checkpoint-86016`), 97.5% (`checkpoint-100352`), and 97.0% (`checkpoint-120832`). On the permanently reused task-reference panel they scored 94.0%, 98.0%, and 97.0%, respectively. The follow-up disjoint research panel measured `checkpoint-100352` at 975/1,000 successes (97.5%). The paired comparisons on the first panel favored `checkpoint-100352`, but those episodes were part of its selection and are not independent confirmation.

**Hypothesis assessment:** The baseline hypothesis is partially supported: PPO learned the training behavior and transferred it strongly to the unchanged reach-and-hold task. It is not sufficient evidence that the human objective is reached, because the disjoint result is 97.5%, below the required 98%, and development measurements cannot declare the official result. The conclusion is limited to this saved policy and evaluation semantics; it does not establish reproducibility or causal superiority of the unchanged recipe.

**Interpretation:** `checkpoint-100352` is the best-supported reusable policy in this campaign. The disjoint panel makes its near-objective performance credible beyond the selection panel, while the below-target rate leaves a scientifically useful path for later training or recipe changes. The fixed task-reference 98.0% result is corroborating context only, not independent confirmation. Since the evidence does not justify expecting a `goal_reached` final verdict, closure should preserve the policy and continue development rather than request the irreversible benchmark now.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-2/inventory.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/evaluation-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-2-checkpoint-100352-200ep-seed2000-f48545f83637.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/evaluation-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-2-checkpoint-100352-1000ep-seed2200-f48545f83637.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/task-reference-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-2-checkpoint-100352-task-reference-v1.json`.

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Experiment 3

**Result:** The adjusted transfer recipe did not improve the best-known policy. The existing experiment-2 `checkpoint-100352` lineage remains both working and best known; the adjusted recipe and its candidates are not retained.

**Observed behavior:** The run reduced PPO learning rate from 0.0003 to 0.0001 and entropy coefficient from 0.01 to 0.0 while continuing from the best-known policy. Its training-success proxy reached 0.99 at checkpoints 35840 and 75776, 0.98 at checkpoint-100352, and declined to 0.96 at checkpoint-120832. On the new disjoint 1,000-episode research panel, checkpoint-100352 achieved 895/1000 successes (89.5%), checkpoint-120832 achieved 900/1000 (90.0%), and the unchanged parent achieved 974/1000 (97.4%). Paired comparisons favored the parent on 79 versus 0 discordant episodes for checkpoint-100352 and 75 versus 1 for checkpoint-120832.

**Hypothesis assessment:** The hypothesis is contradicted under this tested transfer recipe and training horizon. Neither adjusted checkpoint exceeded the parent's 97.5% prior disjoint result or the 97.4% same-panel control, and both were far below the 98% human objective. The evidence supports rejecting this combined parameter adjustment for the selected lineage, but it does not establish whether the learning-rate or entropy change was individually responsible.

**Interpretation:** The adjusted training altered a strong policy into substantially weaker measured policies despite favorable training proxies, confirming that those proxies cannot select a task-useful checkpoint here. Restoring the complete best-known recipe preserves the only policy with repeated near-objective development evidence. The official result remains unknown, and further training, if pursued, is a separate subsequent experiment rather than part of this closure.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-3/inventory.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/evaluation-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-3-checkpoint-100352-1000ep-seed3200-f48545f83637.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/evaluation-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-3-checkpoint-120832-1000ep-seed3200-f48545f83637.json`; `research/evaluations/840f1e05-cd5f-42ed-9505-50aafef87094/evaluation-840f1e05-cd5f-42ed-9505-50aafef87094-experiment-3-best_known-1000ep-seed3200-f48545f83637.json`.
