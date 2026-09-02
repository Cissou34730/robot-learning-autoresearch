# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline achieved 18.50% (37/200) on the research panel and 15.50% (31/200) on the task-reference panel.
**Observed behavior:** It reached tolerance in 41/200 episodes, completed the 100-step hold in 37/200, and had hold interruptions in 8 episodes.
**Interpretation:** The endpoint learned occasional reaching and holding but remains far from the 98% objective; checkpoint-120832 is the best-supported active lineage because it is the measured endpoint.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json`; `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
