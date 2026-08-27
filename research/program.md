# Robot autoresearch

Each research session prepares exactly one experiment, then exits. The runner
owns training, checkpoints, evaluation, rollback, and commits, and starts the
next research session automatically. The overall research loop continues until
the human stops it.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay
within 1 cm for 2 seconds. Never edit `robot_learning/benchmark/`, the robot,
physics, environment mechanics, evaluator, runner, or `tests/benchmark/`.
The protected evaluation target is always the final 1 cm / 2 s goal, not a
restriction on training.

## Research surface

You may modify the research training surface, including
`robot_learning/train.py` and the tunable configuration. Any training method is
fair game. Do not follow a prescribed list of techniques: use the evidence to
decide what to try.

Test one identifiable hypothesis per experiment. It may require multiple
coherent edits. Write `research/proposal.json`, make the corresponding
research-surface edits when needed, then exit. Do not launch training or the
runner: `run_research.ps1` verifies the protected files and runs the experiment
after your process exits.

At the start of each session, read `research/brief.md` and, when a previous
experiment exists, `research/last_train_summary.md`. Analyze that result before
choosing the next hypothesis. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, `run_research.ps1` runs the unchanged
control first; no LLM decision is needed.

The fixed held-out ranking is final-goal success rate, then median maximum
consecutive hold steps, then mean maximum consecutive hold steps, then closest
median distance.
Confirm a passing checkpoint by evaluating that same trained model on additional
held-out seeds; never retrain merely to confirm it. Keep the checkpoint with its
parameters, normalization, and optimizer.

When analyzing a completed experiment, record 3–6 short lines in
`research/postmortems.md`: result, behavior, what it rules out, and the next
idea.

The score decides. Preserve negative results. Never change the benchmark.
