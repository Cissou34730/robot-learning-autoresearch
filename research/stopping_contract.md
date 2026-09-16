# Terminal-readiness stopping contract

This contract defines what evidence supports a terminal official-assessment
request. It is advisory in this version: it does not block a request, authorize
a verdict, or decide when the campaign ends. The Researcher still makes the
scientific stopping decision.

## What problem this addresses

The official benchmark requires at least 196 successful episodes out of 200
(98.0%). Development evidence is collected on fixed panels. Selecting the
best model using a panel biases that panel's measured success upward, so a
development result at or above the objective does not imply the official panel
is likely to pass. At a true episode-success probability of 98%, the official
rule passes with probability only about 62.9%.

The unmet need is a predeclared, deterministic, uncertainty-aware account of
whether terminal evidence has been collected. This is a stopping-evidence
problem, not a reviewer-wording problem.

## Definitions

- **Objective threshold**: `FINAL_SUCCESS_PERCENT = 98.0` on
  `EVALUATION_EPISODES = 200` episodes.
- **Selection episodes**: episodes of the best-known model that were available
  before or at the moment the model was designated best-known. Their measured
  success is upward-biased.
- **Stopping-validation panel**: a panel measured on the frozen best-known model
  *after* its designation, using episode seeds not used by any earlier
  measurement of that model, and declared before its result is observed. This is
  a fresh, fixed-policy panel: it measures one saved artifact and does not
  involve retraining.
- **Stopping evidence**: the one-sided lower confidence bound on success for a
  stopping-validation panel.

## Contract

1. A development result on selection episodes is not by itself terminal
   readiness evidence, no matter how high it is.
2. Terminal readiness requires a stopping-validation panel whose one-sided
   lower confidence bound on success, at `STOPPING_CONFIDENCE = 0.80`, meets or
   exceeds the objective threshold.
3. The panel must be large enough for its resolution to matter. At 200 episodes
   and 80% confidence, the rule requires at least 198 of 200 observed successes;
   196 or 197 observed successes are not supported.
4. A panel that reuses selection seeds is not a stopping-validation panel. Reuse
   is detected structurally from recorded episode seeds, never inferred from
   prose.
5. Independent retraining replication is distinct evidence. It reduces variance
   in the learning process, not in a fixed model's measured success, and cannot
   substitute for a stopping-validation panel.
6. All detailed episode evidence and immutable model identity are preserved.
   The contract consumes them; it does not summarize them away.

## What this reduces and what it cannot guarantee

- It reduces the risk of a premature terminal request driven by selection bias
  on reused episodes.
- It cannot guarantee the official result. A perfectly measured 100% panel still
  leaves open the possibility that the official panel differs because the two
  panels are finite and distinct.
- It trades premature assessment for delay. Requiring a fresh panel costs
  episodes and does not imply that more confirmation is always better.

## Retrospective diagnostic

Four frozen campaigns were examined as a diagnostic only:

| Campaign experiments | Best-known development evidence | Official outcome |
| ---: | --- | --- |
| 1 | 98.5% research, 98.0% task-reference | 97.0%, goal not reached |
| 2 | 98.0% research, 98.5% task-reference | 98.0%, goal reached |
| 4 | 98.0% research, 98.5% task-reference | 98.0%, goal reached |
| 6 | 98.0% research, 98.5% task-reference | 98.0%, goal reached |

Development evidence at the objective is not separated from the official outcome
by campaign depth. This is consistent with the statistical argument above and is
used only to justify collecting a fresh stopping-validation panel. The contract
is not tuned to reproduce these outcomes, and a fresh panel measured at 100%
would still not guarantee the official result.

## Tradeoff and status

The confidence level and the fresh-panel requirement are human-owned choices.
Lowering confidence or dropping the freshness requirement admits more terminal
requests at higher premature-risk; raising it delays terminal assessment and can
cause unbounded confirmation. The current values are deliberately non-blocking:

- The deterministic assessment is reported as evidence, not enforced.
- The policy must be prospectively validated on new campaigns and shown to be
  non-pathological before it becomes blocking.
- Retrospective analysis of frozen campaigns is used as a diagnostic only; the
  contract must not be tuned to reproduce any particular past outcome.
- Making the policy blocking requires explicitly revising the stopping wording
  in `research/program.md`.
