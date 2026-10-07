# AGENTS.md

Repository operational contract for the PI environment, command authority,
file ownership, validation, and evidence use.

The PI lifecycle is described in `contracts/program.md`, the current task in
`contracts/scenario.md`, and the available capability surface in
`contracts/instruments.md`.

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
edit its owned surface and run lightweight analysis. It may not inspect,
modify, or directly execute the human-owned test suite; install dependencies;
execute training or protected evaluation directly; open the viewer; or use
mutating Git commands. Runner validation and heavy scientific operations are
requested through the contracts in `contracts/instruments.md`.

## Layout

- `contracts/` - human-owned task, robot, and runtime contracts that are
  PI-readable but not PI-writable.
- `benchmark/` - human-owned final and task-reference contracts
  and evaluators, hidden from the PI.
- `runner/` - human-owned lifecycle runner, protocol enforcement and state,
  hidden from the PI.
- `pi_workspace/` - bounded PI/Runner exchange files.
- `campaigns/` - Runner-written, PI-readable campaign evidence.
- `robot_learning/scenario/` - current scenario implementation and scientific
  measurement code. The protected `scenario/__init__.py` is a minimal package
  initializer, not a scientific extension point; PI-owned scenario modules
  import each other directly.
- `robot_learning/training/` - learning-method implementation and artifact
  support.
- `robot_learning/train.py`, `evaluate.py`, `play.py` - generic application
  entry points.
- `robot_learning/training/current_params.json` - active runtime configuration overrides.
- `campaigns/results.jsonl` - authoritative completed-operation history.
- `campaigns/EXPERIMENTS.md` - generated human-readable history.
- `campaigns/brief.md` - generated current PI context.
- `pi_workspace/scientific_model.md` - campaign-start PI model of the robot
  and task, frozen after the preliminary phase.
- `robot_learning/lab/` - campaign-scoped PI laboratory tools and analyses,
  separate from policy and training recipes.
- `campaigns/evaluations/` - durable detailed development measurements.
- `campaigns/checkpoints/candidates/` and `campaigns/checkpoints/retained/` -
  archived training candidates and durable explicitly assigned model roles.
- `models/candidates/` - disposable training candidates.
- `tests/` - human-owned validation, outside the PI-owned scientific surface.

## Human-owned paths

The PI must not modify these paths during a scientific session:

- `docs/` - maintainer documents and campaign reports;
- `contracts/` - human-owned contracts readable by the PI;
- `campaigns/` - Runner-written evidence readable by the PI;
- `runner/` - lifecycle runner and protocol enforcement;
- `benchmark/` - final and task-reference evaluation implementation;
- `tools/` - maintainer utilities;
- `researcher_opencode/` - optional runtime implementation;
- `AGENTS.md`, `contracts/program.md`, `contracts/scenario.md`,
  `contracts/instruments.md`, `pi_workspace/scientific_model.md` (after its
  campaign-start PI session);
- `run_research.ps1`, `researcher_mutex.ps1`, `researcher_session.ps1`,
  `runner/copilot_adapter.py`;
- `tools/campaign_report.py`;
- `runner/run_experiment.py`, `runner/reset_campaign.py`, `runner/*.py`,
  `runner/build_brief.py`, `runner/query_training_log.py`;
- `pyproject.toml`, `uv.lock`;
- `contracts/policy_runtime.py`, `runner/migrate_policy_runtime.py`;
- `contracts/robots/two_joint_arm.py` and
  `contracts/robots/two_joint_arm.xml`;
- `robot_learning/__init__.py`, `contracts/robots/__init__.py` and
  `robot_learning/scenario/__init__.py` (minimal protected package initializer);
- `tests/` - every test path; the PI does not create, modify or maintain
  test files.

A protected path takes precedence over any PI-owned prefix.

The preliminary phase can inspect scientific sources under `robot_learning/`
to construct the physical model.
Later phases reject read/view requests and explicit shell-reader targets
matched by the shared reserved-script policy. Maintainer documents under
`docs/`, `tests/`, and harness scripts remain reserved in every phase.
`AGENTS.md`, `contracts/`, and `campaigns/` remain readable.
PI-owned scientific files remain readable, including entry points whose
direct execution is restricted. Read access does not change write authority.
Direct-execution restrictions remain unchanged. This is a tool-level restriction,
not an operating-system filesystem sandbox.

## PI-owned paths

- `robot_learning/scenario/`, except the protected files above;
- `robot_learning/training/`;
- `robot_learning/train.py`, `robot_learning/evaluate.py`,
  `robot_learning/play.py`;
- `robot_learning/training/current_params.json`;
- `robot_learning/lab/`;
- the preliminary deliverable `pi_workspace/scientific_model.md` (only while its
  preliminary session is active);
- `pi_workspace/operation_request.json` while a bounded scientific session is
  active.

Within this surface, the PI has unrestricted scientific authority. Retain,
rewrite, combine, replace, or remove PI-owned implementations and tools
according to the scientific question and the evidence. Existing structure has
no authority over that choice, and no option has standing merely because it
preserves prior work.

Tests are not part of the PI-owned surface. The PI does not
inspect, create, modify, maintain, or directly execute test files. Any path
under `tests/` in its delta is rejected as a path it does not own: it must drop
those paths from the operation rather than edit or restore them. The Runner
retains responsibility for validation.

Durable campaign analysis and diagnostic tooling belongs under `robot_learning/lab/`.
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

The campaign artifacts, especially `campaigns/brief.md`, the durable scientific
session record, completed operation records, and their artifacts, are the
authoritative sources of scientific evidence. Failed operations are execution
history, not evidence.

The PI may use read-only Git only when the current scientific objective requires
understanding code provenance or a code delta. Git history is not scientific
evidence and is not a routine workspace-discovery mechanism. Recipe restoration
uses the instrument contract rather than direct Git mutation.
