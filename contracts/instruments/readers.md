# Scientific instruments: readers

Part of the instrument contract indexed in `contracts/instruments.md`.

## Source readers

`view` reads one exact permitted file. `glob` lists files by pattern. `rg`
searches content and returns matching lines, matching files or counts, with
pattern, glob, type, context and result-limit selectors. Both search tools
accept default, subdirectory or multiple `paths`. Searches skip reserved files
below a readable directory, and reject a reserved search root. Linked paths and
paths outside the repository are unavailable.

Results report output or traversal limits. A truncated result does not
establish that unreturned matches are absent. Use an exact-file read for
content beyond search-preview limits.

## Installed scientific API reference

`scientific_api_reference` reads definitions from the installed `mujoco`,
`gymnasium` and `stable_baselines3` libraries. It loads only those fixed library
roots. It does not call scientific functions or constructors, run supplied
code, inspect arbitrary paths or expose private attributes.

```json
{
  "library": {"type": "string"},
  "symbol": {"type": "string"},
  "action": {"type": "string"},
  "contains": {"type": "string"},
  "offset": {"type": "integer"},
  "limit": {"type": "integer"},
  "max_bytes": {"type": "integer"}
}
```

`library` selects one of the three installed libraries. `symbol` selects a
public dotted name relative to that library. An omitted symbol selects the
library root. Names imported from another library are not definition targets.

`action=members` returns public member names and their kinds. `contains`
filters names by a case-insensitive substring. `offset` and `limit` select
member rows. The result reports the matching count and `next_offset`.

`action=definition` returns the installed signature, documentation, available
Python source and native MuJoCo declaration. `offset` and `max_bytes` select
UTF-8 definition bytes. The result reports version, content fingerprint,
complete byte count and `next_offset`. Unavailable signatures and source are
explicit. A missing symbol returns `symbol_not_found`, not a guessed substitute.
Rejected lookups return a failed tool result with the library, symbol and reason.
Definition availability does not establish execution compatibility.

The PI, the coder and the reviewer can use this reader. It does not widen file
scopes or grant execution.

## JSON evidence interface

`artifact_evidence_query` reads JSON evidence. It resolves a
recorded artifact from a completed measurement operation in the active
campaign and verifies its recorded fingerprint. The PI supplies operation
identity, not an arbitrary filesystem path.

The interface supports:

- `discover`: inspect the structure under an optional prefix;
- `query`: select one path, with optional filtering, projection or aggregation;
- `batch`: apply related query specifications to the same verified artifact;
- `read`: retrieve the artifact's complete content through successive pages.
- `operations`: query compact operation metadata without opening artifacts;
- `metadata`: query one operation's record, artifact references, checkpoints,
  or accepted pending request.

`operations` does not take `operation_id`. Its default path selects operation
rows. `metadata` requires `operation_id`. Its paths are `/operation`, `/record`,
`/artifacts`, `/checkpoints`, and `/pending`. Its default path selects the operation summary.
The operation index includes an accepted pending operation.
Its status is `pending` or `failed_pending`, not completed evidence.
For that operation, `/pending/request` returns the exact wrapped accepted request.
`/pending/measurements` returns resolved invocations and declared outputs.
`/pending` also includes progress, failure, request fingerprint and completed-measurement count.
These fields remain available after an execution failure or context replacement.
They do not authorize artifact-content access to incomplete measurements.
Both actions support the query filters, selection, aggregates and pages.
They report `artifact_contents_inspected` as false. Recorded metadata is not
an inspection of measurement contents.

The PI selects the requested scope. A complete artifact is permitted;
selected fields, summaries and repeated requests for different subsets are
also permitted. Query output is selected before it enters the conversation.
The tool does not execute Python query expressions or interpret the science.

Discovery and query output report truncation and exhausted limits explicitly.
Read and query pages identify their offsets and continuation. Content identity
must remain stable across a continuation; a mismatched identity is an error,
not a page from a different artifact. Partial output is not complete evidence
and does not establish that unreturned fields or records are absent.

For `query` and each `batch` specification, `offset` counts selected records
after filtering and projection, or distinct values for `value_counts`.
`limit` controls the page size. The returned `next_offset` retrieves the
remaining selection. Oversized individual objects remain available through
`read` even when they cannot fit in a query page.

The tool validates the complete JSON syntax of an artifact before it selects
evidence. Query output and decoded values have explicit limits; an exhausted
limit is reported, not silently truncated.

Filtering uses a typed object with required `path` and `equals` fields.
`path` is relative to each selected row; `equals` can be null.
An array selected for filtering, projection or aggregation is expanded into
rows, with the expansion reported in the response. An explicit wildcard also
selects rows. A missing filter field is reported as `filter_field_absent`, not
as a valid zero-match result. Missing selected fields include bounded direct-field
hints. These hints are not a complete inventory.

Ordinary query pages default to small row and byte limits. `limit` selects the
row page size. Set `max_bytes` on the request, not inside `queries`.
All batch items share that byte limit for selected values.
Unsupported fields are rejected, not silently ignored.
Omit `select` for complete rows. A supplied pointer cannot be empty.
Artifact-content requests show the operation and artifact index in the console.
Explicit larger pages and complete original reads remain available.

For `read`, `offset` and `max_bytes` refer to original file bytes.
`encoding` selects readable UTF-8 or base64 for other byte encodings.
UTF-8 pages preserve line endings and do not split a character. The returned
`next_offset` and verified fingerprint identify continuation;
`expected_fingerprint` is required for a nonzero read offset. Joining pages
in offset order reconstructs the complete original content. Full retrieval
does not require parsing the entire artifact within the query limits.

## Training-log interface

`training_log_query` reads preserved training logs. It resolves them from the
active campaign and the training operation identity, not from a filesystem
path or command.

`discover` returns attempt identities, timestep coverage and available metric
names without metric record values. Omitting `action` selects this metadata mode.
`records` requests select attempts, timestep bounds and metric fields.
`raw` requests return preserved log text, including content outside parsed
training records. Complete logs and successive pages are supported. The PI
may request different subsets in separate calls without rerunning training.
The tool reports missing logs, empty selections, available continuation and
content identities explicitly.

`attempts` selects preserved attempt numbers. `records` uses optional
`from_step` and `to_step`, with `offset` and `limit` for selected
row pages. Nonzero row offsets require `expected_log_fingerprints` from the
previous response. Missing metrics are identified separately from zero.
The operation's status does not establish each attempt's outcome.
Record requests require either explicit `metrics` or `all_metrics: true`, not
both. Default row and byte pages are small. `max_bytes` bounds selected record
values as well as raw pages; the PI can explicitly increase it and continue.
Console output identifies operation, action and supplied selectors.

`raw` selects one attempt when multiple logs exist. Its `offset`, `max_bytes`,
`encoding` and `expected_fingerprint` use the same original-byte continuation
semantics as JSON `read`. Raw retrieval includes lines the metric parser
does not recognize and does not require parsing the complete log.

Preserved failure logs describe execution history, not scientific evidence.
Neither parsed metrics nor raw-log retrieval certifies development
performance or chooses a candidate. The PI interprets the returned data.

## Numeric summary tools

`training_series_statistics` computes a summary of one metric in one
preserved training log. It uses the same operation identity, attempt selection
and log fingerprint as `training_log_query`. The PI supplies:

- `operation_id` and the exact `metric` name;
- `attempt`, required when the operation has more than one log;
- optional inclusive `from_step` and `to_step` bounds;
- optional `checks`, at most 20.

The result gives the row count, the first and last values with their steps,
the minimum and maximum with their first step and the number of rows at that
value, the mean and the sample standard deviation. Rows without a finite value
are excluded and counted. A missing metric returns the available metric names.

Each check names a statistic (`min`, `max`, `mean`, `first` or `last`), a
comparison (`>=` or `<=`) and a threshold that the PI chooses. The result gives
the computed value and whether the comparison holds. A `min` or `max` check
also gives the number of rows that do not meet the comparison and the first and
last of their steps. Checks are optional.

`success_rate_pass_probability` relates measured success counts to a
success-rate target. The PI supplies:

- `target`, the `trials` of the panel that decides the goal and the
  `successes` it requires;
- `evidence`, up to 20 entries, each with a `label` and either:
  - `recorded`, a list of completed `research_evaluation` or `task_reference`
    measurements to pool, each as `operation_id`, `candidate` (ID or role) and
    an optional measurement `label` when the candidate appears twice; Runner
    reads successes and episodes from the records, or
  - typed `successes` and `trials`;
  the PI decides which measurements an entry pools;
- `confidence`, the two-sided interval level, from 0.5 to 0.999.

A recorded reference that matches no single measurement is rejected with the
candidate measurements that operation recorded. A recorded entry also lists its
sources and the number of episodes they share; shared episodes are not
independent samples.

For each entry the result gives the proportion, its Wilson interval, whether
the interval is `above`, `below` or `includes` the target rate, and the
probability that a new target panel reaches the required successes. That
probability uses a uniform prior and the beta-binomial predictive distribution.
The result also gives the true success rate at which the target panel passes
with probability 0.5, 0.8 and 0.95. Typed counts are not verified. The tool
assumes independent episodes with one common success probability,
representative of the target panel. Counts of a candidate selected as the best
of several are optimistic.

These tools compute numbers from the supplied data. They do not judge claims,
decide significance, certify development performance or choose a candidate.
The PI interprets the results.
