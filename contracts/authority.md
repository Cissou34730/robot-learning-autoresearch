# Authority and file ownership

This contract states what each campaign role may read, write and execute.
`contracts/program.md` defines the research lifecycle.
`contracts/instruments.md` and its parts in `contracts/instruments/` define
operation formats and acceptance rules.

## Installed scientific stack

Scientific code targets the installed packages: native `mujoco==3.12.0` (not
legacy `mujoco-py`), `gymnasium==1.3.0` and `stable-baselines3==2.9.0`. The
dependency set is fixed and human-owned. `scientific_api_reference` returns
bounded definitions from these installed libraries.

## Scientific coding roles

The PI delegates scientific source changes through `scientific_coding`.

- The coder edits only the exact files that the PI selected and reads only its
  authorized files. Its tools are `view`, `apply_patch` and
  `scientific_api_reference`. It executes no code and submits no operations.
- An independent reviewer checks each new coding assignment. It reads the PI
  request, the supplied context and the actual change. Its tools are `view` and
  `scientific_api_reference`. It returns `validation`, `what_is_wrong`, `why`
  and `where`.
- A failed review goes to the same coder, within the same intent and file
  scope. The same reviewer then checks the repair.
- The PI receives the final change and review, or the requirement that blocked
  the work. Scientific choices, unclear requirements and unresolved repairs
  stay with the PI.

## PI-owned paths

The PI decides the content of these paths. The coder writes them only within
an explicit PI request.

- `robot_learning/scenario/`, except `robot_learning/scenario/__init__.py`, a
  minimal protected initializer; scenario modules import each other directly;
- `robot_learning/training/`, including `current_params.json` for active
  runtime configuration overrides;
- `robot_learning/train.py`, `robot_learning/evaluate.py` and
  `robot_learning/play.py`;
- `robot_learning/lab/`, for campaign analysis and diagnostic tools that are
  separate from policy and training recipes; Runner executes them through
  `python_module` measurements;
- `pi_workspace/scientific_model.md`, only during the preliminary session.

Within these paths the PI may retain, rewrite, combine, replace or remove any
implementation. The existing structure has no authority over that choice, and
no option has standing merely because it preserves prior work.

## Human-owned paths

Every path outside the PI-owned list is outside campaign write authority.
These human-owned paths take precedence over a PI-owned prefix:

- `contracts/` - task, robot, runtime, authority and process contracts;
- `benchmark/` - protected final and task-reference evaluation;
- `runner/` - Runner implementation and state;
- `campaigns/` - Runner-written campaign evidence;
- `tests/` - the validation suite;
- `docs/` and `tools/` - maintainer documents and utilities;
- `run_research.ps1`, `researcher_session.ps1` and `researcher_mutex.ps1` -
  launch scripts;
- `pyproject.toml` and `uv.lock` - the fixed dependency set;
- `robot_learning/__init__.py` and `robot_learning/scenario/__init__.py` -
  protected package initializers;
- `pi_workspace/scientific_model.md` after the preliminary session.

## PI sessions

In an ordinary session the PI has these tools:

- `view` to read one exact file, and `glob` (with `pattern` and `paths`) and
  `rg` to find files;
- `artifact_evidence_query` for JSON evidence and `training_log_query` for
  preserved training logs;
- `training_series_statistics` and `success_rate_pass_probability` for numeric
  summaries;
- `scientific_api_reference` for installed library definitions;
- `scientific_coding` to delegate source changes;
- `submit_operation` to request operations from Runner.

Some operations are outside PI authority. The PI does not write files, run
shell commands, execute code, training, tests or protected evaluation, install
dependencies, open the viewer or run Git commands. Runner executes the
operations that the PI requests through `submit_operation`.

## Read access

Campaign roles can read `contracts/`, `campaigns/`, `pi_workspace/` and the
PI-owned scientific files. The preliminary session can also read all of
`robot_learning/`. Runner, benchmark, test, maintainer and launch files are
reserved in every session. A readable directory does not make the reserved
files below it readable.

## Campaign files

- `campaigns/brief.md` - the generated current context;
- `campaigns/results.jsonl` - the authoritative completed-operation history;
- `campaigns/EXPERIMENTS.md` - the generated readable history;
- `campaigns/evaluations/` - detailed measurement artifacts;
- `campaigns/checkpoints/candidates/` and `campaigns/checkpoints/retained/` -
  archived training candidates and assigned model roles;
- `models/candidates/` - disposable training candidates;
- `pi_workspace/scientific_model.md` - the campaign-start physical model,
  frozen after the preliminary session.

## Runner

Runner validates and executes the operations that the PI requests and returns
factual results. Validation of structure, protected files and the saved
runtime is part of operation acceptance and training. Runner does not write
scientific code, diagnose failures, choose repairs or interpret results.

## Preliminary session

The campaign-start session writes `pi_workspace/scientific_model.md`. Its
tools are `view`, `rg`, `glob`, `apply_patch` limited to that file, a
restricted inspection shell, `artifact_evidence_query`, `training_log_query`,
`training_series_statistics`, `success_rate_pass_probability`
and `scientific_api_reference`. The shell permits read-only Git for code
provenance; Git history is not scientific evidence. The session does not
expose `scientific_coding` or `submit_operation`.
