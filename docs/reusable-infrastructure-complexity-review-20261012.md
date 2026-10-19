# Review of complexity in reusable infrastructure

Date: 2026-10-12.
Updated: 2026-10-13.

**Judgment: SIMPLIFY.**

The two reviews identify three local cleanup opportunities and five opportunities from the broader architecture review.
Four architecture findings concern repeated rules, repeated plans, or duplicate history updates.
The fifth architecture finding concerns duplicate prompt content.
The additional review identifies two modules and two functions that concentrate too many responsibilities.
These findings overlap with some architecture findings.
They do not represent four additional execution defects.

The initial review did not examine the architecture deeply enough to justify its broad conclusion.
The second review changes that conclusion.
Several layers meet explicit requirements, but repeated responsibility creates unnecessary maintenance work.
The first two reviews omitted a separate assessment of responsibility concentration.
That omission did not establish the absence of god modules or god functions.

## Scope and limits

This document combines both reviews and the additional assessment of modules and functions.
The reviews examine reusable infrastructure, launchers, contracts, agent runtimes, evidence tools, and maintainer utilities.
The reviews exclude campaign commits, campaign results, campaign reports, and campaign-specific scientific changes.

The initial and architecture findings record the 2026-10-12 review.
The additional findings record the 2026-10-13 inspection.
Later source changes can alter the status of a finding.

The review uses static source inspection and traces calls between components.
The review does not execute tests, training, or evaluation.
The review does not measure performance or scientific outcomes.
This document does not approve an implementation change.

Source references identify the functions that support each finding.
The references describe reusable code, not campaign evidence.

The document uses the [ASD-STE100 skill](C:/Users/cyril.beurier/code/.copilot/skills/simplified-technical-english/SKILL.md).
The document applies structural rules and uses plain words.
The document does not claim compliance with the official ASD dictionary.

The review applies these methods:

- YAGNI: require a current need for an optional capability.
- Simple design: preserve required behavior before a reduction in duplication or elements.
- Value engineering: compare a component's function against its total maintenance cost.
- Speculative generality: require evidence that an abstraction is unnecessary.
- Trade-off analysis: compare alternatives against explicit reliability and ownership requirements.

### Terms

| Term | Meaning in this document |
|---|---|
| PI | The scientific agent that uses the repository's bounded tools. |
| Runner | The trusted component that accepts operations and manages execution and state. |
| Backend | The Copilot or OpenCode runtime integration. |
| Plan | The checked operation details that Runner uses to construct a pending operation. |
| Fingerprint | A value that identifies artifact content and supports integrity checks. |
| Training | The process that produces policy artifacts from learning operations. |
| Coding child | The scoped Copilot agent that can edit authorized scientific files. |
| Finding | An issue that the review supports through source evidence. |
| Pending operation | An accepted operation that Runner must execute, complete, or recover. |
| God module | A module that concentrates distinct responsibilities and makes separate changes depend on the same implementation. |
| God function | A function that mixes distinct responsibilities and their state, which obscures control flow and ownership. |
| Coordinator | A function that orders stages and retains control of their shared transaction. |
| Event handling | The code that receives runtime events and applies the corresponding actions. |
| Usage accounting | The calculation of token and cost totals for a runtime session. |

### Evidence categories

**Facts:** The cited source contains the functions, rules, and consumers described below.

**Assumptions:** The smaller alternatives can preserve required behavior after implementation and targeted checks.
The review does not establish that result through execution.

**Hypotheses:** Fewer rule definitions can reduce future inconsistencies.
Fewer history writers can reduce recovery work.
Clear responsibility boundaries can make changes easier to understand and check.
The review does not quantify these benefits.

## Findings from the initial review

### I1. Obsolete pytest classification and a different OpenCode rule

**Issue:** Copilot retains code that classifies targeted pytest commands, although its active command policy rejects pytest execution.
OpenCode still uses the targeted-test distinction.

**Evidence:** In [copilot_adapter.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_adapter.py), `command_denial` rejects pytest commands directly.
The reusable execution path does not call `is_repository_wide_pytest`.
Its helper chain includes test-path classification, option lists, a cache, and private pytest API inspection.

In [policy.ts](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/policy.ts), the command policy calls `isRepositoryWidePytest`.
That policy rejects repository-wide pytest commands but retains a targeted-test exception.
[AGENTS.md](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/AGENTS.md) prohibits direct execution of the human-owned test suite by PI sessions.

**Simplification:** Remove Copilot's unused pytest classifier and its helpers.
Align OpenCode with the direct-test prohibition.
Then remove OpenCode's unnecessary targeted-test classifier.

**Trade-off:** OpenCode loses its targeted-test exception.
The current contract does not authorize that exception.
Keep Runner validation available through the instrument contract.
Check the changed command decisions through Runner before adoption.

### I2. Obsolete training-log helpers and an identity budget function

**Issue:** Execution utilities retain an obsolete path for log names and parameters that do not affect the training budget.

**Evidence:** [execution.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/execution.py) contains `training_log_attempts`, `training_log_path`, `training_attempt`, and `training_records`.
The helper chain uses integer experiment numbers and names such as `experiment-N-attempt-N.log`.
The reusable Runner path instead uses operation identifiers and the current helpers in `paths.py`.
The reviewed production paths do not consume the obsolete helper chain or `latest_training_steps`.

The same module's `training_budget` discards three parameters and returns `standard_timesteps` unchanged.
Its caller, `_training_allocation` in [run_experiment.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/run_experiment.py), supplies those unused parameters.

**Simplification:** Remove the unused log helpers after a final consumer check.
Use the configured budget directly.
Remove the parameters that cannot change that budget.

**Trade-off:** These changes remove obsolete internal interfaces.
An undocumented external consumer remains outside the evidence of this review.
Preserve the current operation-based log format and continuation behavior.

### I3. The final evaluator computes diagnostics that its caller discards

**Issue:** The final evaluator calculates window diagnostics that do not affect its published result.

**Evidence:** In [final_benchmark.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/benchmark/final_benchmark.py), `_hold_progress` calculates the longest consecutive success interval.
It also scans windows to calculate `best_window_inside_steps` and `best_window_excess_cm`.
Its production caller, `evaluate_final_model`, consumes only `progress["success"]`.

**Simplification:** Retain the consecutive-success calculation.
Remove the discarded window calculations and unnecessary return fields.

**Trade-off:** The internal helper loses diagnostics that the reviewed caller does not expose.
Preserve the exact success threshold and required hold duration.
Keep the protected evaluator independent from scientific measurement code.
Do not infer a measured speed improvement from this source inspection.

## Findings from the second review

### A1. Several components independently interpret lifecycle rules

**Issue:** Runner, the launcher, the controller, and the brief contain separate interpretations of permitted lifecycle transitions.

**Evidence:** In [protocol.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/protocol.py), `validate_operation_request` enforces active transition rules.
In [run_research.ps1](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1), `Get-RequiredSessionSummaryTransition` separately determines when the session requires a checkpoint.
In [copilot_controller.ps1](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_controller.ps1), `Get-CopilotOperationState` exposes that launcher interpretation to Copilot.

In [build_brief.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/build_brief.py), `_session_lines` lists broad phase capabilities.
The brief warns that current transition rules can restrict those capabilities.
The list can include operations that Runner currently rejects.
For example, a goal-review session needs an opened inquiry before a checkpoint becomes valid.

**Simplification:** Have Runner derive the currently permitted operations and required transition.
Use those facts in the launcher, controller, and brief.
Retain operation validation at the acceptance boundary.

**Trade-off:** The change affects the interface between Runner and the launcher.
Check checkpoint requirements, inquiry caps, and resumed sessions.
Keep transport and process supervision separate from scientific lifecycle decisions.
Do not replace all launcher code with a new orchestration framework.

### A2. Ownership definitions differ across enforcement components

**Issue:** Independent ownership maps require coordinated changes and already classify some paths differently.

**Evidence:** [protocol.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/protocol.py) defines `RESEARCHER_OWNED_PREFIXES` as the broad `robot_learning/` prefix.
[copilot_adapter.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_adapter.py), [researcher_session.ps1](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_session.ps1), and [policy.ts](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/policy.ts) use narrower scopes.
Those scopes include scenario, training, laboratory, and specific entry-point files.

A new `robot_learning/extra.py` therefore receives different ownership classifications.
Finding I1 supplies another example of a shared restriction that differs between backends.
I1 and A2 overlap in policy maintenance, but they describe different changes.

**Simplification:** Align Runner's ownership scope with the documented paths.
Define shared ownership rules and restrictions in one small, fixed source.
Use that definition in each enforcement component.

**Trade-off:** Preserve separate permissions for preliminary sessions, main sessions, and coding children.
Preserve the intentional differences between Copilot and OpenCode tool interfaces.
Keep independent enforcement at each boundary.
Retain path normalization and protection against links or unauthorized targets.

### A3. Two mutable representations contain the same operation history

**Issue:** State and `results.jsonl` both contain event history, and separate code updates each representation.

**Evidence:** In [run_experiment.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/run_experiment.py), `_complete_operation` writes a history event before it updates `state.operation_events`.
`_persist_official_assessment_transition` updates state before it updates the JSONL event.
`replace_failed_operation` also coordinates separate writes.
In [repository.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/repository.py), `upsert_operation_event` maintains the JSONL representation independently.

In [campaign_report.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/tools/campaign_report.py), the report reader checks both representations.
The reader rejects differences in event order or content.
The current recovery stages address interruptions.
The duplication still creates an additional consistency obligation.

**Simplification:** Give history changes one update path.
Generate the second representation from that source at the current recovery and publication boundaries.
A conservative option retains events in operational state and generates the published JSONL history.
Preserve the JSONL format and its external role as authoritative evidence.

**Trade-off:** This recommendation needs the most careful implementation checks.
Preserve current histories, event identities, interrupted publication, and recovery behavior.
An interrupted export can still leave a temporary difference.
The benefit is a single source from which Runner can reconstruct the export.
Do not remove recovery stages or introduce a database merely to implement this change.

### A4. Acceptance discards checked plans and constructs them again

**Issue:** One acceptance pass calculates the same plan twice.
Persistence also contains another definition of request-shape rules.

**Evidence:** In [protocol.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/protocol.py), `validate_operation_request` invokes operation planners but returns only the operation kind.
In [run_experiment.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/run_experiment.py), `_new_pending_operation` then calls `_transaction_data`.
`_transaction_data` invokes the same planners again.
Some planners resolve artifact paths and calculate fingerprints.
The repetition therefore includes filesystem work.

In [repository.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/repository.py), `_validate_operation_request_shape` repeats required and permitted request fields.
That validator checks pending requests and completed historical requests.
Historical requests need shape checks that do not depend on the current lifecycle.

**Simplification:** Return the checked kind and plan from acceptance validation.
Use that plan to construct the pending operation.
Share request-shape checks that do not depend on lifecycle state.

**Trade-off:** Keep fresh validation between separate preflight and acceptance calls.
Keep integrity checks when execution occurs.
Keep distinct checks for historical records and new operations.
Do not reuse authorization across time or introduce a general schema framework.

### A5. A goal-review prompt repeats the same synthesis

**Issue:** Prompt assembly includes an identical scientific payload twice.

**Evidence:** In [run_research.ps1](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/run_research.ps1), `New-ScientificSessionPrompt` includes the previous synthesis in its handoff context.
For goal-review sessions, the prompt later repeats that synthesis under "Current scientific understanding".
Both sections use `checkpoint.current_synthesis`.

**Simplification:** Include the identical payload once in the assembled prompt.
Retain its source and the instructions to revise its interpretation.
Keep the brief available as durable context.

**Trade-off:** Previous-session synthesis and current inquiry synthesis can differ.
Retain both payloads when they express different information.
The source shows duplicate content, but the review does not establish an effect on scientific decisions.

## Additional findings on modules and functions

Size alone does not establish a god module or god function.
These findings use the responsibilities and shared state visible in the source.
The module findings provide stronger evidence for separation than the function findings.
A coordinator can legitimately connect several required stages.
Extract helpers only when the change clarifies ownership or reduces shared state.

### G1. The repository module combines several independent responsibilities

**Issue:** `repository.py` combines Git publication, stored-state validation, lifecycle updates, history presentation, and artifact management.
These responsibilities change for different reasons, but their implementations occupy the same module.
This is the strongest god-module finding.

**Evidence:** [repository.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/repository.py) implements `git`, `commit_paths`, and `publish_scientific_recipe`.
The same module defines state fields and validates pending requests, completed results, and the complete state.
It also implements `start_scientific_session`, `render_operation_log`, `publish_artifact`, and `archive_candidates`.
Those functions span publication policy, data contracts, lifecycle decisions, presentation, and filesystem changes.

**Simplification:** Separate stored-state validation and its field definitions as the first change.
Keep durable state writes and publication order explicit in their current coordinator.
Resolve duplicate history ownership from A3 before further changes to history storage.

**Trade-off:** A new module adds an import boundary.
The change has value only if that boundary separates responsibilities without circular imports or duplicate rules.
Preserve checks that connect state records to artifacts and completed events.
A change in file location alone does not resolve A3 or A4.

### G2. The Copilot adapter combines policy, presentation, and runtime supervision

**Issue:** `copilot_adapter.py` concentrates distinct concerns around the SDK integration.
Console presentation and permission rules share a module with coding-child supervision and operation submission.

**Evidence:** [copilot_adapter.py](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/copilot_adapter.py) defines console formatters and the `Console` class.
It also defines `is_pi_writable_path`, `command_denial`, scoped hooks, and read restrictions.
`ScientificCoding` manages child authorization, reports, changes, and cancellation.
`OperationSubmission` manages controller requests and waits.
`run` and `serve` manage SDK sessions and the persistent runtime.

**Simplification:** Separate Copilot console presentation from runtime supervision.
Resolve shared ownership rules from A2 before a separate change to permission policy.
Keep SDK-specific session and coding-child behavior in the adapter.

**Trade-off:** Event handling connects console output, usage accounting, and runtime state.
Preserve event order and the state that each handler requires.
Preserve independent authorization checks at each trust boundary.
Do not replace native backend behavior with a common provider framework.

### G3. Measurement execution mixes instrument work and transaction coordination

**Issue:** `execute_measurement` combines several substantial stages and their state in one function.
The function is a strong candidate for responsibility separation.

**Evidence:** [execute_measurement](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/runner/run_experiment.py:993) checks frozen contracts and source provenance.
It publishes scientific sources and laboratory tools when required.
It executes three instrument paths and seals module artifacts.
It validates recovered partial results and saves durable progress.

The same function verifies completed evidence and constructs paired comparisons.
It then updates candidate references and completes the operation.
Instrument-specific work, evidence assembly, and transaction coordination therefore share one control flow.

**Simplification:** Extract instrument execution into explicit helpers.
Extract paired-comparison construction into a separate helper.
Keep one coordinator responsible for stage order, partial-result persistence, interruption, and completion.

**Trade-off:** Preserve the exact durable boundaries between stages.
Preserve reuse of sealed artifacts and completed partial results after interruption.
Return explicit results from helpers.
Avoid additional hidden mutations.
Do not remove integrity checks to shorten the function.

### G4. OpenCode session execution mixes supervision and event presentation

**Issue:** OpenCode's `run` function combines session supervision with console events, permissions, and usage accounting.
Nested handlers share mutable state across these concerns.
The function is a strong candidate for responsibility separation.

**Evidence:** [run](C:/Users/cyril.beurier/code/robot-learning-inquiry-centered-lifecycle/researcher_opencode/src/adapter.ts:470) creates or connects to a server and resolves the session.
It manages stream subscription, reconnection, and checks of session completion.
Its nested `handleEvent` handles text, tools, permissions, file changes, usage, errors, and idle events.

The function also manages prompt submission, timeout, interruption, session abort, summary output, and shutdown.
Handlers share flags, completion promises, message positions, model identity, and console state.
That shared state makes the boundaries between supervision and presentation difficult to identify.

**Simplification:** Separate console event handling and usage accounting from session supervision.
Pass the required state explicitly.
Keep completion decisions, reconnection, cancellation, and cleanup under one supervisor.

**Trade-off:** Preserve stream subscription before prompt submission.
Preserve message baselines for resumed sessions and suppression of late output.
Keep permission handling active while the session runs.
Retain the distinction between timeout and an unknown session outcome.
An extraction that merely relocates the same shared state does not simplify the design.

## Complexity that serves explicit requirements

The broader review does not justify removal of these mechanisms merely because they contain substantial code:

| Mechanism | Required function |
|---|---|
| Backend-specific session handling | Preserve native Copilot behavior and the explicitly supported OpenCode interface. |
| Scoped coding children | Limit scientific edits to the authorized files and bounded context. |
| Interruption and publication recovery | Recover pending operations without blindly repeating execution. |
| Bounded evidence queries | Permit scoped inspection and complete retrieval without arbitrary code execution. |
| Frozen policy runtime and fingerprints | Bind evaluation to the saved artifact and its executable behavior. |
| Independent protected evaluators | Preserve fixed task-reference and final-evaluation contracts. |
| Recoverable reset backups | Preserve ignored measurements and support repair after interruption. |

These requirements justify distinct checks at different trust boundaries.
The findings concern repeated rules, repeated work, and excessive concentration of responsibilities.
They do not establish that all repeated checks are unnecessary.
Required behavior does not justify every current module or function boundary.

## Recommended order

1. Align ownership rules and remove the obsolete pytest classifiers.
2. Remove obsolete log helpers, unused budget parameters, and discarded final-evaluation diagnostics.
3. Derive effective lifecycle permissions in Runner.
4. Reuse checked plans within one acceptance pass.
5. Remove identical prompt payloads.
6. Consolidate history updates as a separate change.
7. Separate stored-state validation from repository operations.
8. Separate Copilot presentation and policy after shared rules have one definition.
9. Separate measurement instrument work and comparison construction from transaction coordination.
10. Separate OpenCode event presentation and accounting from session supervision.

Use the current Runner validation for each affected behavior.
Keep checks proportional to each change.
Require interruption and publication checks before adoption of the history change.
Check stage order and cancellation behavior after changes to coordinator boundaries.
Avoid duplicate helpers when architectural changes already address the same responsibility.
The review does not require a new framework, a new backend abstraction, or a repository-wide rewrite.

**SIMPLIFY.** Remove repeated responsibility and clarify boundaries around concentrated responsibilities.
Preserve required behavior, ownership enforcement, artifact integrity, and recovery.
