# Research postmortems

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned substantially during training: the training-success proxy rose from 0 to 0.97 by checkpoint `checkpoint-100352`. Later checkpoints did not improve that proxy and ended at 0.95. This is evidence of learning progress, but the campaign has recorded no task measurements, so there is no evidence that the 98% official success objective has been reached.

**Lessons and limits:** Training success and reward are proxies rather than task outcomes. The reward peak and success peak occur at different checkpoints, so proxy ranking is uncertain. `checkpoint-100352` is retained as the working lineage because it has the highest observed training-success proxy, not because it has independently demonstrated official-task performance. No best-known designation or final assessment is justified without task measurement.

**Open questions:** The working policy's success on the unchanged task distribution and its ability to sustain the required hold remain unmeasured. A later experiment can measure or improve this lineage; any measurement used for selection must not be treated as independent confirmation when it is the same panel.

## 840f1e05-cd5f-42ed-9505-50aafef87094 / Experiment 1

**Result:** The fresh baseline learned a strong training-time proxy but did not produce task evidence for the human objective. `checkpoint-100352` is selected as the working lineage; no best-known model or final benchmark is designated.

**Observed behavior:** The run produced 24 checkpoints through 120,832 steps. Training success was 0 through 70,656 steps, rose to 0.06 at 75,776, 0.17 at 80,896, 0.42 at 86,016, 0.71 at 90,112, and 0.93 at 95,232. It peaked at 0.97 at 100,352, then varied from 0.93 to 0.95 through the final checkpoint. Training reward peaked earlier around 86,016 steps and was lower at the selected checkpoint and at the final checkpoint. All candidate evaluation lists are empty; the brief records zero research-evaluation and task-reference episodes.

**Hypothesis assessment:** The baseline hypothesis is partially supported as a learning-progression result: PPO learned the training proxy from an initially unsuccessful policy to approximately 0.97. It is inconclusive for the human objective because no research or task-reference measurement was recorded, and training proxies cannot establish the required 98% episode success.

**Interpretation:** The run demonstrates that the unchanged recipe can learn the shaped training task, with a late plateau and mild regression after the proxy peak. The selected checkpoint is a practical working artifact for subsequent development, but selecting it is based only on a non-authoritative proxy and must not be presented as independent task validation.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1/inventory.json`; `research/checkpoints/challengers/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1/parameters.json`; `research/training_logs/840f1e05-cd5f-42ed-9505-50aafef87094/experiment-1-attempt-1.log`.
