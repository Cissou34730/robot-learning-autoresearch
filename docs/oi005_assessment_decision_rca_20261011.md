# OI-005: assessment commitment and further-work calibration

Date: 2026-10-11. Approved maintainer investigation and repair.

This RCA combines two independent analyses: the parent session, powered by
GPT-6.1 Sol, and a separate Opus 5.5 session with high reasoning. Both analyses
were completed before their diagnoses were compared. The independent reports
remain in the maintainer session artifacts as `oi005-own-rca.md` and
`oi005-opus55-rca.md`. This document is the reconciled, durable conclusion.

## Finding

**OI-005 remains unresolved by the latest passing campaign.** The active
decision point presents assessment and further inquiry as alternatives but
does not consistently route the PI to a comparison between them. This permits
two different substitutions:

- a favorable development result or local improvement triggers commitment,
  sometimes with the official assessment treated as a reversible diagnostic;
- a PI-selected development criterion, unassigned role or incomplete mechanism
  explanation becomes a prerequisite that repeatedly defers commitment.

An official failure does not prove that requesting assessment was premature.
Reaching the inquiry cap does not prove that continuing was scientifically
pointless. The stronger evidence is in the recorded reasons: omitted residuals,
imagined work after a terminal result, inherited gates and role misconceptions.

The repair makes the existing goal-review choice explicit and symmetric.
It does not favor assessment over continued science, promise a pass, or
guarantee a shorter campaign.

## Evidence and method

Completed-operation requests and final campaign state are the primary evidence.
Historical Git revisions recover campaign artifacts; Git history itself is
not scientific evidence. Counts distinguish completed operations from failed
attempts. Failed execution contributes no scientific result.

| Campaign | Artifact revision | Decision evidence | Outcome |
|---|---|---|---|
| `58dcd817` | `05542f3^` | E9 checkpoint, E10 role assignment, E11 conclusion | Official fail, 195/200 |
| `896c230a` | `d3b8eae^` | E17 checkpoint, E18 role assignment, E19 conclusion | Official fail, 193/200 |
| `79395c88` | `42abcb1^` | Repeated goal-review records, final checkpoint and unset roles | Paused after fifteen inquiries; no assessment |
| `339736e0` | `823831b^` | E57/E59/E61/E63, M17-M20, final roles | Paused after fifteen inquiries; no assessment |
| `ec7f3d3a` | `c43d80f` | M9 and E19-E22 | Official pass, 197/200 |

For these revisions, the sources are `campaigns/results.jsonl` and
`runner/state/research_state.json`. State identity is `campaign.id`; request
bodies are normalized as `request.action`, `request.reason` and checkpoint
fields, not nested under an operation-kind wrapper.

Earlier context comes from the
[legacy log](archive/harness-experiment-log-legacy.md), especially lines
1183-1329 and 2520-2558, and the
[`79395c88` comprehensive RCA](campaign_79395c88_comprehensive_rca_20261009.md).
Older campaigns used different schemas and prompt versions; they support
qualitative recurrence, not a controlled comparison.

Campaign-specific scores and mechanism descriptions below are historical
evidence, not examples or defaults supplied to future PIs.

## Cases

### `58dcd817`: relative improvement and a missing terminal tradeoff

T2 measured 153/160 against T1's 150/160. The checkpoint preserved seven
remaining development failures. E11 emphasized improvement and the fact that
only protected evidence can establish official success. It did not preserve
the residual failures in the request reason or compare further work with the
risk of ending the campaign.

E9's frontier said failure or persistent residuals could motivate a new bounded
inquiry. That is not an available same-campaign successor to assessment.
The official result was 195/200.

Assessment below a development goal is not prohibited. The defect is the
missing comparison and terminal-cost acknowledgment, not the point estimate.

### `896c230a`: protected assessment used as a development probe

T5 measured 125/128, or 97.65625%. The checkpoint explicitly acknowledged that
the goal had not been established. E19 justified the protected operation as
decisive and said that "a failure redirects the next scientific direction".
E17 similarly imagined attention shifting to a residual mechanism after an
official failure. The official result was 193/200.

The record does not establish whether the PI meant a separately authorized
future campaign. It does establish that the request did not acknowledge its
terminal commitment and partly justified the choice by post-failure learning.
That is stronger evidence of the defect than the failed verdict alone.

### `79395c88`: research preferences became assessment prerequisites

Fifteen inquiries produced seventeen completed training operations and
twenty-seven completed measurements. Development candidates remained below
the goal and the final candidate regressed. No best-known role was assigned.

Goal-review records made a development threshold, subgroup success and
mechanism diagnostics prerequisites for assessment. Some records withheld
best-known because the goal or protected assessment had not been established.
The contract defines best-known relatively, so that role interpretation is
incorrect.

The candidate evidence could justify continued work. What is missing is a
fresh explanation of what the proposed work could add, weighed against the
strongest available candidate. The scenario-specific diagnostic labels remain
in that campaign's RCA; they do not become harness rules.

### `339736e0`: useful investigation with persistent gate-based deferral

The campaign recorded sixteen completed and two failed training operations,
twenty completed measurements and thirty-two checkpoints. Its strongest
candidate remained T3 at 153/160. All model roles remained empty.

E57/E59 described an "official best-known" candidate. E59 treated being below
157/160 as sufficient to reject assessment. Later frontiers required retaining
all of T3's successes while improving the fixed development result.
Mechanism uncertainty also appeared as a reason to defer.

M17-M20 and E61/E63 produced useful scientific distinctions; M19 was
inconclusive and M20 corrected the discriminator. Calling this campaign
scientifically empty would be false. Candidate non-improvement nevertheless
needed to inform the expected contribution of another route rather than
leaving an inherited point gate in control.

### `ec7f3d3a`: useful success, not closure of OI-005

M9 measured T9 at 158/160 against T1 at 155/160, with three paired wins and
two preserved residual failures. The PI assigned best-known and requested
assessment. The official result was 197/200.

This shows legitimate progression without a complete causal explanation.
It does not isolate the reason for the improvement or demonstrate symmetric
decision calibration. E22 again emphasized that only official assessment can
establish the goal. That fact is true but cannot discriminate when to commit:
failed campaigns used the same argument.

### Earlier evidence and withdrawn repair

`2381bcbf` lost counterevidence after incomplete diagnostic inspection was
called complete; development 197/200 preceded official 195/200.
`d7080d95` inspected diagnostics and weighed an added inquiry's usefulness,
but prioritized its newer favorable panel over mixed evidence; official
assessment failed. These are not identical access defects.

`06656182` did contain a productivity comparison: its reason said the evidence
did not show a signature that justified delaying assessment for another
inquiry. This is stronger than the earlier tracker account that said no
comparison existed. Conflicting development evidence was not fully weighed,
and the official pass does not prove general calibration.

The three-sentence readiness block in `e4736da` asked for caution about
residuals and favorable development scores. The maintainer withdrew it in
`b275861`. Its effect was unassessed, not experimentally disproven.
Reinstatement is rejected because it addressed only early commitment, did not
make terminality salient, and did not compare commitment with productive work.
Its counterevidence principle is retained in a symmetric form.

## Active cause and contributing conditions

The same core goal-review contract and objective were active across the five
recent campaigns. Their different outcomes therefore cannot be attributed to
a change in that text.

The active gap is at the decision point: two alternatives are listed without
an explicit basis for comparing terminal commitment with further work.
Correct terminality, PI authority and relative best-known semantics already
exist under `contracts/program.md`, **Evidence and model roles**, but are not
consistently applied in the recorded choices.

Three contributing conditions explain the observed substitutions:

1. The ordinary prompt requires an unresolved scientific distinction before
   selecting an operation, including goal review with no active inquiry.
   Its outcome-to-next-direction framing can treat assessment as another
   diagnostic or encourage another investigation merely to resolve uncertainty.
2. Research preferences survive in durable handoffs. Existing revisability
   guidance permits correcting them but does not make their role in the
   assessment comparison explicit.
3. Request reasons do not consistently preserve evidence against the chosen
   alternative. That permits selective commitment and repeated deferral while
   leaving the tradeoff unauditable.

These are evidence-backed mismatches and plausible causal mechanisms, not
isolated causal effect estimates.

## Reconciliation of the independent RCAs

| Question | Parent analysis | Opus analysis | Adopted conclusion |
|---|---|---|---|
| Two error directions | Early commitment and persistent deferral | Same, with trigger/gate distinction | Preserve both; neither is defined by outcome alone. |
| Strongest early-request evidence | Terminal-as-probe wording, with ambiguity about later campaigns | Explicit non-terminal belief across several campaigns | Adopt the concrete wording; retain the ambiguity rather than claiming knowledge of intent. |
| Long campaigns | Useful mechanism evidence coexists with unreviewed gates | Role withholding and stagnant-candidate yield omitted from comparison | Combine both; no forced assessment or claim that the inquiries were wasted. |
| Prompt contribution | Unknown-first routing and successor-direction wording apply to goal review | Main saved objective lacks comparison and terminality routing | Repair both goal-review-only routing and the saved objective; preserve other phases. |
| Decision record | Supporting and contrary evidence, residual gap, useful-work case | Explicit evidence against the chosen alternative | Record a concise two-sided reason, using existing fields rather than a new schema. |
| Statistical illustration | No readiness probability prescription | Binomial and posterior-predictive illustration | Do not use modeled campaign pass probabilities: distribution identity and selection assumptions are unverified. |
| `06656182` | Underweighted conflicting evidence | A partial genuine productivity comparison existed | Correct the earlier oversimplification; a partial comparison is not general closure. |
| Instrument text | No scientific timing guidance there | Optional mechanical terminality sentence | Omit the optional duplicate; the program owns the decision and the existing Runner already enforces terminality. |

The statistical illustration supports only the general observation that finite
development scores are uncertain. It cannot establish that any historical
request had a particular pass probability or was irrational.

## Implemented recommendation

`contracts/program.md`, **Goal review**, owns the comparison:

- assess the strongest evidence-backed candidate in light of supporting and
  contrary evidence, residual failures and measurement uncertainty;
- weigh what further bounded work can credibly change in capability, candidate
  selection or commitment, and why that contribution warrants delay;
- acknowledge that either official verdict ends this campaign;
- preserve evidence against the chosen alternative in its reason;
- distinguish relative best-known assignment from goal certification;
- treat favorable development, unresolved mechanisms and inherited PI criteria
  as evidence, not automatic readiness or deferral rules.

`run_research.ps1` routes ordinary goal reviews and newly saved goal-review
objectives to that single-owner section. Measurement-outcome reasoning remains
available, but is distinguished from a terminal campaign decision. Startup,
scientific-model, active-inquiry and checkpoint-transition prompts stay
unchanged.

No numeric gate, confidence requirement, compulsory repeat, full mechanism
explanation, automatic role assignment or assessment trigger is introduced.
The Runner receives no adequacy judgment or new schema. The inquiry cap,
training allocation, fingerprints, recipe and protected evaluator are unchanged.
OI-019 and OI-021 are explicitly outside this repair.

## Implementation checks and campaign observation

Implementation checks passed: PowerShell parsing and inert before/after
rendering of seven synthetic prompt contexts. Only the two ordinary goal-review
contexts changed. Startup, active inquiry and all three checkpoint transitions
remained identical. The saved goal-review objective was separately rendered
without loading the launcher loop; contract routing and terminality were
present. Linked documents, the six-file change scope and whitespace checks
also passed. No human-owned test suite, model replay or dependency operation
was run. These checks establish implementation consistency, not scientific
effectiveness.

The next fresh campaign is explicitly authorized by the maintainer after
publication, using `baseline-distinct-episodes-v3`. It is the behavioral
observation, not a controlled causal experiment. Review its actual reasons:

- whether both alternatives are weighed using campaign evidence rather than
  copied comparison boilerplate;
- whether terminal reasons retain contrary evidence and recognize finality;
- whether continued work states its expected goal contribution without
  treating a point score or complete mechanism explanation as eligibility;
- whether role reasoning remains relative and evidence-backed;
- whether non-improving work changes the expected-yield comparison.

Pass/fail, fewer inquiries and lower cost are not substitutes for that review.
Monitor AI usage, tool-call volume, wall time and operation counts separately
from scientific usefulness. One passing campaign cannot close both directions.

**Disposition at publication:** implemented / unmeasured. Campaign observation
and any stronger status are recorded separately after execution.

### First authorized campaign: `89a6354a`, operationally blocked

The fresh clean/force reset used the v3 recipe commit
`8256c8c7705a5080a722453b26eb13cd85b6e18f`. The reset imported no policy,
measurement or prior designation and left a clean worktree. The campaign
launched with repository defaults after the repair was committed and pushed.

The launcher exited at the post-I1 checkpoint after two rejected proposals.
S3's accepted operation identities are `T5`, `M6`, `E4`. The PI first listed
only `E4`, then changed the list to empty after mistakenly inferring a fresh
session. Neither matches S3. The existing Runner rejected both and the
launcher's bounded retry limit raised an error. I1's limited-negative closure
remains accepted; its session summary has not been accepted. There is no
official assessment, terminal result, pending operation or new inquiry.
This is an operation-contract failure, not evidence against the learning
method or the OI-005 repair.

S2 supplies one limited behavioral observation. E2 explicitly compared
terminal assessment of T4's 191/200 development result with one bounded
inquiry targeting potentially reducible residual failures. It recognized
terminality and corrected an inherited diagnostic claim: interruptions were
associated with failures but also occurred in successful episodes. E3 correctly
stated that relative best-known assignment would not certify performance.
However its frontier still used a development-score target, and the record
does not establish a mature two-sided comparison or repeated reconsideration.
No terminal request or prolonged-deferral sequence occurred. **OI-005 remains
implemented / unmeasured; the isolated observations do not close it.**

Before the block, five training operations, six measurements, two inquiry
operations and two checkpoints completed. All five training operations
completed 120,832 steps, totaling 604,160. The recorded launcher interval was
about 51 minutes. AIU, token and tool-call totals were not available in the
workspace usage-report path and are not inferred from transcript length.
All accepted campaign commits were already pushed at `4bc3fdc`.

The rejected exchange request is preserved in the maintainer session artifacts
as `oi005-rejected-operation-request.json` before removal from the worktree.
Accepted state, evidence and PI backend session are unchanged. No second
campaign, reset, automatic resumption or unrelated repair is authorized by
this record.

## Limits and preserved boundaries

The sample is small and heterogeneous. Models, seeds, panels, methods and
campaign histories differ. OI-021 contaminated the initial scientific-model
framing in all recorded preliminary sessions; there is no clean control.
It is not repaired or causally quantified here.

Completed measurements, artifact comparisons, official verdicts and recorded
resource use remain factual. This RCA does not establish robot-generic
effectiveness, independent mechanism discovery, guaranteed completion or an
optimal time to assess. The Human retains the goal, the PI the judgment, and
the Runner mechanical execution.
