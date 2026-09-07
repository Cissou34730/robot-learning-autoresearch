# Research Harness Correction Plan

## Goal

Correct the generic methodological regression revealed by campaign
`6f3b5e54-dc1e-4502-bd86-3318074de79c`.

The harness currently helps the Researcher obtain enough evidence to choose a
saved model, but it may stop the investigation before enough evidence has been
used to choose the next scientific direction. A temporary open question can
then capture the persisted Scientific strategy and produce repeated experiments
that resolve uncertainty without improving the learned behavior.

This correction must work for any scenario supported by the repository. Do not
mention the current robot, its geometry, one learning algorithm, a particular
success percentage, a particular panel, or a fixed number of replications in
the implemented protocol.

## Non-negotiable constraints

- Keep the current lifecycle and Runner/Researcher responsibilities.
- Add no phase, state file, scheduler, search policy, stopping rule, experiment
  quota, ranking rule, automatic comparison, or automatic scientific decision.
- Add no proposal or evaluation-request field.
- Keep replication, continuation, fresh initialization, transfer
  initialization, measurement, and direct closure available to the Researcher.
- Keep campaigns scientifically isolated. Do not import lessons, postmortems,
  strategies, measurements, or model state from another campaign.
- Keep exact lineage parents and complete scientific recipes visible.
- Keep evaluation instruments optional.
- Do not require a particular panel, seed count, episode count, comparison, or
  replication count.
- Do not run training, evaluation, reset, a campaign, Git workflow simulations,
  or the complete test suite during implementation.

## Required Git preparation

Perform these steps before changing harness code.

1. Confirm that no training, evaluation, or Researcher process is still writing
   campaign files.
2. Inspect `git status` and identify the durable artifacts from the current
   campaign. Preserve the campaign as it ended; do not reset or rewrite it.
3. Commit only its durable tracked and untracked campaign artifacts, including
   updated result/state/history files and completed evaluation artifacts when
   present. Do not commit transient `research/proposal.json` or
   `research/evaluation_request.json` controls.
4. Create and switch to a new branch named
   `codex/research-strategy-remediation` from that campaign snapshot.
5. Add this plan on the new branch and commit it alone with message:
   `docs: define research strategy remediation`
6. Implement the corrections below in the stated commit sequence. Push the new
   branch after each implementation commit so the work remains reviewable.

Do not amend or squash the campaign snapshot into an implementation commit.

## Root cause that the implementation must address

The relevant failure chain is generic:

1. The efficiency rule asks for the smallest evidence needed for the immediate
   decision.
2. The Researcher obtains enough evidence to choose a model, but does not use or
   request enough evidence to choose the next scientific direction.
3. One unresolved question becomes the best available next topic.
4. That temporary question is written into the persisted Scientific strategy.
5. `strategy_link` gives the temporary question inertia across experiments.
6. A contradicting result is reframed as another uncertainty, allowing the same
   investigation to continue without a concrete change in scientific action.

The harness must not decide when an investigation stops. It must make the
Researcher explicitly decide whether the current investigation is resolved,
still worth pursuing, or should give way to another direction.

Reduced retry context and reduced tool calls are not the cause and must remain.
The authoritative lineage/recipe view is also not the cause and must remain.

## Change 1 — Correct the definition of sufficient evidence

### Intent

Keep question-led, non-redundant evaluation, but stop treating a resolved model
selection as sufficient scientific understanding by itself.

### Files

- `research/program.md`
- `research/instruments.md`
- `run_research.ps1`
- focused prompt/documentation tests already covering these files

### Exact change

Replace the current emphasis on the "smallest sufficient set" with one shared
rule, expressed concisely and consistently:

> Evidence is sufficient when it supports the current model/lineage decision
> and, if the campaign objective has not been reached, supports a rational next
> scientific direction. Minimize redundant or decision-irrelevant evidence, not
> evidence whose absence leaves the next direction arbitrary.

Apply this rule to both possible post-training paths:

- When existing logs, artifacts, code inspection, and local analysis already
  provide both forms of understanding, the Researcher may close directly.
- When the model decision is clear but the next direction is not, the
  Researcher must inspect available detailed evidence, improve its
  researcher-owned instrumentation when necessary, or request a justified
  measurement before closing.

Do not turn this into mandatory evaluation. Do not require evidence about every
open question. Evidence is selected for the current scientific decision and the
next direction only.

In the initial post-training prompt in `run_research.ps1`, add one short
instruction requiring the Researcher to establish both the model decision and,
when further research is needed, the next scientific direction. Keep instrument
descriptions in `research/instruments.md`; do not duplicate their schemas in the
PowerShell prompt.

Do not change retry prompts except where an existing assertion expects the old
wording. Retry prompts must remain compact and must not reload static context.

### Validation

Update only focused tests that assert the relevant documentation or initial
post-training prompt. Verify that:

- direct closure remains valid;
- an evaluation request remains optional;
- no specific instrument or quantity is required;
- retry prompts remain compact.

### Commit

`fix: require evidence for the next scientific direction`

## Change 2 — Separate campaign objective from current investigation

### Intent

Prevent a temporary investigation from silently replacing the durable campaign
objective.

### Files

- `research/program.md`
- `research/instruments.md`
- `research/build_research_brief.py`
- `tests/autoresearch/test_console_presentation.py`
- existing focused Scientific strategy tests

### Exact change

Keep the existing Scientific strategy section and its four existing entries:

- `Direction`
- `Lessons and limits`
- `Open questions`
- `Conditional next steps`

Do not add a field, heading, state object, or schema version.

Define their semantics as follows:

- The campaign objective is always to improve learned behavior toward the
  human-defined objective in `research/scenario.md`. It is not authored or
  replaced by the Scientific strategy.
- `Direction` is the current temporary investigation, not the campaign
  objective.
- `Lessons and limits` records what the current campaign evidence supports and
  what it does not support.
- `Open questions` records uncertainty; it is not a queue of experiments that
  must be completed.
- `Conditional next steps` describes alternatives available after the current
  investigation, not a commitment to continue the same family.

Clarify that `reasoning.strategy_link` may advance, revise, or reject the current
investigation. It does not need to preserve it.

In the generated brief:

1. keep the existing current phase/latest-event section;
2. add one compact generic factual line stating that the campaign objective is
   the objective defined by `research/scenario.md`;
3. label the existing Researcher-authored strategy as a revisable current
   investigation;
4. keep the current lineage identities, valid parents, recipes, parameters, and
   evidence exactly available;
5. do not perform a broad section reorder or remove lineage information.

Do not copy scenario-specific objective text into the brief builder. Reference
`research/scenario.md` as the authoritative objective.

### Validation

Verify with focused rendering tests that:

- the campaign objective and revisable current investigation are visibly
  distinct;
- all four existing strategy entries remain present;
- valid parent identifiers and exact scientific recipes remain present;
- no open question is rendered as mandatory work;
- no scenario-specific wording is hard-coded.

### Commit

`fix: separate objective from current investigation`

## Change 3 — Require an explicit investigation decision after contradictory evidence

### Intent

Handle stochastic or otherwise contradictory results without imposing another
replication or imposing an automatic stop.

### What the harness must do

After post-training evidence is available, the Researcher must explicitly state
one of these scientific interpretations in the existing postmortem and strategy
text:

- the current investigation is sufficiently resolved and the next direction
  changes;
- the current investigation remains useful, with a concrete explanation of what
  another experiment can change in the next scientific action;
- the evidence is genuinely inconclusive, with the unresolved distinction and
  its decision consequence stated explicitly.

These are reasoning choices, not new enum values and not Runner-controlled
states. Do not parse, rank, or automatically enforce the chosen scientific
interpretation.

### Files

- `research/program.md`
- `research/instruments.md`
- `run_research.ps1`
- focused prompt/documentation tests

### Exact change

Use the existing proposal fields. Do not add `next_if_expected`,
`next_if_contradicted`, or any equivalent field.

Clarify the existing meanings:

- `expected_observation` describes evidence that supports the hypothesis and
  what would be learned from it;
- `contradicting_observation` describes evidence that weakens the hypothesis and
  what would be learned from it;
- `strategy_link` explains how the proposed experiment advances, revises, or
  rejects the temporary current investigation.

In post-training instructions, require comparison with the proposal's recorded
expected and contradicting observations. If the Researcher repeats the same
hypothesis family or requests another replication, its written strategy must
explain why the evidence already collected does not resolve the investigation
and what concrete next action can differ after the additional result.

The Runner continues to validate only the existing structure and non-empty
strings. Do not add semantic validation of scientific prose.

### Validation

Focused tests must verify the documentation and initial post-training prompt,
not the scientific quality of generated prose. Verify that no wording:

- mandates another seed or replication;
- mandates abandoning a hypothesis;
- limits the number of experiments;
- changes proposal validation fields;
- gives the Runner scientific authority.

### Commit

`fix: make current investigations explicitly revisable`

## Change 4 — Correct false replication measurement summaries

### Intent

Stop completed replication measurements from appearing as `unmeasured`, which
falsely suggests that an investigation is incomplete.

### Files

- `research/build_research_brief.py`
- `tests/autoresearch/test_console_presentation.py`

### Exact change

The `Repeated operations` renderer currently reads checkpoint-local
`candidate.evaluations`, while completed schema-v4 measurements are persisted in
the experiment result's `requested_evaluations` and
`task_reference_evaluations`.

For each experiment in a replication group, derive the summary from those
authoritative result-level lists. Render:

- experiment number;
- training seed;
- candidate name;
- instrument/panel;
- episodes and evaluation seed when present;
- success percentage when present.

Render `unmeasured` only if both result-level measurement lists are empty. Do
not infer measurement from training metrics and do not include detailed episode
diagnostics.

### Validation

Add focused fixtures for:

- a measured research evaluation;
- a measured task-reference evaluation;
- measurements of different checkpoints in different replications;
- a genuinely unmeasured replication.

### Commit

`fix: report replication measurements from result evidence`

## Change 5 — Accept legacy comparison semantics without equating them

### Intent

Prevent an older scientific recipe from becoming unevaluable only because it
predates `PRIMARY_COMPARISON_SEMANTICS_VERSION`.

This is an operational compatibility correction. It is not part of fresh versus
transfer selection and must not change initialization or lineage behavior.

### Files

- `research/runner_protocol.py`
- `tests/autoresearch/test_research_protocol.py`

### Exact change

In `comparison_semantics_fingerprint()`:

- treat an absent `PRIMARY_COMPARISON_SEMANTICS_VERSION` assignment as legacy
  version `0`;
- include legacy `0` in the fingerprint;
- keep explicit current version `1` distinct from legacy version `0`;
- keep rejection of duplicate assignments;
- keep rejection of malformed explicit assignments.

Do not move the version marker, change fingerprint paths, change evaluation
schemas, or alter compatibility rules beyond the missing-marker fallback.

### Validation

Add focused tests proving:

- missing marker returns a stable fingerprint;
- explicit version `1` differs from missing/legacy version `0`;
- changing an explicit version changes the fingerprint;
- duplicate and malformed explicit assignments remain invalid.

### Commit

`fix: treat missing comparison version as legacy semantics`

## Documentation record

Update `research/PROTOCOL_DECISIONS.md` in the relevant implementation commits.
Record only these decisions:

- evidence sufficiency covers both the current model decision and the next
  scientific direction;
- the campaign objective is distinct from the revisable current investigation;
- contradictory evidence requires an explicit Researcher interpretation, not a
  Runner decision;
- replication summaries use completed result evidence;
- missing comparison-version metadata is legacy version `0`, not current
  semantics.

Do not copy the campaign-specific failure sequence into the permanent protocol
decision log.

## Test scope

Run formatting and lint only on touched files. Run only the focused test modules
that own changed behavior, normally:

```powershell
uv run pytest -q tests/autoresearch/test_console_presentation.py
uv run pytest -q tests/autoresearch/test_research_protocol.py
uv run pytest -q tests/autoresearch/test_scientific_reasoning.py
```

Run an additional focused module only if it directly owns an edited function.
Do not run `uv run pytest` without a target. Do not run scenario, training,
benchmark, reset, Git workflow, model-runtime, or campaign tests for these
documentation, brief-rendering, and comparison-fingerprint changes.

## Final acceptance criteria

- A model can still be selected with no additional evaluation when existing
  evidence is sufficient.
- A Researcher that needs further research is told to establish a rational next
  direction, not merely select a model.
- The campaign objective cannot be replaced by temporary strategy prose.
- An open question does not become mandatory work.
- Another experiment in the same family remains possible but requires an
  explicit Researcher rationale using existing fields.
- No scientific stop or continuation decision is made by the Runner.
- No new schema, phase, state, abstraction, or mandatory instrument exists.
- Campaigns remain isolated.
- Exact lineage and recipe visibility is preserved.
- Replication measurements are reported truthfully.
- Restoring an older recipe without an explicit comparison version no longer
  crashes evaluation and does not make it comparable to version `1`.
- Retry context and targeted tool-use optimizations remain unchanged.
