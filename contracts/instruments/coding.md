# Scientific instruments: coding

Part of the instrument contract indexed in `contracts/instruments.md`.

## Saved controller execution

Saved candidates include policy weights, normalization state when used, and the
executable runtime defined in `contracts/policy_runtime.py`.

Task-reference and official evaluations use protected environments, not the
PI-owned research environment. The protected environment calls the saved
`io.observe(data)` to construct each policy observation. The saved runtime
performs policy inference with its normalization state. The environment calls
`io.action(policy_action)`, then validates and clips the result before applying
it to the robot. It calls the optional `io.reset()` callback at each episode reset.

Controller logic affects protected evaluation only if the saved runtime executes
it. A runtime marker alone does not cause the protected environment to call
research-environment code. Research evaluation uses the PI-owned environment,
which can apply additional control logic outside the saved runtime. Identical
artifact fingerprints do not establish identical applied commands across these
environments.

## Scientific coding interface

`scientific_coding` delegates a bounded change to PI-owned source: a new
method, a measurement or analysis tool, or a repair. The coder and the
reviewer roles are defined in `contracts/authority.md`.

The PI session deadline is 30 minutes of active session time by default.
Coding and review count toward it. Waiting for Runner execution does not.

`scientific_coding` accepts:

- `intent`: the precise expected output of the bounded change;
- `allowed_paths`: exact repository-relative writable scientific files;
- `read_paths`: optional additional relevant scientific sources, contracts or
  the frozen `pi_workspace/scientific_model.md`;
- `source_context`: optional PI-selected requirements, caller context and errors;
- `session_handle`: optional returned native child identity for same-change
  corrections within this bounded context;
- `evidence_inputs`: optional, new calls only; up to 10 recorded inputs that the
  changed code will read. A measurement artifact is given as `operation_id` and
  `artifact_index`; the coder and the reviewer receive its recorded structure
  inventory: JSON paths and field names, without values. A model candidate is
  given as `candidate` (ID or role); they receive its archive path, file names
  and `artifact.json` metadata.

New calls require `intent` and `allowed_paths`. A correction supplies
`session_handle` and `intent`, with optional `source_context`. Omitted scope
fields reuse the stored binding; resubmitted scope fields must match it, and a
changed field is rejected with its name. A new scope requires a new call
without a handle. A handle is valid only within the current session.

Writes are limited to PI-owned files. Protected paths, directories, wildcard
scopes, operation requests and paths outside the repository are refused; the
rejection names the path and the reason. A new writable file does not require
an existing parent directory. Reads are limited to the selected files; the
frozen scientific model is read-only. A rejected read binding does not mean
that new-file creation is unavailable.

The coder and the reviewer receive the scenario and fixed excerpts of the
authority and instrument contracts. They do not receive the PI conversation:
state the relevant requirements in `intent` and `source_context`. The coder
reports missing or unclear requirements in its summary and unchecked scope.

### Review

After the coder's first handoff, an independent reviewer with high reasoning
receives the original request, the task context, the changed files and the
diff. The review checks coding defects and the equations, units, physical
assumptions, timing and measurement meaning of the changed code. It checks
whether the protocol and the reported quantities can answer the PI's stated
question. An untested scientific hypothesis is not a defect.

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
request; all three fields then explain the defect. A failed review goes
unchanged to the same coder, and the same reviewer checks the repair. A
correction review covers only the reported problems and errors introduced by
the repair. This repair loop does not return to the PI. A repair with no source
change followed by another failed review returns `needs_pi` with the reason and
the current changes. When `validation` is true, the explanation fields can
carry concerns, confounds or scientific choices for the PI.

### Coding result

The result contains:

- the session handle;
- the changed-file manifest and diff for the invocation, including repairs;
- the coder summary and unchecked scope;
- `review`: the four-field report, its `mode` (`initial` or `correction`),
  status, reviewer handle, models, reasoning and usage;
- `repair_history`: each forwarded review, the coder status and summary, and
  the follow-up review.

Large review output is stored in a file and returned as a path. Errors and
timeouts return partial changes when available. An unavailable or failed
review is reported as such, not as a completed review.

Review checks engineering and does not certify scientific validity. Inspect
the actual changes and the reported limitations before relying on them. The
coder executes nothing; measurements and analyses are separate operations.
