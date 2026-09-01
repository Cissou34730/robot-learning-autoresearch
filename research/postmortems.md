# Research postmortems

## Experiment 1
**Result:** Fresh PPO baseline reached 66.5% at checkpoint-105472, versus 65.5% at 90112 and 66.0% at 120832; the task-reference panel measured 55.0%.
**Observed behavior:** Research diagnostics solved all 89 targets at radius <=12 cm, while only 44/111 were solved at 105472; successful reaches usually held for all 100 steps.
**Interpretation:** The baseline's limiting mechanism is outer-radius reach/generalization, not maintaining the hold after reaching; later training did not improve this and showed a small regression.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
