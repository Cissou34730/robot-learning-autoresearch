# Robot autoresearch

Each research session prepares exactly one experiment, then exits. The runner
owns training, checkpoints, evaluation, rollback, and commits, and starts the
next research session automatically. The overall research loop continues until
the human stops it.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay
within 1 cm for 2 seconds. With the fixed control timestep, those 2 seconds are
currently 100 consecutive control steps; the duration is the source of truth
and the step count is derived from it. Never edit `robot_learning/benchmark/`,
the robot, physics, environment mechanics, evaluator, runner, or
`tests/benchmark/`.
The protected evaluation target is always the final 1 cm / 2 s goal, not a
restriction on training.

## Research surface

You may modify the research training surface, including
`robot_learning/train.py` and the tunable configuration. Any training method is
fair game. Do not follow a prescribed list of techniques: use the evidence to
decide what to try.

Test one identifiable hypothesis per experiment. It may require multiple
coherent edits. Write `research/proposal.json`, make the corresponding
research-surface edits when needed, then exit. Use `"kind": "training"` for a
model or training-recipe experiment and `"kind": "method"` for a change to the
research method. Do not launch training or the runner: `run_research.ps1`
verifies the protected files and executes the proposal after your process
exits.

At the start of each session, read `research/brief.md` and, when a previous
experiment exists, `research/last_train_summary.md`. Analyze that result before
choosing the next hypothesis. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, `run_research.ps1` runs the unchanged
control first; no LLM decision is needed.

## Selection method v2

During training, evaluate the policy after completed learning updates on 50
fixed development episodes. Rank checkpoints by success count, then—only for
failed episodes—longest consecutive in-circle hold, steps inside the best
100-step window, and cumulative distance outside the 1 cm boundary in that
window. Keep the top three checkpoints with their normalization and optimizer
state.

After 120,000 steps, run one tournament containing those three checkpoints and
the accepted champion. Evaluate every contender on the same 200 episodes for
seeds 1000, 3000, and 5000. Rank them by seeds reaching 98%, worst-seed success,
pooled success, then the failed-episode progress metrics above. Extend close
decisions with more seeds. The winner becomes the champion; an exact tie keeps
the incumbent. Archive the best candidate from every completed experiment.

Training verdicts are `promoted`, `champion retained`, or `invalid`. Research
method verdicts are `method adopted` or `method rejected`. A method decision is
independent from whether the next trained model beats the champion.

When analyzing a completed experiment, record 3–6 short lines in
`research/postmortems.md`: result, behavior, what it rules out, and the next
idea.

The tournament decides model promotion. Preserve negative results and archived
challengers. Never change the benchmark.
