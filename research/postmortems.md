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

## Experiment 3

**Result:** The transferred long-range proximity reward reached 91.50% pooled success over two 200-episode researcher seeds, improving on the accepted champion's 63.25% pooled result.

**Observed behavior:** Success was 93.5% and 89.5% across the two researcher seeds, and 90.5% on the independent task-reference panel versus 55.5% for the champion; remaining failures were concentrated near the outer workspace and usually broke the hold shortly after reaching tolerance.

**Interpretation:** Increasing the closeness-potential length scale from 5 cm to 10 cm improved long-range approach and hold reliability without changing the task distribution or protected hold semantics, so checkpoint-120832 is the active lineage and the experiment code should be kept. The evidence is strong development evidence but remains below the 98% objective, so it does not warrant a final benchmark request.

**Evidence inspected:** `research/evaluations/evaluation-experiment-3-checkpoint-120832-200ep-seed1000-0933e7adff8a.json`, `research/evaluations/evaluation-experiment-3-checkpoint-120832-200ep-seed2000-0933e7adff8a.json`, `research/evaluations/evaluation-experiment-3-champion-200ep-seed1000-0933e7adff8a.json`, `research/evaluations/evaluation-experiment-3-champion-200ep-seed2000-0933e7adff8a.json`, `research/evaluations/task-reference-experiment-3-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-3-champion-task-reference-v1.json`

## Experiment 4

**Result:** The transferred hold-stability reward reached 97.0% pooled success over two 200-episode researcher seeds, one percentage point below the 98% objective.

**Observed behavior:** Checkpoint-120832 scored 97.0% on both researcher seeds and on the independent task-reference panel, with six failures per researcher seed; failures were mostly at larger radii or involved reaching tolerance but losing the hold.

**Interpretation:** Forfeiting half of accumulated hold progress after a tolerance exit improved both seed consistency and task-reference performance over the champion's 91.5% pooled researcher result and 90.5% task-reference result. The evidence is sufficiently close and independent to request the final benchmark, while the measured result itself does not declare success.

**Evidence inspected:** `research/evaluations/evaluation-experiment-4-checkpoint-120832-200ep-seed1000-d04f4e422fe3.json`, `research/evaluations/evaluation-experiment-4-checkpoint-120832-200ep-seed2000-d04f4e422fe3.json`, `research/evaluations/evaluation-experiment-4-champion-200ep-seed1000-d04f4e422fe3.json`, `research/evaluations/evaluation-experiment-4-champion-200ep-seed2000-d04f4e422fe3.json`, `research/evaluations/task-reference-experiment-4-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-4-champion-task-reference-v1.json`

## Experiment 5

**Result:** The transferred hold-stability reward reached 97.5% pooled success over two 200-episode researcher seeds, below the 98% objective.

**Observed behavior:** Checkpoint-120832 scored 97.5% on both researcher seeds versus 97.0% for the champion, with 10 failures across the two challenger panels versus 12 for the champion; the task-reference panel improved from 97.0% to 98.5%, while remaining failures included missed reaches and short or interrupted holds.

**Interpretation:** Increasing `HOLD_EXIT_FORFEIT_FRACTION` from 0.5 to 1.0 produced a small but consistent improvement in researcher and independent task-reference measurements, supporting checkpoint-120832 as the active lineage and keeping the reward change. The independent evidence is close enough to the objective to request the official final benchmark, but these research measurements do not declare success.

**Evidence inspected:** `research/evaluations/evaluation-experiment-5-checkpoint-120832-200ep-seed1000-268f629ee9a9.json`, `research/evaluations/evaluation-experiment-5-checkpoint-120832-200ep-seed2000-268f629ee9a9.json`, `research/evaluations/evaluation-experiment-5-champion-200ep-seed1000-268f629ee9a9.json`, `research/evaluations/evaluation-experiment-5-champion-200ep-seed2000-268f629ee9a9.json`, `research/evaluations/task-reference-experiment-5-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-5-champion-task-reference-v1.json`
