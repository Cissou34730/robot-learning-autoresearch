# Research Harness Remediation Plan

## Purpose

Improve the Researcher's decisions without adding a new framework or changing the
scientific objective. The completed campaign showed three concrete harness
problems:

1. the current lineage, admissible parent identifiers, effective recipe, and
   incumbent evidence are too difficult to reconstruct;
2. mechanism-specific interventions are sometimes proposed before the relevant
   behavior has been measured on saved policies;
3. reward-only changes can make otherwise comparable success measurements appear
   incompatible.

Two smaller changes must then reduce avoidable model cost without hiding the
effect of the three corrections above:

4. a retry in the same Researcher session must not reload all static context;
5. an evaluation request must contain only measurements that can answer its stated
   question or change the lineage decision.

Implement these five areas through the six ordered, reviewable commits below;
priority 1 is deliberately split into two commits. Do not combine them into a new
state machine, data store, service, plugin system, or generic framework.

## Mandatory Git workflow

1. Start from the current commit of `codex/campaign-correctness-remediation`.
2. Inspect `git status --short`. Preserve the completed campaign artifacts and
   this plan. Do not reset, delete, replay, or continue the campaign.
3. Create and switch to the branch:

   ```text
   codex/research-harness-remediation
   ```

4. Do not create a worktree.
5. Commit this plan first with:

   ```text
   docs: add research harness remediation plan
   ```

6. Implement the steps below in order. Commit and push after every step with the
   exact commit message specified for that step. Do not squash the commits.
7. Before each commit, inspect the diff and include only the files belonging to
   that step.

## Constraints for the whole implementation

- Keep `research/results.jsonl` and `research/research_state.json` as the existing
  sources of persisted campaign facts.
- Keep `research/brief.md` derived. Do not add another persisted state file.
- Keep the existing research phases and JSON deliverables.
- Do not add a new evaluation phase, request type, metric schema, lineage role, or
  command.
- Do not make a scientific decision for the Researcher.
- Do not automatically compare every candidate to `best_known`.
- Do not automatically request the task-reference instrument.
- Do not change training, the robot, scenario behavior, reward, observations,
  benchmark semantics, or final benchmark execution.
- Do not add a registry, dependency graph, AST analysis, plugin, dependency
  injection layer, transaction mechanism, or second integrity system above Git.
- Do not run a campaign, training, MuJoCo simulation, model evaluation, Git
  integration test, or reset test.
- Do not run the full test suite or the whole `tests/autoresearch` directory.
- Tests added by this work must use small synthetic dictionaries/files or existing
  checked-in artifacts as read-only examples. They must not create commits,
  branches, worktrees, models, or evaluation processes.

## Step 1 — Expose an authoritative current lineage and recipe view

### Objective

The Researcher must not reconstruct basic lineage facts by searching Git or by
guessing from old postmortems. The brief must expose the current factual state in
one compact place, with no recommendation about what to select next.

This step also fixes the terminology that caused a parameter-only change to be
retained accidentally: the existing `code.action` lineage field acts on the full
scientific recipe, not only Python source code.

### Required changes

#### `research/build_research_brief.py`

Add a compact section near the top of the generated brief named:

```text
## Current lineages and scientific recipes
```

Build it only from existing state, result, artifact metadata, and repository
facts. Do not persist a duplicate representation.

The section must contain:

- the exact currently valid `training_parent` identifiers:
  - `working`, when a working lineage exists;
  - `best_known`, when a best-known lineage exists;
  - every retained-lineage identifier already accepted by the current protocol;
- for every exposed lineage:
  - candidate name;
  - origin experiment;
  - accumulated training steps;
  - artifact path;
  - model fingerprint;
  - scientific commit;
  - effective parameters already stored with the lineage or artifact;
  - recorded evaluation artifact paths;
- the effective scientific recipe currently present in the worktree;
- an explicit factual parameter difference between the current worktree recipe,
  `working`, and `best_known` when they differ;
- a separate list of current experiment checkpoints available for measurement.

Do not mix checkpoint names with valid `training_parent` identifiers. Do not rank
lineages and do not describe one as preferred.

If a fact is absent, render `not recorded`; do not infer it from a similarly named
model.

Keep the section compact. Parameters may be rendered as one stable JSON object per
lineage. Do not duplicate full evaluation contents.

#### `research/instruments.md`

Clarify the existing lineage contract without changing its JSON schema:

- keep the field name `code.action` for compatibility;
- state that this action applies to the complete researcher-owned scientific
  recipe: researcher-owned source, tests, and `research/current_params.json`;
- define:
  - `keep`: keep the experiment's complete scientific recipe;
  - `revert`: restore the scientific parent's complete recipe;
  - `restore`: restore the complete recipe associated with the explicitly named
    eligible lineage;
- state that exact valid parent identifiers are listed in the current brief.

Do not introduce a renamed JSON field or a schema migration.

#### `research/program.md`

Use “scientific recipe” where the current text could make the Researcher believe
that lineage `code.action` affects source files but not parameters. Keep the
existing roles and lifecycle unchanged.

#### `run_research.ps1`

In lineage-decision prompts and console labels only, describe `code.action` as the
scientific recipe action. Do not alter the state machine or accepted JSON.

### Validation

Add or update focused tests in:

- `tests/autoresearch/test_console_presentation.py` for the generated brief;
- `tests/autoresearch/test_lineage_roles.py` only if a pure, non-Git helper needs
  coverage.

Use synthetic state and artifact metadata. Cover:

1. exact parent identifiers are displayed separately from checkpoints;
2. lineage origin, steps, artifact, fingerprint, commit, parameters, and evidence
   are displayed;
3. a lingering worktree parameter difference is visible;
4. missing facts render as `not recorded`;
5. the wording says that `code.action` controls the complete scientific recipe.

Do not test actual Git restoration in this step.

Run only the exact focused test functions added or changed, plus lint on touched
Python files.

### Commit

```text
fix: expose authoritative lineage and recipe state
```

Push the branch after the commit.

## Step 2 — Remove redundant incumbent-evidence transcription

### Objective

When the Researcher proposes replacing `best_known`, it must cite evidence for the
proposed replacement. It must not have to copy the incumbent's already recorded
evidence paths back into the proposal. The Runner already owns those incumbent
facts in `best_known_lineage.evaluation_artifacts`.

This removes the failure that stopped the previous campaign while preserving the
evidence guard itself.

### Required changes

#### `research/runner_protocol.py`

In validation of a `best_known` replacement:

1. continue to validate the proposed model's cited evidence exactly as today;
2. obtain incumbent evidence from
   `state["best_known_lineage"]["evaluation_artifacts"]`;
3. validate those stored paths as incumbent evidence;
4. require at least one incumbent measurement compatible with at least one cited
   measurement for the proposed model;
5. return a precise validation error if the state has no valid compatible
   incumbent evidence;
6. do not require incumbent evidence paths to be repeated in the Researcher's
   proposal;
7. do not choose the winner or weaken model/artifact identity checks.

Remove only the requirement that incumbent paths appear in the proposal. Do not
change the meaning of the proposed model's `best_known.evidence` list.

#### `research/instruments.md`

Update the lineage-decision entry so it states:

- `best_known.evidence` identifies evidence for the proposed best-known model;
- incumbent evidence is resolved from the current lineage state by the Runner;
- comparable evidence is still required on both sides.

#### `research/build_research_brief.py`

Ensure the Step 1 lineage section exposes the incumbent evidence paths the Runner
will use. Do not add a second evidence section.

### Validation

In `tests/autoresearch/test_lineage_roles.py`, use synthetic state and local JSON
fixtures only. Cover:

1. replacement succeeds when candidate evidence is cited and compatible incumbent
   evidence exists in `best_known_lineage.evaluation_artifacts`;
2. the proposal does not repeat the incumbent path;
3. replacement fails clearly when incumbent evidence is absent;
4. replacement fails clearly when existing incumbent evidence is incompatible;
5. model/artifact mismatch remains rejected.

Do not invoke Git and do not execute an evaluator.

Run only these focused test functions and lint the touched Python file.

### Commit

```text
fix: resolve incumbent evidence from lineage state
```

Push the branch after the commit.

## Step 3 — Make mechanism-driven remeasurement explicit

### Objective

The Researcher must be able to check a mechanism on already saved policies before
spending another training run. This is not a mandatory telemetry phase. It is the
existing post-training evaluation/refinement loop, used only when a measurement
can distinguish the competing explanations.

### Required changes

#### `research/program.md`

Clarify the existing post-training lifecycle:

```text
training completes
-> inspect training outcome and available evidence
-> formulate the scientific question for evaluation
-> request measurements
-> if the evidence is insufficient, optionally modify researcher-owned
   instrumentation and request another measurement round on saved policies
-> close the experiment when the evidence supports a decision
```

State explicitly:

- additional measurement rounds are available only while closing the current
  trained experiment;
- they may measure current candidates and eligible saved lineages through the
  existing request flow;
- if a proposed mechanism depends on an unmeasured quantity that can be observed
  on saved policies, measure it before launching a mechanism-specific intervention;
- no additional round is required when the available evidence already answers the
  scientific question.

Do not add an inter-experiment investigation state or make any instrument
mandatory.

#### `research/instruments.md`

Describe the existing evaluation request and researcher-owned instrumentation as
available during post-training analysis and its refinement rounds. Keep the
existing request schema and instrument catalogue. Do not prescribe a fixed list of
diagnostics.

#### `run_research.ps1`

Update only the initial post-training analysis prompt and evaluation-refinement
prompt so they require this reasoning order:

1. inspect what happened during training;
2. state the scientific question;
3. identify which measurement could change the interpretation;
4. request that measurement, or close if current evidence is sufficient.

The prompt must mention that researcher-owned instrumentation can be changed when
the relevant quantity is not currently emitted. Do not require a diagnostic code
change and do not prescribe a particular metric.

### Validation

Use focused text/contract tests in
`tests/autoresearch/test_research_protocol.py` and/or
`tests/autoresearch/test_console_presentation.py`.

Verify only that:

- refinement is optional;
- it is limited to the current experiment's post-training analysis;
- existing saved policies can be remeasured;
- no new state, request type, or required instrument is introduced.

Do not run any evaluation or simulation.

### Commit

```text
fix: expose mechanism-driven evaluation refinement
```

Push the branch after the commit.

## Step 4 — Separate artifact identity from success comparability

### Objective

Keep the broad evaluation fingerprint for artifact identity and diagnostic/cache
integrity, but stop treating a reward-only change as proof that two primary
success measurements cannot be paired.

### Required changes

#### `research/runner_protocol.py`

Keep `evaluation_semantics_fingerprint()` unchanged in purpose.

Add one narrower fingerprint for paired primary-success comparison. Use an
explicit small tuple of paths in this repository; do not build dependency
discovery. The tuple must cover the code that determines episode execution and
primary success extraction, and must exclude:

- `robot_learning/scenario/reward.py`;
- researcher-only diagnostic payload definitions that do not change primary
  success.

Name the stored field:

```text
comparison_semantics
```

Store it on newly produced research-evaluation records. Use it only when deciding
whether primary-success paired comparisons are compatible. Continue to use the
broad `evaluation_semantics` value for artifact naming, cache identity, detailed
diagnostic identity, and every existing purpose unrelated to paired primary
success.

Backward compatibility for existing artifacts must be conservative:

- if both records have `comparison_semantics`, require equality;
- otherwise allow pairing only when their existing broad
  `evaluation_semantics` values are equal;
- do not rewrite historical artifacts.

Do not relax candidate identity, panel, seed, episode, or per-episode pairing
checks.

#### Runner modules that serialize or read evaluation records

Update only the existing serialization/read paths that need to carry
`comparison_semantics`. Likely affected files are:

- `research/runner_execution.py`;
- `research/runner_protocol.py`;
- `research/run_experiment.py` only if it directly assembles the persisted record.

Do not move responsibilities between modules as part of this work.

#### `research/instruments.md`

Explain briefly that paired primary-success comparison requires matching primary
comparison semantics; detailed diagnostic artifacts retain their broader
evaluation identity. Do not expose implementation path lists to the Researcher.

### Validation

Add focused synthetic-record tests in
`tests/autoresearch/test_research_protocol.py`:

1. records with different broad semantics but equal `comparison_semantics` can be
   paired;
2. records with different `comparison_semantics` cannot be paired;
3. legacy records with equal broad semantics can still be paired;
4. legacy records with different broad semantics remain incompatible;
5. panel, seed, episode, and model identity checks remain unchanged.

Do not run a model or generate real evaluation artifacts.

### Commit

```text
fix: distinguish success comparison semantics
```

Push the branch after the commit.

## Step 5 — Stop reloading static context on same-session retries

### Objective

A validator retry resumes the same Researcher session. The full conversation is
already present, so asking it to reread all static files wastes context and tool
calls. Initial entries into a new phase still need their normal grounding.

### Required changes

#### `run_research.ps1`

Change only retry prompts used with `-Continue` after an invalid deliverable.

For those retry prompts:

- remove the blanket instruction to reread `AGENTS.md`, `research/program.md`,
  `research/scenario.md`, `research/instruments.md`, and `research/brief.md`;
- state that the same session context remains available;
- include the exact validator error;
- ask the Researcher to correct only the invalid or missing deliverable;
- allow rereading one relevant contract/state file when the error indicates that
  current state changed or an exact field definition is needed.

Do not change the normal first prompt for a new hypothesis, post-training analysis,
evaluation refinement, or lineage decision. Those prompts must keep their initial
grounding requirements.

Do not change retry count, session IDs, lifecycle, or validation.

### Validation

Add a small static test in `tests/autoresearch/test_console_presentation.py` that
checks:

- initial phase prompts still contain their grounding instruction;
- same-session retry prompts do not contain the blanket five-file reread;
- retry prompts still include the validator error and expected deliverable.

No process needs to be launched.

### Commit

```text
perf: avoid redundant context reload on retries
```

Push the branch after the commit.

## Step 6 — Request only decision-relevant measurements

### Objective

Reduce automatic-looking evaluation requests without limiting scientific freedom.
The Researcher must formulate a question first and request the smallest evidence
set whose outcome could change its interpretation or lineage decision.

### Required changes

#### `research/program.md`

State these neutral rules:

- evaluation is a scientific measurement, not an automatic competition step;
- formulate the question before choosing models, panels, and instruments;
- request only measurements whose possible outcomes could change the current
  interpretation or decision;
- reuse compatible measurements already listed in the brief;
- task-reference measurement is optional and is requested only when it answers the
  stated question;
- comparison with `working` or `best_known` is optional and justified by the
  question, not by phase convention.

Do not add a numeric gate, mandatory comparison, mandatory task-reference request,
or Runner-selected evaluation plan.

#### `research/instruments.md`

Keep all instruments equally documented. Add no recommendation to any individual
instrument entry. Put the “smallest decision-relevant set” rule once in the common
evaluation-request contract.

#### `run_research.ps1`

Align the post-training evaluation prompt with the same rule. It must ask for:

- the scientific question;
- why each requested measurement can change the answer;
- reuse of compatible existing evidence;
- the smallest sufficient set.

Do not force a comparison or task-reference measurement.

### Validation

Use focused static tests only. Verify that the prompt and protocol:

- do not make task-reference or comparison mandatory;
- require a scientific question and a reason for requested measurements;
- retain the existing JSON schema and phase transitions.

### Commit

```text
perf: focus evaluations on decision-relevant evidence
```

Push the branch after the commit.

## Final verification

After all six implementation commits:

1. inspect the complete diff from the branch point;
2. confirm no training/scenario/benchmark behavior changed;
3. confirm no campaign artifact or campaign state was rewritten;
4. confirm no new persisted state, phase, request type, or framework was added;
5. run Ruff only on touched Python files;
6. run only the individual fast unit tests changed by this plan;
7. do not run a campaign, training, evaluation, reset, Git workflow test, full
   suite, or full `tests/autoresearch` suite;
8. push the final branch state.

The final report must list:

- each commit hash and purpose;
- exact files changed per step;
- exact focused tests run and their duration;
- any intentional deviation from this plan.

If an implementation detail cannot follow this plan exactly, stop before adding an
alternative architecture. Report the conflict and wait for a decision.

## Acceptance criteria

The work is complete only when all of the following are true:

- the brief exposes valid parents, lineage identity, effective recipes, parameter
  differences, and recorded evidence without recommendation;
- `code.action` is consistently documented and presented as operating on the full
  scientific recipe;
- replacing `best_known` no longer requires the Researcher to repeat incumbent
  evidence paths already stored in lineage state;
- the existing evaluation-refinement loop clearly supports optional
  mechanism-driven remeasurement of saved policies;
- reward-only changes do not prevent an otherwise valid primary-success paired
  comparison, while incompatible task semantics still do;
- same-session retries do not reread all static context;
- evaluation requests are framed around the smallest decision-relevant evidence
  set rather than automatic comparison;
- all changes remain within the current simple architecture.
