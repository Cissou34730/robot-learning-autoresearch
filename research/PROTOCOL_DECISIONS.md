# Research design decision log

This file records the structural choices made with the human about the
simulation, learning setup, reward, researcher freedom, and experiment
selection protocol. It records both active decisions and the choices they
superseded. It does not instruct the autonomous researcher and does not replace
`research/program.md`, `research/scenario.md` or `research/current_params.json`.

## 2026-08-28 — Fixed final benchmark, flexible training target

- **Status:** Clarified later on 2026-08-28: the human objective is invariant,
  but its implementation files are not protected from research changes.

- **Decision:** The reported task remains 1 cm for 2 seconds, currently 100
  consecutive control steps, over 200 fixed evaluation episodes.
- **Reason:** Every candidate needs one stable definition of success.
- **Boundary:** Training may use a curriculum or another intermediate target,
  but it cannot alter the final evaluator or reported benchmark.

## 2026-08-28 — Correct target geometry and invalidate prior research

- **Decision:** Sample the target in the physical plane of the arm by using the
  end-effector plane for its world-space height. Keep measuring the true 3-D
  Euclidean distance after MuJoCo updates the world positions.
- **Reason:** The previous target height did not match the arm plane and created
  an artificial distance floor around 2 cm. Optimizer, reward, and curriculum
  experiments performed with that geometry could not answer the intended task.
- **Consequence:** Reset the active research state, champion, and experiment
  history. Start again with a fresh PPO baseline. Old commits remain recoverable
  in Git but are not evidence for the corrected task.
- **Preserved:** The robot, MuJoCo physics, target radius distribution, 500-step
  episode limit, and corrected evaluation measurements remain unchanged.

## 2026-08-28 — Exact definition of episode success

- **Decision:** One episode succeeds if the end effector remains continuously
  within 1 cm for 100 consecutive control steps. The streak may begin anywhere
  within the episode; it does not have to begin at reset.
- **Decision:** A model reaches the reported goal at 98% success over 200
  evaluation episodes.
- **Reason:** This directly represents the desired behavior. The number 100 is
  derived from 2 seconds and the control timestep, rather than being an
  independent duration setting.

## 2026-08-28 — Diagnostic ranking for incomplete episodes

- **Decision:** Compare task progress lexicographically using: success rate;
  then, only across failures, mean longest consecutive in-circle streak; mean
  number of in-circle steps in the best 100-step window; and finally cumulative
  distance outside the 1 cm circle in that window.
- **Reason:** At low success rates, distance-to-target alone cannot distinguish
  a policy that briefly enters the circle from one that nearly completes the
  hold. Once a model succeeds, success remains the dominant criterion.
- **Supersedes:** Selecting checkpoints mainly from closest median distance and
  using median hold duration as a promotion criterion.

## 2026-08-28 — One identifiable hypothesis per experiment

- **Decision:** One research session prepares one proposal testing one
  identifiable hypothesis; one hypothesis may require several coherent edits.
- **Reason:** Results remain attributable and reversible without restricting a
  researcher to a parameter-only change.
- **Execution:** The researcher prepares the change and exits. The runner owns
  training, evaluation, rollback, persistence, and the next session.

## 2026-08-28 — Runner-owned training budget

- **Decision:** A transfer experiment receives 120,000 training steps. A fresh
  challenger competing with an accumulated champion receives matching lineage
  compute; the initial baseline receives 120,000 steps.
- **Reason:** The researcher may choose the method, but cannot make a result win
  merely by silently giving it more compute.

## 2026-08-28 — Fresh corrected baseline starts with PPO

- **Decision:** Start the corrected research scenario from a fresh PPO policy,
  not from any checkpoint trained with the invalid geometry. The initial policy
  is a two-layer `64 x 64` tanh network.
- **Starting PPO configuration:** `learning_rate=0.0003`, `n_steps=1,024`,
  `batch_size=64`, `gamma=0.99`, `gae_lambda=0.95`, and `ent_coef=0.01`.
- **Reason:** The temporarily inherited `learning_rate=0.00005`,
  `n_steps=4,096`, and `batch_size=128` were transfer-tuned settings, not a
  justified starting point for a model initialized from scratch.
- **SAC status:** SAC parameters remain available to the researcher, but SAC is
  not active. Earlier SAC results were obtained before the geometry reset and
  are not carried into the corrected scenario.

## 2026-08-28 — No predefined curriculum

- **Decision:** Begin with the final 1 cm / 100-step training objective and no
  hard-coded curriculum.
- **Reason:** We want the autonomous researcher to decide from evidence whether
  a curriculum is required and, if so, design its stages rather than inherit an
  arbitrary ladder.
- **Interface:** The hold reward is expressed relative to
  `hold_steps_required`, so a researcher-created training stage can consistently
  change both its target and its reward progress while final evaluation remains
  fixed at 1 cm / 100 steps.

## 2026-08-28 — Current progressive hold reward

- **Status:** Relocated on 2026-08-29. The reward is now code in
  `robot_learning/scenario/reward.py`; its coefficients left
  `research/current_params.json` with unchanged numerical values.

- **Decision:** Keep the original approach and centering terms as differences
  of potentials, plus an action-energy cost:
  `10*(previous_distance-current_distance)`, the change in
  `4*exp(-distance/0.05)`, and `-0.05*sum(action^2)`.
- **Decision:** Inside the active training radius, accumulate nonlinear hold
  capital `50*(held_steps/required_steps)^2`. Later hold steps are therefore
  more valuable than early ones. Completing the required hold pays an additional
  one-time bonus of 50.
- **Decision:** Leaving after beginning a hold forfeits 50% of the accumulated
  hold capital. After that exit, every continued outside step is penalized until
  re-entry. The outside penalty grows linearly across a 1 cm band and is capped
  at 0.5 per step.
- **Reason:** Reward entry, then increasingly value sustained residence, while
  making a late exit costly without making all incomplete attempts net to zero.
- **Supersedes:** A constant per-step dwell reward, then the first version of the
  progressive reward that forfeited 100% of accumulated capital on exit.

## 2026-08-28 — Development checkpoint cadence

- **Status:** Superseded later on 2026-08-28 by neutral checkpoint production
  and researcher-designed evaluation.

- **Decision:** Request a checkpoint evaluation every 20,000 training steps,
  executed only after a completed optimizer update/rollout.
- **Reason:** A checkpoint must represent a completed PPO update. If `n_steps`
  changes, the actual checkpoint is the first completed boundary after the
  nominal threshold (for example 20,480 with `n_steps=1,024`).

- **Current replacement:** Training now saves neutral candidates at the first
  completed learning-update boundary after each researcher-configurable
  checkpoint interval. It performs no evaluation or ranking. The researcher
  decides later which saved candidates warrant measurement.

## 2026-08-28 — Use 200 development episodes

- **Status:** Superseded later on 2026-08-28. The researcher chooses development
  evaluation volume; 200 episodes remains part of the human's reported result.

- **Decision:** Evaluate every development checkpoint on the same 200 episodes.
- **Reason:** With 50 episodes, one success changes the score by 2 percentage
  points and did not filter the noise we observed. With 200 episodes, one
  success represents 0.5 point and episode-by-episode paired comparisons have
  more discriminatory evidence.
- **Supersedes:** The earlier choice of 50 development episodes.

## 2026-08-28 — Retain three checkpoint finalists

- **Status:** Superseded later on 2026-08-28 by retaining the neutral checkpoint
  inventory and letting the researcher decide what to measure and retain.

- **Decision:** Keep three checkpoints from a completed training run, including
  their normalization and optimizer state.
- **Reason:** PPO can peak and regress during one run; retaining only the final
  checkpoint or one noisy apparent maximum discards useful candidates.
- **Selection:** Prefer checkpoints meaningfully better than the accepted
  champion. Among statistically equivalent checkpoints, preserve early,
  middle, and late training-time representatives. For the first baseline, where
  no champion exists, use the descriptive task ranking to choose the three.
- **Clarification:** A `[selection] ... unreferenced checkpoint pool` message
  during the first baseline means only that the checkpoint was measured and
  saved in the temporary pool. It is not yet declared the winner.

## 2026-08-28 — Final paired tournament

- **Status:** Superseded later on 2026-08-28. There is no automatic tournament.

- **Decision:** After training, compare the three finalists and the accepted
  champion on identical episodes: 200 episodes on each of three seeds, extended
  with additional seeds only for close or positive-but-uncertain results.
- **Reason:** Paired episodes distinguish a genuine behavioral improvement from
  different random target samples.
- **Isolation:** Development seeds, tournament seeds, and the fixed reported
  benchmark seed are disjoint.

## 2026-08-28 — Conservative champion promotion

- **Status:** Superseded later on 2026-08-28 by researcher-owned lineage
  selection.

- **Decision:** Promote a challenger only with positive paired net wins, an
  exact paired-test probability at or below 0.05, and an improvement exceeding
  the measured training-seed noise floor. Ties or insufficient evidence retain
  the champion.
- **Reason:** `kept/reverted` must be based on repeatable evidence rather than a
  tiny change in an aggregate score.
- **Reporting:** The untouched benchmark is run only after selection and never
  participates in choosing the winner.

## 2026-08-28 — Defer A/A calibration until the 98% regime

- **Status:** Superseded later on 2026-08-28. Calibration is now a researcher
  choice rather than a runner gate.

- **Decision:** Training-seed A/A calibration becomes mandatory only after the
  accepted champion reaches 98% success. Below 98%, structural experiments,
  including a researcher-designed curriculum, remain allowed.
- **Reason:** Repeating a weak recipe three times measures its weakness at high
  cost and blocks more useful structural research. Near the goal, the noise
  floor becomes necessary to distinguish small improvements.
- **Supersedes:** The earlier rule requiring calibration before every ordinary
  experiment whenever no noise floor existed.

## 2026-08-28 — Researcher controls the learning method

- **Status:** Expanded later on 2026-08-28 to include evaluation, runner code,
  candidate decisions, and both model and code lineages. Given an explicit code
  location on 2026-08-29: the researcher-owned science is `robot_learning/scenario/`.

- **Decision:** The researcher may change coherent training code and tunable
  parameters, including reward, observations, PPO/SAC choice, neural-network
  size, curriculum, and checkpoint-comparison logic. Architecture changes must
  use fresh initialization when checkpoint formats are incompatible.
- **Boundary:** The final benchmark, robot, corrected physics/environment
  mechanics, and evaluator remain protected. Compute allocation remains owned
  by the runner.
- **Reason:** The autonomous component should act like a researcher, not merely
  tune a small parameter whitelist, while it must not move the goalposts.

## 2026-08-28 — Safe interruption and safety limits

- **Decision:** `Ctrl-C` asks training to stop cleanly and saves the current
  model, optimizer state, observation normalization and SAC replay buffer when
  applicable. The proposal is preserved. The next launch resumes only the
  remaining training steps, or resumes evaluation directly when training had
  already completed. A second interruption updates the same recovery state.
- **Fallback:** If interruption occurs before any recoverable training artifact
  exists, the same preserved proposal restarts from the beginning; the runner
  does not ask the researcher for a different experiment.
- **Decision:** Training has a 12-hour hard safety limit and a separate
  30-minute no-progress limit. Evaluation now reports completed episodes, has
  the same 12-hour hard limit, and stops after 30 minutes without completing a
  new episode.
- **Reason:** These are failure guards, not research compute budgets. They stop
  hung processes without rejecting a slow evaluation that is still advancing.
  The former estimate of 10 seconds per episode incorrectly rejected a live
  200-episode evaluation after 33 minutes 20 seconds.

## 2026-08-28 — Keep Luna as the default researcher model

- **Status:** Clarified on 2026-08-29. The researcher *instructions* are now
  model-agnostic; only the loop's default `$model` value names a provider, and it
  remains overridable through `RESEARCH_MODEL`.

- **Decision:** Keep `github-copilot/gpt-5.6-luna` with medium reasoning as the
  default research model, while preserving environment-variable overrides.
- **Reason:** The apparent failure to converge was traced to invalid simulation
  geometry, not evidence that Luna was incapable. The proposed switch to Terra
  was therefore not retained.

## 2026-08-28 — Compact but diagnostic research memory

- **Decision:** Keep structured experiment cards, concise postmortems, a compact
  research brief, compressed training dynamics, and episode-level failure
  diagnostics.
- **Reason:** The researcher needs exact prior changes and failure geometry
  without loading large raw logs into the LLM context or repeating exhausted
  hypotheses.

## 2026-08-28 — Version accepted artifacts and preserve negative evidence

- **Status:** Clarified later on 2026-08-28: the accepted model is chosen by the
  researcher; the runner archives candidates without ranking them.

- **Decision:** Keep the accepted policy artifact and research state under Git;
  candidate training directories remain disposable. Archive the neutral
  checkpoint inventory from every completed experiment and retain concise
  negative results. No checkpoint is called the "best challenger" before the
  researcher has requested and interpreted the relevant measurements.
- **Reason:** Models are small and local, so Git gives a recoverable lineage and
  prevents a later training run from silently erasing a previously accepted
  model or repeating a failed idea.

## 2026-08-28 — Researcher owns candidates and lineage decisions

- **Decision:** The researcher controls checkpoint timing, metrics, ranking,
  number of finalists, candidate submission, and which candidate or prior
  champion becomes the lineage for subsequent work.
- **Runner role:** Execute the human/researcher-defined training and evaluation
  plan, save artifacts and raw measurements, and persist explicit decisions. It
  does not allocate the budget, select candidates, promote, retain, or roll back
  scientific work automatically.
- **Workflow:** Training ends with an unevaluated checkpoint inventory. The
  researcher first requests useful measurements, then interprets them and records
  `continue_from` plus separate model- and code-lineage rationales before defining
  the next experiment.
- **Reason:** Candidate selection and temporary regressions are part of the
  research method. A fixed automatic promotion rule can discard a lineage that
  is scientifically useful for curriculum or longer-term learning.
- **Supersedes:** Runner-owned `promoted/champion retained`, automatic rollback,
  mandatory A/A gating, the three-finalist limit, and the four progress metrics
  as fixed runner policy.

## 2026-08-28 — Project map is descriptive, not a code whitelist

- **Status:** Clarified later on 2026-08-28: implementation files are not
  protected. Only the human-defined objective and budget are authoritative.
  **Revised on 2026-08-29:** the benchmark, the official robot and the
  enforcement mechanism are protected from research proposals.

- **Decision:** Explain the role of important files without instructing the
  researcher that learning changes must fit a narrow per-file whitelist.
- **Invariant:** The human-defined objective and budget remain fixed unless the
  human changes them. The researcher may edit their implementation—including
  robot, environment, benchmark, evaluator, tests, or runner—to correct or
  improve the experiment without silently changing that objective.
- **Reason:** Scientific freedom must exist in executable code, not only in the
  wording of `program.md`.

## 2026-08-28 — Researcher owns evaluation and both lineages

- **Status:** Partially revised on 2026-08-29. The researcher still owns
  evaluation design and both lineages, but may no longer change the benchmark,
  the official robot, or `research/run_experiment.py`.

- **Decision:** Training produces a neutral inventory of periodic checkpoints.
  It performs no development ranking and does not retain an automatic top three.
- **Decision:** After training, the researcher chooses which candidates or
  champion to evaluate, with which episode counts, seeds, comparisons, and
  diagnostics. The runner executes that request exactly. The fixed paired
  tournament is removed.
- **Decision:** After measurement, the researcher chooses both the model lineage
  and the code/configuration lineage (`keep` or `revert`). The runner
  persists that explicit decision and performs no automatic promotion or rollback.
- **Decision:** No path whitelist gives the runner scientific authority. The
  researcher may change training, benchmark, evaluator, comparison, and runner
  implementation when evidence requires it. The human-defined objective and
  compute budget remain invariant unless the human explicitly changes them.
- **Reason:** The runner is an execution mechanism, not a second researcher.
  Selection and measurement design are part of the scientific method and must
  remain with the researcher.
- **Interruption:** Training and requested evaluation plans remain resumable after
  `Ctrl-C`; completed requested measurements are reused rather than repeated.

## 2026-08-29 — Implemented researcher-directed experiment cycle

- **Checkpoint production:** `robot_learning.train` saves a neutral candidate at
  the first completed learning-update boundary after each configured checkpoint
  interval, plus the final state when needed. It performs no evaluation, ranking,
  top-three retention, or deletion based on model quality.
- **Evaluation request:** After training, the compact brief exposes all saved
  candidate names and the current champion when one exists. The researcher writes
  `research/evaluation_request.json` with the candidates, episode counts, seeds,
  and labels it wants measured. The runner executes only that plan.
- **No tournament:** The automatic paired tournament and its automatic candidate
  decision have been removed. Paired statistical helpers remain available only
  as optional tools for a researcher-designed comparison.
- **Two explicit lineages:** The following proposal must choose a model parent and
  record whether the experiment's code/configuration is kept or reverted. A
  revision is a separate next experiment. The brief includes the exact pre-experiment Git commit so the code
  decision can be implemented without guessing.
- **Interruption:** Each completed requested evaluation is persisted immediately.
  After `Ctrl-C`, the same plan resumes and skips measurements already completed.
- **Validation:** The active tests verify the absence of a path whitelist, neutral
  candidate inventories, update-boundary checkpointing, researcher-owned lineage,
  and non-duplicating evaluation resume behavior.

## 2026-08-29 — Explicit research reset command

- **Decision:** `reset_research.ps1 -Force` starts a clean experimental scenario
  without reverting the current implementation. It removes only active research
  state, accepted/challenger checkpoints, disposable autoresearch candidates,
  pending recovery/evaluation controls, and experiment history; it then creates a
  fresh baseline marker.
- **Preserved:** The robot, benchmark implementation, learning code, current
  parameters, and this decision log remain unchanged.
- **Safety:** The command refuses a dirty Git working tree and commits the blank
  research state, so the next baseline starts from a clean, reproducible commit.
- **Reason:** A clean reset is a normal research operation in this project and
  should not require manually reconstructing a fragile collection of markers,
  state files, models, and history.

## 2026-08-29 — Publish every automatic commit

- **Decision:** Every commit created by the reset script, research loop, or
  experiment runner is immediately pushed to `origin` on the current branch.
- **Failure behavior:** If the commit succeeds but the push fails, execution
  stops and reports that the local commit has not been published.
- **Reset correction:** Every file removed by `reset_research.ps1`, including
  transient proposal and evaluation controls, is included in the reset commit;
  reset-state JSON is written in deterministic order so repeated resets are
  idempotent.
- **Reason:** The remote repository is now part of the persistence contract; a
  successful local commit alone is no longer considered a completed operation.

## 2026-08-29 — Separate the current scenario from the AutoResearch core

- **Decision:** All science specific to the current problem lives in
  `robot_learning/scenario/`: `environment.py`, `observations.py`, `reward.py`,
  `evaluation.py`, `brief.py`, `viewer.py`, and a thin `final_benchmark.py`
  adapter over the protected benchmark. Generic code imports only the functions
  re-exported by `robot_learning/scenario/__init__.py` and never reaches into a
  scenario submodule.
- **Boundary:** `robot_learning/train.py`, `robot_learning/evaluate.py`,
  `robot_learning/play.py`, the generic training helpers/callbacks,
  `robot_learning/training/research_config.py`, `research/run_experiment.py` and
  `research/build_research_brief.py` contain no import of the reach environment,
  reward, observations, robot assets or benchmark modules, and no import of
  MuJoCo. An architecture test parses each of these modules and fails if such a
  dependency reappears.
- **Explicitly not done:** no scenario selection, loader, registry, plugin
  system, dependency injection, generic robot/physics abstraction, reward DSL, or
  universal metric schema. This repository remains one repository, one scenario.
- **Reason:** Replacing the robot or the task should require replacing the
  scenario package, the protected benchmark, the physics assets and
  `research/scenario.md` — not redesigning the experiment runner, training
  lifecycle, checkpointing, lineage, recovery or final-benchmark lifecycle.
- **Compatibility:** `robot_learning/environments/reach_env.py`,
  `robot_learning/rewards/reach_reward.py` and
  `robot_learning/training/observations.py` remain as thin re-exports of the
  single authoritative implementation.
- **Equivalence:** The migration is structural only. Bit-exact regression
  goldens captured before the move cover the seeded reset target, observations,
  five environment transitions, every reward case, the research evaluation
  result and the pooled evaluation summary.

## 2026-08-29 — The reward is research code, not runtime configuration

- **Decision:** `research/current_params.json` holds generic runtime knobs only:
  `algorithm`, `ppo`, `sac`, `policy`, `training`. The `reward` section was
  removed and its ten coefficients moved, unchanged, into
  `robot_learning/scenario/reward.py`.
- **Decision:** The reward returns a scalar `total` plus a free-form
  `components` mapping. No generic module validates reward component names,
  their number, or the mathematical form of the reward.
- **Consequence:** A reward change is now a code change recorded by the existing
  Git code lineage, not a `params` override. Proposals no longer accept
  `params.reward.*`.
- **Reason:** The researcher must be able to replace the entire reward function,
  not only tune a predefined coefficient list. Configuration validation was
  silently freezing the reward structure.
- **Supersedes:** `current_params.json` as the single source of truth for all
  scientific parameters, and the `apply_reward_overrides` whitelist.

## 2026-08-29 — Split the protocol from the current problem

- **Decision:** `research/program.md` contains reusable autonomous-research
  methodology only. `research/scenario.md` contains the current problem: the
  objective, protected robot mechanics, researcher-mutable scenario files,
  terminology, and scenario-specific diagnosis.
- **Decision:** Every researcher phase that reads `research/program.md` also
  reads `research/scenario.md`. A test enforces this on `run_research.ps1`.
- **Decision:** `program.md` uses scenario-independent wording (task feasibility,
  success region, task acquisition and stability). No task number — distance,
  tolerance, hold duration, episode count or success percentage — appears in it.
- **Reason:** `program.md` should stay usable almost unchanged if this
  repository is copied for another RL problem.

## 2026-08-29 — Success semantics and evaluation summary belong to the scenario

- **Decision:** The generic core does not define the task success percentage.
  The threshold is read inside `robot_learning/scenario/evaluation.py` from the
  human-owned `robot_learning/benchmark/final_contract.py`.
- **Decision:** Pooling several evaluations into a summary is a scenario
  operation (`summarize_research_evaluations`). `research/run_experiment.py`
  no longer interprets `failed_episode_progress`, hold progress, best-window
  fields, distance traces or target geometry; the same applies to
  `research/build_research_brief.py`.
- **Decision:** The final benchmark returns an explicit `goal_reached` boolean.
  The runner acts on that boolean and never on a percentage.
- **Compatibility:** The persisted field name `seeds_passing_98_percent` and the
  historical `reward.*` family labels are preserved. They are non-executable
  strings and do not affect current scientific behavior.
- **Reason:** A future scenario may have no concept of reaching, tolerance entry
  or hold duration. If the runner depends on those fields, replacing the
  scenario still means modifying the AutoResearch engine.

## 2026-08-29 — Rendering is a scenario concern

- **Decision:** The live training viewer and the trained-policy playback loop
  live in `robot_learning/scenario/viewer.py` and are reached through
  `make_training_viewer_callback` and `watch_scenario_policy`.
  `robot_learning/training/viewer_callback.py` was removed and
  `robot_learning/play.py` is now a thin CLI.
- **Decision:** The windowing stack is imported lazily, so headless runs of the
  runner, the brief builder and training never load it.
- **Reason:** Rendering is physics-engine specific. Keeping it in the generic
  training helpers would force a non-MuJoCo scenario to rewrite core modules.

## 2026-08-29 — Protection belongs to the benchmark, not the training environment

- **Decision:** Remove `assert_immutable_invariants()`. The training environment
  is no longer required to match the official target distribution, success
  threshold, hold duration, control timing or episode horizon.
- **Decision:** The official task is enforced only where success is measured:
  the protected `final_contract.py` / `final_benchmark.py`, the frozen robot
  asset hash, and the benchmark tests, which now assert the contract against
  `official_environment()` rather than the training environment.
- **Reason:** Training and benchmark have different owners. Forcing the training
  environment to reproduce the official configuration would make curriculum,
  staged difficulty and altered randomization impossible, re-freezing part of
  the researcher-owned scenario. The researcher may train on an easier, harder
  or differently randomized environment and is still judged against the
  unchanged official benchmark.
- **Supersedes:** The training-environment invariant assertions previously held
  in `robot_learning/training/research_config.py`, then briefly in
  `robot_learning/scenario/environment.py`.

## 2026-08-29 — The whole GOAL_REACHED path is human-owned

- **Problem:** After the scenario separation, the completion path ran through
  `robot_learning/scenario/final_benchmark.py`, which converts the protected
  result into `goal_reached`. That file was ordinary research code, so a
  proposal could have returned `goal_reached = True` without passing the
  human-owned benchmark.
- **Decision:** The protected surface now covers every file that can declare the
  objective reached or redefine the robot it is measured on:
  `benchmark/final_contract.py`, `benchmark/final_benchmark.py`,
  `scenario/final_benchmark.py`, `scenario/__init__.py`,
  `robots/two_joint_arm.py` and `robots/two_joint_arm.xml`.
  `scenario/__init__.py` is included because it is the module from which the
  runner imports `evaluate_final_model`.
- **Mechanism:** The existing research-surface validation is unchanged; only its
  explicit path set grew. No registry, manifest, permission system or ownership
  framework was introduced.
- **Scope:** These files are human-owned for the duration of one research
  problem, not immutable forever. A human setting up a new scenario may replace
  the benchmark, the robot and the task contract deliberately.
- **Unaffected:** Reward, observations, training environment, evaluation,
  diagnostics, brief evidence and rendering remain freely researcher-owned.
- **Reason:** Only the protected human-owned benchmark may declare the research
  objective reached. Generic orchestration may transport that boolean; mutable
  research code must not be able to manufacture it.

## 2026-08-29 — The runner enforces the protocol and is not researcher-owned

- **Decision:** `research/run_experiment.py` is protected from research
  proposals, together with the import-routing files that resolve the protected
  benchmark and robot: the `__init__.py` of `robot_learning`,
  `robot_learning/benchmark`, `robot_learning/robots` and
  `robot_learning/scenario`.
- **Ownership model:**
  - the researcher owns scientific choices and their implementation;
  - the runner owns mechanical execution and enforcement of the human-defined
    research protocol;
  - the researcher cannot modify the enforcement mechanism during a run.
- **Reason:** The runner validates protected paths, controls the final-benchmark
  lifecycle, verifies the accepted artifact and writes `GOAL_REACHED`. If the
  researcher can edit it, every other protection is advisory rather than
  enforceable. Protecting it does not give the runner scientific authority: it
  still chooses no hypothesis, no candidate, no lineage and no significance.
- **Scope:** A package `__init__.py` is protected only when it resolves a
  protected module. There is no recursive protection, package scanning,
  permission framework or sandbox.
- **Supersedes:** "The researcher may edit their implementation — including
  robot, environment, benchmark, evaluator, tests, or runner" and "No path
  whitelist gives the runner scientific authority. The researcher may change
  training, benchmark, evaluator, comparison, and runner implementation."
  Reward, observations, training environment, evaluation, diagnostics, brief,
  rendering, `train.py`, `evaluate.py` and the training helpers remain freely
  researcher-owned.
- **Residual:** See the 2026-08-29 trust-model decision below.

## 2026-08-29 — Cooperative-agent trust model for protected paths

- **Assumption:** The research loop assumes a cooperative researcher agent that
  follows the documented protocol.
- **Decision:** `PROTECTED_BENCHMARK_PATHS` is a protocol guardrail against
  accidental or ordinary research modifications of the human-owned surface:
  protocol enforcement, official benchmark, official robot, and the trusted
  import-routing files. The existing research-surface validation enforces this
  during normal protocol-compliant research, and every violation is recorded in
  Git lineage.
- **Out of scope:** Resistance to a deliberately hostile agent with arbitrary
  repository write access. The check runs from the working tree it protects, so
  a rogue agent could edit the checker itself. Closing that gap requires an
  external trust boundary.
- **Decision:** Do not add an external integrity check, sandbox, filesystem
  permissions, signature verification, or any other security mechanism. This
  limitation is accepted and documented rather than mitigated.
- **Documentation:** `research/program.md` states the protected surface and this
  assumption to the researcher; `research/scenario.md` lists the exact paths.
- **Reason:** The threat model is researcher error and protocol drift, not
  adversarial behavior. A security framework would add substantial machinery
  without changing the outcome for the failure mode we actually have.

## 2026-08-29 — PPO is the current implementation, not the research space

- **Decision:** The built-in training implementation is PPO only.
  `robot_learning/train.py` constructs and trains PPO directly; the algorithm
  registry, the `--algorithm` switch, the resume-time algorithm check and the
  SAC replay-buffer save/load/copy paths are removed.
  `robot_learning/training/algorithms.py` keeps only `load_policy`, because the
  protected benchmark imports it.
- **Decision:** `research/current_params.json` means the effective configuration
  of the currently active training method. The dormant `sac` block is removed
  and no dormant configuration for a hypothetical future algorithm replaces it.
- **Decision:** The configuration is no longer pushed into the researcher's
  default context. New-experiment, retry and evaluation-design prompts read
  `program.md`, `scenario.md`, `brief.md` and `last_train_summary.md`; the brief
  states `Current learning method: PPO` instead of embedding the full parameter
  set. The researcher inspects `current_params.json` when a diagnosed mechanism
  makes a setting relevant.
- **Decision:** `program.md` states that the current implementation is a starting
  point, that the researcher may replace the learning method, that the
  implemented algorithms are not the considerable set, that an algorithm change
  requires a diagnosed mechanism, and that exposed configuration is not a menu of
  interventions. The canonical training-proposal example is now a neutral
  structural shape, and `params` is defined as optional overrides to the active
  runtime configuration rather than an `algorithm/ppo/sac/...` enumeration.
- **Decision:** Baseline protocol wording is algorithm-neutral (`Fresh
  baseline`); the baseline still trains PPO because PPO is the current
  implementation.
- **Explicitly not done:** no algorithm catalog, capability registry, plugin
  interface, generic SB3 factory, replay abstraction or cross-method
  configuration schema. Stable-Baselines3 and the installed environment already
  form a discoverable capability surface.
- **Boundary unchanged:** `robot_learning/train.py`, `robot_learning/training/*`,
  `research/current_params.json` and `pyproject.toml` remain researcher-owned. A
  future algorithm replacement is an ordinary scientific mutation, not a human
  framework-extension step.
- **Reason:** Pre-exposing SAC and a full hyperparameter list biased the
  researcher towards easy mutations before diagnosis. Removing that bias must not
  create the reverse bias of locking PPO in.
- **Supersedes:** "SAC parameters remain available to the researcher, but SAC is
  not active" and "`research/current_params.json` holds generic runtime knobs
  only: `algorithm`, `ppo`, `sac`, `policy`, `training`".

## 2026-08-29 — Opaque effective configuration and minimal proposals

- **Decision:** `robot_learning/train.py` owns the interpretation of the active
  runtime configuration and writes its resolved `effective_config` into every
  artifact. The runner obtains the expected value from the training
  implementation and compares it only for equality; it does not reconstruct
  PPO parameters, divide rollout steps, or interpret configuration sections.
- **Decision:** An ordinary training proposal requires only `kind`, `family`,
  `hypothesis`, `change`, and `initialization`. `training_parent` is required
  only for transfer and rejected for fresh initialization. `training_seed` and
  `params` remain optional; code-only and structural experiments remain valid.
- **Reason:** The prior reusable-artifact check embedded the current PPO
  configuration shape in the protected runner, and the proposal validator
  contradicted the method-neutral protocol by forcing configuration fields.

## 2026-08-29 — Remove migration-only numerical goldens

- **Decision:** Remove `tests/research/scenario_goldens.json` and its numerical
  scenario-regression test. They were temporary evidence that the scenario
  extraction was bit-identical, not a permanent contract for researcher-owned
  reward, observations, environment or evaluation code.
- **Decision:** Keep the functional reward tests and express their expectations
  through the active reward coefficients instead of the superseded initial
  coefficient values.
- **Reason:** Exact snapshots of researcher-mutable outputs made intentional
  reward experiments fail against historical values. Protected task invariants
  and behavioral properties remain covered by their dedicated tests.


