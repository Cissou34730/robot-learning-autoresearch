# Harness change tracker

Maintainer-only tracking record for harness changes and open issues. This file
is deliberately compact. It records current status, evidence, decisions and
next actions; it does not reproduce full RCAs, campaign logs or prompt text.

## Operating rules

- **Human:** owns the goal and approves scope.
- **PI/Researcher:** owns scientific interpretation, experiment design and
  training decisions.
- **Runner:** operates the lifecycle, enforces mechanical contracts and records
  evidence; it does not make scientific judgments or coordinate PI coding,
  diagnosis, debugging or repair decisions. This boundary is immutable.
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

## Current architecture and operational status

**Reviewed 2026-10-21.** This is an engineering status summary, not a new
campaign-result report.

- The standalone harness repository is `robot-learning-harness`, published on
  GitHub's default branch `harness`. PI-owned science, state and artifacts live
  in the independent, local-only `robot-learning-campaigns` repository.
  The old inquiry-centered-lifecycle worktree remains a forensic safeguard.
- Launch/reset use `-CampaignRoot` (default: sibling campaign folder), the
  harness Python environment and a per-campaign mutex. Both restore the
  caller's folder on exit. Baseline v3 is a local recipe tag used with
  Fresh/RecipeRef. There are no full reset backups.
- Migration repairs cover absolute contract read aliases (`2a35d7b`),
  training-log classification/ignore rules (`1a794c3`), generated-file audit
  coverage (`d8c812f`), and launcher/reset folder restoration (`3ce7063`,
  `2c4bfde`). The generated-file/path/access suite passed 78 checks; the final
  shell-location suite passed 13. These are targeted implementation results.
- The full suite at physical separation had 500 passes and 44 failures
  identical to the saved pre-refactor baseline. It is not a green full suite.
  Historical green runs below describe their named revisions, not today's code.
- OpenCode Zen/Go now route through Copilot SDK 1.0.19; the separate legacy
  TypeScript adapter is not the current runtime. Native coder/reviewer use
  Copilot; reviewers use high reasoning. Scientific-model preparation on
  Copilot uses max reasoning.
- A live separated campaign ran, then hit the migrated training-log rejection.
  That ownership gate was repaired and checked against the preserved state.
  Restarting its fatal conversation exposed a distinct recovery mismatch
  (OI-037). That incident did not complete official assessment.
  Its recovery path remains unverified. The maintainer closed OI-037 on
  21 October without requesting further recovery work.
- `run_research.ps1` refuses to launch or resume while the harness worktree
  has uncommitted or untracked changes (`7f562d91`).
- On 21 October, campaign `2d4fcc0e` ran on the separated layout through
  official assessment and passed at 200/200. This does not exercise the
  OI-037 recovery path.

Current commands: [README](../README.md), [reset guide](reset-research.md),
[split design and correction record](harness-campaign-split.md).

## Failed campaign `5d94bf8a` (23 October)

**Outcome.** The official assessment failed at 193/200 (96.5%) with
T3:checkpoint-40960. This was the first campaign on branch `system-prompt`
(OI-041, `3afe89f2`). It ran 4 h 45 min with 31 PI sessions, 13 inquiries,
7 training runs and 35 measurements (3 failed), for 151.17 AIU (PI 102.95,
coders 34.85, reviewers 13.37). Model and reasoning settings were the same as
in `cfa88359` and `6882b9ec` (gpt-6-luna; PI high, analyst max).

| Campaign | Result | Wall time | PI sessions | Inquiries | Training (fresh/transfer) | Measurements | AIU |
|---|---|---|---|---|---|---|---|
| `2d4fcc0e` | passed 200/200 | — | — | — | 4 runs | — | 77.7 |
| `6882b9ec` | failed 193/200 | 146 min | 15 | 5 | 3/1 | 10 | 68.6 |
| `cfa88359` | passed 199/200 | 65 min | 6 | 2 | 2/0 | 7 | 30.1 |
| `5d94bf8a` | failed 193/200 | 285 min | 31 | 13 | 1/6 | 35 | 151.2 |

**Scientific path.**

| Phase | Time | AIU | Events |
|---|---|---|---|
| 1. Baseline and range gap | 0–50 min | 20.6 | The analyst model omitted the 14–20 cm training range. Startup trained T1 on the unchanged recipe (110/160). I1 traces led the PI to the range gap. T2, a transfer with 6–20 cm targets, scored 157/160, then 195/200 research and 196/200 task reference. |
| 2. Selection and sector | 50–105 min | 22.2 | Checkpoint comparisons in I2–I4 and a five-arm goal-review measurement (M5). I5 located failures in a rear bearing sector. T3, a transfer with 50:50 sector oversampling, gave no clear gain (193–197/200). I6 screened another T3 checkpoint. |
| 3. Six interventions | 105–270 min | 100.1 (66%) | All started from T3 weights and all were negative: T4 capture-speed cost 190 against 193/200; T5 shell progress reward 190 against 195; T6 velocity-servo overlay 174 against 194; T7 IK feasibility cue 128 against 194; frozen 5° shoulder shield 380 against 393/400; frozen predictive projection 375 against 383/400. The phase also had 12 trace diagnostics and 3 failed measurements; M19 and M20 failed identically on the PI's own float check. |
| 4. Assessment | 270–285 min | 8.2 | M34 390/400; M35 task reference 198/200; assessment 193/200. |

Six inquiries contained one operation each. The 14 goal reviews cost 34.4
AIU. Twelve measurements ran outside inquiries.

**Cause of the plateau (maintainer analysis).** The failure is one-sided.
Over its 2,600 research episodes, T3:checkpoint-40960 fails 61/240 (25.4%)
at bearings −150° to −120°, 0/216 in the mirror bin 120° to 150°, and
15/2,144 (0.7%) elsewhere. The same weakness is present in T1 (14/27 against
0/20 in the mirror bin) and T2:checkpoint-90112 (26/131 against 0/125), so it
passed through the transfer chain. The arm, its ±170° joint limits, zero
gravity and the reset are mirror-symmetric about the x axis; the asymmetry
belongs to the learned policy, not the task. The PI described a "rear
sector" with shoulder-limit proximity and never compared the mirror sector.
In `cfa88359` the PI tested reflection symmetry and passed with a
reflection-canonicalized policy I/O trained fresh. `6882b9ec` failed with the
same weakness (−155° to −120°, 31%). Neither scientific model, before or
after OI-041, states the mirror symmetry.

**Assessment decision.** Pooled research evidence for T3 was 2,524/2,600
(97.1%), a pass chance of about 0.3; the PI cited 0.267 and 0.382 for its two
evaluation versions. It chose the fixed task-reference panel, 198/200 (0.778),
because that panel uses the protected execution path. The panel composition
is normal (45/200 rear-sector episodes, 22.5%); it held 2 sector failures where
about 5 were expected. The task reference is one fixed 200-episode panel, and
the PI had changed its research evaluation semantics during the campaign
(`604d52985c97` to `d844c174d575`). The decision repeats `6882b9ec`.

**Effect of OI-041.**

- Mechanics as intended: no reference re-read in 31 PI sessions; three
  compactions (236k to 44k, 249k to 64k, 267k to 79k tokens) kept the 23k-token
  system part, with no later re-read. PI AIU per session at equal depth:
  sessions 1–6 2.53 (`cfa88359` 2.68, `6882b9ec` 3.13), sessions 7–15 2.14
  (`6882b9ec` 2.13). `view` calls per session 4.7 against 7.3 and 8.1.
- Attributable regression: the analyst read 6 files instead of 38 and
  omitted the training range, and the startup message no longer carries the
  model synthesis. Startup trained the unchanged recipe; full-range exposure
  came about 30 minutes later. `cfa88359` and `6882b9ec` trained the full range
  in their first run. The scientific-model phase cost 3.52 AIU against 6.89
  (`cfa88359`) and 6.87 (`6882b9ec`), with 17 tool calls against 56 and 84 and
  322 s against 493 and 651 s. The new model was better structured but lost
  the training-range gap and the singular start posture.
- Not attributable from this campaign: the plateau and the assessment
  decision repeat `6882b9ec`, which ran before OI-041.
- Probable contributor, not verified: a more defensive PI. Six inquiries
  only validated or compared checkpoints; all six interventions protected T3
  (transfers or frozen overlays) instead of retraining a changed method. Per
  10k characters of PI records, against `6882b9ec` and `cfa88359`: "limited"
  2.3 (1.2, 0.3), "fresh panel" 1.8 (0.7, 0.3), "pre-specified" 1.7 (0, 0),
  method-level terms 0.8 (1.0, 4.8). The system prompt gives `program.md`,
  whose guidance is mostly limits on claims, system-level weight on every
  turn. The new tone adds "Claim no more than the tested implementation and
  the recorded evidence show", and the SDK "bias to action" text, the only
  counterweight, was removed. One campaign cannot separate this from
  run-to-run variation.

**Candidate follow-ups (not approved).**

1. Analyst: read the full recipe, including training environment and reward,
   and state the system's physical symmetries and invariances.
2. Startup message: restore the model's decision-relevant synthesis.
3. Inquiry objective: restore the persistence sentence.
4. Rebalance the system prompt: remove the caution added by the new tone.

New capabilities, such as task-reference panels with PI-chosen seeds, wait
until the core behavior is fixed (maintainer decision, 23 October).

## Completed campaign `2d4fcc0e` (21 October)

**Outcome:** T4 checkpoint 120,832 passed the official assessment at 200/200.
The campaign used the unchanged harness commit `7f562d91`.
The same selected artifact scored 400/400 on two fresh local panels and
200/200 in protected development evaluation before assessment.

**Decision behavior:** the PI rejected T3's proposed improvement after an
independent confirmation did not support it. The PI then developed T4,
checked its actual execution, and requested assessment without exhaustive
ablations. These observations support OI-005, OI-014 and OI-036 closure.
They do not isolate a prompt effect or guarantee future decisions.

**Method:** T4 combines a selected IK branch, joint-space PD control, a
learned residual and a slew limiter in its saved policy runtime.
This is a hybrid controller, not PPO alone. The measurements do not isolate
the contribution of learning or each changed component.

**Maintainer resources:** four 120k allocations produced 483,328 actual
training steps and 96 archived candidates. Total usage was 77.7488285 AIU:
PI/preparation 59.8567265, coders 13.2948005 and reviewers 4.5973015.
This is 27.7% above `758843c0` at 60.8711035 AIU.
Scientific performance improved. Lower total cost is not demonstrated.
The 120k allocation, three-candidate evaluation limit and final benchmark
remain fixed constraints.

**Remaining limits:** the PI overstated the training-success plateau.
Twelve reports between steps 58,368 and 69,632 were 0.99, not 1.00.
The measured evaluation scores remain correct. This observation belongs
under OI-025, not a new issue.
The startup interruption came from the maintainer closing the laptop.
It is not evidence of a harness stall or fatal-conversation recovery.

The [campaign report](research-overview/robot-campaign-2d4fcc0e-20261021.html)
preserves the detailed analysis.

## Historical campaign baseline (12 October)

**As of 2026-10-12**

- Latest completed campaign: fresh v3 campaign `f917968b`.
- Latest attempted campaign: `90563aac`, paused after all 15 inquiries closed.
  No official assessment or scientific conclusion was recorded.
  Eleven trainings completed (1,329,152 actual steps), 26 measurements completed,
  and 12 measurement attempts failed. Best development evidence was 153/160.
  Final recorded cost was 263.614205 AIU: PI/preparation 202.243796 and
  coders 61.370409 (23.28%). Another 162.310939 AIU followed the first 153/160
  result without a higher score. This is observed plateau cost, not isolated
  prompt causality.
- Earlier attempted campaign: tooling campaign `0d39d52c`, stopped by the
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
  ordinary PI prompts. The later `90563aac` plateau exposed asymmetric
  continuation reasoning. The newly approved OI-005/OI-014 adjustment removes
  the assessment-only burden and connects proposed methods to actual tested
  implementations. Its campaign effect is unmeasured. OI-004 remains unchanged.
- Latest completed-campaign resources: nine training operations (1,087,488 steps),
  thirteen completed measurements, nine inquiries, 156.47 AIU and 54m09s PI
  time. Previous campaign: 845,824 steps, eight measurements, three inquiries,
  77.03 AIU and 29m02s PI time. Extra inquiry work accounts for most of the
  increase; this comparison does not isolate a wording effect.
- No campaign operation ran during implementation checks. The maintainer
  separately authorized publication, one fresh v3 reset and one visible-console
  campaign launch after the four adjustments are complete.
- The fifteen-inquiry limit remains a checkpointed operational pause, not a
  scientific-exhaustion result.
- The full startup-budget review remains open.
- The latest successful campaign does not establish that every representation,
  robot or velocity encoding will work; its claim is bounded to the measured
  artifacts and panel.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Open** | The issue needs investigation or a repair. |
| **Observed** | The change exists. Campaign evidence shows some intended behavior. The complete effect remains uncertain. |
| **Needs recovery check** | The retry code exists. Recovery from a real service error of the same type remains unconfirmed. |
| **Closed** | Work ended through a supported repair or an explicit maintainer decision. The entry states the closure basis. |
| **Retired** | The concern no longer requires a separate repair. This status does not claim a repair. |
| **Paused** | The maintainer suspended the proposed change. |
| **Proposal** | The maintainer did not approve the proposed change. |
| **Withdrawn** | The maintainer rejected or withdrew the proposal. |

## Outstanding issue register

**Status and description review: 24 October 2026.**

Five issues require work. One change needs more evidence. Thirty-two issues
are closed. Twelve entries are inactive. All 50 issue IDs remain.

The maintainer approved closure of OI-005, OI-014 and OI-036.
The maintainer also closed OI-033 and OI-037 without a verified recovery claim,
and OI-021, OI-026, OI-038 and OI-046 by decision on 22 October.
OI-040 to OI-047 replace the former follow-up items outside the register.
OI-006 is retired because the training allocation remains a fixed constraint.
Retirement does not claim that this allocation is optimal.

### Terms

| Term | Meaning |
|---|---|
| PI | The principal investigator agent that chooses and interprets scientific work. |
| Runner | The program that checks and executes PI-approved operations. Runner does not make scientific decisions. |
| Operation | One approved action, such as a measurement or a training run. |
| Inquiry | A bounded scientific question that can contain several operations. |
| Candidate | A saved policy that the PI can evaluate. |
| Recipe | The scientific source files and parameters that define a training method. |
| Training checkpoint | A saved version of a policy during training. |
| Policy runtime | The saved functions that convert observations into policy inputs and policy outputs into actions. |
| Protected evaluation | An evaluation that uses human-owned task checks and the saved policy runtime. |
| Official assessment | The final protected evaluation that records the campaign result. |
| Artifact | A recorded output file from a completed operation. |
| Fingerprint | A recorded value that identifies the exact contents of a file. |
| File scope | The exact files that a coding agent can read or change. |

The descriptions use short sentences and consistent technical terms.
This review does not certify compliance with the official ASD-STE100 dictionary.

### Open issues — 5

These issues need investigation or design before a repair.
This register does not authorize runtime changes or campaign operations.

| ID | Issue | Status | Next action |
|---|---|---|---|
| OI-024 | The PI repeats measurements because the first request omits required diagnostic fields. The prompt guidance did not prevent this pattern. | **Open** | Separate avoidable reruns from fresh panels, matched controls and corrected diagnostics. Permit reuse of prior results. Preserve PI judgment. No automatic duplicate gate is approved. |
| OI-025 | The PI can confuse measurement fields or state conclusions that the data do not support. Later accurate summaries do not explain the earlier errors. | **Open** | T4 trace complete (2026-10-21): the query reply was complete and correct (79 records, not truncated, 12 values at 0.99 between 58,368 and 69,632). The PI wrote "stayed at 1.00 through 120,832" 18 seconds after reading it; M16 and E26 repeated the claim. Classification: PI interpretation error, no tool defect found. Optional tool `training_series_statistics` (window summary with PI-chosen checks) was added on 2026-10-21. No campaign has used it, so its effect on this error is unmeasured. Preserve the historical evidence. |
| OI-039 | The paired success difference between candidate and reference has an exact sign-test p-value but no confidence interval. | **Open** | Optional tool `episode_outcome_breakdown` (2026-10-22) reads recorded measurements and gives the exact sign test and a Wilson interval for the first measurement's share of discordant episodes, per stratum when asked. The maintainer reversed "no harness tool": in `e7dbbece` the PI rebuilt this comparison itself (607 lines). The tool is optional, reads protected paired counts unchanged, and the PI-owned `comparison.py` stays available. Track use. Use: 8 calls in `cfa88359`, 45 in `5d94bf8a`. |
| OI-040 | The console shows no progress while a PI model request runs. The PI also lacks clear guidance about when to checkpoint a session. | **Open** | Show the elapsed time of the current PI model request. Change checkpoint guidance only if a campaign shows a defect. Faster responses do not show recovery from a stalled request. |
| OI-041 | The PI role arrives in the first user message. The SDK system message stays at its default. | **Open** | Decided 2026-10-22: `customize` mode on SDK 1.0.26 (runtime 1.0.103). Remove or replace the coding-agent parts that conflict with the PI role: the identity, `code_change_rules`, the coding tone, and in `runtime_instructions` the `autonomy_and_persistence` ("bias to action"), `subagent_usage` ("use custom agents sparingly"), editing, destructive-action, session-folder, GitHub-reference and commit-trailer blocks. Keep `safety`, `tool_instructions`, system notifications and tool-use guidelines. Replace the tone with a scientific reporting tone. Move campaign-invariant content into the system prompt: the PI role, the authority boundaries, `scenario.md`, `program.md`, core `instruments.md` and the frozen scientific model; the opening analyst gets its own prompt with its contract files. Each moved file leaves the first-message list, and the path policy refuses re-reads of exactly those files. **Warning:** context compaction ran in PI inquiry sessions of `49e58c12`, `573d538c`, `4a65a241` and `fd2afc2e` (about 220k tokens reduced to about 25k), which removes first-message content. Before re-reads are blocked, verify that the customized system message survives compaction unchanged; the console must flag every compaction with the tokens removed. Keep the coder and reviewer prompts separate and check whether they inherit the session system message. Evaluate scientific outcomes separately from the prompt integration. The approved plan is in [OI-041 system-prompt plan](#oi-041-system-prompt-plan-22-october); work is on branch `system-prompt`. First campaign `5d94bf8a` failed at 193/200: mechanics held (no re-reads, compaction kept the reference, equal per-session cost); the analyst's lean reading delayed full-range training; the plateau and assessment decision repeat `6882b9ec`. See [Failed campaign `5d94bf8a`](#failed-campaign-5d94bf8a-23-october). |

### Changes that need more evidence — 1

Context compaction and context-size reductions show intended behavior in
campaign records. Their effect on sustained context growth over a long campaign
remains unconfirmed.

| ID | Issue | Status | Remaining check |
|---|---|---|---|
| OI-008 | Repeated context can increase cost and obscure current evidence. | **Observed** | Size reductions since 21 October: per-operation instrument files instead of one contract; first-message context files for PI sessions (effective from `e7dbbece`) and for the opening scientific-model session (2026-10-22); `campaigns/results.jsonl` read through `artifact_evidence_query`; context bands in the console. PI AIU per session: `49e58c12` 5.10, `e7dbbece` 2.88, `6882b9ec` 2.80, `cfa88359` 3.29. After startup the PI re-reads almost no contract files. The opening session's `contracts/scenario.md` re-reads fell from 21 to 0 in `cfa88359`; it still re-read `authority.md` (11) and `policy_runtime.py` (6), which are now included. Remaining check: context growth and cost across a campaign longer than about 15 sessions. Keep the complete history accessible. Do not infer a context repair from faster model responses. |

### Closed issues — 32

Most closures reflect recorded repairs.
OI-021, OI-026, OI-033, OI-037, OI-038 and OI-046 were closed by maintainer
decision; OI-033 and OI-037 without verified recovery.
Closure does not establish scientific success or cover every future case.
An unrelated official assessment is not a condition for closure.

| ID | Original issue | Status | Closure basis and limit |
|---|---|---|---|
| OI-001 | The first PI action can ignore the initial scientific model. | **Closed** | Startup connects the physical model to the chosen scientific action. A training run is not a mandatory first action. |
| OI-002 | An inquiry can continue without a clear end condition. | **Closed** | The PI can close an inquiry with a positive, negative, or limited result. |
| OI-003 | The PI can treat unread evidence as absent evidence. | **Closed** | Scientific conclusions identify their evidence. The PI distinguishes unread evidence from absent evidence. Separate interpretation errors remain under OI-025. |
| OI-004 | The PI can prefer the last training checkpoint without a comparison with relevant alternatives. | **Closed** | The PI selects candidates from training context and measured results. The PI does not need to evaluate every checkpoint. |
| OI-005 | The PI can continue research without a balanced comparison with official assessment. | **Closed** | Goal review compares official prospects with further work and considers selection bias. In `2d4fcc0e`, the PI continued at 97.2% on pooled fresh panels and requested assessment at 400/400. No automatic assessment rule or readiness condition was added. Closure does not guarantee future assessment success. |
| OI-009 | A request to save a session can list the wrong completed operations. | **Closed** | The interface supplies the session identity and exact operation list. Rejections show submitted and expected values. This repair does not recover a fatal conversation. |
| OI-011 | Unclear console paths and file access rules can hide errors or expose protected files. | **Closed** | The console identifies evidence paths and query options. Phase-specific access rules protect maintainer files. |
| OI-014 | The PI can claim a new method or a cause that the tested code does not establish. | **Closed** | In `2d4fcc0e`, the PI closed T3's inquiry after confirmation did not support its proposed gain. T4's claimed method exists in the tested code and saved runtime. Execution traces support its realization, not isolated component causality. |
| OI-015 | A recipe restore can replace unrelated sources and remove scientific tools. The saved record can obscure the actual experiment. | **Closed** | A restore names exact source files and preserves unselected files and laboratory tools. Source records and parameters show the actual experiment. Scientific intent remains PI work. |
| OI-016 | A new inquiry can repeat resolved work or inherit an outdated next question. | **Closed** | The PI preserves inquiry boundaries. Goal review can revise the next question from current evidence. |
| OI-017 | The PI cannot inspect required values inside a saved artifact. | **Closed** | The evidence tool reads selected values from the recorded file. It checks the fingerprint before access. |
| OI-018 | Unclear query arguments can cause repeated errors or return too much evidence. | **Closed** | The query interface defines limits and filters. It rejects invalid fields and supports complete retrieval through explicit pages. Large-file issues have separate records. |
| OI-019 | The current goal gap can contradict the final official result. | **Closed** | The brief uses the official result for the current gap. It labels the earlier PI record as historical. Closure does not imply campaign success. |
| OI-021 | The initial prompt supplies task-specific ideas before the PI analyzes the robot. Those ideas can bias later scientific choices. | **Closed** | Closed by maintainer decision on 22 October. The preliminary session builds the physical model from the human-owned definitions of the robot, simulator and task, labels recipe code as a design choice and selects no intervention; the PI selects interventions. The planned impact analysis was not completed. |
| OI-022 | Extra process output can corrupt the exit code and cause a false rejection. | **Closed** | The process helper returns one exit code. It keeps unrelated output separate from that value. Retry limits and operation checks are unchanged. |
| OI-023 | A search through a permitted folder can expose protected files below that folder. | **Closed** | Search tools exclude protected files before they inspect content or return paths. This repair does not create an operating-system sandbox. |
| OI-026 | Source changes and review can consume resources when a requirement remains unclear. A coder cannot supply a missing PI decision. | **Closed** | Closed by maintainer decision on 22 October. Coders receive contract excerpts and the recorded structure of selected evidence (`evidence_inputs`); missing scientific decisions return to the PI; independent review remains. Coding and review cost 7.1 of 30.1 AIU in `cfa88359`. No separate clarification-cost measurement was completed. |
| OI-027 | A failed session can report an old success state or omit the actual error. | **Closed** | The response retains errors and reports timeout or interruption explicitly. This repair reports the outcome. It does not recover the session. |
| OI-028 | Publication can fail after Runner accepts a replacement request, without an explicit publication error. | **Closed** | Runner preserves the publication error across the process boundary. The controller reports a fatal publication failure without a repeat of the operation. |
| OI-029 | A malformed operation request can reach the submission channel. | **Closed** | The shared schema checks the operation wrapper before dispatch. Invalid structures receive a specific error. Scientific decisions are unchanged. |
| OI-030 | A correction request can lose or change the coder's original file scope. | **Closed** | The coding tool reuses the stored file scope for the same coder. It rejects changed scope and invalid task identifiers. Clarification cost remains under OI-026. |
| OI-031 | The PI can select an incorrect file when it copies an artifact filename. Full records can obscure the required metadata. | **Closed** | Compact lookups identify recorded operations and artifacts. The interface checks artifact fingerprints before execution. Complete artifacts remain accessible. Runner does not select scientific evidence. |
| OI-032 | A limit on complete JSON files can block access to a small required value. | **Closed** | The reader selects values from large files without a full load into memory. It preserves complete syntax checks, fingerprints, and explicit limits. |
| OI-033 | A recoverable error from the language-model service can stop a conversation after the coder completes its work. | **Closed** | Closed by maintainer decision on 21 October. The retry mechanism exists, but recovery from the original service error was not verified. No further recovery work is requested. |
| OI-034 | Repeated scans of a large JSON file can delay each query. | **Closed** | The reader reuses validation and scan locations. It limits cached records and still checks file fingerprints. Cold reads and explicit query limits remain intentional. |
| OI-035 | A temporary remote Git error can stop publication of completed work. | **Closed** | The helper retries specified server errors with the same commit and branch. The retry count is limited. Campaign repositories never push. |
| OI-036 | A controller can work in research evaluation but omit required behavior in protected evaluation. | **Closed** | T4's saved runtime contains the required controller and episode state. The same artifact scored 400/400 locally, 200/200 in protected development and 200/200 officially. Closure combines source inspection with measured use. It does not claim identical trajectories across different panels. |
| OI-037 | A fatal conversation can reject new requests while Runner still records an active session. A restart resumes the unusable conversation. | **Closed** | Closed by maintainer decision on 21 October, together with GitHub #61. No recovery repair or successful recovery verification is claimed. Completed operations and evidence are unchanged. |
| OI-038 | Reported success rates are point values. They do not state the uncertainty that comes from the number of episodes behind each value. | **Closed** | Closed by maintainer decision on 22 October. `success_rate_pass_probability` gives Wilson intervals, the pass probability and the pass probability at the interval bounds from measured counts. Training-log success rates average the last 100 training episodes in the PI-owned checkpoint callback; consecutive values share episodes and use the training distribution, so they are trend indicators, not samples. The contracts already state that training facts do not establish development performance. |
| OI-046 | A runtime change tested on frozen weights has no route to protected evaluation. | **Closed** | Closed by maintainer decision on 22 October (rule B in `contracts/instruments/coding.md`): runtime changes reach a candidate only through training; frozen-weight runtime tests are diagnostics; measurement artifacts never become candidates. The repackaging operation is not built. In `cfa88359` the PI trained T2 fresh with a reflection in its policy I/O and passed at 199/200. |
| OI-045 | Inquiry training requests must use the full 120,000-step allocation. | **Closed** | Closed on 24 October by the harness change after `efd58acc`: an inquiry run now lies between the allocation (120k) and the maintainer maximum (`-MaxTimesteps`, default 360k). Startup stays at most the allocation. |
| OI-048 | The robot contract files carry a scenario-specific name (`contracts/robots/two_joint_arm.py` and `.xml`). | **Closed** | Renamed on 24 October to `contracts/robots/robot.py` and `robot.xml`; the constant `TWO_JOINT_ARM_XML_PATH` is now `ROBOT_XML_PATH`. The XML content and its fingerprint are unchanged. Benchmark imports, protected-path lists and tests follow. The campaign repository's local tag `baseline-distinct-episodes-v3-robot` (commit `8bee2b4` on top of `baseline-distinct-episodes-v3`) updates the two recipe imports and `campaigns/task_contract.json`; Fresh resets use it. `tools/initialize_campaign.py` still defaults to the old tag. |

### Inactive entries — 12

These entries do not authorize implementation.
The historical evidence remains valid.

| ID | Subject | Status | Disposition |
|---|---|---|---|
| OI-006 | The effect of the 120,000-step training allocation on cost and scientific progress remains unknown. This allocation is not the PI session deadline. | **Retired** | The maintainer retained 120k per allocation as a hard constraint. No allocation change is pending. Continue maintainer cost monitoring without asking the PI to optimize economic cost. Retirement does not establish an optimal allocation. Superseded in part on 24 October: the standard allocation stays 120k, but an inquiry run may extend to the maintainer maximum (`-MaxTimesteps`, default 360k); see the ledger entry "Harness change after `efd58acc`". |
| OI-007 | The prompt order determines when the PI sees its role and the human goal. | **Paused** | Scientific context already precedes operation choices. The maintainer did not approve a goal-first prompt for ordinary sessions. |
| OI-010 | The old protocol log raised a separate access concern. | **Retired** | No current defect supports a separate repair. General file-access concerns belong to OI-011 and OI-023. This status does not claim a new repair. |
| OI-012 | The proposal permits separate publication of a frozen policy. | **Proposal** | The maintainer did not approve or implement the proposal. This proposal does not authorize campaign recovery. |
| OI-013 | The proposal removes the fifteen-inquiry limit. | **Withdrawn** | The maintainer retained the limit. The campaign pauses after a saved checkpoint when it reaches that limit. The resume mechanism is unchanged. |
| OI-020 | One proposed issue combined unrelated assessment concerns and task-specific terms. | **Withdrawn** | The generic issue was invalid. Assessment decisions remain under OI-005. Task-specific observations remain in their campaign analysis. This entry does not authorize a generic repair. |
| OI-042 | Each new session receives whole context files. Only named sections could reduce cost further. | **Proposal** | Distant future. One PI-selected named-sections context tool, as in the [SDK consolidation plan](copilot-sdk-consolidation-plan.md). Reconsider after OI-008 shows the remaining context cost. |
| OI-043 | Instruction changes are tested only in full campaigns. | **Proposal** | Replay one recorded PI decision point with the same fixed evidence under the old and the new instructions, with no operations, and compare the chosen action. Precedent: two fixed-evidence replays of the pre-I13 goal-review boundary of `79395c88` under OI-016; both chose differently from the campaign. A replay is not campaign evidence. No framework or test infrastructure is approved. |
| OI-044 | The PI can attribute a recorded measurement to the wrong candidate. | **Proposal** | Implement an on-demand `artifact_evidence_query` action that returns one candidate's recorded measurements if a campaign shows this error again. Precedent: E11 in `49e58c12` attributed T1's 192/200 to T2. Recorded references in `success_rate_pass_probability` already cover the counts behind pass estimates. |
| OI-047 | Code paths used only for external inference providers remain when the PI runs on GitHub Copilot. | **Proposal** | Low priority. Remove the `read` tool, `read_alias` and `json_editors` if external providers are no longer used. |
| OI-049 | The opening analyst shares the PI's system-prompt construction and differs only in a few sections. | **Proposal** | After the next campaign, give the analyst its own system prompt, designed for building a complete physical model. Evidence: in `5d94bf8a` the analyst read 6 files instead of 38 and omitted the 14–20 cm training range. |
| OI-050 | The harness lifecycle is much heavier than the workflow of a human robot-learning lab, and it slows the PI on easy tasks. | **Proposal** | Discuss later; no change is authorized. A human lab runs many cheap experiments in parallel (sweeps, several seeds, early stopping), keeps an informal notebook, compares candidates on a fixed validation set and tests once at the end, watches plots and videos of the robot, keeps continuity in the same people, edits code directly and gets feedback from colleagues. The harness runs one formal operation at a time, wraps each question in an inquiry with a closure condition, checkpoint record and goal review, applies paired statistics from the start, gives numeric evidence only, rebuilds each session from records, routes code through coder and reviewer agents, and gives no feedback during a campaign. Many rules were added to fix past failures, and many decisions follow technical constraints: one machine's compute capacity (sequential training and evaluation), LLM context exhaustion (bounded sessions, records, brief), no physical robot and no vision model (numeric evidence only), and coding efficiency and safety (coder/reviewer split, protected boundaries). Evidence: `efd58acc` used 32 sessions, 14 inquiries and about 126 AIU over about 6 h on an easy task, and most sessions served the process rather than the robot. Next step: a written comparison of each lifecycle element with the constraint it serves, whether that constraint still holds, and its cost in recent campaigns. Candidate experiment (24 October): replace the starting recipe with a minimal skeleton that keeps only the interfaces the Runner and the protected benchmark call (training and evaluation entry points, checkpoint, log and artifact formats, policy-runtime factory, observation contract) and none of the scientific choices (reward, observations, action mapping, algorithm settings, training distribution). Every campaign so far began by repairing the recipe (T1 always widened the training range); one campaign on the skeleton shows whether the PI does better when it owns every design choice. Built on branch `experiment/minimal-recipe` in a dedicated worktree. |

### Evidence and review limits

The [19 October evidence review](https://github.com/Cissou34730/robot-learning-autoresearch/blob/335877f/docs/harness-experiment-log.md#outstanding-issue-register)
preserves the detailed closure reasons, campaign labels, measurements, and check results.
The implementation ledger below preserves the earlier repair history.
Issue descriptions do not require those internal labels.

The 19 October review used campaign
`df7f6838-a5d1-4d18-9306-43ee4840cb3a`, through the checkpoint after its fifth scientific session.
The PI saved records for five scientific sessions. The PI closed two inquiries.
No official assessment occurred before that cutoff. These are dated observations,
not a live status feed.

The latest observation source is campaign `2d4fcc0e`, completed on 21 October.
It passed the official assessment at 200/200 with T4 checkpoint 120,832.
Its records are `campaigns/results.jsonl`, `runner/state/research_state.json`
and `reports/session_usage/2d4fcc0e-6634-4fa3-ba58-b06bfa149c34.jsonl`.
The [campaign report](research-overview/robot-campaign-2d4fcc0e-20261021.html)
gives the details. It is one campaign, not a controlled comparison.

The earlier review used `campaigns/results.jsonl`, `campaigns/brief.md`,
`reports/session_usage/df7f6838-a5d1-4d18-9306-43ee4840cb3a.jsonl`,
and the associated native session events.
That review covered 57 initial scientific-model sessions under the OI-021 prompt.
It supplied no unaffected campaign control.
The recorded scores remain factual.
Claims of independent discovery require this qualification.

The retry mechanism under OI-033 permits five retries with five-second waits.
Offline checks confirm the mechanism, not recovery from the original service failure.
The cause of that original request failure remains unknown.
The maintainer closed OI-033 without requesting further recovery verification.
The Git mechanism under OI-035 permits three retries with 60-second waits.
It does not repair the remote service or repeat scientific work.

### GitHub reconciliation (21 October)

| Issue | Current status | Disposition |
|---|---|---|
| [#11](https://github.com/Cissou34730/robot-learning-autoresearch/issues/11) | Closed as superseded | Current inquiry closure requires an outcome and a reason, not another measurement. Do not restore the historical evaluation-request schema. |
| [#37](https://github.com/Cissou34730/robot-learning-autoresearch/issues/37) | Closed as not planned | The proposed mandatory statistical stopping contract is not the selected design. This closure does not claim its implementation. PI assessment decisions remain scientific judgments. |
| [#41](https://github.com/Cissou34730/robot-learning-autoresearch/issues/41) | Closed by maintainer decision | The historical structural proposal is not planned. Closure does not claim that every proposed refactor was implemented. |
| [#61](https://github.com/Cissou34730/robot-learning-autoresearch/issues/61) | Closed by maintainer decision | OI-037 tracking ended without a recovery repair or verification claim. |

GitHub #37 and OI-037 are different issues.
No GitHub issues remain open at this review.

### Next maintainer actions

1. In the next campaign, check whether frozen-weight runtime tests now lead to
   a training run that carries the change (rule B in
   `contracts/instruments/coding.md`), instead of repeated controller variants
   or attempts to preserve a runtime in a measurement artifact. Check use of
   `episode_outcome_breakdown` and count PI-built lab modules that duplicate
   it. Compare AIU per PI session with `e7dbbece` (2.88) and `49e58c12` (5.10).
   Do not make the tools mandatory.
2. Classify OI-024 reruns by their actual information gain or corrected
   defect. Do not equate all repetition with waste.

These priorities authorize neither repairs nor campaign operations.

### Follow-up outside the numbered register

The former follow-up items are now OI-040 to OI-047 in the register above.

### OI-041 system-prompt plan (22 October)

Approved by the maintainer on 22 October. Branch `system-prompt`.

**SDK sections (PI and opening analyst).** Mode `customize`.

| Section | Action |
|---|---|
| `identity` | Replace with the role text (A). |
| `tone` | Replace with the scientific tone (B). |
| `tool_efficiency`, `safety`, `tool_instructions` | Keep. |
| `environment_context` | Keep. Replace with working directory and OS only if it lists hidden harness folders. |
| `code_change_rules` | Remove. |
| `guidelines`, `last_instructions` | Inspect; remove coding-agent wording. |
| `custom_instructions` | Replace with the campaign reference. |
| `runtime_instructions` | Keep `system_notifications`, `preamble_messages`, `tool_use_guidelines`. Replace `exploration_and_reading_files` (C) and `autonomy_and_persistence` (D). Remove `subagent_usage`, `editing_constraints`, `destructive_actions`, `session_context`, `github_reference_formatting`, `git_commit_trailer`. Warn on the console when a targeted block is absent. |

**Texts.**

- A (PI): "You are the Principal Investigator of an autonomous robot-learning
  research campaign." + `$piPersona` (scenario reference points to the
  campaign reference) + `$scientificModelUseGuidance` + "Direct every decision
  toward the human goal and distinguish evidence from conjecture."
  A (analyst): `$modelAnalystPersona`.
- B: "Write as for a laboratory record. Separate observation, inference and
  conjecture. Give each number with its denominator, its uncertainty and the
  operation or artifact it comes from. Claim no more than the tested
  implementation and the recorded evidence show. Be concise."
- C: "The campaign reference in this prompt holds the current content of the
  contracts and the scientific model. These files do not change during the
  campaign. Read results, artifacts and other files as the scientific question
  requires."
- D (PI only): "No human answers questions during the campaign. Call
  submit_operation with the request object. Results and changed state return
  directly to this conversation. Continue within this context until checkpoint
  or terminal commitment ends it."

**Campaign reference.** Each file once, labelled by path, under "Current
content. These files do not change during this campaign."

- PI: `contracts/scenario.md`, `contracts/authority.md`, `contracts/program.md`,
  `contracts/instruments.md`, all five `contracts/instruments/*.md` operation
  parts (measurement, training, inquiry, coding, readers; may be reduced later),
  `contracts/policy_runtime.py`, `pi_workspace/scientific_model.md`.
- Analyst: `contracts/scenario.md`, `contracts/task_spec.py`, the robot files,
  `contracts/authority.md`, `contracts/policy_runtime.py`,
  `contracts/instruments/scientific-model.md`.

**Read refusal.** The path policy refuses `view`/`read` and `rg` targeting a
reference file for the main PI and the analyst: "Its current content is in your
system prompt." Coder and reviewer reads stay allowed.

**PI first message.**

- Remove (moved): persona, model-use guidance, "Direct every decision…",
  "Human goal: …", "essential task conditions… scenario.md", the startup
  pointer to the model and program, the copied model synthesis, the pointer to
  program/instruments for the session record, source guidance variants, the
  submit_operation sentences (now D).
- Remove (repeat `program.md`): near-threshold and overstatement sentences;
  checkpoint nomination; training proxies; update the case / repeated work;
  candidate selection and mechanism test; diagnostic choice and defect repair;
  unresolved causes at closure; checkpoint timing and inquiry persistence;
  "Existing PI-owned implementations…"; the `success_rate_pass_probability`
  description.
- Keep: launcher-only guidance by session kind (goal-review prospects
  comparison, measurement outcome effect, record the choice, residual
  failures; non-goal-review distinction and outcome effect; inquiry drift),
  `next_question` rules, transition rules, allowed operations, training
  allocation, correction, state blocks, brief.
- Rewrite: source guidance ("campaigns/brief.md is included below; the latest
  scientific session record is summarized above…"); submission ("use the
  request envelope and the contract for the operation you choose; both are in
  the campaign reference. Submit one scientific action."); transition contract
  pointer; startup objective ("…as program.md 'Campaign startup' defines");
  inquiry objective (first two sentences).

**Analyst first message.** Remove the persona (also from the retry) and the
"do not open again" sentence; point to the scenario and definitions in the
campaign reference.

**Contract.** `contracts/program.md` "Context routing": the reference holds the
contracts and the scientific model; the brief is the compact current context.

**Console.** A warning card on each compaction with tokens before and after
and messages removed.

**Checks.** Rendering probe (show the final prompts); compaction probe (a
system-prompt marker survives compaction); subagent probe (coder and reviewer
do not inherit the PI system message); targeted tests (read refusal for PI,
not for coder; each reference file once). Judge behavior on the next fresh
campaign.

**Known limit.** Continuation and repair messages rebuild the whole first
message; the remaining guidance repeats in the same conversation.

**Status (22 October, implemented on `system-prompt`, not yet used by a
campaign).** Rendering: the PI system prompt is 108k characters with 11
reference files, the analyst prompt 24k with 7. Replacing the `identity` group
also drops tone and tool efficiency, so the role replaces `preamble` and a
transform removes the remaining coding-agent lines of the group. Tool
instructions also lose the GitHub CLI, GitHub MCP and code-search blocks.
Compaction probe: two forced compactions (down to 24k tokens; system part
constant at 22,062 tokens), after which the model quoted the scenario
sentence exactly. Subagent probe: a custom agent's system message is its own
prompt plus the SDK safety text; it does not contain the PI role or the
reference. `environment_context` lists no hidden folders and is kept.

**Adaptation after `5d94bf8a` (23 October, maintainer-approved).** The
laboratory tone and the neutral autonomy text removed every push to act while
`program.md`, mostly limits on claims, gained system-level weight. Our own
texts replace them; nothing returns to the SDK defaults or the old launcher
wording.

- Tone: "Report as a scientist briefing a colleague: lead with what you found
  and what you will do next, then the evidence. Give numbers with their
  source. State uncertainty where it changes a decision, not as a disclaimer.
  Be concise."
- PI initiative (autonomy block): act on the evidence; measure again only
  when the result could change the next action; after a failed approach,
  separate idea from implementation, and answer a plateau with a different
  method (representation, controller structure, training from scratch); a
  gain that leaves the main failure in place is partial; an inquiry continues
  across tests until answered or redirected; the `submit_operation` sentences.
- PI exploration: explain results from the physics (geometry, dynamics,
  limits, symmetries); a performance difference between conditions the physics
  treats as equivalent comes from the policy or the recipe.
- Analyst exploration: read the simulator configuration and the whole recipe,
  including training environment and reward; derive workspace, dynamics,
  limits, symmetries and invariances; record where the recipe departs from the
  task. Analyst autonomy: complete the model in this session.
- Reference header: the documents define the task, the rules and what a
  result may claim; for the PI, "They limit claims, not the methods you may
  try."
- `run_research.ps1` is unchanged: the removed launcher lines are in
  `program.md` or the persona, or the new texts cover them.
- The analyst gets its own complete system prompt after the next campaign
  (OI-049).

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

## Historical comprehensive RCA crosswalk

Source: [`campaign_79395c88_comprehensive_rca_20261009.md`](campaign_79395c88_comprehensive_rca_20261009.md).

This table preserves the earlier review, not current status.
The outstanding issue register above records later evidence and closures.

| RCA finding | Tracker coverage | Conclusion at that review |
|---|---|---|
| Inquiry closure became coupled to recipe switching | OI-016; related OI-002/OI-004 | Closed for the bounded defect: the current campaign used multi-operation inquiry work and did not reproduce the stale-question loop. |
| Durable handoff gave provisional decisions excessive authority | OI-016 | Closed for the bounded defect: E19 → E20 handed off the updated frontier and the campaign progressed to E21/E22 without preserving a stale question. |
| Intended method differed from implemented experiment | OI-015 | Wording repair exists; semantic realization still needs the planned replay. |
| Available evidence was carried forward as missing | OI-003 and OI-017 | Closed for the tracked defect: access was fixed under OI-017 and the current campaign did not repeat the false-absence interpretation. |
| Candidate comparisons were mistaken for causal comparisons | OI-014 | Claim limits improved in `f917968b`, but did not sufficiently update direction choices. The cumulative direction correction is unmeasured. |
| Research preferences became acceptance criteria | OI-005; campaign-specific evidence remains in the RCA | Symmetric comparison appeared in `89a6354a` E15, but threshold-trigger wording remains in its handoff. OI-005 is observed, not closed. The radius/panel symptom is not generic harness guidance. |
| The brief became large and cognitively expensive | OI-008, partly addressed | Brief compaction was implemented, but context-delivery causes and scientific effect remain unmeasured. |

## Historical RCA validation proposals

This checklist records the earlier proposals and their disposition.
It creates no current replay requirement for closed issues.
The next maintainer actions above define the current priorities.

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
| 2026-10-24 | Harness change after `efd58acc` | Maintainer decision after campaign `efd58acc` (stopped at I15 after about 6 h; 14 inquiries, 10 training runs, 53+ measurement records, about 126 AIU by I14). The learned-policy definition worked: every candidate was a network deciding each command. But the PI stalled near 97.5% for about 4 h on an easy task. **Evidence.** (1) Seed noise: the same T1 recipe (full range, fresh, 120k) scored 64% (`f83fca4d`, `cfa88359`), 69% (`5d94bf8a`), 91% (`faff0d94`) and 94% (`efd58acc`); one seed per intervention could not separate a method from its seed, and seven interventions closed as "no net advantage". (2) Re-measurement: a paired comparison required the reference in the same operation, so T2 and T5 were re-run on about 12 fresh panels each although evaluation is deterministic. (3) The PI never ran a controller, even as a reference; the scenario's prohibition read as "no controllers at all". (4) Training is cheap: a 120k run took about 3 minutes. **Changes.** (a) `contracts/scenario.md`: the clause on what measurements and diagnostics may use is removed; the scenario only defines the assessed policy. (b) PI persona (`runner/copilot/system_prompt.py`): the scenario constrains only the assessed policy; controllers, planners and robot models remain tools to understand, measure and train. (c) `contracts/instruments/training.md`: an inquiry run lies between the allocation and the longest run; a standard run uses the allocation; a longer run takes proportionally more time; each run adds time and AI usage. Guidance on when to run longer or to repeat seeds was drafted and withdrawn: the contracts state capabilities and costs, and the choice stays with the PI. A first draft also tied seeds to "regions of the robot's workspace", a scenario leak (it encoded the one-sided sector of this task). (d) Runner and launcher: `MAX_TIMESTEPS`/`--max-timesteps`/`-MaxTimesteps` (default 360,000); inquiry steps must lie between the allocation and the maximum; the session context states both. (e) Runner: a paired comparison may take the reference from an earlier completed `research_evaluation` of the same saved artifact on the same seeds under the current semantics; the accepted plan freezes those records (`reference_stored_measurements`), execution re-verifies their artifact fingerprints, and their artifacts join the comparison's `source_artifacts`. (f) `contracts/instruments/measurement.md`: the pairing rule above, and a fixed development panel (seed 100000, 400 episodes), stated without guidance on its use. Multi-seed training stays a sequence of ordinary training operations (no new operation). **Validation.** 579 autoresearch and benchmark tests pass on a clone of the renamed-robot baseline, including a new test that a paired comparison reuses the stored reference without re-running it, and the updated inquiry allocation bounds. **Watch in the next campaign:** whether the PI uses longer runs only with a stated reason, runs repeated seeds, measures candidates on the development panel and reuses stored references, uses a controller as a reference or teacher, and whether time to a candidate above 98% falls. |
| 2026-10-24 | Learned-policy definition in `contracts/scenario.md` | Maintainer decision after `f83fca4d`. The scenario required "a learned policy" without defining it; `2d4fcc0e`, `faff0d94` and `f83fca4d` passed with analytic IK/computed-torque control in the saved runtime and a network with little or no measured contribution (in `f83fca4d`, T4 checkpoints from 5,120 to 120,832 steps gave identical outcomes). The intent is to train a network, as an RL robotics team would. The scenario now defines the assessed policy: a trained network decides the motor command at every control step; the runtime builds the observation freely and maps the output through a fixed transformation that may include fixed-gain feedback towards a network target, but no planner, trajectory generator, inverse kinematics or robot model; measurements and diagnostics may use any method. Under it, `2d4fcc0e`, `faff0d94` and `f83fca4d` would not count as passes; `cfa88359` would. Also corrected `contracts/instruments/training.md`: every model-role action copies the candidate into `campaigns/checkpoints/retained/`, named by origin operation and fingerprint. |
| 2026-10-23 | Campaign report usage by role | Closed. `tools/campaign_report.py` labelled the usage of every role as PI usage. It now labels totals "all roles", adds a table by role (analyst, PI, scientific coder, scientific reviewer) and a Role column per invocation, and the comparison overview gives AIU per role. On `faff0d94`: analyst 3.71, PI 36.74, coders 9.61, reviewers 4.54, total 54.60 AIU. |
| 2026-10-23 | OI-041 third adaptation: two channels | Maintainer decision after `5e7172ca`. System prompt (how): full PI and analyst personas, tone, tools, drive to act, and the contracts reference (75k characters; the scientific model is no longer in it). First message (what): one role line ("You are the Principal Investigator described in your system prompt. The scientific model of the system you study follows."), then the full `pi_workspace/scientific_model.md`, then state, guidance and brief; the analyst's first message starts with a one-line role. The model is readable again so that it survives compaction; contract reads stay refused. Removed the two scenario-derived sentences ("conditions the physics treats as equivalent"). `contracts/program.md` "Context routing" updated. |
| 2026-10-23 | Information run `5e7172ca` on `harness` (`d07a21c9`) | The maintainer ran the pre-system-prompt setup for information and stopped it after about 1 h 40 min: 11 sessions, 3 inquiries, 3 training runs, 9 measurements, 54.44 AIU (PI 37.79, coders 11.70, reviewers 4.95). T1 (full range) was weak (120–130/200); best-known T3:checkpoint-65536 reached about 77% (307/400). The PI framed I1 in bearing and kinematic terms, derived the arm's planar mirror symmetry itself in I2 and implemented a limit-gated reflection in the saved PolicyIO; T2 and T3 were transfers. Robotics-to-RL vocabulary 0.72 (system-prompt runs 0.14). The analyst cost 6.52 AIU and 940 s; part of it was coding-prompt document housekeeping (git status, ASCII and whitespace checks over 10 patch rounds); its model mentioned elbow branches 20 times but not the ±bearing symmetry. Recorded prompts: the SDK coding system prompt (15.8k) in every session; first messages of 75k growing to 105k characters (persona, full scientific model, program, instruments, scenario, brief). No PI session was compacted. Conclusion for OI-041: the first user message decides what problem the PI works on; the system prompt shapes how it works. T1 strength differed between runs, so the visibility of the asymmetry is a confound; the vocabulary shift is not. |
| 2026-10-23 | Campaign `c06b15e4` stopped; OI-041 second adaptation | The maintainer stopped `c06b15e4` after about 55 minutes (4 PI sessions, 1 inquiry, 3 training runs, 7 measurements, 2 failed). The analyst read 17 files and covered the training range; startup trained the full range (T1 150/160). Defensive language fell ("limited" 0.4 per 10k characters against 2.3 in `5d94bf8a`), but the PI looped on training: T2 velocity damping (155/152 against 154/160) and T3 "continue PPO" (152/152 against 151/160), both null. Again 14 of T1's 20 failures lay at bearings −150° to −130° and none in the mirror band; the PI split results by radius only. Robotics-to-RL vocabulary in PI records: 0.48 in `6882b9ec` and `cfa88359`, 0.14 in `5d94bf8a` and `c06b15e4`. Side-by-side comparison of recorded prompts: before, the persona, the full scientific model and the model synthesis sat in the first user message (about 75k characters) and the SDK coding prompt pushed to implement working solutions; after, the first message held state and brief (8–22k), the model sat at characters 80,000–100,000 of a 104k system prompt, and the new initiative text named retraining first. Second adaptation: no examples or lists in our texts; the scientific model moves into the PI preamble directly after the role (characters 1,800–22,600); the drive to act reads "derive the change from the robot's mechanics and the evidence, implement it, and test it" and "when adjustments within one method stop improving the result, change the method"; PI exploration explains results through the model; analyst exploration uses the reference definitions, reads the whole recipe and derives what the system can and cannot do and which conditions it treats as equivalent. The first message is unchanged; moving the synthesis there waits until system-prompt options are exhausted. |
| 2026-10-23 | OI-041 adaptation; console fixes; OI-048/049 | System prompt: our own tone, PI initiative, physics-first exploration, analyst full-recipe exploration and a reference header that limits claims, not methods (see the OI-041 plan section). `run_research.ps1` unchanged. Console: multi-line boundary details stay on separate lines when output is piped, so TRAINING RESULTS prints one checkpoint per line; the session END card no longer shows "Usage: usage unavailable" (the usage row is written after the card), and each session prints `[session] USAGE` once its usage is recorded. New proposals OI-048 (generic robot file names) and OI-049 (own analyst system prompt). OI-039 wording corrected. |
| 2026-10-23 | Campaign `5d94bf8a` failed at 193/200; first OI-041 campaign | 4 h 45 min, 31 PI sessions, 13 inquiries, 7 training runs (6 transfers), 35 measurements, 151.17 AIU (PI 102.95, coders 34.85, reviewers 13.37). Best T3:checkpoint-40960 plateaued at 97.1% (2,524/2,600 research episodes) from about 105 minutes; six later interventions were negative and cost 100 AIU. Maintainer analysis: one-sided failure at bearings −150° to −120° (25.4%) against 0% in the mirror bin, present since T1 and inherited through transfers; same weakness as `6882b9ec`; `cfa88359` passed by reflection canonicalization. Assessment rested on the fixed task-reference panel (198/200) over pooled research evidence. OI-041 mechanics held (0 re-reads, 3 compactions, equal per-session cost); the analyst's lean reading delayed full-range training. Details: [Failed campaign `5d94bf8a`](#failed-campaign-5d94bf8a-23-october). |
| 2026-10-22 | Campaign `cfa88359` passed at 199/200; opening-session files | Official assessment passed at 99.5% (199/200) with T2:checkpoint-95232 about 67 minutes after the first session, for 30.09 AIU (PI 23.0 over 7 sessions, coders 4.95, reviewers 2.15), the lowest recorded cost. 2 inquiries, 2 fresh training runs, 7 measurements. T1 (full 6–20 cm range) scored 127/200 with failures concentrated at 0°–90°; the M3 mechanism test showed T1's actions violated planar reflection symmetry; T2 trained fresh with a reflection canonicalization in the PI-owned policy I/O (the rule B route) scored 199–200/200 against T1's 111/200 on M4. The PI did not assess on the selection-affected M4: it ran a fresh research panel (200/200) and `task_reference` (200/200) in M7, then assessed citing 96.99% pass probability and 67.43% at the interval's lower bound. `episode_outcome_breakdown` was called 8 times. Maintainer replay: 1998/2000 (99.9%) on fresh protected episodes. The opening-session first message removed its `contracts/scenario.md` re-reads (21 to 0) and cut its tool calls from 84 to 56, but its AIU stayed at 6.9 because it re-read `authority.md` 11 times and `policy_runtime.py` 6 times; both are now included. Weak points: M6 repeated M5 after a correction; one training seed. One campaign cannot attribute the pass to the harness changes. |
| 2026-10-22 | Campaign `6882b9ec` failed at 193/200; root cause | 5 inquiries, 4 training runs, 10 measurements (M6 failed after a PI evaluator change), 68.63 AIU (PI 44.8 over 16 sessions, coders 17.54, reviewers 6.29). Every change was tested by training (rule B held): T2 joint-limit inputs 107/200, T3 substep hold 3/200, T4 transfer from T1 with an occupancy reward 198/200 (M8, used for checkpoint selection) and 197/200 (M9). `episode_outcome_breakdown` was called 14 times; no `task_reference` was run. The PI assessed T4:checkpoint-115712 at an estimated 64% pass chance from M9 alone. Maintainer replay outside the campaign record: the official panel reproduces 193/200; 2,000 fresh episodes give 1927/2000 (96.35%, 95% interval 95.5–97.2%) in both the protected environment and the PI research environment, so there is no environment gap. At that rate the official pass chance was 14% and a panel of at least 197 occurs 6% of the time. Root cause: (1) a weakness the PI found in I1 stayed unresolved: radius 15–19 cm at angles −155° to −120°, 5% of episodes, where T4 fails 31%; 5 of the 7 official failures lie there. (2) Assessment rested on one 200-episode panel (M9) that held 2 sector episodes instead of about 10; the PI's M10 stratified analysis read "no clear geometry weakness" from those 2 episodes (OI-025 type). (3) Every research panel had 200 episodes; a 2,000-episode research evaluation takes about 5 minutes and would have shown 96.4%. The pass-probability figure was correct under its stated assumptions, and its interval (95.7–99.5%) contained the true rate, but one 200-episode panel cannot separate 96% from 98%. No harness change caused the failure, but goal-review text favoured assessment: "Neither an untested variant nor a candidate near the threshold justifies a choice by itself" was read as requiring a tested intervention before further work (the PI wrote "no identified, evidence-backed intervention" despite the I1 sector), and "No numerical confidence estimate or repeated measurement is required" read as one panel being enough. Follow-up: `contracts/program.md` and the goal-review prompt now say that a development result near the threshold does not establish the candidate's rate and that further work does not need an already tested intervention; the defensive sentences about eligibility, required estimates and Runner readiness are removed; `success_rate_pass_probability` also returns the pass probability at the interval bounds (197/200: 64.1%, bounds 6.5% to 99.6%). A goal-review sentence that recommends larger panels was rejected because it could drive endless measurement. The console shows Why, Rationale, Panels and Results as sections, a campaign line (elapsed time, AIU, best-known), success counts with labels, earlier episode exposure, paired counts, and a compact training summary. |
| 2026-10-22 | Campaign `e7dbbece` stopped; rule B and `episode_outcome_breakdown` | The maintainer stopped `e7dbbece` during I5 after 5 inquiries, 2 training runs and 12 completed measurements, for 71.315 AIU (PI 46.118 over 16 sessions, coders 18.108, reviewers 7.089). No official assessment. T2:checkpoint-120832 (full 6–20 cm exposure) scored 192/200 on the task reference and 191/200 and 190/200 on fresh research panels. First-message files were included and re-reads stopped. From I4 on, the PI tested runtime changes on frozen T2 weights: branch redirection 193/200 against 189/200 (4 rescued, 0 lost), near-target damping 161/200 against 186/200. I5 then tried to preserve the M11 runtime bytes inside a measurement artifact; M13 failed on its own runtime hash check. No training followed after T2. Follow-up: `contracts/instruments/coding.md` states that runtime changes reach a candidate only through training, that frozen-weight runtime tests are diagnostics and that measurement artifacts never become candidates. New optional tool `episode_outcome_breakdown` gives per-measurement successes with Wilson intervals, paired counts with an exact sign test for two measurements of the same episodes, and bins of a PI-chosen per-episode field; it verifies fingerprints and recorded counts. Validation on `e7dbbece`: M4 T2 against T1 by radius reproduces the PI's M5 (inner 103/105 against 52/105) and M6 paired counts match Runner's (52 and 5); the 64 MB M8 artifact is read lazily; mismatched episode sets, absent fields and a foreign campaign are refused. Failing tests were identical before and after (46 with the campaign root set). |
| 2026-10-22 | Pass probability from recorded measurements | The external review found E11 attributing T1's 192/200 on M1, and T1's 13.1% pass estimate, to T2. `success_rate_pass_probability` evidence entries can now pool recorded `research_evaluation` or `task_reference` measurements by operation and candidate, with an optional measurement label; Runner reads the counts, lists the sources and counts episodes shared between them. A reference that matches no single measurement is refused with that operation's recorded candidates. Typed counts remain available. The `current_goal_gap` rule asks for counts from the record of the cited operation and candidate. Validation on `49e58c12`: the E11 reference (T2 on M1) is refused; pooled T6:checkpoint-55296 on M12 and M19 reproduces the PI's 396/400 and 85.8%; pooling M19 twice reports 200 shared episodes; runtime and ownership tests pass. A pushed candidate list was rejected to avoid anchoring; an on-demand candidate lookup is deferred. |
| 2026-10-22 | Episode-seed exposure across candidates and instruments | An external review of `49e58c12` found that M19, presented as a fresh confirmation panel (seeds 20268001 to 20268200), reused all 200 seeds of PI-written M15, and Runner gave no indication: repeat detection covered only the same saved artifact and instrument. The PI then estimated a 96.99% pass chance from M19 as if independent. Research evaluations now list `episodes_seen_in_earlier_measurements` for any earlier measurement of any candidate or instrument on the same seeds. `python_module` artifacts can declare a top-level `episode_seeds` list; Runner records it as ranges and reports the same overlap. The coder's `python_module` excerpt mentions the declaration. The PI decides whether reuse matters. Validation: the M15/M19 case flags 200 shared episodes once M15 declares its seeds; the pending validator accepts the field and rejects malformed entries; failing tests were identical before and after (12 stale fixtures). The same review found E11 attributing T1's 192/200 and 13.1% pass estimate to T2; that factual-memory issue is open for discussion. |
| 2026-10-22 | Campaign `49e58c12` and follow-up changes | Campaign `49e58c12` passed the official assessment at 99.0% (198/200) with T6:checkpoint-20480, after 4 inquiries, 6 training runs and 19 measurements, for 126.566 AIU (PI 87.979, coders 28.107, reviewers 10.480). A PC reboot interrupted session S13; no operation was left pending and the campaign resumed. `success_rate_pass_probability` was called in every session kind; the PI pooled only independent panels, stated the numeric goal gap and assessed at an estimated 97.0% pass chance. No `campaigns/results.jsonl` read occurred. Peak PI context rose (median 143k) and AIU per PI session rose to 5.10. The first-message files were never sent: Runner sets `backend_session_id` at session start, so the launcher's new-conversation check was always false. A T2 runtime controller scored 199/200 and 200/200 on research panels but had no route to protected evaluation (postponed optional item below). Follow-up commits: the new-conversation check uses the launcher invocation count or the SDK session folder; `evidence_inputs` accepts a candidate (archive files and `artifact.json`); discovery past the node limit returns the paths found and a recovery hint, and a missing operations path explains list-indexed rows; the console shows the coding request, child patches and a per-minute child heartbeat, colours tool names and operation status, summarizes pass-probability evidence and series checks, and colours context at 100k and 150k. Validation used reproductions on the finished campaign's state and the existing suites; failing tests were identical before and after each change (13 in the runtime, lifecycle, session, launcher, stop-control and coding set). One campaign cannot attribute the pass or the cost to these changes. |
| 2026-10-21 | Campaign `573d538c` and follow-up changes | Campaign `573d538c` ran with the numeric tools, shorter descriptions and the instrument split. It failed the official assessment at 97.5% (195/200; the goal is 196) with T2:checkpoint-80896, after 6 inquiries, 5 training runs and 18 measurements, for 81.856 AIU (PI 56.955, coders 17.805, reviewers 7.096). T2 reached 98.5% on the task reference by I3. I4 (slew limiter) and I5 (target braking) were limited negative results. I6 ran diagnostics. The PI assessed on a pooled 980/1,000. No research and protected scores diverged, so the moved saved-controller section showed no effect. `wilson_proportion_interval` was never called; `training_series_statistics` was called 7 times. A diagnostic module failed four times in a row (M13 to M16): wrong field names, wrong success location, an expected episode absent, and a candidate folder passed instead of its `model.zip`. One campaign cannot attribute the failure to the harness changes. Follow-up commits: `success_rate_pass_probability` replaces the Wilson tool and goal review names it; `current_goal_gap` is stated in numbers; `python_module` inputs accept a candidate and `scientific_coding` accepts `evidence_inputs` (recorded field structure for the coder and reviewer); `view` and search on `campaigns/results.jsonl` redirect to `artifact_evidence_query`; a new PI conversation receives the brief, scenario, core instruments, program and scientific model inline; the console shows reader failure statuses, context growth, review verdicts, a single operation-failure card and the included files. Validation used minimal reproductions and the existing suites. Failing tests were identical before and after each change: 21 in the lifecycle, phase, session, launcher and stop-control set and 6 in the brief set, all with stale fixtures. |
| 2026-10-21 | Split `contracts/instruments.md` by use | In campaigns `2d4fcc0e` and `60ec83bd`, every PI session read the whole 37k-character file one to three times; 32 of 35 reads took the whole file. The core file now keeps the index, paths, request envelope, operations by session and the scientific session record (7.2k). The other sections moved verbatim to `contracts/instruments/`: `measurement.md`, `training.md` (with model role and recipe restoration), `inquiry.md` (with campaign conclusion), `coding.md` (with saved controller execution), `readers.md` and `scientific-model.md`. The only text change in the moved sections is one link to the saved-controller section, which now points into `coding.md`. The launcher now names the contract file for each currently permitted operation kind. Coder and reviewer excerpts are byte-identical to before. The new files are protected context paths. `program.md`, `authority.md`, `AGENTS.md` and the `submit_operation` description name the parts. A rough estimate is about 5% fewer campaign input tokens if the PI reads only the parts it uses; the effect is unmeasured. Nine phase-structure and researcher-session tests fail on the parent commit as well (for example, goal-review training now fails on field validation before the session check); they were not changed. |
| 2026-10-21 | Shorter PI tool descriptions | Rewrote the descriptions of `artifact_evidence_query`, `training_log_query`, `training_series_statistics` and `scientific_api_reference` to state purpose, modes and when a result is partial or not evidence: from 218/104/124/105 words to 83/54/55/62. Transport details such as UTF-8, base64 and fingerprint rules now appear only in the parameter fields and `contracts/instruments.md`. The `action` field descriptions of both readers were shortened in the same way. The starting context is about 11k tokens, so the expected token saving is small; the aim is clarity. The effect on PI behavior is unmeasured. `test_training_log_lookup_uses_the_training_operation_id` fails on the parent commit as well (path ownership in `runner/paths.py`); it is unrelated and was not changed. |
| 2026-10-21 | Wilson tool: PI-chosen confidence, threshold and batches | `wilson_proportion_interval` no longer fixes 95%. The PI supplies a required two-sided confidence level, up to 20 labelled proportions, and an optional threshold rate. Each interval is reported as above, below or including the threshold. The tool uses the standard-library normal quantile, with no new dependency. In campaign `60ec83bd` the PI did not call the previous version, so its use remains unobserved. Validation: a minimal `uv run` reproduction only. |
| 2026-10-21 | Repeated-measurement pending-state schema | The repeat annotation introduced by `7b7f354a` did not match the strict schema for pending measurements. Campaign `60ec83bd` remains stopped in S9 after two rejected, unexecuted replays, while M9 remains completed. Research-evaluation and task-reference plans now accept optional `repeats_earlier_measurements` and validate its exact fields, nonempty strings and positive overlap counts. Five selected cases passed, including both new acceptance/persistence/result regressions and malformed-annotation rejection, and lint and whitespace checks passed. A generic-tool test first failed only because `ROBOT_LEARNING_CAMPAIGN_ROOT` was unset; with it set, the repeat, earlier-measurement and generic-tool cases pass. No PI code or campaign state changed, unknown fields remain rejected, and campaign recovery and scientific improvement remain untested. |
| 2026-10-21 | Subsession: optional numeric tools for the PI | Added two read-only PI tools. `training_series_statistics` summarizes one metric of one preserved training log over a step window (rows, first, last, min and max with steps and counts, mean, sample sd). It also evaluates optional PI-chosen threshold checks, and min/max checks report the rows that do not meet the comparison. `wilson_proportion_interval` returns a 95% Wilson interval from PI-supplied counts. Both are documented in `contracts/instruments.md` and listed in `contracts/authority.md`. Neither tool is mandatory or judges claims. A trend interval was rejected because training curves are autocorrelated. Opened OI-038 (proportion uncertainty) and OI-039 (paired-difference interval, researcher-owned). Validation: a minimal `uv run` reproduction only, with no campaign run. The effect on PI behavior is unmeasured. |
| 2026-10-21 | Maintainer-directed recovery and structural-item closures | Closed OI-037, OI-033 and GitHub #61/#41 on explicit maintainer instruction. These are decision closures, not verified recovery repairs or completed structural refactors. Removed recovery from the active priorities. All 37 OI IDs remain: four open, one awaiting evidence, 26 closed and six inactive. No GitHub issue remains open. No runtime code, campaign state or evidence changed. |
| 2026-10-21 | Approved tracker and GitHub reconciliation | Closed OI-005/014/036 from recorded decision, implementation and saved-controller evidence. Retired OI-006 because 120k remains fixed. All 37 IDs remain: five open, two awaiting evidence, 24 closed and six inactive. GitHub #11 is superseded, #37 is not planned, and #41 remains deferred with current context. New #61 tracks OI-037. Costs remain visible: `2d4fcc0e` used 77.7488285 AIU versus 60.8711035 for `758843c0`. No runtime or campaign change was made. |
| 2026-10-21 | Dirty-harness launch refusal and goal-review guidance | Commit `7f562d91`. Campaign `4a65a241` launched with uncommitted harness changes. Runner rejected every protected evaluation, and the PI repeated checkpoint-only sessions for about six hours (205.786 AIU) until the maintainer stopped it. `run_research.ps1` now refuses to launch or resume while the harness worktree has uncommitted or untracked changes. Goal review now compares the official prospects of the strongest candidate with further work, says that neither an untested variant nor a near-threshold candidate justifies a choice by itself, and asks the PI to consider selection bias. The diagnostic sentence now reads "Choose a diagnostic when its possible outcomes would lead to different next actions." Campaign `2d4fcc0e` then ran on the clean commit and passed the official assessment at 200/200 (77.749 AIU). Both goal reviews compared prospects: the PI deferred at 97.2% and assessed at 400/400. The maintainer closed OI-005 on this evidence. The first startup attempt timed out because the maintainer's laptop was closed, not because of a harness defect. One campaign does not isolate the cause. See the [campaign report](research-overview/robot-campaign-2d4fcc0e-20261021.html). |
| 2026-10-20 | Balance PI inquiry guidance toward candidate development | Commit `2b52e36a`. An inquiry operation can state a development step and how its outcome can produce or select a better candidate. A diagnostic is worth its cost when its outcomes lead to different next actions. A repair is a valid next action when evidence locates a defect. The clause that a negative result gives no reason to try another variant was removed. The next campaign, `758843c0`, failed the official assessment at 189/200 (60.871 AIU) after 3 inquiries, 3 training runs and 11 measurements. The earlier campaign `1c940d68` also failed at 189/200. See its [campaign report](research-overview/robot-campaign-1c940d68-20261020.html). |
| 2026-10-20 | Campaign-root scientific read routing | Commit `f94a52d8` resolves campaign-owned reads addressed under the harness root. Three focused existing cases and four formerly denied live reads succeeded. Writes were not broadened. This is access evidence, not a scientific-performance claim. |
| 2026-10-20 | Repeated-episode reporting | Commit `7b7f354a` reports repeated measurement episodes and states that they are not new samples. This does not prevent omitted diagnostic fields or establish lower measurement cost. OI-024 remains open. Fresh panels and matched controls are not automatically duplicate work. |
| 2026-10-20 | Audience separation, hidden inquiry cap and contract dedupe | Commits `b16d460`..`1c44bc3`. New `contracts/authority.md` owns campaign permissions; `AGENTS.md` is maintainer-only and unreadable by campaign agents. The PI sees the opened-inquiry count, not the cap. Each lifecycle rule has one home; runtime internals moved to `docs/runtime-mechanics.md`. The reviewer fails only coder-repairable defects; the coder reports missing requirements. The resource summary now prints one candidate count. Session logs of the next campaign show no cap text reached the PI. Scientific effect is unmeasured. |
| 2026-10-20 | Remove PI cost guidance and duplicate reminders | Removed cost considerations from the goal-review prompt. Removed its duplicate comparison and eligibility reminders from the program contract. PI-facing descriptions and messages use limits instead of budget terminology. Execution limits, machine identifiers, and maintainer usage records are unchanged. No campaign operation occurred. OI-005 decision quality remains unconfirmed. |
| 2026-10-20 | Plain-language issue register | Rewrote all 37 descriptions without internal campaign labels. Separated open work, changes that need evidence, closed issues, and inactive entries. The HTML hides closed and inactive tables until the reader opens them. Shorter status labels preserve the prior decisions. The evidence review remains available in commit `335877f`. Only the two documents changed, with no runtime edits or campaign operations. |
| 2026-10-19 | Evidence-backed OI status reconciliation | Closed 15 bounded repairs: OI-004/009/015/018/019/022/023/027/028/029/030/031/032/034/035. Retired obsolete OI-010 without claiming a repair. OI-005/008/014/036 are implemented/observed, while OI-033 still needs native error-recovery evidence. Six real open investigations remain: OI-006/021/024/025/026/037. The Markdown register and all 37 HTML rows agree. Existing reproductions/regression evidence can close mechanical defects without a new official assessment. Live evidence is bounded to `df7f6838` through E10; no scientific success, causal attribution, campaign recovery or runtime change is claimed. Only the tracker and current HTML overview change. |
| 2026-10-19 | Standalone harness and local campaign repository split | Implemented with a live campaign observation and subsequent migration repairs, not a completed end-to-end scientific validation. See the current architecture section and `harness-campaign-split.md`. Absolute contract read aliases, training-log ownership, generated-file publication and caller-directory restoration are covered by targeted checks. Fatal-conversation recovery remains OI-037. |
| 2026-10-19 | Current-documentation reconciliation | Updated the main HTML overview, operator guides, agent/instrument storage context, decision log and current tracker for the physical split. Historical campaign reports and RCAs retain their original evidence and dates. Removed obsolete current claims about reset backups, the TypeScript OpenCode adapter, reviewer max reasoning and dedicated console-interrupt exit codes. No runtime behavior, PI scientific direction or campaign files changed. |
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
| 2026-10-12 | Approved adjustments to OI-005/OI-008/OI-014/OI-018 | Implemented/unmeasured. Replace asymmetric assessment wording with a short two-sided comparison. Connect method claims to actual tested source/runtime and recorded component evidence. Replace full brief replay with current-state routing and an all-training index, retaining complete checkpoint access and pairwise outcome facts without full seed lists. Clarify the shared top-level byte budget, retain explicit rejection with corrective feedback, and display artifact index on starts/failures. Targeted inert checks, registered SDK dispatch, PowerShell parsing/rendering and baseline-relative lint pass; paused campaign state, history and model hashes remain unchanged. The paused-state brief is 85.53% smaller in memory. The five implemented items awaiting review and all unimplemented OIs are unchanged. The maintainer authorizes publication followed by one fresh v3 reset and one visible-console campaign, not continuation of the capped run. Scientific effects remain to be observed. |
| 2026-10-12 | Approved tactical permission repair, step 1 of 2 | Implemented/unmeasured, separate from OI status changes. In `5da30677`, a child permission request preceded tool start by 9 ms; the old lookup depended on that later event. Permission callbacks now consume the native permission-event identity and current exact-file binding. Unknown/stale callers fail closed with a harness authorization error. Main PI writes and protected-path access remain denied. Inert actual-SDK event replay covers ordering, missing call IDs, replay, child/main identity, changed bindings and target scope without model inference or file edits. No campaign launched, resumed, reset or mutated. API-reference and early-check support are reserved for the second commit. |
| 2026-10-12 | Approved tactical API compatibility repair, step 2 of 2 | Implemented/unmeasured after the permission commit. Both PI and authorized coder can read bounded installed definitions through `scientific_api_reference`; arbitrary code, paths, private attributes and foreign-library definitions are rejected. A changed integration can return a distinct, artifact-independent compatibility mode of the scoped verification module as `proposed_compatibility_check`, using the existing Runner `python_module` path. Program guidance requires actual changed production calls before larger integration work, not only imports or saved JSON. Targeted reference/SDK-handler checks and a synthetic one-joint Runner-helper reproduction exercise corrected fields, reset, step and site Jacobian; both original missing-attribute accesses fail. Permission checks still pass and no new lint findings appear. No dependency, OI status, campaign source, state or evidence changes; no campaign launched, resumed or reset. Scientific effectiveness remains unmeasured. |
| 2026-10-12 | Approved raw-artifact ignore and publication repair | M15 in `4702776a` completed locally but its 473.0/798.5 MiB Git blobs blocked publication. Raw files now remain in the predictable ignored `campaigns/evaluations/` archive. Runner ownership, recorded paths/fingerprints and query access remain; automatic, reset and recovery staging excludes raw contents. Baseline restoration validates local data against completed records in retained schema-6 state references and copies selected files from the reset backup, preserving cross-branch imported-baseline reuse without a new registry or schema. The bounded follow-up considers retained references rather than first-parent ancestry, still matches exact selected candidate/artifact identities, and skips unsupported reference schemas without accepting them or blocking a valid source. Specific Git push errors are no longer hidden. Validation passed 35 small-file assertions with inert Git calls, including mixed-schema reference ordering, local query/integrity and backup preservation; both touched modules compile and pass targeted lint. A temporary Git fixture was blocked by permission denial; no environment repair was attempted. Authorized real-branch cleanup replaced only unpublished M15 `ec0e4ff` with `86af8bcc`, preserving every non-raw tree entry and published parent `7aef71c`. The oversized blobs never reached origin. Current tracking and unpublished oversized history are repaired; the tip has no raw entries and the unpublished range has no blob above 100 MiB. All 25 local files (1,388,353,693 bytes), exact inventory, byte sizes and SHA-256 fingerprints are unchanged, as are campaign state, results, generated history and the untracked accepted M15 handoff. Publication uses a normal fast-forward push; published history is untouched. Old objects may remain in shared local reflogs/object storage; no global GC, pruning or reflog expiration was run and disk reclamation is not claimed. No OI status, scientific trace policy, campaign state or completed measurement content changed; no campaign launched, resumed, reset, trained or evaluated, no operation accepted/finalized and no M15 rerun. |
| 2026-10-12 | Approved controller publication-diagnostic preservation | The M13 replacement acceptance stopped during publication with `remote: fatal error in commit_refs`; the controller discarded that cause and returned only Git's generic final summary. The helper now preserves all nonempty lines from the existing captured error output. Inert reproduction also confirms M12's reward checker double-counted the aggregate speed penalty and that the existing PI repair rejects incorrect scalar and aggregate attribution; that scientific file is not modified by this repair. Accepted-stage fatal classification remains unchanged. The underlying remote rejection is not explained or repaired by preserving diagnostics. No publication retry, campaign operation, pending-operation recovery or campaign-state change is authorized by this repair. |
| 2026-10-10 | Three-layer harness documentation structure | Adopted: compact tracker, curated thematic narrative and unchanged chronological archive. Narrative curation remains pending. |
| 2026-10-12 | Harness-only bug tracking: OI-027/OI-028 | The maintainer authorized investigation and tracking, not repairs. A bounded pass covered native coding, submission and session reporting. Isolated response expressions reproduce omitted runtime errors and stale status. Existing evidence confirms the accepted-stage publication classification gap. Only this tracker changes. No runtime or PI source changed. No human tests, live SDK session or campaign operation ran. Campaign state, history and the live request remain unchanged. |
| 2026-10-12 | Approved OI-027/OI-028 reporting repairs | Session outcomes now retain SDK errors and distinguish failed exits, timeout and interruption from the last operation status. A typed push failure crosses the existing subprocess boundary through exit code 3. Both replacement request forms preserve that signal. The controller reports publication failure even before execution. Inert checks cover session outcomes, both replacement forms and controller classifications. Compilation and baseline-relative lint pass. No human tests, live SDK session or campaign operation ran. No retry, new tool, scientific gate or state transition is added. PI sources and campaign files remain unchanged. |
| 2026-10-12 | Combined tooling RCA, corrections and rejected loop | Recorded in `copilot_tools_combined_rca_20261012.md`. Corrected six alleged argument failures to four schema failures plus two closed-context denials, and 81 discovery calls to 91 attempts/81 successes. Role cost does not prove workload displacement. M31-M40 share one malformed input; fifteen queries hit the whole-artifact ceiling. The maintainer permanently rejects Runner-controlled coding/debugging coordination. OI-029/OI-030 start the approved interface batch; OI-031/OI-032 remain separate batches. PI review, scientific authority, retry limits and campaign state remain unchanged. No campaign launched, resumed, reset or mutated. |
| 2026-10-12 | Approved OI-029/OI-030 interface batch | Implemented/unmeasured. SDK and Runner share exclusive wrapper structure with actionable errors; operation bodies remain under existing stateful validation. Handle-only PI corrections retain and revalidate scope; explicit scope changes, foreign/stale handles and non-idle children reject. Stop guidance and AGENTS record the authority boundary. Actual SDK handlers pass 112 inert assertions with fake channels/tasks, compilation passes, and touched-file lint adds no findings over HEAD. No human tests, live SDK session, model inference, native author edits or campaign operation ran. Campaign and PI sources remain unchanged. OI-031/OI-032 are not implemented by this batch. No Runner-controlled loop, retry increase, new agent, dependency change or scientific gate is added. |

| 2026-10-12 | Approved OI-031/OI-032 completion | Implemented/unmeasured. Compact operation/checkpoint lookup and frozen named artifact references address history-search and filename-transcription failures. File-backed selection removes the whole-artifact ceiling while retaining integrity, syntax validation and query budgets. Controlled validation passes 482 assertions, including exact shallow/deep values on recorded 38.7, 46.3 and 77.8 MB artifacts. No campaign operation, PI-source repair, dependency, new agent or Runner-controlled engineering loop. All approved implementation batches are complete; cost and campaign effects remain unmeasured. |
| 2026-10-13 | Approved OI-033 bounded model-call retry | The maintainer requested five retries with a five-second wait for the reported Copilot exception. The adapter uses the installed SDK errorOccurred hook, not a new session or repeated prompt. Only the matching recoverable parent model-call error requests a retry; unrelated errors, closed contexts and stop requests retain their existing stop behavior. Retry notices expose each attempt. Forty-nine offline assertions pass through installed SDK hook dispatch, including counter reset, exhaustion, native child/synthetic-message isolation and closure guards. One measured wait is 5.000 seconds. Compilation and baseline-relative lint pass. The rejected request's origin remains unresolved. Native/backend behavior is not certified by offline handler checks. No live SDK/model call or campaign operation ran. |
| 2026-10-13 | Approved initial coding instruction and tool-description rewrite | Implemented / campaign effect unmeasured. The maintainer approved two shorter texts after the read-only review of initial coding deliveries in `5ff87d6b`. The coder instruction now defines a Python scientific-software engineer, relevant-source inspection, actual inputs/outputs, reuse, preserved behavior, small checks and explicit unchecked scope. Its required JSON handoff remains in a short formatting footer. The PI-facing tool description asks for the change, actual inputs/outputs, constraints and selected context instead of repeating repair and lifecycle rules. Only these two strings change in `runner/copilot_adapter.py`. Native SDK dispatch, tools, exact file permissions, schemas, hooks, check execution and PI/Runner authority remain unchanged. This is not evidence of fewer first-delivery defects or lower campaign cost. No campaign launched, resumed, reset, trained or evaluated. |
| 2026-10-14 | Approved native independent coding review | Retained / campaign effect unmeasured. A silent target-IK angle-representation defect survived coder checks and PI review in `dc48cc2f`. Blind original-delivery trials found both known code defects with Sonnet 5.5/high (46.234810 AIU), only the checker defect with Haiku 5.5/high (5.494677 AIU), and the angle defect plus two analysis-input validation gaps with GPT-6 Luna/max (5.146284 AIU). Luna missed the checker defect. The maintainer selected Luna/max for a fresh read-only native review after each completed coding delivery. Original intent survives same-child corrections; findings return to the PI without automatic repairs or scientific approval. Exact read scope, operation locking, cancellation, verified model/reasoning and separate reviewer accounting reuse the existing native lifecycle. Targeted offline checks pass 135 assertions. A real registered-SDK review completed two authorized source reads with verified Luna/max, no file changes and 0.087176 AIU. Compilation and baseline-relative lint pass with no new findings. These are implementation checks, not campaign effectiveness. No campaign or human test suite ran during validation. Commit/push remains authorized, but the maintainer withdrew agent campaign-launch permission before any reset or launch. Next action: the maintainer controls the next campaign and can assess review findings, PI corrections and cost. |

| 2026-10-14 | Approved reviewer correction-flow repair | Retained / campaign effect unmeasured. Startup in `d205479e` reached the existing 30-minute deadline during its fifth independent review. Reviewer time was 21m36s. No Runner check ran in that session. Each correction had restarted the original review. The repair retains one native Luna/max reviewer per coding assignment. Corrections supply the incremental diff, correction intent and previous report. Findings now distinguish confirmed defects, verification gaps and unresolved questions. Each finding names its requirement, expected behavior, actual behavior and evidence. The PI decides repairs and requests the small production-path check. Missing assertions do not automatically require repairs. Timeout settings, model settings, file permissions, usage accounting and Runner authority are unchanged. Focused inert-native checks cover retained handles, correction payloads, categories, denied tools, failed profiles, unavailable reviewers and cancellation. The first isolated native replay verified one actual Luna/max reviewer across the recorded delivery and its first correction. Its initial review took 401.467 seconds and its correction review took 172.014 seconds. Recorded review usage was 4.9694645 AIU, separate from campaign usage. The correction returned a verification gap, not a demonstrated production defect. The replay did not flag the known periodic IK representation defect. It establishes the handoff behavior, not complete defect coverage or improved initial-review latency. A repeated live replay was stopped and provides no additional validation. Syntax and baseline-relative lint pass. No campaign operation or human test suite ran. |

| 2026-10-14 | Approved reviewer-directed engineering repair batches | Retained / campaign effect unmeasured. The native coding handoff now sends the reviewer's complete defect batch to the same coder. The same reviewer checks the repair before the PI receives the final package or a blocking reason. Structured decisions distinguish repair requests, ready packages and PI decisions. Every confirmed defect must enter the batch. Verification gaps and questions cannot trigger repairs. The eight-finding instruction is removed. Exact file scope stays fixed. Repeated repair IDs and absent source progress stop automatic dispatch. The final delta includes all repairs. History records batches and child outcomes. Scientific choices remain with the PI. Runner does not coordinate repairs or execute checks without a PI request. Offline checks cover batch routing, retained handles, scope denials, blocked handoffs, incremental review, final deltas, failed profiles, usage and cancellation. Syntax and baseline-relative lint pass with no added findings. No live-model replay, campaign operation or human test suite ran. Timeout, models, dependencies and scientific sources remain unchanged. These checks do not establish defect coverage, lower cost or scientific effectiveness. |

| 2026-10-14 | Approved six-part Copilot adapter refactor | Implemented / campaign effect unmeasured. Six sequential extractions move existing command parsing to `runner/command_policy.py`, console and usage accounting to `runner/copilot_console.py`, path rules to `runner/path_policy.py`, models and inline prompts to `runner/coding_contracts.py`, native coding and authorization handlers to `runner/coding_session.py`, and controller submission to `runner/operation_submission.py`. The adapter remains the CLI and SDK composition root, reduced from 3,731 to 829 lines. All 123 original declarations retain identical ASTs. Offline comparisons preserve global bindings, schemas, prompts, console output, usage rows, agent profiles and operation replay. Existing adapter checks retain exactly the baseline outcomes: 143 pass and the same 29 pre-existing failures. No test files changed. Lint adds no findings. This is code organization, not a redesign of Console state, locks, review flow or cancellation. No provider/BYOK feature, prompt loader, dependency change, live-model replay or campaign operation is included. |

| 2026-10-15 | Approved grouped Copilot runtime and Markdown prompts | Implemented / campaign effect unmeasured. All nine Copilot runtime files now live in `runner/copilot/`, alongside `scientific-coder.md` and `scientific-reviewer.md`. There is no separate prompts subfolder or `__init__.py`; the installed top-level Copilot SDK remains distinct. Imports, launcher paths, repository-root calculations, ownership references and existing test imports follow the move. `coding_contracts.py` reads each UTF-8 prompt once relative to its own location, with exact content and explicit file errors. Runtime logic and prompt wording remain unchanged. No provider feature, new dependency, live-model call or campaign operation is included. |

| 2026-10-15 | Approved custom-tool contract alignment | Implemented / campaign effect unmeasured. Keep custom tools and the retained native coder/reviewer repair loop. Both children receive fixed environment, scenario and operation-contract text with the PI-selected source context. Remove mandatory verification modules, check proposals, compatibility modes and argument conversion from the coding handoff. Submission exposes complete operation bodies and shares structural validation with Runner; unresolved output tokens reject before acceptance while preserved failed requests remain readable. Bounded metadata now exposes exact pending requests, resolved invocations and failures without treating incomplete outputs as evidence. Failure feedback reports accepted arguments and expected output, not a source diagnosis; changed arguments require replacement, not null reacceptance. Runner scientific ownership now matches the documented surface. One Runner availability calculation supplies acceptance, brief, launcher prompt and controller state. Opus 5.5 found a blocking stdout-capture mismatch and an imprecise checkpoint rejection; both are corrected. A stub-based transport check missed the capture mismatch and is superseded by checks through the real process helper. They cover stderr separation, null/malformed responses, native errors, checkpoint transitions and controller state. Twenty-six new behavioral cases pass, including installed-SDK dispatch and inert measurement failures. The targeted subset has 300 passes and 51 failures, all present in HEAD baselines; no new failure identity or lint finding. PowerShell parsing passes. These are implementation checks, not observed campaign reliability. No dependency, scientific source, campaign state or accepted-request change. No campaign launched, resumed, reset, trained or evaluated. |

| 2026-10-15 | Approved output-first handoff and reader repairs | Implemented / campaign effect unmeasured. The existing coding request now asks the PI for a precise expected output. The coder chooses the implementation, and the reviewer checks that output without a new form or review cycle. Existing reader instructions and parameter descriptions identify `glob.paths`, the batch limit, artifact JSON paging and training-log access. Native MuJoCo static methods now pass the existing descriptor ownership rule. Expected API lookup rejections return explicit failed SDK results with library, symbol and reason; authorization and unexpected-error handling remain unchanged. Eighteen offline cases through the installed SDK and API ownership helper pass. Touched Python compiles, and lint retains the same four baseline findings with no new finding. The existing Runner separately finalized the already-completed E15 publication; it did not repeat the operation. Scientific source and evidence fingerprints remain unchanged, with 21 completed operations, no pending operation and no active scientific session. No campaign resumed, training executed, dependency changed or scientific source repaired. Reliability in a subsequent campaign remains unmeasured. |

| 2026-10-16 | Approved focused review and 15-minute PI deadline | Implemented / campaign effect unmeasured. Retain GPT-6 Luna and change reviewer reasoning from max to high. The default whole PI active-time budget is 900 seconds, including coding and review. Runner execution waits remain excluded. Do not separate child time from the PI budget or add a grace period. The reviewer prompt now targets concrete implementation defects instead of formal proof, exhaustive audits or optional hardening. Report schemas, read permissions and the retained repair loop remain unchanged. Offline checks confirm the registered reviewer settings, 900-second default and preserved explicit timeout override. Touched Python compiles and lint passes. The existing partial analyzer and campaign state/evidence fingerprints remain unchanged. No dependency change, live-model request, scientific edit or campaign resume. |

| 2026-10-16 | Approved four-field review and direct correction handoff | Implemented / campaign effect unmeasured. Reviewer JSON now contains only `validation`, `what_is_wrong`, `why` and `where`. A failed report passes unchanged to the same scoped coder, whose correction returns to the same reviewer. Remove finding categories, IDs, nested repair batches and duplicated correction instructions. Automatic correction messages do not resend unchanged contracts. Fresh PI clarification remains available on PI-directed corrections. Existing file permissions, explicit failure handling and the whole-PI 900-second deadline remain in force. A repair with no source change and another failed validation returns control to the PI. Eleven isolated schema and production-loop cases cover validation, same-child routing, permission boundaries, no progress, PI clarification and cancellation preservation. Changed Python compiles and adds no lint finding against the two-finding baseline. These are offline implementation checks, not measured campaign reliability. The maintainer separately authorized reset and a fresh visible-console campaign. |

| 2026-10-16 | Approved max reasoning for scientific-model preparation | Implemented / scientific effect unmeasured. Copilot scientific-model preparation now uses the selected PI model at max reasoning, including continuations. The override occurs within the bounded invocation after controller binding validation. Ordinary PI sessions keep the launcher reasoning setting. Reviewer reasoning remains high and its prompt is unchanged. The 900-second deadline, persistent runtime and OpenCode behavior remain unchanged. Five isolated checks reach the actual SDK session-configuration boundary and confirm preparation, continuation and ordinary-session reasoning, unchanged model and deadline. The changed adapter compiles and targeted lint passes. No live model request is made. The change responds to the importance of the initial physical model after campaign `5c83824d` exposed an incorrect initial-distance bound. A higher effort setting does not establish that the next model will be correct. No scientific source or model document is repaired, and no campaign is reset or launched. |

| 2026-10-16 | Approved balanced scientific-code reviewer prompt | Implemented / campaign effect unmeasured. Apply the maintainer's prompt with one approved addition: "For corrections, review only the reported problems and errors introduced by the repair." Coding defects remain the priority. Scientific checks concern equations, units, physical assumptions, simulation timing, measurement definitions and intended task semantics in changed code. Untested hypotheses are not defects, and unclear requirements or scientific choices remain with the PI. Remove the redundant verdict instructions and previous ending rather than adding another review process. Four-field JSON, reviewer model/high reasoning, scoped read-only tools, retained-child repair routing and the whole-PI deadline remain unchanged. This is a prompt and directly related documentation change, not evidence of improved review quality. No PI-authored code, scientific-model document or campaign evidence is changed. No campaign is reset, resumed or launched. |

| 2026-10-16 | Approved max reasoning with bounded reviewer scope | Implemented / effect unmeasured. The maintainer stopped campaign `366d41cb` and requested max reasoning now that the review scope is fixed. Change only the reviewer reasoning setting from high to max. Retain GPT-6 Luna, the approved prompt, four-field JSON, scoped read-only tools and the same-coder/same-reviewer correction loop. Coder and ordinary PI reasoning remain inherited from the launcher. Scientific-model preparation remains max. The whole-PI 900-second deadline is unchanged. Review duration, cost and defect coverage at the restored setting remain to be measured. No PI source or campaign state is changed. No campaign is reset, resumed or launched. |

| 2026-10-16 | Approved high reasoning and diagnostic-condition prompts | Implemented / new prompt effect unmeasured. Restore reviewer reasoning from max to high, superseding the max trial above. Campaign `20affb08` reached its 900-second deadline during a third review; the two completed reviews took 255.746 and 181.010 seconds and found concrete timing defects. This observation does not isolate reasoning effort from task complexity. Add the approved scenario-independent PI instruction to state the conditions needed for a diagnostic to answer its question and limit conclusions when those conditions do not hold. Replace the reviewer's diagnostics bullet with a check that the protocol and reported quantities answer the PI's question, flagging concrete confounds or missing conditions. Retain the reviewer model, four-field report, scoped tools, narrow correction review and 900-second deadline. Coder and ordinary PI reasoning remain launcher-selected; scientific-model preparation remains max. No PI code, scientific-model document or campaign state is changed. No campaign is reset, resumed or launched. |

| 2026-10-16 | Approved process-local JSON validation reuse | Implemented / residual query latency remains open as OI-034. Keep up to 128 successful root spans by source fingerprint and Python validation limits. A lock coalesces concurrent validation. Each request still hashes its source and owns its temporary snapshot. The cache retains no mmap handles or decoded trees, and syntax failures are not cached. Seven targeted cases cover concurrency, cleanup, content replacement, invalid unselected JSON, failed validation, eviction and changed runtime limits. The pre-change single M7 count took 35.515 seconds. Offline replay of all eleven original requests used one full validation and took 394.499 seconds across three waves. The first nine outputs exactly matched the campaign results, including discovery-budget exhaustion. The two previously interrupted batches completed in a 204.709-second wave. The first two waves took 189.790 seconds versus about 398 seconds of recorded campaign waits. These are reader measurements, not a new campaign or evidence of scientific effectiveness. A separate warm-count profile, with profiler overhead, took 37.239 seconds. Structural scans accounted for 36.368 seconds and 9,137,542 string scans. No full validation occurred, while snapshot construction took 0.612 seconds. Further scan optimization needs separate approval. No PI source, campaign state, scientific artifact or dependency changed. |

| 2026-10-16 | Approved bounded JSON container-span reuse | Implemented / reader replay measured, campaign effect unmeasured. After the partial mitigation above, the maintainer separately approved caching container end offsets by content fingerprint and start offset. Keep at most 50,000 entries globally, not per artifact. A lock coalesces concurrent scans. Retain the existing scan algorithm, source verification, runtime-limit validation, query budgets and request-local snapshots. No full JSON tree or mmap handle enters either cache. Nine targeted cases pass, including shared scans, changed content at the same offsets and eviction of both metadata caches. Replay of the same eleven M7 requests takes 46.498 seconds versus 394.499 seconds with validation caching alone. The three waves take 33.264, 7.920 and 5.313 seconds. All nine recorded outputs match exactly, including discovery-budget exhaustion. Both previously interrupted batches complete. One full validation serves the entire replay. The replay scans 65,091 distinct container offsets and retains only 50,000. A subsequent count returns the same result in 6.439 seconds, with three rescans after eviction. Cold validation remains necessary. These measurements establish reader behavior and latency, not scientific effectiveness. No PI source, campaign state, scientific artifact or dependency changed, and no campaign restarted. |

| 2026-10-16 | Approved terminal brief repair (OI-019) | Implemented / terminal rendering verified. The best-evidence block already used the final official assessment, but the current-gap selector always used the earlier PI checkpoint. No post-assessment PI session refreshes that checkpoint. Use the stored assessment summary for the current gap and identify the unchanged checkpoint as pre-assessment history, retaining its original goal gap. No new state field, lifecycle operation, scientific interpretation or PI-source change. Five targeted cases cover passed/failed precedence, unassessed checkpoint selection, preserved checkpoint data and unchanged startup rendering. The completed `4a8bc5c7` brief now reports the official 94.0% failure as its current gap. Campaign state, completed-operation history and the frozen scientific model remain byte-for-byte unchanged. This establishes rendering behavior, not scientific effectiveness. The maintainer separately authorized publication, a fresh reset to `baseline-distinct-episodes-v3`, and a visible-console campaign launch. |

| 2026-10-16 | Approved bounded Git publication retry (OI-035) | Implemented / campaign effect unmeasured. The maintainer selected up to three retries with a 60-second wait before each retry, not an unlimited wait. Retry only explicit remote `Internal Server Error`, `fatal error in commit_refs`, and HTTP 500/502/503/504 failures. Pin the source commit and destination branch once, so later local changes cannot alter the retry. Report each failure and wait, then recovery if a retry succeeds. Authentication, permission, oversized-file, branch-rule, non-fast-forward and unknown failures remain fatal. Interruption propagates immediately. Exhaustion preserves the last Git error through `PublicationError`. Thirty-three scoped Git and training-publication recovery cases pass, including eighteen new retry cases with simulated failures and waits. Three additional legacy inquiry-recovery cases fail before publication because their fixtures omit the required prior checkpoint; the same failures reproduce with the untouched HEAD implementation loaded in memory. Those unrelated fixtures are not changed. Touched-file lint passes, and formatting retains only two pre-existing differences. Only the shared Git push is repeated; local commits and scientific execution are not. The existing active campaign is not restarted, reset or repaired by this change. This is an availability mitigation, not a diagnosis or repair of GitHub's server internals. |

| 2026-10-16 | Approved saved-controller contract clarification (OI-036) | Implemented / campaign effect unmeasured. M5 and M6 in `a5d7f35a` used the same T3 artifact, but only research evaluation applied its environment-side guidance. Source inspection confirms that protected evaluation executes the saved observation/action callbacks, not the research environment. Document that boundary inside the existing operation-envelope excerpt, which the current handoff supplies to both coder and reviewer. Link the task-reference description to that contract. Add a focused check to the existing reviewer prompt for required controller behavior, action mapping and episode state. No runtime logic, new tool, behavioral check, agent, review cycle or scientific gate is added. No PI code, saved candidate or campaign state is changed. The maintainer confirmed that the campaign was stopped before these edits. No campaign is launched, resumed, reset, trained or evaluated. Improved review coverage and scientific effectiveness remain unmeasured. |

| 2026-10-17 | Approved OpenCode inference within Copilot SDK | Implemented / remote acceptance pending / scientific effect unmeasured. Launch-time provider/model selection supports GitHub Copilot, Zen and Go with Luna as default. The working pi-harness reference supplies catalogue and exact identity-header behavior. No Pi read/glob implementation is ported. Installed-SDK loopback checks cover Chat Completions, Responses and Anthropic routing, mandatory read, native child reads/edits, main/reviewer write denials, selected model identity and resume. They exposed omitted child read definitions, omitted freeform patches on Chat Completions and Anthropic double-v1 URL joining. The approved adaptation retains exact role/file hooks while using inherited definitions, scoped UTF-8 read and native JSON editors. Reviewer uses the selected campaign route, retaining independent read-only review and the existing correction lifecycle. External usage retains tokens/catalogue prices without invented AIU or billing totals. Remote acceptance awaits a local OpenCode credential. No dependency, scientific source or campaign state changed. No campaign launched, resumed, reset, trained or evaluated. System-message/context-tool work and legacy-runtime retirement remain outside this implementation. |

| 2026-10-18 | Approved restoration of the 30-minute PI deadline | Implemented / campaign effect unmeasured. Campaign `fb0baa2a` stopped in S5 at 11:03:48 local after exhausting the 900-second active-session budget during evidence analysis. Restore the default to 1,800 seconds. Coding and review still consume the same budget; Runner execution waits remain excluded. Explicit timeout overrides, timeout failure handling, model settings and reasoning remain unchanged. Next action: None. No campaign is launched, resumed, reset or mutated by this change. |

| 2026-10-18 | Approved session-sized deliverables within an inquiry | Implemented / campaign effect unmeasured. The resumed S5 in `fb0baa2a` exhausted its fresh 30-minute active budget while developing, repairing and interpreting trajectory analysis. Its objective largely repeated the broader inquiry, and the prompt tied checkpointing to a stable decision. Separate the inquiry from its session deliverable. New inquiry-session objectives and inquiry prompts explicitly permit checkpointing completed or useful intermediate work with supported findings, limitations and remaining work, without resolving all mechanisms or closing the inquiry. Apply the prompt guidance to resumed sessions without rewriting their stored objectives. Existing checkpoint fields, inquiry transitions, operation permissions, timeout accounting and PI scientific authority remain unchanged. No campaign state or PI-owned source is changed. No campaign is launched or resumed. |

## Evidence index

| Evidence | Role |
|---|---|
| `campaigns/results.jsonl` | Authoritative completed-operation history. |
| `campaigns/brief.md` | Generated current campaign context; identifies the preserved PI checkpoint as historical after official assessment. |
| `campaigns/EXPERIMENTS.md` | Generated campaign-readable history. |
| `reports/session_usage/*.jsonl` | AIU, token and tool-call accounting. |
| `docs/campaign_79395c88_comprehensive_rca_20261009.md` | Full independent RCA and proposed validation. |
| `docs/oi016_post_campaign_rca_20261009.md` | Earlier OI-016-specific analysis; superseded where the comprehensive RCA differs. |
| `docs/oi005_assessment_decision_rca_20261011.md` | Reconciled parent and Opus 5.5/high RCAs, evidence, disagreements, bounded repair and campaign-observation criteria. |
| `docs/copilot_tools_combined_rca_20261012.md` | Reconciled tooling RCA, corrected statistics, OI-029/OI-030 implementation scope, later evidence-access batches and the rejected Runner-controlled loop. |
| `docs/research-overview/robot-campaign-ec7f3d3a-20261010-error-correction-report.html` | Detailed report for the historical `ec7f3d3a` campaign. |
| `docs/research-overview/robot-campaign-0d39d52c-20261011-tooling-review.html` | Stopped tooling campaign evidence, final cost, correction topics and separately labeled subsequent harness repairs. |
| `docs/research-overview/robot-campaign-1c940d68-20261020.html` | Failed `1c940d68` campaign (189/200), its likely geometric cause and proposed harness changes. |
| `docs/research-overview/robot-campaign-2d4fcc0e-20261021.html` | Passed `2d4fcc0e` campaign (200/200), its hybrid controller and the effect of the 20-21 October guidance changes. |
| `docs/research-overview/robot-campaign-5d94bf8a-20261023.html` | Failed `5d94bf8a` campaign (193/200), the only clean OI-041 system-prompt run: what `3afe89f2` changed, the one-sided plateau and the RL-centric, defensive PI. |
| `docs/research-overview/robot-campaign-faff0d94-20261023.html` | Passed `faff0d94` campaign (200/200) with a gated hybrid controller on `ba92677f`; information only because `0b64ea66` and `ec21e7bf` added behavioural directives. |
| `docs/research-overview/robot-campaign-f83fca4d-20261024.html` | Passed `f83fca4d` campaign (200/200) on `a969f07b`, the first goal-focused OI-041 system-prompt run: episode-latched analytic IK and computed-torque controller with a learned posture choice, prompt assessment decision, and the maintainer concern about the analytic shortcut. |
| `docs/harness-change-narrative.md` | Curated explanation of harness failures, attempted repairs, reversals and current conclusions. |
| `archive/harness-experiment-log-legacy.md` | Full prior narrative log, retained for historical lookup only. |

## Maintenance template

Every future entry must answer these questions in this order:

1. **Issue/change ID:** existing OI or a newly approved ID.
2. **Observed defect or decision:** one precise statement.
3. **Evidence:** campaign, artifact, source path or implementation check.
4. **Change:** what was altered, or explicitly that no change was made.
5. **Disposition:** one status from the vocabulary above.
6. **Next action:** one owner and one bounded action, or `None`.
7. **Campaign boundary:** explicitly state that no campaign was launched,
   resumed, reset or mutated unless the maintainer independently records
   otherwise.

Do not append full RCA prose, copied prompts, complete campaign timelines or
duplicate generated reports here. Put detailed analysis in a dedicated RCA or
campaign report and link it from this tracker.
