# Scientific instruments: coding

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Saved controller execution

A saved candidate contains the policy weights, the normalization state when the
policy uses one, and the executable saved runtime that
`contracts/policy_runtime.py` defines.

The task-reference evaluation and the official assessment use protected
environments, not the PI-owned research environment. The protected environment
calls the saved `io.observe(data)` to build each observation. The saved runtime
computes the network output with its normalization state. The environment calls
`io.action(policy_action)`. Then it validates the result and clips it before it
applies it to the robot. At each episode reset, it calls the optional
`io.reset()` callback.

Control logic has an effect in protected evaluation only when the saved runtime
executes it. A runtime marker alone does not make the protected environment
call code of the research environment. Research evaluation uses the PI-owned
environment, which can apply additional control logic outside the saved
runtime. An identical artifact fingerprint does not establish that the motor
commands applied in these two environments are identical.

Only a training operation makes a candidate. Training and the export of its
training checkpoints use `make_policy_io()` in
`robot_learning/scenario/policy_io.py`. Thus each candidate contains the saved
runtime that this source file defined when the candidate was trained. A runtime change becomes part of a candidate only when two conditions are true:
this source file contains the change, and a training run uses it. The training
run can use `fresh` or `transfer` initialization.

A `python_module` measurement that runs the weights of an existing candidate
with another runtime is a diagnostic. It can justify a training run. It does
not make, change or replace a candidate. Measurement artifacts never become
candidates.

## Scientific coding interface

`scientific_coding` delegates a bounded change of PI-owned source code to the
coder: a new method, a measurement or analysis tool, or a repair.
`contracts/authority.md` defines the roles of the coder and the reviewer.

By default, a PI session ends after 6 hours of active session time. The time
of the coder and the reviewer counts. The time that you wait for the Runner
does not count.

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
  structure inventory: the JSON paths and the field names, without values. Give
  a candidate as `candidate` (identity or role). They then receive its archive
  path, its file names and its `artifact.json` metadata.

A new call requires `intent` and `allowed_paths`. A correction gives
`session_handle` and `intent`, and optionally `source_context`.

When you do not
give a scope field, the coder keeps the stored scope. A scope field that you
give again must be the same as the stored one. The Runner rejects a changed
field and gives its name. For a new scope, make a new call without a handle. A
handle is valid only in the current session.

The coder can write only PI-owned files. The tool refuses protected paths,
folders, wildcards, operation requests and paths outside the repository. The
rejection gives the path and the reason. A new file does not need an existing
parent folder.

The coder can read only the selected files. The frozen scientific model
is read-only. When the tool rejects a read path, you can still create new
files.

The coder and the reviewer receive `contracts/scenario.md` and fixed parts of
the authority and instrument contracts. They do not receive your conversation.
Give the relevant requirements in `intent` and `source_context`. The coder
reports missing or unclear requirements in its summary and in its unchecked
scope.

### Review

After the first delivery of the coder, an independent reviewer with high
reasoning starts. It receives the original request, the task context, the
changed files and the diff. The review checks coding defects. It also checks the equations,
the units, the physical assumptions, the timing and the meaning of the
measurements in the changed code. It checks if the protocol and the reported
quantities can answer your stated question. An untested scientific hypothesis
is not a defect.

The reviewer returns exactly four fields:

```json
{
  "validation": {"type": "boolean"},
  "what_is_wrong": {"type": "string"},
  "why": {"type": "string"},
  "where": {"type": "string"}
}
```

The three explanation fields contain plain text, not nested finding records.
`validation` is false only for defects that the coder can repair within the
request. All three fields then explain the defect. A failed review goes without
change to the same coder, and the same reviewer checks the repair. A correction
review checks only the reported problems and the errors that the repair added.

This repair loop does not come back to you. When a repair changes no source
code and the next review fails again, the tool returns `needs_pi` with the
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
path. Errors and timeouts return the partial changes when they are available. A
review that was not available or that failed is reported as such, not as a
completed review.

The review checks the engineering: the code, the equations, the units and the
measurement meaning. It does not certify scientific validity. Inspect the
actual changes and the reported limitations before you rely on them.
The coder executes nothing. Measurements and analyses are separate operations.
