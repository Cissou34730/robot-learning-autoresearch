# Scientific instruments: coding

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Saved controller execution

A saved candidate contains the policy weights, the normalization state when the
policy uses one, and the executable saved runtime that
`contracts/policy_runtime.py` defines.

The task-reference evaluation and the official assessment use protected
environments. The research evaluation uses the PI-owned research environment.

The protected environment calls the saved `io.observe(data)` to build each
observation. The saved runtime computes the network output with its
normalization state. The environment calls `io.action(policy_action)`. Then it
validates the result and clips it before it applies it to the robot. At each
episode reset, it calls the optional `io.reset()` callback.

In protected evaluation, control logic has an effect when the saved runtime
executes it. The protected environment calls the saved runtime alone. The
PI-owned research environment can apply additional control logic outside the
saved runtime. Compare the motor commands of the two environments directly to
establish that they are identical.

A training operation is the only source of a candidate. Training and the export
of its training checkpoints use `make_policy_io()` in
`robot_learning/scenario/policy_io.py`. Thus each candidate contains the saved
runtime that this source file defined when the candidate was trained. A runtime
change becomes part of a candidate when two conditions are true: this source
file contains the change, and a training run uses it. The training run can use
`fresh` or `transfer` initialization.

A `python_module` measurement that runs the weights of an existing candidate
with another runtime is a diagnostic. It can justify a training run. Each
candidate stays as its training run saved it. Measurement artifacts stay
measurement artifacts.

## Scientific coding interface

`scientific_coding` delegates a bounded change of PI-owned source code to the
coder: a new method, a measurement or analysis tool, or a repair.
`contracts/authority.md` defines the roles of the coder and the reviewer.

By default, a PI session ends after 6 hours of active session time. This time
includes the time of the coder and the reviewer. It excludes the time that you
wait for the Runner.

`scientific_coding` accepts these fields:

- `intent`: the precise expected output of the bounded change
- `allowed_paths`: the exact scientific files that the coder can write,
  relative to the repository
- `read_paths`: optional. Other relevant scientific sources, contracts or the
  frozen scientific model `pi_workspace/scientific_model.md`.
- `source_context`: optional. The requirements, the caller context and the
  errors that you select.
- `session_handle`: optional. The returned identity of the coder, for
  corrections of the same change in this session.
- `evidence_inputs`: optional, for new calls only. Up to 10 recorded inputs that
  the changed code will read. Give a measurement artifact as `operation_id` and
  `artifact_index`. The coder and the reviewer then receive its recorded
  structure inventory: the JSON paths and the field names. Give a candidate as
  `candidate` (identity or role). They then receive its archive path, its file
  names and its `artifact.json` metadata.

A new call requires `intent` and `allowed_paths`. A correction gives
`session_handle` and `intent`, and optionally `source_context`.

A correction keeps the stored scope. A scope field that you give again is the
same as the stored one, or the Runner rejects the changed field and gives its
name. For a new scope, make a new call and omit the handle. A handle is valid
in the current session.

The coder writes PI-owned files alone. The tool refuses protected paths,
folders, wildcards, operation requests and paths outside the repository. The
rejection gives the path and the reason. The tool creates the parent folder of
a new file.

The coder reads the selected files alone. The frozen scientific model is
read-only. After the tool rejects a read path, you can still create new files.

The coder and the reviewer receive `contracts/scenario.md` and fixed parts of
the authority and instrument contracts. Your conversation stays with you. Give
the relevant requirements in `intent` and `source_context`. The coder reports
missing or unclear requirements in its summary and in its unchecked scope.

### Review

After the first delivery of the coder, an independent reviewer with high
reasoning starts. It receives the original request, the task context, the
changed files and the diff. The review checks coding defects. It also checks
the equations, the units, the physical assumptions, the timing and the meaning
of the measurements in the changed code. It checks if the protocol and the
reported quantities can answer your stated question. An untested scientific
hypothesis passes the review.

The reviewer returns exactly four fields:

```json
{
  "validation": {"type": "boolean"},
  "what_is_wrong": {"type": "string"},
  "why": {"type": "string"},
  "where": {"type": "string"}
}
```

The three explanation fields contain plain text. `validation` is false for
defects that the coder can repair within the request, and for these alone. All
three fields then explain the defect. A failed review goes unchanged to the
same coder, and the same reviewer checks the repair. A correction review checks
the reported problems and the errors that the repair added.

The repair loop runs inside the tool. When a repair leaves the source code
unchanged and the next review fails again, the tool returns `needs_pi` with the
reason and the current changes. When `validation` is true, the explanation
fields can contain concerns, confounds or scientific choices for you.

### Coding result

The result contains:

- the session handle
- the list of changed files and the diff for the call, with the repairs
- the summary of the coder and its unchecked scope
- `review`: the report with four fields, its `mode` (`initial` or
  `correction`), the status, the reviewer handle, the models, the reasoning and
  the usage
- `repair_history`: each review that the tool sent, the status and summary of
  the coder, and the next review

When the review output is large, the tool stores it in a file and returns the
path. Errors and timeouts return the partial changes when they are available.
The result states when a review was unavailable or failed.

The review checks the engineering: the code, the equations, the units and the
measurement meaning. You judge the scientific validity. Inspect the actual
changes and the reported limitations before you rely on them. The Runner alone
executes code: measurements and analyses are separate operations.
