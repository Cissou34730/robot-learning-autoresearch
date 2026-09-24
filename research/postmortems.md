# Research postmortems

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Scientific strategy

**Current synthesis:** The unchanged PPO recipe learned a strong policy, with experiment-2 `checkpoint-100352` achieving 97.5% on both the 200-episode selection panel and the disjoint 1,000-episode research panel. It remains the best-known lineage, while the fixed task-reference panel returned 98.0%; these development results show near-objective transfer but do not establish the official 98% objective.

**Lessons and limits:** Training success and reward are proxies rather than task outcomes, and both the training proxy and measured task success regressed after the 100352-step checkpoint: the final checkpoint scored 97.0% on the 200-episode research panel. The selection-panel score is not independent evidence, the task-reference panel is permanently reused, and no result predicts the official verdict or attributes the residual failures to a particular training parameter.

**Open questions:** It remains unresolved whether the near-converged policy can be stabilized or refined beyond its 97.5% disjoint-panel performance, and the official benchmark result is unknown.

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
