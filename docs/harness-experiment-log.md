# Harness experiment log

Maintainer record of harness changes, their rationale, observed results, and
disposition. This is not PI guidance or campaign scientific evidence. It is
not injected into PI prompts and does not replace the lifecycle contracts.

Record implementation checks separately from campaign observations. Passing
tests does not establish that a harness change improves scientific decisions.
An untested change is not a failed experiment, and a retained change is not
automatically a successful one. Superseded and reverted entries remain here.

## Current baseline

The reference baseline is `b4f1cdf`: the winning campaign's harness plus the
inquiry-closure correction, restored in `4a48da9`. Only harness files were
restored; the subsequent campaign's scientific recipes and artifacts were not
rewound.

The active experiment is the reduced scientific handoff below. It is a single
prompt-only bundle on this reference baseline; its campaign effect is untested.

The objective under investigation is scientifically justified action selection:
the PI chooses the action that can resolve a consequential uncertainty rather
than automatically turning each plausible explanation into another training
intervention. The objective is not simply fewer training runs.

The closure correction is retained for lifecycle correctness. No post-win
correction has yet demonstrated a solution to training-first behavior.

## 2026-09-29 reference: winning campaign

- **References:** campaign `3b9f0c1b-33c6-451a-b321-744b012458e5`; final result
  commit `f6fea61`; starting harness preserved by tag
  `inquiery-harnes-success-1` on `aa8b34a`.
- **Observed result:** 159/160 development successes and 199/200 official
  successes. Eight training runs consumed 702,464 effective training steps.
- **What worked:** the campaign measured IK-branch feasibility and joint-limit
  structure, then found a mechanism-specific correction.
- **What did not:** successive ideas still became training interventions.
  I1 stayed open after its own closure condition had been satisfied.
- **Lesson:** reaching the goal does not establish efficient scientific action
  selection. This successful harness also exhibited training-first behavior.

## 2026-09-29: inquiry closure

- **Commit / scope:** `b4f1cdf`; `research/program.md`, `run_research.ps1`.
- **Rationale / change:** separate inquiry closure from campaign completion.
  Use the inquiry's own decision-sufficient result as the positive closure
  criterion; exhaustive certainty is not required. Update session objectives
  and prompt guidance without Runner scientific judgment.
- **Implementation checks:** PowerShell parsing and 16 focused tests passed.
- **Campaign observation:** I1-I4 closed after decisive measurements in campaign
  `7f551163-bae6-40bc-9b0b-a960be607ffb`. That campaign also contained the
  subsequent active-inquiry prompt change, so the effect was not isolated.
- **Disposition / lesson:** retained for correctness. Working closure does not
  by itself improve the choice of the next inquiry or instrument.

## 2026-09-29: broad Meta-Prompting rollout and reversal

- **Commit / scope:** `40ec8e3`; `research/program.md`, `run_research.ps1`.
- **Rationale / change:** recenter active inquiries on scientific decisions,
  expose resource use, and state a positive criterion for training.
- **Implementation checks:** parsing, 16 focused tests, and prompt probes
  passed.
- **Campaign observation:** campaign `f48d2a00` requested training in startup
  before checkpointing, goal review, or inquiry opening.
- **Diagnosis:** the global training criterion and zero-operation/resource
  framing affected startup, while decision-centered ordering applied only to
  active inquiries. The change was mis-scoped. Scientific-model regeneration
  and PI stochasticity prevent a controlled causal attribution.
- **Disposition:** reverted with the stopped campaign in `bb198d2`. The full
  resulting tree exactly matched pre-rollout `1bb7cb5`; closure remained.
- **Lesson:** an inquiry-only design is not inquiry-only if shared documents
  or context change other phases. Passing implementation checks missed the
  behavioral regression. None of this rollout's added global training or
  resource guidance remains.

## 2026-09-29: narrow active-inquiry prompt

- **Commit / scope:** `6c73715`; only `run_research.ps1`.
- **Rationale / change:** keep the human goal first, then surface the inquiry,
  closure condition, and existing decision frontier before score-oriented
  evidence. Add one evidence-based action-selection sentence.
- **Implementation checks:** parsing and 16 focused tests passed. Startup and
  goal-review prompt output was unchanged; inquiry rendering was checked.
- **Campaign observation:** campaign `7f551163...` followed startup checkpoint,
  goal review, and inquiry opening. Inquiries closed, but I2-I5 still converted
  proposed mechanisms directly into training interventions.
- **Scientific results:** T1 scored 151/160; T2 scored 0/160; T3 scored 118/160;
  T4 scored 131/160. T5 training completed, but no M5 result was committed at
  the stop. The five runs consumed 604,160 effective training steps.
- **Interpretation:** the campaign did not demonstrate improvement on the
  intended training-first objective. Its original angular failure pattern
  remained unexplained. Differences in PI-authored diagnostics and scientific
  choices mean these outcomes do not prove the prompt change caused worse
  science than the winning campaign.
- **Disposition / lesson:** removed in the closure-only rollback. Changing
  execution inside an inquiry is insufficient when inquiry selection already
  commits to a training intervention.

## 2026-09-29: goal-review correction and concise-goal revision

- **Commits / scope:** `b5ddb3f`, refined by `0c8ae6a`;
  `run_research.ps1`, `research/build_research_brief.py`.
- **Rationale / change:** make goal review independently own the next campaign
  decision. Label the previous next direction as a non-binding proposal;
  describe the gap as observed failure rather than a remedy; have closure
  preserve its result rather than select the next route.
- **Revision:** `b5ddb3f` also repeated the full official-task paragraph.
  `0c8ae6a` replaced that over-implementation with concise task-coverage and
  uninterrupted-hold wording plus the existing success criterion.
- **Implementation checks:** parsing, Ruff, and rendered-prompt checks passed;
  20 focused tests passed for the first change and five targeted tests passed
  after the wording correction. These are separate runs, not 25 unique tests.
- **Campaign observation:** none. Both commits were made after the campaign
  stopped.
- **Disposition / lesson:** removed in the closure-only rollback as an untested
  bundle, not a demonstrated failure. Independent goal review remains a
  hypothesis that could be tested separately; it is not validated by wording
  checks and should not accumulate on the baseline merely because it was
  implemented.

## 2026-09-29: closure-only rollback

- **Decision:** keep `b4f1cdf`; reverse `6c73715`, `b5ddb3f`, and `0c8ae6a`
  without rewriting commit history.
- **Scope:** restore `run_research.ps1` and
  `research/build_research_brief.py`; `research/program.md` already matches
  the closure-only baseline. Introduce this separate maintainer log instead of
  extending the poorly maintained `research/PROTOCOL_DECISIONS.md`.
- **Verification:** all three harness files exactly match `b4f1cdf`.
  Campaign state, operation request, evidence, configuration, and scientific
  source files were fingerprint-checked and remained unchanged. PowerShell
  parsing, Ruff, and all 20 focused brief/launcher tests passed.
- **Result:** a simpler, understood baseline, not a solution to training-first
  behavior. No campaign was launched or reset for this rollback.

## 2026-09-29: reduced scientific handoff - active, campaign-untested

- **Baseline / scope:** `4a48da9`, whose harness matches `b4f1cdf`.
  `run_research.ps1` and `research/build_research_brief.py`; this log records
  the change. The experiment is introduced by the commit updating this entry.
- **Rationale:** the failed campaign promoted a conjectured explanation into
  the next intervention inquiry. Once the inquiry required a trained
  correction, action selection within it was already committed to training.
  The intervention point is the checkpoint/closure/goal-review handoff.
- **Change:** checkpoint guidance distinguishes observed findings from
  hypotheses and describes the goal gap as a shortfall rather than a fix.
  Closure records the answer, its implications for hypotheses, and uncertainty
  for goal review. Goal review independently chooses the unresolved scientific
  decision; the previous next direction is explicitly non-binding.
- **Context change:** ordinary goal review reads goal, gap, understanding,
  evidence, previous frontier, and proposed direction in that order. Other
  session context ordering remains at the reference baseline. The goal stays
  first, with one concise reminder that it covers the complete official task
  distribution; the full task paragraph is not repeated.
- **Limits:** no state fields, Runner scientific judgments, training rules,
  resource framing, mandatory diagnostic sequence, or hypothesis checklist.
  The existing open/reframe/close session boundaries and closure criterion are
  preserved. This is not a restoration of the entire earlier prompt rollout.
- **Implementation checks:** PowerShell parsing, Ruff, and 20 focused
  brief/launcher tests passed. Direct rendered-context checks covered startup,
  ordinary and terminal goal review, active and closed inquiries, and the
  open/reframe/close transitions. These checks do not test scientific judgment.
- **Expected result:** a conjecture remains a conjecture across fresh sessions.
  The next inquiry addresses the decision that evidence has not resolved,
  instead of inheriting a proposed remedy as a requirement. Training remains
  a valid deliberate choice, not the default consequence of the handoff.
- **Observation to record:** after consequential measurements, inspect the
  checkpoint, closure outcome, and next goal-review decision. Does the
  conjecture retain its evidential status? Does goal review account for what
  remains unexplained and earlier negative results, rather than repeat a
  correction by default? Does the chosen action answer the stated decision?
- **Failure signal:** if successive inquiries still automatically turn the
  unresolved explanation into another trained intervention, the bundle has
  not solved the problem. Fewer training runs alone do not establish success;
  successful wording checks also do not establish success.
- **Campaign observation / disposition:** none yet. Active as one tracked
  experiment, not a validated improvement. No campaign was started or resumed.

## Discussed but not implemented

Hypothesis registries, premise-status fields, mandatory reasoning checklists,
reference-panel reuse, submission-handoff clarification, and explicit
protection of the old protocol log were not introduced by these changes.
Analysis proposals are not part of the active harness unless a commit and
disposition are recorded.

## Future entries

For each change, record the baseline and commit, the specific expected effect,
affected surfaces, implementation checks, campaign evidence and its limits,
and the retain/remove/supersede decision. If no campaign has exercised the
change, record it as untested. Keep automated scientific-recipe changes
separate from harness changes so their outcomes are not conflated.
