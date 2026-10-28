# Scientific instruments: readers

This file is a part of the instrument contract. `contracts/instruments.md` lists
all parts.

## Source readers

`view` reads one exact permitted file. `glob` lists files by pattern. `rg`
searches content. It returns matching lines, matching files or counts, with
selectors for the pattern, the glob, the type, the context and the result
limit.

Both search tools accept the default path, a subfolder or several
`paths`. Searches skip the reserved files in a readable folder and reject a
reserved search root. Linked paths and paths outside the repository are not
available.

The results report output limits and search limits. A truncated result does not
establish that the matches that it did not return are absent. To read content after
the limit of a search preview, read the exact file.

## Installed scientific API reference

`scientific_api_reference` reads definitions from the installed `mujoco`,
`gymnasium` and `stable_baselines3` libraries. It loads only the roots of these
fixed libraries. It does not call scientific functions or constructors. It does not
run supplied code, read other paths or show private attributes.

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
public dotted name, relative to this library. When you do not give a symbol,
the tool selects the root of the library. A name that the library imports from
another library is not a definition target.

`action=members` returns the public member names and their kinds. `contains`
filters the names by a case-insensitive substring. `offset` and `limit` select
member rows. The result gives the number of matches and `next_offset`.

`action=definition` returns the installed signature, the documentation, the
available Python source and the native MuJoCo declaration. `offset` and
`max_bytes` select UTF-8 bytes of the definition. The result gives the
version, the content fingerprint, the complete byte count and `next_offset`.

The result states when a signature or a source is not available. A missing
symbol returns `symbol_not_found`, not a guessed replacement. A rejected lookup
returns a failed tool result with the library, the symbol and the reason. An
available definition does not establish execution compatibility.

The PI, the coder and the reviewer can use this reader. It does not add files
to their scopes and it does not permit execution.

## JSON evidence interface

`artifact_evidence_query` reads JSON evidence. It finds a recorded artifact of
a completed measurement operation in the active campaign and verifies its
recorded fingerprint. You give the operation identity, not an arbitrary file
path.

The interface has these actions:

- `discover`: show the structure under an optional prefix
- `query`: select one path, with optional filters, projection or aggregation
- `batch`: apply related query specifications to the same verified artifact
- `read`: read the complete content of the artifact, page by page
- `operations`: query short operation metadata without opening artifacts
- `metadata`: query the record, the artifact references, the session records
  or the accepted pending request of one operation

`operations` does not take `operation_id`. Its default path selects operation
rows. `metadata` requires `operation_id`. Its paths are `/operation`,
`/record`, `/artifacts`, `/checkpoints` and `/pending`. Its default path
selects the operation summary.

The operation index includes an accepted pending operation. Its status is
`pending` or `failed_pending`. It is not completed evidence. For this
operation, `/pending/request` returns the exact accepted request with its
wrapper. `/pending/measurements` returns the resolved invocations and the
declared outputs. `/pending` also includes the progress, the failure, the
request fingerprint and the number of completed measurements.

These fields stay available after an execution failure or after a new session
starts. They do not permit you to read the artifact contents of incomplete
measurements.

`operations` and `metadata` support the query filters, the selection, the
aggregates and the pages. They report `artifact_contents_inspected` as false.
Recorded metadata is not an inspection of the contents of a measurement.

You select the scope of the request. You can read a complete artifact. You can
also read selected fields, summaries or different subsets in different
requests. The tool selects the query output before it enters the conversation.
The tool does not execute Python query expressions and does not interpret the
science.

The output of `discover` and `query` reports truncation and exhausted limits
explicitly. Pages of `read` and `query` give their offsets and the
continuation. The content identity must stay the same through a continuation.
A mismatched identity is an error, not a page of a different artifact. Partial
output is not complete evidence. It does not establish that the fields or
records that it did not return are absent.

For `query` and for each `batch` specification, `offset` counts the selected
records after the filter and the projection, or the distinct values for
`value_counts`. `limit` sets the page size. The returned `next_offset` reads
the rest of the selection. When one object is too large for a query page,
`read` can still return it.

Before it selects evidence, the tool validates the complete JSON syntax of the
artifact. The query output and the decoded values have explicit limits. The
tool reports an exhausted limit. It does not truncate without a report.

A filter is a typed object with the required fields `path` and `equals`.
`path` is relative to each selected row. `equals` can be null. When you select
an array for a filter, a projection or an aggregation, the tool expands it into
rows and reports this expansion. An explicit wildcard also selects rows.

A missing filter field gives `filter_field_absent`, not a valid result with
zero matches. For missing selected fields, the tool gives a bounded list of
direct field names. This list is not a complete inventory.

Normal query pages have small default limits for rows and bytes. `limit` sets
the number of rows on a page. Set `max_bytes` on the request, not in `queries`.
All batch items share this byte limit for the selected values.

The tool rejects fields that it does not support. It does not silently ignore
them. Do not give `select` when you want complete rows. A supplied pointer
cannot be empty.

Larger explicit pages and complete reads of the original file stay available.

For `read`, `offset` and `max_bytes` refer to bytes of the original file.
`encoding` selects readable UTF-8, or base64 for other byte encodings. UTF-8
pages keep the line endings and do not split a character.

The returned `next_offset` and the verified fingerprint identify the
continuation. `expected_fingerprint` is required for a read offset that is not
zero. When you
join the pages in offset order, you get the complete original content. A full
read does not need to parse the complete artifact within the query limits.

## Training-log interface

`training_log_query` reads the kept training logs. It finds them from the
active campaign and the identity of the training operation, not from a file
path or a command.

`discover` returns the attempt identities, the covered timesteps and the
available metric names, without metric values. When you do not give `action`,
the tool uses this metadata mode. A `records` request selects attempts,
timestep bounds and metric fields. A `raw` request returns the kept log text,
which includes the content outside the parsed training records.

You can read complete logs and successive pages. You may request different
subsets in separate calls without a new training run. The tool reports missing
logs, empty selections, the available continuation and the content identities
explicitly.

`attempts` selects the kept attempt numbers. `records` uses the optional
`from_step` and `to_step`, with `offset` and `limit` for pages of selected rows.
An offset that is not zero requires `expected_log_fingerprints` from the
previous response. The tool reports missing metrics separately from the value
zero. The status of the operation does not establish the outcome of each
attempt.

A records request requires explicit `metrics` or `all_metrics: true`, but not
both. The default pages of rows and bytes are small. `max_bytes` bounds the
selected record values and the raw pages. You can explicitly increase it and
continue.

When there are several logs, `raw` selects one attempt. Its `offset`,
`max_bytes`, `encoding` and `expected_fingerprint` follow the same continuation
semantics for original bytes as the JSON `read` action. A raw read includes the lines that
the metric parser does not recognize. It does not need to parse the complete
log.

Kept failure logs describe execution history, not scientific evidence. Parsed
metrics and raw logs do not certify development performance or choose a
candidate. You interpret the returned data.

## Numeric summary tools

`training_series_statistics` computes a summary of one metric in one kept
training log. It uses the same operation identity, attempt selection and log
fingerprint as `training_log_query`. You give:

- `operation_id` and the exact `metric` name
- `attempt`, required when the operation has more than one log
- optional inclusive `from_step` and `to_step` bounds
- optional `checks`, at most 20

The result gives these values:

- the number of rows
- the first and the last values, with their steps
- the minimum and the maximum, with their first step and the number of rows at
  that value
- the mean and the sample standard deviation

The tool excludes and counts the rows without a finite value. A missing metric
returns the available metric names.

Each check names a statistic (`min`, `max`, `mean`, `first` or `last`), a
comparison (`>=` or `<=`) and a threshold that you choose. The result gives the
computed value and whether the comparison is true. A `min` or `max` check also
gives the number of rows that do not meet the comparison. It also gives the
first and the last step of these rows. Checks are optional.

`success_rate_pass_probability` relates measured success counts to a
success-rate target. You give:

- `target`: the `trials` of the panel that decides the goal, and the
  `successes` that it requires
- `evidence`: up to 20 entries. Each entry has a `label` and one of these:
  - `recorded`: a list of completed `research_evaluation` or `task_reference`
    measurements to pool. Give each as `operation_id`, `candidate`
    (identity or role), an optional `instrument` and an optional measurement
    `label`. Use them when the operation measured the candidate more than one
    time. The Runner reads the successes and the episodes from the
    records.
  - typed `successes` and `trials`
- `confidence`: the level of the two-sided interval, from 0.5 to 0.999

You decide which measurements an entry pools. When a recorded reference
matches no single measurement, the tool rejects it and lists the measurements
of candidates that this operation recorded. A recorded entry also lists its
sources and the number of episodes that they share. Shared episodes are not
independent samples. For each source, it also gives the number of candidates
that the campaign measured on exactly the same episodes, and their successes.

For each entry, the result gives the proportion, its Wilson interval, and
whether the interval is `above`, `below` or `includes` the target rate. It also
gives the probability that a new target panel reaches the required successes.
This probability uses a uniform prior and the beta-binomial predictive
distribution. The result also gives the pass probability when the true rate
equals the lower or the upper bound of the interval. It gives the true success
rate at which the target panel passes with the probability 0.5, 0.8 and 0.95.

The tool does not verify typed counts. It assumes independent episodes with one
common success probability, representative of the target panel. The counts of a
candidate that you selected as the best of several on the same episodes are
optimistic. The optimism increases with the number of candidates that you
compared on these episodes.

`episode_outcome_breakdown` reads the episode results of recorded
`research_evaluation` or `task_reference` measurements. You give:

- `measurements`: one or two references, each as `operation_id`, `candidate`
  (identity or role), an optional `instrument` and an optional measurement
  `label`
- optional `strata`, with three fields:
  - `rows`: a JSON Pointer to the per-episode rows that contain `episode_seed`
    (default `/episode_results`)
  - `field`: the numeric field of these rows
  - `edges`: from 2 to 21 increasing edges. The last bin includes its upper
    edge.
- `confidence`: the level of the two-sided interval, from 0.5 to 0.999

The Runner verifies the fingerprint of each artifact. It checks its episode
results against the recorded episode and success counts. For each measurement,
the result gives the successes, the trials and a Wilson interval.

Two measurements must cover the same episode seeds, with the same instrument
and the same evaluation semantics or task-reference panel. Their result adds
the paired counts: both succeed, only the first, only the second, neither. It adds the
exact two-sided sign test over the episodes in which exactly one succeeds. It
also adds the Wilson interval of the share of these episodes that the first
measurement has.

Strata repeat these results for each bin. They use the field values of the
first measurement. They count the episodes outside the edges or without a
value. Rows of a research evaluation that contain fields such as the target
radius can be in another section of the artifact. `artifact_evidence_query`
with `action=discover` shows them. Edges that you choose after you see the
episode outcomes make the differences between strata optimistic.

These tools compute numbers from the supplied data. They do not judge claims,
decide significance, certify development performance or choose a candidate. You
interpret the results.
