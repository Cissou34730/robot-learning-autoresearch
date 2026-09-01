# Research postmortems

## Experiment 1

**Result:** Baseline reached 66% success at checkpoint-110592, the best of the six measured checkpoints.
**Observed behavior:** Success rose from 54% at 30,720 steps to 66% at 110,592, then was 65% at 120,832; successful episodes held for 100 control steps, while failures generally did not sustain a hold.
**Interpretation:** PPO learns reliable reach-and-hold behavior for a subset of targets, but the plateau and 55% task-reference result show substantial generalization and holding failures remain.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-30720-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-60416-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-80896-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-95232-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-110592-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
