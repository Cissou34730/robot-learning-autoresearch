# Research postmortems

## Experiment 1

**Result:** Baseline reached 66% success at checkpoint-110592, the best of the six measured checkpoints.
**Observed behavior:** Success rose from 54% at 30,720 steps to 66% at 110,592, then was 65% at 120,832; successful episodes held for 100 control steps, while failures generally did not sustain a hold.
**Interpretation:** PPO learns reliable reach-and-hold behavior for a subset of targets, but the plateau and 55% task-reference result show substantial generalization and holding failures remain.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-30720-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-60416-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-80896-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-95232-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-110592-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-100ep-seed1000-1a1d8367302b.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`

## Experiment 2

**Result:** With 0.5 hold-progress forfeiture, success was 77.0%, 61.0%, 76.0%, and 80.5% at checkpoints 60,416, 90,112, 110,592, and 120,832; the accepted champion scored 66.5%.
**Observed behavior:** The selected 120,832-step policy had the lowest mean minimum distance (0.670 cm), reached tolerance in 15.4 steps on average, and held for 82.2 steps on average; its task-reference result was 84.5% versus 55.0% for the champion.
**Interpretation:** The improvement over the champion and the task-reference comparison support penalizing exits from the tolerance band as a useful hold-stability intervention, although the 90,112-step dip and sub-98% result leave learning instability and generalization unresolved.
**Evidence inspected:** `research/evaluations/evaluation-experiment-2-checkpoint-60416-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-2-checkpoint-90112-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-2-checkpoint-110592-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-2-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-2-champion-200ep-seed1000-31932e1eb9a8.json`, `research/evaluations/task-reference-experiment-2-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-2-champion-task-reference-v1.json`
