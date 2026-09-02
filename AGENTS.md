# AGENTS.md

Repository operational contract: environment, commands, layout, ownership,
validation and Git conventions.

The Researcher protocol is defined in `research/program.md`, the current task in
`research/scenario.md`, and the available capability surface in
`research/instruments.md`.

## Environment

This repository uses a fixed Python stack built around MuJoCo, Gymnasium and
Stable-Baselines3. Dependencies are human-owned: the Researcher may use the
installed stack but may not install packages or modify `pyproject.toml` or
`uv.lock`.

All project Python execution goes through `uv run`. Never invoke system
`python`, `python3`, `pytest` or `ruff`, or the interpreter inside `.venv`.

```bash
uv run python <script>
uv run python -m <module>
uv run pytest <target>
uv run ruff <arguments>
```

## Command ownership

```bash
uv sync                                  # Human: install the fixed dependencies
uv run python -m robot_learning.train    # Runner: train a policy
uv run python -m robot_learning.play --model <model.zip>  # Human: open the viewer
uv run pytest                            # Runner: complete test suite
```

The bounded Researcher session may inspect files and Git history, edit its owned
surface, run lightweight analysis, and run targeted tests. It may not execute
training, the generic evaluator, the viewer, the Runner, the final benchmark,
repository-wide tests, mutating Git commands or dependency-management commands.
The exact available operations are cataloged in `research/instruments.md`.

## Layout

- `robot_learning/benchmark/` - human-owned final and task-reference contracts
  and evaluators.
- `robot_learning/scenario/` - current scenario implementation and scientific
  measurement code, with protected adapters to the human-owned panels.
- `robot_learning/training/` - learning-method implementation and artifact
  support.
- `robot_learning/train.py`, `evaluate.py`, `play.py` - generic application
  entry points.
- `research/run_experiment.py` - Runner CLI and lifecycle orchestration.
- `research/runner_*.py` - Runner protocol, execution, persistence, paths and
  console implementation.
- `research/current_params.json` - active runtime configuration overrides.
- `research/results.jsonl` - authoritative experiment history.
- `research/EXPERIMENTS.md` - generated human-readable history.
- `research/brief.md` - generated current Researcher context.
- `research/evaluations/` - durable detailed development measurements.
- `research/checkpoints/accepted/` and `research/checkpoints/retained/` - reusable
  policy lineages.
- `models/candidates/` - disposable training candidates.
- `tests/benchmark/`, `tests/autoresearch/`, `tests/scenario/`,
  `tests/training/` - tests grouped by ownership domain.

## Human-owned paths

The Researcher may read but not modify these paths through an experiment:

- `AGENTS.md`, `research/program.md`, `research/scenario.md`,
  `research/instruments.md`;
- `run_research.ps1`, `researcher_session.ps1`, `researcher_copilot.py`;
- `research/run_experiment.py`, `research/runner_*.py`,
  `research/build_research_brief.py`, `research/query_training_log.py`;
- `pyproject.toml`, `uv.lock`;
- `robot_learning/benchmark/`;
- `robot_learning/robots/two_joint_arm.py` and
  `robot_learning/robots/two_joint_arm.xml`;
- `robot_learning/__init__.py`, `robot_learning/robots/__init__.py` and
  `robot_learning/scenario/__init__.py`;
- `robot_learning/scenario/final_benchmark.py` and
  `robot_learning/scenario/task_reference.py`;
- `tests/benchmark/` and `tests/autoresearch/`.

Protection is enforced centrally by `research/runner_protocol.py`. A protected
path takes precedence over any researcher-owned prefix.

## Researcher-owned paths

- `robot_learning/scenario/`, except the protected files above;
- `robot_learning/training/`;
- `robot_learning/train.py`, `robot_learning/evaluate.py`,
  `robot_learning/play.py`;
- `tests/scenario/`, `tests/training/`;
- `research/current_params.json`;
- the phase deliverables `research/proposal.json`,
  `research/evaluation_request.json` and `research/postmortems.md`.

Scientific analysis, diagnostics and temporary tooling must be created within a
researcher-owned code prefix. They are ordinary experiment code: they travel
with its code lineage and validation, and are not an ignored scratch surface.

## Validation

Do not run repository-wide lint or format passes. Format only touched files.

The Runner's complete validation is syntax checking plus `ruff check` on changed
Python files, JSON parsing for changed JSON files, and selected pytest suites.
A fresh baseline and changes outside the positively declared researcher-owned
surface receive complete validation. Researcher-owned code changes omit only
`tests/benchmark`; parameter-only proposals and decisions without code changes
run no suites.

Tests assert the behavior owned by their domain. Human-owned benchmark and
AutoResearch tests remain method-neutral. Architecture guards derive the
surface they protect rather than naming one implementation file.

## Persistence and Git

The Runner owns mutating Git operations and experiment persistence. The
Researcher has read-only Git access.

`research/results.jsonl` is written before `research/EXPERIMENTS.md` is
regenerated atomically. Validation-only commands do not reconcile or mutate the
derived view. Researcher-owned tests and scientific code travel together in the
experiment's `code_changes` and Git lineage.
