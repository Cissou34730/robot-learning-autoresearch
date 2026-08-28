# Protocol decision log

This file records human-approved choices about how research experiments are
run and compared. It explains *why* the active rules in `research/program.md`
exist. `program.md` remains the normative protocol when the two differ.

Training-recipe choices such as PPO hyperparameters and reward coefficients do
not belong here; they are experiment configuration and are tracked by experiment
cards and Git history.

## 2026-08-28 — Fixed final benchmark, flexible training target

- **Decision:** The reported task remains 1 cm for 2 seconds, currently 100
  consecutive control steps, over 200 fixed evaluation episodes.
- **Reason:** Every candidate needs one stable definition of success.
- **Boundary:** Training may use a curriculum or another intermediate target,
  but it cannot alter the final evaluator or reported benchmark.

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

## 2026-08-28 — Development checkpoint cadence

- **Decision:** Request a checkpoint evaluation every 20,000 training steps,
  executed only after a completed optimizer update/rollout.
- **Reason:** A checkpoint must represent a completed PPO update. If `n_steps`
  changes, the actual checkpoint is the first completed boundary after the
  nominal threshold (for example 20,480 with `n_steps=1,024`).

## 2026-08-28 — Use 200 development episodes

- **Decision:** Evaluate every development checkpoint on the same 200 episodes.
- **Reason:** With 50 episodes, one success changes the score by 2 percentage
  points and did not filter the noise we observed. With 200 episodes, one
  success represents 0.5 point and episode-by-episode paired comparisons have
  more discriminatory evidence.
- **Supersedes:** The earlier choice of 50 development episodes.

## 2026-08-28 — Retain three checkpoint finalists

- **Decision:** Keep three checkpoints from a completed training run, including
  their normalization and optimizer state.
- **Reason:** PPO can peak and regress during one run; retaining only the final
  checkpoint or one noisy apparent maximum discards useful candidates.
- **Selection:** Prefer checkpoints meaningfully better than the accepted
  champion. Among statistically equivalent checkpoints, preserve early,
  middle, and late training-time representatives. For the first baseline, where
  no champion exists, use the descriptive task ranking to choose the three.

## 2026-08-28 — Final paired tournament

- **Decision:** After training, compare the three finalists and the accepted
  champion on identical episodes: 200 episodes on each of three seeds, extended
  with additional seeds only for close or positive-but-uncertain results.
- **Reason:** Paired episodes distinguish a genuine behavioral improvement from
  different random target samples.
- **Isolation:** Development seeds, tournament seeds, and the fixed reported
  benchmark seed are disjoint.

## 2026-08-28 — Conservative champion promotion

- **Decision:** Promote a challenger only with positive paired net wins, an
  exact paired-test probability at or below 0.05, and an improvement exceeding
  the measured training-seed noise floor. Ties or insufficient evidence retain
  the champion.
- **Reason:** `kept/reverted` must be based on repeatable evidence rather than a
  tiny change in an aggregate score.
- **Reporting:** The untouched benchmark is run only after selection and never
  participates in choosing the winner.

## 2026-08-28 — Defer A/A calibration until the 98% regime

- **Decision:** Training-seed A/A calibration becomes mandatory only after the
  accepted champion reaches 98% success. Below 98%, structural experiments,
  including a researcher-designed curriculum, remain allowed.
- **Reason:** Repeating a weak recipe three times measures its weakness at high
  cost and blocks more useful structural research. Near the goal, the noise
  floor becomes necessary to distinguish small improvements.
- **Supersedes:** The earlier rule requiring calibration before every ordinary
  experiment whenever no noise floor existed.

## 2026-08-28 — Compact but diagnostic research memory

- **Decision:** Keep structured experiment cards, concise postmortems, a compact
  research brief, compressed training dynamics, and episode-level failure
  diagnostics.
- **Reason:** The researcher needs exact prior changes and failure geometry
  without loading large raw logs into the LLM context or repeating exhausted
  hypotheses.

