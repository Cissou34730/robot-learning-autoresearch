# Harness experiment log

Maintainer record of harness changes, their rationale, observed results, and
disposition. This is not PI guidance or campaign scientific evidence. It is
not injected into PI prompts and does not replace the lifecycle contracts.

Record implementation checks separately from campaign observations. Passing
tests does not establish that a harness change improves scientific decisions.
An untested change is not a failed experiment, and a retained change is not
automatically a successful one. Superseded and reverted entries remain here.

A harness rollback does not reset or revert a campaign or its scientific
artifacts. Campaign history remains in Git for later maintainer analysis.

## Current baseline

The instruction reference is the winning campaign's final `f6fea61`,
restored in `5fef279`. The post-winning
closure-strengthening change `b4f1cdf` and scientific-handoff change `c0cfcb6`
remain removed. The goal-review role-assignment correction below changes only
operation availability, terminal prerequisites, and the meaning of best-known.
The scientific-frontier guidance remains active with mixed subsequent
campaign observations and no isolated causal attribution. The ordinary
goal-review measurement experiment below is active; its first completed
campaign did not exercise the new measurement permission, but campaign
`010714c2` used it for physical investigation before opening I3 and for a
readiness measurement before official assessment. The inquiry architecture and
independent runtime fixes remain unchanged. The measurement-evidence handoff
distinguishes reduced result summaries from full artifacts and exposes bounded structural
inventories. This is a data-presentation change, not new scientific-action
guidance. Campaign `010714c2` explicitly distinguished the summary from the
recorded diagnostics and inspected the artifacts; no recurrence of the prior
false absent-diagnostics claim was observed. Its instrument-document addition
is restored after the documentation-only startup comparison below still
selected training first. Both changes are provisionally retained, not a
demonstrated solution to training-shaped progression. The brief-only context
compaction below removes duplicate presentation while retaining all candidates,
completed operations, and artifact inventories. Its campaign effect on PI cost
and scientific decisions remains unassessed; that compaction did not change
prompts or SDK settings. The October 2 startup-wording clarification is now
withdrawn by the exact working-reference restoration below. Phase permissions
are unchanged.
Campaign `48993cfd` exercised that clarification with a completed plant probe
before checkpointing or training. Its later M5 closure nevertheless lost a
substantial outer-reaching gain behind an aggregate regression, despite
advertised diagnostics. The question-based inquiry-objective experiment below
now targets that framing gap without changing closure criteria or adding
scientific gates. Campaign `2381bcbf` sustained one inquiry through diagnostics,
targeted reaching, and hold-focused shaping, consistent with that intended
continuity but without isolated causal attribution. It failed official
assessment at 195/200 after 197/200 development success; its closure lost
non-entry counterevidence and treated readiness as settled too early. The
startup requested-step ceiling below is implemented as a separate tactical
change; its campaign effect is unassessed. Campaign `d7080d95` used the full
startup allocation and assessed its unchanged startup policy after two
regressing interventions. It failed at 194/200. The narrow goal-review
readiness guidance from `e4736da` is withdrawn by maintainer decision;
neither failed campaign had it. Its scientific effect remains unassessed,
not experimentally disproven. The coordinator confirmed that a separate
agent completed the rollback. The repair commit includes this rollback.
The maintainer approved removing the invented ending and isolating the
temporary inquiry cap. Implementation and directly affected checks are complete.
The shutdown repair `2e897c7`
remains provisionally retained as an operational repair, with campaign-level
behavior unassessed.
The full 120,000-step startup-budget review remains pending.
The maintainer rejects scientific exhaustion / `no_credible_route` as a valid
campaign outcome. Future requests and obsolete pending execution for that
ending are rejected. Historical records remain readable. The current
fifteen-inquiry cap is a temporary execution
limit, not a scientific decision signal, and is intended to be removed when
the scientist is ready. The cap now pauses execution at a checkpointed boundary;
its value is unchanged. An explicit maintainer increase at that boundary can
resume the same campaign. Independent
frozen-policy publication remains a proposal. The main and campaign HTML
failure explanations are updated before runtime edits.

The objective under investigation is scientifically justified action selection:
the PI chooses the action that can resolve a consequential uncertainty rather
than automatically turning each plausible explanation into another training
intervention. The objective is not simply fewer training runs.

This restoration is not a demonstrated solution to training-first behavior.
The reference campaign's closure and efficiency limitations remain known;
restoring its prompts does not guarantee that a future opening will repeat
its scientific breadth or achieve its result.

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

- **Commit / scope:** `b4f1cdf`; `contracts/program.md`, `run_research.ps1`.
- **Rationale / change:** separate inquiry closure from campaign completion.
  Use the inquiry's own decision-sufficient result as the positive closure
  criterion; exhaustive certainty is not required. Update session objectives
  and prompt guidance without Runner scientific judgment.
- **Implementation checks:** PowerShell parsing and 16 focused tests passed.
- **Campaign observation:** I1-I4 closed after decisive measurements in campaign
  `7f551163-bae6-40bc-9b0b-a960be607ffb`. That campaign also contained the
  subsequent active-inquiry prompt change, so the effect was not isolated.
- **Disposition / lesson:** initially retained for correctness, then removed in
  the 2026-09-30 winning-prompt restoration after the I15 campaign. Working
  closure did not establish better inquiry selection or method development;
  the combination with the later handoff change remained trial-centered.

## 2026-09-29: broad Meta-Prompting rollout and reversal

- **Commit / scope:** `40ec8e3`; `contracts/program.md`, `run_research.ps1`.
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
  `run_research.ps1`, `runner/build_brief.py`.
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
  `runner/build_brief.py`; `contracts/program.md` already matches
  the closure-only baseline. Introduce this separate maintainer log instead of
  extending the poorly maintained `docs/protocol-decisions.md`.
- **Verification:** all three harness files exactly match `b4f1cdf`.
  Campaign state, operation request, evidence, configuration, and scientific
  source files were fingerprint-checked and remained unchanged. PowerShell
  parsing, Ruff, and all 20 focused brief/launcher tests passed.
- **Result:** a simpler, understood baseline, not a solution to training-first
  behavior. No campaign was launched or reset for this rollback.

## 2026-09-29: reduced scientific handoff - reverted after the I15 campaign

- **Commit / baseline / scope:** `c0cfcb6` on `4a48da9`, whose harness matches
  `b4f1cdf`.
  `run_research.ps1` and `runner/build_brief.py`; this log records
  the change.
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
- **Campaign observation / disposition:** exercised by campaign
  `eb19a5f3-14b3-4590-ad74-1b31cf5ae3d5` through I15. Thirteen inquiries each
  contained one training operation, and none was reframed. The intended
  improvement in sustained scientific investigation was not demonstrated.
  Removed together with the closure-strengthening change in the 2026-09-30
  restoration. Their individual causal effects were not isolated.

## 2026-09-30: restore winning prompts and preserve the I15 evidence

- **Decision / scope:** remove `b4f1cdf` and `c0cfcb6` from the active prompt
  configuration. Restore only the three harness files named in the current
  baseline to `f6fea61`, and update this maintainer log. Do not revert campaign
  commits, restore scientific recipes, reset a campaign, or create a separate
  archive. No work on `reports/` is part of this change.
- **Preserved campaign:** `eb19a5f3-14b3-4590-ad74-1b31cf5ae3d5`, final commit
  `6f0da24`, ended at E73 with `no_credible_route`. All scientific source,
  operation history, evaluation artifacts, and archived learned models remain
  in the campaign's existing Git history. No official assessment ran, and no
  working, best-known, or retained role was assigned.
- **Observed process:** 15 inquiry openings and 15 closures, no reframes, and
  exactly one training operation in each of 13 inquiries. I2 and I5 used
  measurement without training. I14 included a standalone controller
  measurement before distillation; the campaign was not devoid of science.
  Nevertheless, most inquiry conditions turned a method question into a
  pre-specified candidate trial, often judged against the entire 196/200
  campaign threshold.
- **Resources:** 13 completed training operations consumed 1,449,984 effective
  PPO steps. Sixteen measurement rounds completed; two other attempts failed
  during implementation repair. Completed measurements executed 7,720
  standard development episodes, plus the 138-target I2 grid and 200-episode
  I14 controller panel. The PI used 107 invocations and 390.386 AIU, versus
  36 invocations and 129.114 AIU in the winning reference. Costs do not
  establish scientific inadequacy by themselves.
- **Opening evidence:** M1 repeated all 160 winning-baseline episode outcome
  records exactly, but lacked the winning measurement's branch, joint-state,
  joint-limit, conditioning, and velocity diagnostics. The narrowed
  coverage-versus-hold question appeared in startup synthesis. Actual startup
  prompts were identical between the winning and first closure-only campaign;
  the changed shared program was read in startup and goal review. This
  identifies a possible cross-phase influence, not a controlled attribution
  of the initial narrowing to one sentence.
- **Interpretation:** the strongest observed failure mode is local
  completion-driven framing. An inquiry selects a prototype, scores it,
  closes negatively, and relegates unexplained collapse or other training
  formulations to a different question. Literal closure became more salient
  than sustained method development. The two retained prompt changes are
  removed as an unsuccessful combined harness experiment, not because every
  negative candidate result was invalid or all inquiry cycles are harmful.
- **Broader scientific evidence retained for later analysis:**
  - I3 tested T2's 17-element representation and obtained 129/200 versus
    T1's 192/200 in M3. Its frozen source at `22748ed` computes feasibility
    from an unwrapped shoulder angle. A 6 cm target at -165 degrees produces
    a raw shoulder angle of -221.25 degrees but a legal equivalent of
    +138.75 degrees; the feature incorrectly marks that branch infeasible.
    This confounds the claimed test of correct feasibility features and does
    not establish that the defect alone caused the performance loss.
  - I6's velocity-sensitive reward candidate achieved 0/200 in M6 and the
    inquiry closed. That is a failed recipe, not an explanation of its
    learning collapse or a rejection of all velocity-sensitive rewards.
  - I14's M14 and M15 were MuJoCo API implementation failures, not scientific
    evidence. The same PI session S32 repaired the call for native MuJoCo
    3.12.0; M16's fixed computed-torque controller then achieved 200/200.
    Controller success alone does not satisfy the learned-policy objective.
  - I14's selected distilled learner achieved 47/200 and 40/200 in M17.
    The frozen training implementation at `9ba48a2` receives the teacher
    configuration and normalizes its fitting inputs, but records no
    imitation-loss diagnostic and no isolated pre-PPO learned-policy
    evaluation. The records do not distinguish failure to imitate from
    subsequent PPO damage; the candidate failure does not resolve that
    method-development question.
  - The unchanged T1 reference was measured on 19 non-overlapping panels:
    3,600 successes in 3,720 episodes, approximately 96.77%. Those fresh
    observations add reliability information beyond inquiry-closure behavior.
  - I15's T13 candidate achieved 197/200 and 195/200 in M18; the reference
    achieved 198/200 and 195/200. The candidate had zero paired wins and one
    paired loss. It failed the PI-added requirement of 196 successes on
    each panel. Its pooled 392/400 is 98%, but is neither an official result
    nor proof of a reliability ceiling. E71 and E73 preserve the actual
    negative decision rather than rewriting it.
- **Evidence limits:** the campaign regenerated its physical model and made
  different scientific implementations, seed choices, and measurement
  decisions. Its behavior supports rejecting the combined prompt experiment;
  it does not isolate the causal contribution of either prompt change or
  prove that restoring the winning prompts will repair scientific decisions.
- **Implementation checks:** the three restored files exactly match
  `f6fea61`; four-file scope, whitespace, PowerShell parsing, and touched-file
  Ruff checks passed. Eight rendered phase, transition, and validation-feedback
  probes match the reference. Eight existing brief/phase tests passed; twelve
  trust-gate tests were blocked before their assertions because Git could not
  access their temporary fixture directories. A repository-local rerun
  reproduced the permission failure. No tests or filesystem permissions were
  changed to bypass it. These checks cannot validate scientific effectiveness.
  No campaign was started or resumed to validate this restoration.

## Goal-review model-role correction

- **Baseline:** winning scientific-work prompts restored in `5fef279`.
- **Implementation commit:** the commit containing this entry,
  `Fix goal-review model-role assignment`.
- **Defect:** goal review could request official assessment only for an
  explicitly assigned best-known candidate, but could not assign any model
  role. When the inquiry cap prevented another inquiry and all roles were
  empty, this made assessment mechanically unreachable. The completed
  I1-I15 campaign ended in that configuration at `6f0da24`.
- **Change:** permit model-role operations during goal review using the
  existing completed-evidence and candidate-integrity requirements. Terminal
  launcher guidance states the best-known prerequisite and permitted role
  assignment. The program defines best-known as a relative evidence-backed
  selection, not certification that the human goal has been reached.
  Instruments document the updated operation availability.
- **Unchanged:** no automatic promotion or assessment, score threshold,
  inquiry-cap change, scientific-action-selection rewrite, or checkpoint
  bypass. Opening an inquiry still requires checkpointing into a fresh
  inquiry session before any model-role operation.
- **Implementation checks:** eleven selected behavior tests passed, covering
  role assignment and assessment requests at the cap, unchanged inquiry and
  training counters, absence of automatic assessment, rejection of empty,
  unknown, or failed evidence, and the inquiry-opening checkpoint boundary.
  Touched-file Ruff and launcher PowerShell parsing passed. The assessment
  tests record requests only; they do not execute protected evaluation.
- **Disposition:** retained as a permission-correctness fix. Scientific
  effectiveness is untested. This does not explain weaker campaign openings
  or solve the remaining scientific-inquiry and method-development problem.
  No campaign was started, resumed, reset, or otherwise modified.

## Scientific-frontier instruction experiment

- **Instruction baseline:** winning-reference prompts plus the goal-review
  permission correction in `eabb35c`. Campaign
  `35365763-6aa0-4675-8e86-f8f277558aa4` exercised that baseline before this
  change; its unfinished M4 transaction and artifacts remain untouched.
- **Implementation commit:** the commit containing this entry,
  `Restore scientific frontier guidance across PI sessions`.
- **RCA:** `6d6d41e` removed explicit causal working-memory guidance and the
  distinction between a recipe outcome and its proposed cause. Later persona
  restoration did not fully restore those meanings. The loss predates the
  winning reference, so textual provenance establishes a weakness, not proof
  that it caused later campaign behavior.
- **Change:** define the scientific meanings of the existing
  `current_synthesis`, `decision_frontier`, and `next_direction_or_closure`
  fields in `contracts/program.md`. Restore the cautions against treating a
  useful policy as causal proof or a failed recipe as broad method
  invalidation. Inject the saved frontier directly into the session prompt
  and connect operation choice and checkpoint preservation to it.
- **Expected effect:** consequential alternatives, claim limits, and the
  unresolved question survive the handoff rather than becoming only a next
  recipe plan. The PI remains free to choose training, measurement, local
  analysis, implementation, or another supported action.
- **Unchanged:** closure rules, session boundaries, operation permissions,
  schemas, instrument contracts, and Runner neutrality. No required extra
  measurement, diagnosis phase, hypothesis registry, scenario-specific hint,
  or training gate.
- **Implementation checks:** seven focused behavior cases passed, including
  rendered frontier transmission into goal-review and inquiry prompts,
  startup without a checkpoint, and existing startup, protection, and
  checkpoint-boundary contracts. Touched-file Ruff and launcher PowerShell
  parsing passed. The context test checks data transmission, not instruction
  wording.
- **Disposition:** retained for a future campaign trial; scientific
  effectiveness is untested. The maintainer confirmed the campaign was
  stopped before edits. No campaign operation was started, resumed, reset,
  or modified.

## Large-scope Git publication and completed-operation recovery

- **Implementation commit:** the commit containing this entry,
  `Fix large Runner Git publication`.
- **RCA and campaign evidence:** campaign
  `15a3cf8a-0cdf-4c03-88fe-f9a832863e8e` completed T1 at 500,736 steps and
  archived 100 checkpoints. Its 405 changed Runner-memory paths produced a
  42,185-character staging command, exceeding Windows' 32,767-unit process
  command limit. The longest actual file path was 178 characters. The failure
  was argument expansion during publication, not training or filesystem path
  length.
- **Change:** scoped staging and commits use temporary, NUL-delimited literal
  pathspec files instead of expanded argument lists. Scoped staged-diff checks
  use batches bounded by the Windows command limit, including quoting, UTF-16
  units, and the terminating NUL. Unrelated staged changes remain outside the
  campaign commit, and temporary pathspec files are removed on success or error.
- **Recovery:** completed execution awaiting result publication or finalization
  is reported as a publication failure. A failed resume is caught and reported
  consistently. The launcher stops with the preserved transaction identified,
  rather than claiming no recoverable state or inviting PI scientific repair.
  Resume continues publication without retraining, reacceptance, a new
  operation, duplicate evidence, or a change to accepted intent.
- **Implementation checks:** 18 focused publication and recovery cases passed,
  including native Git publication above the Windows argument limit, literal
  file and directory scopes, deletion, unrelated staged changes, temporary-file
  cleanup, and training recovery through initial and repeated publication
  failures. Touched-file Ruff and PowerShell parsing passed. The older
  native-Git trust-snapshot fixture remains blocked by Windows pytest-directory
  permissions; the new native-Git checks use isolated test repositories and
  process-local, exact-directory trust without changing ACLs or global Git
  settings.
- **Disposition:** implemented; the publication/recovery backlog item is
  resolved. Campaign files and trained artifacts were preserved. No campaign
  operation was started, resumed, reset, or finalized during implementation.
  This infrastructure correction establishes no scientific improvement.

## Current backlog and remaining work

### Outstanding issue register (2026-10-07)

Use `OI-###` as the stable identifier for an outstanding harness issue. Do not
reuse an identifier after an issue is resolved, withdrawn or rejected.
Implementation checks and unassessed campaign effects are not separate issues.

| ID | Issue | Status / boundary |
|---|---|---|
| OI-001 | Startup scientific-method selection | **Open, narrowed 2026-10-08.** Defined as a failure of traceable coupling from the PI-generated scientific briefing, through startup action selection, to the startup handoff. Three failure locations: briefing defect, use defect and handoff defect. A five-campaign retrospective found no handoff collapse and sound startups in four of five. It found one use defect (06656182) and a briefing that steered the method in four of five. R8 had removed the PI-authority sentence, now restored. The scientific-model prompt (`ef9516f`) changed language, persona and closing section at once. The closing section is restored in controlled English; language and persona stay. Campaign bd32cc79 ran the bundled prompt without the synthesis. Effect on startup selection is not separable. This is separate from the startup training budget. |
| OI-002 | Inquiry control and bounded closure | **Closed 2026-10-09; bounded closure observed.** The contract and inquiry reminder permit positive, negative, limited and inconclusive closure. Campaign `1ae27a27` closed all inquiries at their declared evidence boundaries, including negative and limited results. The campaign does not isolate causality, but the original indefinite-continuation symptom did not recur. Inquiry granularity and later progression belong to OI-004; the temporary cap remains OI-013. |
| OI-003 | Measurement-evidence inspection and interpretation | **Open; expanded 2026-10-09.** The PI has overlooked advertised diagnostic strata, read partial artifacts as complete and lost consequential counterevidence in synthesis. In campaign `1ae27a27`, I9 said arrival-speed change was unestablished although completed M11 artifacts contained the relevant speed diagnostics. I11 treated equal success labels as preserved behavior although M13 showed fewer first reaches and more interruptions. Discoverability is retained, but decision-linked inspection and aggregate-versus-mechanism interpretation remain unresolved. |
| OI-004 | Checkpoint nomination, evidence selection and scientific progression | **Implemented 2026-10-09; campaign effect unmeasured.** Campaign `1ae27a27` evaluated only terminal checkpoints in I9-I15 despite earlier training peaks being available for nomination. I11 then progressed from a behavior-preservation interpretation contradicted by completed diagnostics, while I12-I14 show that the PI could obtain and use further mechanism evidence. The program and ordinary-session prompt now give terminal checkpoints no privileged status, preserve failed or unavailable discriminating evidence as unresolved, and require the next direction to follow completed evidence and the recorded frontier. No Runner gate or required operation sequence was added. OI-004 is not closed until post-change campaign evidence shows whether progression improves. |
| OI-005 | Counterevidence preservation and official-assessment readiness | **Postponed.** The narrow readiness guidance was withdrawn. Residual-evidence loss and premature readiness conclusions remain unresolved. No replacement readiness prompt is approved. |
| OI-006 | Full startup-budget review | **Pending.** Shorter startup requests are permitted, but the maintainer-owned 120,000-step ceiling and its scientific effect have not received the planned full review. This budget question is not the cause or solution for OI-001. |
| OI-007 | Complete prompt-stack review item R2 | **Paused.** Scientific context now precedes operational options, but ordinary sessions do not place the human goal before the PI role. The remaining ordering change is not approved. |
| OI-008 | Residual context-delivery work | **Possible work, not approved.** Brief-only compaction is implemented. Prompt replay and SDK output handling remain separate possible causes of context flooding. |
| OI-009 | Operation-submission handoff clarification | **Unimplemented.** No change is approved. |
| OI-010 | Explicit protection of the old protocol log | **Unimplemented.** Read-access policy remains a separate decision. |
| OI-011 | Console clarity and maintainer-file read controls | **Deferred.** Phase-specific source-read controls are implemented. Console presentation and any further maintainer-file controls remain separate work. |
| OI-012 | Independent frozen-policy publication | **Proposal only.** Publication independent of training is not approved or implemented. Campaign recovery is not authorized. |
| OI-013 | Remove the temporary fifteen-inquiry cap | **Pending.** The cap now pauses at a checkpointed boundary and no longer represents scientific exhaustion. Its value is unchanged. Removal remains a later maintainer decision. |
| OI-014 | Single-change attribution in an intervention | **Open.** An intervention can change several factors at once and then receive a single-cause explanation. The explanation directs the following inquiries, so a wrong attribution can send later work along the wrong route. The requirement is attribution that matches the change, not a repeatable campaign. A bundled change stays valid when its candidate receives direct paired evaluation and the unresolved attribution stays visible. No design or runtime change is approved. |
| OI-015 | Intended intervention versus effective experiment | **Open 2026-10-09; no repair approved.** T16 and T17 recorded different intended controller source, but all corresponding learned-policy and optimizer members, all training records, and all 160 measured episode behaviors were identical. Their complete runtime artifacts were not byte-identical, and the cause is unknown. The record does not establish whether the new intervention was inactive, neutralized, delivered differently at runtime, or equivalent for another reason. An intended source change must not be counted as an independent effective experiment until completed evidence establishes that the experimental distinction was exercised. |

### Detailed backlog and status context

| Item | Status / boundary |
|---|---|
| Full 120,000-step startup baseline | **Instruction correction implemented below; scientific effect remains unresolved.** Fresh startup `2573991c` trained first after the two-string restoration. Startup `c7040992` only planned and checkpointed before goal review opened a baseline inquiry. The change clarifies initial direction, first-action selection and reusable tools. It does not change the allocation or candidate publication. |
| Counterevidence preservation and official-assessment readiness | Guidance `e4736da` withdrawn and its rollback published in `b275861`. Scientific effect remains unassessed. The residual-evidence concerns remain open. No replacement readiness prompt is added; the approved contract repair is separate. |
| Shorter startup training | Tactical change implemented below. The PI may request any positive integer up to the maintainer's per-run allocation during startup, never a larger request. Training remains optional; inquiry requests still use the full allocation. Existing rollout rounding is retained. Campaign effect is unassessed. |
| Reliable measurement-evidence inspection | Discoverability provisionally retained. In `48993cfd`, M5 feedback advertised diagnostics, but the PI closed without inspecting the strata and incorrectly claimed no outer-reaching gain. In `2381bcbf`, M3/M4 diagnostic reads stopped at lines 1-310, were described as full inspection, and remaining non-entry cases were lost in the synthesis. Decision-linked inspection and interpretation remain unresolved. |
| Context flooding | Brief-only compaction implemented below: 57.39% smaller on the completed campaign, with all candidates and inventory references preserved. Campaign benefit remains unassessed; prompt replay and SDK output handling are unchanged and remain separate possible work. |
| Training-shaped inquiry commitments and scientific continuity | Open. Campaign `b366ab54` preserved the exact I2 question across sessions, but the question asked which intervention would work. Each negative result therefore led to another intervention. A bounded inquiry question must permit a positive, negative, limited or inconclusive answer. The inquiry must close when it reaches its declared evidence boundary. No runtime change is approved. |
| Fresh-session scientific handoff fidelity | **Exact conclusion and next-question handoff implemented below; campaign effect remains unassessed.** Startup and inquiry checkpoints now state the next inquiry question. The Runner preserves the source conclusion and question in inquiry state and injects them verbatim into goal-review and inquiry prompts as the same PI's restored scientific state. This removes dependence on the generated brief as the sole compact carrier. It does not prove that the PI will preserve all consequential evidence or select the correct question. |
| Checkpoint nomination and evidence selection | Deferred behind progression; available training facts are not proof of development performance. |
| Operation-submission handoff clarification | Still unimplemented. |
| Explicit protection of the old protocol log | Still unimplemented; read-access policy is a separate decision. |
| Console clarity and maintainer-file read controls | Console work remains deferred. Phase-specific scientific-source reads are implemented below: preliminary can inspect protected benchmark implementation, while later phases retain reserved-read restrictions. Maintainer documents and harness files remain reserved in every phase. Execution and write restrictions remain unchanged. This is not an OS sandbox or demonstrated scientific remedy. |
| Independent frozen-policy publication | **Proposal only.** Publication independent of training is not approved or implemented; campaign recovery is not authorized. |
| Scientific-exhaustion / no-credible-route outcome | **Removed from future requests and instructions.** Obsolete pending execution is rejected. Historical E19 remains readable and unchanged. Directly affected checks pass; scientific effect remains unassessed. |
| Fifteen-inquiry cap | **Decoupled; value unchanged.** The launcher pauses after active work is checkpointed, without a terminal state. Measurements keep their permission. Only an explicit maintainer increase at that paused boundary resumes execution. Later cap removal remains pending. E19 at four of fifteen inquiries was not cap-triggered. |
| Publication/recovery, maintainer training allocation, and goal-review role availability | Implemented; not active repair items. |
| Independent prompt-stack review R1-R8 | **R1, R5-1, R5-2, R6, R7 and R8 are implemented. R2 is partially implemented and paused as OI-007. R3 and R4 are discarded for distinct reasons.** R2 removes the generic policy destination and puts scientific context before operational options. It does not put the human goal before the PI role in ordinary sessions. R3 made the inquiry question too important. The original inquiry rules are restored. R4 became redundant after later recovery work supplied its useful behavior. R5-2 explains candidate-free measurement capability without prescribing an operation or sequence. R5-1 rewrites the instrument contract in controlled English without changing its schemas or mechanical rules. R6 clarifies retention and replacement neutrality. R7 corrects routing and paths. R8 assigns instruction types to one owner and removes launcher repetition. None is a campaign operation or Runner scientific gate. |

The startup allocation change is tactical, not a solution to scientific
continuity. Counterevidence preservation and official-assessment readiness
remain unresolved after the maintainer withdrew the narrow prompt guidance.
Implementation checks do not establish scientific effectiveness. The full
startup-budget review remains pending; no replacement guidance or budget
change is approved. The earlier operational-block versus scientific-exhaustion
proposal is superseded by the maintainer's rejection of scientific exhaustion
as an intended endpoint. Operational constraints must not be presented as
scientific exhaustion.

Hypothesis registries, premise-status fields, mandatory reasoning checklists,
reference-panel reuse, submission-handoff clarification, and explicit
protection of the old protocol log were not introduced by these changes.
Analysis proposals are not part of the active harness unless a commit and
disposition are recorded.

**Deferred: restrict PI reads of maintainer-facing files.** The PI was observed
reading `README.md`, `run_research.ps1`, and `researcher_session.ps1` instead of
staying within its scientific concerns. Investigate SDK file-access controls
or tool-policy enforcement to prevent these reads, including indirect access
through search and shell tools, rather than relying only on prompt wording.
Preserve access to the scientific corpus, robot/task/benchmark contracts, and
PI-owned implementations and tools. This is pending investigation and
implementation; no SDK capability or restriction is assumed to exist yet.
This is not an approved next intervention or an established explanation for
the current scientific regression.

## Future entries

For each change, record the baseline and commit, the specific expected effect,
affected surfaces, implementation checks, campaign evidence and its limits,
and the retain/remove/supersede decision. If no campaign has exercised the
change, record it as untested. Keep automated scientific-recipe changes
separate from harness changes so their outcomes are not conflated.

## Maintainer allocation, engineering scope, and robotics inquiry alignment

- **Implementation commit:** the commit containing this entry,
  `Restore maintainer training allocation and inquiry alignment`.
- **Approved scope:** the two approved backlog items and the agreed prompt
  adjustment. No lifecycle, schema, scientific implementation, or test
  infrastructure redesign.
- **Training allocation RCA:** `034daed` replaced the maintainer-controlled
  allocation with PI-authored `steps` checked only for positivity. The stopped
  campaign consequently requested 500,000 steps for both T1 and T2.
- **Allocation change and expected improvement:** restore the 120,000-step
  default through launcher `-Timesteps` and Runner `--timesteps`. A request's
  `steps` remains a checked assertion of that allocation, not PI authority to
  choose it. Validation, acceptance, and dispatch reject a different value.
  The prompt exposes the actual allocation. This restores predictable,
  maintainer-controlled training expenditure without changing scientific
  operation identities or the learning algorithm's rollout rounding.
- **Engineering scope change and expected improvement:** put the agreed
  strict-scope instructions in `.github/copilot-instructions.md` only, as
  selected by the maintainer. Require approval before expanding an engineering
  task, use proportional existing checks, report unrelated validation blockers,
  and stop after requested delivery. Expected benefit is less unapproved work,
  latency, and resource waste. This does not narrow PI scientific authority;
  `AGENTS.md` and user-wide instructions are unchanged.
- **Inquiry alignment change and expected improvement:** replace the generic
  resolution sentence in the phase prompt with the approved robotics/RL-grounded
  guidance and align `contracts/program.md`. Question, goal connection, and
  closure describe one campaign-relevant decision. New evidence must clarify
  what changes for that decision and why the next action addresses its remaining
  question. Expected benefit is an explicit, coherent continuation or transition,
  rather than another recipe justified by score improvement alone. No mandatory
  extra measurement, automatic closure, or Runner scientific judgment is added.
- **Implementation checks:** ten focused cases passed for budget defaults and
  overrides, refusal of PI changes, preservation of a mismatched pending
  request, frozen training, transfer, and publication-only recovery. Touched-file
  Ruff passed. PowerShell parsing and a mocked-process probe confirmed that the
  launcher forwards the maintainer allocation. No prompt-wording tests, native
  Git fixtures, campaign replay, or full suite were added or run.
- **Disposition:** both backlog items are implemented. Expected PI behavior
  and engineering cost improvement remain untested in subsequent work. The
  stopped campaign and its artifacts remain unchanged: its accepted 500,000-step
  T2 request is not silently resized or reaccepted and will be refused before
  redispatch under the restored default. No campaign was resumed or reset.

## Remove the scientific-model Markdown heading gate

- **Implementation commit:** the commit containing this entry,
  `Remove scientific model heading acceptance gate`.
- **RCA:** the launcher ended a register at any Markdown heading, including
  nested subsections. The current model placed a morphology subsection
  immediately after its facts heading, so existing facts were incorrectly
  reported as missing. This was a formatting rejection, not absent content.
- **Change:** remove that additional PowerShell gate and its obsolete
  heading-specific test and helper. Retain the unchanged Python validator for
  file existence and non-empty content. The three scientific registers remain
  the PI's content contract; no replacement Markdown parser is introduced.
- **Expected improvement:** accept valid model layouts without unnecessary
  PI rewrites, retries, or preparation failures. Scientific adequacy remains
  the PI's responsibility rather than a heading-template judgment.
- **Implementation check:** the launcher accepts the existing model without
  changing its bytes or campaign state. PowerShell parsing and touched-file
  Ruff passed; no new tests or parser infrastructure were added.
- **Disposition:** implemented. The scientific model is not rewritten, and
  no campaign operation is started, resumed, or reset.

## Remove the repository-level engineering instruction bundle

- **Implementation commit:** the commit containing this entry,
  `Remove repository-level engineering scope instructions`.
- **Reason:** the maintainer requested removal after the next PI startup chose
  a baseline before structural changes. The shared instruction bundle is a
  possible source of engineering-to-science priming despite its PI exemption;
  that causal interpretation is not established by this single campaign.
- **Change:** remove only the added maintainer-directed engineering section
  from `.github/copilot-instructions.md`. Keep its AGENTS.md reference.
- **Expected improvement:** remove this possible source of conflicting
  scientific-action guidance without imposing a mandatory preparation sequence.
- **Disposition:** the instruction-file portion of `3d6d29e` is withdrawn.
  The maintainer-owned training allocation, robotics/RL inquiry guidance, and
  `AGENTS.md` are unchanged. No campaign operation is executed by this change.

## Restore pre-alignment scientific guidance after campaign failure

- **Implementation commit:** the commit containing this entry,
  `Restore pre-alignment scientific guidance`.
- **Failed experiment:** the inquiry-alignment addition in `3d6d29e` did not
  produce the expected preparation, evidence selection, and scientific
  progression in campaign `102eeeb6-1f71-4f83-8b93-cb122f526952`.
- **Startup evidence:** unlike preparation-heavy campaign `15a3cf8a`, this
  startup performed no measurement. The PI stated that startup permitted only
  a durable handoff, despite the instrument contract permitting measurement.
  Its preceding harness search exposed a transition-only no-measurement rule
  without its condition. The false phase restriction is confirmed; attributing
  it to that exposure or the new inquiry guidance remains an interpretation.
- **Checkpoint-selection evidence:** M1 evaluated only the terminal
  `T1:checkpoint-120832`, obtaining 151/160 successes. It did not compare
  `T1:checkpoint-100352`, which had the highest recorded training success
  (97%, versus the terminal checkpoint's 95%). Training success does not prove
  that the unmeasured checkpoint would have performed better in development.
- **Progression evidence:** I1 closed after M1, I2 opened, and T2 was accepted
  without evaluating that alternative checkpoint. This failed the maintainer's
  expected deliberate evaluation and method development before further training.
- **Rollback:** restore the pre-adjustment scientific prompt guidance and
  remove its matching program paragraph. Reinstate the engineering instruction
  section removed by `c21feef`: withdrawing it did not recover the desired
  opening. Retain the maintainer-owned 120k allocation, publication fixes, and
  scientific-model heading-gate removal.
- **Expected effect and disposition:** inquiry-alignment experiment withdrawn;
  engineering instructions reinstated. Return to the earlier scientific
  guidance without imposing a mandatory measurement or forbidding a baseline.
  The effect on the next campaign remains untested. All campaign code, results,
  models, checkpoints, and pending work are preserved; the launcher was stopped
  by the maintainer before this rollback.

## Outstanding: evidence selection and scientific progression after startup

- **Issue:** a substantive startup does not by itself ensure that later work
  selects informative policy artifacts, resolves a bounded scientific question,
  or chooses the next operation from the remaining uncertainty rather than
  defaulting to another training recipe.
- **Observed evidence:** the winning campaign achieved the goal while I1
  remained the research container. The later preparation-heavy campaign
  investigated control feasibility before training but continued I1 into T2.
  The stopped campaign evaluated only the terminal T1 checkpoint, left its
  training-peak alternative unmeasured, closed I1, and opened a training-shaped
  I2. Neither keeping an inquiry open nor closing it after one evaluation is,
  by itself, evidence of good scientific progression.
- **Concrete selection trace:** the post-T1 prompt directly supplied both
  the 97% training-success checkpoint and the 95% terminal checkpoint. The PI
  nevertheless called the terminal artifact the "canonical fresh baseline"
  and said training success/reward were not behavioral evidence. Candidate
  nomination from training-distribution observations must be distinguished
  from independent development validation; the metadata was available, not
  hidden by the interface.
- **Current boundary:** the pre-adjustment scientific guidance is restored.
  The best-known role-permission repair removes a mechanical assessment dead
  end, not the checkpoint-selection or scientific-decision problem; no
  model-role operation has been recorded in the stopped campaign.
- **Limits:** an unmeasured training peak is not a proven better development
  policy. The startup's false phase inference and excess browsing do not
  establish a read-perimeter defect as the cause of the regression.
- **Desired improvement:** checkpoint selection should use the available
  learning trajectory and the inquiry's evidence needs; conclusions should
  preserve what remains untested; continuation, closure, and new operations
  should follow the resulting campaign-relevant decision. This does not require
  evaluating every checkpoint, proving every cause, or inserting compulsory
  diagnostic rounds before training.
- **Disposition:** outstanding. Restoring earlier guidance does not establish
  that this problem is solved; further changes require a bounded proposal and
  maintainer approval.

## 2026-10-01: ordinary goal-review scientific measurements

- **Implementation commit:** `c68627d`,
  `Allow scientific measurements during ordinary goal review`.
- **Baseline / observations:** completed campaign
  `e8788df6-9f4a-4dac-92b7-48e40477e827` used 15 inquiries, each with one
  training and one policy-evaluation measurement round, and no reframes. The
  training operations comprised 14 fresh initializations and one transfer,
  totaling 1,812,480 completed steps. PI usage comprised 96 invocations and
  423.484 AIU. The retained role-permission correction was exercised at E62,
  assigning T9 as best-known; it did not prevent the training-shaped sequence.
- **Message evidence:** goal review repeatedly wrote a single training and
  evaluation into an inquiry's closure condition. The next prompt made
  advancing that condition the session objective, and the PI described its
  training action as required or authorized. Partial improvements did not
  produce sustained development of the tested method: T5 reduced post-entry
  failures from five to two while worsening angular acquisition, after which
  goal review selected a different control representation. The investigative
  reference startup and this campaign received the same startup objective,
  but only the reference chose a physical probe before learning. Restored
  wording alone therefore does not guarantee the earlier opening.
- **RCA / limits:** premature recipe commitment is visible in the inquiry
  contracts and subsequent PI messages. Goal review could inspect and analyse
  existing evidence but could not request a measurement before making that
  commitment. This restriction did not force training: the PI could already
  open a diagnostic inquiry. It is an upstream intervention point, not proof
  that the restriction caused the observed behavior.
- **Approved change:** permit the existing measurement operation in ordinary
  goal review while no inquiry is active and the inquiry-creation cap has not
  been reached. Measurements return to the same scientific session. Replace
  only the ordinary goal-review objective and no-active-inquiry context with
  the approved wording, and synchronize the program and instrument permission
  descriptions.
- **Preserved boundaries:** startup, active-inquiry prompts and closure rules,
  persona, shared scientific guidance, training allocation, request schemas,
  and terminal goal-review behavior remain unchanged. Opening an inquiry still
  requires its goal-review checkpoint before further scientific work. No
  compulsory measurement, built-in diagnostic, training gate, or Runner
  scientific judgment is introduced.
- **Expected effect / distinction from earlier experiments:** allow the PI to
  produce evidence that shapes the question or method before freezing a
  one-run inquiry contract. Earlier evidence-selection, closure, and handoff
  wording changes preserved this operation restriction; this experiment
  changes the capability as well as the narrowly scoped context.
- **Implementation checks:** 18 targeted cases passed, covering PI-owned tool
  execution and evidence recording in ordinary goal review, same-session and
  backend continuation, unchanged inquiry/training counters, the cap and
  post-opening restrictions, continued training rejection in goal review,
  model roles, checkpoint boundaries, and preserved startup behavior.
  Touched-file Ruff checks and launcher PowerShell parsing passed.
- **Disposition:** implemented for a future campaign trial; scientific effect
  is untested and the progression issue remains outstanding. Judge the trial
  by whether evidence changes or refines method development, not merely by
  fewer training runs. No campaign was started, resumed, reset, or modified.

## 2026-10-01: first campaign observation and I1 artifact-reading error

- **Campaign / harness reference:** `77a975a5-9917-4178-ad06-ede00161560f`,
  following the goal-review capability and wording change in `c68627d`.
  The initial live assessment was taken around 08:41 local; the campaign
  subsequently completed its protected official assessment at 08:52.
- **Campaign retrieval tag:** `inquiery-harnes-success-2`, an annotated tag on
  `7ce2850`, preserves the completed 200/200 campaign before the later
  measurement-evidence handoff change. The tag is published on the remote.
- **Retrieval references:** these commits archive the relevant operation
  records and artifacts, independently of later campaign resets.

| Finding | Evidence commit |
|---|---|
| M1 startup dynamics probe and artifact | `b5d4e10` |
| M2 learned-policy evaluation | `1f972df` |
| E4 reframe of I1 after M2 | `648fe28` |
| M3 failed learned PD-interface evaluation and nested diagnostics | `cd6aaef` |
| E6 closure of I1, including the false missing-diagnostics claim | `70f1a61` |
| E8 opening of the training-shaped I2 | `5341420` |
| M4 successful hybrid-policy development evaluation | `ad255ec` |
| E11 successful closure of I2 | `62e1059` |
| Protected official assessment outcome | `7ce2850` |

- **Opening:** the PI executed and interpreted a dynamics probe before
  learning. Soft and balanced PD each completed 112/112 tested holds; firm PD
  completed only 12/112 and showed sustained saturation. This was substantive
  physical investigation, not merely a promise to measure. Startup already
  permitted this work before `c68627d`, so the opening does not establish the
  effect of the new goal-review capability.
- **Inquiry progression:** I1 did not close after its first training and
  evaluation. M2 achieved 98/160, with 58 failures before first reach and four
  after entry; the inner-radius result was strong while outer-radius reach
  failed. The PI reframed I1 around that distinction, then trained and
  evaluated the joint-target PD interface before closing the inquiry.
- **I1 closing error:** the E6 reason says M3 contains no per-radius or
  hold-streak diagnostics. That is false: the artifact already archived in
  `cd6aaef` contains all 160 rows under
  `research_evidence.episode_diagnostics`, including target radius, first
  reach, maximum held steps, and interruptions. Its recorded sealed
  fingerprint matches. Those rows show 149 failures before first reach and
  11 after entry. This is an evidence-inspection error, not missing
  instrumentation or a later addition to the artifact.
- **Scope of that error:** T2's zero training success and M3's 0/160 complete
  holds support rejecting the tested candidate and ending that recipe branch.
  They do not establish why learning collapsed or invalidate PD control or
  PPO generally. Closure itself was defensible; the stated absence of
  diagnostic evidence was not. The later campaign success does not correct
  this earlier misreading.
- **Bias / training-first behavior:** both ordinary goal reviews received the
  new optional-measurement wording but opened training-led inquiries without
  requesting measurements. I2 again prescribed one fixed-allocation training
  and evaluation. There is no observed compulsory measurement-first pattern,
  but training-shaped inquiry selection persists. The campaign's better
  investigation and reframe do not imply that every subsequent training
  choice was premature or that the general progression problem is solved.
- **Completed outcome:** M4 achieved 160/160 complete holds, including 25/25
  at 18-20 cm, with no recorded pre-reach failures, post-reach failures, or
  interruptions. I2 closed on that supported development result without
  declaring official success. The subsequent protected assessment passed
  with 200/200 successes for `T3:checkpoint-120832`. Three training runs
  consumed 362,496 completed steps; recorded PI usage was 21 invocations and
  66.268 AIU.
- **Disposition / attribution:** the campaign succeeded and the revised
  prompts reached the PI, but no goal-review session used the newly permitted
  measurement operation. Non-use alone is not failure; equally, this outcome
  does not establish that `c68627d` caused the successful opening, reframe, or
  method. The causal effect remains unestablished, and the I1 evidence-reading
  error remains a recorded finding. No further prompt, instrument, or runtime
  change is introduced by this entry.

## 2026-10-01: generic measurement-evidence handoff

- **Implementation commit:** `f986a2c`, `Expose measurement artifact contents`.
- **RCA / generalization:** M3's artifact contained 160 custom diagnostic rows,
  but the returned record excluded `research_evidence`. The PI inspected only
  lines 1-80 and falsely asserted that those diagnostics were absent; their
  section began at line 1450. The reduced result presentation advertised the
  artifact path without its contents or the scope of the summary. The same
  exposure exists beyond M3: M1's laboratory result exposed only a reference,
  M2 omitted custom evidence, and M4 omitted even the PI-produced compact
  radius-stratified summaries. Those other measurements were used successfully,
  so the visibility gap is a general risk, not a sufficient explanation for
  every interpretation error.
- **Approved change:** derive neutral artifact-contents metadata from the
  actual JSON artifact for all three measurement instruments. It lists JSON
  Pointer locations, types, container sizes, and the union of field names in
  actual object rows. Breadth-first object traversal surfaces top-level
  sections before deeper details. Array values are not copied or individually
  expanded. No scientific field name or interpretation is built in.
- **Bounded presentation:** the structural inventory has a 4096-byte compact
  metadata budget. Omitted sections or field lists are explicitly marked;
  omitted array columns retain their field count when that descriptor fits.
  This is not a change to the SDK tool-output threshold. A complete structural
  overview is still not the complete evidence.
- **Integrity / persistence:** store the inventory with the existing artifact
  reference metadata, derived from the recorded artifact rather than the
  reduced metric dictionary. Preserve full artifacts, their existing
  fingerprints, operation envelopes, and schema-6 lifecycle. The laboratory
  branch indexes its sealed copy and preserves existing recovery behavior.
- **Feedback:** live result feedback and the generated brief distinguish
  reduced result summaries from artifact contents. Limited inventories and
  records without an inventory are explicit rather than implying absent data.
  The instrument contract documents only the metadata's mechanical meaning.
- **Expected improvement / limits:** expose available evidence without
  duplicating its bulk values into the PI context, enabling targeted reads.
  This can address discoverability and clarify inspection scope. It does not
  ensure correct interpretation, nominate a checkpoint, judge a scientific
  claim, require exhaustive reading, or resolve training-shaped commitments.
- **Preserved boundaries:** no scenario or training code, scientific gates,
  inspection checklist, phase objectives, training guidance, model choice,
  context-limit change, dependency, new fingerprint, or campaign operation.
- **Implementation checks:** 17 targeted behavior cases passed, covering
  neutral structure discovery, heterogeneous row fields, pointer escaping,
  bounded and explicitly limited inventories, all three instrument paths,
  immutable artifacts, recovery, and live/brief data transmission. Touched-file
  Ruff and PowerShell parsing passed. Read-only checks of the completed
  campaign's four artifacts confirmed that M3's actual diagnostic fields are
  advertised and that oversized inventories are explicitly limited. These
  checks establish implementation behavior, not improved scientific judgment.
- **Disposition:** implemented for a campaign trial after maintainer approval.
  Scientific effectiveness remains unassessed; no campaign is started or
  resumed to validate the change.

## 2026-10-01: documentation-only reversal for repeated baseline-first openings

- **Implementation commit:** `c2abfc7`,
  `Reverse artifact inventory documentation for startup comparison`.
- **Baseline / observed openings:** the completed successful campaign
  `77a975a5-9917-4178-ad06-ede00161560f` began with a candidate-free dynamics
  measurement before training. After `f986a2c`, fresh campaign
  `b3efe2bc-05e7-4f1d-b595-df09ac6b7a2c` checkpointed an unchanged-recipe
  baseline direction, opened a candidate-dependent inquiry, and requested
  training. Fresh campaign `6350d383-c0a4-4a20-9357-c34df595a68b` requested
  the same kind of baseline directly in startup, without any inquiry handoff.
  These are observations of action selection and requests, not claims about
  completed training or scientific performance.
- **Repeated rationale:** the second opening states that "a baseline candidate
  is needed before deciding whether the restricted 14-20 cm training
  distribution, reward shaping, or control representation requires
  intervention." The first opening similarly describes baseline training and
  diagnostics as the smallest route "without presupposing an intervention."
  Both prioritize observing the existing recipe before changing it.
- **Comparison / RCA limits:** the first startup prompts, restored scientific
  recipes, backend model and reasoning setting, and phase-enforcement code
  match the successful campaign. The direct-startup repeat shows that neither
  an inquiry handoff nor the first opening's mistaken inquiry-first phase
  interpretation is necessary for this behavior. The instrument-document
  addition was read before both decisions and remains a suspected influence;
  this association does not establish its causal mechanism. The new inventory
  and measurement-rendering paths had not been exercised before either first
  training request.
- **Approved reversal:** remove only the complete 44-line "Artifact contents
  metadata" addition from `contracts/instruments.md`, restoring that document
  to its pre-`f986a2c` content. Do not replace it with different guidance,
  remove selected schema fields, or add a required physical probe.
- **Retained implementation:** artifact inventory generation, its 4096-byte
  bound, all three instrument integrations, live feedback, brief rendering,
  request schemas, fingerprints, phase permissions and transitions, persona,
  objectives, training allocation, and scientific runtime remain unchanged.
  The maintainer log is not part of the PI instruction corpus. The metadata
  remains operational even though its explanatory contract section is
  temporarily absent.
- **Test / observation:** the maintainer runs the next fresh campaign with
  the old instrument document and current executable harness. Record the
  first selected action and its public justification, especially whether the
  PI again makes a baseline candidate a prerequisite to method development.
  Investigation before baseline training would support an opening influence
  from the removed text; another unchanged-recipe baseline justified by that
  prerequisite would weaken the hypothesis. Evaluate the reasoning and work,
  not merely whether a particular instrument comes first. A fresh campaign
  regenerates its scientific model, so preserve that model alongside the
  prompt and request when interpreting the comparison.
- **Resources / execution boundary:** the direct-startup repeat used two PI
  invocations totaling 257.506 seconds and 3.282158 AIU before its training
  request. The maintainer approved applying this reversal for the next fresh
  campaign while handling the currently dispatched run. No campaign is
  stopped, reset, started, resumed, or evaluated by this engineering change.
- **Observed comparison:** campaign
  `010714c2-5abd-4836-96bd-364caaf82042` started from `c2abfc7` and read the
  instrument document without the metadata section. In S1 startup, before
  any inquiry, measurement, or checkpoint, the PI expanded training radii
  from 0.14-0.20 m to 0.06-0.20 m and submitted a fresh 120000-step PPO
  request. The sole accepted scientific-code change was that training-range
  expansion. This preserved training-first ordering, but was an intervention
  rather than the previous unchanged-recipe baseline prerequisite. No
  completed policy outcome is used for this opening assessment.
- **Observed resources:** the preliminary and startup invocations totaled
  243.959 seconds and 5.035910 AIU before the training request.
- **Disposition:** the removal did not restore investigation before training;
  the document addition is not necessary for the observed training-first
  behavior. The reasoning and recipe did change, so this is not evidence of
  identical decisions or zero influence on every aspect of the opening.
  Restore the document after maintainer approval and retain the inventory
  implementation.

## 2026-10-01: restore the instrument contract and inspect model/prompt framing

- **Implementation commit:** the commit containing this entry,
  `Restore artifact inventory contract after startup trial`.
- **Approved restoration:** restore the exact 44-line metadata section from
  `f986a2c` in `contracts/instruments.md`. No executable code, phase prompt,
  scientific model, training recipe, or campaign operation changes.
- **Archived model references:** the winning campaign
  `77a975a5-9917-4178-ad06-ede00161560f` published
  `pi_workspace/scientific_model.md` in `7d88b15`; its frozen content is also
  retained by `inquiery-harnes-success-2`. The training-first startup
  `010714c2-5abd-4836-96bd-364caaf82042` published its model in `d189d5a`.
  These archived documents, not a later campaign's worktree file, support
  the comparison.
- **Main framing clue:** the winning model describes a second-order coupled
  plant and leaves practical motor authority, braking margin, settling, and
  closed-loop observables explicitly uncharacterized. The later model retains
  physical unknowns but also concludes that "the principal uncertainty is the
  policy's ability to infer and control the system's transient response rather
  than to estimate a changing world." This sentence was exposed in the PI's
  complete model read before action selection. It assigns priority to learned
  control before compiled dynamics or bounded closed-loop capability have
  been characterized.
- **Additional context clue:** the winning model already situates the
  restricted training range among physical failure classes. The later model
  omits that range, and the startup discovers it during implementation
  inspection, then selects its expansion as the highest-leverage intervention.
  This is a difference in framing and discovery sequence, not a proposal to
  insert a prescribed training intervention into the physical model.
- **Prompt interaction / limits:** the common startup prompt asks the PI to
  establish the first direction from the model and actively use its physical
  consequences and unknowns to form explanations. A model that names policy
  capability as the principal uncertainty can therefore supply a preselected
  learning question, whereas an uncharacterized-plant framing can support
  candidate-free investigation. The public openings follow those respective
  framings, but this association is not an isolated causal test. Both models
  contain physical and learning uncertainties; neither compels one instrument.
- **Disposition:** instrument documentation restored; training-first
  progression remains unresolved. Model priority-setting in combination with
  the startup prompt is an investigative lead only. No preliminary prompt or
  scientific-model contract change is approved or implemented here.

## 2026-10-02: assess evidence-led progression in the completed campaign

- **Reference:** campaign `010714c2-5abd-4836-96bd-364caaf82042`; authoritative
  operation records and terminal result in `runner/state/research_state.json`,
  detailed measurements under `campaigns/evaluations/010714c2-5abd-4836-96bd-364caaf82042/`,
  and PI resource records in
  `reports/session_usage/010714c2-5abd-4836-96bd-364caaf82042.jsonl`.
- **Observed result:** official assessment failed at 189/200 (94.5%) for
  `T7:checkpoint-120832`, below the required 196/200. Six completed training
  operations consumed 724,992 steps; 41 PI invocations consumed 112.084903 AIU.
- **Goal-review capability:** M4/M5 investigated control authority before
  opening I3. The first probe saturated and failed; the PI corrected the
  controller rather than infer physical impossibility. M5 then achieved
  160/160 with the nearest-branch low-gain controller. M9 was also requested
  in goal review to examine readiness before official assessment. This is
  actual exercise of the permission added by `c68627d`, not proof that the
  permission alone caused the scientific direction.
- **Evidence inspection:** all 14 measurement artifact records carried
  structural inventories. After M1, the PI explicitly recognized that
  diagnostics were present although their values were omitted from the
  summary. It inspected them, corrected a radius-binning defect, and queried
  geometry and hold diagnostics in later rounds. No recurrence of the
  earlier partial-read claim that diagnostics were absent was observed.
- **Progression limits:** I1 was diagnostic-only; I3 continued a partial gain
  to replication; I4 tested two seeds. Nevertheless, I2 explicitly
  prescribed one training/evaluation round and later inquiries still framed
  method questions around fixed recipes. I4's no-material-hold-regression
  condition was softened to the stronger run despite 23 interruptions for
  T6 versus four for T7. For T7 readiness, M8 scored 156/160 and M9 157/160;
  the combined 313/320 (97.8125%) did not support the claim that performance
  had reproduced above threshold. These are PI scientific-judgment limits,
  not a request for Runner scientific gates.
- **Execution failure:** T3 failed Ruff before training. The same PI session
  repaired formatting; T4 superseded T3 with the identical scientific request,
  seed, initialization, and allocation. The repair added 49.315 seconds of
  PI invocation time and 1.525432 AIU, with no training steps or scientific
  evidence. No direction change was observed.
- **Disposition:** maintainer accepted provisional retention of the
  goal-review measurement and evidence-inspection changes. Their specific
  mechanisms worked in this campaign; the broader progression objective was
  only partly met. Official policy failure does not establish that those
  mechanisms failed. Context flooding is the next approved backlog item;
  no startup, inquiry, closure, or readiness prompt change is introduced.

## 2026-10-02: compact repeated brief content without evidence selection

- **Implementation commit:** the commit containing this entry,
  `Compact repeated research brief content`.
- **Approved scope:** `runner/build_brief.py`, directly affected
  tests in `tests/autoresearch/test_research_brief.py`, and this log. No phase
  prompt, scientific contract, authoritative campaign record, artifact,
  fingerprint, session-continuity rule, or SDK offloading threshold changes.
- **Rationale:** the completed campaign's prior rendered brief was 109,508
  UTF-8 bytes. It repeated the statistics of 144 candidates in both a verbose
  registry and training-event JSON blocks. Fourteen artifact inventories
  contained only three distinct structures. The brief also copied the latest
  checkpoint synthesis into its leading evidence section.
- **Change:** list every candidate in one compact table with origin,
  per-operation and accumulated steps, training success/reward, and evaluation
  references. Full archive locations and metadata remain explicitly
  addressable through `runner/state/research_state.json`'s candidate registry.
  Training events retain initialization, parent, seed, requested/completed
  steps, and mechanical provenance but reference the table instead of
  repeating checkpoint statistics. Render each exact structural inventory
  once and associate every measurement artifact with its reference; distinct,
  truncated, and missing inventories remain distinguishable. Render the full
  checkpoint synthesis once. Keep the human goal, gap, inquiry, session
  objective, all completed operations, measurement summaries, paired
  comparisons, artifact references, and execution-failure history.
- **Implementation checks:** seven directly affected brief/goal-context
  tests passed; touched-file Ruff checks passed. A read-only replay of the
  completed campaign compared the old and new renderers: 109,508 -> 46,656
  bytes, a 57.39% reduction. It verified all 144 candidate rows and their
  statistics, every completed-operation reference, artifact reference and
  paired comparison, and all 14 inventories resolving to three exact
  structures. The authoritative state was unchanged. The quantitative
  comparison uses both renderers' UTF-8 output, not differing file newline
  encodings.
- **Campaign observation:** none yet with this compact renderer. No campaign,
  training, or protected evaluation was started or resumed for this change.
- **Disposition / limits:** implemented for observation. The measured
  presentation reduction exceeds the approved less-than-half-size target,
  but does not demonstrate lower PI cost or better scientific decisions.
  Repeated full prompts and large tool outputs remain outside this isolated
  change; there is no history cutoff, candidate ranking, semantic
  summarization, or deletion from the factual record.

## 2026-10-02: separate startup investigation from formal inquiry opening

- **Implementation commit:** the commit containing this entry,
  `Clarify scientific investigation during startup`.
- **Trigger:** in S1 of campaign
  `a6def80f-a30e-44ec-9c18-188c04fdb535`, the PI stated: "The active session is
  the initial startup session, so the contract requires a durable checkpoint
  before inquiry selection." It submitted E1 without a measurement or training
  operation and prescribed baseline training for the next inquiry.
- **RCA:** the startup prompt repeated "inquiry selection follows in goal
  review" in both the active-inquiry description and the session objective.
  The actual protocol restricts formal inquiry opening to goal review; startup
  already permits scientific operations before its closing checkpoint.
  Selecting a scientific question or investigating it is not mechanically
  gated by formal opening. The broader wording can encourage a planning-only
  interpretation. It was present before brief compaction; that does not make
  it neutral, nor establish that it alone caused the baseline-first choice.
- **Approved change:** change only those two startup strings in
  `run_research.ps1`. State that startup permits selecting and investigating
  a scientific question before checkpointing. Establish the initial direction
  through the model and scientific work in that session, and checkpoint when
  the work reaches a stable decision. Reserve only formal inquiry opening for
  goal review. Do not require a probe, measurement, training run, or baseline.
- **Preserved boundary:** no phase-permission, session-transition, scientific
  model, persona, goal-review/inquiry objective, SDK, or brief-renderer change.
  The existing campaign state, operation request, and PI-owned code edits are
  not modified. The maintainer will reset and restart the campaign.
- **Implementation checks:** 11 existing targeted prompt/phase-permission
  cases passed. The full launcher parsed successfully. A read-only rendering
  comparison evaluated the actual objective expressions and context functions:
  only the startup active-inquiry description and objective changed;
  goal-review and inquiry objectives and rendered prompts were unchanged.
  It did not execute the campaign loop. No tests of instruction wording were
  added.
- **Disposition:** implemented for a fresh-campaign observation. It corrects
  the distinction between scientific work and administrative inquiry opening;
  whether it improves startup decisions or later method development remains
  unassessed.

## 2026-10-02: M5 tradeoff lost in inquiry closure

- **Reference:** campaign `48993cfd-1808-4db6-a7b8-000fd5daba50`; M5 paired
  artifacts under `campaigns/evaluations/48993cfd-1808-4db6-a7b8-000fd5daba50/`;
  E9/E10 closure and checkpoint, followed by E11/E12 opening I3. The maintainer
  stopped the campaign. This entry assesses that scientific handoff, not a
  terminal assessment or the result of later training.
- **Observed tradeoff:** on 200 shared episode seeds, T1 achieved 130 successes
  and T2 116. At 6-14 cm, complete holds fell from 115/118 to 75/118. At
  14-20 cm, first reaches increased from 17/82 to 54/82 and complete holds
  from 15/82 to 41/82. Outer-radius paired wins were 37 versus 11 losses,
  a net gain of 26; inner-radius net loss was 40, yielding the aggregate
  loss of 14. Different training seeds limit attribution to the shaping term,
  but do not erase the measured candidate behavior.
- **Incorrect conclusion:** the PI said there was "no evidence of improved
  outer reach" and closed the IK-shaping route. Rejecting T2 as the better
  overall candidate was defensible; denying its outer-reaching improvement
  was not. The tradeoff was lost in the checkpoint and the next
  representation-conditioned inquiry.
- **Actual evidence access:** the public S6 SDK session
  `3ef30620-9d43-441e-88de-414372c3d70d` received both M5 artifact paths,
  `/research_evidence/episode_diagnostics`, `target_radius_cm`,
  `first_reach_step`, and full inline structural inventories in its feedback.
  The closure turn read brief lines 27-45 and the inquiry contract, then
  submitted and validated the close request; it did not inspect the M5
  diagnostic artifacts. The recent brief compaction did not hide those
  diagnostic references or require an inventory-registry lookup in that turn.
- **Harness attribution:** the immediate claim error was PI scientific
  judgment. Aggregate-first feedback and a session objective duplicating
  the PI's one-cycle closure condition are plausible amplifiers, not proven
  causes. Keep the observed startup and discoverability benefits; do not
  treat them as a solved interpretation or continuity problem. Add this
  verified failure case to the existing continuity backlog rather than a
  new scientific-judgment framework.

## 2026-10-02: derive inquiry objectives from the scientific question

- **Implementation commit:** the commit containing this entry,
  `Focus inquiry objectives on scientific questions`.
- **RCA:** I2's question asked whether outer reaching could improve and whether
  trajectories distinguished braking/stabilization from learning failure.
  Its closure condition specified one bounded intervention cycle. The launcher
  promoted the latter into the repeated session objective, making trial
  completion the operational target even though the scientific distinction
  remained visible elsewhere. M5's tradeoff was then reduced to a negative
  aggregate result. This identifies a framing gap, not a proven causal
  explanation of the wrong claim.
- **Prior-experiment comparison:** `f6fea61` and the restored baseline used
  "Advance ... toward its closure condition." `b4f1cdf` instead emphasized
  bringing the inquiry to the decision required by its closure condition and
  closing as soon as evidence supplied it. `6c73715` reordered active-inquiry
  context but retained that closure-based objective. `c0cfcb6` changed the
  broader handoff while also retaining it. Those combined experiments did
  not demonstrate sustained method development. None isolated the scientific
  question itself as the session objective.
- **Approved isolated change:** in `run_research.ps1`, derive the fresh inquiry
  session objective from `active_inquiry.question`, not
  `active_inquiry.closure_condition`: "Advance [inquiry] toward an
  evidence-supported answer to its scientific question: [question]."
  The closure condition remains unchanged and visible in the active-inquiry
  context; this does not weaken or bypass the closure contract.
- **Unchanged:** context ordering, action guidance, feedback, persona,
  scientific-model guidance, startup and goal-review objectives, inquiry
  permissions, session transitions, checkpoint/close schemas, brief rendering,
  scientific artifacts, and existing persisted session objectives. No
  hypothesis registry, reasoning checklist, mandatory measurement or retry,
  Runner scientific judgment, or training allocation change.
- **Observation criterion:** after a candidate regresses overall but improves
  the inquiry's targeted behavior, the PI accurately preserves gains,
  regressions, claim limits, and unresolved explanations in its decision and
  handoff, even if it rejects the candidate. Continuing, reframing, or closing
  remains its scientific choice.
- **Failure signal:** an aggregate negative result again becomes an unsupported
  claim of no mechanism improvement, or completion of a planned trial alone
  redirects to another recipe while the question remains unexplained.
  Fewer trainings, correct prompt rendering, or a successful policy alone
  do not establish improved scientific continuity.
- **Implementation checks:** 11 existing targeted prompt/phase-permission
  cases passed. The full launcher parsed. A read-only comparison evaluated
  the actual objective expressions and context functions: only the inquiry
  current-objective field changed, using the supplied question rather than
  closure-condition data; the original criterion remained in active-inquiry
  context. Startup, ordinary goal review, and terminal goal review objectives
  and rendered prompts were unchanged. No campaign loop or scientific
  operation was executed, and no instruction-wording tests were added.
- **Campaign observation / disposition:** implemented for observation; no
  campaign has been reset or restarted for this change. The specific effect
  is unassessed. Existing campaign state and pending requests are untouched.

## 2026-10-02: near miss after sustained inquiry development

- **Reference:** completed campaign `2381bcbf-72c1-4535-9334-7e0d753f356d`;
  authoritative M1-M4 artifacts, E4-E6 checkpoint/closure records, E7/E8
  promotion and assessment request, and terminal result `d12d794`.
- **Outcome and resources:** 195/200 official successes, one below the required
  196. One inquiry, three completed training runs, 362,496 completed steps,
  19 PI invocations, and 43.832647 AIU. T1 failed before training on a Windows
  file-permission error and was superseded by T2; it supplied no scientific
  evidence. An uncommitted maintainer backlog edit separately blocked the
  startup checkpoint until it was published in `2b7b9e1`; the preserved request
  then validated without changing campaign state or scientific content.
- **Scientific progress:** M3 compared T3 against T2 on shared episode seeds:
  190/200 versus 130/200, with 60 gains and no losses. M4 compared T4 against
  T3 on a fresh shared panel: 197/200 versus 188/200, with nine gains and no
  losses. Diagnostics informed an outer-target curriculum and then hold-credit
  forfeiture within the same inquiry, rather than a new inquiry for each trial.
- **Lost counterevidence:** the T4 fixed grid achieved 124/128 successes and
  126/128 first entries. Two failures never entered tolerance: 14 cm at
  -135 degrees and 20 cm at -157.5 degrees. Two entered but failed to hold:
  12 cm at -135 degrees and 14 cm at 22.5 degrees. The 12 cm failure was absent
  in T2; the 14 cm/22.5-degree failure was absent in T3. The positive matched
  panel gains did not erase these grid tradeoffs.
- **Actual handoff:** S3 read M3/M4 diagnostic lines 1-310 but described the M4
  read as full inspection. Its synthesis characterized the residual failures
  as hold/angle cases rather than non-entry. Fresh S4 closure and S5 goal review
  inherited that interpretation without reading the diagnostic artifacts.
  S5 claimed the remaining uncertainty was only protected-panel transfer and
  that no further development inquiry was justified. Best-known assignment
  did not require that terminal choice, and further measurement was available.
- **Readiness uncertainty:** 197/200 is a narrow observed pass, not assurance
  that another panel will meet 196/200. Illustratively, even a true 98.5%
  episode success probability gives about an 18.35% chance of fewer than 196
  successes in 200 independent episodes. The retained official record contains
  only aggregate outcome facts; it does not establish the exact physical
  mechanisms of the five official failures.
- **Harness attribution / disposition:** the question-based objective was
  present in both inquiry sessions, and sustained development is consistent
  with its intended effect, not proof of causation. Brief compaction and
  inventories did not hide the diagnostic references. Startup did not become
  endless preparation, and shorter startup training was not yet implemented.
  Retain the recent changes provisionally. The next substantive target is
  faithful counterevidence handoff and assessment readiness, not another
  startup requirement, numerical scientific gate, or Runner judgment.

## 2026-10-02: permit shorter startup training requests

- **Implementation commit:** the commit containing this entry,
  `Allow shorter startup training requests`.
- **RCA:** the maintainer allocation was enforced as exact equality in every
  training phase. Startup therefore could not request a shorter learning
  observation even though training is optional there.
- **Approved tactical change:** during startup, accept a positive integer
  request up to the maintainer's per-run allocation, whose default remains
  120,000. The maintainer selected a requested-step ceiling, not a strict
  executed-step ceiling. Inquiry requests still require the full allocation.
- **Acceptance and execution:** proposal validation, new-operation acceptance,
  accepted-request checks, and training dispatch apply the current session's
  allocation contract. Dispatch preserves the accepted requested steps instead
  of replacing them with the ceiling. Frozen request identity, repair intent,
  maintainer overrides, and completed-result publication remain unchanged.
- **PI contract:** startup prompts identify the ceiling and permit shorter
  positive requests; other phase allocation prompts remain unchanged.
  `contracts/program.md` and `contracts/instruments.md` state the same contract.
  No new request field, automatic run length, training requirement, phase
  transition, scientific implementation, dependency, or cumulative budget.
- **Rollout rounding:** completed steps may still exceed requested steps at
  the learning algorithm's existing rollout boundary. This is not permission
  to request more than the maintainer's startup ceiling.
- **Implementation checks:** 31 targeted allocation, accepted-request,
  dispatch/publication-recovery, and phase-contract cases passed. Touched-file
  Ruff and formatting checks passed, and the full launcher parsed without
  executing its campaign loop. No instruction-wording tests were added.
- **Campaign observation / disposition:** implemented for observation, not a
  demonstrated scientific improvement. No campaign operation is run, reset,
  or resumed by this change. Counterevidence preservation and official-assessment
  readiness remains the next substantive design topic.

## 2026-10-03: unchanged startup policy fails official assessment

- **Reference:** campaign `d7080d95-e5e9-4077-a667-f75ddc16876b`;
  completed T1-T3, M1-M5 and E1-E15 records; terminal publication `cf2bb98`.
  The detailed maintainer report is
  `docs/research-overview/robot-campaign-d7080d95-20261002.html`.
- **Outcome and resources:** 194/200 official successes, two below the required
  196. Three inquiries, three completed training runs, 362,496 completed
  steps, 26 PI invocations, 63.153858 AIU and 1,745.52 seconds of recorded PI
  invocation time. No failed execution attempt was recorded. M5's artifact
  path was rejected before dispatch and corrected without changing intent.
- **Scientific results:** T1 achieved 151/160 on the original development
  panel. The two tested interventions regressed: feasibility observations
  produced 80/160; branch-aware reward shaping produced 28/160. Paired
  comparisons found no gains and respectively 71 and 123 losses. These are
  negative results for the tested recipes, not proof that every related
  representation or reward method is invalid.
- **Readiness pivot:** S8 inspected M5's detailed artifact and summarized
  radius bins and all seven failures. Unchanged T1 achieved 393/400 on fresh
  seeds. The PI treated this as sufficient to stop exploration and request
  assessment. The two distinct T1 development panels contained 544/560
  successes, or 97.14%; repeated original-panel evaluations add no independent
  cases. Only three of the fifteen permitted inquiries had been used.
- **Measurement and claim limits:** M2 and M5 used identical diagnostic module
  bytes. M2 reproduced the original panel outcomes, and success flags matched
  the uninterrupted-hold criterion. The seven M5 failures remained in the
  negative-angle shoulder-limit sector. The recorded nearest analytic branch
  is not a direct observation of the policy's internal decision. The aggregate
  official record does not identify the mechanisms of its six failures.
- **Disposition:** the repeated near miss concerns assessment calibration,
  but not the earlier partial-file inspection error. It does not establish
  that recent harness changes caused the official failure. The readiness
  guidance below was absent during this campaign.

## 2026-10-03: goal-review assessment-readiness guidance

- **Implementation commit:** `e4736da`,
  `Clarify assessment readiness in goal review`.
- **RCA and approval:** two campaigns justified official assessment from
  narrow above-target development results while consequential residual
  evidence or uncertainty remained. The maintainer approved the three-sentence
  goal-review block and then authorized its application after the campaign
  stopped.
- **Exact scope:** `New-ScientificSessionPrompt` in `run_research.ps1` adds the
  approved block after action guidance and before source routing. It applies
  to ordinary and inquiry-capped goal review. Checkpoint-only transitions,
  startup and inquiry prompts remain unchanged.
- **Guidance:** distinguish the strongest available candidate from assessment
  readiness; consider residual failures, regressions and measurement
  uncertainty; do not treat inquiry closure or an above-target development
  score as automatic justification for assessment.
- **Unchanged contracts:** objectives, phase permissions, request schemas,
  operation validation, model roles, transitions and Runner behavior are
  unchanged. There is no numerical readiness gate, required replication,
  mandatory artifact sequence or Runner scientific judgment.
- **Implementation checks:** the full launcher parsed without executing its
  loop. A seven-context rendering comparison verified the exact addition in
  both goal-review contexts and identical output in the other five contexts.
  The three existing targeted checkpoint-frontier cases passed. No
  instruction-wording tests or new test infrastructure were added.
- **Documentation:** the process overview marks the change as implemented.
  Campaign reports preserve the fact that it was absent during their runs.
  HTML wording uses short technical sentences and retains the existing
  qualification about unverified formal ASD-STE100 compliance.
- **Disposition:** initially implemented for observation, then withdrawn by
  maintainer decision and rolled back in the working tree, as recorded below.
  Scientific effect remains unassessed; withdrawal is not experimental
  disproof. The original implementation did not start, resume or reset a
  campaign, or change campaign evidence or scientific code.

## 2026-10-03: bounded Copilot runtime shutdown

- **Implementation commit:** `2e897c7`.
- **RCA and approval:** campaign `3ac5a413` stopped at the PI-to-Runner
  handoff. S6 completed its final turn, destroyed its session, and prepared
  the CLI runtime for shutdown at 08:13:00 CEST. The adapter and runtime
  remained alive. The saved measurement request was not accepted or executed,
  and the invocation usage row was not written. The exact blocked SDK call
  was not established. The maintainer stopped the campaign and approved this
  repair.
- **Harness defect:** the PI-turn timeout did not bound session disconnection
  or client shutdown. The launcher waited for the adapter process to exit.
- **Exact scope:** `runner/copilot_adapter.py` uses explicit client lifetime
  management. Abort, when requested, session disconnection, and graceful
  client shutdown share a 30-second timeout. A timeout or cleanup error is
  reported before the SDK force-stops only this client's owned runtime.
  Forced cleanup has a separate 10-second timeout.
- **Preserved behavior:** successful forced cleanup preserves the original
  PI exit status. Failed forced cleanup reports a runtime failure. Usage is
  recorded after cleanup. Session data and saved operation requests are not
  deleted, rewritten, or regenerated. There is no replacement PI session,
  automatic campaign restart, or change to scientific operation validation.
- **Implementation checks:** targeted adapter cases cover normal shutdown,
  stalled disconnection and client shutdown, cleanup errors, failed forced
  cleanup, stalled abort, and cancellation during the turn or cleanup.
  They check usage
  recording, saved artifacts, and the original PI result without starting
  a real session.
- **Disposition:** provisionally retained operational repair, not a
  scientific intervention.
  Campaign-level behavior remains unassessed. The startup-baseline review
  remains pending; this repair does not change its training budget.

## 2026-10-03: withdraw goal-review readiness guidance

- **Decision / scope:** the maintainer approved rollback of the three-sentence
  goal-review readiness guidance from `e4736da`, while retaining shutdown
  repair `2e897c7`. The coordinator confirmed that a separate agent removed
  the exact nine-line readiness block and its prompt inclusion from
  `run_research.ps1`. The rollback is complete in the working tree, not yet
  committed. Historical entries and backlog findings remain preserved.
- **Implementation checks:** the coordinator reported that PowerShell
  parsing and whitespace checks passed without executing the launcher.
  Shutdown repair `2e897c7` and campaign artifacts were untouched.
  This log-only update changes no executable behavior. These checks and
  the historical implementation checks above are not evidence of scientific
  effectiveness.
- **Scientific limits:** campaign `3ac5a413` does not establish that the
  readiness guidance caused termination or was experimentally disproven.
  The training-centered candidate-publication path and `no_credible_route`
  terminal mechanism predate `e4736da`.
- **Disposition / boundary:** this readiness approach is withdrawn and rolled
  back in the working tree. A replacement is to be designed later, not
  approved or implemented now. Independent frozen-policy publication remains
  a proposal, not an approved or implemented change. The earlier
  operational-block versus scientific-exhaustion proposal is superseded by
  the maintainer clarification below; exhaustion is not an intended endpoint.
  Shutdown repair remains provisionally
  retained with its existing scientific disposition. The full 120,000-step
  startup-budget review remains pending. No state recovery, reset, new
  experiment, registration fix, isolation change or banner fix is authorized
  by this decision.

## 2026-10-03: PI-requested terminal outcome after wrapper measurements

- **Reference:** campaign `3ac5a413-ac79-4850-9c3a-83a3f0b41457`;
  terminal E19 in S10. See the
  [detailed maintainer report](research-overview/robot-campaign-3ac5a413-20261003.html).
- **Terminal RCA:** the PI explicitly requested `no_credible_route`.
  This terminal outcome was not maintainer-triggered, an inquiry-cap stop,
  a crash or an official benchmark failure. The earlier S6 shutdown stall
  recorded above is a separate operational event. The terminal interface
  lacks an explicit operational-block outcome; Runner records PI decisions,
  not scientific judgments.
- **Operations and resources:** four of fifteen inquiries, ten sessions,
  eight measurements and two training operations. T1 and T2 each requested
  120,000 steps and completed 120,832, for 241,664 completed steps in total.
  Recorded usage is 34 invocations and 94.397128 AIU. The stranded S6
  accounting row is absent, so these records are not guaranteed complete
  billing. Elapsed time is omitted because console elapsed and timestamps
  disagree.
- **Development evidence:** ordinary T1 `checkpoint100352` scored 151/160.
  M6's wrapper scored 160/160; M7's frozen wrapper also scored 160/160.
  Both wrapper measurements used the same reused development panel. M7 is
  not independent confirmation, and neither result is official success.
- **Publication boundary:** M8 found no registry binding for the wrapper and
  no dedicated registration operation. It did not prove that every possible
  authorized producer route was exhausted. Standard candidate publication
  is training-centered. Validators accept zero completed steps and the PI
  owns producer code, but an export-only route is undocumented and untested
  end-to-end. These checks do not establish an authorized or proven workaround.
- **Terminal state and artifacts:** M7 model and runtime artifacts still
  exist and match their measured hashes. The campaign remains terminal, with
  no official assessment, 48 registered T1/T2 candidates and no best-known
  role. These facts do not authorize recovery or a new operation.
- **Interpretation / disposition:** development success was followed by a
  PI-reported publication barrier, not an official test of the wrapper.
  The record supports neither exhaustive route closure nor a causal claim
  against `e4736da`. Readiness withdrawal is a maintainer decision; shutdown
  repair remains provisionally retained, not scientifically validated by
  this outcome. No campaign or implementation change is made by this entry.

## 2026-10-03: reject scientific-exhaustion outcomes

- **Maintainer clarification:** scientific exhaustion / `no_credible_route`
  is rejected as a valid campaign outcome. Remove it from future design;
  do not preserve a supposedly genuine scientific-exhaustion endpoint.
  This supersedes the earlier proposal to distinguish operational-block
  from scientific-exhaustion endpoints.
- **Historical fact / runtime:** the PI requested E19 `no_credible_route` in
  S10 of campaign `3ac5a413`. That record remains accurate and the campaign
  remains terminal. The runtime still contains this outcome. Requested
  removal has not been patched; historical recording is not endorsement.
- **Execution limit:** the current fifteen-inquiry cap is temporary, not a
  scientific decision signal. The maintainer intends to remove it when the
  scientist is ready. Cap removal is not implemented.
- **RCA / scope:** the requested bounded code/instruction RCA is now reviewed
  and complete, as reported by the coordinator. This tracking session records
  those findings without further code or SDK investigation. This batch rolls
  back only `e4736da` readiness guidance; outcome removal and cap decoupling
  remain unimplemented.
- **Origin:** at local conversation turn 264, the user explicitly said fifteen
  inquiries was only test-safety. The assistant added policy success or
  establishing no credible route as alternative campaign objectives to avoid
  endless inquiry. Core commit `034daed` and lifecycle commit `6d6d41e`
  implement that unrequested alternative objective.
- **Instruction and execution path:** `contracts\program.md:19-21,63`,
  `contracts\instruments.md:313-318` and `run_research.ps1:1099` explicitly
  instruct `no_credible_route`. `runner\protocol.py:779-805` accepts
  the action with a nonempty reason. `runner\run_experiment.py:774-788`
  writes `terminal_state`; `run_research.ps1:1058-1073` breaks the loop.
- **Separate cap violation:** `runner\protocol.py:837-844` blocks
  goal-review measurements at the cap. `run_research.ps1:759-769` forces a
  terminal decision. Actual E19 at four of fifteen inquiries was not
  cap-triggered.
- **Readiness-guidance limit:** `e4736da` sought to prevent premature official
  assessment after narrow above-target development results. It neither
  introduced nor removed `no_credible_route`; its causal effect on E19 is
  unproven. The rejected decision option and training-centered publication
  remain after the readiness rollback.
- **Disposition / boundary:** independent frozen-policy publication remains
  a proposal, not approved or implemented. Shutdown repair `2e897c7` remains
  provisionally retained. Backlog findings and historical entries remain
  preserved. The full 120,000-step startup-budget review remains pending;
  campaign recovery and other code changes are not authorized by this
  log update.

## 2026-10-03: remove invented ending and isolate inquiry cap

- **Approval and order:** after the exact code/instruction RCA, the maintainer
  approved the repair. The main overview and campaign report were updated
  before runtime edits. Implementation and directly affected checks are complete.
- **Failure:** the assistant changed goal-directed research into either
  satisfying the goal or establishing that no credible route remained.
  Prompts and contracts exposed that invented ending. The PI selected it
  after encountering an artifact-publication barrier; the Runner recorded
  the terminal state and the launcher stopped.
- **Separate cap error:** the temporary inquiry cap also restricted
  goal-review measurements and forced a terminal decision. It must only
  pause execution resumably. Actual E19 at four of fifteen inquiries was
  not cap-triggered.
- **Approved scope:** remove the invented action from future requests and
  instructions; separate the cap from scientific decisions and instrument
  permissions. Preserve E19, campaign state and evidence. Keep the current
  cap value, training allocation and shutdown repair.
- **Other boundaries:** independent frozen-policy publication remains a
  proposal. No campaign recovery, reset, training or assessment is authorized.
  The maintainer also reauthorized a bounded SDK check of PI read controls
  for maintainer documents. Required scientific Markdown must remain readable;
  enforcement limits must be stated, not hidden.
- **Implementation:** future conclusion requests permit only official
  assessment. Obsolete pending conclusions are rejected before mutation.
  Existing E19 and terminal records remain readable; no migration or reopening
  is performed. The launcher pauses at the cap only after active inquiry and
  session work finish. Goal-review measurement permissions no longer depend
  on the count. Only an explicit maintainer increase at the paused boundary
  can change the persisted cap after startup.
- **Read controls:** SDK `PermissionRequestRead` and explicit shell-reader
  targets use the existing reserved path matcher. `RESERVED_SCRIPT_PATHS`
  includes maintainer documents and harness source patterns. Scientific
  Markdown remains readable. The initial implementation also denied reads of
  PI-owned reserved entry points. The correction below restores their reads;
  execution restrictions are unchanged.
  Rejections give visible feedback. Arbitrary code and broad searches are not
  filesystem-isolated; no OS sandbox is claimed.
- **Checks and limits:** the initial four-file targeted run found twelve
  temporary Git-init permission failures and an unrelated malformed training
  fixture missing `initialization`. Neither is repaired by this change.
  The new explicit-reader bypass was fixed and directly affected old reader
  expectations were updated. The final focused run passed 209 tests, with
  the thirteen identified unrelated cases deselected. Touched-file Ruff
  checks, launcher parsing, HTML structure, theme and local-link checks
  passed. Campaign state and results SHA256 values are unchanged. These
  checks do not establish scientific effectiveness or OS-level isolation.
- **Disposition:** implemented for observation. No scientific effect
  is claimed from this operational repair.
- **Publication:** the maintainer authorized commit and push of the repair,
  tests and documentation. The maintainer will reset the campaign separately.

## 2026-10-03: restore the successful-reference startup text exactly

- **Approval:** the maintainer rejected new or adapted instructions and
  approved restoring the two original startup blocks verbatim.
- **Source:** tag `inquiery-harnes-success-2`, commit `7ce2850`, the successful
  reference for campaign `77a975a5` that began with a candidate-free dynamics
  measurement. `3a8f034` identifies the annotated tag object, not the commit.
- **Exact scope:** restore only the startup active-inquiry description and
  startup session objective in `run_research.ps1`. Withdraw the two-string
  October 2 clarification. No whole-commit rollback or replacement wording.
  The preliminary scientific-model instructions and the startup section in
  `contracts/program.md` already match the reference and are not changed.
- **Retained:** startup training below the maintainer allocation remains
  allowed. Training acceptance and dispatch, phase permissions, scientific
  implementation, other session instructions, read controls, and the removal
  of the invented campaign ending are unchanged.
- **Observation target:** establish whether a fresh startup builds its first
  scientific direction from the physical model and unresolved questions,
  rather than treating an unchanged-recipe baseline as a prerequisite.
  This is one text-restoration trial, not a new scientific requirement.
- **Evidence limits:** the original wording also occurred in training-first
  openings and was sometimes read as requiring a planning-only checkpoint.
  Exact source restoration does not guarantee identical PI behavior.
- **Campaign boundary:** existing state and requests are not rewritten.
  A saved session retains its existing objective. This comparison requires
  a fresh campaign started by the maintainer; no reset or launch is performed.
- **Checks:** both restored strings match the reference exactly. The launcher
  parses, the existing startup phase-contract case passes, and the touched
  files pass the whitespace check. No new test or instruction gate is added.
- **First observed trial:** stopped fresh campaign `2573991c` loaded the
  restored objective but requested an unchanged-recipe 120,000-step PPO
  baseline before empirical investigation. S1 named hypotheses, then made
  baseline training a prerequisite in both its initial inquiry proposal and
  accepted T1 request. The restoration did not recover the intended behavior.
- **Context comparison:** actual session inputs were not identical to the
  successful campaign. Instrument documentation, inventory context,
  training-allocation wording, and the generated scientific model differ.
  The latest model also incorrectly claims two joint-limit-feasible IK
  branches at every official target: at 20 cm and 150 degrees, one shoulder
  solution is 172.33 degrees, beyond the 170-degree limit. The archived M1
  probe records only one feasible branch there. This identifies a changed
  scientific input and an error, not a causally isolated harness defect.

## 2026-10-03: keep PI-owned scientific files readable

- **RCA and approval:** the read guard reused the execution-denial matcher
  without first checking PI ownership. It therefore denied inspection of
  scientific entry points that the PI owns. The maintainer approved a
  separate, minimal correction; the older training-first startup issue is
  not attributed to this later read restriction.
- **Exact change:** `file_read_denial` returns no denial for paths accepted
  by the existing PI-ownership helper, then applies the reserved matcher.
  The same helper serves SDK read/view and explicit shell-reader requests.
  Execution restrictions and protected-file ownership checks are unchanged.
- **Scope:** no SDK configuration, new permission list, dependency, startup
  instruction, scientific implementation, or campaign artifact changes.
  Existing parameterized cases cover owned reads, including reserved
  filenames inside the lab, and a protected scenario file that must still
  be denied. The directly affected documentation states the ownership rule.
- **Disposition:** read-access defect corrected. This is not a startup
  behavior fix or a claim of filesystem isolation.
- **Checks:** all 144 adapter cases pass, including existing execution
  restrictions and reserved maintainer reads. Touched-file Ruff and
  whitespace checks pass. Campaign state and request SHA256 hashes are
  unchanged. The runtime delta is two added lines.

## 2026-10-04: restore only two historical scientific passages

- **RCA:** `eb1118e` restored two startup strings, but fresh campaign
  `2573991c` still requested an unchanged-recipe baseline before empirical
  investigation. Its request named competing mechanisms while admitting
  that training tested the current recipe, not either mechanism separately.
  The successful opening instead used a candidate-free physical probe to
  distinguish stabilization capability from learning and coverage. The
  two-string restoration did not recover that decision process.
- **Opus 5.5 review:** the same public startup wording produced both probe-first
  and training-planned or training-requested openings. `6d6d41e` removed the
  explicit non-default-operation principle and measurement-purpose passage;
  `7cff9f6` restored causal-memory meanings but not these passages. Both were
  already absent at the successful startup base, so their absence alone is
  not an established cause of the behavioral divergence.
- **Sonnet 5.5 Meta-Prompting review:** the actual successful startup base is
  `e26fbc4`, not the campaign-end tree containing PI-authored scientific
  changes. Equal phase prompts do not establish equal full inputs: the
  generated physical model and available implementation reads differed.
  Later read denials may affect the latest model, but cannot explain earlier
  training-first drift. The separate owned-read correction is not a startup
  repair.
- **Approval and exact source:** after rejecting the assistant's newly proposed
  candidate-absence sentence, the maintainer approved restoring only the two
  historical passages verbatim from `6d6d41e^:contracts/program.md`:
  the operation-selection paragraph at lines 144-147 and the measurement-purpose
  paragraph at lines 177-178.
- **Placement and boundary:** restore both paragraphs in `contracts\program.md`
  under Inquiry work. The original lifecycle forced baseline training before
  these inquiry principles applied. No startup-specific applicability clause
  or new candidate-absence rule is added. The original "causal research map"
  wording is retained without reviving a former artifact or schema.
- **Unchanged:** launcher prompts, phase permissions, training allocation,
  read controls, scientific implementation, and campaign state and requests.
  No test infrastructure, campaign reset, launch, or scientific operation.
- **Disposition:** both passages restored verbatim. Startup behavior remains
  unresolved; no scientific effectiveness is claimed. The tracking log and
  existing overview HTML were updated before the instruction restoration.
- **Checks:** both passages match their historical source exactly. Removing
  only those two additions reproduces the prior instruction file. Campaign
  state and request SHA256 hashes are unchanged.

## 2026-10-04: clarify startup purpose and instruction delivery

- **Approval:** the maintainer approved a change, not another historical
  rollback. The complete existing persona must start every prompt and must
  not disappear from continuations, retries or repairs. Startup must explicitly
  include reusable scientific tools without imposing the same tool-building
  sequence on every campaign.
- **Original purpose:** the agreed redesign describes an initial scientific
  session that establishes the most credible direction from the human goal,
  physical model and available evidence, then chooses the first useful
  scientific action. A baseline is optional. Tool and method design are
  possible routes, not compulsory startup deliverables.
- **Observed failure:** startup `c7040992` read context, named competing
  explanations and submitted E1 without empirical investigation. Its shell
  action validated checkpoint JSON. S2 opened a baseline inquiry and S3 trained
  and measured. The record correctly distinguished absent policy artifacts
  from its own session summary. The failure was a planning-only interpretation,
  not demonstrated confusion between saved weights and a scientific record.
- **Instruction RCA:** `cd579a6` added the checkpoint-before-goal-review wording.
  `eb1118e` later restored that wording and removed the October 2 distinction
  between scientific investigation and formal inquiry opening. The shared
  prompt also displayed inquiry framing during startup, placed the persona
  after context and allocation, and omitted it from the preliminary retry.
  The Copilot adapter added a separate, redundant scientific instruction block.
  These are verified instruction defects, not an isolated cause of every
  training-first opening.
- **Approved implementation:** use the agreed startup objective with initial
  direction, reusable scientific tools and PI-owned methods where needed,
  first-action selection, and a record of actual work and remaining uncertainty.
  Omit startup inquiry framing. Keep the full persona first. Remove scientific
  instructions from the adapter instead of copying redundant text elsewhere.
  Shorten the startup allocation line without changing its value or validation.
- **Record terminology:** human-facing prompts and contracts distinguish the
  scientific session record from a policy checkpoint. The existing `checkpoint`
  operation and `pi_checkpoint` fields remain unchanged. The Runner checks
  operational contracts, not scientific adequacy.
- **Access boundary:** preliminary can read scientific sources under
  `robot_learning/`, including protected benchmark implementation. Later phases
  retain reserved-read restrictions. SDK reads and explicit shell readers use
  the same phase distinction. Maintainer documents and harness files remain
  reserved; write and direct-execution restrictions remain unchanged.
- **Language guidance:** used the repository's
  `.github\skills\simplified-languages` guide for the new HTML explanation.
  The guide is readable locally but is not registered in this CLI session.
  The maintainer's untracked skill files were not modified. The supplied checker
  found no structural errors and flagged two uses of the technical noun
  "training." Its vocabulary checks do not certify formal STE compliance.
- **Boundary:** no new phase, marker, schema, dependency, scientific-adequacy
  gate, campaign recovery, reset or execution. Campaign artifacts and existing
  saved objectives are not rewritten. Update this log and the overview HTML
  before code changes; use only directly affected existing checks.
- **Checks:** 171 directly affected existing cases passed, with 36 unrelated
  phase cases deselected. Touched-file Ruff passed. The launcher parses.
  Offline rendering exercised scientific initial/retry prompts and the actual
  preliminary initial/retry flow with mocked operations. Every prompt starts
  with the complete persona, and startup omits active-inquiry framing.
  The complete persona is unchanged from the committed launcher. HTML structure
  and scoped whitespace checks passed. Campaign state, scientific model,
  parameters and completed-operation history retain their original hashes;
  the operation request remains absent. No source-wording test or new test
  infrastructure was added.
- **Disposition:** implemented for observation. Scientific effectiveness
  remains unassessed.

## 2026-10-04: make the full process overview coherent

- **Reason / approval:** the maintainer requested a bounded review of the
  full overview, not another harness intervention. The old "Current harness
  changes" heading mixed implemented behavior, withdrawn revisions and
  proposals. Red/green labels implied incompatible meanings, and notes mixed
  current guidance with historical observations and decisions.
- **Exact scope:** only
  `docs\research-overview\robot-learning-overview-20261002.html` and this
  documentation-tracking entry. Existing edits in both documents were
  preserved. No skill was modified or registered.
- **Organization / vocabulary:** label the current goal, process, ownership,
  operation and evidence sections explicitly. Separate the implementation
  inventory, maintainer decisions, folded historical revisions and checks,
  unresolved work, and historical campaign reports. Define Implemented,
  Historical, Withdrawn, Decision, Observation, Open, Proposal and Deferred.
  All status badges use one neutral treatment. Color does not encode
  scientific success or failure; implementation and scientific effect are
  separate claims. Preserve the self-contained Clawpilot theme and navigation.
- **Stale claims corrected:** the report index ends at `3ac5a413`; the working
  state and brief now concern `c7040992` with no terminal state. Root campaign
  files are not permanent sources for the older report. Keep M7's path and
  hashes as recorded historical references, not current-file assertions.
  Move the withdrawn readiness block's residual-failure guidance out of the
  current-runtime explanation. Mark old code line references, startup wording,
  relocation/read-access notes and engineering checks as historical or
  superseded. The rollback chronology distinguishes the initial uncommitted
  removal from the later recorded publication in `b275861`.
- **Current behavior retained:** startup establishes the most credible initial
  direction and first useful action, with reusable scientific tools and
  PI-owned methods where needed. The full unchanged persona leads every
  phase prompt, including continuation, retry and repair. Startup has no
  Active inquiry section or old handoff instruction. The adapter handles
  runtime and permissions. Scientific session records remain distinct from
  saved policy weights; `checkpoint` and `pi_checkpoint` are unchanged.
  Preliminary reads include all scientific sources under `robot_learning`,
  including protected benchmark implementation. Later reserved reads,
  maintainer-file reservations, writes and direct-execution restrictions
  remain as implemented. No mandatory instrument or scientific-adequacy gate
  is added or described as current policy.
- **Evidence / retained information:** cross-check current claims against
  `AGENTS.md`, the program and instruments, launcher and adapter source,
  this log, the relevant historical design, and linked campaign records.
  Preserve original report links and IDs, commit and campaign references,
  quantified observations, M7 hashes, decision rationale, uncertainties and
  unimplemented proposals. Campaign observations remain evidence-limited,
  not a controlled comparison or proof of a harness change's effectiveness.
- **Concurrent publication:** source edits were uncommitted at the initial
  snapshot. External commit `7f86168` appeared during this review and includes
  the startup source batch. Their contents still match the initial hashes.
  The maintainer subsequently confirmed commit and push as `7f86168`,
  `Clarify startup purpose and instruction delivery`, with
  `origin/inquiry-centered-lifecycle` verified to match. Exactly the six
  core/contract/test files were included; neither documentation file was
  staged or changed by that publication.
  Update publication wording without reverting or changing those sources.
  This documentation review did not stage, commit or push anything.
- **Validation:** balanced HTML, 20 unique IDs, 36 local/internal links and
  ARIA references pass inspection. Original IDs, links, commit/campaign
  references and recorded hashes remain. Theme variables and the initial
  theme script are unchanged; component colors use Clawpilot variables.
  Browser checks exercised the actual page in light and dark themes at
  320, 760 and 1,280 pixels, including expanded details, theme toggling and
  internal navigation. No content overflow occurred outside intended
  scroll containers. A fresh load produced no JavaScript console errors.
  Direct `file:` access was blocked, so an attached localhost server was
  used without installing packages. Scoped whitespace checks pass. Formal
  ASD-STE100 compliance is not claimed.
- **Preservation / disposition:** at completion of the pre-launch review
  (4 October, 10:38 CEST), campaign state, scientific model, parameters and
  completed-operation history matched the supplied initial SHA-256 values;
  the operation request was absent. Existing source, contract and test
  contents were unchanged by this work. This is a documentation-only correction.
  Scientific effectiveness remains unassessed. This review executed no
  campaign, training, assessment, viewer, repository-wide test or dependency
  change. The maintainer subsequently reported starting a campaign themselves.
  Later campaign-artifact or HEAD changes can be external maintainer or Runner
  activity and are not covered by the pre-launch preservation check. No live
  campaign or HEAD inspection was done after that report. Historical claims
  retain their dated original references; no live findings were incorporated.

## 2026-10-04: remove startup action and training cues

- **RCA and approval:** the latest campaign went directly from startup context
  to an unchanged-recipe full-allocation training request. The phrase "first
  useful scientific action" supplied no scientific criterion for usefulness,
  while the standalone training ceiling gave one operation a concrete,
  prominent cue. The maintainer approved removing both from the startup prompt
  and rejected replacement budget guidance or another training-specific line.
- **Exact change:** the startup objective retains initial-direction scientific
  work, reusable tools and PI-owned methods. It no longer selects a "first
  useful scientific action" or requires a record summary in that objective.
  Startup displays no training allocation. Inquiry allocation wording and all
  mechanical allocation validation remain unchanged.
- **Documentation:** `contracts/program.md`, the lifecycle redesign and the
  canonical HTML describe the corrected startup purpose. Earlier tracking
  entries remain unchanged as history of the superseded wording.
- **Boundary:** no operation type, sequence, training size, measurement,
  implementation, or adequacy rule is prescribed. No allocation behavior,
  schema, dependency, campaign artifact, scientific implementation, or Runner
  judgment changes.
- **Checks:** the launcher parses successfully. Active startup source, program
  and lifecycle descriptions no longer instruct a "first useful scientific
  action" or display a startup "Training ceiling." The already-running campaign's generated
  `campaigns/brief.md` retains its original saved objective and was not
  rewritten. No campaign, training, reset, assessment, or operation executed.
- **Disposition:** implemented for observation. Scientific effectiveness
  remains unassessed.

## 2026-10-04: enforce documented ownership of `docs/`

- **Bug:** `b275861` declared the whole `docs/` tree human-owned and reserved
  from PI access, but `runner/protocol.py` continued to classify only
  protected source paths and `tests/` as human-owned. The existing ownership
  registry test exposed the mismatch during campaign training validation.
- **Impact:** one protected-harness validation failure was routed through the
  operation repair flow and repeatedly superseded the same unchanged training
  request. The disposable campaign, its generated artifacts and its 261
  campaign commits were removed; this entry is the retained record of the
  failure.
- **Correction:** add `docs/` to the Runner's human-owned prefixes. This aligns
  delta validation and clean-worktree enforcement with `AGENTS.md`. Existing
  adapter restrictions already keep `docs/` unreadable and unwritable by the
  PI, so no permission expansion or scientific instruction changes.
- **Boundary:** no campaign state, operation request, PI-owned scientific file,
  training behavior, recovery behavior, HTML overview, schema or dependency
  changes.
- **Disposition:** ownership drift corrected as a harness bug. The repeated
  reaccept loop remains a Runner defect to address separately.

## 2026-10-04: fully reserve the human-owned test surface

- **Problem:** `tests/` was protected from PI modification and scientific
  deltas, but the PI adapter still allowed test source inspection and targeted
  `pytest` execution. That exposed human-owned validation semantics despite the
  ownership boundary.
- **Correction:** reserve the complete `tests/` tree from PI reads in every
  phase and reject every direct PI `pytest` invocation. Runner-owned validation
  remains available and unchanged.
- **Boundary:** no PI-owned scientific path, training allocation, evaluation
  panel, campaign state, operation contract, dependency, or scientific
  instruction changes.
- **Disposition:** retained as a boundary-consistency correction.

## 2026-10-04: structural ownership-boundary refactor

- **Problem:** human contracts, hidden benchmark code, Runner machinery,
  PI-owned science and generated campaign evidence were mixed across
  `research/` and `robot_learning/`, forcing ownership enforcement to depend on
  scattered exception lists.
- **Correction:** move the approved surfaces into `contracts/`, `benchmark/`,
  `runner/`, `pi_workspace/`, `campaigns/` and unrestricted PI-owned
  `robot_learning/` prefixes, and mechanically migrate recorded path strings.
- **Boundary:** no scientific behavior, allocation rule, lifecycle semantic,
  physics, reward value, success criterion, observation layout, dependency or
  official assessment changed. The failed in-flight campaign was removed
  rather than migrated.
- **Disposition:** retained as a structural boundary correction; scientific
  effectiveness is not assessed.

## 2026-10-05: port baseline-distinct-episodes recipe to split layout

- **Problem:** the reusable `baseline-distinct-episodes-v2` tag described a
  valid scientific recipe, but its source commit predated the ownership
  restructure and therefore exposed the old `research/` and
  `robot_learning/scenario/` paths to `RecipeRef` validation.
- **Correction:** preserve the complete recipe delta under the current
  `robot_learning/scenario/` and `robot_learning/training/` layout, including
  the 11-value observation representation, closeness-potential reward and
  0.14-0.20 m training distribution. Publish the current-layout recipe as
  `baseline-distinct-episodes-v3`.
- **Boundary:** no Runner behavior, human task contract, evaluation semantics,
  training allocation, campaign state or campaign execution changed.
- **Disposition:** retained as a recipe provenance and path-compatibility
  correction; scientific effectiveness remains unassessed.

## 2026-10-05: fail closed on launcher snapshot enumeration errors

- **Problem:** an ignored `.py-git-probe/` test artifact contained a directory
  with an unreadable Windows ACL. The launcher trust snapshot attempted to
  traverse it, emitted a non-terminating access error and continued into PI
  campaign preparation with an incomplete protected-file inventory.
- **Correction:** exclude the known Git probe root with the other generated
  tool directories and make every unexpected directory-enumeration error
  terminate snapshot construction.
- **Boundary:** no campaign operation, training, evaluation, scientific
  implementation, task contract, allocation or lifecycle policy changed.
- **Disposition:** retained as a fail-closed launcher integrity correction.

## 2026-10-05: align startup context with operation validation

- **Problem:** the generated research brief described an active startup session
  as goal review and did not expose the campaign-specific evaluation artifact
  root. The PI consequently attempted an inquiry that startup validation
  rejects, then used a non-scoped Python-module artifact path that it could not
  derive from its visible context.
- **Correction:** report the actual session kind and mechanically available
  operation kinds, publish the exact campaign evaluation root, clarify the
  Python-module path contract and include the required prefix in validation
  feedback.
- **Boundary:** no lifecycle transition, operation permission, scientific
  choice, campaign state, training, evaluation or Runner judgment changed.
- **Disposition:** retained as a PI-context and validator-alignment correction.

## 2026-10-05: exclude active Runner state from scientific deltas

- **Problem:** the ownership refactor moved campaign state under the wholly
  human-owned `runner/` prefix while retaining an older scientific-delta
  predicate that re-included Runner-owned paths when they were also
  human-owned. Starting any bounded session therefore made the Runner's own
  uncommitted state update appear as an invalid PI scientific change.
- **Correction:** exclude Runner control and memory paths unconditionally from
  scientific deltas. Uncommitted Runner source and every other human-owned path
  remain rejected.
- **Boundary:** no operation permission, lifecycle transition, scientific
  implementation, campaign state, training, evaluation or Runner judgment
  changed.
- **Disposition:** retained as an ownership-refactor regression correction.

## 2026-10-05: withdraw startup action and training-cue removal

- **Decision:** the maintainer reviewed the five harness changes immediately
  preceding the ownership restructure. The latest behavioral experiment,
  `371bae1`, had removed the startup instruction to choose and explain the
  first useful scientific action, removed the corresponding session-record
  requirement, and hid the maintainer's startup training ceiling.
- **Observation:** a later fresh startup still moved directly to an
  unchanged-recipe full-ceiling training request. The intended improvement in
  training-first startup behavior was not observed. This is not a controlled
  causal comparison and does not establish that the removed wording is
  scientifically effective.
- **Correction:** withdraw only the behavioral experiment introduced by
  `371bae1` in the current repository layout. Restore the first-action
  responsibility, its explanation and scientific-session record, and display
  the maintainer's requested-step startup allocation as a ceiling rather than
  a required operation.
- **Preserved:** keep the ownership restructure, the remaining `7f86168`
  persona and instruction-delivery corrections, operational fixes, current
  paths, mechanical allocation validation and the original historical
  `371bae1` entry. Do not restore its unrelated README changes.
- **Boundary:** this is a forward semantic withdrawal, not `git revert` or
  history rewriting. It changes no operation permission, allocation value,
  Runner judgment, scientific implementation, campaign state or accepted
  operation. No campaign, training, reset, measurement or evaluation is
  executed.
- **Disposition:** `371bae1` is withdrawn after no observed improvement. The
  restored startup semantics are the behavioral baseline, not a demonstrated
  solution to training-first action selection.

## 2026-10-05: restore scientific-model prompt ordering

- **Observation:** the successful campaign's scientific-model prompt placed
  the human goal before the unchanged PI persona. The current prompt placed
  the persona first. Its scientific-model objective, required registers and
  persona wording were otherwise unchanged.
- **Decision:** restore the earlier ordering for the scientific-model phase
  only: human goal first, then the complete PI persona. Apply the same ordering
  to that phase's validation retry. Other phase prompts continue to lead with
  the persona.
- **Purpose:** test whether goal-first context reduces variation in preliminary
  model framing. This ordering change does not prescribe plant-first analysis,
  candidate-free measurement or any first campaign operation.
- **Boundary:** no persona wording, scientific-model objective, operation
  permission, training allocation, Runner judgment, campaign state or
  scientific implementation changes. No campaign, training, reset,
  measurement or evaluation is executed.
- **Disposition:** implemented for observation; scientific effectiveness is
  unassessed.

## 2026-10-05: retain goal-first model prompt after inquiry rush

- **Campaign observation:** campaign
  `edc16754-3f16-45b9-bd0b-faea041c3db5` used the restored goal-first
  scientific-model ordering. Its preliminary model returned to a plant-first
  account of coupled dynamics, braking and hold stability. Startup then built
  and ran candidate-free measurement `M2` before training.
- **Useful startup evidence:** `M2` found that all 40 tested valid IK
  configurations completed the static hold and all 160 tested initial-velocity
  perturbations through 0.5 rad/s remained within tolerance. All 160
  one-control-interval full motor impulses exited tolerance, with larger
  excursions at larger radii. This was useful physical evidence, not proof
  that the ordering change caused the behavior.
- **Transition failure:** startup checkpoint `E1` immediately selected a fresh
  baseline as the next action. Goal review opened `I1` with a closure condition
  that required one 120000-step training run and development evaluation.
  Checkpoint `E3` preserved that commitment, so the inquiry session inherited
  a preselected operation rather than reconsidering the scientific direction.
- **Contract-to-implementation mismatch:** `I1` and training request `T1`
  described the run as using the full official target distribution, while
  `robot_learning/training/environment.py` still samples radii
  0.14--0.20 m rather than the official 0.06--0.20 m range. The unchanged run
  therefore could not literally test the training-distribution claim in its
  request.
- **Subsequent operations:** `T1` completed 120832 steps. Development
  measurement `M3` scored both the peak-training and final checkpoints at
  151/160 successes (94.375%) on the shared 160-episode panel. These are
  development results, not official assessment or evidence that the inquiry
  framing was adequate.
- **Maintainer action:** the maintainer stopped the campaign after `M3`, before
  a new inquiry synthesis, closure decision or official assessment. The stop is
  an execution decision, not a scientific campaign conclusion.
- **Disposition:** retain the scoped `756ae4b` prompt-order change. One
  campaign supports its intended direction but does not establish causality.
  The startup-to-inquiry rush and the inaccurate distribution claim remain
  unresolved; this entry approves no further harness change.

## 2026-10-05: make the PI persona robotics-first

- **Decision:** replace the shared PI persona with the maintainer-approved
  three-part wording. It identifies the PI with embodied robotics, names
  reinforcement learning once among the available disciplines, and removes
  the learned-policy destination from the opening identity.
- **Authority:** the human defines the goal and protected boundary; the PI
  owns everything else. Existing code, architecture, metrics, hypotheses and
  prior decisions remain provisional scientific artifacts rather than
  authorities.
- **Preserved:** the scientific-model prompt remains goal-first and all other
  phase prompts remain persona-first. Startup, inquiry, operation permissions,
  Runner validation, training allocations and scientific implementation are
  unchanged.
- **Boundary:** this is a persona change, not a startup instruction or a
  prescribed action-selection heuristic. No campaign, training, reset,
  measurement or evaluation is executed.
- **Disposition:** implemented for observation. Its effect on startup and
  inquiry behavior is unassessed.

## 2026-10-05: measure previous-persona startup stochasticity

- **Reference:** the previous PI persona was restored in `ea35499`, then
  three fresh campaigns were reset and run sequentially with no harness
  change between trials. The detailed report is
  `docs/persona-stochasticity-report-20261005.md`.
- **Observed variation:** Trial 1 selected training first, Trial 2 changed
  PI-owned training code before training and measurement, and Trial 3
  selected an official-annulus physical characterization measurement before
  any training. Their first inquiry behavior also differed.
- **Boundary failures:** Trial 1 crossed the requested stop boundary and
  dispatched inquiry training before the stop was observed. Trial 2
  modified PI-owned scientific code during startup, so it is not a clean
  repetition. Trial 3 stopped correctly with the first inquiry training
  request pending before Runner acceptance.
- **Interpretation:** the previous persona permits materially variable
  startup method selection, including useful physical investigation, but
  does not reproduce it reliably. The result demonstrates qualitative
  stochasticity, not a clean quantitative causal estimate of persona
  influence.
- **Disposition:** retain the restored previous persona for the requested
  comparison. No additional harness change is made from this experiment.

## 2026-10-05: independent prompt-stack review and follow-up directions

- **Review context:** an independent, read-only review examined the complete
  PI-facing prompt and instruction stack after repeated concern about early
  training, loss of preliminary embodied-robotics reasoning, and inquiries
  inheriting preselected operations. The submitted review is preserved
  verbatim in `docs/prompt-instruction-stack-review-20261005.md`.
- **Main diagnosis retained for discussion:** the instruction stack asks for
  substantial scientific reasoning, but the preliminary model's consequential
  conclusions are less concrete at startup action selection than operational
  state, resource information and available actions. This is a design
  hypothesis supported by static prompt analysis, not an established causal
  result.
- **Direction 1 - preliminary-to-startup handoff:** investigate a concise,
  PI-authored carry-forward of consequential physical understanding into
  startup. It must remain revisable and must not turn the frozen preliminary
  model into an authority or require measurement before action.
- **Direction 2 - scientific context before operation mechanics:** investigate
  whether current understanding, evidence limits and the decision frontier
  should be presented before operation types and resource mechanics. Keep
  persona wording and universal goal-first ordering as separate decisions;
  neither is approved by this entry.
- **Direction 3 - inquiry meaning without procedural question-first rules:**
  preserve the distinction between a scientific inquiry and an operation
  request, but do not reintroduce a procedural requirement to formulate an
  unresolved distinction, predicted findings or artificial alternatives before
  every action. Question-centered inquiry framing was already implemented in
  the 2026-10-02 experiment above and observed in campaign `2381bcbf`; its
  isolated causal effect was not established.
- **Decision pending:** no harness implementation is approved here. The
  maintainer will decide whether these directions should be designed and
  exercised together or one at a time. Campaign state and pending operation
  state remain untouched.

## 2026-10-05 to 2026-10-06: complete R1 scientific-model handoff

- **Source:** independent prompt-stack review preserved in
  `docs/prompt-instruction-stack-review-20261005.md`, recommendations R1-R8.
- **Approved scope:** implement R1 only. The preliminary model now requires
  assumptions and implementation or contract source references for each
  consequential implication or unknown. It must finish with a concise
  PI-authored `Decision-relevant synthesis` selecting only the conclusions most
  likely to change initial campaign decisions. Startup receives that selected
  synthesis rather than Runner-selected full model sections, and the brief
  routes directly to both the frozen model and `contracts/program.md`. Later
  checkpoints continue to preserve or revise consequential conclusions through
  the existing synthesis and decision-frontier fields.
- **Campaign evidence:** campaign `9fa1f256` verified that the earlier R1
  handoff reached the actual startup prompt and materially shaped startup,
  measurements, inquiries and checkpoints. The same campaign also propagated
  a physical-direction error and several evidence-transcription errors. R1
  provides continuity, not scientific verification; those fidelity and action-
  selection problems remain separately tracked.
- **Unchanged:** persona wording, prompt ordering outside this startup-specific
  guidance, inquiry semantics, instrument contracts, operation permissions,
  training allocation, Runner validation, campaign state, and pending requests.
  No measurement, training, reset, resume, or evaluation was executed.
- **R2-R8 backlog:** R2 scientific-context ordering, R3 inquiry meaning,
  R4 continuation/recovery classification, R5 candidate-free instrument
  discoverability, R6 replacement-authority wording, R7 routing/backend
  alignment, and R8 instruction ownership/repetition remain unimplemented.
  Their proposed wording is not silently included in R1.
- **Implementation checks:** PowerShell parsing, targeted Python compilation,
  scientific-model contract probes, brief rendering, and whitespace checks
  passed. The stopped campaign state, T4 recipe commit and pending operation
  request were not modified or executed.
- **Disposition:** R1 is complete as a bounded continuity mechanism. It does
  not verify the model's truth, require measurement first, formulate a
  procedural question before acting, or treat the preliminary model as an
  authority or intervention menu.

## 2026-10-06: implement R2 scientific-context ordering

- **Commit / scope:** `fb9b10d`; `run_research.ps1` and synchronized
  maintainer documentation.
- **Source:** independent prompt-stack review preserved in
  `docs/prompt-instruction-stack-review-20261005.md`, recommendation R2.
- **Approved scope:** remove the learned-policy destination from the shared PI
  identity. The persona now assigns scientific direction toward the
  human-authored scenario goal and integrates robotics, learning, control,
  simulation, system identification, experimental design and scientific
  software as the problem requires, without implying a research method.
- **Session ordering:** ordinary PI scientific-session prompts remain
  persona-first. They then present the human goal, essential task conditions
  and protected boundaries; initial physical understanding and current
  synthesis; completed evidence and recorded interpretive limits; goal gap and
  decision frontier; active inquiry and objective; decision guidance; legal
  operations and applicable training allocation; then source routing and
  submission mechanics.
- **Intentional deviation:** the review's literal human-goal-before-persona
  ordering is not applied to `New-ScientificSessionPrompt`. The established
  persona-first rule remains for ordinary phases. The preliminary
  scientific-model prompt keeps its separately documented human-goal-first
  exception and is otherwise unchanged.
- **Resource boundary:** startup keeps its requested-step ceiling and inquiry
  work keeps the maintainer allocation in the operations/resource area.
  Goal-review and checkpoint-only transitions do not repeat a training
  allocation because training is not legal there.
- **Unchanged:** R1, the scenario's actual learned-policy requirement, PI
  authority, legal instruments, resource values, validation, campaign state,
  operation schemas and the preliminary prompt ordering. No Runner scientific
  judgment or gate is added.
- **R3-R8 backlog:** inquiry meaning, continuation/recovery classification,
  candidate-free instrument discoverability, replacement-authority wording,
  routing/backend alignment and instruction ownership/repetition remain
  unimplemented and separately scoped.
- **Disposition:** R2 is partially implemented. The method-neutral persona and
  context-before-operations order are present. Ordinary sessions still put the
  PI persona before the human goal. Thus the implementation does not complete
  the review's goal-first order. No campaign operation was executed.

## 2026-10-06: record ordinary-session goal-first ordering follow-up

- **Correction:** R2's independent-review recommendation literally ordered the
  human goal, essential task conditions and protected boundaries before the PI
  role. Implemented commit `fb9b10d` intentionally did not apply that order to
  ordinary PI sessions: it retained persona-first delivery while moving
  scientific context and state ahead of operational options.
- **Backlog:** complete R2. Put the human goal, task conditions and protected
  boundaries before the PI role in ordinary sessions. This entry
  records the missing part. It does not change `run_research.ps1`.
- **Evidence boundary:** the preliminary scientific-model prompt's scoped
  goal-first ordering had one positive local observation in campaign
  `edc16754`, but no causal proof. Ordinary-session persona-first ordering was
  an approved structural choice, not a demonstrated quality improvement. The
  previous-persona trials in
  `docs/persona-stochasticity-report-20261005.md` showed materially variable
  openings. They support a stochasticity conclusion, not a claim that one
  order or persona is better.
- **Status:** R1 (`8c0a25b`) is implemented. R2 (`fb9b10d`) is partially
  implemented because its ordinary-session goal-first order is missing. R3-R8
  remain separate backlog items. No campaign operation or runtime change is
  performed.

## 2026-10-06: implement bounded R3 inquiry semantics

- **RCA:** the original R3 proposal could make formal question construction
  the center of the campaign. Repeating a question-first procedure before each
  action could reproduce the earlier question-centered behavior. The human
  goal, evidence and evolving scientific understanding must remain central.
- **Approved scope:** inquiry opening now records a temporary unresolved matter
  or capability need rather than an operation name. The question can support
  descriptive investigation or method development. It does not require
  artificial competing hypotheses. The closure condition records an answer,
  bounded conclusion or redirection rather than operation completion alone.
- **Closure meaning:** closure distinguishes completed operation outcomes, the
  supported inquiry answer, remaining uncertainty and the campaign
  implication. New evidence can close or reframe an inquiry without requiring
  the PI to defend its previous formulation.
- **Placement boundary:** the clarification appears in the program contract,
  inquiry field meanings and the goal-review opening objective. It is not added
  to common action guidance or repeated before every operation. No question
  hierarchy, hypothesis backlog, schema field, operation sequence or Runner
  scientific gate is added.
- **Status:** R3 is implemented with this narrower scope. R2 remains partial
  and paused. R4-R8 remain separate backlog items. No campaign operation was
  started, resumed or reset.

## 2026-10-06: discard R3 and restore pragmatic inquiry closure

- **RCA:** R3 made the inquiry question too important. A broad capability or
  mechanism question can support more investigation without a clear end. The
  question can then become the campaign's governing unit instead of a temporary
  aid to the human goal.
- **Correction:** remove the R3 question definitions from the program,
  instrument contract and goal-review prompt. Restore the original definition
  of an inquiry as a temporary question or obstacle. Restore the actionable
  result as one valid reason for closure.
- **Rollback boundary:** the instrument contract and goal-review prompt match
  their exact pre-R3 text. The program contract also matches its pre-R3 text,
  except for the closure rule below. Commit `9c5ef61` also included the
  previously approved handoff backlog row and R2 pause documentation. Those
  separate records remain.
- **Closure rule:** the PI may close an inquiry with a limited or inconclusive
  result while the human goal remains unmet. Closure does not require a
  complete answer to the inquiry question. The campaign then returns to goal
  review.
- **Evidence limit:** the active campaign showed that R3 reached the PI prompt
  and produced a capability-shaped question. It did not prove that R3 improved
  campaign decisions. The risk follows from the contract semantics, not from a
  demonstrated endless inquiry.
- **Disposition:** R3 is discarded. The inquiry lifecycle remains. R2 remains
  partial and paused. R4-R8 remain separate backlog items. No campaign
  operation was started, resumed or reset.

## 2026-10-06: allow Runner transactions during protected-runtime checks

- **Campaign evidence:** campaign
  `3d0d131d-3cb5-41fc-8c57-64e7521b3051` reached M4 with three of five
  submeasurements completed. The first diagnostic then failed because its
  accepted module arguments omitted the required `--artifact` option. The
  Runner correctly preserved the three evaluation artifacts and
  `measured_3_of_5` transaction state.
- **Regression:** accepting the PI's corrected replacement request rechecked
  research-panel independence through the protected benchmark adapter. The
  clean-worktree guard rejected the Runner-generated evaluation artifacts and
  `runner/state/research_state.json` because the ownership restructure
  classifies all `campaigns/` and `runner/` paths as human-owned. The PI could
  neither restore nor publish those protected transaction files, creating a
  recovery deadlock.
- **Correction:** continue rejecting uncommitted human-owned and protected
  sources, but exclude paths explicitly registered by
  `repository.is_runner_owned()` as Runner control or memory. This includes
  pending state and campaign evaluation artifacts, not Runner source code,
  benchmark code, contracts, documentation, tests or tools.
- **Boundary:** no operation schema, scientific judgment, measurement intent,
  campaign state, pending request, completed artifact or PI-owned code is
  changed. The fix does not resume or finalize M4.
- **Implementation checks:** targeted Ruff, Python compilation, and a direct
  guard probe confirmed that Runner transaction paths are permitted while a
  dirty contract remains rejected.
- **Disposition:** retained as an ownership-refactor regression correction.
  The three partial M4 evaluations remain unpublished transaction evidence
  until the maintainer chooses whether to resume the campaign.

## 2026-10-06: stop treating PI style findings as execution failures

- **Campaign evidence:** T2 in campaign
  `3d0d131d-3cb5-41fc-8c57-64e7521b3051` was rejected before training because
  Ruff reported only an unsorted import block. The same scientific request was
  then superseded as T3 after formatting repair, consuming an operation ID and
  recording a failed training attempt without scientific evidence.
- **Decision:** formatting and lint style are not execution correctness and
  must not block PI scientific code. Source validation continues to reject
  invalid Python syntax and malformed JSON. Training still runs the existing
  directly affected behavioral validation selected by the Runner before
  publication and execution.
- **Change:** remove blocking Ruff execution from
  `execution.validate_changed_sources`. Keep its in-process Python compilation
  and JSON parsing checks.
- **Boundary:** this does not weaken ownership checks, dependency-lock
  validation, active-configuration validation, targeted behavioral validation,
  runtime exceptions, or operation schemas. It does not alter or erase the
  historical T2 failure.
- **Implementation checks:** targeted Ruff on the Runner change, Python
  compilation, and direct probes confirmed that unsorted but syntactically
  valid Python is accepted while invalid syntax remains rejected.
- **Disposition:** retained as a validation-semantics correction. A style
  issue no longer creates a failed scientific operation.

## 2026-10-06: discard R4 and continue with R5

- **Proposal:** R4 proposed explicit reconsideration after results. It also
  proposed explicit classification of request, execution-environment,
  implementation and publication failures.
- **Decision:** discard R4 as an independent remediation item. Later recovery
  work already returns an error to the same PI and backend session. It
  preserves valid evidence and excludes failed operations from scientific
  evidence. The PI repairs the same action unless the diagnosis changes the
  scientific decision.
- **Checkpoint boundary:** current checkpoint guidance records changed
  evidence, unresolved uncertainty and the next direction. The full R4 wording
  would mostly repeat these instructions. It could also cause unnecessary
  reconsideration after routine results.
- **Current example:** the recent observation-shape mismatch was an
  implementation mismatch. The PI drew no scientific conclusion and repaired
  the same bounded action. Durable records show that T4 failed before training,
  is execution history rather than scientific evidence, and was superseded by
  T5. These records do not prove why the PI responded this way.
- **Safeguard boundary:** discarding R4 does not remove or weaken recovery
  safeguards. Failure classification remains useful even though the separate
  R4 wording is unnecessary.
- **Disposition:** R4 is discarded because later recovery work superseded its
  useful proposal. R1 remains implemented. R2 remains partial and paused. R3
  remains discarded for its separate inquiry-semantics reason. R5-R8 remain
  open and separately scoped. No campaign operation was started, resumed or
  reset.
## 2026-10-06: implement R5-2 candidate-free capability visibility

- **Problem:** the instrument contract gave clear scientific names to training
  and candidate evaluation. It described `python_module` only through module
  paths, arguments and artifact paths. This could hide its candidate-free
  scientific capability behind a technical interface name.
- **Change:** add a short capability overview before the detailed interfaces.
  State that `python_module` runs a PI-owned experiment or analysis and does not
  require a learned candidate. Repeat that capability beside its interface.
- **Boundary:** the overview does not define a required sequence or give
  preference to an operation. It adds no instrument, schema field, permission,
  scientific gate or Runner judgment.
- **Disposition:** R5-2 is implemented. It makes candidate-free measurement
  visible without making measurement the default. No campaign operation was
  started, resumed or reset.

## 2026-10-06: implement R5-1 controlled-English instrument contract

- **Order:** the maintainer approved R5-2 before R5-1. The item numbers identify
  their scopes, not their execution order.
- **Change:** rewrite the explanatory text in `contracts/instruments.md` with
  the ASD-STE100 skill. Use short sentences, active voice, consistent terms and
  one condition per sentence. Keep technical names where the contract requires
  them.
- **Preserved contract:** all 14 fenced text and JSON blocks match the pre-R5
  contract exactly. Operation kinds, field types, required fields, acceptance
  rules, permissions, resource limits, outputs and evidence rules are
  unchanged. R5-2 is the only added semantic explanation.
- **Language check:** the structural checker reports zero errors. It reports 15
  advisory warnings for required technical terms such as `training`, `working`,
  `learning` and `discriminating`.
- **Disposition:** R5-1 is implemented as a wording refactor. R5-2 remains the
  separate capability clarification. R6-R8 remain open. No campaign operation
  was started, resumed or reset.

## 2026-10-07: propose custom Copilot tools for bounded PI capabilities

- **Hypothesis:** custom Copilot SDK tools can give the PI a smaller and more
  relevant context than generic shell and editing tools. A tool can return the
  required files or structured evidence instead of adding broad file content
  to the PI context. This can reduce token use and help the PI construct the
  context for a scientific decision.
- **Initial application:** a preliminary-phase
  `publish_scientific_model` tool could accept the complete scientific model,
  validate its required structure and publish it deterministically. The
  preliminary toolset could provide repository inspection and this publication
  tool without generic write, edit or shell capabilities.
- **Boundary:** tools provide information or perform mechanical publication.
  They do not select scientific questions, interpret evidence or choose an
  operation. The Runner keeps the authoritative acceptance check.
- **Status:** proposal only. No SDK tool, phase-specific toolset or runtime
  behavior changed.

## 2026-10-07: preserve exact PI conclusions and next questions across inquiries

- **RCA:** fresh scientific sessions represent the same PI with refreshed model
  context. The generated brief carried a reduced summary, but it did not
  restore the prior conclusion and selected question as explicit PI state.
  This allowed a mechanism-specific conclusion about braking, residual velocity
  and state-dependent regulation to become a generic reach-versus-hold inquiry.
- **Change:** add `next_question` to every scientific session record. Startup
  selects the first inquiry question. Inquiry closure selects the question for
  the next inquiry. A checkpoint that continues an active inquiry repeats its
  current question. Goal review preserves the question of the inquiry that it
  opened.
- **Exact handoff:** when goal review opens an inquiry, the Runner copies the
  source checkpoint's `current_synthesis`, `next_question` and session identity
  into the inquiry state. Goal-review and inquiry prompts receive the source
  conclusion and question verbatim, in addition to the existing documents and
  generated campaign context.
- **Continuity rule:** the fresh context continues the same PI. It does not
  invite a new scientific opinion. The PI changes the restored conclusion or
  question only when new evidence, an implementation finding or a concrete dead
  end changes the scientific situation. The later record states what changed
  and why.
- **Boundary:** the Runner preserves and presents PI-authored scientific state.
  It does not interpret the conclusion, select the question or prescribe an
  instrument. Inquiry remains a bounded context for the PI, not an independent
  success criterion.
- **Implementation checks:** Python compilation and Ruff passed for the changed
  Runner modules. PowerShell parsing passed. A minimal state reproduction
  confirmed exact conclusion and question transfer and rejection of a
  goal-review checkpoint that changes the opened inquiry question.
- **Status:** implemented for the next fresh campaign. No campaign operation
  was started, resumed or reset during implementation.

## 2026-10-07: log inquiry-control failure from campaign b366ab54 (OI-002)

- **Observation:** I2 asked which intervention would most reliably suppress the
  observed failure mechanism. This question did not define a bounded set of
  interventions. It also made a successful intervention appear to be the
  required answer.
- **Decision-progress loss:** M4 supplied the first negative intervention
  result. M5 weakened the branch-switch cause. M7 showed no improvement from
  action smoothing. I2 still continued to full-distribution training. M9
  finally supplied sufficient evidence to close the inquiry.
- **RCA:** the exact handoff worked. It preserved the conclusion and question
  across fresh contexts. The preserved question was too broad. Each failed
  intervention removed one option but did not answer which intervention would
  work.
- **Required improvement:** an inquiry question must permit a positive,
  negative, limited or inconclusive answer. Its closure condition must define
  the evidence needed for a decision. It must not require the PI to find a
  successful intervention.
- **Evidence:** campaign `b366ab54-1218-4ab4-9bf1-3fd6a19c86bb` and
  `docs/research-overview/robot-campaign-b366ab54-final-analysis-20261007.html`.
- **Boundary:** this entry records the inquiry-control issue only. Assessment
  readiness is postponed. No prompt, contract, Runner or campaign behavior
  changed.
- **Status:** open for a separately approved design and implementation.

## 2026-10-07: implement R6 and R7

- **R6:** implemented in commit `fa5bd6b` to clarify retention and replacement
  neutrality. Existing PI-owned structure has no standing over a scientific
  choice.
- **R7:** implemented in commit `80e4add` to align contract paths, protected
  paths, and policy routing with the current repository layout.
- **Validation:** validation was performed for both commits.
- **Boundary:** the assessment-readiness issue remains postponed. No campaign
  has been launched, resumed, reset, trained, measured, or evaluated.
- **Status:** R6 and R7 are implemented. The b366ab54 inquiry-control finding
  remains intact as OI-002 for separate follow-up.

## 2026-10-07: implement R8 and number outstanding issues

- **R8 implementation:** commit `8166e2f` assigns lifecycle meanings to
  `contracts/program.md`, mechanics to `contracts/instruments.md`, ownership
  and command authority to `AGENTS.md`, and current state and legal actions to
  the launcher prompt. It removes repeated launcher guidance without changing
  inquiry closure, operation permissions, allocation values or Runner
  validation.
- **Issue register:** the active backlog now uses stable `OI-###` identifiers.
  OI-001 records unreliable startup scientific-method selection separately
  from OI-006, the startup-budget review. OI-002 identifies the inquiry-control
  failure already recorded above.
- **Boundary:** numbering does not prioritize an issue, approve a solution or
  establish scientific effect. Completed changes and unassessed effects remain
  status context rather than new outstanding issues.
- **Status:** R8 is implemented. OI-001 through OI-013 are the current
  outstanding-issue register.

## 2026-10-08: OI-001 retrospective, R8 correction, and neutral scientific-model prompt

- **OI-001 definition:** a failure of traceable coupling from the PI-generated
  scientific briefing, through startup action selection, to startup handoff
  content. It ends at the startup handoff. Training is not a defect when it is
  scientifically justified. Three failure locations: briefing defect (relevant
  facts or uncertainties absent, wrong, or framed so an unsuitable action
  looks informative), use defect (a relevant uncertainty is received but the
  action does not address it), and handoff defect (reasoning collapses into a
  preselected operation).
- **Method:** five retrospective process traces (campaigns 06656182,
  97633a56, b366ab54, ab62348f, 0284114e) at frozen commits, one `gpt-6-luna`
  xhigh subsession each, then one `claude-opus-5.5` cross-campaign synthesis.
  The five reports coded the briefing as indeterminate because
  `campaigns/brief.md` is git-ignored. The synthesis corrected this: the
  briefing is the "Decision-relevant synthesis" section of
  `pi_workspace/scientific_model.md`, which the launcher pasted into the
  startup prompt and which is saved at every cutoff.
- **Findings:** all five startups named a real uncertainty and kept evidence,
  alternatives, limits and conditional next steps in the handoff. The briefing
  contained no missing or wrong facts. Its framing matched the startup method
  in four of five campaigns. In ab62348f it said the dynamics question
  "matters only if" something else, and startup trained first. In b366ab54 and
  97633a56 the briefing pointed to measurement and startup measured first.
  06656182 named a dynamics measurement as decisive, then trained because a
  probe "would require tool construction". It is the only run under R8, which
  had removed the PI-authority sentence. Both train-first runs used the same
  recipe and seed and scored 99.5% and 73%.
- **Confidence:** briefing defect weak as a defect and weak to moderate as a
  mediator; use defect moderate; handoff defect contradictory. The required
  handoff fields may hide a collapse.
- **Limits:** n=5, one coder who knew the outcomes, no repeated startups with
  identical inputs, encrypted model reasoning, and the campaigns that prompted
  OI-001 (`2573991c`, `c7040992`) were not included.
- **Diagnostic tests not yet run:** briefing-swap replay with the prompt held
  fixed, startups with a ready-made lab tool, a training-ceiling cue
  variation, repeated identical startups, and a free-form handoff.
- **R8 correction (`adff08e`):** restored the launcher sentence that lets the
  PI inspect, modify or replace PI-owned implementations before submitting an
  operation. R8 had removed it as duplicated from `AGENTS.md`.
- **Scientific-model prompt (`ef9516f`):** the phase now runs under a robotics
  and simulation analyst persona. It builds the model from first principles
  and the human-owned definitions of the robot, simulator and task. It has
  three registers (Established facts, Physical consequences, Unknowns). The
  "Decision-relevant synthesis" section is removed. The validator, brief and
  contracts match. Startup reads the whole model and selects its own
  direction. The reason is that a different persona ranking unknowns steered
  the startup PI.
- **Retained:** the per-item decision relevance inside the registers, and the
  `campaigns/brief.md` pointers, which carry the legal operation list.
- **Validation:** the PowerShell script parses and the touched Python modules
  compile. Targeted tests show 11 failures, 6 known and 5 reproduced on the
  untouched baseline.
- **Not yet observed:** whether neutral models change startup action
  selection. Compare the next campaigns against the five analyzed here.
- **Boundary:** no campaign has been launched, resumed, reset, trained,
  measured, or evaluated.
- **Status:** OI-001 remains open and narrowed. The prompt change is
  implemented and unmeasured.

## 2026-10-08: review campaign 06656182 and record OI-014

- **Campaign:** `06656182-d7f0-4011-898d-2b870e8a2a54` ran on 7 October under
  the R8 instruction stack without the PI-authority sentence and under the
  previous scientific-model prompt. It passed the official assessment with
  196 of 200 episodes (98.0%) using `T5:checkpoint-120832`. The record holds
  6 training runs, 9 measurements, 5 of 15 inquiries and 23 operations.
- **Handoff:** no handoff collapsed. Every checkpoint preserved the result,
  the interpretation, the decision frontier and the next action. Negative
  results for T2, T4 and T6 stayed explicit to the end of the campaign. This
  supports the OI-001 retrospective finding. Handoff is not the weakness here.
- **Inquiry coherence and closure:** each of I1 to I5 closed after one
  intervention and one matched evaluation. Three closed on a negative or
  limited result, and the PI accepted them. The campaign therefore shows the
  bounded closure that OI-002 asks for, without any approved OI-002 change.
  One run does not establish that the harness now produces that behavior.
- **OI-002 evidence:** I4 repeats the exact question text of the closed I3
  inquiry. The I4 rationale, closure condition and experiment are different,
  so the defect is in the inquiry question rather than the work. OI-002
  remains open.
- **OI-014 evidence:** T3 changed the training context and added the settling
  reward term in one operation. I2 attributed the gain to the settling term
  alone. T4 and T5 then refined that term. Later evidence supported the
  braking route, so no failure followed. The risk is route selection, not
  reproducibility.
- **Official assessment request:** legitimate and reasonably justified. T5 was
  the assigned best-known candidate, scored 95% on M8 and 98% on M9, beat T6
  on all eight discordant M9 episodes, and no inquiry was active. The E23
  reason emphasized the 98% panel and the absence of a dynamics signature. It
  did not weigh the conflicting 95% and 98% results against the value of one
  more inquiry. Requiring near-certain readiness would instead let a campaign
  continue without end, so the balance, not the certainty, is the open point.
  This sits inside OI-005, whose replacement guidance stays postponed.
- **Reporting:** `docs/research-overview/robot-campaign-06656182-final-analysis-20261008.html`
  records the campaign, and the overview was updated in commit `5f58dd5`.
- **Boundary:** this entry records a review and one new issue. No prompt,
  contract, Runner or campaign behavior changed. No campaign was launched,
  resumed, reset, trained, measured or evaluated.
- **Status:** OI-014 is open and unimplemented. OI-002 and OI-005 remain open.
  The new scientific-model prompt is still untested by any campaign.

## 2026-10-08: heading fix, campaign bd32cc79 observation, and closing-section restoration

- **Bundled change in `ef9516f`:** the scientific-model rewrite changed four
  things at once. It rewrote the language of the whole phase prompt. It
  replaced the PI persona with an analyst persona. It removed the "Decision-
  relevant synthesis" section. It set three registers. No campaign tested any
  of these separately. This bundle breaks the single-change rule of OI-014.
- **Heading failure (`b3f4307`):** the first campaign start after `ef9516f`
  failed. The prompt required three `##` registers but did not say how to nest
  topics. The analyst wrote topics as `##` sections, so `## Established facts`
  was empty. The prompt, the retry text and `contracts/instruments.md` now say
  that each register is a `##` heading and topics use `###`. The validator is
  unchanged. This is a format repair, not a scientific change.
- **Campaign bd32cc79 (read-only review):** it is the first campaign that used
  the bundled prompt. All sessions exited 0 and handoffs held. The model was
  rigorous and cited its sources. It stated the training-range mismatch (14-20
  cm training, 6-20 cm official) twice, among about 20 items of equal weight.
  Startup chose M1, a broad measurement that confirmed what the model already
  stated. The mismatch was first tested after M1, T1, M2, M3, M4 and an
  inquiry reframe. I2 then changed only the training range (T2). In the paired
  M5 evaluation T2 scored 150/160 (93.75%) against 110/160 (68.75%) for T1.
  I3 opened afterwards.
- **Attribution limit:** the good results may come from the language, the
  persona or the other model that ran this campaign. The slow route to the
  mismatch fits the removed ranking, but the older campaigns also started
  with a measurement in two of five cases. The data cannot separate these
  causes.
- **Closing section restored:** the model again ends with the `## Decision-
  relevant synthesis` register. The analyst selects the consequences and
  unknowns most likely to change the first campaign decisions. Each item keeps
  decision relevance, assumptions, source references and discriminating
  evidence. No item count is set. Startup receives the register, as before.
  The text uses controlled English (ASD-STE100 style) and the analyst
  persona. The old negative phrase "not an intervention plan" is replaced by
  the positive statement that the section states consequences and
  discriminating evidence, and that the PI selects the interventions. Files:
  `run_research.ps1`, `runner/run_experiment.py` (four required headings),
  `runner/build_brief.py`, `contracts/instruments.md`, `contracts/program.md`.
- **Kept:** the new language and the analyst persona. Their effect on a
  campaign stays unmeasured.
- **Validation:** the PowerShell script parses with 0 errors and the two
  touched Python modules compile.
- **Boundary:** no campaign was launched, resumed, reset or trained. The
  results above come from a read-only review of a campaign the maintainer
  runs.
- **Status:** OI-001 stays open. The next campaign tests the restored closing
  section under the new language and persona. Reverting the language or the
  persona would be a separate test.

## 2026-10-09: remove the context leak from handoffs and align the goal-review objective

- **Observation:** campaign 61f732e1 was the first run with the restored
  synthesis. It reached the full-range inquiry at E6, three events earlier
  than bd32cc79. The synthesis still ranked nothing. Inquiry I3 ran T3, T4
  and a pending T5 (150, 152, then 153 of 160), so it did not close. This is
  OI-002 evidence. The maintainer stopped the campaign at T5. One campaign
  cannot separate the synthesis from run-to-run noise.
- **Leak removed:** the goal-review and inquiry handoffs said "Do not replace
  or reinterpret it because the model context is fresh". That sentence
  explained a harness design reason to the PI, who does not need it. Both
  handoffs now say "Continue from this state" and keep the rule that new
  evidence, an implementation finding, or a concrete dead end can change the
  state, with a record of what changed and why.
- **Goal-review objective:** "Reassess the scientific direction ... using
  completed evidence" became "Use the completed evidence to update the
  scientific direction toward the human goal." The verb now matches the
  restored handoff. The objective keeps the optional measurements and the
  choice between official assessment and one bounded inquiry. A single
  purpose per prompt stays an open design question for goal review.
- **Validation:** the PowerShell script parses with 0 errors. No test or
  contract text refers to the removed or changed sentences.
- **Boundary:** no campaign was launched, resumed, reset or trained.
- **Status:** implemented and unmeasured.

## 2026-10-09: implement the OI-002 closure-boundary clarification

- **RCA:** OI-002 is an insufficiently defined stopping boundary and an
  insufficiently explicit check of that boundary. The exact handoff can
  preserve a question that is too broad. Success was not the only existing
  exit: redirection was also allowed. The prompt already asked the PI to
  record when evidence resolves or redirects an inquiry, but it did not tell
  the PI to compare accumulated evidence with the closure condition before
  choosing more work. Full training allocation remains an amplifier, not an
  established cause, and is unchanged.
- **Implementation:** `contracts/program.md` now states that the closure
  condition identifies sufficient evidence for the inquiry and permits
  positive, negative, limited or inconclusive conclusions. Obtaining and
  assessing that evidence can span several operations. The active-inquiry
  objective in `run_research.ps1` now tells the PI to compare accumulated
  evidence with the closure condition before choosing the next action and to
  close when the condition is met.
- **Boundary:** The change does not select methods, interventions,
  measurements or their sequence. It does not add an operation count, a
  successful-intervention requirement, Runner scientific judgment or automatic
  closure. `contracts/instruments.md` remains unchanged because it describes
  instrument mechanics, not scientific protocol.
- **Campaign evidence:** The maintainer stopped campaign `61f732e1` at T5.
  It was not reset or restarted. Its evidence remains read-only campaign
  history and does not measure this implementation.
- **Validation:** PowerShell parsing and the HTML housekeeping checks passed.
  The change remains unmeasured until a maintainer-run campaign uses it.
- **Status:** OI-002 implementation is complete and unmeasured. OI-002 must
  be reviewed for both premature closure and indefinite continuation.

## 2026-10-09: close OI-002 and activate OI-004 progression review

- **OI-002 disposition:** campaign `1ae27a27` closed positive, negative,
  limited and inconclusive inquiries at their declared evidence boundaries. The
  indefinite-continuation symptom did not recur. The campaign does not isolate
  the reminder's causal effect because one-intervention inquiry closure existed
  in earlier campaigns and other prompt changes were active. OI-002 is closed
  with observed bounded closure; its current contract and prompt text stay.
- **Issue separation:** one-recipe inquiry granularity is not attributed to the
  OI-002 reminder. Scientific progression and artifact selection are OI-004.
  Consuming the temporary inquiry allowance remains OI-013. Bundled-change
  attribution remains OI-014.
- **OI-004 checkpoint-selection evidence:** I9-I15 evaluated the terminal
  checkpoint for every completed training run. Earlier training peaks were
  available for T10 and T12-T17, including 1.00 training-success checkpoints
  for T13-T17. Training-distribution metrics do not prove development
  performance, but they can nominate contrasting artifacts. None of those
  earlier checkpoints received development measurement, so the recipe-level
  negative conclusions cover the terminal artifacts that were tested and leave
  the alternatives unmeasured.
- **OI-004 progression evidence:** I9 and I10 made supported changes from reward
  shaping to representation and then action design. I12 used completed
  mechanism evidence to redirect. I13 is a positive counterexample: after the
  recipe result, goal review ran M25 to discriminate branch- and
  trajectory-conditioned arrival states before opening I14. The progression
  defect is therefore not a universal train-after-failure rule.
- **Direct progression failures:** I11's planned residual-margin measurements
  failed and produced no evidence, but the inquiry still concluded that the
  unchanged paired outcome justified moving to plant-level control. I14 found
  a modest failed-case margin improvement together with more interruptions; its
  frontier called for a different mechanism or redirection, yet its checkpoint
  selected the exact same question for I15. These are the strongest OI-004
  examples in this campaign.
- **Boundary:** this entry changes issue status and records a read-only RCA. It
  does not approve a prompt or contract repair, reject the broader method, add
  Runner scientific judgment, or require evaluation of every checkpoint. No
  campaign was launched, resumed, reset or trained.
- **Next step:** propose a bounded OI-004 change that improves candidate
  nomination and requires the next direction to follow the recorded evidence
  and decision frontier. Present the proposal for maintainer approval before
  implementation.
## 2026-10-09: implement the bounded OI-004 progression repair

- **Approved scope:** improve candidate nomination, preserve missing
  discriminating evidence as unresolved, and connect the next direction to the
  completed evidence and recorded decision frontier. The repair does not add a
  Runner scientific gate, an operation count, compulsory measurement,
  automatic method rejection or a requirement to evaluate every checkpoint.
- **Program contract:** training dynamics and saved checkpoints can nominate
  artifacts for development measurement, but do not establish development
  performance. The terminal checkpoint has no privileged status. The PI
  selects the artifact or comparison that best addresses the frontier. Failed
  or unavailable planned evidence remains unresolved, and mechanism conclusions
  and redirects use completed evidence with recipe-specific limits preserved.
- **Ordinary-session prompt:** the decision instruction now asks the PI to
  review completed evidence, the learning trajectory and unmeasured artifacts;
  distinguish nomination from development evidence; preserve missing evidence;
  and state which evidence supports continuation, redirection or obtaining the
  missing evidence.
- **Fixed-context subsession checks:** four cases covered an earlier training
  peak versus a terminal checkpoint, identical aggregate outcomes with a failed
  mechanism diagnostic, a supported recipe-level redirect, and a proposed
  repeated question that contradicted the recorded frontier. The guidance kept
  training facts as nomination evidence, preserved the missing mechanism result
  as unresolved, permitted the supported redirect with limits, and rejected the
  unsupported repeated question.
- **Validation correction:** the first prompt draft asked how "the selected
  result" would change direction, which implied choosing an outcome in advance.
  It now asks how the decision-relevant possible outcomes of the selected
  operation would affect direction.
- **Validation:** `run_research.ps1` parses with zero PowerShell errors and the
  touched-file whitespace checks pass. No campaign was launched, resumed,
  reset, trained, measured or evaluated.
- **Status:** OI-004 implementation is complete. Its campaign effect remains
  unmeasured. OI-013 and OI-014 remain separate open issues; this change may
  affect their observed symptoms but does not close them.

## 2026-10-09: refine OI ownership from the detailed I9-I15 RCA

- **Scope decision:** keep the approved OI-004 program and prompt repair
  unchanged. Do not combine evidence inspection, scientific progression and
  experimental realization into one broader harness change.
- **OI-003 evidence:** completed M11 artifacts contained arrival-speed
  diagnostics that the I9 interpretation described as unestablished. M13
  recorded equal complete-success labels for T13 and T3, but T13 had 155 first
  reaches and 6 interruptions versus T3's 157 first reaches and 4
  interruptions. I11 nevertheless described reach and hold behavior as
  preserved. These are inspection and interpretation findings, not new
  checkpoint-selection requirements.
- **OI-004 refinement:** terminal-only checkpoint nomination remains supported.
  The progression finding is narrower than an automatic train-after-failure
  loop. I12 obtained M18, I13 obtained M23, and goal review obtained M25 before
  opening I14. These are evidence-dependent progression counterexamples. The
  bounded OI-004 repair remains implemented, but its campaign effect is
  unmeasured and the issue is not closed.
- **OI-015 opened:** T16 and T17 had different intended source snapshots, but
  corresponding saved learned-policy and optimizer members, all 24 training
  records, and the complete 160-episode measured behavior were identical. The
  runtime artifacts differed, so the complete candidates are not described as
  byte-identical. The available evidence does not identify the cause or prove
  that the T17 experimental distinction was active. This realization gap is
  separate from OI-014's bundled-change attribution problem.
- **Boundary:** this update records issue ownership and evidence only. It does
  not alter the OI-004 implementation, approve an OI-003 or OI-015 repair,
  modify scientific code, or launch, resume, reset or train a campaign.
