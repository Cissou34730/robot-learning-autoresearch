# AGENTS.md

Instructions for AI coding agents (Codex, Copilot, OpenCode) working on this repository.

## Project overview

Local virtual robotics learning playground for reinforcement learning experimentation.
Not production robotics — prioritize readability, explicitness, and easily adjustable
parameters over performance optimization.

Stack: Python 3.13+, MuJoCo (physics), Gymnasium (env API), Stable-Baselines3 (PPO/SAC),
PyTorch (NN backend). Dependency management via **uv**. Must work CPU-only; GPU is optional.

Core loop: observation → action → MuJoCo simulation → new state → reward → learning.
Behavior must emerge from the reward function and available actions — never hard-code
movement logic.

## Commands

```bash
uv sync                      # install/sync dependencies
uv run python -m robot_learning.train --env <env> [--resume <path>]   # train an agent
uv run python -m robot_learning.play --model <path>                   # watch trained agent in MuJoCo viewer
uv run pytest                # run tests
uv run ruff check .          # lint
uv run ruff format .         # format
uv run mypy .                # type check
```

Note: mypy is not configured yet. Verify actual command names before relying on them.

## Architecture

Keep these concepts separate and identifiable:

- `robots/` — robot definitions (MuJoCo XML morphologies + physics). A robot definition
  must be reusable across scenarios without duplicating its physical model.
- `environments/` or `tasks/` — Gymnasium environments wrapping robots: observations,
  actions, termination, terrain, difficulty settings.
- `rewards/` — reward functions. They must be explicit, easy to locate, read and modify.
  Do NOT hide reward logic behind abstraction layers — prefer plain readable functions
  with named coefficients.
- `training/` — training configuration and scripts (SB3). Training results are saved under
  `models/` and must never be overwritten silently. Prefer resuming from a saved policy
  over restarting from scratch when the setup is compatible.
- `configs/` — hyperparameters and experiment configurations.

## Conventions

- Increase task/environment difficulty (constraints, terrain, randomization, objectives)
  before changing the robot itself.
- Training must render nothing (headless); rendering happens only in the viewer/play path.
- Random seeds should be configurable for reproducibility.
- Keep abstractions minimal: introduce one only when there is an actual reuse problem.

## Verification

Before declaring a change done:

1. `uv run ruff check .` and `uv run ruff format --check .`
2. Type check if configured (`uv run mypy .`)
3. Run relevant tests with `uv run pytest`
4. For env/reward changes: short smoke training run (e.g., a few thousand steps) to prove
   the loop runs end-to-end without error.
