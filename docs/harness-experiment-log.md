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
  never launch, resume, reset, train, measure or evaluate a campaign.
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

**As of 2026-10-10**

- Latest completed campaign: `ec7f3d3a`.
- Official result: `197/200` (98.5%), above the `196/200` threshold.
- Latest harness changes: OI-016 handoff revision, OI-003/OI-015/OI-014
  evidence-fidelity wording, OI-017 nested artifact access, and OI-018 query
  batching and observability.
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
| OI-004 | Checkpoint nomination and progression | **Closed** | Nonterminal candidates and failed probes can inform progression; `896c230a` showed evidence-backed selection. | None. Do not infer causal improvement. |
| OI-005 | Counterevidence and assessment readiness | **Open / postponed** | Narrow readiness guidance was withdrawn. Residual-evidence loss and premature readiness conclusions remain unresolved. | Design an approved repair before changing prompts. |
| OI-006 | Full startup-budget review | **Open** | The 120,000-step ceiling and its scientific/cost effect have not been reviewed. | Separate maintainer budget analysis from scientific repairs. |
| OI-007 | Prompt-stack ordering R2 | **Paused** | Scientific context precedes operational options; putting the human goal before the PI persona in ordinary sessions is not approved. | No action unless reopened. |
| OI-008 | Residual context delivery | **Open / not approved** | Brief compaction was implemented; prompt replay and SDK output handling remain possible causes of flooding. | Do not bundle with another repair. |
| OI-009 | Operation-submission handoff | **Open** | No implementation approved. | Define the exact ambiguity before editing. |
| OI-010 | Protection of the old protocol log | **Open / likely obsolete** | No implementation approved; policy decision is separate from scientific behavior. | Reassess only if a concrete access defect recurs. |
| OI-011 | Console clarity and maintainer-file controls | **Closed** | Logical JSON Pointer rendering, query modifiers and phase-specific read controls are implemented. | None. New defects require a new issue. |
| OI-012 | Independent frozen-policy publication | **Proposal** | Not approved or implemented. Campaign recovery is not authorized. | None. |
| OI-013 | Remove the fifteen-inquiry cap | **Withdrawn** | The cap is accepted as an operational checkpoint pause; its value and resume mechanism remain unchanged. | None unless maintainer reopens it. |
| OI-014 | Single-change attribution | **Open** | Reporting now preserves confounding limits, but matched-seed or attribution instruments remain unapproved. | Keep claims at artifact-comparison level. |
| OI-015 | Intended method versus implemented experiment | **Implemented / unmeasured** | Wording requires conclusions to name what was actually implemented. The T10/I12 semantic mismatch was not exercised by `ec7f3d3a`; it remains a documented historical limitation, not an open campaign defect. | None for the current harness. Reopen only if a new mismatch occurs. |
| OI-016 | Inquiry boundaries and revisable handoff | **Closed** | Campaign `ec7f3d3a` used bounded multi-operation inquiry work, positive closure, an updated E19 → E20 frontier handoff, and assessment progression without forcing a stale question. The two fixed-evidence replays provide supporting boundary evidence. | None. A future distinct handoff defect requires a new issue. |
| OI-017 | Nested artifact evidence access | **Closed** | Operation-scoped, fingerprint-verified access retrieved nested evidence and changed conclusions in campaign `339736e0`. | None. |
| OI-018 | Artifact-query ergonomics and context amplification | **Implemented / unmeasured** | Batch queries, bounded discovery and modifier-visible console output are implemented. The 544-call historical problem was not measured under the new interface. | Capture query-shape and cost evidence in a future campaign. |
| OI-019 | Terminal brief contradiction | **Open / low priority** | `build_brief.py` can place a final pass beside a stale pre-assessment checkpoint. No later PI session exists to refresh it. | Repair the durable brief when reporting work resumes. |
| OI-020 | Self-imposed acceptance gates and slice-label drift | **Open / newly registered** | The comprehensive RCA found PI preferences treated as gates: unlabeled “inner-band” populations, changing radius/panel meanings, and readiness/role decisions tied to non-contract criteria. The latest pass does not prove this is fixed. | Define reporting boundaries and preserve PI authority without adding Runner judgment. |

## Comprehensive RCA crosswalk

Source: [`campaign_79395c88_comprehensive_rca_20261009.md`](campaign_79395c88_comprehensive_rca_20261009.md).

| RCA finding | Tracker coverage | Current conclusion |
|---|---|---|
| Inquiry closure became coupled to recipe switching | OI-016; related OI-002/OI-004 | Closed for the bounded defect: the current campaign used multi-operation inquiry work and did not reproduce the stale-question loop. |
| Durable handoff gave provisional decisions excessive authority | OI-016 | Closed for the bounded defect: E19 → E20 handed off the updated frontier and the campaign progressed to E21/E22 without preserving a stale question. |
| Intended method differed from implemented experiment | OI-015 | Wording repair exists; semantic realization still needs the planned replay. |
| Available evidence was carried forward as missing | OI-003 and OI-017 | Closed for the tracked defect: access was fixed under OI-017 and the current campaign did not repeat the false-absence interpretation. |
| Candidate comparisons were mistaken for causal comparisons | OI-014 | Still open. Artifact results are valid; causal explanations remain bounded hypotheses. |
| Research preferences became acceptance criteria | OI-020 | Newly registered; not fixed. |
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
| 2026-10-10 | OI-020 acceptance-gate and slice-label drift | Registered from comprehensive RCA; no repair approved. |
| 2026-10-11 | OI-003 and OI-016 closure | Closed from `ec7f3d3a` campaign evidence; no replay or campaign mutation was required. OI-015 remains implemented/unmeasured because its historical semantic mismatch was not exercised. |
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
