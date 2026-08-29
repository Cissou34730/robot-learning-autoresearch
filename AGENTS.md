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

- `robot_learning/benchmark/final_contract.py`, `final_benchmark.py` - protected
  Human-owned final task semantics and evaluator
- `robot_learning/benchmark/` - final task metric implementation
- `robot_learning/scenario/` - everything specific to the current research
  problem: environment, observations, reward, evaluation, brief evidence, and a
  thin adapter over the protected benchmark. Generic code imports only the four
  functions re-exported by `robot_learning/scenario/__init__.py`.
- `robot_learning/train.py`, `play.py` - CLIs
- `research/current_params.json` - runtime configuration of the currently
  active training method. Reward and other scenario science
  live in `robot_learning/scenario/` as code.
- `research/program.md` - generic research protocol (read before touching `research/`)
- `research/scenario.md` - the current scientific problem
- `research/checkpoints/accepted/` - Git-versioned accepted policy
- `models/candidates/` - disposable training candidates

## Conventions

- Training is headless; rendering only in play/viewer paths.
- Do not run repo-wide lint/format passes; format only files you touched.
- Immutable benchmark tests live in `tests/benchmark/`; research-method tests
  live in `tests/research/`.
