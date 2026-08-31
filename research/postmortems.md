# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline reached 66.5% (133/200) at checkpoint-105472, compared with 65.5% at checkpoint-90112 and 66.0% at checkpoint-120832; the task-reference measurement at the final checkpoint was 55.0%.
**Observed behavior:** The research diagnostics solved every sampled target from 6-14 cm, while failures were concentrated at 14-20 cm and were predominantly failures to reach; checkpoint-105472 had 15 reached-but-not-held failures.
**Interpretation:** Training produced a useful but incomplete baseline with no reliable late-training improvement; checkpoint-105472 is the strongest measured lineage, but the single-seed, one-point differences and 55.0% task-reference result do not support final benchmarking.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-1a1d8367302b.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
