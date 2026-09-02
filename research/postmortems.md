# Research postmortems

## Experiment 1

**Result:** Fresh PPO baseline reached 26.5% success (53/200) at checkpoint-100352; the terminal checkpoint reached 18.5% (37/200).

**Observed behavior:** Research diagnostics show the best checkpoint completed the 100-step hold in 53 episodes, while later checkpoints completed it in 33, 25, and 37 episodes despite rising logged training reward.

**Interpretation:** The baseline learned some reaching behavior, but its reward optimization did not produce a robust hold policy; additional training after checkpoint-100352 degraded task-aligned success rather than resolving the failure.

**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-100352-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-110592-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-115712-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
