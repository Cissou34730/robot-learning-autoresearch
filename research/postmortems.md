# Research postmortems

> One section per experiment, appended by the researcher after reading the
> training log and evaluation diagnostics. Fresh sessions MUST read the last
> few sections before choosing an experiment.

## Experiment 28 — ent_coef 0.01 → 0.005 (parameter mode) — hypothesis PARTIALLY supported; most informative scenario-2 run so far

**Result:** 0% eval success, mean/median dist 14.3/14.5 cm. Verdict recorded as
"reverted (worse)" against the 100% header — note that header is a retired
scenario-1 score, so the true comparator is runs 20–24 (all 0%, median ~2.1 cm).
By that standard this run is not "worse"; it is qualitatively different.

**Was the hypothesis supported?** Half. The mechanism predicted — lower noise
equilibrium makes band-entry streaks samplable and unlocks the curriculum —
**worked for the first time in scenario 2**: rollout `success_rate` was nonzero
from step 1 (0.33–0.50 for the first ~20k steps), proving stage-0 holds (3 cm ×
5 steps) finally occurred during stochastic training. Every predecessor
(20–24) sat at exactly 0 all run. The std trajectory confirms the knob did what
was claimed: 0.99 → 0.165 by end (exp 14 under ent_coef 0.01 plateaued at 0.72).
But the stronger claim — that this converts to eval success — is falsified:
success_rate declined monotonically from ~20k steps, hit exactly 0 at ~67k, and
stayed pinned there for the final 55k steps while ep_len_mean rose back to 500.

**What behavior changed:** early rollouts approached and terminated quickly
(ep_len ~360, ep_rew +9 around iter 15–20 — the healthiest scenario-2 training
state ever logged); afterwards holding events vanished entirely and the final
deterministic policy barely approaches at all (mean 14.3 cm vs 2.1 cm for all
predecessors). Value fitting stayed excellent throughout
(explained_variance 0.92–0.99 late), so this is not an optimization failure.

**Likely current binding constraint:** the hold signal exists only behind
*consecutive-streak termination*, and the only thing that ever produced those
streaks was incidental noise-driven contact. As noise fell, incidental contact
disappeared before deliberate station-keeping could be learned — the
chicken-and-egg loop persists in a new form: precision needs hold-reward
samples; samples need contact; contact needs noise; noise destroys precision.
Worse, once holds became unreachable, the dense-shaping + action-cost economy
made *parking still far away* near-optimal (ep_rew recovering −14.7 → −1 with
zero completions; approach actively degraded). A policy that cannot terminate
is taught to freeze, not to reach.

**What was learned / do NOT retry:** (a) exploration-noise scale was genuinely
part of the blockage — but lowering it via ent_coef alone removes the accidental
contact that fed the curriculum without adding any deliberate incentive;
ent_coef below 0.005 or log_std-style noise shrinking should not be retried
alone. (b) Do not re-run gamma/dwell/bonus reweightings under the OLD noise
regime assumptions — exps 21–23 were tested in a regime where the band was
never entered; their verdicts may not transfer to a low-noise policy.
(c) The ratchet's best=100% (scenario-1 scoring) makes every scenario-2 result
auto-"reverted"; experimenter may want to reset the baseline header so real
scenario-2 progress can be kept.

**Recommended next experiment class:** reward structure. The now-proven low-noise
policy can actually occupy the band — it just has no standing reason to. Make
in-band occupancy itself valuable every step (e.g. DWELL_BONUS_PER_STEP 0.5 → 10,
pure parameter mode) so a converged low-noise controller has a continuous
gradient pulling it into and anchoring it inside the band, independent of
whether a 100-step termination streak occurs. Exp 21 tested exactly this knob
but under high noise where entry never happened; the regime has changed.

## Experiment 29 — ent_coef 0.01 → 0.005 + DWELL_BONUS_PER_STEP 0.5 → 10 (parameter mode, coordinated) — hypothesis NOT supported; completes the noise × dwell factorial

**Result:** 0% eval success, mean/median dist 4.3/3.7 cm (comparator vs runs
20–24: mean was ~2.1 there, so the final policy hovers *farther* out — just
outside the 3 cm stage-0 band). Verdict auto-"reverted" against the retired
scenario-1 100% header.

**Was the hypothesis supported?** No. The untested fourth cell of the
{noise, dwell} factorial (low noise + high dwell) failed with the *same
signature* as cell three (exp 28): rollout success_rate started at 0.5,
peaked ~0.5 (ep_rew_mean up to 39.8, ep_len 373 — terminations were paying
~80 each and occurring in half of all rollouts), then declined monotonically
and hit exactly 0 at iter 62/118 (~63k steps), ep_len pinned at 500 thereafter.
Incentive scale did not change the outcome at all — the decline tracks
exploration-std decay, not payoff size.

**What behavior changed:** same three phases as exp 28. (1) Early noise-driven
terminations, healthy approach. (2) Slide: as std decayed, entries vanished
before deliberate station-keeping formed; ep_rew crashed 39.8 → −13. (3)
Freeze basin: ep_rew recovered −13 → +1.6 with success pinned at 0 and
explained_variance 0.97–0.998 — the value function perfectly fits the
freeze-far-away regime, actively sealing it. Final hover at 3.7 cm sits just
outside the stage-0 band, clipping it occasionally (source of the +1.6).

**Likely current binding constraint:** attribution masking under exploration
noise plus premature commitment. While torque noise dominates, in-band
occupancy is caused by noise, so advantages cannot credit the *mean* action
for station-keeping; by the time std falls far enough for actions to matter,
the policy has already drifted into the freeze basin and PPO+entropy-collapse
locks it there behind a confidently-fit value function. Secondary: the
curriculum never advanced past stage 0 in ANY scenario-2 run (advance needs
≥0.7; peak was 0.5), so the entire ladder above 3 cm × 5 steps is untested
territory. Note the streak-reset mechanic: an oscillating policy that spends
half its time in-band earns almost nothing, so partial competence is not
reinforced proportionally.

**What was learned / do NOT retry:** the {noise ↓, dwell ↑} 2×2 is now fully
explored — all four cells fail identically (21: high/high; 28: low/low; 29:
low/high; 20–24: high/low baseline). Making occupancy samplable, valuable, or
both is jointly insufficient; neither ent_coef, DWELL_BONUS_PER_STEP, gamma,
nor HOLD_COMPLETE_BONUS should be retouched along these axes. Coefficient /
hyperparameter tuning around the reach-and-hold economy is exhausted. Also:
termination truncates the episode on the 5th in-band step, so trajectories
that would teach *holding longer* are never observed even when succeeds happen.

**Recommended next experiment class:** reward structure (code mode,
reach_reward.py only). Restructure HOW occupancy pays, not how much: replace
the consecutive-streak ramp (hard reset to 0 on one out-of-band step) with a
payment proportional to recent in-band *rate* (or a flat unconditional per-
in-band-step payment), so partial competence earns proportional reward and the
gradient from freeze-basin → hover → hold becomes continuous instead of
all-or-nothing. This directly targets the newly identified partial-competence
blind spot and does not touch thresholds, hold logic, or the evaluator.



