# Robot autoresearch

Run exactly one experiment, then stop.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay within 1 cm for 2 seconds. Evaluation is 200 deterministic episodes; success is at least 98%. Keep the evaluator, target distribution, robot physics, seed, and 120,000-transition budget fixed.

## Research surface

You may change any training method: curriculum, reward, observations, PPO or another algorithm, network size, exploration, schedules, and all training parameters. The current curriculum starts at 2 cm / 0.02 s and ends at 1 cm / 2 s, but changing it is a valid experiment.

Use one hypothesis and one coherent change. Write `research/proposal.json`, then run `uv run python research/run_experiment.py`. The runner measures the fixed evaluator and keeps an improvement; otherwise it restores the change.

Read `research/brief.md` before choosing. Read `research/last_train_summary.md` after training. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, run the unchanged control first. No LLM decision is needed for that baseline.

Record 3–6 short lines in `research/postmortems.md`: result, behavior, what it rules out, and the next idea. Then stop.

The score decides. Preserve negative results. Never change the benchmark to make the score look better.
