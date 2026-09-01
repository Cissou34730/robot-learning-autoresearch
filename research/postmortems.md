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

## Experiment 3

**Result:** The hold-duration curriculum reached 61.5%, 59.0%, 58.5%, and 49.5% at checkpoints 60,416, 90,112, 110,592, and 120,832; the champion scored 83.5%.
**Observed behavior:** The final candidate regressed to 2.13 cm mean minimum distance and 26.09 mean maximum held steps, versus 0.62 cm and 45.97 steps for the champion; its task-reference result was 48.5% versus 84.5%.
**Interpretation:** Gradually increasing the hold requirement did not solve the learning bottleneck and instead degraded both reach quality and sustained holding, with performance declining late in training. The curriculum is rejected; the accepted hold-stability reward remains the stronger lineage.
**Evidence inspected:** `research/evaluations/evaluation-experiment-3-checkpoint-60416-200ep-seed2000-5a38689675b6.json`, `research/evaluations/evaluation-experiment-3-checkpoint-90112-200ep-seed2000-5a38689675b6.json`, `research/evaluations/evaluation-experiment-3-checkpoint-110592-200ep-seed2000-5a38689675b6.json`, `research/evaluations/evaluation-experiment-3-checkpoint-120832-200ep-seed2000-5a38689675b6.json`, `research/evaluations/evaluation-experiment-3-champion-200ep-seed2000-5a38689675b6.json`, `research/evaluations/task-reference-experiment-3-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-3-champion-task-reference-v1.json`

## Experiment 4

**Result:** Increasing PPO gamma from 0.99 to 0.995 produced 41.0%, 38.5%, 40.5%, and 30.0% success at checkpoints 60,416, 90,112, 110,592, and 120,832, versus 81.5% for the accepted champion.
**Observed behavior:** Performance stayed low and degraded late: the final candidate averaged 386.1 episode steps, 2.718 cm minimum distance, and 30.07 maximum held steps, versus 188.2 steps, 0.619 cm, and 83.87 held steps for the champion. The task-reference panel likewise scored the candidate 29.0% versus 84.5%.
**Interpretation:** The results do not support the long-horizon credit hypothesis. Higher gamma did not improve reach or sustained holding and is rejected; the accepted hold-stability lineage remains preferable.
**Evidence inspected:** `research/evaluations/evaluation-experiment-4-checkpoint-60416-200ep-seed2000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-4-checkpoint-90112-200ep-seed2000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-4-checkpoint-110592-200ep-seed2000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-4-checkpoint-120832-200ep-seed2000-31932e1eb9a8.json`, `research/evaluations/evaluation-experiment-4-champion-200ep-seed2000-31932e1eb9a8.json`, `research/evaluations/task-reference-experiment-4-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-4-champion-task-reference-v1.json`
