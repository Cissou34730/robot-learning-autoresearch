# Research design decision log

This file records the structural choices made with the human about the
simulation, learning setup, reward, researcher freedom, and experiment
selection protocol. It records both active decisions and the choices they
superseded. It does not instruct the autonomous researcher and does not replace
`research/program.md` or `research/current_params.json`.

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
  candidate decisions, and both model and code lineages.

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
  candidate training directories remain disposable. Archive the best challenger
  from every completed experiment and retain concise negative results.
- **Reason:** Models are small and local, so Git gives a recoverable lineage and
  prevents a later training run from silently erasing a previously accepted
  model or repeating a failed idea.

## 2026-08-28 — Researcher owns candidates and lineage decisions

- **Decision:** The researcher controls checkpoint timing, metrics, ranking,
  number of finalists, candidate submission, and which candidate or prior
  champion becomes the lineage for subsequent work.
- **Runner role:** Allocate compute, execute, measure the fixed objective, and
  persist every submitted candidate and its evidence. Do not promote, retain,
  or roll back scientific work automatically.
- **Workflow:** An experiment ends with measured candidates and a pending
  researcher decision. The next proposal records `continue_from` and its
  rationale before defining the next experiment.
- **Reason:** Candidate selection and temporary regressions are part of the
  research method. A fixed automatic promotion rule can discard a lineage that
  is scientifically useful for curriculum or longer-term learning.
- **Supersedes:** Runner-owned `promoted/champion retained`, automatic rollback,
  mandatory A/A gating, the three-finalist limit, and the four progress metrics
  as fixed runner policy.

## 2026-08-28 — Project map is descriptive, not a code whitelist

- **Decision:** Explain the role of important files without instructing the
  researcher that learning changes must fit a narrow per-file whitelist.
- **Invariant:** The objective definition, robot identity, corrected task
  geometry, and mechanical runner remain protected. Other learning and
  measurement implementation may evolve while tests preserve the objective.
- **Reason:** Scientific freedom must exist in executable code, not only in the
  wording of `program.md`.

## 2026-08-28 — Researcher owns evaluation and both lineages

- **Decision:** Training produces a neutral inventory of periodic checkpoints.
  It performs no development ranking and does not retain an automatic top three.
- **Decision:** After training, the researcher chooses which candidates or
  champion to evaluate, with which episode counts, seeds, comparisons, and
  diagnostics. The runner executes that request exactly. The fixed paired
  tournament is removed.
- **Decision:** After measurement, the researcher chooses both the model lineage
  and the code/configuration lineage (`keep`, `revert`, or `revise`). The runner
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
