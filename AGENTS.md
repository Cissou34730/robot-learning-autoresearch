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
- `tests/benchmark/` - immutable official-task tests: the objective, the official
  robot, the benchmark contract and the final goal verdict
- `tests/autoresearch/` - immutable generic AutoResearch harness tests: proposal
  and evaluation validation, execution lifecycle, persistence, lineage,
  protected paths, scenario boundary, console and brief presentation, and the
  generic training-artifact contract
- `tests/scenario/` - researcher-owned scenario tests: environment, reward,
  observations, curriculum, research evaluation
- `tests/training/` - researcher-owned learning-method tests: they describe the
  currently active method and evolve with it

## Conventions

- Training is headless; rendering only in play/viewer paths.
- Do not run repo-wide lint/format passes; format only files you touched.
- Tests are organized by repository domain. During a research campaign the
  researcher may modify only `tests/scenario/` and `tests/training/`;
  `tests/benchmark/` and `tests/autoresearch/` are human-owned and the runner
  rejects any proposal that creates, modifies, renames or deletes a file under
  them.
- Researcher-owned tests are ordinary research code: they travel with the
  experiment's `code_changes` and its Git code lineage.
- `tests/benchmark/` and `tests/autoresearch/` must stay method-neutral: they
  never import or assert against a concrete RL algorithm class.
- Validation timing, enforced by `research/run_experiment.py`:
  - fresh campaign baseline - complete validation before training, even with an
    unchanged worktree;
  - experiment with code changes (including researcher-owned tests) - complete
    validation before training;
  - parameter-only experiment - proposal and effective configuration only, no
    pytest;
  - continuation, evaluation or lineage decision without code changes - no test
    suites.
- Complete validation is: syntax check plus `ruff check` on changed Python
  files, JSON parse of changed `.json` files, a non-mutating `uv lock --check`
  when dependency metadata changed, then
  `pytest -q tests/benchmark tests/autoresearch tests/scenario tests/training`.
