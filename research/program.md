# RL Research Program - Scenario 2: "Reach and Hold"

You are an autonomous research agent. Execute exactly one experiment per
session, then stop. Do not create subagents.

## Environment and bounded context

- Windows PowerShell: use PowerShell-native commands.
- Start with `research/brief.md`; it is the compact source of research state.
- Use `research/last_train_summary.md`, never the full training log, unless the
  summary explicitly says parsing failed.
- Do not read full `EXPERIMENTS.md`, `postmortems.md`, or `archive.md`
  unless one specific ambiguity cannot be resolved from the brief.
- Modified generated research files are normal. Never edit
  `research/EXPERIMENTS.md`; the runner owns it.
- Do not inspect runner or immutable-task source during an experiment. Input
  errors reported by SUMMARY are authoritative.

## Repository map

```
research/brief.md                    # compact default context
research/last_train_summary.md       # compressed training dynamics
research/current_params.json         # tunable parameters
research/proposal.json               # agent-written experiment proposal
research/postmortems.md              # full scientific memory; append only
robot_learning/rewards/reach_reward.py
robot_learning/environments/reach_env.py
tests/test_reach_env.py
```

For learning-algorithm experiments only, the runner additionally permits
focused edits to `robot_learning/train.py`, `evaluate.py`, and `play.py`.

## Immutable mission

Success means the end-effector remains within 1.0 cm of a random target for 100
consecutive control steps (2.0 s). Targets remain 6–20 cm from the base,
episodes remain at most 500 steps, evaluation remains 200 episodes, and the goal
is at least 98% success.

Training uses a transfer curriculum initialized from the solved experiment-19
3 cm policy. The curriculum may ease intermediate stages, but its final stage
and every evaluation must retain the immutable 1 cm / 2 s task.

## Escalation ladder

After five consecutive failures in a class, follow `ESCALATION_REQUEST`:

1. coefficient and hyperparameter tuning
2. reward structure
3. observation representation
4. training curriculum
5. policy architecture and training schedule
6. learning algorithm
7. broader goal-preserving training-method changes

## Experiment modes

Use one coherent hypothesis and exactly one mode:

- Parameter mode: put changes under `"params"` in `proposal.json`; do not
  edit code.
- Code mode: make only the allowed focused edits and omit `"params"`.

Every proposal contains `change`, `hypothesis`, `class`, and optionally
`initialization`:

- `"transfer"` is the default and resumes the experiment-19 checkpoint.
- `"fresh"` is allowed from observation representation onward when checkpoint
  compatibility would be invalid, including observation-size, policy-
  architecture, and learning-algorithm changes.

The runner rejects policy-architecture parameter changes under transfer
initialization because checkpoint tensor shapes may not match.

Allowed parameter keys:

- reward: `PROGRESS_COEFFICIENT`, `CLOSENESS_COEFFICIENT`,
  `CLOSENESS_LENGTH_SCALE`, `ACTION_COST_COEFFICIENT`,
  `DWELL_BONUS_PER_STEP`, `HOLD_COMPLETE_BONUS`
- ppo: `learning_rate`, `gamma`, `gae_lambda`, `n_steps`, `batch_size`,
  `n_epochs`, `clip_range`, `ent_coef`, `vf_coef`, `max_grad_norm`,
  `target_kl`
- policy: `net_arch`, `activation`
- env: training-only curriculum advancement rate and minimum-episode settings

Never change robot physics, success threshold, final hold duration, target
distribution, evaluator, seed, episode count, or the goal.

## Protocol

1. Stop if `GOAL_REACHED` exists. Obey `ESCALATION_REQUEST` if present.
2. Read `research/brief.md` and `git log --oneline -8`.
3. Form one falsifiable hypothesis and write `research/proposal.json`.
4. Run exactly `uv run python research/run_experiment.py`.
5. Read the SUMMARY line. Fix and rerun once only for a trivial input error.
6. Read `research/last_train_summary.md` and interpret behavior beyond score.
7. Append a 300–500 word postmortem containing:
   - whether the hypothesis was supported
   - approach distance, hold/stability behavior, and curriculum progression
   - the likely binding constraint
   - what must not be retried
   - the recommended next class
8. Run `uv run python research/build_research_brief.py`, then stop.

## Budget

Each experiment uses 120000 training steps with seed 0. Only the experimenter
may change this budget between sessions.
