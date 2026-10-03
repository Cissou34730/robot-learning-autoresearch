# AGENTS.md

Repository operational contract for the PI environment, command authority,
file ownership, validation, and evidence use.

The PI lifecycle is described in `research/program.md`, the current task in
`research/scenario.md`, and the available capability surface in
`research/instruments.md`.

## Environment

This repository uses a fixed Python stack built around MuJoCo, Gymnasium and
Stable-Baselines3. Dependencies are human-owned: the PI may use the
installed stack but may not install packages or modify `pyproject.toml` or
`uv.lock`.

The locked runtime APIs are native `mujoco==3.12.0` (not legacy `mujoco-py`),
`gymnasium==1.3.0` and `stable-baselines3==2.9.0`. PI-owned integrations
must target those packages and versions.

`jello` is available through the PI environment for JSON and JSONL artifacts.

All project Python execution goes through `uv run`. Never invoke system
`python`, `python3`, `pytest` or `ruff`, or the interpreter inside `.venv`.

```bash
uv run python <script>
uv run python -m <module>
uv run pytest <target>
uv run ruff <arguments>
```

## Command authority

The PI session may inspect files and, when the current bounded objective
requires understanding code state or a code delta, use read-only Git. It may
edit its owned surface, run lightweight analysis, and run targeted tests. It may
not install dependencies, execute training or protected evaluation directly,
open the viewer, run repository-wide or end-to-end tests, or use mutating Git
commands. Heavy scientific operations are requested through the contracts in
`research/instruments.md`.

## Layout

- `robot_learning/benchmark/` - human-owned final and task-reference contracts
  and evaluators.
- `robot_learning/scenario/` - current scenario implementation and scientific
  measurement code, with protected adapters to the human-owned panels. The
  protected `scenario/__init__.py` is a minimal package initializer, not a
  scientific extension point; PI-owned scenario modules import each
  other directly.
- `robot_learning/training/` - learning-method implementation and artifact
  support.
- `robot_learning/train.py`, `evaluate.py`, `play.py` - generic application
  entry points.
- `research/current_params.json` - active runtime configuration overrides.
- `research/results.jsonl` - authoritative completed-operation history.
- `research/EXPERIMENTS.md` - generated human-readable history.
- `research/brief.md` - generated current PI context.
- `research/scientific_model.md` - campaign-start PI model of the robot
  and task, frozen after the preliminary phase.
- `research/lab/` - campaign-scoped PI laboratory tools and analyses,
  separate from policy and training recipes.
- `research/evaluations/` - durable detailed development measurements.
- `research/checkpoints/candidates/` and `research/checkpoints/retained/` -
  archived training candidates and durable explicitly assigned model roles.
- `models/candidates/` - disposable training candidates.
- `tests/` - human-owned validation, outside the PI-owned scientific surface.

## Human-owned paths

The PI must not modify these paths during a scientific session:

- `docs/` - maintainer documents and campaign reports;
- `AGENTS.md`, `research/program.md`, `research/scenario.md`,
  `research/instruments.md`, `research/scientific_model.md` (after its
  campaign-start PI session);
- `run_research.ps1`, `researcher_mutex.ps1`, `researcher_session.ps1`,
  `researcher_copilot.py`;
- `tools/campaign_report.py`;
- `research/run_experiment.py`, `research/reset_campaign.py`, `research/runner_*.py`,
  `research/build_research_brief.py`, `research/query_training_log.py`;
- `pyproject.toml`, `uv.lock`;
- `robot_learning/benchmark/`;
- `robot_learning/policy_runtime.py`, `research/migrate_policy_runtime.py`;
- `robot_learning/robots/two_joint_arm.py` and
  `robot_learning/robots/two_joint_arm.xml`;
- `robot_learning/__init__.py`, `robot_learning/robots/__init__.py` and
  `robot_learning/scenario/__init__.py` (minimal protected package initializer);
- `robot_learning/scenario/final_benchmark.py` and
  `robot_learning/scenario/task_reference.py`;
- `tests/` - every test path; the PI does not create, modify or maintain
  test files.

A protected path takes precedence over any PI-owned prefix.

The Copilot adapter also rejects read/view requests and explicit shell-reader
targets matched by its shared reserved-script policy, including `docs/`.
`AGENTS.md` and the scientific Markdown under `research/` remain readable.
PI-owned scientific files remain readable, including entry points whose
direct execution is restricted. This is a tool-level restriction,
not an operating-system filesystem sandbox.

## PI-owned paths

- `robot_learning/scenario/`, except the protected files above;
- `robot_learning/training/`;
- `robot_learning/train.py`, `robot_learning/evaluate.py`,
  `robot_learning/play.py`;
- `research/current_params.json`;
- `research/lab/`;
- the preliminary deliverable `research/scientific_model.md` (only while its
  preliminary session is active);
- `research/operation_request.json` while a bounded scientific session is
  active.

Within this surface, the PI has unrestricted scientific authority.
Nothing is sacred, preferred, required to remain recognizable, or exempt from
replacement. It may create, rewrite, combine, or remove PI-owned
implementations and tools; the existing architecture carries no authority.

Tests are not part of the PI-owned surface. The PI does not
create, modify or maintain test files, and any path under `tests/` in its delta
is rejected as a path it does not own: it must drop those paths from the
operation rather than edit or restore them.

Durable campaign analysis and diagnostic tooling belongs under `research/lab/`.
It is separate from policy and training recipes. Scientific runtime changes
remain in the scenario and training surface.

## Validation

Do not run repository-wide lint or format passes. Format only touched files.

Keep validation proportional to the change. Every test or check must cover
changed behavior or a directly affected regression risk. Prefer existing
targeted tests or a minimal reproduction; do not add speculative, redundant,
or unrelated cases or build new test infrastructure for a minor fix.
If an unrelated environment problem blocks validation, report it instead of
expanding the task into a test-environment repair.

Tests cover executable behavior and explicit machine-readable contracts, never
documentation wording, headings, labels, source fragments, ordering, or
enumeration counts.

## Persistence and Git

The campaign artifacts, especially `research/brief.md`, the durable PI
checkpoint, completed operation records, and their artifacts, are the
authoritative sources of scientific evidence. Failed operations are execution
history, not evidence.

The PI may use read-only Git only when the current scientific objective requires
understanding code provenance or a code delta. Git history is not scientific
evidence and is not a routine workspace-discovery mechanism. Recipe restoration
uses the instrument contract rather than direct Git mutation.
