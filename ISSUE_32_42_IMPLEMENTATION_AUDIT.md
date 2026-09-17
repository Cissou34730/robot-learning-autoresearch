# Issues 32-42 Implementation Audit

**Date:** 2026-09-17  
**Repository:** `Cissou34730/robot-learning-autoresearch`  
**Audited implementation ref:** `issue-33-42-decision-quality` (`fd5ab9324bae10cd8490902cc5463188fc007516`)  
**Comparison base:** `master` / merge base `ecc9fb97e04ee5d77eb7e9eb28bf7c2d334c047c`

## Scope and method

This audit reviewed the original GitHub issue bodies and all post-development comments for issues [#32](https://github.com/Cissou34730/robot-learning-autoresearch/issues/32) through [#42](https://github.com/Cissou34730/robot-learning-autoresearch/issues/42). It then inspected the named implementation commits and the final state of `issue-33-42-decision-quality` using read-only Git operations.

Issue #32 was described as implemented on `issue-30-decision-quality-remediation`, but both named commits (`f2cfc1c`, `11a09c8`) are ancestors of the audited branch. It is therefore present in the final audited state.

This was a static review. Tests and linters were not rerun. Existing test code and the validation claims in issue comments were reviewed, but those claims were not independently executed.

## Executive assessment

The work is directionally strong and several changes solve their root cause rather than masking symptoms. The best implementations are #35, #36, #38, and #42. They establish clearer ownership, separate training-only behavior from evaluation semantics, neutralize instrument presentation, and restore development/final-panel independence.

The branch is not ready to be described as completing issues 32-42:

- **#34 is knowingly incorrect in the exact metric the issue exists to expose.** It can report repeated fixed-panel confirmation as zero repeated coverage.
- **#37 is a useful advisory prototype, not a completed stopping policy.** It cannot establish that evidence was measured after designation or predeclared for stopping validation.
- **#39 preserves round provenance well for newly executed measurements, but reused measurements are not linked into the round that relied on them.**
- **#41 implements only the low-risk subset.** Ownership remains registry-based and the phase machine remains split across PowerShell and Python.
- **#33 records that v4 already behaves as three phases; it does not perform the requested consolidation.** This is a defensible scope correction, but should be reported as verification/reclassification rather than implementation.

Overall status:

- Complete or effectively complete: **#32, #36, #38, #40, #42**
- Mostly complete with a bounded correction/decision: **#35, #39**
- Partial or pilot-only: **#33, #37, #41**
- Defective and requiring correction: **#34**

## Findings

### 1. High: #34 reports campaign episode coverage incorrectly

`research/build_research_brief.py::_v4_cost_accounting_section` computes campaign coverage by summing each candidate's already-deduplicated summary:

```text
distinct_episodes += summary["episodes"]
episode_executions += summary["episode_executions"]
repeated_episodes += summary["repeated_episodes"]
```

Those summaries deduplicate only within one model. If five models are evaluated on the same 160 deterministic episode identities, the section reports 800 distinct, 800 executions, and 0 repeated instead of 160 distinct, 800 executions, and 640 repeated. Task-reference executions are counted, but task-reference distinct/repeated coverage is not reported at all.

The implementation comment correctly admits this defect. The problem is not a minor limitation: repeated confirmation visibility is the main purpose of #34, so the known defect defeats the issue's expected benefit and creates false reassurance.

The test `test_cost_accounting_counts_repeated_rounds_and_coverage_separately` supplies a precomputed single-candidate summary and asserts it. It never constructs two models sharing the same panel identities, so it cannot detect the campaign-level error.

**Required correction**

Compute coverage from recorded episode identities across the campaign, separately by instrument:

- `research_evaluation`: `(evaluation_semantics, episode_seed)`
- `task_reference`: `(panel_id, episode_seed)`

For each instrument report `distinct = len(unique identities)`, `executions = total episode executions`, and `repeated = executions - distinct`. Add tests with multiple models and rounds reusing the same panel, overlapping research panels, and repeated task-reference execution.

**Relevant implementation:** commit `e89055c`; `research/build_research_brief.py:1049-1137`; `tests/autoresearch/test_brief_sections.py:202-245`.

### 2. High: #37 confuses model origin with best-known designation

`research/stopping_policy.py::assess_terminal_readiness` uses `best_known["origin_experiment"]` as the designation boundary and classifies any later, seed-disjoint research evaluation as a fresh stopping-validation panel.

Origin and designation are not the same event. A model trained in experiment 1 can be designated `best_known` during a later closure. A seed-disjoint measurement from experiment 2 may therefore predate the designation but still be classified as post-designation stopping evidence.

The written contract requires the panel to be measured after designation and declared before observing its result. The current state records neither a designation event/ordinal nor a request purpose. Consequently the deterministic code infers scientific intent from chronology and seeds, despite the contract identifying predeclaration as part of the definition.

The post-development comment accurately discloses that freshness is inferred and proposes `purpose: selection | terminal_validation`, but it understates the designation error: the code does not have a designation timestamp and substitutes `origin_experiment`.

**Required correction**

- Persist the experiment/closure ordinal at which `best_known` was designated.
- Add an explicit optional measurement purpose to the accepted request and immutable round record.
- Treat only a predeclared `terminal_validation` panel executed after the designation event as stopping-validation evidence.
- Preserve the current seed-disjointness check against every earlier measurement of the same artifact.
- Use recorded integer successes or detailed episode outcomes rather than reconstructing successes from floating-point `success_percent`.

**Relevant implementation:** commit `f0b16c0`; `research/stopping_policy.py:53-132`; `research/stopping_contract.md:17-52`; `tests/autoresearch/test_stopping_policy.py:59-101`.

### 3. Medium: #37 is an advisory pilot without prospective validation

The Wilson lower-bound implementation is present and coherent. The contract clearly states the 80% one-sided confidence choice, its false-terminal/delayed-terminal tradeoff, and that the result neither blocks nor authorizes terminal assessment.

However, no prospective validation was performed, task-reference reuse is not surfaced by the assessment, and the fresh-panel source remains implicit. The branch also changes `research/program.md` from no fresh-panel requirement to saying such a panel is "expected." That wording will influence Researcher behavior before the policy has been shown non-pathological, even though it remains non-blocking in code.

This is acceptable as staged research, but not as completion of #37's rollout. The issue should remain open or be split into "advisory prototype" and "prospective validation/activation" work.

**Required correction before blocking use**

- Run and document prospective validation on new campaigns or a predeclared simulation study.
- Justify or revise the 80% confidence tradeoff using that evidence.
- Explicitly state that the fixed task-reference panel is selection/diagnostic evidence and cannot satisfy freshness.
- Decide whether fresh research-evaluation seeds are the canonical stopping source or whether a second protected panel is required.

### 4. Medium: #39 does not link reused evidence to the round that requested it

The round implementation has good restart properties:

- it persists the accepted request before execution;
- it freezes and rechecks model fingerprints;
- it saves each newly completed measurement immediately;
- it resumes without repeating completed measurement identities;
- it keeps ordered round metadata in pending and durable results.

The remaining gap occurs when a requested measurement is already present in the accumulated ledger. The executor prints `already complete; reusing` and skips it. Because result references are appended to the active round only after a new execution, the current round records the requested operation under `measurements` but has no corresponding result/artifact reference under `results`.

This means the durable round cannot fully answer which prior artifact satisfied the request. It also makes "requested," "executed," and "reused" impossible to distinguish from the round record alone. The implementation comment admits that skipped/reused measurements are not re-added, but that behavior conflicts with the acceptance criterion requiring resulting measurement and artifact references for each round.

**Required correction**

For each requested operation, persist a resolution record with a status such as `executed`, `reused`, or `failed`. A reused record should link the existing artifact/fingerprint and its source round without incrementing execution cost. Keep execution accounting based only on `executed` records.

**Relevant implementation:** commit `c04da0d`; `research/run_experiment.py:577-621`, `729-871`, `923-929`; `research/runner_repository.py:331-354`.

### 5. Medium: #41 leaves its two architectural causes in place

The delivered subset is useful:

- the v4 brief was split into independently testable section builders;
- explicit path classifications gained an existence guard;
- dead re-export shims and the unclassified throughput probe were removed.

The two central structural changes were deferred:

- protected scenario files were not moved out of the researcher-owned prefix, so ownership is still determined by a registry plus exceptions;
- the phase machine remains in `run_research.ps1`, split from Python validators, schemas, sandbox rules, and prose.

The implementation comment is transparent about this. The issue nevertheless cannot be considered complete, because the root causes in its title and findings 1 and 4 remain unchanged. The existence guard reduces one failure mode but does not make ownership derivable from location.

Retaining `tests/scenario/` and `tests/training/` as protected prefixes is a reasonable deviation: they actively prevent recreating retired researcher-owned test domains. The code comment now states that purpose.

**Required correction**

At a planned campaign boundary, complete or explicitly split the deferred work:

1. Move protected scenario adapters out of the researcher-editable directory and reduce exception-based ownership rules.
2. Move phase orchestration into a Runner module and leave PowerShell as a thin launcher.
3. Update reset, sandbox, documentation, and architecture guards atomically.
4. Treat evaluation-semantics/path-identity migration as an explicit compatibility event.

**Relevant implementation:** commits `ac3b69e`, `b20dc86`; `research/runner_protocol.py:45-108`, `172-226`; `run_research.ps1:328-445`.

### 6. Medium: #35 protects more than the established correctness invariant

Moving deterministic episode identity, duplicate coverage handling, and conflicting-outcome rejection to `robot_learning/paired_evidence.py` is the right root-cause fix. Recipe restoration can no longer reintroduce the known shared-episode defect, and the placement avoids forbidden benchmark/scenario dependency directions.

The move also protects `exact_mcnemar_pvalue` and the complete comparison output. The issue's rationale establishes episode pairing as a correctness property, but does not independently establish that the choice of statistical comparison is human-owned rather than a scientific instrument the Researcher may modify. The implementation comment acknowledges this consequence without resolving the ownership decision.

**Required decision**

Either document that the exact McNemar statistic is part of the human-owned measurement contract, or protect only episode identity/conflict reconciliation and keep the choice of downstream statistic in a researcher-owned wrapper. This is an ownership decision, not evidence that the current statistic is mathematically wrong.

**Relevant implementation:** commit `c20ab00`; `robot_learning/paired_evidence.py:16-71`; `research/runner_protocol.py:52-58`; `tests/autoresearch/test_paired_evidence_restoration.py`.

### 7. Low: #33 verifies a scope correction rather than implementing consolidation

The branch establishes that normal schema-v4 flow exposes three Researcher sessions:

- experiment design (`new hypothesis`);
- investigation (`post-training analysis`), including optional measurement rounds;
- closure (`lineage decision`).

The separate evaluation-design block remains for legacy `pending_evaluation_request` state. Therefore the issue's premise that v4 still has four active phases appears stale. Avoiding a phase-machine rewrite under an issue that explicitly prohibited schema/state/transition changes is reasonable.

Still, commit `50049ae` changes only documentation and a source-text test. The test checks that phase strings and branch snippets exist; it does not execute the state machine or prove that a schema-v4 state cannot reach the legacy branch. The work should be described as "verified/reclassified" rather than "implemented."

**Recommended correction**

Replace or supplement the text test with a state-transition test proving the three schema-v4 phase paths and legacy-only reachability. Keep full removal of the legacy phase coupled to #41's phase-machine migration.

### 8. Low: #42 meets the functional goal but lacks one explicit compatibility test

The implementation changes research-evaluation defaults to seed 4200 and 160 episodes, while the official panel remains seed 1000 and 200 episodes. Both the Runner and CLI consume the shared research defaults. The guard checks tuple inequality, independent seed and episode counts, and sampled target-sequence inequality. The official and task-reference contracts are unchanged.

This satisfies the core issue. The only acceptance item not directly pinned by the new test is that an explicit request for seed 1000 remains accepted and executes unchanged. No validator was tightened, so static review found no behavioral regression, but a focused protocol test would make the compatibility promise durable.

The change does not make the official panel secret: the constants remain readable and a cooperative Researcher can request seed 1000. The issue and implementation comment correctly acknowledge that limitation.

### 9. Low: branch composition makes review and integration unnecessarily risky

The audited ref contains the issue commits, campaign resets, scientific-recipe commits, retained model artifacts, evaluation artifacts, and campaign-state changes in one long history. This is consistent with the repository's campaign persistence model, but it makes a wholesale merge difficult to review and can couple harness remediation to campaign state.

**Recommended correction**

Prepare an integration branch containing the reviewed harness commits and only the campaign/provenance changes intentionally required by repository policy. At minimum, document which non-issue commits are expected to merge. Do not blindly cherry-pick #34 until its coverage defect is corrected; coordinate #37 and #39 schema additions so measurement purpose and designation provenance are introduced once.

## Per-issue review

### #32 - Three-candidate cap reads as a quota

**Expected:** Make the cap visibly an upper bound, keep measurement optional, and validate smaller requests as complete.  
**Done:** Removed repeated quota-like framing; final instrument text says the limit is an execution ceiling, one/two-model requests are complete when sufficient, and the cap applies per request.  
**Assessment:** Complete. The final wording is stronger and clearer than the first implementation comment.  
**Benefit realized:** Lower prompt pressure toward routinely evaluating three candidates and clearer cost-sensitive Researcher discretion.

### #33 - Consolidate prompts to three phases

**Expected:** Fold the extra phase into Investigation or Experiment design without changing schemas, states, or transitions.  
**Done:** Documented and text-tested that v4 already uses three Researcher sessions; retained the schema-v3 compatibility branch.  
**Assessment:** Scope-corrected verification, not a substantive implementation. The deviation is defensible, but the test is structural text matching rather than behavioral validation.  
**Benefit realized:** Clearer lifecycle documentation and protection against casually reintroducing a fourth normal v4 session.

### #34 - Replication/confirmation cost visibility

**Expected:** Accurate factual training and evaluation cost, including campaign-level distinct and repeated episode coverage per instrument.  
**Done:** Added training steps, explicit replication indices, round/execution totals, and a research coverage line.  
**Assessment:** Defective. The coverage line is wrong across models and omits task-reference distinct/repeated coverage.  
**Benefit realized:** Experiment, step, replication, round, and gross execution counts are useful; the central reuse metric is not trustworthy.

### #35 - Shared-episode fix reverted by reset

**Expected:** Decide whether pairing is protected correctness or reset-carried science, then prevent resets from reintroducing the defect.  
**Done:** Moved pairing/accounting to protected `robot_learning/paired_evidence.py`, rewired consumers, and added restoration/boundary tests.  
**Assessment:** Mostly complete and technically strong. The protected scope of the statistical test itself needs an explicit ownership decision.  
**Benefit realized:** Shared-episode correctness and conflict rejection now survive recipe restoration.

### #36 - Separate training-only environment setup

**Expected:** Move training-only target distribution and `make_training_env()` out of shared evaluation semantics without changing behavior.  
**Done:** Added `scenario/training_environment.py`, moved the constant/factory, updated importers, and added boundary tests.  
**Assessment:** Complete. Later deletion of the temporary throughput probe does not undermine the final boundary.  
**Benefit realized:** Training-distribution changes no longer invalidate otherwise compatible evaluation evidence.

### #37 - Terminal-readiness evidence and stopping policy

**Expected:** Written assumptions/tradeoffs, deterministic uncertainty-aware implementation, focused tests, retrospective diagnostics without overfit, and prospective validation before blocking.  
**Done:** Added an advisory Wilson-bound assessment and contract, updated brief/program wording, and added focused tests.  
**Assessment:** Partial pilot. Statistics exist, but purpose is not declared, designation time is not recorded, task-reference reuse is not surfaced, and no prospective validation exists.  
**Benefit realized:** Selection panels are no longer presented as sufficient terminal evidence, and uncertainty is made explicit; the assessment is not yet reliable enough to enforce.

### #38 - Task-reference presentation bias

**Expected:** Equal factual depth and prominence for both instruments without defaults or recommendations.  
**Done:** Added parallel sections with identical categories: ownership, settings, measured task, outputs, and artifact semantics; added neutrality tests.  
**Assessment:** Complete. Different output capabilities are factual distinctions, not presentation asymmetry.  
**Benefit realized:** Researchers receive useful capability information without systematic prompt pressure toward or away from task reference.

### #39 - Evaluation-round provenance

**Expected:** Ordered immutable requests and results across state, closure, and restart, with question/reason/selections/comparisons/artifacts.  
**Done:** Added ordered round records before execution, per-measurement persistence, artifact canonicalization, brief sections, closure copy, and interruption tests.  
**Assessment:** Mostly complete. Reused evidence is not linked to the round that relied on it, so request resolution is incomplete.  
**Benefit realized:** Newly executed multi-round investigations are auditable and restart-safe without reconstructing purpose from timestamps.

### #40 - Optional researcher-owned tests

**Expected:** Researcher source changes run only protected boundary checks; researcher tests are optional; protected/unclassified changes retain full validation.  
**Done:** Verified existing routing, strengthened Researcher wording, documented policy, and retained retired test prefixes as smuggling guards.  
**Assessment:** Complete as verification/close-out. Keeping the prefixes is justified and better than the audit note's proposed deletion.  
**Benefit realized:** Scientific iteration avoids mandatory maintenance of method-specific tests without weakening architecture or task guards.

### #41 - Structural ownership and lifecycle cleanup

**Expected:** Location-derived ownership, brief seams, phase machine in Runner, and bounded housekeeping.  
**Done:** Brief seams, explicit-path existence guard, dead-shim/probe removal; deferred ownership relocation and phase extraction.  
**Assessment:** Partial. Useful enabling work landed, but the issue's root structural properties remain.  
**Benefit realized:** Presentation changes are easier to review/test and one registry-drift mode now fails in validation.

### #42 - Research panel equals official panel

**Expected:** Decouple defaults, prove panel/target independence, preserve explicit seeds and official/reference contracts.  
**Done:** Set research defaults to 4200/160, shared by Runner and CLI; added tuple/value/target-sequence guards.  
**Assessment:** Complete with a small explicit-seed compatibility test gap.  
**Benefit realized:** Default development evaluation no longer reproduces the official verdict panel.

## Required change sequence

1. **Fix #34 before merge or decision use.** Campaign coverage must be recomputed from episode identities per instrument.
2. **Extend #39 round records with operation resolution.** Link reused evidence without counting it as a new execution.
3. **Add designation provenance and declared measurement purpose for #37.** This should be one additive state/round schema change coordinated with #39.
4. **Keep #37 advisory while collecting prospective evidence.** Do not make it blocking or stronger in prompt wording until validated.
5. **Decide the ownership of the McNemar statistic in #35.** Keep pairing invariants protected either way.
6. **Split and schedule #41's deferred architecture at a campaign boundary.** Ownership relocation and phase migration need explicit compatibility planning.
7. **Strengthen focused tests.** Add cross-model/panel cost cases, reused-round linkage, designation-versus-origin cases, behavioral phase reachability, and explicit seed-1000 compatibility.

## Consolidated table

| Issue | What it was about | Expected benefit | What was done | What needs correction |
| --- | --- | --- | --- | --- |
| #32 | Three-model ceiling behaved like a quota | Fewer unnecessary evaluations; cap remains per-request only | Neutralized framing; explicitly says ceiling, not target; one/two models valid | No material correction |
| #33 | Four-phase prompt structure versus three intended Researcher phases | Co-locate investigation/measurement reasoning and simplify lifecycle | Documented that v4 already has three sessions; retained legacy v3 evaluation-design path | Describe as verification, add behavioral reachability test, remove legacy path only with #41 migration |
| #34 | Invisible replication and repeated evaluation cost | Factual view of exploration/confirmation resource use | Added training/step/replication/round/execution totals and coverage line | Recompute campaign identities across models; add task-reference distinct/repeated coverage; replace tests that encode candidate-local summaries |
| #35 | Reset could restore broken shared-episode comparison logic | Pairing correctness survives recipe restoration | Moved comparison/accounting to protected module and added guards | Decide whether the McNemar statistic itself should be protected or researcher-owned |
| #36 | Training-only distribution polluted evaluation semantics | Training curricula can change without invalidating completed evidence | Moved training factory/range to `training_environment.py`; updated callers/tests | No material correction |
| #37 | No uncertainty-aware stopping evidence | Reduce premature terminal requests without an LLM gate | Added advisory Wilson contract, deterministic assessment, brief/program presentation | Record designation time and declared purpose; handle task-reference status; prospectively validate before enforcement |
| #38 | Task reference was more salient than research evaluation | Neutral instrument choice with useful facts retained | Parallel five-category documentation and neutrality tests | No material correction; observe future campaigns prospectively |
| #39 | Multi-round purpose/order disappeared after flattening | Auditable, restart-safe iterative measurement | Persisted ordered rounds, request metadata, new result refs, comparisons, and closure records | Link reused/skipped operations to source artifacts and distinguish requested/executed/reused |
| #40 | Researcher tests were a campaign completion burden | Lower scientific iteration overhead without weakening protected checks | Verified routing, strengthened optional-test wording, retained smuggling guards | No material correction |
| #41 | Ownership/phase boundaries encoded in registries and mixed files | Structural enforcement, lower drift, easier presentation work | Brief section seams, explicit-path guard, dead-code cleanup | Complete location-derived ownership and Runner-owned phase machine at campaign boundary |
| #42 | Default development panel reproduced official benchmark | Restore practical holdout independence | Changed defaults to 4200/160; guarded values and sampled target sequence | Add explicit seed-1000 request compatibility test; do not claim secrecy |

## Final quality judgment

The implementation demonstrates good local engineering judgment and unusually candid post-development comments. That candor makes the remaining defects easier to find, but disclosure is not completion. The branch should be treated as a strong partial remediation set, not as a closed 32-42 package.

The minimum acceptance bar is to correct #34 and link reused evidence in #39. The next coherent design step is a single provenance extension for #37 that records best-known designation and predeclared measurement purpose. #41's deferred architecture should be separated from those correctness fixes and executed only at an explicit campaign boundary.