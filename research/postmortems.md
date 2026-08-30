# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline reached 66.5% research success at checkpoint-105472, below the 98% objective; checkpoint-120832 was 66.0% and checkpoint-90112 was 65.5%.
**Observed behavior:** All candidates solved the 6-14 cm target bins, but success collapsed for larger targets: 0/41 successes at 17-20.01 cm and only 8-10/36 at 14-17 cm. Failures were predominantly never reaching tolerance, not interrupted holds.
**Interpretation:** The measured model lineage should use checkpoint-105472, the small aggregate lead and best descriptive reach behavior. The pattern supports a reachability/generalization limitation; it does not justify final benchmarking or calling the baseline solved. Keep the unchanged baseline code lineage.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-02bb2e760e90.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-02bb2e760e90.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-02bb2e760e90.json`
