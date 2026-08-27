# Robot autoresearch

Run exactly one experiment, then stop. The runner owns checkpoints, evaluation,
rollback, and commits.

## Fixed benchmark

Train the MuJoCo two-joint arm to reach a random target 6–20 cm away and stay
within 1 cm for 2 seconds. Never edit `robot_learning/benchmark/`, the robot,
physics, environment mechanics, evaluator, runner, or `tests/benchmark/`.
The protected evaluation target is always the final 1 cm / 2 s goal, not a
restriction on training.

## Research surface

You may change rewards, observations, PPO/SAC choice, network size, exploration,
schedules, all whitelisted training parameters, and `robot_learning/train.py`.
Training defaults to the final 1 cm / 2 s task for the full fixed budget. There
is no preconfigured curriculum API. If a curriculum is your hypothesis, design
and implement it as the single coherent training-method change for that
experiment. Never modify the evaluation target in
`research/research_state.json` directly.

Use one hypothesis and one coherent change. Write `research/proposal.json`, make
the corresponding research-surface edit when needed, then stop. Do not launch
training or the runner: `run_research.ps1` verifies the protected files and runs
the experiment after your process exits.

Read `research/brief.md` before choosing. Read `research/last_train_summary.md`
after training. Do not paste full logs or histories into context.

If `research/BASELINE_PENDING` exists, `run_research.ps1` runs the unchanged
control first; no LLM decision is needed.

The final-goal held-out success rate decides first, then closest distance.
Confirm a passing checkpoint by evaluating that same trained model on additional
held-out seeds; never retrain merely to confirm it. Keep the checkpoint with its
parameters, normalization, and optimizer.

Record 3–6 short lines in `research/postmortems.md`: result, behavior, what it
rules out, and the next idea. Then stop.

The score decides. Preserve negative results. Never change the benchmark.
