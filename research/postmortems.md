# Research postmortems

No experiments recorded.

## 670368bb-2a56-4874-bd71-a57d639fd0bf / Scientific strategy

**Current synthesis:** The fresh PPO baseline learned strong reach-and-hold behavior. Checkpoints 100352 and 120832 both achieved 195/200 (97.5%) on the disjoint researcher panel, while checkpoint 100352 scored 98% on the fixed task-reference panel and checkpoint 120832 scored 97%. The disjoint comparison found no wins or discordant episodes, so checkpoint 100352 is selected as the working and best-known lineage based on the modest task-reference advantage and earlier proxy peak, not on an independent advantage from the reused panel.

**Lessons and limits:** Measured task behavior was substantially better than training proxies alone suggested, and continued training past checkpoint 100352 did not show a measured improvement. The development measurements are not the official final assessment; the 97.5% disjoint result is below the 98% campaign objective and the fixed task-reference panel was reused during selection. The baseline recipe and exact model fingerprints are preserved in the closure decision.

**Open questions:** Whether the selected policy achieves at least 196/200 on the official final panel remains unresolved. The two late checkpoints are effectively tied on the independent researcher panel, so this experiment does not establish a causal benefit from stopping at checkpoint 100352.

## 670368bb-2a56-4874-bd71-a57d639fd0bf / Experiment 1

**Result:** The baseline produced two late checkpoints with strong but not officially validated reach-and-hold performance. Checkpoint 100352 is selected as working and best-known; checkpoint 120832 is retained as a close alternative.

**Observed behavior:** Checkpoint 100352 scored 99/100 on the first researcher panel, 195/200 on the disjoint researcher panel, and 98% on the fixed task-reference panel. Checkpoint 120832 scored 99/100, 195/200, and 97% on those corresponding measurements. The disjoint paired comparison had zero wins and zero discordant episodes. Training proxies peaked near checkpoint 100352 and varied or declined thereafter.

**Hypothesis assessment:** Partially supported. The fresh baseline established a useful high-performing policy, but development measurements do not establish the official 98% objective, and the independent panel measured 97.5% for both selected candidates. This conclusion is limited to the recorded evaluation semantics and panels.

**Interpretation:** Checkpoint 100352 is the most defensible working lineage because it has the stronger fixed task-reference result and was reached at the proxy peak, although the task-reference advantage is not independent confirmation. Checkpoint 120832 remains worth retaining because its disjoint performance is tied and it represents the endpoint after continued training. No further measurement is needed to resolve this experiment's lineage decision.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/670368bb-2a56-4874-bd71-a57d639fd0bf/experiment-1/inventory.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/evaluation-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-100352-200ep-seed21000-f48545f83637.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/evaluation-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-120832-200ep-seed21000-f48545f83637.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/task-reference-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-100352-task-reference-v1.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/task-reference-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-120832-task-reference-v1.json`
