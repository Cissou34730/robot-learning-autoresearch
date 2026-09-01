# Research postmortems

## Experiment 1
**Result:** Fresh PPO baseline success was 0%, 10%, 38%, 44%, and 34% at 5,120, 30,720, 60,416, 90,112, and 120,832 steps; the final 200-episode task-reference result was also 34%, far below the 98% objective.
**Observed behavior:** On the 100 overlapping seeds, checkpoint-120832 changed 21 checkpoint-90112 successes to failures and 8 failures to successes; mean maximum hold fell from 44.01 to 32.77 steps while interruptions rose from 2.32 to 5.44.
**Interpretation:** The paired evidence supports late-training hold instability rather than monotonic improvement, although it comes from one training seed; checkpoint-90112 is therefore the strongest measured lineage.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-5120-100ep-seed1000-31932e1eb9a8.json` `research/evaluations/evaluation-experiment-1-checkpoint-30720-100ep-seed1000-31932e1eb9a8.json` `research/evaluations/evaluation-experiment-1-checkpoint-60416-100ep-seed1000-31932e1eb9a8.json` `research/evaluations/evaluation-experiment-1-checkpoint-90112-100ep-seed1000-31932e1eb9a8.json` `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json` `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`
