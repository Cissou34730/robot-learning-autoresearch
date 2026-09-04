# Research postmortems

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 1

**Result:** Fresh PPO baseline peaked at 66.0% on checkpoint-120832 (200 episodes, seed 1000), below the 98% objective.
**Observed behavior:** Measured success was 64.5% at checkpoint-86016, 65.5% at checkpoint-100352, and 66.0% at checkpoint-120832; at the best checkpoint 67 failures never reached tolerance and 1 reached it without completing the hold.
**Interpretation:** The small late-training gain does not establish a meaningful improvement (paired comparisons had only 1–3 discordant episodes); failures were dominated by reaching far targets, with 67 of 68 failures at targets of at least 14 cm.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-86016-200ep-seed1000-41299d1f0507.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-100352-200ep-seed1000-41299d1f0507.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-120832-200ep-seed1000-41299d1f0507.json`

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 2

**Result:** Far-target-focused training reached 97.0% (194/200) on the fixed 6–20 cm evaluation panel at both checkpoints 100352 and 120832.
**Observed behavior:** Each trained checkpoint had 6 failures, compared with 68 for the 66.0% champion; paired outcomes were 64 candidate-only successes and 2 champion-only successes.
**Interpretation:** Training on 14–20 cm targets substantially improved the diagnosed far-target weakness without changing the research evaluation distribution; the one-episode checkpoint difference provides no evidence that later training is better.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-2-checkpoint-100352-200ep-seed1000-261fd1f2c5ff.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-2-checkpoint-120832-200ep-seed1000-261fd1f2c5ff.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-2-champion-200ep-seed1000-261fd1f2c5ff.json`

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 3

**Result:** Angular-hard-region-focused training reached 62.0% at checkpoint-90112 and 51.5% at checkpoint-120832, far below the accepted 97.0% champion.
**Observed behavior:** The candidates had 76 and 97 failures respectively versus 6 for the champion; paired outcomes favored the champion by 75–5 and 95–4, and only 7 and 10 candidate failures fell in the oversampled -160 to -100 degree sector.
**Interpretation:** Oversampling the diagnosed angular sector did not preserve broad-task competence and worsened with further training, so neither candidate is a viable active lineage.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-3-checkpoint-90112-200ep-seed1000-53d9aac1b6d1.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-3-checkpoint-120832-200ep-seed1000-53d9aac1b6d1.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-3-champion-200ep-seed1000-53d9aac1b6d1.json`

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 4

**Result:** Mild angular-hard-region focus reached 69.0% at checkpoint-100352 and 64.5% at checkpoint-120832, below the accepted 97.0% champion.
**Observed behavior:** The candidates had 62 and 71 truncated failures respectively versus 6 for the champion; on the task-reference panel, checkpoint-120832 scored 70.5% versus 98.0% for the champion.
**Interpretation:** Adding 20% sampling of the -160 to -100 degree sector to far-target-focused training did not preserve broad competence and worsened with further training, so the experiment-4 code and candidates are not viable.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-4-checkpoint-100352-200ep-seed1000-88c7ea5975c7.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-4-checkpoint-120832-200ep-seed1000-88c7ea5975c7.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-4-champion-200ep-seed1000-88c7ea5975c7.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/task-reference-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-4-checkpoint-120832-task-reference-v1.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/task-reference-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-4-champion-task-reference-v1.json`

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 5

**Result:** Far-target training with 20% full-range background reached 55.5% (111/200) at both checkpoints 115712 and 120832, below the accepted 97.0% champion.
**Observed behavior:** Both candidates had 89 truncated failures versus 6 for the champion; paired outcomes favored the champion by 85–2 at checkpoint 115712 and 87–4 at checkpoint 120832.
**Interpretation:** Adding full-range background sampling to the far-target curriculum did not preserve broad-task competence; the held-out task-reference result was also 55.0% versus 98.0% for the champion, so neither candidate is viable.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-5-checkpoint-115712-200ep-seed1000-b55ec848ea09.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-5-checkpoint-120832-200ep-seed1000-b55ec848ea09.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-5-champion-200ep-seed1000-b55ec848ea09.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/task-reference-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-5-checkpoint-120832-task-reference-v1.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/task-reference-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-5-champion-task-reference-v1.json`
