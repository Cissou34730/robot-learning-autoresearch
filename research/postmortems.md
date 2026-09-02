# Research postmortems

## Experiment 1
**Result:** Fresh PPO baseline peaked at 47.5% (95/200) on checkpoint-115712; checkpoint-120832 fell to 34.0%, well below the 98% objective.
**Observed behavior:** Successful episodes held for 100 steps after reaching the target, while failures generally truncated at 500 steps; checkpoint-120832 lost 33 successes relative to checkpoint-115712 on the same episode seeds.
**Interpretation:** The baseline learned partial reach-and-hold control but became less reliable late in training; checkpoint-115712 is the strongest measured lineage, not evidence for final success.
**Evidence inspected:** research/evaluations/evaluation-experiment-1-checkpoint-100352-200ep-seed1000-31932e1eb9a8.json research/evaluations/evaluation-experiment-1-checkpoint-110592-200ep-seed1000-31932e1eb9a8.json research/evaluations/evaluation-experiment-1-checkpoint-115712-200ep-seed1000-31932e1eb9a8.json research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json
