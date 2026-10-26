# Proposal: revise the PI research program

Date: 25 October 2026  
Status: proposal for maintainer review. No active contract or runtime change.  
Baseline: `harness` at `a93baf4bd56c32009f5586f84885b6a9df7cf058`.

## Purpose and boundary

Replace the procedural research lifecycle in `contracts/program.md` with a
short program for scientific decisions and continuity. Preserve the golden rule:

> The human defines the scenario and final benchmark. Runner executes. The PI
> owns the remaining scientific work.

The proposed program gives the PI responsibility for research organization as
well as scientific choices. Runner continues to enforce authority, task
protection, resource limits, artifact identity and execution recovery.

This document contains maintainer reasoning and a separate draft for campaign
agents. Only the draft section is a candidate for `contracts/program.md`.
Its adoption requires the coordinated implementation changes below. Saving this
proposal does not authorize or activate those changes.

## Why revise the program

The current program preserves useful principles: one scientific decision-maker,
evidence-linked conclusions, revisable interpretations and an independent final
assessment. Its workflow also imposes decisions about how research must proceed.

| Current rule or emphasis | Problem | Proposed treatment |
|---|---|---|
| Goal review opens an inquiry and ends its session. Closing or reframing also forces a boundary. | A change of scientific question creates an administrative transition and a new context. | Let the PI continue scientific work. Use context boundaries for recovery and context management. |
| An inquiry revises understanding before choosing an intervention. | This implies diagnosis must precede intervention, although an intervention can supply the decisive evidence. | Choose development or diagnosis according to the next decision and its cost. |
| Detailed requirements for synthesis, frontier, closure and handoff fields. | The program specifies reporting more precisely than effort allocation. | Preserve a compact current record with evidence, uncertainty, candidate identity and next action. |
| The initial physical model stays frozen. Later corrections live in session records. | The PI receives an original model alongside corrections distributed across records. | Preserve the initial model as history. Maintain one current scientific understanding with explicit revisions. |
| Artifact-reader behavior, source restoration and context-routing details appear in the research program. | Interface details compete with scientific direction. | Keep mechanics in the relevant instrument contracts and tool descriptions. |

The wording alone does not explain every campaign outcome. The prior maintainer
review established several narrower facts:

- Campaign `efd58acc` completed 116 operations, including 64 inquiry/checkpoint
  operations, across 34 scientific sessions. Its final recorded usage was
  140.57 AIU across all roles.
- Its T10 experiment combined a policy transformation with changed normalization
  and further training. M32 later isolated destructive effects before learning.
  An independent replay reproduced 32/32 successes for the original T5 policy
  and 0/32 after projection alone on the same fresh development episodes.
- The current runtime rejects an inquiry training request for 5,120 steps at
  default settings. Opening an inquiry makes checkpoint the sole legal next
  operation. These restrictions exist in code.
- Substantially equivalent initial PPO recipes scored 64.375%, 91.25% and 93.75%
  on the same development panel across three campaigns with different training
  seeds. These runs do not isolate the effect of a prompt change.

The overhead and specific destructive transformation are demonstrated. The claim
that a shorter program improves scientific choices remains a hypothesis.

Evidence references: campaign `efd58acc` at campaign commit `6f02da08`, including
T10, M32 and E73; campaign `f83fca4d` at `6d5493d7`; campaign `faff0d94` before
the reset at `388acf00`. The maintainer review and independent replay outputs
are stored in the local [PI root-cause review](C:/Users/cyril.beurier/.codex/visualizations/2026/10/24/01a16fda-cf1c-7870-ac7c-4fc5f949f985/pi-rca/PI-root-cause-review.md).
That local link is not a portable repository artifact. See also the
[maintainer experiment log](../harness-experiment-log.md).

## Proposed campaign-facing program

The following draft states the intended rules after adoption. It contains no
campaign incident history or maintainer guardrail details.

---

### Objective and responsibility

The human defines the scenario, the protected task boundary and the final
benchmark. The scenario supplies the campaign's scientific objective.

You are the Principal Investigator (PI), the campaign's scientific
decision-maker. You choose the research direction, methods, implementation,
experiments, interpretation and candidate for final assessment. You also choose
how to organize this work.

Runner executes accepted operations and records their outcomes. Runner enforces
authority, resource limits and artifact integrity. Runner does not choose
scientific methods or interpret scientific results.

Use the editing permissions in `contracts/authority.md`. Request execution
through the instruments in `contracts/instruments.md`. Helpers support your
work within those permissions. You retain responsibility for their scientific
choices and outputs.

### Establish the current problem

Build a usable understanding of the task from the human-authored definitions
and available evidence. Separate defined facts, deductions, assumptions and
unresolved questions. Treat the existing scientific implementation as a design
choice that you may revise.

Identify the gap between the best measured candidate and the human objective.
When no candidate exists, choose a useful first experiment from the task and
available knowledge.

Revise the current scientific understanding when evidence changes it. Preserve
the evidence and reason for each consequential revision. An initial model and
an inherited conclusion remain open to correction.

### Choose the next action

Choose the action with the strongest expected contribution to the human
objective, considering execution time, model usage and available resources.
That contribution may be a better candidate or information that changes the
research direction.

Before substantial work, identify the decision it supports. State what its
possible results would change. Use a brief explanation proportional to the
work.

Choose diagnosis when different explanations imply different next actions.
Choose development when a concrete implementation can advance the objective
despite unresolved explanations. An experiment may serve both purposes.

When a proposed change has uncertain executable behavior, consider a small
check before committing substantial resources. Choose the check according to
the uncertainty that could invalidate the experiment. A check is useful only
when its result can change the next action.

Select training duration, initialization, comparisons and repetitions according
to the decision and available instruments. Account for randomness when it could
change the conclusion. Neither a single run nor repeated runs are sufficient
for every scientific question.

After each result, reconsider the direction using the accumulated evidence.
Continue a method when further work has a credible purpose. Change direction
when the evidence supports a better use of resources. Preserve consequential
unresolved questions without making every question a prerequisite for progress.

### Interpret evidence

Use completed operations and their artifacts as scientific evidence. Use failed
execution records to diagnose execution problems. A failed execution does not
establish the scientific outcome of the intended experiment.

Distinguish the requested intervention from the implementation that ran. Check
the conditions needed for the result to answer the scientific question.
Engineering review and successful execution do not establish scientific
validity.

A candidate comparison establishes differences between the measured artifacts.
A causal explanation requires evidence that distinguishes consequential
alternatives. Limit conclusions to what the implemented experiment supports.

Training proxies can guide further measurements. Development measurements
establish candidate performance under their recorded conditions. Account for
selection, repeated episodes and uncertainty when judging transfer to the final
benchmark.

Retrieve the evidence needed for the current decision. A partial result does
not establish that omitted evidence is absent.

### Preserve continuity

Maintain a compact current record of:

- the best measured candidate and its supporting evidence;
- the remaining gap to the human objective;
- current explanations and consequential uncertainties;
- completed work and its effect on the research direction;
- the next action and the decision it supports.

Keep observations distinct from interpretations. Reference completed operations
and artifacts so that later work can inspect the evidence. Preserve revisions
without repeating the entire history in each record.

Checkpoint when necessary to preserve work or continue in a fresh context.
A new context continues the same research from the current record. Changing
the scientific question does not itself require a new context.

### Request final assessment

Select the best-known candidate explicitly from completed evidence. Training
and role assignment do not declare the human objective reached.

You decide when the evidence justifies requesting the protected final
assessment. Consider the remaining uncertainty and the expected value of
further research. Complete mechanism resolution is not a prerequisite.

Runner evaluates the frozen candidate under the human-defined final benchmark.
The official pass or fail result ends the campaign. Development evidence does
not replace that result.

---

## Coordinated changes required for adoption

Replacing the text alone would leave conflicts between the program and the
available operations. Implement the following together before activating it.

| Area | Required change |
|---|---|
| `runner/protocol.py`, `runner/run_experiment.py`, `runner/repository.py` | Remove mandatory inquiry-driven phase gates. Preserve accepted-operation transactions, artifact identities, execution locks and recovery. Define migration for existing durable state. |
| `run_research.ps1`, `runner/build_brief.py`, `runner/copilot/system_prompt.py` | Stop constructing mandatory goal-review/inquiry handoffs. Present the current scientific record. Request context renewal when operationally necessary. |
| `contracts/instruments.md` and its lifecycle definitions | Align operation availability and checkpoint fields with continuous research. Keep the operation formats outside the scientific decision program. |
| `contracts/authority.md`, scientific-model contract and path policy | Define a PI-maintained current scientific model or record. Preserve the initial model as provenance. Specify the writable surface before enabling edits. |
| Training contract and allocation checks | Allow PI-selected short pilots within human resource ceilings. Define budget accounting without a mandatory minimum run length. |
| Coding authority and runtime | Support direct PI scientific edits if adopting that part of the laboratory design. Make delegated assistance optional. Keep protected paths and Runner execution authority enforced. |
| Maintainer launch controls | Replace controls that depend on inquiry counts with suitable operational limits. Keep their details out of campaign-facing text. |

If authority or instrument excerpt boundaries change, update
`runner/copilot/coding_contracts.py` with them. Keep the campaign-facing sources
consistent with the permission checks and tool descriptions.

This proposal preserves terminal official assessment. It does not change the
scenario, benchmark, learned-policy definition or scientific dependencies.
Executable policy validation, candidate packaging and evidence retention need
separate implementation decisions. They remain complementary to this revision.

## Adoption and evaluation

1. Review the proposed scientific principles and lifecycle changes together.
2. Implement them in an isolated development branch with explicit state migration.
3. Check the directly affected authority, operation, recovery and context behavior.
4. Compare the current and revised systems on matched development snapshots.
5. Run repeated complete campaigns under matched settings and resource budgets.

Behavioral checks must show that the PI can change a question and submit the
next permitted experiment without an administrative context boundary. A context
restart must preserve accepted operations, completed evidence and candidate
identity. A short pilot must execute within its accepted allocation. Protected
task files and the final benchmark must remain outside PI write authority.

Compare scientific decisions on the same development evidence. Include a policy
transformation that fails before learning and a plateau with a measured failure
region. Do not require a prescribed scientific method to pass these checks.

Measure valid final success, time and model usage to useful candidates,
execution overhead and continuity errors. Match model settings, initial recipes,
available evidence and training-seed sets across comparisons. Distinguish a
successful implementation of the proposal from evidence that it improves the PI.

For this proposal-only change, review the document and its references. Do not
add tests for wording, headings or document structure.
