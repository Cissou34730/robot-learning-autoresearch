# AGENTS.md

Virtual robotics RL playground (MuJoCo + Gymnasium + Stable-Baselines3, CPU-first).
Core loop: robot -> environment -> reward -> PPO training -> saved policy -> viewer.
Readability and tunability beat performance. Never hard-code movement logic.

## Commands

```bash
uv sync                                  # install dependencies
uv run python -m robot_learning.train    # train (see --help)
uv run python -m robot_learning.play --model <model.zip>   # watch in MuJoCo viewer
uv run pytest                            # tests
```

## Layout

- `robot_learning/environments/reach_env.py` - task: observations, episode, hold logic
- `robot_learning/rewards/reach_reward.py` - reward structure (values live in JSON, see below)
- `robot_learning/train.py`, `play.py` - CLIs
- `research/current_params.json` - single source of truth for ALL tunable parameters
- `research/program.md` - rules for autonomous research sessions (read before touching `research/`)
- `models/<timestamp>/` - training outputs, never overwrite silently

## Conventions

- Training is headless; rendering only in play/viewer paths.
- Do not run repo-wide lint/format passes; format only files you touched.
- Immutable task definition (threshold, hold duration, targets, evaluator): see
  `robot_learning/training/research_config.py`.
