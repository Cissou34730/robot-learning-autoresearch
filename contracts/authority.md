# Authority and file ownership

This contract states what each campaign role can read, write and execute.
`contracts/program.md` defines the research lifecycle.
`contracts/instruments.md` and its parts in `contracts/instruments/` define
the operation formats and the acceptance rules.

## Installed scientific stack

Scientific code uses the installed packages: native `mujoco==3.12.0` (the
`mujoco` package), `gymnasium==1.3.0` and `stable-baselines3==2.9.0`. The set
of dependencies is fixed and human-owned. `scientific_api_reference` returns
definitions from these installed libraries, in parts of limited size.

## Scientific coding roles

The PI delegates scientific source changes to the coder through
`scientific_coding`.

- The coder changes the exact files that the PI selected, and reads the files
  that the request permits. Its tools are `view`, `scientific_api_reference`
  and one file editor: `apply_patch`, or `create` and `edit`. The Runner alone
  executes code and operations.
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

The PI decides the content of these paths. The coder writes them within an
explicit request of the PI.

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
- `pi_workspace/scientific_model.md`, during the analyst session

Variant source files use `robot_learning/variants/<label>/<innerpath>`.
The label follows the training variant label format.
Each variant file has the ownership of `robot_learning/<innerpath>`.
Protected files keep their protection inside variants.
Each variant maps directly to the scientific package, in one level.

In these paths, the PI can keep, rewrite, combine, replace or remove any
implementation. The PI judges each option on the evidence. The existing
structure and the earlier work have the same standing as a new design.

## Human-owned paths

Campaign roles write the PI-owned paths alone. These human-owned paths have
priority over a PI-owned prefix:

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

You act through these tools. The Runner executes the operations that you
request through `submit_operation`. The Runner and the human keep all other
actions: file writes, shell commands, the execution of code, training, tests
and protected evaluation, dependency installation, the viewer and Git commands.

## Read access

Campaign roles can read `contracts/`, `campaigns/`, `pi_workspace/` and the
PI-owned scientific files. The analyst can also read all of `robot_learning/`.
Runner, benchmark, test, document, tool and script files are reserved in
every session. Reserved files stay reserved inside a readable folder. Read
`campaigns/results.jsonl` through `artifact_evidence_query`, by operation.

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
the structure, of the protected files and of the saved runtime. Scientific
code, diagnosis, repairs and interpretation belong to you.

## Analyst session

The analyst session writes `pi_workspace/scientific_model.md`. Its tools are
`view`, `rg`, `glob`, `apply_patch` for this file alone,
`artifact_evidence_query`, `training_log_query`,
`training_series_statistics`, `success_rate_pass_probability`,
`episode_outcome_breakdown` and `scientific_api_reference`. This list is
complete.
