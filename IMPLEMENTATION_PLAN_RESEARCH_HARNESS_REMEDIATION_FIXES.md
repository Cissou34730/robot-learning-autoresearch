# Research Harness Remediation — Focused Corrections

## Intent

Correct the remaining gaps in `codex/research-harness-remediation` without
redesigning the harness.

The existing implementation is authoritative and mostly correct. This work is
limited to:

1. making primary-success comparability consistent with researcher-owned
   instrumentation;
2. using that same comparability rule when replacing `best_known`;
3. removing avoidable duplication and ambiguity introduced by the remediation;
4. recording the protocol decision.

Do not add a framework, state, phase, request type, registry, dependency graph,
or generic instrumentation API.

## Working rules

- Continue on the existing branch `codex/research-harness-remediation`.
- Do not create another branch or worktree.
- Do not alter or replay campaign state.
- Do not run training, evaluation, reset, Git workflow tests, or a campaign.
- Do not run the full test suite or the complete `tests/autoresearch` suite.
- Make the two commits specified below and push after each commit.
- Tests must use synthetic records and temporary files only.

## Correction 1 — Make comparison and best-known designation coherent

### Problem A: diagnostic edits still invalidate primary comparison

`comparison_semantics_fingerprint()` currently hashes the complete files:

- `robot_learning/scenario/evaluation.py`;
- `robot_learning/evaluate.py`.

The researcher-owned diagnostic payload is implemented in
`robot_learning/scenario/evaluation.py`. Therefore an edit that only adds or
changes diagnostics still changes `comparison_semantics`, contrary to the
intended contract.

The current test does not detect this. It edits a synthetic
`robot_learning/scenario/instrumentation.py`, while the real instrumentation is
inside `evaluation.py`.

### Required implementation for Problem A

Keep the existing broad `evaluation_semantics_fingerprint()` unchanged.

For `comparison_semantics_fingerprint()`:

1. continue hashing the concrete runtime/environment sources that affect replay
   and primary task success;
2. stop hashing all of `robot_learning/evaluate.py`, because it is a CLI and
   progress-output wrapper;
3. stop hashing all of `robot_learning/scenario/evaluation.py`, because that also
   contains researcher-owned diagnostics;
4. add this researcher-owned integer constant to
   `robot_learning/scenario/evaluation.py`:

   ```python
   PRIMARY_COMPARISON_SEMANTICS_VERSION = 1
   ```

5. include the value of this constant in the comparison fingerprint;
6. keep hashing `robot_learning/policy_runtime.py` and
   `robot_learning/scenario/environment.py`;
7. document next to the constant that it is incremented only when episode
   execution or the meaning/extraction of primary success changes, not when
   `research_evidence`, labels, summaries, progress output, or other diagnostics
   change.

Read the constant without importing the MuJoCo/Gymnasium scenario module. Use a
small strict regular-expression extraction from the source file, matching the
existing integer assignment. Raise a clear error if the constant is absent,
duplicated, or invalid. Do not add another module or metadata file for one
integer.

This is deliberately a small explicit version marker. Do not build AST-based
semantic hashing or automatic dependency discovery.

### Problem B: `best_known` still uses the old broad equality rule

Paired primary-success comparison uses `comparison_semantics`, but replacement
of `best_known` still intersects the old complete `settings` tuples. A reward-only
candidate can therefore pass a paired comparison and then fail designation
because its broad `evaluation_semantics` differs from the incumbent.

This can also make task-reference measurement effectively mandatory even though
the protocol correctly defines it as optional.

### Required implementation for Problem B

In `research/runner_protocol.py`:

1. keep candidate evidence resolution and incumbent evidence auto-resolution as
   currently implemented;
2. replace the raw `selected_settings & incumbent_settings` test with one shared
   compatibility rule;
3. for two `research_evaluation` records, use the existing primary-comparison
   compatibility logic:
   - instrument, episode count, seed, and exact episode identities remain
     compatible requirements;
   - when both records contain `comparison_semantics`, require those values to
     match;
   - for records missing that field, require equal broad
     `evaluation_semantics`;
4. for two `task_reference` records, retain exact panel/version/episode/seed
   compatibility;
5. never treat different instruments as compatible;
6. preserve all model fingerprint, artifact fingerprint, file existence, and
   immutable-evidence validation;
7. do not make a promotion decision for the Researcher.

Use one small helper shared by paired-comparison planning and best-known evidence
validation. Do not introduce a comparison service or class hierarchy.

### Documentation

Update `research/instruments.md` only where required to make the following true:

- the same primary-success compatibility rule applies to a requested paired
  comparison and to comparable evidence supporting a `best_known` replacement;
- detailed diagnostic identity remains governed by broad
  `evaluation_semantics`;
- task-reference remains optional.

Do not add implementation path lists to the Researcher documentation.

### Focused validation

Modify only focused tests in:

- `tests/autoresearch/test_research_protocol.py`;
- `tests/autoresearch/test_lineage_roles.py`.

Required cases:

1. changing only reward or researcher diagnostics preserves
   `comparison_semantics`;
2. changing `PRIMARY_COMPARISON_SEMANTICS_VERSION` changes it;
3. changing environment execution semantics changes it;
4. the test changes the actual diagnostic owner
   `robot_learning/scenario/evaluation.py`, not a fictional instrumentation file;
5. a reward-only candidate with matching `comparison_semantics` can replace
   `best_known` from research-evaluation evidence;
6. incompatible primary semantics still reject replacement;
7. records without primary-semantics metadata remain conservative;
8. task-reference compatibility remains unchanged;
9. model and artifact mismatches remain rejected.

Run only the exact tests added or modified for these cases and Ruff on touched
Python files.

### Commit

```text
fix: align comparison and best-known evidence semantics
```

Push immediately after this commit.

## Correction 2 — Compact the brief and remove request ambiguity

### Problem C: the authoritative lineage section duplicates existing sections

The generated campaign brief now contains the new authoritative lineage data,
then repeats much of the same information under `Working lineage` and
`Best-known model`. When `working` and `best_known` are the same artifact, their
full recipe is also printed twice in the authoritative section.

The information is useful; the duplication is not.

### Required implementation for Problem C

In `research/build_research_brief.py`:

1. keep `## Current lineages and scientific recipes` near the top;
2. keep the exact valid parent identifiers, artifact identity, origin, cumulative
   steps, scientific commit, effective parameters, evidence paths, current
   parameters, and parameter differences;
3. render each unique lineage artifact/recipe once;
4. when `working` and `best_known` identify the same artifact and scientific
   recipe, show `best_known` as an alias of `working` rather than repeating the
   full block;
5. keep the Researcher's distinct reasons for `working` and `best_known` where
   they differ;
6. in the later `Working lineage` and `Best-known model` sections, remove
   facts already present in the authoritative section; retain only information
   not represented there, or replace the duplicate block with a short reference
   to the authoritative section;
7. keep current experiment checkpoints separate from valid lineage identifiers;
8. do not remove scientific facts merely to hit a line-count target.

Do not add another brief section or another data source.

### Problem D: `reason` wording can imply an unsupported per-measurement field

`evaluation_request.json` has one request-level `reason`. Individual measurement
objects do not accept a `reason` field. The current wording can lead the
Researcher to add an invalid per-measurement field.

### Required implementation for Problem D

In `research/instruments.md` and the matching initial evaluation prompts in
`run_research.ps1`, use this unambiguous contract:

```text
Use the request-level `reason` to explain why every listed measurement is needed
to answer the question and how its possible outcomes could change the
interpretation or lineage decision.
```

Do not add `reason` to measurement entries and do not change the JSON schema.

### Problem E: protocol decisions were not recorded

Append one concise dated entry to `research/PROTOCOL_DECISIONS.md` covering the
completed remediation and these corrections. Record only the durable decisions:

- the brief exposes authoritative lineage and complete scientific-recipe facts;
- incumbent best-known evidence comes from persisted lineage state;
- optional remeasurement is available during current-experiment post-training
  analysis;
- broad evaluation identity is distinct from primary-success comparability;
- retries reuse same-session context;
- evaluation requests are question-led and minimal rather than automatic
  competitions.

Do not reproduce the implementation plan or campaign narrative in the decision
log.

### Focused validation

Modify only focused tests in:

- `tests/autoresearch/test_console_presentation.py`;
- `tests/autoresearch/test_research_protocol.py`.

Required cases:

1. identical `working` and `best_known` recipes are rendered once with both roles
   visible;
2. distinct recipes remain fully distinguishable;
3. exact parent identifiers and checkpoint separation are preserved;
4. the request-level `reason` wording is present;
5. measurement entries still reject an unsupported `reason` field;
6. no new request key or phase is introduced.

Run only the exact tests added or modified for these cases and Ruff on touched
Python files.

### Commit

```text
fix: compact lineage context and clarify evaluation reasons
```

Push immediately after this commit.

## Final acceptance criteria

The corrections are complete when:

- diagnostic-only and reward-only edits do not invalidate primary-success
  comparability;
- real primary outcome or environment execution changes do invalidate it;
- evidence accepted for paired primary comparison is also eligible to support a
  `best_known` replacement under the same compatibility rule;
- task-reference remains optional;
- the brief retains exact recipe provenance without repeating identical lineage
  blocks;
- the evaluation request has one clearly defined request-level `reason`;
- the decisions are recorded once in `research/PROTOCOL_DECISIONS.md`;
- no campaign, training, evaluator, Git workflow, reset, full suite, or full
  autoresearch suite was run;
- no new architecture was introduced.

The final implementation report must provide the two commit hashes, the focused
tests run, and any deviation. If the implementation cannot follow this document
without a wider redesign, stop and report the conflict instead of improvising.
