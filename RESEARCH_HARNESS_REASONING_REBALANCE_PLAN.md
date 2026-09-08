# Research Harness Reasoning Rebalance — Exact Implementation Specification

## Execution rule

Implement exactly the edits specified below. Do not paraphrase the required
wording, introduce adjacent improvements, refactor surrounding code, add schema
fields, or invent tests. If an exact anchor is absent, stop and report the
missing anchor instead of choosing an alternative implementation.

Do not run training, evaluation, a campaign, reset logic, Git-lineage simulation,
or the full test suite.

The implementation branch is `codex/research-reasoning-rebalance`.

## Invariants that must not change

Do not change:

- proposal, evaluation-request, postmortem, or lineage JSON schemas;
- Runner states or phase transitions;
- validation, fingerprints, model identity, evidence identity, or persistence;
- `working`, `best_known`, retained-lineage, or scientific-recipe semantics;
- recipe restoration or Git behavior;
- available operations: training, continuation, replication, fresh, and transfer;
- available evidence instruments or their execution;
- benchmark implementation, secrecy, or terminal behavior;
- scenario, training, reward, observation, environment, or evaluation code.

The next scientific direction, Scientific strategy, `strategy_link`, evidence
sufficiency for the next direction, and initialization justification remain
mandatory. This change adjusts their meaning and presentation; it does not
remove them.

## Commit sequence

Create and push exactly these three implementation commits, in this order:

1. `rebalance research brief attention order`
2. `clarify mechanism-driven research reasoning`
3. `record research reasoning rebalance decision`

Push immediately after each commit. Do not amend, squash, or combine them.

---

## Commit 1 — Rebalance research brief attention order

### Modify `research/build_research_brief.py`

In `_render_v4_research_brief`, do not change any helper function or rendered
content. Change only the order of existing blocks.

Remove this call from immediately after `Current phase and latest event`:

```python
    lines.extend(["", *_current_lineages_and_recipes_lines(state, current_params)])
```

Keep the complete existing `## Latest experiment` block unchanged. Immediately
after the `if isinstance(pending, dict) / elif latest / else` block that ends in:

```python
    else:
        lines.append("No experiment has completed in this campaign.")
```

insert exactly:

```python
    strategy = scientific_strategy_section(postmortems, campaign_id)
    lines.extend(
        [
            "",
            "## Current scientific direction",
            "",
            "Revisable current investigation authored by the Researcher:",
            "",
        ]
    )
    lines.append(
        "\n".join(strategy.splitlines()[1:]).strip()
        if strategy
        else "No scientific strategy recorded for this campaign yet."
    )

    lines.extend(["", *_current_lineages_and_recipes_lines(state, current_params)])
```

Delete the old duplicate strategy block after `## Working lineage`, including
its local `strategy = ...` assignment. Keep `## Working lineage` unchanged and
after the lineage/recipe block.

The resulting top-level order must be exactly:

1. `## Current phase and latest event`
2. `## Latest experiment`
3. `## Current scientific direction`
4. `## Current lineages and scientific recipes`
5. `## Working lineage`
6. `## Campaign experiment index`

All later sections keep their current order and content.

### Modify focused tests

In
`tests/autoresearch/test_research_context.py::test_v4_brief_indexes_all_experiments_newest_first_without_candidate_metrics`,
replace the current section-order assertions with exactly:

```python
    assert rendered.index("## Current phase and latest event") < rendered.index(
        "## Latest experiment"
    )
    assert rendered.index("## Latest experiment") < rendered.index(
        "## Current scientific direction"
    )
    assert rendered.index("## Current scientific direction") < rendered.index(
        "## Current lineages and scientific recipes"
    )
    assert rendered.index("## Current lineages and scientific recipes") < rendered.index(
        "## Working lineage"
    )
    assert rendered.index("## Working lineage") < rendered.index(
        "## Campaign experiment index"
    )
```

In these three tests in `tests/autoresearch/test_console_presentation.py`:

- `test_v4_brief_exposes_authoritative_lineages_recipes_and_checkpoints`
- `test_v4_brief_renders_best_known_as_an_alias_of_identical_working_recipe`
- `test_v4_brief_renders_absent_lineage_facts_as_not_recorded`

replace the lineage-section end delimiter:

```python
        "## Latest experiment", 1
```

with:

```python
        "## Working lineage", 1
```

In `test_v4_brief_exposes_authoritative_lineages_recipes_and_checkpoints`, add:

```python
    assert brief.index("## Latest experiment") < brief.index(
        "## Current scientific direction"
    )
    assert brief.index("## Current scientific direction") < brief.index(
        "## Current lineages and scientific recipes"
    )
```

Do not change assertions proving that lineage IDs, artifacts, fingerprints,
scientific commits, parameters, evaluation artifacts, aliases, and checkpoints
remain visible.

### Validate, commit, and push

Run only:

```text
uv run pytest -q tests/autoresearch/test_research_context.py tests/autoresearch/test_console_presentation.py tests/autoresearch/test_scientific_reasoning.py
uv run ruff check research/build_research_brief.py tests/autoresearch/test_research_context.py tests/autoresearch/test_console_presentation.py
```

Commit with `rebalance research brief attention order`, then push.

---

## Commit 2 — Clarify mechanism-driven research reasoning

### Modify `research/program.md`

#### A. Replace the complete body of `## Scientific memory and direction`

Replace everything after that heading and before `## Lifecycle` with exactly:

```markdown
The campaign objective is always to improve learned behavior toward the
human-defined objective in `research/scenario.md`; the Scientific strategy does
not author or replace that objective. `Direction` is the current temporary
investigation. When a measured `best_known` model exists, `Direction` must name
its highest-priority unresolved behavioral gap and the causal question currently
being tested against that gap. Before a best-known model exists, use the most
relevant measured behavior available for the campaign objective.

A training statistic, implementation observation, or secondary finding does not
automatically become the primary direction. When a training metric conflicts
with measured policy behavior, measured policy behavior governs the choice of
the next scientific problem. A training metric may motivate an investigation
only when the Researcher states a plausible causal link to the measured
behavioral gap.

Maintain the current campaign's **Scientific strategy** section in
`research/postmortems.md`, using the exact format in `research/instruments.md`.
Separate this revisable synthesis from the historical experiment entries.
Preserve past observations and decisions; revise current interpretations with
new evidence rather than rewriting what was believed at the time.

`Lessons and limits` must scope every conclusion to the evidence. Failure of one
concrete intervention rejects that intervention under the tested conditions; it
rejects the broader mechanism class only when the evidence discriminates against
that class. `Open questions` records plausible unresolved explanations and
secondary findings, not a mandatory experiment queue. `Conditional next steps`
states the concrete preferred next action and the observation that would instead
change direction. The next direction remains mandatory when the campaign
continues.

Think beyond the next experiment without committing to a fixed sequence or
number of experiments. Revise the strategy when evidence changes it and state
uncertainty when evidence is insufficient. The `reasoning.strategy_link` may
advance, revise, or reject the current investigation; it does not need to
preserve it.
```

#### B. Replace the first two paragraphs of `## Experiment preparation`

Replace the text from `Inspect relevant repository state...` through
`does not require a parameter or code modification.` with exactly:

```markdown
Inspect relevant repository state and completed evidence. First identify the
measured behavioral gap being addressed. Compare the selected causal explanation
with at least one plausible alternative, then choose the intervention that most
clearly distinguishes them. Only after choosing the mechanism and intervention,
choose continuation, replication, or training with fresh or transfer
initialization and write `research/proposal.json`. Make scientific code or
parameter changes only when the selected operation calls for them. The phase is
incomplete until that deliverable exists and satisfies the contract in
`research/instruments.md`.

Before submitting, establish or update the Scientific strategy. The proposal's
existing `reasoning` fields record inspected evidence, the competing explanation,
expected and contradicting observations, the initialization rationale, and the
link to the strategy. Explain why the selected experiment discriminates between
the causal explanations. Choose fresh or transfer from the semantic compatibility
of the intervention with the parent policy and learned representation; unchanged
tensor dimensions alone do not establish semantic compatibility. Continuing an
unchanged method is a legitimate experiment and does not require a parameter or
code modification.
```

#### C. Replace the scientific interpretation text in `## Post-training analysis`

Keep all lifecycle and measurement-round mechanics. Replace the paragraphs
beginning `Revisit the proposal's original expected...` and `The postmortem and
strategy must explicitly...` with exactly:

```markdown
Compare the observed result with the proposal's original expected and
contradicting observations. State separately what the exact intervention
established and whether the broader causal mechanism is resolved or remains
open. Failure of one intervention does not close its mechanism class unless the
evidence actually discriminates against that class.

Update the Scientific strategy from measured behavior. When training metrics
and measured policy behavior disagree, use measured behavior to choose the next
scientific problem unless an explicit causal link justifies the proxy. Keep a
secondary finding in `Open questions` unless evidence shows that it is now the
highest-priority behavioral gap. Establish a concrete next direction anchored to
the campaign objective and the unresolved measured behavior of `best_known` when
the campaign continues.

Mechanistic investigation may use logs, code inspection, lightweight analysis,
scientific instrumentation, and development measurements as useful; no
particular diagnostic or action sequence is mandatory. State whether the current
investigation is resolved and direction changes, remains useful with a concrete
next action, or is genuinely inconclusive with the unresolved distinction and
its decision consequence. These are Researcher reasoning choices, not
Runner-controlled states.
```

#### D. Replace the final-benchmark paragraph before `## Validation and recovery`

Replace the complete paragraph beginning `The final benchmark may be requested`
with exactly:

```markdown
The final benchmark may be requested only through closure and targets the frozen
best-known model. It is a terminal objective verdict, not a development
measurement, lineage selector, or source for a later hypothesis. Requesting it
ends the campaign after either verdict. Request it when the available development
evidence makes terminal assessment of the best-known model the highest-value next
action. The existence of another imaginable or scientifically useful experiment
does not by itself prohibit the request. The closure rationale must explain why
terminal assessment is more valuable now than further development research.
```

#### E. Replace the body of `## Stopping`

Use exactly:

```markdown
Development measurements, training metrics, individual checkpoints, subsets and
seeds are not the official result. Continue with another experiment when further
development research is the highest-value next action. Request the official
benchmark when terminal assessment is the highest-value next action. The Runner
then ends the campaign after either `goal_reached` or `goal_not_reached`; a failed
official verdict is never development feedback for another hypothesis.
```

### Modify `research/instruments.md`

Do not change the proposal JSON example or any field name.

#### A. Replace the proposal reasoning prose

Replace the prose from `Maintain the campaign's Scientific strategy...` through
the paragraph ending `another experiment or replication is appropriate only
when its result can change the next scientific action.` with exactly:

```markdown
Maintain the campaign's Scientific strategy section before submitting. The
Runner requires its four existing entries and snapshots it with `reasoning` in
the experiment record. Existing historical records without these fields remain
readable; a newly submitted proposal must satisfy this contract.

An eligible `training_parent` must be exposed by the brief as `working`,
`best_known`, or a retained lineage ID. `continuation` continues the selected
recipe without a learning-method change. A `training` proposal may deliberately
apply a changed recipe to an existing parent with `initialization: "transfer"`.
Continuation, replication, and additional seeds are available scientific choices,
not mandatory controls or gates for accepting a model.

Use the existing reasoning fields in this order. `evidence` identifies the
measured behavioral gap. `alternative` states a plausible competing causal
explanation. `expected_observation` and `contradicting_observation` state how the
experiment distinguishes those explanations and what each outcome would teach.
`strategy_link` explains how that discriminating experiment advances, revises,
or rejects the current investigation.

Choose the mechanism and intervention before initialization. Then use
`initialization_reason` to explain why fresh or the selected transfer parent is
semantically compatible with that intervention. Unchanged tensor dimensions
alone do not establish semantic compatibility. Neither fresh nor transfer is
preferred by this contract.
```

#### B. Replace the paragraph after the Scientific strategy template

Replace the paragraph beginning `The campaign objective remains...` and ending
`may advance, revise, or reject the current investigation.` with exactly:

```markdown
The campaign objective remains the human-defined objective in
`research/scenario.md`; this strategy cannot replace it. `Direction` names the
highest-priority unresolved measured behavioral gap of `best_known` and the
current causal question. Before a best-known model exists, it uses the most
relevant measured campaign behavior. `Lessons and limits` records scoped
conclusions: an exact intervention result is not a mechanism-class conclusion
unless the evidence discriminates against that class. `Open questions` records
plausible competing explanations and relevant secondary findings.
`Conditional next steps` states the preferred concrete next action and the
evidence that would change it. It does not remove the requirement for a next
direction when the campaign continues. The proposal's `reasoning.strategy_link`
may advance, revise, or reject the current investigation.
```

#### C. Replace both official-benchmark explanations

Replace the paragraph beginning `Omit request_final_benchmark...` with exactly:

```markdown
Set `request_final_benchmark` to `false` when further development research is the
highest-value next action. Set it to `true` when the available development
evidence makes terminal assessment of `best_known` the highest-value next action.
The existence of another possible experiment does not itself decide between
these choices. A `true` value ends the campaign after either `goal_reached` or
`goal_not_reached`; the result cannot select a later hypothesis.
```

Under `## Request the official benchmark`, replace the paragraph beginning
`After applying the lineage decision...` with exactly:

```markdown
After applying the lineage decision, the Runner benchmarks the frozen best-known
model. Read the terminal verdict in `research/brief.md` under **Current status →
Reported result**. Request this assessment only when it is the highest-value next
action according to the available development evidence. The closure rationale
must explain why terminal assessment is more valuable now than further
development research. The assessment ends the campaign after either verdict and
is never an experiment-selection probe or input to another hypothesis.
```

### Modify `run_research.ps1`

Do not change control flow, conditions, variables, function calls, or retry
prompts. Replace only the three initial prompt arrays below.

#### A. Replace `$analysisPrompt` exactly

```powershell
        $analysisPrompt = @(
            $analysisPhasePrompt
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
            "Inspect what happened during training and compare the result with the proposal's expected and contradicting observations. State separately what the exact intervention established and whether the broader causal mechanism is resolved or remains open."
            "Use measured policy behavior, not a conflicting training proxy, to choose the next scientific problem unless you state a causal link from that proxy to the measured behavioral gap. Keep secondary findings as open questions unless evidence makes one the highest-priority gap."
            "State the scientific question before requesting evidence. Request only measurements whose possible outcomes can change the interpretation, model/lineage decision, or next scientific direction. Reuse compatible existing evidence. Comparison and task-reference measurement are optional."
            "Available evidence tools include checkpoint inventory and raw-log query, structured-artifact analysis, code inspection, lightweight local analysis, researcher measurement instrumentation, research measurement, task-reference measurement, and optional paired comparison."
            "Current candidates and eligible saved lineages can be remeasured through the existing request flow. If the relevant quantity is not currently emitted, you may modify researcher-owned measurement instrumentation before requesting it. Additional measurement rounds are optional and available only while closing this trained experiment."
            "When the campaign continues, establish a concrete next direction anchored to the campaign objective and the highest-priority unresolved measured behavior of best_known. Preserve a broader mechanism as open when only one concrete intervention failed."
            "Choose exactly one outcome: write research/evaluation_request.json for another measurement round, or append the experiment postmortem and write a closure-only research/proposal.json choosing working lineage, code action, retention, and optionally best known. Candidate-only measurement and closure without new measurements are valid."
            "Set request_final_benchmark to true only when terminal assessment of best_known is the highest-value next action according to the available development evidence, and explain why it is more valuable now than further research. A true value ends the campaign after either goal_reached or goal_not_reached and its result cannot select a later hypothesis."
            "Do not run training, measurements, Git mutations, final assessment, or research/run_experiment.py; the launcher validates and executes the accepted deliverable."
        ) -join " "
```

#### B. Replace `$decisionPrompt` exactly

```powershell
        $decisionPrompt = @(
            "Current phase: close experiment $($researchState.pending_researcher_decision.experiment) and resolve its lineage and scientific recipe. Do not exit without the required deliverables."
            "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
            "Inspect the detailed evidence referenced for this experiment as needed to support the postmortem and lineage decision, preferring targeted extraction over full-artifact reads."
            "Use campaign artifacts for scientific evidence; inspect read-only Git only if the current experiment's scientific recipe delta is needed to justify keep or revert."
            "In the postmortem and Scientific strategy, state separately what the exact intervention established and whether its broader causal mechanism remains open. When the campaign continues, keep the next direction anchored to the highest-priority unresolved measured behavior of best_known."
            "Set request_final_benchmark to true only when terminal assessment is the highest-value next action according to available development evidence; explain why it is more valuable now than further research. A true value ends the campaign after either verdict and cannot provide feedback for another hypothesis."
            "Expected deliverables: the required experiment entry in research/postmortems.md and the lineage-only research/proposal.json, using the contracts in research/instruments.md."
            "Do not design another evaluation, modify the next learning method, propose the next experiment, or invoke research/run_experiment.py; the launcher validates and executes the decision."
        ) -join " "
```

#### C. Replace `$researchPrompt` exactly

```powershell
    $researchPrompt = @(
        "Current phase: prepare experiment $nextExperiment. The previous experiment is closed and no evaluation or lineage decision is pending. Do not exit without the required deliverable."
        "Read AGENTS.md, research/program.md, research/scenario.md, research/instruments.md, and research/brief.md."
        "Start from the campaign objective and the highest-priority unresolved measured behavioral gap of best_known. Compare the selected causal explanation with at least one plausible alternative, then choose the intervention that most clearly distinguishes them."
        "Only after choosing the mechanism and intervention, choose continuation, replication, or training with fresh or transfer initialization. Base fresh or transfer on semantic compatibility with the parent policy and learned representation; unchanged tensor dimensions alone do not establish compatibility."
        "Available evidence tools include checkpoint inventory and raw-log query, structured-artifact analysis, code inspection, lightweight local analysis, and focused researcher-owned tests."
        "Use the brief and campaign artifacts for scientific evidence; inspect read-only Git only if the selected operation requires understanding the current code state or delta."
        "Code or configuration edits are required only when the selected operation calls for them."
        "Expected deliverable: research/proposal.json for experiment $nextExperiment, using the unchanged contract in research/instruments.md, plus any edits called for by the selected operation."
        "Do not exit after analysis or diagnosis: this phase is incomplete until research/proposal.json has been written."
        "Do not start training or evaluation, write a lineage decision, or invoke research/run_experiment.py; the launcher validates and executes the proposal."
    ) -join " "
```

### Modify focused tests

Do not add a test file.

In `tests/autoresearch/test_researcher_session.py`:

1. In `test_phase_prompts_expose_choices_without_bounded_task_framing`, remove
   the assertion counting the old `Available preparation operations...` sentence
   and add exactly:

```python
    assert LOOP.count(
        "Compare the selected causal explanation with at least one plausible alternative"
    ) == 1
    assert LOOP.count(
        "Only after choosing the mechanism and intervention, choose continuation"
    ) == 1
    assert LOOP.count(
        "unchanged tensor dimensions alone do not establish compatibility"
    ) == 1
```

2. Replace
`test_post_training_prompt_distinguishes_continuation_from_terminal_assessment`
with exactly:

```python
def test_post_training_prompt_distinguishes_research_from_terminal_assessment():
    assert "terminal assessment of best_known is the highest-value next action" in LOOP
    assert "explain why it is more valuable now than further research" in LOOP
    assert "ends the campaign after either goal_reached or goal_not_reached" in LOOP
    assert "its result cannot select a later hypothesis" in LOOP
    assert "when a scientifically useful next experiment remains" not in LOOP
```

In `tests/autoresearch/test_research_protocol.py`:

1. Keep every schema and validator test unchanged.
2. In
   `test_post_training_reasoning_requires_a_revisable_investigation_interpretation`,
   replace assertions for removed prompt text with:

```python
    assert "what the exact intervention established" in LOOP
    assert "whether the broader causal mechanism is resolved or remains open" in LOOP
    assert "Preserve a broader mechanism as open when only one concrete intervention failed" in LOOP
    assert "These are Researcher reasoning choices, not Runner-controlled states." in normalized_program
```

3. In `test_evaluation_requests_support_the_model_decision_and_next_direction`,
   preserve assertions about optional comparison, optional task-reference
   measurement, reusable evidence, and evidence sufficiency. Add:

```python
    assert "measured policy behavior governs the choice of the next scientific problem" in normalized_program
    assert "states a plausible causal link to the measured behavioral gap" in normalized_program
    assert "highest-priority unresolved measured behavioral gap" in normalized_program
```

4. Add exactly:

```python
def test_experiment_choice_precedes_initialization_choice():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    normalized_program = " ".join(PROGRAM.split())
    normalized_instruments = " ".join(instruments.split())

    assert "Compare the selected causal explanation with at least one plausible alternative" in LOOP
    assert "Only after choosing the mechanism and intervention" in LOOP
    assert "Choose the mechanism and intervention before initialization." in normalized_instruments
    assert "unchanged tensor dimensions alone do not establish semantic compatibility" in normalized_program
    assert "Neither fresh nor transfer is preferred by this contract." in normalized_instruments
```

5. Add exactly:

```python
def test_terminal_assessment_uses_information_value_without_becoming_feedback():
    instruments = (ROOT / "research" / "instruments.md").read_text(encoding="utf-8")
    combined = " ".join((PROGRAM + "\n" + instruments + "\n" + LOOP).split())

    assert "terminal assessment" in combined
    assert "highest-value next action" in combined
    assert "more valuable now than further development research" in combined
    assert "ends the campaign after either verdict" in combined
    assert "no next experiment is intended" not in combined
    assert "no scientifically useful path remains" not in combined
    assert "when a scientifically useful next experiment remains" not in combined
```

Do not add Runner execution or JSON validation tests because those mechanisms do
not change.

### Validate, commit, and push

Run only:

```text
uv run pytest -q tests/autoresearch/test_research_protocol.py tests/autoresearch/test_researcher_session.py tests/autoresearch/test_scientific_reasoning.py tests/autoresearch/test_research_context.py
```

Do not run Ruff: no Python production file changes in this commit. Commit with
`clarify mechanism-driven research reasoning`, then push.

---

## Commit 3 — Record research reasoning rebalance decision

### Modify `research/PROTOCOL_DECISIONS.md`

Append exactly:

```markdown
## 2026-09-08 — Anchor strategy to measured behavior before choosing initialization

Decision: Keep the mandatory revisable Scientific strategy and concrete next
direction, but anchor them to the campaign objective and the highest-priority
unresolved measured behavior of the best-known model. Require the Researcher to
compare a causal explanation with a plausible alternative and choose the
discriminating intervention before choosing fresh, transfer, continuation, or
replication. Treat the result of one concrete intervention as evidence about that
intervention, not automatically as resolution of its broader mechanism class.

Reason: Recent campaigns showed that persistent strategy could be captured by a
secondary training signal, that transfer compatibility could influence the
intervention itself, and that scoped negative results could be generalized too
broadly. The existing strategy, evidence sufficiency, lineage provenance, and
recipe restoration remain useful and are preserved.

Terminal assessment: Keep the official benchmark secret and terminal. Choose it
when available development evidence makes assessment of the best-known model the
highest-value next action, rather than requiring every scientifically useful path
to be exhausted first. A failed official verdict remains unavailable as feedback
for another hypothesis.

Scope: This changes brief ordering and Researcher-facing reasoning instructions
only. It adds no schema field, phase, instrument, score, automatic comparison,
automatic stopping rule, or Runner scientific decision.
```

Run only:

```text
git diff --check
```

Do not rerun tests passed in commits 1 and 2. Commit with
`record research reasoning rebalance decision`, then push.

## Final report required from the implementer

Report only:

- the three commit hashes;
- the focused test commands and pass counts;
- confirmation that no schema, state transition, instrument, scientific code,
  training code, evaluation semantics, fingerprint, or Git behavior changed;
- deviations from this specification. The expected deviation list is empty.
