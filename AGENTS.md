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

The Copilot agent runtime uses `github-copilot-sdk==1.0.19`. Its native
subagents, hooks and custom tools are harness integration, not an interchangeable
model-provider interface. The scientific stack and Runner operations remain
separate from the SDK. Dependencies remain human-owned.

JSON evidence is read through `artifact_evidence_query`; preserved training
logs are read through `training_log_query`. Both tools support scoped requests
and complete retrieval. The PI chooses the requested content and may inspect
successive subsets. Large results report their continuation explicitly rather
than silently truncating. No general Python-query execution tool is exposed.

All project Python execution goes through `uv run`. The PI must not execute
tests or repository validation commands directly; request Runner validation
through the contracts in `contracts/instruments.md`. Never invoke system
`python`, `python3`, `pytest` or `ruff`, or the interpreter inside `.venv`.

## Command authority

The ordinary Copilot main PI session may inspect files and call
`submit_operation`; it has no file-write tools. The trusted launcher validates
and executes the structured request through Runner and returns factual results
and current state to the same conversation. Scientific source edits use the
`scientific_coding` tool, which dispatches a native Copilot coding subagent.
The main agent's tool set excludes file writes; only the registered coder
receives scoped `view` and `apply_patch`. Its readable and writable files are
bound mechanically to the explicit request. Copilot main and coding agents
have no shell tools. Native start instructions remind the coder of the locked
scientific API versions above; it cannot install or change dependencies.
Analysis code is authored in the PI laboratory and executed by Runner.
The preliminary analyst retains its existing tools and scientific-model
publication permission; coding delegation is not exposed in that phase.
These SDK interfaces apply to Copilot. The optional OpenCode backend retains
its legacy request-file, scientific-edit and command-policy interfaces; it does
not expose `submit_operation` or `scientific_coding`. Its launcher and Runner
ownership, validation and bounded-session controls remain unchanged.
Read-only Git remains permitted when the bounded objective requires code
provenance or a delta, not as routine discovery. No PI session may inspect,
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
matched by the shared reserved-script policy. Searches must apply that policy
to descendants before reading their contents or returning their paths; a
readable repository root does not authorize all files below it. Copilot
directory enumeration uses scoped `glob`, not directory `view`. Preliminary
shell traversal and wildcard readers are denied; exact permitted file reads
remain available. Maintainer documents under `docs/`, `tests/`, and harness
scripts remain reserved in every phase.
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
- `pi_workspace/operation_request.json` is internal Copilot controller/Runner
  exchange, not a main PI writable path. OpenCode retains legacy proposal
  authoring at this path while a bounded scientific session is active.

Within this surface, the PI has unrestricted scientific authority. Retain,
rewrite, combine, replace, or remove PI-owned implementations and tools
according to the scientific question and the evidence. Existing structure has
no authority over that choice, and no option has standing merely because it
preserves prior work.
This is scientific ownership, not direct main-session write permission.
The coding child cannot write operation requests or campaign/state files.
Its native handle supports same-change corrections within the current bounded
context without expanding file scope. A handle from another context is not an
authorization to attach a coder. Lifecycle hooks and actual change reports
support main-PI review; they do not certify scientific validity or add a
scientific decision-maker.
The Copilot runtime remains alive across operations and bounded contexts.
Ordinary results continue in the same context; checkpoints end it, and the
launcher starts a fresh context from durable state. An interrupted or lost
response must be recovered from existing pending/completed Runner state, not
blindly resubmitted. Publication failures stop for repair; they do not authorize
reacceptance or re-execution.

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
