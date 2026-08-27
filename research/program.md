# Robot autoresearch

Run exactly one experiment, then stop. The runner owns checkpoints, curriculum
promotion, evaluation, rollback, and commits.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay
within 1 cm for 2 seconds. Never edit `robot_learning/benchmark/`, the robot,
physics, environment mechanics, evaluator, runner, or `tests/benchmark/`.
The runner's current stage is the protected evaluation target, not a restriction
on training.

## Research surface

You may change rewards, observations, PPO/SAC choice, network size, exploration,
schedules, and all whitelisted training parameters. You also own the training
curriculum through `params.curriculum.segments`: choose any ordered benchmark
stages and positive fractions summing to 1.0. The model, normalization state,
optimizer, and replay buffer continue across segments. A fresh algorithm may
start at stage 0 and finish at the current evaluation stage. Never modify the
global stage in `research/research_state.json` directly.

Use one hypothesis and one coherent change. Write `research/proposal.json`, make
the corresponding research-surface edit when needed, then stop. Do not launch
training or the runner: `run_research.ps1` verifies the protected files and runs
the experiment after your process exits.

Read `research/brief.md` before choosing. Read `research/last_train_summary.md`
after training. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, `run_research.ps1` runs the unchanged
control first; no LLM decision is needed.

The current-stage held-out success rate decides first, then closest distance.
Earlier stages may not regress. Confirm a passing checkpoint by evaluating that
same trained model on additional held-out seeds; never retrain merely to confirm
a promotion. Promote the checkpoint with its parameters, normalization, and
optimizer. The final 1 cm / 2 s score remains a parallel global measurement.

Record 3–6 short lines in `research/postmortems.md`: result, behavior, what it
rules out, and the next idea. Then stop.

The score decides. Preserve negative results. Never change the benchmark.
