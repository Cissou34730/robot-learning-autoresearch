# Research postmortems

## d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f / Experiment 1

**Result:** Fresh PPO baseline peaked at 66.0% on checkpoint-120832 (200 episodes, seed 1000), below the 98% objective.
**Observed behavior:** Measured success was 64.5% at checkpoint-86016, 65.5% at checkpoint-100352, and 66.0% at checkpoint-120832; at the best checkpoint 67 failures never reached tolerance and 1 reached it without completing the hold.
**Interpretation:** The small late-training gain does not establish a meaningful improvement (paired comparisons had only 1–3 discordant episodes); failures were dominated by reaching far targets, with 67 of 68 failures at targets of at least 14 cm.
**Evidence inspected:** `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-86016-200ep-seed1000-41299d1f0507.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-100352-200ep-seed1000-41299d1f0507.json`, `research/evaluations/d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f/evaluation-d04a0bde-a6d2-429f-a0d5-cd1a8c3a854f-experiment-1-checkpoint-120832-200ep-seed1000-41299d1f0507.json`
