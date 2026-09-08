# Research Harness Reasoning Rebalance — Implementation Plan

## Purpose

This change must correct the reasoning regressions observed after the recent
memory and strategy improvements without rolling those improvements back.

The current harness correctly preserves scientific strategy, lineage recipes,
evidence, and an explicit next direction. However, the Researcher can still:

- promote a secondary training signal into the campaign's main question;
- treat one failed intervention as if it resolved an entire mechanism class;
- choose an intervention partly to preserve transfer compatibility;
- defer the terminal benchmark merely because another experiment can be imagined.

The desired reasoning order is:

1. identify the unresolved measured behavioral gap of the best-known policy;
2. compare plausible causal explanations for that gap;
3. choose the intervention that best discriminates between those explanations;
4. only then choose fresh or transfer initialization based on scientific
   compatibility;
5. after training, distinguish what the exact intervention established from
   what remains unknown about the broader mechanism;
6. choose further research or terminal assessment according to information
   value, not according to whether another experiment is merely possible.

This is a focused correction to documentation, prompts, and brief ordering. It
must not create a new workflow, state, schema, validator, score, or instrument.

## Required branch and commit workflow

Implementation starts from branch `codex/research-reasoning-rebalance`, where
this plan is committed before implementation.

Use the following commits and push each commit immediately after it is created:

1. `rebalance research brief attention order`
2. `clarify mechanism-driven research reasoning`
3. `record research reasoning rebalance decision`

Do not combine all implementation into one final commit. Do not amend or squash
the plan commit. If the requested implementation cannot be completed without a
design change outside this plan, stop and report the conflict before coding it.

## Behavior that must remain unchanged

The implementation must preserve all of the following:

- the campaign objective and current investigation remain distinct;
- every closed non-terminal experiment leaves a concrete next scientific
  direction;
- the Scientific strategy remains mandatory and revisable;
- `reasoning.strategy_link` remains mandatory;
- the Researcher must have enough evidence to choose a rational next direction,
  not only enough evidence to select a model;
- the existing `fresh`, `transfer`, `continuation`, and `replication` operations;
- the existing fresh/transfer initialization justification;
- `working` and `best_known` remain distinct lineages;
- exact scientific recipe provenance and restoration remain intact;
- existing evidence identity and model identity checks remain intact;
- development measurements remain optional and reusable when compatible;
- comparison and task-reference measurement remain optional rather than phase
  defaults;
- the official benchmark remains protected, secret, terminal, and unavailable
  as development feedback;
- the existing proposal, evaluation-request, postmortem, and lineage-decision
  schemas remain unchanged;
- the Runner executes and validates; it does not choose the scientific question.

## 1. Reorder the generated research brief

### File

`research/build_research_brief.py`

### Objective

Put the latest scientific situation before durable lineage bookkeeping. The
Researcher must first see what just happened and what behavioral gap remains,
while still retaining complete access to lineage and recipe information.

### Required change

Change only the order in which existing brief sections are emitted. Do not
remove, summarize further, rename, or change the data model of any section.

The generated brief must present its main sections in this order:

1. current phase and the immediately required deliverable;
2. latest experiment or latest completed training/evaluation facts;
3. current Scientific strategy;
4. current lineages and scientific recipes;
5. experiment index, available artifacts, and the remaining existing evidence
   or operational sections in their current relative order.

`Current lineages and scientific recipes` must no longer precede the latest
result and Scientific strategy. Its complete identifiers, artifacts,
parameters, recipe information, and restoration information must remain
available after reordering.

Do not introduce a second compact lineage summary near the top. Do not copy the
strategy into another section.

### Focused tests

Update only the affected assertions in:

- `tests/autoresearch/test_research_context.py`
- `tests/autoresearch/test_console_presentation.py`
- `tests/autoresearch/test_scientific_reasoning.py` if it asserts section order.

Tests must prove that:

- latest-result content appears before Scientific strategy;
- Scientific strategy appears before current lineages and recipes;
- lineage identifiers, recipe details, and artifact references are still
  present;
- no brief content was dropped because of the reorder.

Run only the focused tests relevant to this commit, then commit and push.

## 2. Clarify the scientific reasoning contract

### Files

- `research/program.md`
- `research/instruments.md`
- `run_research.ps1`
- focused tests under `tests/autoresearch/`

### 2.1 Anchor the next direction to measured behavior

In `research/program.md`, retain the mandatory next scientific direction but
clarify its subject.

Add wording with this exact meaning:

- the next direction must remain anchored to the campaign objective and the
  most important unresolved measured behavioral gap of `best_known`;
- a new training statistic, implementation observation, or secondary finding
  does not automatically become the campaign's primary direction;
- when training metrics conflict with measured policy behavior, measured policy
  behavior governs the choice of the next scientific problem;
- a training metric may motivate a hypothesis only when the Researcher states a
  plausible causal link from that metric to the measured behavioral gap.

Do not hard-code any robot-specific failure mode, metric name, algorithm, reward
term, or scenario behavior.

### 2.2 Require competing explanations before selecting an intervention

In `research/program.md`, immediately before the existing proposal reasoning
requirements, require the Researcher to:

1. state the measured gap being addressed;
2. consider at least one plausible competing causal explanation;
3. explain why the selected intervention is the most discriminating reasonable
   next experiment among the explanations considered.

This must refine the existing `alternative`, `expected_observation`, and
`contradicting_observation` contract. Do not add a proposal field and do not
require a fixed number of hypotheses beyond the existing selected hypothesis
and at least one plausible alternative.

### 2.3 Separate intervention results from mechanism-class conclusions

In both `research/program.md` and the Scientific strategy guidance in
`research/instruments.md`, add wording with this exact meaning:

- rejecting one parameter value, representation variant, schedule, or other
  concrete intervention rejects that intervention under the tested conditions;
- it resolves the broader mechanism class only when the observed evidence
  actually discriminates against that class;
- otherwise, the mechanism remains open, with the failed intervention recorded
  as a scoped lesson;
- secondary findings belong in `Open questions` when relevant but do not
  automatically replace `Direction`.

Do not require the Researcher to repeat the full experiment history or maintain
a permanent list of every rejected intervention in the strategy.

### 2.4 Keep the existing strategy structure and define its entries precisely

In `research/instruments.md`, keep the existing four headings exactly:

- `Direction`
- `Lessons and limits`
- `Open questions`
- `Conditional next steps`

Clarify them as follows:

- `Direction`: the primary measured best-known behavioral gap and the current
  causal question selected to address it;
- `Lessons and limits`: scoped conclusions supported by completed evidence,
  explicitly separating an exact intervention result from a mechanism-class
  conclusion;
- `Open questions`: plausible competing explanations and relevant secondary
  findings that remain unresolved;
- `Conditional next steps`: the preferred discriminating continuation or
  bifurcation and the evidence that would cause the direction to change.

The next direction remains mandatory. `Conditional next steps` must not become
an excuse to provide no concrete next action.

### 2.5 Choose mechanism and intervention before initialization

In `research/program.md` and the experiment-proposal explanation in
`research/instruments.md`, preserve `reasoning.initialization_reason` but state
the required order explicitly:

1. choose the scientific mechanism and intervention;
2. determine whether the parent policy and its learned representation remain
   scientifically compatible with that intervention;
3. choose fresh or transfer initialization;
4. record that rationale in `initialization_reason`.

State explicitly that unchanged tensor dimensions alone do not establish
semantic compatibility. Do not express a preference for fresh or transfer.

In `run_research.ps1`, update the new-hypothesis prompt so it follows this same
order. The prompt must not lead with the list of initialization modes before it
asks for the gap, explanations, mechanism, and intervention. The operations may
still be named, but only after that reasoning instruction.

### 2.6 Update post-training reasoning prompts

In the post-training analysis prompt in `run_research.ps1`, retain the existing
requirement to establish a rational next scientific direction. Add concise,
explicit instructions to:

- compare the actual result with the proposal's expected and contradicting
  observations;
- state what the exact intervention established;
- state separately whether the broader mechanism is resolved or remains open;
- anchor the next direction to the primary measured best-known gap;
- treat conflicting training proxies as subordinate to measured policy
  behavior unless a causal link is justified;
- keep secondary findings as open questions unless evidence makes one the new
  primary gap.

Apply the same scientific semantics to any separate lineage/closure prompt that
asks the Researcher to update the postmortem or Scientific strategy. Do not
duplicate the full protocol text in every prompt; use compact instructions that
remove the current ambiguity.

Retry prompts must remain correction-only prompts. Do not add the full reasoning
contract to retry prompts.

### 2.7 Correct the terminal benchmark decision criterion

In `research/program.md`, `research/instruments.md`, and the relevant
post-training/closure prompt in `run_research.ps1`, preserve these facts:

- requesting the official benchmark terminates the campaign after either pass
  or fail;
- its result cannot be used to choose a later experiment;
- it is not a development measurement.

Replace the current rule that effectively permits a request only when no useful
scientific path remains. The new criterion must have this exact meaning:

- request the terminal benchmark when the available development evidence makes
  terminal assessment the highest-value next action for the best-known model;
- the mere existence of another imaginable or scientifically useful experiment
  does not by itself prohibit terminal assessment;
- the closure rationale must explain why terminal assessment is more valuable
  now than further development research.

Remove or replace all prompt/document wording equivalent to:

- “request only when no next experiment remains”;
- “omit while any scientifically useful path remains”;
- “stop only when no scientifically useful path remains.”

Do not add a numeric readiness threshold, automatic benchmark trigger, Runner
approval policy, or access to benchmark results after failure.

### Focused tests for section 2

Update only focused contract/presentation tests in:

- `tests/autoresearch/test_research_protocol.py`
- `tests/autoresearch/test_researcher_session.py`
- `tests/autoresearch/test_scientific_reasoning.py`
- `tests/autoresearch/test_research_context.py` when documentation text is
  asserted there.

Tests must establish that:

- a next scientific direction remains required;
- the direction is tied to the measured best-known gap and campaign objective;
- prompts require competing explanations before intervention selection;
- prompts choose intervention before initialization;
- same tensor shape is not described as sufficient semantic compatibility;
- post-training reasoning separates exact intervention evidence from broader
  mechanism conclusions;
- measured behavior takes precedence over conflicting training proxies;
- the official benchmark is still terminal and not development feedback;
- the obsolete “no useful path may remain” restriction is absent;
- proposal and lineage JSON schemas have not changed;
- no new phase, request type, or instrument was introduced.

Run only:

```text
uv run pytest -q tests/autoresearch/test_research_context.py tests/autoresearch/test_scientific_reasoning.py tests/autoresearch/test_research_protocol.py tests/autoresearch/test_researcher_session.py tests/autoresearch/test_console_presentation.py
```

Run Ruff only on Python files changed by this implementation. Do not run a
campaign, training job, evaluation, Git lineage simulation, or repository-wide
test suite.

Commit and push this section after the focused tests pass.

## 3. Record the protocol decision

### File

`research/PROTOCOL_DECISIONS.md`

Append one concise decision entry that records:

- observed problem: persistent strategy could be captured by secondary signals,
  exact failed interventions were overgeneralized, transfer compatibility could
  influence intervention choice, and terminal assessment was deferred by an
  overly strict stopping formulation;
- decision: preserve mandatory strategy and next direction while anchoring them
  to the measured best-known gap, require competing causal explanations, choose
  intervention before initialization, scope conclusions to the evidence, and
  select terminal assessment by information value;
- explicit non-change: no new phase, schema, instrument, scoring rule, automatic
  comparison, or automatic stopping condition;
- validation method: focused prompt/document/brief tests followed by a separate
  human-run campaign; the implementation itself must not launch that campaign.

Do not rewrite earlier decision entries. Commit and push this documentation and
any final focused test alignment as the third implementation commit.

## Out of scope

Do not implement any of the following:

- new proposal, evaluation, postmortem, or lineage fields;
- a new lifecycle state or investigation phase;
- a new measurement, comparison, benchmark, or analysis instrument;
- automatic experiment ranking, mechanism scoring, or direction scoring;
- hard experiment quotas, patience counters, or forced stopping rules;
- automatic continuation, transfer, fresh, or replication selection;
- an algorithm-specific or scenario-specific recommendation;
- changes to training, reward, observations, environment, model architecture, or
  evaluation semantics;
- changes to lineage restoration, recipe restoration, model/evidence identity,
  Git persistence, or campaign reset behavior;
- removal of the current evidence sufficiency, strategy, or provenance work;
- a general refactor of the Runner or research harness;
- training or campaign execution as validation.

## Completion criteria

The implementation is complete only when:

1. the brief presents current evidence and strategy before lineage bookkeeping;
2. the Researcher is still required to provide a concrete next direction;
3. that direction is explicitly grounded in the best-known model's measured
   behavioral gap rather than the newest available proxy;
4. the Researcher must compare plausible causal explanations before choosing an
   intervention;
5. fresh/transfer is selected after the intervention for compatibility reasons,
   without a preference for either mode;
6. post-training conclusions distinguish intervention evidence from broader
   mechanism conclusions;
7. terminal benchmark use is governed by highest next information value while
   remaining terminal and secret;
8. all existing schemas, phases, instruments, lineage semantics, and evidence
   integrity mechanisms are unchanged;
9. focused tests and targeted lint pass;
10. the three implementation commits and this plan commit are visible on the
    remote branch.
