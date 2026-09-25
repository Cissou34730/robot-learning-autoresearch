# Research postmortems

No experiments recorded.

## 670368bb-2a56-4874-bd71-a57d639fd0bf / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned strong reach-and-hold behavior. The selected checkpoint-100352 and retained checkpoint-120832 are tied at 195/200 (97.5%) on the disjoint researcher panel; checkpoint-100352 scored 98% on the reused task-reference panel versus 97% for checkpoint-120832. The selected lineage is therefore the best-supported development policy, but not an independently established improvement over the late-training alternative.

**Lessons and limits:** Measured task behavior was better than training proxies alone suggested, while continued training past checkpoint-100352 did not improve the measured result. The 97.5% disjoint result is below the 98% objective, and the fixed task-reference panel was reused during selection; neither development record is the official final assessment. The baseline recipe and exact model fingerprints are preserved in the closure decision.

**Open questions:** Whether the selected policy achieves at least 196/200 on the official final panel remains unresolved. The available measurements do not establish a causal benefit from stopping at checkpoint-100352 or a validated route for improving the residual failures.

## 670368bb-2a56-4874-bd71-a57d639fd0bf / Experiment 1

**Result:** The baseline produced two late checkpoints with strong but not officially validated reach-and-hold performance. Checkpoint 100352 is selected as working and best-known; checkpoint 120832 is retained as a close alternative.

**Observed behavior:** Checkpoint 100352 scored 99/100 on the first researcher panel, 195/200 on the disjoint researcher panel, and 98% on the fixed task-reference panel. Checkpoint 120832 scored 99/100, 195/200, and 97% on those corresponding measurements. The disjoint paired comparison had zero wins and zero discordant episodes. Training proxies peaked near checkpoint 100352 and varied or declined thereafter.

**Hypothesis assessment:** Partially supported. The fresh baseline established a useful high-performing policy, but development measurements do not establish the official 98% objective, and the independent panel measured 97.5% for both selected candidates. This conclusion is limited to the recorded evaluation semantics and panels.

**Interpretation:** Checkpoint 100352 is the most defensible working lineage because it has the stronger fixed task-reference result and was reached at the proxy peak, although the task-reference advantage is not independent confirmation. Checkpoint 120832 remains worth retaining because its disjoint performance is tied and it represents the endpoint after continued training. No further measurement is needed to resolve this experiment's lineage decision.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/results.jsonl`; `research/checkpoints/challengers/670368bb-2a56-4874-bd71-a57d639fd0bf/experiment-1/inventory.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/evaluation-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-100352-200ep-seed21000-f48545f83637.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/evaluation-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-120832-200ep-seed21000-f48545f83637.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/task-reference-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-100352-task-reference-v1.json`; `research/evaluations/670368bb-2a56-4874-bd71-a57d639fd0bf/task-reference-670368bb-2a56-4874-bd71-a57d639fd0bf-experiment-1-checkpoint-120832-task-reference-v1.json`
