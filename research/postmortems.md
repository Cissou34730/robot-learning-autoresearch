# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline reached a best development success of 46.5% at checkpoint-90112, far below the 98% objective threshold.
**Observed behavior:** Ordinary evaluation success declined from 46.5% at 90112 steps to 38.5%, 29.0%, 27.0%, 28.5%, and 22.0% at later checkpoints; the latest task-reference result was 21.5%.
**Interpretation:** The measured baseline peaks before the training budget ends, so checkpoint-90112 is the strongest available lineage; later training did not improve this method.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-100352-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-110592-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-1-checkpoint-115712-200ep-seed1000-31932e1eb9a8.json`, and `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`.
