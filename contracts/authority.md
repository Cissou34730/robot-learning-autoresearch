# Authority and file ownership

This contract states what each campaign role may read, write and execute.
`contracts/program.md` defines the research lifecycle.
`contracts/instruments.md` and its parts in `contracts/instruments/` define
the operation formats and the acceptance rules.

## Installed scientific stack

Scientific code uses the installed packages: native `mujoco==3.12.0` (not the
old `mujoco-py`), `gymnasium==1.3.0` and `stable-baselines3==2.9.0`. The set of
dependencies is fixed and human-owned. `scientific_api_reference` returns
definitions from these installed libraries, in parts of limited size.

## Scientific coding roles

The PI delegates scientific source changes to the coder through
`scientific_coding`.

- The coder changes only the exact files that the PI selected. It reads only
  the files that the request permits. Its tools are `view`, `apply_patch` and
  `scientific_api_reference`. It executes no code and submits no operations.
- An independent reviewer checks each new coding request. It reads the request
  of the PI, the supplied context and the actual change. Its tools are `view`
  and `scientific_api_reference`. It returns `validation`, `what_is_wrong`,
  `why` and `where`.
- When a review fails, the same coder receives it, with the same intent and the
  same files. The same reviewer then checks the repair.
- The PI receives the final change and the review, or the requirement that
  stopped the work. Scientific choices, unclear requirements and unresolved
  repairs stay with the PI.

## PI-owned paths

The PI decides the content of these paths. The coder writes them only within
an explicit request of the PI.

- `robot_learning/scenario/`, except `robot_learning/scenario/__init__.py`,
  which is a minimal protected initializer. The modules in this folder import
  each other directly.
- `robot_learning/training/`, which includes `current_params.json` for the
  active overrides of the runtime configuration
- `robot_learning/train.py`, `robot_learning/evaluate.py` and
  `robot_learning/play.py`
- `robot_learning/lab/`, for the analysis and diagnostic tools of the campaign.
  These tools are separate from the policy and from the training recipe. The
  Runner executes them through `python_module` measurements.
- `pi_workspace/scientific_model.md`, only during the analyst session

In these paths, the PI may retain, rewrite, combine, replace or remove any
implementation. The existing structure has no authority over this choice. No
option has standing merely because it preserves earlier work.

## Human-owned paths

No campaign role can write a path that is not in the PI-owned list. These
human-owned paths have priority over a PI-owned prefix:

- `contracts/` - the task, robot, runtime, authority and process contracts
- `benchmark/` - the protected official and task-reference evaluation
- `runner/` - the Runner source code and state
- `campaigns/` - the campaign evidence that the Runner writes
- `tests/` - the validation suite
- `docs/` and `tools/` - the documents and the tools
- `run_research.ps1`, `researcher_session.ps1` and `researcher_mutex.ps1` -
  the scripts
- `pyproject.toml` and `uv.lock` - the fixed dependencies
- `robot_learning/__init__.py` and `robot_learning/scenario/__init__.py` -
  the protected package initializers
- `pi_workspace/scientific_model.md` after the analyst session

## PI sessions

In a PI session, you have these tools:

- `view` to read one exact file, and `glob` (with `pattern` and `paths`) and
  `rg` to find files
- `artifact_evidence_query` for JSON evidence and `training_log_query` for the
  preserved training logs
- `training_series_statistics`, `success_rate_pass_probability` and
  `episode_outcome_breakdown` for numeric summaries
- `scientific_api_reference` for the definitions of the installed libraries
- `scientific_coding` to delegate source changes to the coder
- `submit_operation` to request operations from the Runner

Some actions are outside your authority. You do not write files or run shell
commands. You do not execute code, training, tests or protected evaluation. You
do not install dependencies, open the viewer or run Git commands. The Runner
executes the operations that you request through `submit_operation`.

## Read access

Campaign roles can read `contracts/`, `campaigns/`, `pi_workspace/` and the
PI-owned scientific files. The analyst can also read all of `robot_learning/`.
Runner, benchmark, test, document, tool and script files are reserved in
every session. A readable folder does not make the reserved files in it
readable. Read `campaigns/results.jsonl` through `artifact_evidence_query` by
operation, not through `view` or a search.

## Campaign files

- `campaigns/brief.md` - the current context, generated
- `campaigns/results.jsonl` - the authoritative history of completed
  operations
- `campaigns/EXPERIMENTS.md` - the readable history, generated
- `campaigns/evaluations/` - the detailed measurement artifacts
- `campaigns/checkpoints/candidates/` and `campaigns/checkpoints/retained/` -
  the archived candidates and the candidates with roles
- `models/candidates/` - the temporary candidates from training
- `pi_workspace/scientific_model.md` - the scientific model: the initial
  physical model of the campaign, frozen after the analyst session

## Runner

The Runner validates and executes the operations that you request, and returns
factual results. Operation acceptance and training include the validation of
the structure, of the protected files and of the saved runtime. The Runner does
not write scientific code, diagnose failures, choose repairs or interpret
results.

## Analyst session

The analyst session writes `pi_workspace/scientific_model.md`. Its tools are
`view`, `rg`, `glob`, `apply_patch` for this file only,
`artifact_evidence_query`, `training_log_query`,
`training_series_statistics`, `success_rate_pass_probability`,
`episode_outcome_breakdown` and `scientific_api_reference`. This session does
not expose a shell, `scientific_coding` or `submit_operation`.
