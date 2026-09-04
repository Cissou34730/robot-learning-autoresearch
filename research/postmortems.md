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
