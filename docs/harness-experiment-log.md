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
prompts or SDK settings. The startup-wording correction below now distinguishes
selecting and investigating a scientific question from formally opening an
inquiry. It does not change phase permissions or prescribe an instrument.
Campaign `48993cfd` exercised that clarification with a completed plant probe
before checkpointing or training. Its later M5 closure nevertheless lost a
substantial outer-reaching gain behind an aggregate regression, despite
advertised diagnostics. The question-based inquiry-objective experiment below
now targets that framing gap without changing closure criteria or adding
scientific gates. Its behavioral effect remains unassessed.

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

### Current backlog (2026-10-02)

| Item | Status / boundary |
|---|---|
| Reliable measurement-evidence inspection | Discoverability provisionally retained. In `48993cfd`, M5 feedback supplied both artifacts, diagnostic paths, radius/first-reach fields, and full inventories, but the PI closed without inspecting the strata and incorrectly claimed no outer-reaching gain. Decision-linked inspection remains unresolved. |
| Context flooding | Brief-only compaction implemented below: 57.39% smaller on the completed campaign, with all candidates and inventory references preserved. Campaign benefit remains unassessed; prompt replay and SDK output handling are unchanged and remain separate possible work. |
| Training-shaped inquiry commitments and scientific continuity | Open. Verified subcase: aggregate regression mistaken for mechanism failure, losing subgroup gains and tradeoffs in closure and the next inquiry. The isolated question-based inquiry-objective experiment below is implemented for observation; it is not a demonstrated solution. Startup clarification is retained, and scientific-model framing remains an unproven lead. |
| Checkpoint nomination and evidence selection | Deferred behind progression; available training facts are not proof of development performance. |
| Operation-submission handoff clarification | Still unimplemented. |
| Explicit protection of the old protocol log | Still unimplemented; read-access policy is a separate decision. |
| Console clarity and maintainer-file read controls | Separate deferred work; read restrictions are not the established remedy for the present evidence-inspection failure. |
| Publication/recovery, maintainer training allocation, and goal-review role availability | Implemented; not active repair items. |

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
  guidance and align `research/program.md`. Question, goal connection, and
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
  metadata" addition from `research/instruments.md`, restoring that document
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
  `f986a2c` in `research/instruments.md`. No executable code, phase prompt,
  scientific model, training recipe, or campaign operation changes.
- **Archived model references:** the winning campaign
  `77a975a5-9917-4178-ad06-ede00161560f` published
  `research/scientific_model.md` in `7d88b15`; its frozen content is also
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
  operation records and terminal result in `research/research_state.json`,
  detailed measurements under `research/evaluations/010714c2-5abd-4836-96bd-364caaf82042/`,
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
- **Approved scope:** `research/build_research_brief.py`, directly affected
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
  addressable through `research/research_state.json`'s candidate registry.
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
  artifacts under `research/evaluations/48993cfd-1808-4db6-a7b8-000fd5daba50/`;
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
