# Research postmortems

## Experiment 1
**Result:** The fresh PPO baseline reached 66.5% research success at checkpoint-105472, below the 98% objective; checkpoint-120832 was 66.0% and checkpoint-90112 was 65.5%.
**Observed behavior:** All candidates solved the 6-14 cm target bins, but success collapsed for larger targets: 0/41 successes at 17-20.01 cm and only 8-10/36 at 14-17 cm. Failures were predominantly never reaching tolerance, not interrupted holds.
**Interpretation:** The measured model lineage should use checkpoint-105472, the small aggregate lead and best descriptive reach behavior. The pattern supports a reachability/generalization limitation; it does not justify final benchmarking or calling the baseline solved. Keep the unchanged baseline code lineage.
**Evidence inspected:** `research/evaluations/evaluation-experiment-1-checkpoint-90112-200ep-seed1000-02bb2e760e90.json`, `research/evaluations/evaluation-experiment-1-checkpoint-105472-200ep-seed1000-02bb2e760e90.json`, `research/evaluations/evaluation-experiment-1-checkpoint-120832-200ep-seed1000-02bb2e760e90.json`

## Experiment 2
**Result:** The outer-workspace sampling intervention reached 97.0% research success (194/200), substantially above the incumbent champion's 40.5% (81/200), but remains below the 98% objective and is not an official benchmark result.
**Observed behavior:** The selected checkpoint completed 194/200 holds, reached tolerance in all 200 episodes, and completed 61/65 holds in the 17-20 cm band; the champion completed 0/65 in that band and failed to reach tolerance in 45/65 episodes.
**Interpretation:** The evidence supports insufficient outer-workspace coverage as the baseline limitation. Make checkpoint-120832 the active model lineage, keep the Experiment 2 code lineage, and retain Experiment 1's checkpoint-120832 as a reusable alternative; do not request the final benchmark because the measured evidence is single-seed and below 98%.
**Evidence inspected:** `research/evaluations/evaluation-experiment-2-checkpoint-120832-200ep-seed1000-0709faf8a915.json`, `research/evaluations/evaluation-experiment-2-champion-200ep-seed1000-0709faf8a915.json`

## Experiment 4
**Result:** The hold-exit forfeiture intervention reached 86.5% research success (173/200), below the incumbent champion's 96.0% and the 98% objective; neither is an official benchmark result.
**Observed behavior:** The challenger lost all 19 discordant paired episodes, had 27 failures including 9 episodes that never reached tolerance, and its task-reference success was 79.0% versus 98.5% for the champion.
**Interpretation:** The reward change did not improve hold stability and degraded reach-and-hold reliability, so reject this lineage, revert its code, continue from the champion, and request the official benchmark because independent task-reference evidence supports that selection.
**Evidence inspected:** `research/evaluations/evaluation-experiment-4-checkpoint-120832-200ep-seed2000-ed676b79d068.json`, `research/evaluations/evaluation-experiment-4-champion-200ep-seed2000-ed676b79d068.json`, `research/evaluations/task-reference-experiment-4-checkpoint-120832-task-reference-v1.json`, `research/evaluations/task-reference-experiment-4-champion-task-reference-v1.json`
