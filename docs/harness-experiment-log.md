# Harness change tracker

Maintainer-only tracking record for harness changes and open issues. This file
is deliberately compact. It records current status, evidence, decisions and
next actions; it does not reproduce full RCAs, campaign logs or prompt text.

## Operating rules

- **Human:** owns the goal and approves scope.
- **PI/Researcher:** owns scientific interpretation, experiment design and
  training decisions.
- **Runner:** operates the lifecycle, enforces mechanical contracts and records
  evidence; it does not make scientific judgments.
- The assistant may inspect and edit approved maintainer-owned files, but must
  never launch, resume, reset, train, measure or evaluate a campaign without
  explicit maintainer authorization for that bounded task.
- A harness implementation check is not evidence of scientific effectiveness.
- A campaign observation does not prove causality unless the comparison
  isolates the claimed change.
- Resolved, withdrawn and superseded work remains discoverable through Git
  history and the archived log
  [`archive/harness-experiment-log-legacy.md`](archive/harness-experiment-log-legacy.md).
- Harness documentation uses three layers: this live tracker, a curated
  thematic narrative, and the untouched chronological archive. The narrative
  preserves failures, reversals, superseded reasoning and decision evolution;
  the archive is supporting source material, not the primary explanation.
  See
  [`harness-change-narrative.md`](harness-change-narrative.md).

## Current baseline

**As of 2026-10-11**

- Latest completed campaign: fresh v3 campaign `f917968b`.
- Latest attempted campaign: tooling campaign `0d39d52c`, stopped by the
  maintainer during M11, with no official assessment or campaign conclusion.
  Four trainings completed (483,328 actual steps), ten measurements completed,
  and I3 remains active. M11 has no completed result or sealed partial panel;
  its pending state and progress file are execution history, not evidence.
  Final recorded cost is 44.938901 AIU through 23:08:52 local on 2026-10-11:
  PI/preparation 32.845532 and coders 12.093369 (26.91%).
  The stopped campaign review below records the new correction topics.
- Earlier failed startup `5de5e4a0` published the scientific model, then rejected
  two valid training proposals through the PowerShell transport. No training or
  measurement completed; preparation/startup used 4.893137 AIU. This remains an
  implementation failure, not a scientific result or restart authorization.
- Official result: `193/200` (96.5%), below the `196/200` threshold, using
  `T3:checkpoint-120832`.
- Previous campaign `89a6354a` passed at `196/200` with T7. Its launcher
  stopped after I1's invalid session-operation lists. Only that
  checkpoint metadata was corrected to `T5`, `M6`, `E4`; all scientific fields
  were preserved and the same campaign continued without a reset.
- Parent and independent RCAs found a connected decision defect: failed
  variants preserved the broader direction, then justified assessment of an
  unchanged candidate. The approved OI-014/OI-005 revision directly requires
  cumulative direction review and a candidate-specific commitment case in
  ordinary PI prompts. A narrow OI-004 clarification puts training proxies in
  their exposure/runtime context. The latest revision is unmeasured.
- Latest completed-campaign resources: nine training operations (1,087,488 steps),
  thirteen completed measurements, nine inquiries, 156.47 AIU and 54m09s PI
  time. Previous campaign: 845,824 steps, eight measurements, three inquiries,
  77.03 AIU and 29m02s PI time. Extra inquiry work accounts for most of the
  increase; this comparison does not isolate a wording effect.
- No campaign operation is running or authorized by this record.
- The fifteen-inquiry limit remains a checkpointed operational pause, not a
  scientific-exhaustion result.
- The full startup-budget review remains open.
- The latest successful campaign does not establish that every representation,
  robot or velocity encoding will work; its claim is bounded to the measured
  artifacts and panel.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Open** | The defect or decision remains unresolved and may require a repair. |
| **Implemented / unmeasured** | Code or wording changed; campaign effect is not established. |
| **Implemented / observed** | The intended behavior appeared in campaign evidence, without causal proof. |
| **Closed** | The original bounded defect no longer recurs under the stated evidence. |
| **Paused / proposal** | Not approved for implementation. |
| **Withdrawn** | Explicitly not pursued; historical evidence remains valid. |

## Outstanding issue register

| ID | Scope | Status | Evidence / disposition | Next action |
|---|---|---|---|---|
| OI-001 | Startup scientific-method coupling | **Closed** | Campaign `896c230a` connected the scientific model, startup control, physical measurements and I1 handoff. | None. Startup cost remains OI-006. |
| OI-002 | Inquiry control and bounded closure | **Closed** | Campaign `1ae27a27` closed positive, negative and limited inquiries without indefinite continuation. | None. |
| OI-003 | Evidence inspection and interpretation | **Closed** | `current_synthesis` now requires claim-to-artifact references and distinguishes uninspected from absent evidence. Campaign `ec7f3d3a` used nested diagnostic artifacts without repeating the M30 false-missing interpretation. | None. A future distinct interpretation defect requires a new issue. |
| OI-004 | Checkpoint nomination and progression | **Original defect closed; nomination clarification unmeasured** | `896c230a` showed nonterminal selection. In `f917968b`, M14 omitted the two 100% T10 training proxies and every full-radius-stage checkpoint. T3's terminal selection was supported by measurement, so this is incomplete nomination, not proven terminal bias. Program and direct prompt guidance now contextualize proxies by exposure/runtime. | Observe context-aware nomination in a separately authorized campaign; do not require measuring every checkpoint. |
| OI-005 | Counterevidence and assessment-decision calibration | **Open / suspected continuation regression; RCA required** | The earlier `f917968b` commitment defect remains historical. Campaign `90563aac` closed all 15 inquiries and paused without official assessment or a scientific conclusion. Opening reasons repeatedly treat development performance below 98% as making assessment unjustified; E44 calls the candidate known to be below the goal threshold. The contract explicitly rejects PI-selected eligibility gates, but permits only assessment or another inquiry. Stronger assessment justification did not reliably produce an equally substantive further-work comparison. The maintainer identifies OI-005 as the continuation-regression suspect; exclusive causality is not established. | Compare the delivered OI-005 prompt revisions (`88076a7`, `91bffe5`, `7d99ca0`) against actual E24-E60 decision reasons at a fixed evidence frontier. Proposed wording direction: replace the extra assessment-only burden with a short symmetric comparison of candidate prospects and the concrete contribution of further work; retain limitations without eligibility gates. Runtime wording remains unchanged pending approval; no automatic assessment or scientific-exhaustion ending. |
| OI-006 | Full startup-budget review | **Open** | The 120,000-step ceiling and its scientific/cost effect have not been reviewed. | Separate maintainer budget analysis from scientific repairs. |
| OI-007 | Prompt-stack ordering R2 | **Paused** | Scientific context precedes operational options; putting the human goal before the PI persona in ordinary sessions is not approved. | No action unless reopened. |
| OI-008 | Residual context delivery | **Corrective revision implemented / unmeasured** | `0d39d52c` exposed repeated access solicitation and accumulating tool replies. The approved correction removes per-result access reminders, automatic full artifact inventories and repeated paired-seed arrays. Compact facts, source pointers and transition metadata remain; full evidence is explicitly retrievable. Bounded-session lifecycle is unchanged. | Observe context growth and retrieval choices in the separately authorized fresh campaign; do not claim reduced scientific cost from implementation checks. |
| OI-009 | Operation-submission handoff and checkpoint bookkeeping | **Implemented / unmeasured** | `89a6354a` stopped after two wrong S3 operation lists. The interface now supplies the current session and exact list at checkpoint transitions, reports expected/submitted lists on rejection, and documents accepted-request consumption. The old validator and boundary wording predate OI-005; a newly observed failure is not proof of a newly introduced regression. | Observe the repaired interface in a separately authorized campaign; do not change retry limits or automatically rewrite scientific content. |
| OI-010 | Protection of the old protocol log | **Open / likely obsolete** | No implementation approved; policy decision is separate from scientific behavior. | Reassess only if a concrete access defect recurs. |
| OI-011 | Console clarity and maintainer-file controls | **Closed** | Logical JSON Pointer rendering, query modifiers and phase-specific read controls are implemented. | None. New defects require a new issue. |
| OI-012 | Independent frozen-policy publication | **Proposal** | Not approved or implemented. Campaign recovery is not authorized. | None. |
| OI-013 | Remove the fifteen-inquiry cap | **Withdrawn** | The cap is accepted as an operational checkpoint pause; its value and resume mechanism remain unchanged. | None unless maintainer reopens it. |
| OI-014 | Decision-relevant causal attribution | **Corrective revision implemented / observation under review** | `f917968b` improved claim limits but preserved a regulation direction across unsuccessful variants. The existing correction addresses accumulated evidence and the next investment. In `0d39d52c`, I2 combines braking and hold-margin reward changes with a new training seed and evaluation panel; this tests a complete candidate, not an isolated component. Combined changes are not themselves a defect. | Assess whether subsequent conclusions and investments exceed the actual comparison. Keep this existing issue separate from query reliability, repetition and evidence fidelity; no compulsory one-factor experiment or Runner judgment. |
| OI-015 | Intended method versus implemented experiment | **Scoped restoration repair implemented / unmeasured** | The historical T10/I12 mismatch remains distinct. E12 in `0d39d52c` restored the older environment/evaluator and removed diagnostics requested by M10. Restoration now requires exact selected files, including recorded parameters; no implicit whole-recipe rollback is accepted. Unselected measurement sources and campaign laboratory tools are preserved. Shared learning/instrumentation files still require PI-authored integration rather than a Runner-inferred merge. | Observe source selection and measurement continuity in the authorized fresh campaign. The repair prevents accidental blanket restoration, not deliberate restoration of a mixed-purpose file or every intended-method mismatch. No old campaign evidence was changed. |
| OI-016 | Inquiry boundaries and revisable handoff | **Closed** | Campaign `ec7f3d3a` used bounded multi-operation inquiry work, positive closure, an updated E19 → E20 frontier handoff, and assessment progression without forcing a stale question. The two fixed-evidence replays provide supporting boundary evidence. | None. A future distinct handoff defect requires a new issue. |
| OI-017 | Nested artifact evidence access | **Closed** | Operation-scoped, fingerprint-verified access retrieved nested evidence and changed conclusions in campaign `339736e0`. | None. |
| OI-018 | JSON/training-log query reliability and context amplification | **Partial improvement observed / explicit rejection retained; usability work backlogged** | In `90563aac`, log-record requests explicitly select metrics or all-metrics, but JSON calls have 14 SDK validation failures from unsupported `queries[].max_bytes`. Revision `435a864` extended the existing byte-budget field to query/batch output and added strict extra-field rejection. Nested query budgets were never implemented; before strict validation they were silently ignored. The maintainer prefers visible rejection and retains it. The two M31 errors at 03:25:55 local are distinct artifact indices 0 (T9) and 1 (T4), hidden by the console renderer; corrected retries at 03:25:58 succeed. | Backlog clearer schema/tool guidance that `max_bytes` is a shared top-level batch budget, and actionable rejection feedback instead of repeated parameter-location mistakes. Backlog console rendering of artifact index. Retain unknown-field rejection, honest continuation and complete retrieval; verify the actual rejected and corrected request shapes through registered SDK dispatch. Per-query budgets are not required by this decision and no API extension, silent argument dropping or runtime patch is approved. |
| OI-019 | Terminal brief contradiction | **Open / low priority** | `build_brief.py` can place a final pass beside a stale pre-assessment checkpoint. No later PI session exists to refresh it. | Repair the durable brief when reporting work resumes. |
| OI-020 | Self-imposed acceptance gates and slice-label drift | **Withdrawn as an invalid generic issue.** | The `79395c88` RCA observation remains valid campaign history, but this issue improperly combined assessment-readiness concerns already owned by OI-005 with scenario-specific radius and panel terminology. No generic harness repair is authorized from that symptom. | Preserve the finding in the campaign RCA; do not add scenario vocabulary to generic guidance. |
| OI-021 | Scenario-specific scientific-model prompt | **Open / high priority.** | The preliminary scientific-model objective in `run_research.ps1` explicitly names reaching, trajectory control, convergence, stabilization and multiple kinematic solutions. The wording is delivered only during the fresh-campaign scientific-model phase, but its generated model and decision-relevant synthesis are handed into startup and remain available throughout the campaign. All 57 recorded scientific-model sessions were exposed, so there is no clean campaign control. Policy scores and recorded measurements remain factual; independent mechanism discovery and robot-generic harness claims are contaminated. | Complete the impact RCA before changing the prompt. Then replace scenario-supplied capability categories with a robot- and task-derived requirement without weakening physical analysis. |
| OI-022 | False operation rejection from process return contamination | **Implemented / unmeasured** | Campaign `5de5e4a0` rejected valid startup training with `OPERATION_VALID: training`. An uncaptured asynchronous stdin-write completion entered PowerShell's success stream beside exit code zero. The completion is now discarded. Twelve harmless checks assert exact scalar Int32 exits for success/failure and varied stdin in capture/stream modes; two existing pipe checks preserve live Unicode streaming and error tails. | Observe only in a separately authorized campaign; no retry-limit or validator change. |
| OI-023 | Search access through readable parent directories | **Implemented / unmeasured** | Root searches in `5de5e4a0` exposed a pre-existing descendant-access hole. Trusted `rg`/`glob` overrides now prune reserved descendants before enumeration or content reads; ripgrep receives only permitted files. Harmless checks cover roots, mixed scopes, phase-specific reads, linked aliases and explicit preview limits. The false rejection exposed the hole; it did not restore write authority. | Observe only in a separately authorized campaign; direct-read controls and scientific ownership remain. |
| OI-024 | Fragmented diagnostics and repeated measurements | **Open / repair not approved** | In `0d39d52c`, M3/M5/M7 reran the same T1 candidate on the same 160 seeds while diagnostics were added in stages. Outcomes stayed 150/160. Branch conditioning was already required by E2 before M3, but was added only after M5. These runs add fields, not independent replication. OI-016 covers redundant inquiries and stale handoff, not this distinct operation-level pattern. | Design a duplicate-work safeguard at the existing submission boundary, with prior-result reuse and PI explanation of genuinely new evidence. Preserve scientifically justified repetition; the Runner must not judge scientific necessity. No blanket evaluation ban or automatic operation rewriting approved. |
| OI-025 | Evidence fidelity in scientific synthesis | **Open / RCA deferred** | In `0d39d52c`, M7 episode 26 has `hold_interruptions=192` but `boundary_in_tolerance_internal_excursions=193`; E4 and subsequent synthesis call 192 the latter. Episode 43 has 242 for both, obscuring the conflation. I1's public statement at 22:34:50 says the open branch occurred at all 160 first reaches, but only 153 have a non-null first reach (150 successes, three reached failures, seven non-reaches). Actual first-reach labels are open where defined; E4 says every first reach without the explicit 160 denominator. An earlier M5 synthesis said eight non-reaches/two reached failures; M7 corrected that split to seven/three. | Later RCA must trace artifact fields, query results and public PI statements into E4 and checkpoints, distinguish corrected statements from propagated errors, and explain why source review and executable checks do not establish interpretation fidelity. No RCA or correction of campaign evidence authorized in this entry. |
| OI-026 | Coding-context, review and verification cost | **Open / comparison required** | Through the T2 request in `0d39d52c`, coders used 12.093369 of 33.638433 AIU (36%); PI/preparation used 21.545064. The two incremental diagnostic coding rounds used 5.169096 AIU before parent review. Exact-file child context, actual diff/source review and executable verification introduce work; the latest native migration retained the earlier review requirement. Historical inline coding is mixed into PI usage, so the 36% share is not an incremental-cost estimate. | Compare earlier inline coding with child authoring, parent review and check execution using attributable usage and equivalent work. Review proportionality and mandatory check proposals separately from mandatory policy evaluation. Retain the implementation-safety rationale; no removal of review, new agent or scientific gate approved. |

## Capped campaign `90563aac`: regression follow-up backlog

The maintainer authorized this backlog update, not runtime repairs, prompt
changes, replay, reset, resume or another campaign. The run paused after I15
closed and checkpointed; there were 15 inquiries plus startup, 31 scientific
sessions and one preliminary model session, not 16 numbered inquiries.

- **Continuation suspect (OI-005, related OI-014):** early development improved
  from 105/160 to 150/160 and then 153/160. After M19 first measured the strongest
  T4 candidate, another 162.310939 of the total 263.614205 AIU was spent without a
  higher development score. Repeated assessment deferral and acceptance of
  nominally new methods require a joint direction/commitment RCA. The binary
  goal-review contract predates `435a864`; that tooling repair did not change
  the cap or ending options. Presence of OI-005 guidance is not demonstrated
  effectiveness, and an observed long run is not exclusive causal attribution.
- **Method realization as a competing contributor:** T3/T7/T8 have matching
  policy weights, optimizer state and normalization at all 24 corresponding
  checkpoints; T2/T9 also match at all 24. Packaged runtime artifacts differ.
  T7 to T8 has no scientific-source delta, despite I11's new-route framing.
  This establishes repeated realized learning, not a general equivalence of
  all artifacts or proof that method collapse is scientifically uninformative.
  The continuation RCA must explain why this evidence did not prevent
  unsupported claims of a new contribution; Runner must not make that judgment.
- **Query budget clarification (OI-018):** a shared reply budget was intended to
  bound the total context returned by a batch, rather than allow each item its
  own full allocation. Strict nested validation made a previously ignored
  argument visible as an error. The maintainer retains that visible rejection,
  not the old silent dropping. Clarify the top-level budget location and
  actionable error feedback; preserve the rejected and corrected actual
  shapes as SDK-dispatch verification criteria. The prior proposal to support
  per-query budgets is not the selected correction. No runtime change is
  authorized, and implementation fixtures did not establish reliable PI use.
- **Console identity correction (OI-018):** include `artifact_index` when
  rendering evidence requests. The quoted M31 calls have distinct SDK call IDs,
  each with one start and completion event; apparent duplicate rendering comes
  from omitted artifact identity, not duplicate delivery.

Recorded sources: `campaigns/results.jsonl` E24-E63 and M31/M35,
`reports/session_usage/90563aac-4d55-41a2-9cfd-dffab0145883.jsonl`, the parent SDK
events for `f1dc1193-bf5a-4c72-b27d-d0dee1108962` (03:25:55-58 local) and
`18c14be1-cf82-4066-a3a9-955139a0073a` (04:13:23 local), and bounded read-only
scientific-source/artifact comparisons. Prior campaign evidence is unchanged.

## Stopped tooling campaign: final review evidence

Campaign `0d39d52c` is a maintainer-stopped observation, not a completed
scientific conclusion. Tracking these topics authorizes no implementation.

- **Costs (OI-026):** final recorded usage is 44.938901 AIU, including preparation,
  all five coders and the interrupted S7 invocation (exit code 6). The final
  usage rows reconcile with source-attributed SDK metering; child lifetime totals
  are not added again. Spending after the T2 request was 11.300468 AIU, all PI.
  The earlier common-stage total remains 33.638433 versus 21.113303 mean AIU for
  the five predecessors reaching T2 request (+59.3%). Historical inline coding
  has no separate role cost or per-call AIU record, so its exact coding cost and
  the new mechanism's incremental overhead are not established.
- **Context (OI-008/OI-018):** 28 submission responses returned 68,281 bytes of
  summaries, navigation metadata and state. Nineteen JSON calls and four log
  calls returned another 538,987 bytes in total across bounded contexts; this is
  returned payload volume, not simultaneous context size or unique evidence.
  S7's SDK shutdown reports 123,500 current tokens, including 116,578 conversation
  tokens. Live scientific stdout is console-only; complete artifacts/logs are
  not automatically attached. Explicit tool results do enter the conversation.
- **Query recurrence (OI-018):** after the initial corrected M7 sequence, S7 again
  queried array-level paths without row wildcards. Two unrestricted log calls
  at 22:53 returned 108,800 bytes, including a third retrieval of T1's full
  parsed trajectory. M9's two complete diagnostic-array queries returned
  239,791 bytes. These observations justify correction work; they do not isolate
  how much cost came from interface design versus PI evidence choices.
- **Capability and direction (OI-014):** M9 measured two T2 checkpoints at 0/160
  each, with no first reaches. I2 closed negatively without condemning the
  general method. In M10, T3 scored 114/160 with 121 first reaches, while the
  unchanged T1 reference scored 154/160 with 156 first reaches on the same new
  panel. T1's 154 versus earlier 150 is a panel change, not a policy improvement.
  I3 then trained T4 under the T2 recipe with the same seed as T3: a more
  discriminating control than the original different-seed comparison. T4's
  zero-success training proxy is not development evidence; interrupted M11
  cannot complete that inference. No model role or official result was assigned.
- **Lost diagnostics (OI-015/OI-025):** E12 explicitly restored
  `robot_learning/scenario/environment.py`,
  `robot_learning/scenario/evaluation.py` and
  `robot_learning/training/reward.py`. Both M10 artifacts use semantics
  `604d52985c97` and lack the qvel/action, contact, branch and internal-step
  fields present in M7/M9. The M10 request nevertheless names those diagnostics.
  The PI correctly extracted basic reach counts but did not acknowledge this
  missing portion of its requested measurement. E13 later restored the T2
  evaluator too; M11 did not finish. Existing recipe restoration behaved as
  specified; this observation is not yet an RCA or permission to redesign it.
- **Duplicate-work safeguard (OI-024):** Copilot's `submit_operation` still passes
  through trusted Runner acceptance, so SDK integration does not prevent such a
  safeguard. Current checks protect call/transaction replay and pending partial
  recovery; they do not require recognition of redundant new measurements.
  Any proposal must distinguish an exact repeat from new diagnostics, new
  panels and deliberate replication, using existing identities and leaving
  scientific necessity with the PI.

Sources: completed `campaigns/results.jsonl` records M9/M10/E12/E13 and their
referenced artifacts; `reports/session_usage/0d39d52c-e9f6-4b27-814c-3b9e21c07b2a.jsonl`;
source-attributed SDK usage and public tool events; the stopped Runner state;
`runner/copilot_adapter.py`, `runner/protocol.py` and `runner/run_experiment.py`.
Only the tracker was changed. No campaign was launched, resumed, reset, measured,
or mutated by this review; the evidence-fidelity RCA remains deferred.

## Comprehensive RCA crosswalk

Source: [`campaign_79395c88_comprehensive_rca_20261009.md`](campaign_79395c88_comprehensive_rca_20261009.md).

| RCA finding | Tracker coverage | Current conclusion |
|---|---|---|
| Inquiry closure became coupled to recipe switching | OI-016; related OI-002/OI-004 | Closed for the bounded defect: the current campaign used multi-operation inquiry work and did not reproduce the stale-question loop. |
| Durable handoff gave provisional decisions excessive authority | OI-016 | Closed for the bounded defect: E19 → E20 handed off the updated frontier and the campaign progressed to E21/E22 without preserving a stale question. |
| Intended method differed from implemented experiment | OI-015 | Wording repair exists; semantic realization still needs the planned replay. |
| Available evidence was carried forward as missing | OI-003 and OI-017 | Closed for the tracked defect: access was fixed under OI-017 and the current campaign did not repeat the false-absence interpretation. |
| Candidate comparisons were mistaken for causal comparisons | OI-014 | Claim limits improved in `f917968b`, but did not sufficiently update direction choices. The cumulative direction correction is unmeasured. |
| Research preferences became acceptance criteria | OI-005; campaign-specific evidence remains in the RCA | Symmetric comparison appeared in `89a6354a` E15, but threshold-trigger wording remains in its handoff. OI-005 is observed, not closed. The radius/panel symptom is not generic harness guidance. |
| The brief became large and cognitively expensive | OI-008, partly addressed | Brief compaction was implemented, but context-delivery causes and scientific effect remain unmeasured. |

## RCA validation still outstanding

The comprehensive RCA proposed four fixed-evidence checks. Only the
pre-I13 goal-review replay was performed, twice. These checks are not campaign
operations and must remain separate from campaign execution:

1. **Completed:** pre-I13 goal review can decline a redundant inherited
   question.
2. **Not required for closure:** T10/I12's historical mismatch was not
   re-exercised by `ec7f3d3a`; it remains a documented limitation under OI-015,
   not a current defect requiring an expensive replay.
3. **Not required for closure:** M30's historical nested-margin case is
   resolved by the evidence-access repair and the absence of recurrence in
   `ec7f3d3a`; a future distinct interpretation failure becomes a new issue.
4. **Completed in campaign behavior:** `ec7f3d3a` included training-first
   startup, measurement and training as peer options, positive closure and
   bounded multi-operation inquiry work.

## Recent implementation ledger

| Date | Change | Disposition |
|---|---|---|
| 2026-10-09 | OI-002 bounded-closure clarification | Retained; campaign effect observed but not causally isolated. |
| 2026-10-09 | OI-004 progression repair | Retained; evidence-backed selection observed. |
| 2026-10-09 | OI-003 interpretation repair | Implemented; recurrence replay pending. |
| 2026-10-09 | OI-015 realization-observability repair | Implemented; semantic replay pending. |
| 2026-10-09 | OI-016 handoff and inquiry-boundary repair | Implemented; fixed-evidence replay completed. |
| 2026-10-09 | Evidence-handoff fidelity revision | Implemented; supports OI-003, OI-014 and OI-015. |
| 2026-10-10 | OI-017 nested artifact query | Closed after successful campaign use. |
| 2026-10-10 | OI-018 batch query and console guidance | Implemented; campaign effect unmeasured. |
| 2026-10-10 | OI-019 terminal brief contradiction | Registered; no repair approved. |
| 2026-10-10 | OI-020 acceptance-gate and slice-label drift | Withdrawn as an invalid generic issue. The campaign-specific RCA observation remains preserved. |
| 2026-10-11 | OI-003 and OI-016 closure | Closed from `ec7f3d3a` campaign evidence; no replay or campaign mutation was required. OI-015 remains implemented/unmeasured because its historical semantic mismatch was not exercised. |
| 2026-10-11 | OI-021 scenario-specific scientific-model prompt | Registered high priority. Direct leakage is confined to the preliminary scientific-model prompt, with downstream influence through its durable output. Impact review precedes repair. |
| 2026-10-11 | OI-005 reconciled dual RCA and goal-review repair | Implemented/unmeasured. The program owns a two-sided terminal-assessment/further-work comparison; only ordinary goal-review routing and its saved objective change. The maintainer explicitly authorized publication, fresh reset with the v3 recipe and one campaign launch after this repair. No replay, cap, budget, recipe, OI-019 or OI-021 change is bundled. |
| 2026-10-11 | Authorized OI-005 campaign observation | `89a6354a` completed five training operations and six measurements, then stopped after two invalid S3 checkpoint proposals. The correct list is `T5`, `M6`, `E4`; the PI submitted `E4` then an empty list. No official result or automatic restart. The rejected exchange request was preserved outside the repository; accepted campaign evidence and backend session remain intact. Details are in the OI-005 RCA. |
| 2026-10-11 | Same-campaign checkpoint correction and completion | Under the original autopilot authorization, only S3's operation list was corrected; every scientific field was unchanged. The Runner accepted E5 and the same campaign continued to an official 196/200 pass with T7. OI-005 is observed, not closed: terminality and work comparison appeared, but commitment omitted recorded residuals and handoff trigger wording persisted. Campaign commits published through `c33531e`; no second reset or campaign. |
| 2026-10-11 | OI-009 checkpoint/submission repair and OI-005 direct reason | Approved and implemented/unmeasured. Checkpoint transitions expose session identity and operation list; rejection reports expected versus submitted values. The instrument contract explains request consumption. Ordinary goal review directly requires an evidence-based decision despite acknowledged limitations, without extra measurements or readiness gates. Program comparison and authority remain. No campaign launched, resumed, reset or mutated. |
| 2026-10-11 | OI-014 claim-driven experimental design | Approved and implemented/unmeasured. The RCA distinguishes candidate selection from causal explanation and corrects the T6 changed-file interpretation: its observation values and reward remained equivalent to T4's. Program guidance now connects comparison design to decision-relevant claims; ordinary scientific prompts state the same distinction. No new instrument, matched-seed mandate, repetition rule, budget change or Runner judgment. Inert prompt checks cover ordinary contexts and unchanged checkpoint transitions. No campaign launched, resumed, reset or mutated. |
| 2026-10-11 | OI-014/OI-005 cumulative direction and commitment correction; narrow OI-004 nomination | Approved after parent and independent RCAs of `f917968b` versus `89a6354a`. Replace blanket non-disproof/no-gate permissions with direct ordinary-prompt rules for accumulated evidence, credible next work and candidate-specific commitment. Contextualize checkpoint proxies. Inert rendering confirms direct guidance in ordinary contexts; checkpoint transitions lose only the old handoff disclaimer, and campaign evidence hashes remain unchanged. Prior wording remains historical, not proven causal. Original OI-002/OI-016/OI-015 defects are not reopened. Measurement-code correction remains separate. Latest revision implemented/unmeasured; no Runner, recipe, budget, cap or schema change. No campaign launched, resumed, reset or mutated. |
| 2026-10-11 | Approved coding-author / main-PI-review mechanism, step 1 of 2 | Implemented/unmeasured. `scientific_coding` creates or resumes an isolated, exact-file-scoped child on the existing SDK client. Ordinary main PI sessions cannot directly edit source or use shell tools; they retain request-file submission. The child proposes an executable laboratory check but cannot execute it or submit operations. Actual diffs, source and check require main-PI review; Runner remains the sole executor. Child usage is recorded separately without counting its duration twice. Preliminary publication and per-invocation runtime lifecycle remain unchanged. Only inert maintainer checks; no campaign or real SDK session ran, and stopped campaign evidence/state remain unchanged. Structured submission and persistent runtime are reserved for step 2. |
| 2026-10-11 | Approved structured submission / persistent Copilot runtime, step 2 of 2 | Implemented/unmeasured. Main PI calls `submit_operation` without file-write or shell tools. An authenticated, sequential launcher channel binds campaign/session identity and passes validated payloads to the existing Runner path; the request file is internal exchange. Compact factual results/errors and checkpoint restrictions return to the same conversation. One SDK process/client survives ordinary operations and fresh checkpoint-bounded contexts; preliminary publication and scoped coding remain. Pending/completed state controls channel-loss recovery; both main resume paths disable unfinished-work replay and receive durable state in the resume prompt. Publication failures stop without automatic reacceptance. Validation capture stays silent; execution streams both pipes live with bounded useful error tails, not a repeated completion log. PI duration excludes Runner wait and child time; child usage is recorded once. OpenCode remains explicitly legacy. Inert fake-controller/SDK, harmless output-only process and AST/import checks only; no campaign or real SDK session ran, and stopped evidence/state remain unchanged. Parent review/publication precedes any separately authorized launch. |
| 2026-10-11 | Authorized tooling campaign failure, OI-022/OI-023 RCA | `5de5e4a0` published the preliminary model, then rejected two valid startup training proposals because the process helper returned an extra asynchronous-write value beside exit code zero. No scientific operation completed. Root searches exposed a pre-existing descendant-access hole. Usage was 4.893137 AIU. The stopped state and model remain preserved; this observation does not authorize a restart. |
| 2026-10-11 | SDK 1.0.19, dependency cleanup and OI-022 return repair | Approved and implemented. `jello` is removed from the researcher group and lockfile; the SDK minimum and locked version are 1.0.19. MuJoCo, Gymnasium, Stable-Baselines3 and NumPy versions are unchanged. The pipe helper discards its write-completion value. Twelve exact-scalar/stdin/capture/stream checks, two existing output-process groups and nine inert controller groups pass. No real Runner operation, campaign launch, reset or scientific execution. |
| 2026-10-11 | Native coding, OI-023 scoped search and PI-selected evidence access | Implemented/unmeasured. Native `scientific-coder` tasks replace manually created coding sessions; identical-scope corrections use the same context-local child. Start/stop hooks carry installed API reminders and challenge incomplete engineering handoffs. Actual diffs and proposed lab checks remain main-PI review, not scientific certification. Per-invocation usage is separate from labeled task-lifetime totals. Trusted search prunes before traversal. One JSON tool supports original-byte retrieval and selected pages; one training-log tool reuses the parser for raw/record access. Real harmless native calls verified delegated reads, freeform patches, permissions, corrections and cancellation in 67 assertions; 68 no-model policy checks, including long-line preview disclosure, and 19 evidence fixture groups also pass. Five real registered SDK tool dispatches verify JSON/log raw access, selection and fingerprint-bound record continuation without model inference or Runner execution. Human tests and scientific operations were not run. Stopped campaign state, history and model remain unchanged; no reset or launch. |
| 2026-10-11 | Frozen scientific-model coding context and scope diagnostics | Implemented/unmeasured after startup observation in `180ced98`. Both characterization requests included the frozen model in `read_paths`; the first coding implementation (`eb04314`) excluded it and returned a generic error, unchanged by the native migration. The PI incorrectly blamed an absent lab directory and switched to training. The repair allows only explicitly selected model reads, retains protected writes, and identifies the rejected path/reason in tool feedback and console output. New writable files remain supported without existing parents. Thirty-seven harmless assertions reproduce both actual requests, distinguish the original rejection, and cover selected reads, denied writes and actionable errors; 68 existing no-model policy checks pass. No campaign resumed/reset or scientific execution performed for this repair. |
| 2026-10-11 | Stopped tooling campaign correction topics: OI-008/OI-014/OI-018/OI-024/OI-025/OI-026 | Maintainer approved tracking and final read-only assessment, not fixes. Query ergonomics now have observed correction needs under OI-018; context flow, combined-method claims, fragmented measurement, evidence fidelity and coding/review cost remain separate topics. OI-025 preserves exact field/count discrepancies for a later RCA. The maintainer stopped `0d39d52c`; this entry neither declares scientific exhaustion nor authorizes continuation. Only this tracker changed; no campaign launched, resumed, reset, measured or mutated by the assessment. |
| 2026-10-11 | Approved OI-018/OI-008/OI-015 corrections and campaign report | Custom query engine retained. Equality filters have a typed schema with required nullable values; array paths expand to rows for selectors and aggregates, and absent filter fields differ from zero matches. JSON/log pages default to 20 rows and 16 KiB selected-value budgets; original reads and explicit broader retrieval remain. Log discovery returns names/coverage, records require metrics or explicit all-metrics, and console shows selectors. Completion replies drop repeated access solicitation, full inventories and repeated paired-seed lists. Recipe restoration requires exact selected source paths and recorded configuration; unselected files and campaign lab tools stay intact. Shared-file integration remains PI science, not a guessed Runner merge. AGENTS, program, instruments and narrative updated. 134 harmless assertions, eight registered SDK dispatches and actual stopped-artifact reproductions pass; compact PowerShell summaries retain outcomes/provenance. No new lint findings relative to HEAD; existing findings remain. Obsolete pre-native fixture signatures were not used to certify this revision. HTML report built in the requested subsession. The maintainer explicitly authorized publication, a fresh v3 recipe reset and one visible-console campaign launch after completion. Scientific effectiveness is unmeasured; OI-024/OI-025/OI-026 and prior campaign evidence are not repaired by this change. |
| 2026-10-12 | Capped `90563aac` continuation suspicion and query defects backlogged | Maintainer approved backlog documentation only. OI-005 now records the suspected continuation regression rather than leaving the correction unmeasured; exact prompt contribution remains to be isolated. OI-018 records observed partial gains and the `435a864` strict nested-budget rejection. Per-query caps under the shared ceiling and visible artifact indices are backlogged, not implemented. Repeated realized methods remain a competing contributor to the long plateau. Only this tracker changes; no runtime repair, scientific-evidence mutation, reset, resume or campaign launch. |
| 2026-10-12 | Retain explicit query rejection; clarify proposed corrections | Maintainer prefers visible rejection of unsupported fields. OI-018 now selects shared-budget schema guidance, actionable rejection feedback and artifact-index console identity, not acceptance of nested budgets or silent dropping. OI-005 records a recommendation to simplify the assessment-only burden into a symmetric comparison; runtime wording is unchanged and a prompt patch is not approved. Only this backlog changes; no campaign action. |
| 2026-10-10 | Three-layer harness documentation structure | Adopted: compact tracker, curated thematic narrative and unchanged chronological archive. Narrative curation remains pending. |

## Evidence index

| Evidence | Role |
|---|---|
| `campaigns/results.jsonl` | Authoritative completed-operation history. |
| `campaigns/brief.md` | Generated current campaign context; may contain stale checkpoint prose. |
| `campaigns/EXPERIMENTS.md` | Generated campaign-readable history. |
| `reports/session_usage/*.jsonl` | AIU, token and tool-call accounting. |
| `docs/campaign_79395c88_comprehensive_rca_20261009.md` | Full independent RCA and proposed validation. |
| `docs/oi016_post_campaign_rca_20261009.md` | Earlier OI-016-specific analysis; superseded where the comprehensive RCA differs. |
| `docs/oi005_assessment_decision_rca_20261011.md` | Reconciled parent and Opus 5.5/high RCAs, evidence, disagreements, bounded repair and campaign-observation criteria. |
| `docs/research-overview/robot-campaign-ec7f3d3a-20261010-error-correction-report.html` | Detailed report for the historical `ec7f3d3a` campaign. |
| `docs/research-overview/robot-campaign-0d39d52c-20261011-tooling-review.html` | Stopped tooling campaign evidence, final cost, correction topics and separately labeled subsequent harness repairs. |
| `docs/harness-change-narrative.md` | Curated explanation of harness failures, attempted repairs, reversals and current conclusions. |
| `archive/harness-experiment-log-legacy.md` | Full prior narrative log, retained for historical lookup only. |

## Maintenance template

Every future entry must answer these questions in this order:

1. **Issue/change ID:** existing OI or a newly approved ID.
2. **Observed defect or decision:** one precise statement.
3. **Evidence:** campaign, artifact, source path or implementation check.
4. **Change:** what was altered, or explicitly that no change was made.
5. **Disposition:** open, implemented/unmeasured, implemented/observed, closed,
   paused, withdrawn or superseded.
6. **Next action:** one owner and one bounded action, or `None`.
7. **Campaign boundary:** explicitly state that no campaign was launched,
   resumed, reset or mutated unless the maintainer independently records
   otherwise.

Do not append full RCA prose, copied prompts, complete campaign timelines or
duplicate generated reports here. Put detailed analysis in a dedicated RCA or
campaign report and link it from this tracker.
