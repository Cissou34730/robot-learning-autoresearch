# Researcher instruments

This scenario-neutral catalog is authoritative for the instruments,
Runner-mediated operations and session capabilities available to the
Researcher. It describes contracts and limits without ranking evidence or
prescribing a scientific strategy.

Phase names are **experiment preparation**, **research evaluation** and
**experiment closure**. Read-only capabilities are available in every
Researcher session unless an entry says otherwise. Runner-mediated operations
are requested by the Researcher and executed only by the Runner.

## Repository inspection

**Purpose:** Read and search repository files, configuration, history, briefs,
source code and measurement artifacts.

**Phases:** Every Researcher session.

**Invocation:** Use the session's file viewing, search and glob tools.

**Inputs:** Repository-relative paths or search expressions.

**Output:** Tool results returned to the session. Inspection does not persist a
new research artifact.

**Ownership:** All repository paths are readable. Mutability is defined in
`AGENTS.md`.

**Limits:** Large results may be offloaded by the session runtime and read from
the returned path. Reading a protected file does not make it mutable.

## Git inspection

**Purpose:** Inspect worktree state, diffs and repository history.

**Phases:** Every Researcher session.

**Invocation:** Run read-only `git status`, `git diff`, `git log`, `git show`,
`git rev-parse`, `git ls-files`, `git ls-tree`, `git cat-file`, `git describe`,
`git blame` or `git shortlog` through the shell.

**Inputs:** Arguments accepted by the named read-only Git command.

**Output:** Command output returned to the session.

**Ownership:** The Runner owns Git mutations and scientific lineage changes.

**Limits:** Mutating and unknown Git subcommands are denied. Code reversion is a
lineage request described below.

## Current research brief

**Purpose:** Inspect the current campaign state and the models available to the
current phase.

**Phases:** Every Researcher session; content depends on campaign state.

**Invocation:** Read `research/brief.md`.

**Inputs:** None. The Runner regenerates the brief before the session.

**Output:** Current parameters, campaign history, prior interpretations,
available candidate names and artifact paths, completed measurement references,
retained lineages, and phase-specific state.

**Ownership:** Runner-generated and read-only to the Researcher.

**Limits:** The brief is a compact view. `research/results.jsonl` and referenced
artifacts retain the durable detail.

## Checkpoint-aligned training facts

**Purpose:** Inspect factual training metrics aligned with each saved candidate
checkpoint.

**Phases:** Research evaluation and experiment closure when candidates are
available in `research/brief.md`.

**Invocation:** Read the candidate entries in `research/brief.md`.

**Inputs:** None.

**Output:** Candidate name, checkpoint timestep, checkpoint-aligned training
success, checkpoint-aligned mean episode reward and artifact path.

**Ownership:** Supplied automatically by the Runner from the candidate manifest;
read-only to the Researcher.

**Limits:** These are recorded training facts at the saved checkpoint. They are
not research-evaluation results or an objective verdict.

## Raw training records

**Purpose:** Inspect preserved training metrics over an inclusive timestep range
for one experiment, including separate execution attempts.

**Phases:** Every Researcher session after the requested experiment has training
records.

**Invocation:**

```bash
uv run python research/query_training_log.py --experiment <positive-integer> --from-step <nonnegative-integer> --to-step <integer-at-least-from-step>
```

**Inputs:** All three arguments are required. Timestep bounds are inclusive; an
equal lower and upper bound requests one exact timestep.

**Output:** A Markdown table returned to the shell with attempt number,
timestep and every recorded metric. Distinct training attempts remain distinct.

**Ownership:** Raw logs and the query command are Runner-owned and read-only.

**Limits:** The command performs no aggregation or interpretation. It exits with
an error when the experiment has no preserved log.

## Lightweight analysis and diagnostics

**Purpose:** Compute or inspect evidence without invoking a Runner-owned
operation.

**Phases:** Every Researcher session.

**Invocation:** Run a script, module or inline command through `uv run` using the
fixed project environment.

**Inputs:** Researcher-selected code and repository evidence.

**Output:** Command output returned to the session; files are persisted only
when the code explicitly writes them into a researcher-owned path.

**Ownership:** Analysis code must be created in a researcher-owned code prefix
listed by `AGENTS.md` and becomes part of the experiment's code lineage.

**Limits:** Training, the generic evaluator, the viewer, the Runner and final
benchmark cannot be invoked. Package installation, dependency synchronization
and dependency metadata changes are unavailable. The shell policy is a
guardrail rather than a security sandbox.

## Scientific development

**Purpose:** Change the learning method, reward, observations, training
environment, research evaluation, scientific instrumentation and associated
tests.

**Phases:** Experiment preparation; research evaluation only when refining
research-evaluation instrumentation for another round.

**Invocation:** Edit files within the researcher-owned surface in `AGENTS.md`.

**Inputs:** Source, test or configuration changes supported by the scientific
reason recorded in the phase deliverable.

**Output:** Worktree changes recorded with the experiment's `code_changes` and
Git lineage.

**Ownership:** Researcher-owned. `research/current_params.json` holds runtime
overrides; scenario science remains code.

**Limits:** Human-owned paths and dependency metadata are rejected. The method
may change only within the installed dependency set. Changes to measurement
semantics can change measurement identity.

## Runtime parameter editing

**Purpose:** Override values in the currently active runtime configuration.

**Phases:** Experiment preparation.

**Invocation:** Edit `research/current_params.json` directly or supply a
`params` object in `research/proposal.json`.

**Inputs:** JSON values accepted by the active configuration validator. The
available structure is the current file and resolved training configuration,
not a catalog of scientific choices.

**Output:** Validated overrides are persisted as the active configuration and
recorded as parameter changes in experiment history.

**Ownership:** Researcher-owned; interpretation and persistence are performed by
the training configuration and Runner.

**Limits:** Parameter-only proposals do not create code changes. Dependency
metadata and values outside the active configuration contract are unavailable.

## Focused source checks

**Purpose:** Run syntax or lint diagnostics on selected researcher-owned files.

**Phases:** Every phase in which researcher-owned code may be inspected or
changed.

**Invocation:**

```bash
uv run ruff check <specific-paths>
```

**Inputs:** One or more explicit researcher-owned paths and supported Ruff
arguments.

**Output:** Diagnostics returned to the session.

**Ownership:** The Researcher chooses the focused check; the Runner owns final
validation.

**Limits:** Do not run repository-wide lint or formatting. A focused check does
not replace Runner validation.

## Targeted tests

**Purpose:** Execute a focused check of researcher-owned behavior.

**Phases:** Every phase in which researcher-owned code may be inspected or
changed.

**Invocation:**

```bash
uv run pytest <specific-test-path-or-suite>
```

**Inputs:** At least one explicit test path or suite.

**Output:** Test output returned to the session.

**Ownership:** Tests under `tests/scenario/` and `tests/training/` are
Researcher-owned; the Runner owns complete validation.

**Limits:** An argument-less repository-wide pytest run is denied. Running a
targeted check does not replace Runner validation.

## Research evaluation request

**Purpose:** Request researcher-owned measurements of available models.

**Phases:** Research evaluation.

**Invocation:** Write `research/evaluation_request.json` with the common fields
and at least one entry across `evaluations` and
`task_reference_evaluations`.

| Field | Type | Requirement |
| --- | --- | --- |
| `experiment` | integer | Required; identifies the current experiment. |
| `question` | non-empty string | Required; states the scientific question. |
| `reason` | non-empty string | Required; states why the requested evidence addresses the question. |
| `evaluations` | array of research-evaluation entries | Optional. |
| `task_reference_evaluations` | array of task-reference entries | Optional. |
| `paired_comparisons` | array of paired-comparison entries | Optional. |
| `need_more_evidence` | boolean | Optional; selects another measurement round or experiment closure after this round. |

A research-evaluation entry has these fields:

| Field | Type | Requirement |
| --- | --- | --- |
| `candidate` | string | Required; a model name exposed by the brief. |
| `episodes` | positive integer | Required. |
| `seed` | integer | Required. |
| `label` | string | Optional presentation label. |

**Output:** The Runner writes one durable JSON artifact per distinct
candidate/episode-count/seed/measurement-semantics identity under
`research/evaluations/` and references it from the brief and history.

**Ownership:** Request and research-evaluation semantics are Researcher-owned;
execution and durable persistence are Runner-owned.

**Limits:** The request cannot invoke the official benchmark. Candidate names
must come from the current brief. Repeating an existing measurement identity
reuses its durable artifact.

## Task-reference evaluation request

**Purpose:** Request the human-owned task-reference panel for an available
model.

**Phases:** Research evaluation.

**Invocation:** Add an entry to `task_reference_evaluations` in
`research/evaluation_request.json`.

| Field | Type | Requirement |
| --- | --- | --- |
| `candidate` | string | Required; a model name exposed by the brief. |
| `label` | string | Optional presentation label. |

**Output:** The Runner writes a durable task-reference JSON artifact under
`research/evaluations/` and references it from the brief and history.

**Ownership:** The Researcher chooses the model. The Human owns the panel and
the Runner executes it.

**Limits:** No other entry fields are accepted. Panel inputs and semantics are
fixed by the current scenario and cannot be set by the request. The result is
development evidence, not the objective verdict.

## Paired comparison request

**Purpose:** Compare two ordinary research evaluations whose episode evidence
supports the repository's paired-comparison computation.

**Phases:** Research evaluation.

**Invocation:** Add an entry to `paired_comparisons` in
`research/evaluation_request.json`.

| Field | Type | Requirement |
| --- | --- | --- |
| `candidate` | string | Required; names a candidate represented in `evaluations`. |
| `reference` | string | Required; names another candidate represented in `evaluations`. |

**Output:** The comparison is recorded in the experiment result with candidate
wins, reference wins, success difference and exact paired-test value.

**Ownership:** The Researcher requests the comparison; the Runner computes and
persists it.

**Limits:** Both sides require compatible ordinary research-evaluation episode
records. Task-reference results are not paired-comparison inputs.

## Additional measurement round

**Purpose:** Preserve completed measurements and return to research-evaluation
design within the same experiment.

**Phases:** Research evaluation.

**Invocation:** Set the boolean `need_more_evidence` field in
`research/evaluation_request.json` to the value selecting another round.

**Inputs:** A valid evaluation request and a boolean field value.

**Output:** Completed artifacts remain durable; the Runner regenerates the brief
and opens another research-evaluation session for the same experiment.

**Ownership:** The Researcher makes the scientific request; the Runner controls
the phase transition.

**Limits:** This does not create a phase between experiments and does not start
new training.

## Training experiment request

**Purpose:** Request training for a scientific intervention.

**Phases:** Experiment preparation.

**Invocation:** Write `research/proposal.json` with these fields:

| Field | Type | Requirement |
| --- | --- | --- |
| `kind` | `training`, `continuation` or `replication` | Required. |
| `family` | non-empty string | Required; stable identifier for one hypothesis family. |
| `hypothesis` | non-empty string | Required; falsifiable mechanism under test. |
| `change` | non-empty string | Required; intervention being tested. |
| `initialization` | `fresh` or `transfer` | Required. |
| `training_parent` | string | Required only for `transfer`; unavailable for `fresh`. |
| `training_seed` | integer | Optional except where required by the selected kind. |
| `replication_of` | positive integer | Required only for `replication`. |
| `params` | object | Optional overrides to the active runtime configuration. |

**Output:** After validation, the Runner executes training and persists candidate
artifacts, checkpoint-aligned facts and experiment history.

**Ownership:** Scientific changes and request are Researcher-owned; validation,
training and persistence are Runner-owned.

**Limits:** A `training` request must contain a code change or `params`. A
`transfer` request requires an eligible parent exposed by the brief. Dependency
changes and protected-path changes are rejected.

## Continuation request

**Purpose:** Train an unchanged method further from an eligible lineage.

**Phases:** Experiment preparation.

**Invocation:** Use the training proposal fields with `kind` set to
`continuation`, `initialization` set to `transfer`, and `training_parent` naming
an eligible lineage from the brief.

**Inputs:** The common training proposal fields and an eligible parent.

**Output:** The Runner produces candidates under a new experiment identity and
preserves accumulated lineage training steps.

**Ownership:** The Researcher requests scientific continuation; the Runner
executes it.

**Limits:** Continuation does not change the method. It is distinct from
Runner-controlled recovery, which resumes or restarts an interrupted execution
without creating a scientific continuation request.

## Replication request

**Purpose:** Rerun a completed experiment under the repository's current
replication contract.

**Phases:** Experiment preparation.

**Invocation:** Use the training proposal fields with `kind` set to
`replication`, `initialization` set to `fresh`, `replication_of` naming the exact
experiment and an explicit `training_seed`.

**Inputs:** Common training proposal fields, a positive experiment number and an
explicit integer seed.

**Output:** The Runner executes a fresh run and groups the result with the named
experiment in durable history.

**Ownership:** The Researcher requests replication; the Runner validates and
executes it.

**Limits:** The replicated method and configuration are unchanged. Replication
cannot include other code or parameter changes.

## Postmortem record

**Purpose:** Preserve the Researcher's experiment conclusion and its evidence.

**Phases:** Experiment closure.

**Invocation:** Append `## Experiment <integer>` to
`research/postmortems.md` with non-empty `**Result:**`,
`**Observed behavior:**`, `**Interpretation:**` and
`**Evidence inspected:**` entries.

**Inputs:** Existing detailed evaluation artifact paths from the current
experiment.

**Output:** A durable Markdown record committed before lineage application and
included in later briefs.

**Ownership:** Researcher-authored; the Runner validates, commits and presents
it.

**Limits:** At least one named artifact must exist and belong to the current
experiment. Interpretation remains contestable evidence.

## Lineage decision request

**Purpose:** Close an experiment, select the active model and resolve scientific
code and retained lineages.

**Phases:** Experiment closure after the postmortem is complete.

**Invocation:** Write `research/proposal.json` containing only
`previous_result_decision` with these fields:

| Field | Type | Requirement |
| --- | --- | --- |
| `experiment` | integer | Required; current experiment. |
| `continue_from` | string | Required; available candidate or current active lineage exposed by the brief. |
| `reason` | non-empty string | Required. |
| `code` | object | Required; contains only `action` and `reason`. |
| `retain` | array of retention entries | Optional. |
| `remove_retained` | array of retained-lineage identifiers | Optional. |
| `request_final_benchmark` | boolean | Optional. |

The `code` object accepts `action` as `keep` or `revert` and requires a non-empty
`reason`. A retention entry contains only `candidate`, `id` and `reason`; each is
a non-empty string and `id` must be a unique file-name-safe identifier.

**Output:** The Runner promotes the selected artifact, applies the code action,
updates retained lineages, removes unretained heavyweight candidates and
persists the decision. Development measurements remain durable.

**Ownership:** The Researcher makes the lineage decision; the Runner validates
and applies it, including Git mutations.

**Limits:** The selected model and retained candidates must be exposed by the
brief. The active model cannot also be retained. Removal identifiers must name
existing retained lineages.

## Final benchmark request

**Purpose:** Request the sole human-owned objective verdict for the selected
lineage.

**Phases:** Experiment closure as part of the lineage decision.

**Invocation:** Set the boolean `request_final_benchmark` field in
`previous_result_decision` to the value selecting a final benchmark.

**Inputs:** A valid lineage decision and boolean field value.

**Output:** After lineage application, the Runner executes the protected panel,
persists its artifact and either records the objective as reached or returns the
campaign to research.

**Ownership:** The Researcher requests the operation; the Human owns its
semantics and the Runner executes it.

**Limits:** It cannot be invoked during research evaluation or used to select a
lineage. The same accepted artifact cannot receive the same official benchmark
again.