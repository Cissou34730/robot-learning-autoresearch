# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline achieved 18.50% (37/200) on the research panel and 15.50% (31/200) on the task-reference panel.
**Observed behavior:** It reached tolerance in 41/200 episodes, completed the 100-step hold in 37/200, and had hold interruptions in 8 episodes.
**Interpretation:** The endpoint learned occasional reaching and holding but remains far from the 98% objective; checkpoint-120832 is the best-supported active lineage because it is the measured endpoint.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json`; `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`

## Experiment 2
**Result:** Raising PPO entropy from 0.01 to 0.03 improved research-panel success to 22.00% (44/200) from 18.50% (37/200), and task-reference success to 21.50% (43/200) from 15.50% (31/200).
**Observed behavior:** The endpoint reached tolerance in 51/200 episodes and completed the 100-step hold in 44/200, versus 41/200 and 37/200 for the champion; mean first reach was 14.1 versus 37.5 steps. In eight equal angle bins, task-reference successes covered 6/8 bins versus 4/8 for the champion.
**Interpretation:** The matched-budget result supports insufficient exploration as a useful limiting mechanism, while not establishing whether running the baseline longer would also help; one fresh seed still leaves substantial angle gaps and is far from the 98% objective. Checkpoint-120832 is the stronger active lineage.
**Evidence inspected:** `research/evaluations/evaluation-experiment-2-checkpoint-120832-200ep-seed1000-31932e1eb9a8.json`; `research/evaluations/evaluation-experiment-2-champion-200ep-seed1000-31932e1eb9a8.json`; `research/evaluations/task-reference-experiment-2-checkpoint-120832-task-reference-v1.json`; `research/evaluations/task-reference-experiment-2-champion-task-reference-v1.json`
