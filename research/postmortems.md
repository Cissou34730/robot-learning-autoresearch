# Research postmortems

## Experiment 1

**Result:** The fresh PPO baseline reached 66.5% at its best measured checkpoint, below the 98% objective.

**Observed behavior:** Research evaluation was 65.5% at 90,112 steps, 66.5% at 105,472, and 66.0% at 120,832; failures concentrated on the larger-radius targets, while successful episodes generally completed the full 100-step hold.

**Interpretation:** The baseline learned reliable reach-and-hold behavior for nearer targets but remained unreliable across the outer workspace; the small decline after 105,472 steps does not support continuing from the final checkpoint over the best measured checkpoint.

**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-794a24359f81.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-794a24359f81.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-794a24359f81.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
