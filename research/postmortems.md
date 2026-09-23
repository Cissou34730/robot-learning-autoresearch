# Research postmortems

## 021d2780-9c61-4eb5-88a8-68644fdf7d39 / Scientific strategy

**Current synthesis:** The unchanged PPO baseline learned strong reach-and-hold behavior late in training, with `checkpoint-100352` the best-supported policy at 391/400 successes (97.75%) across two disjoint research panels. It also achieved 196/200 on the reused task-reference panel. The later `checkpoint-120832` scored 194/200 on each research panel, so the additional unchanged training did not improve the measured policy.

**Lessons and limits:** Training-time reward and success identified a useful late-training region but remain proxies. The selected checkpoint is one pooled success below the 98% target, and its paired comparison with the final checkpoint favors it by 3 to 0 discordant wins. All measurements are development evidence; none establishes the official 200-episode result or explains the residual failures.

**Open questions:** Whether the near-objective plateau is improved or preserved by a changed training recipe, and whether the resulting policy merits the official assessment, remain unresolved.

## 021d2780-9c61-4eb5-88a8-68644fdf7d39 / Experiment 1

**Result:** The baseline produced a near-objective policy, with `checkpoint-100352` selected as the strongest measured candidate at 97.75% over two disjoint 200-episode research panels.

**Observed behavior:** Training proxies were near zero through 70,656 steps, then increased rapidly: `checkpoint-90112` had 0.71 training success, `checkpoint-100352` 0.97, and `checkpoint-120832` 0.95. On research episodes 2000-2199, the three measured checkpoints scored 96.5%, 97.5%, and 97.0%, respectively. On the disjoint episodes 2200-2399, `checkpoint-100352` scored 98.0% and `checkpoint-120832` 97.0%. The pooled result for `checkpoint-100352` was 391/400 (97.75%). On the fixed task-reference panel, `checkpoint-100352` scored 98.0%, but this panel was reused after candidate selection and is not independent evidence.

**Hypothesis assessment:** Partially supported. The fresh baseline established substantial learned reach-and-hold competence and approached the human objective, but the available development evidence does not establish at least 98% reliably. The conclusion is limited to this PPO recipe, training run, saved checkpoints, and measured panels; the official result remains unknown.

**Interpretation:** Performance improved into a late-training plateau, with `checkpoint-100352` outperforming both the earlier local proxy peak and the final checkpoint on the measured task. The disjoint panel confirms that selecting `checkpoint-100352` was not based solely on the panel used for selection. The final checkpoint's lower result suggests that continuing this unchanged run past the selected checkpoint was not beneficial, but it does not identify the cause or rule out a different training intervention.

**Evidence inspected:** `research/brief.md`; `research/research_state.json`; `research/checkpoints/challengers/021d2780-9c61-4eb5-88a8-68644fdf7d39/experiment-1/inventory.json`; `research/evaluations/021d2780-9c61-4eb5-88a8-68644fdf7d39/evaluation-021d2780-9c61-4eb5-88a8-68644fdf7d39-experiment-1-checkpoint-100352-200ep-seed2000-f48545f83637.json`; `research/evaluations/021d2780-9c61-4eb5-88a8-68644fdf7d39/evaluation-021d2780-9c61-4eb5-88a8-68644fdf7d39-experiment-1-checkpoint-100352-200ep-seed2200-f48545f83637.json`; `research/evaluations/021d2780-9c61-4eb5-88a8-68644fdf7d39/evaluation-021d2780-9c61-4eb5-88a8-68644fdf7d39-experiment-1-checkpoint-120832-200ep-seed2000-f48545f83637.json`; `research/evaluations/021d2780-9c61-4eb5-88a8-68644fdf7d39/evaluation-021d2780-9c61-4eb5-88a8-68644fdf7d39-experiment-1-checkpoint-120832-200ep-seed2200-f48545f83637.json`; `research/evaluations/021d2780-9c61-4eb5-88a8-68644fdf7d39/task-reference-021d2780-9c61-4eb5-88a8-68644fdf7d39-experiment-1-checkpoint-100352-task-reference-v1.json`.
