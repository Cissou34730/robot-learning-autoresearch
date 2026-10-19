# Campaign 79395c88: independent campaign and harness RCA

Date: 2026-10-09. Campaign: `79395c88-afcd-40f0-a644-16ca95368c28`.

## Finding and recommendation

This campaign spent substantially more resources than the earlier capped campaign without establishing a goal-qualified learned policy. Its central failure was weak accumulation of decision-changing knowledge across interventions. Several experiments established that a particular candidate was worse; their conclusions then nominated another method without resolving the explanation that was supposed to guide that choice. Later, an intended method was assessed using a different implementation, an inquiry opened on evidence already sufficient for its closure, and the final handoff incorrectly declared available diagnostics missing.

**OI-016 was insufficient, but this campaign does not establish that OI-016 caused the poor policies or increased campaign cost.** Its operation-neutral wording was present. Startup began with a physical measurement. Inquiry work included a controller capability probe, measurement-only work, nonterminal checkpoint selection, and a four-training inquiry. The campaign was not mechanically forced into one training per inquiry.

The strongest remediation is to make durable scientific state easier to correct and evidence easier to inspect, while simplifying OI-016's repeated process instructions. Preserve bounded closure, scientific freedom, and the Runner's mechanical role. Do not impose measurement-first, prohibit method-specific inquiries, require a complete causal answer before closure, or increase the inquiry cap as the primary fix.

This report proposes changes; it does not implement them. All analysis used existing artifacts and read-only source/history inspection. No campaign operation was executed, no PI-owned file was written, and no analysis script was stored.

## Evidence and version control

Primary evidence:

- `campaigns/results.jsonl`: 114 records; operation IDs and one-based source lines are cited below.
- Completed measurement artifacts under `campaigns/evaluations/79395c88-afcd-40f0-a644-16ca95368c28/`.
- Candidate parameter files, saved-component comparisons, and scientific recipe commits recorded by completed training operations.
- `runner/state/research_state.json`, `campaigns/brief.md`, and `reports/session_usage/79395c88-afcd-40f0-a644-16ca95368c28.jsonl` for lifecycle state, durable claims, and runtime metadata.

The final campaign evidence is preserved at Git revision `2638849`. Later revision `961916c` adds the existing `docs/oi016_post_campaign_rca_20261009.md`; that report is a secondary interpretation, not the factual basis of this RCA.

The campaign started at 13:17:45 UTC from base `4e87f6053469bb6648d355bc03a7a70faa91f33f`, whose parent is OI-016 commit `e0ffcd8`. The base restored scientific recipe `8256c8c7705a5080a722453b26eb13cd85b6e18f`. The preliminary scientific model was published at `594a6d7`. The reviewed harness source and contracts have no delta between the campaign base and final checkout. Thus the restoration was present; an obsolete version of the reviewed prompt is not supported as the explanation.

All 117 recorded runtime invocations used `gpt-5.6-luna` with `high` reasoning. The nearby campaigns `896c230a` and `81a5458d` used the same model/reasoning and restored recipe source. These control some background differences, but their scientific decisions, training seeds, panels and campaign lengths differ. They are not controlled prompt ablations. Source provenance establishes what code was available; it does not provide a counterfactual campaign outcome.

## Outcome and resource accounting

| Measure | Latest campaign | Earlier capped campaign `1ae27a27` |
|---|---:|---:|
| Inquiries opened and closed | 15 | 15 |
| Completed training operations | 17 | 14 |
| Failed training operations | 0 | 3 |
| Requested steps in completed training | 2,040,000 | 1,680,000 |
| Actual steps in completed training | 2,053,312 | 1,691,648 |
| Completed measurement operations | 27 | 19 |
| Failed measurement operations | 3 | 9 |
| Elapsed start to final checkpoint | 4 h 39 min 44 s | 2 h 44 min 55 s |
| Protected assessment | None | None |

Historical counts come from `021ff566` for `1ae27a27`. Requested/completed step totals exclude failed training attempts; they are not total compute consumed by those failures. The latest campaign used 21.4% more completed training allocations and 42.1% more completed measurements. Its start-to-final-checkpoint duration was about 69.6% longer. These timestamps include different startup durations, so they differ from measurement-to-checkpoint durations in the existing OI-016 report.

All 17 training operations requested the full 120,000-step inquiry allocation. Sixteen PPO runs completed 120,832 steps; SAC completed 120,000. This matches the existing allocation/rollout rule. It is not an OI-016 budget change.

The 27 completed measurement operations contain 40 research evaluations and 18 Python-module measurements. Counting only M-operation IDs understates the amount of evidence produced.

T1 achieved 150/160 on seed panel 4200. T8/T9/T10 nominated checkpoints achieved 153/160 on that panel. Later T15 achieved 156/160 on panel 4800 but 190/200 on panel 5000. T16 achieved 192/200 on panel 5200. T17 achieved 168/200 on panel 5400, against T1's 192/200 on the same panel, losing all 24 discordant episodes.

The last trained candidate was substantially worse than its paired reference. That does not mean the campaign lost access to its better archived candidates. No working or best-known role was assigned. No official assessment occurred, and the terminal campaign state remained unset: the launcher reached the completed inquiry boundary at its cap. It did not establish scientific exhaustion or official failure.

## Inquiry-by-inquiry reconstruction

Here “training first” means first completed training/measurement operation, excluding recipe restoration. Twelve inquiries fit that definition; I9 and I12 began with measurement, and I13 had no new training/measurement. Five of the twelve performed recipe restoration before training, so 12/15 is not a count of literal first protocol actions.

| Scope | Completed scientific operations | Evidence and resulting decision |
|---|---|---|
| Startup | M1 | Compiled dynamics, action responses and IK feasibility. Established a physical basis before training. |
| I1 | T1, M2–M3 | Full-distribution PPO: 150/160; seven failures before first reach, three after. Redirected toward branch/limit coverage. |
| I2 | T2, M4–M5 | Altered sampling: 52/160; 104/108 failures before first reach. Rejected the recipe and selected representation work. |
| I3 | T3, M6 | Explicit margin/feasibility features: 30/160; 129/130 failures before first reach. Selected stabilization/history work. |
| I4 | T4, M7 | Previous-action history: 73/160; 86/87 failures before first reach. Returned to branch/trajectory work. |
| I5 | T5, M8–M9 | Endpoint-velocity features: 107/160 and 108/160 for two checkpoints. Selected action/control work. |
| I6 | T6, M10 | Action slew limit: 17/160 nonterminal, 11/160 terminal. Selected a more selective action modification. |
| I7 | T7, M11 | Joint-limit guard: 30/160. Returned to policy-side learning. |
| I8 | T8, M12–M13, T9, M14 | Continued PPO improved to 153/160. Stabilization reward also measured 153/160; failure-mode differences were recorded. |
| I9 | M17, T10, M18 | Same-interface computed torque reached 160/160 at three gain settings. PPO with an expert-action reward penalty stayed at 153/160. |
| I10 | T11, M19–M20 | Coupled phase/history/trajectory observation: 0/160; 150 failures before first reach. |
| I11 | T12, M21 | Static branch/limit-conditioned observation: 44/160; 103/116 failures before first reach. Selected controller imitation. |
| I12 | M22 | Diagnosed existing T10, still 153/160. Closed as a controller-imitation negative despite no direct supervised-imitation experiment. |
| I13 | None | Opened and closed on previously completed T11/T12 evidence. |
| I14 | T13–T16, M23–M28 | Multiple observation/horizon variants within one inquiry, including a checkpoint between operations. T15/T16 recovered near-baseline performance but did not establish the goal. |
| I15 | T17, M30 | SAC: 168/200 versus paired T1 192/200. Closed while optimization-versus-representation remained unresolved. |

M15 and M16 failed on MuJoCo API usage before M17 succeeded. M29 failed on SAC policy loading before M30 succeeded. These failures are execution history, not scientific negative results. They were corrected and do not explain the full plateau.

## Root-cause findings

### 1. Inquiry closure became coupled to switching recipes

**Observed; causal contribution to inquiry consumption is strong.** I2–I7 repeatedly opened a method-oriented question, tested one recipe, measured a substantial regression, closed with a limited negative, and opened another method-oriented question. The same acquisition-versus-stabilization uncertainty survived. I3–I5 visibly alternated between representation and stabilization routes without resolving why the new representations were difficult to learn.

Limited-negative closure is legitimate. A method-specific question is also legitimate: developing a method is scientific work. The defect is not that every broad question remained unresolved. It is that the opening evidence boundary often amounted to “reach the campaign threshold or produce failures that redirect us,” making nearly any completed candidate evaluation sufficient for closure. The inquiry increasingly tracked the selected recipe rather than a deliberately bounded increment of understanding or capability.

I13 makes the duplication concrete. E54 opened the inquiry at source line 88; E56 closed it at line 90 using T11/M19–M20 and T12/M21, all available before opening. No new training or measurement intervened. Reinterpretation of existing evidence can be useful, and no-operation closure can prevent waste. Here, however, the opening rationale already cited that evidence. The goal-review/open/checkpoint/close/checkpoint sequence did not need a new campaign experiment to establish its eventual conclusion.

The harness already allows multiple operations, checkpoint continuation, and reframing. I14 exercised multi-operation continuation; no inquiry used the reframe operation. Consequently, “add support for several operations” would not address the actual problem. Neither would requiring inquiries to stay open until their broad question is fully answered: that would recreate OI-002 and conflict with bounded work.

### 2. Durable handoff gives provisional decisions excessive authority

**Observed restrictive wording; contribution to persistence is plausible, not experimentally isolated.** `contracts/program.md:207` requires an exact next question; lines 214 onward say the next context continues the same scientific state and changes its conclusion/question only after new evidence, an implementation finding, or a concrete dead end. `run_research.ps1:789` onward reinforces the conclusion and question verbatim.

Preserving evidence across fresh sessions is useful. But a fresh review can discover that an old conclusion was unsupported by evidence already available. It should not need a new event to reconsider it. The present wording gives inherited interpretation and inherited facts similar authority.

Examples of resulting commitments include E41's direction to prioritize phase/history acquisition, E49's controller-imitation direction, E57's instruction to open the exact next question, and E63's requirement to retain the direct-action interface. OI-016 adds “not a commitment” warnings alongside those durable directions; it does not remove their practical influence.

The direct-action restriction and complete inner-band preservation requirement were PI-selected research constraints, not immutable requirements of `contracts/scenario.md`. They may be useful experimental controls. Repeated handoff treated them increasingly like continuing obligations. The harness should preserve their provenance and revisability, not select a different control method on the PI's behalf.

### 3. An intended method was substituted for the implemented experiment

**Established implementation/interpretation mismatch.** T10's request described a controller-derived action prior. Scientific commit `3df27c98e94daac42a10116344ea9e87c589f1e3` adds:

- calculation of the computed-torque expert action before the transition;
- a reward term `-0.1 * sum((action - expert_action)^2)`;
- ordinary PPO transfer from `T8:checkpoint-60416`.

This is expert-action reward shaping. There is no added supervised action-regression training loop in that delta. T10's own request accurately describes the penalty.

E50/I12 instead asks whether “controller-imitation training” transfers the demonstrated capability and calls direct imitation the proposed capability test. Its only new operation, M22, replays the existing T10 policy. E52 then closes the controller-imitation inquiry using that policy's 153/160 result.

Reward shaping can be part of an imitation approach, but this evidence does not test the distinct direct-supervision route invoked by I12's reasoning. The report should name the implemented PPO reward-shaping recipe, retain direct supervised acquisition as untested, and let the PI decide whether it is worth pursuing. No harness rule should mandate that method.

OI-015's hashes cannot catch this semantic substitution. Different serialized policies establish neither implementation of the intended method nor discrimination of its scientific explanation.

### 4. Available evidence was incorrectly carried forward as missing

**Established recurrence of the OI-003 defect.** E66 and E67 say M30 does not expose nearest-branch limit margins for unreached failures. The completed artifact does expose them:

`evaluation-79395c88-afcd-40f0-a644-16ca95368c28-m30-T17-checkpoint-120000-200ep-seed5400-e6e1ee979b3f.json`

The relevant field is:

`research_evidence.episode_diagnostics[*].terminal_state.ik.nearest_branch_limit_margin_rad`

Recounting the completed records, joined to their episode outcomes:

| M30 candidate | Failures before first reach | Positive nearest-branch margin | Negative nearest-branch margin | Failures after first reach |
|---|---:|---:|---:|---:|
| T17 SAC | 23 | 15 | 8 | 9 |
| T1 reference | 4 | 0 | 4 | 4 |

For example, seed 5412 never reached tolerance and records a nearest-branch margin of `1.5989007624860698` radians. This is directly accessible completed evidence, not inferred from source code. M30's artifact inventory also lists `terminal_state`; it is not marked truncated.

The correction establishes that positive-margin non-reaching occurs in the tested SAC policy and distinguishes it from the paired T1 residual. It does **not** establish whether optimization, representation, reward, or another factor caused it. A nearest-analytic-branch margin is also not the actual joint-limit margin or a proof that the entire trajectory is feasible. Those quantities must remain distinct.

The existing “mechanism unresolved” qualification was appropriately cautious, but its stated reason—missing evidence—was false. Repeating the current OI-003 reminder more often is unlikely to be a sufficient repair by itself.

### 5. Candidate comparisons were stronger than causal comparisons

**Established design limitation; contribution to poor route selection is plausible.** Fresh training seeds changed with successive interventions: T1 seed 0, T2 seed 1, through later variants and SAC seed 17. T14 was described as changing only the rollout horizon relative to T13, but changed training seed 13 to 14. T15 changed observation and seed; T16 changed horizon and seed again. Later evaluation panels changed too, although each reported candidate/reference pair shared its panel.

These comparisons establish the measured performance of the particular artifacts. They do not isolate a representation or horizon effect. T14's improvement relative to T13 cannot simply be attributed to horizon, and the single near-baseline T16 run does not estimate how often the original recipe succeeds.

The large regressions are real candidate-level negatives. The causal explanations—“representation collapse,” “optimization limitation,” “trajectory incompatibility”—remain hypotheses unless the available comparisons distinguish them. Adding a general-method disclaimer after each result helps, but does not repair an unsupported causal premise used to select the next intervention. This is directly within OI-014's attribution scope.

There is also genuine evidence of useful improvement: transfer T8 improved the same panel from 150/160 to 153/160, and M17 demonstrated successful computed-torque control through the bounded action interface. The campaign failed to convert those findings into a sufficiently successful learned candidate; it did not establish a physical impossibility.

### 6. Research preferences became additional acceptance criteria

**Observed drift; influence on stopping is plausible.** Repeated records require a candidate to reach a “196/200-equivalent development threshold,” preserve complete inner-band success, and sometimes supply all listed mechanism diagnostics before role assignment or official assessment. E49, E53 and E57 explicitly couple diagnostics to role eligibility. Yet `contracts/program.md:234` says best-known need not meet the human goal, and official assessment is a PI judgment. `contracts/scenario.md` specifies the protected 196/200 result, not a separate mandatory development gate or perfect sub-band score.

No role was assigned despite multiple evidence-backed reference candidates. This did not prevent comparisons—T1 remained accessible—but it left the campaign without the explicit best-known decision the lifecycle supports.

“Inner band” also changed meaning. The repeated 40/40 refers to 6–10 cm on panel 4200. M17's 93/93 refers to below 14 cm. T1/T10 on panel 4200 were 90/93 below 14 cm, despite 40/40 below 10 cm. Later 113- and 118-episode inner-band counts refer to below 14 cm on other panels. The numeric statements can each be correct while an unlabeled handoff suggests a stronger preserved capability than was shown.

This does not mean the PI should have requested official assessment or accepted inner-band regressions. It means those decisions should remain revisable scientific judgments, with explicit populations, rather than inherited harness-like gates.

### 7. The nominally compact brief is large

**Measured size; cognitive impact unproven.** The final `campaigns/brief.md` is 155,551 bytes and 776 lines. Its “Available artifacts and evidence” section contains approximately 145,535 characters. It enumerates candidate artifacts and embeds detailed comparison payloads, including full episode-seed arrays.

Fresh contexts avoid unbounded conversational history, but they still receive a large growing evidence directory if they read this file in full. A compact current state followed by durable artifact links would better serve the reason inquiries and sessions exist. The PI does not need to be told about context exhaustion.

Do not blame OI-015 for this entire size: its exact-component summary lines account for only about 2,788 characters. The larger burden comes from the general artifact/history rendering. Nor can file size alone prove why M30 was misread. This is a measurable harness improvement opportunity, not an established cause of policy performance.

## Attribution to recent harness changes

| Change | Evidence in this campaign | Assessment |
|---|---|---|
| OI-016, `e0ffcd8` | Present before startup; many rationales repeat operation-neutral language. M1 precedes training, I9 probes capability, I12 measures, I14 spans several interventions. Recipe/question coupling still recurs. | Insufficient repair. No isolated evidence of net benefit or that it caused the poor learning outcomes. Simplify and revise its boundary definition. |
| OI-002, `a3d05ac` | All inquiries close, including limited negatives; no indefinitely open success-only inquiry. Some evidence boundaries are so broad that one candidate failure triggers redirection. | Preserve bounded closure. Refine scope/continuation semantics; do not restore success-only or complete-answer closure. Interaction with recipe-level scope is plausible, not isolated. |
| OI-004, `cc736a1` | Nonterminal T5/T6 checkpoints are compared; T8/T9 use nonterminal candidates; M18 compares early and terminal T10. Failed probes are repaired. I13 and the recurring unresolved frontier show progression weaknesses remain. | Candidate-selection behavior improved in observable ways. Keep it; distinguish that success from evidence-backed progression. |
| OI-003, `8834bc4` | Many closures report reach/hold tradeoffs instead of only aggregate scores. E66/E67 nevertheless misstate available M30 margins as missing. | Keep the principle; record a concrete recurrence and address claim-to-artifact traceability. Earlier closure of the issue was not a guarantee across future campaigns. |
| OI-015, `6dd0f5a` | Completed training records contain component comparisons. Across 120 prior-run comparisons, 2,572 aligned policy-component comparisons report zero exact matches. T17 has no aligned comparisons. | Mechanism present, but this campaign did not exercise a duplicate-policy detection case. No evidence that it caused the plateau; no basis to claim its intended behavioral benefit was demonstrated. |
| Earlier verbatim handoff rules | Strong next-method and constraint commitments recur. Existing evidence is not reliably reinterpreted or corrected before opening the next inquiry. | Credible contributor to persistence of mistakes. Modify the correction boundary while retaining factual continuity. |
| Full allocation and 15-inquiry cap | Every inquiry training costs a full allocation; launcher pauses after I15's completed checkpoint. | Cost multiplier and stopping boundary, not explanations for the unsuccessful scientific choices. Do not change them merely to improve inquiry-count metrics. |

The nearby pre-OI-016 campaign `81a5458d` already began with physical measurement and then made method-oriented training choices. It had only four closed inquiries at the reviewed boundary, so it is not a like-for-like full-campaign comparison. Campaign `896c230a`, after OI-003/OI-004 but before OI-015/OI-016, reached official assessment after four inquiries and five trainings; its result was **193/200, an official failure**, not goal success. These histories weaken claims that OI-016 created training-first behavior or that earlier changes guaranteed better campaigns.

## Proposed remediation

### Priority 1: replace restrictive handoff and redundant OI-016 guidance

Change the existing contract/prompt passages rather than adding another layer of reminders. Keep the existing operation permissions and closure outcomes.

Proposed inquiry-boundary wording in `contracts/program.md`:

> An inquiry is a bounded scope of scientific work toward the human goal. Its question states what remains to be learned or developed, and its closure condition states the evidence sufficient for that bounded conclusion. A method-specific question is valid; opening it does not require an operation or predetermine the result. Obtaining and assessing the evidence may span several operations.

Keep the existing positive, negative, limited and inconclusive closure provision, including redirection and loss of a credible route. Add no mandatory minimum operation count. Preserve continuing, checkpointing and reframing as available choices when the work changes within a still-useful scope.

Replace the restrictive handoff language around `contracts/program.md:214` and its two prompt counterparts with:

> Continue from the recorded evidence and scientific state. Conclusions, research constraints and proposed next actions remain revisable. Correct an unsupported interpretation or a mismatch between the question and the evidence when you identify it, including from evidence already available. Record the correction and its basis. A proposed next question does not require opening an inquiry already settled by that evidence.

Retain exact question matching where it identifies an inquiry actually opened or currently active. Recast the preceding session's selected question as a proposed continuation rather than an instruction that goal review must enact. This can use the current fields; it does not require the Runner to judge scientific adequacy.

Remove duplicate OI-016 demands to restate the distinction and justify the first operation from multiple prompt locations. Keep one short operation-neutral reminder. Do not prohibit a question such as whether direct controller imitation can acquire the demonstrated capability; require only that the evidence and conclusion actually concern the implemented experiment.

**Expected effect:** the PI can correct inherited interpretation, avoid redundant inquiry opening, and retain or change methods without manufacturing a new broad question. This is an expected effect to test, not a promised campaign outcome.

### Priority 2: strengthen the evidence handoff with less prose

First make the existing `current_synthesis` convention precise, without adding a new mandatory schema:

> For a conclusion that changes the next direction, identify the completed experiment and the relevant artifact field or diagnostic. Distinguish what was implemented from the intended method. An uninspected diagnostic is not missing evidence. Preserve causal limits when other experimental factors changed.

This should replace overlapping interpretation/realization reminders, not be repeated beside them. It addresses M30, T10/I12 and OI-014 together while leaving the PI free to choose which distinctions matter and how to test them. It does not require exhaustive artifact review, fixed diagnostics, matched seeds for every candidate experiment, or a Runner scientific acceptance test.

At the same time, keep the top-level brief focused on current state, role candidates and referenced evidence. Move exhaustive candidate listings and long comparison payloads behind existing file references or query access. Report episode-panel identifiers/ranges instead of embedding every shared seed. Preserve the full authoritative results and artifacts. This is a presentation change, not evidence deletion or automatic scientific ranking.

A structural artifact index may expose nested field paths, including paths inside array elements, without calculating scientific conclusions. M30 already exposed `terminal_state` at the array level, so richer indexing is assistance, not an explanation that excuses the false absence claim.

### Priority 3: remove accidental gates without selecting the research

Clarify once, alongside the existing model-role rule, that development evidence informs the PI's assessment decision; the protected assessment defines official success. PI-selected sub-band, action-interface and method restrictions remain research choices unless they come from an immutable contract. Label retained slice statistics with both their radius boundary and panel.

Do not automatically assign best-known, launch assessment, replace the PI's method, or make a controller the required next step. Do not lower the official goal. The campaign needs freedom to decide, not a different compulsory path.

Keep the 120k allocation and inquiry cap unchanged while evaluating these repairs. A future choice to treat 120k as a ceiling for inquiry training could reduce the cost of exploratory runs, but it is a separate maintainer budget decision. Raising the cap would extend the current process without repairing it.

## Validation and attribution plan

Use existing campaign evidence to check the proposed boundaries before another expensive campaign. Conduct isolated maintainer-side replay checks; write any outputs under `docs/`, and never continue or mutate the stopped campaign as part of a harness wording test.

1. **Goal review before I13:** supply the actual completed evidence and handoff. Check whether the PI recognizes that existing evidence already supports the proposed bounded conclusion, without being instructed to skip an inquiry. Either useful reinterpretation or a genuinely unresolved new scope can be valid; manufacturing a new operation is not required.
2. **Controller-imitation handoff before I12:** include T10's actual implementation evidence. Check whether the PI distinguishes action-matching reward shaping from the direct-supervision method invoked by the question. It remains free to measure, train, reinterpret or choose another route.
3. **M30 closure:** supply the actual artifact and proposed final conclusion. Check whether it identifies the available terminal-state margins and correctly reports 15 positive / eight negative among the 23 SAC pre-reach failures. It should retain uncertainty about their cause.
4. **Boundary controls:** retain a case where training first is a valid choice, a measurement-only inquiry, and a limited/inconclusive closure with the broader problem unresolved. A repair that forces measurement, bans method development, or prevents bounded closure fails these controls.

Compare the current version, OI-016 reverted alone, and the proposed replacement on the same fixed evidence contexts with the same model settings. Repeat the small decision checks enough to avoid treating one stochastic response as reliable. Then isolate handoff correction from brief-presentation changes; do not bundle every recommendation and attribute the result to one line of wording.

For implementation validation, parse the changed PowerShell, review generated prompts, and use targeted executable-contract tests only for actual state/presentation changes. Do not add tests that assert exact documentation sentences. No parser or repository test was run for this analysis-only document.

Judge the next campaign on faithful evidence use, corrected claims, useful continuation and the cost of decisions, alongside measured candidate performance. Training-first percentage, fewer inquiries, and nominal rule compliance are not independent success criteria. The human goal remains the goal.

## Differences from the existing OI-016 post-campaign RCA

The existing report correctly identifies the repeated method-pivot pattern and the I13 duplication, but its diagnosis needs these qualifications:

- A method family in a question is not inherently a defect. Banning it would reduce PI freedom and exclude valid method development.
- “The closure rules do not require resolution of the underlying distinction” is not by itself a bug. Limited and inconclusive closure are necessary boundaries; broader scientific uncertainty may survive them.
- The first campaign action was measurement. The defect cannot be equated with training-first ordering.
- Absence of a development score at 98% does not mechanically make official assessment impermissible. This was the PI's decision, not a harness gate.
- OI-015 reporting operated, but the duplicate-policy scenario was not exercised; technical presence is not proof of behavioral effectiveness.
- The raw M30 artifacts contradict the final handoff's assertion of missing margins. That recurrence materially broadens the RCA beyond OI-016.

## Evidence locator

All line numbers below refer to the current `campaigns/results.jsonl`, preserved with campaign-end revision `2638849`.

| Claim | Operation/source lines or immutable source |
|---|---|
| Measurement precedes first training | M1 line 1; T1 line 5 |
| Inquiry opening/closure pattern | E2–E66 inquiry records; operation table above |
| Continued training and stabilization comparison | T8 line 54; M12–M14 lines 55, 56, 58; T9 line 57 |
| Same-interface controller capability | M17 line 65; `python-module-M17-1-same_interface_model_based_control_capability.json` |
| Implemented T10 reward shaping | T10 line 66; scientific commit `3df27c98e94daac42a10116344ea9e87c589f1e3` |
| Early versus terminal T10 tradeoff | M18 line 67; E40 line 68 |
| I12 intention/evidence mismatch | E50 line 83; M22 line 85; E52 line 86 |
| I13 opens and closes on existing evidence | E54–E57 lines 88–91; T11/M19–M20 and T12/M21 precede them |
| I14 multi-operation continuation | Lines 92–107; E61 checkpoint line 100 |
| Confounded horizon/observation variants | T13 line 95, T14 line 98, T15 line 101, T16 line 104; candidate `parameters.json` files |
| Late candidate comparisons | M27 line 103; M28 line 105; M30 line 112 |
| False missing-margin claim | E66 line 113; E67 line 114; M30 artifact field specified above |
| Recovered execution failures | M15 line 63; M16 line 64; M29 line 111 |
| No model-role assignment or official outcome | Completed-operation kinds; final `research_state.json` |
| Prior capped campaign | `021ff566:campaigns/results.jsonl` and `runner/state/research_state.json` |
| Nearby pre-OI-016 comparisons | `5581bee` for `896c230a`; `e0ffcd8` for `81a5458d` |

