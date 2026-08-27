# Robot autoresearch

Run exactly one experiment, then stop.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay within 1 cm for 2 seconds. Evaluation is 200 deterministic episodes; success is at least 98%. Keep the evaluator, target distribution, robot physics, seed, and 120,000-transition budget fixed.

## Research surface

You may change any training method: curriculum, reward, observations, PPO or another algorithm, network size, exploration, schedules, and all training parameters. The current curriculum starts at the transferred checkpoint's demonstrated 3 cm / 0.02 s capability and ends at 1 cm / 2 s, but changing it is a valid experiment.

Use one hypothesis and one coherent change. Write `research/proposal.json`, then run `uv run python research/run_experiment.py`. The runner measures the fixed evaluator and keeps an improvement; otherwise it restores the change.

Read `research/brief.md` before choosing. Read `research/last_train_summary.md` after training. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, the runner automatically runs the unchanged
control first; no proposal or LLM decision is needed for that baseline.

The ratchet is lexicographic: maximize fixed-benchmark success first, then fixed
curriculum progress, then minimize closest distance. This lets learning progress
survive while final success is still 0%, without weakening the final benchmark.

Record 3–6 short lines in `research/postmortems.md`: result, behavior, what it rules out, and the next idea. Then stop.

The score decides. Preserve negative results. Never change the benchmark to make the score look better.
