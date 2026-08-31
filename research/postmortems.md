# Research postmortems

## Experiment 1

**Result:** The fresh PPO baseline reached 66.5% at its best measured checkpoint, below the 98% objective.

**Observed behavior:** Research evaluation was 65.5% at 90,112 steps, 66.5% at 105,472, and 66.0% at 120,832; failures concentrated on the larger-radius targets, while successful episodes generally completed the full 100-step hold.

**Interpretation:** The baseline learned reliable reach-and-hold behavior for nearer targets but remained unreliable across the outer workspace; the small decline after 105,472 steps does not support continuing from the final checkpoint over the best measured checkpoint.

**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-794a24359f81.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-794a24359f81.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-794a24359f81.json`, `research/evaluations/task-reference-experiment-1-checkpoint-120832-task-reference-v1.json`

## Experiment 2

**Result:** The fresh outer-workspace curriculum regressed to 21.75% pooled success over two 200-episode seeds, far below the accepted 66.5% baseline.

**Observed behavior:** The challenger was strong below 14 cm but succeeded only 17.7% and 15.5% in the 14-18 cm band and 0% at 18-20 cm across the two seeds; the accepted champion scored 24.0% and 26.0% on the same researcher panels and 55.5% on the task-reference panel versus 15.0% for the challenger.

**Interpretation:** Oversampling outer targets did not solve the baseline's outer-workspace failures and instead damaged generalization, including nearby targets in the researcher panels; the challenger is not a useful active lineage, so the curriculum code should be reverted and the accepted champion retained.

**Evidence inspected:** `research/evaluations/evaluation-experiment-2-checkpoint-120832-200ep-seed1000-5b3ead329245.json`, `research/evaluations/evaluation-experiment-2-checkpoint-120832-200ep-seed2000-5b3ead329245.json`, `research/evaluations/evaluation-experiment-2-champion-200ep-seed1000-5b3ead329245.json`, `research/evaluations/evaluation-experiment-2-champion-200ep-seed2000-5b3ead329245.json`, `research/evaluations/task-reference-experiment-2-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-2-champion-task-reference-v1.json`
