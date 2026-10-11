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
- Latest resources: nine completed training operations (1,087,488 steps),
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
| OI-005 | Counterevidence and assessment-decision calibration | **Observed, not closed; corrective revision unmeasured** | `f917968b` E43 preserved some limitations but committed unchanged T3 after failed alternatives. Best-known rank, failed alternatives and official certification authority cannot substitute for a reasoned case for this candidate meeting the human goal. This comparison now appears directly in ordinary goal-review prompts. | Observe candidate prospects and further-work contributions in a separately authorized campaign; no numerical gate or automatic ending. |
| OI-006 | Full startup-budget review | **Open** | The 120,000-step ceiling and its scientific/cost effect have not been reviewed. | Separate maintainer budget analysis from scientific repairs. |
| OI-007 | Prompt-stack ordering R2 | **Paused** | Scientific context precedes operational options; putting the human goal before the PI persona in ordinary sessions is not approved. | No action unless reopened. |
| OI-008 | Residual context delivery | **Open / not approved** | Brief compaction was implemented; prompt replay and SDK output handling remain possible causes of flooding. | Do not bundle with another repair. |
| OI-009 | Operation-submission handoff and checkpoint bookkeeping | **Implemented / unmeasured** | `89a6354a` stopped after two wrong S3 operation lists. The interface now supplies the current session and exact list at checkpoint transitions, reports expected/submitted lists on rejection, and documents accepted-request consumption. The old validator and boundary wording predate OI-005; a newly observed failure is not proof of a newly introduced regression. | Observe the repaired interface in a separately authorized campaign; do not change retry limits or automatically rewrite scientific content. |
| OI-010 | Protection of the old protocol log | **Open / likely obsolete** | No implementation approved; policy decision is separate from scientific behavior. | Reassess only if a concrete access defect recurs. |
| OI-011 | Console clarity and maintainer-file controls | **Closed** | Logical JSON Pointer rendering, query modifiers and phase-specific read controls are implemented. | None. New defects require a new issue. |
| OI-012 | Independent frozen-policy publication | **Proposal** | Not approved or implemented. Campaign recovery is not authorized. | None. |
| OI-013 | Remove the fifteen-inquiry cap | **Withdrawn** | The cap is accepted as an operational checkpoint pause; its value and resume mechanism remain unchanged. | None unless maintainer reopens it. |
| OI-014 | Decision-relevant causal attribution | **Corrective revision implemented / unmeasured** | `f917968b` improved claim limits but preserved a regulation direction across unsuccessful variants. Program and direct prompt guidance now distinguish a method remaining possible from evidence supporting its next investment. Unresolved causes may survive closure, but their decision consequences remain. | Observe cumulative direction updates and distinguishing evidence in a separately authorized campaign, alongside cost. No new instrument, compulsory control or Runner judgment. |
| OI-015 | Intended method versus implemented experiment | **Implemented / unmeasured** | Wording requires conclusions to name what was actually implemented. The T10/I12 semantic mismatch was not exercised by `ec7f3d3a`; it remains a documented historical limitation, not an open campaign defect. | None for the current harness. Reopen only if a new mismatch occurs. |
| OI-016 | Inquiry boundaries and revisable handoff | **Closed** | Campaign `ec7f3d3a` used bounded multi-operation inquiry work, positive closure, an updated E19 → E20 frontier handoff, and assessment progression without forcing a stale question. The two fixed-evidence replays provide supporting boundary evidence. | None. A future distinct handoff defect requires a new issue. |
| OI-017 | Nested artifact evidence access | **Closed** | Operation-scoped, fingerprint-verified access retrieved nested evidence and changed conclusions in campaign `339736e0`. | None. |
| OI-018 | Artifact-query ergonomics and context amplification | **Implemented / unmeasured** | Batch queries, bounded discovery and modifier-visible console output are implemented. The 544-call historical problem was not measured under the new interface. | Capture query-shape and cost evidence in a future campaign. |
| OI-019 | Terminal brief contradiction | **Open / low priority** | `build_brief.py` can place a final pass beside a stale pre-assessment checkpoint. No later PI session exists to refresh it. | Repair the durable brief when reporting work resumes. |
| OI-020 | Self-imposed acceptance gates and slice-label drift | **Withdrawn as an invalid generic issue.** | The `79395c88` RCA observation remains valid campaign history, but this issue improperly combined assessment-readiness concerns already owned by OI-005 with scenario-specific radius and panel terminology. No generic harness repair is authorized from that symptom. | Preserve the finding in the campaign RCA; do not add scenario vocabulary to generic guidance. |
| OI-021 | Scenario-specific scientific-model prompt | **Open / high priority.** | The preliminary scientific-model objective in `run_research.ps1` explicitly names reaching, trajectory control, convergence, stabilization and multiple kinematic solutions. The wording is delivered only during the fresh-campaign scientific-model phase, but its generated model and decision-relevant synthesis are handed into startup and remain available throughout the campaign. All 57 recorded scientific-model sessions were exposed, so there is no clean campaign control. Policy scores and recorded measurements remain factual; independent mechanism discovery and robot-generic harness claims are contaminated. | Complete the impact RCA before changing the prompt. Then replace scenario-supplied capability categories with a robot- and task-derived requirement without weakening physical analysis. |

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
| `docs/research-overview/robot-campaign-ec7f3d3a-20261010-error-correction-report.html` | Detailed report for the latest successful campaign. |
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
