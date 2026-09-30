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
operation availability, terminal prerequisites, and the meaning of best-known;
the scientific-frontier instruction experiment below is now active as a
separate, untested behavioral hypothesis. The inquiry architecture and
independent runtime fixes remain unchanged.

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

- **Commit / scope:** `b4f1cdf`; `research/program.md`, `run_research.ps1`.
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

## 2026-09-29: reduced scientific handoff - reverted after the I15 campaign

- **Commit / baseline / scope:** `c0cfcb6` on `4a48da9`, whose harness matches
  `b4f1cdf`.
  `run_research.ps1` and `research/build_research_brief.py`; this log records
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
  fields in `research/program.md`. Restore the cautions against treating a
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

## TODO: restore the maintainer-owned training allocation

- [ ] Restore the 120,000-step per-run training allocation, configurable only
  by the maintainer. Neither the PI nor the Runner may independently change it.
  Preserve that boundary in request validation and execution, and cover it with
  targeted behavior tests.
- **Provenance:** `034daed` replaced the Runner's maintainer-controlled
  `--timesteps` allocation (default `120_000`) with PI-authored `steps` checked
  only for positivity. This transferred budget authority rather than merely
  removing an illustrative number from a PI-visible contract.
- **Status:** pending implementation. This entry does not change or interrupt
  the current training operation.
