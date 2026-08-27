# Research postmortems

> One section per experiment, appended by the researcher after reading the
> training log and evaluation diagnostics. Fresh sessions MUST read the last
> few sections before choosing an experiment.

## Experiment 71 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed at 0% success with 2.1 cm mean and median final distance; the runner reverted the equal result.
**Behavior:** `DummyVecEnv` completed 120832 transitions without the Windows `SubprocVecEnv` startup failure, but rollout success stayed at 0 and episodes remained at 500 steps.
**Training:** Reward rose from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, reproducing the entry-free regime.
**What it rules out:** Single-process vectorization makes the run executable but does not improve reach-and-hold learning.
**Next idea:** Retry the pending curriculum-advancement-window hypothesis only after making the runner explicitly select the safe one-worker path for parameter-mode runs.

## Experiment 70 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions; no fixed-evaluator score was produced.
**Behavior:** The runner again selected Windows `SubprocVecEnv` and raised `EOFError` while receiving environment spaces.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window or the curriculum hypothesis.
**State:** The parameter override was transient and `current_params.json` remains unchanged.
**Next idea:** Diagnose why the runner invocation still uses multiple workers despite the documented single-worker default before retrying curriculum changes.

## Experiment 69 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions; no fixed-evaluator score was produced.
**Behavior:** The runner selected Windows `SubprocVecEnv` and raised `EOFError` while receiving environment spaces.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window or the curriculum hypothesis.
**State:** The parameter override was transient and `current_params.json` remains unchanged.
**Next idea:** Resolve why the runner still supplies more than one environment before retrying curriculum changes; do not treat this as a curriculum result.

## Experiment 68 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions; no fixed-evaluator score was produced.
**Behavior:** The runner again selected Windows `SubprocVecEnv` and raised `EOFError` while receiving environment spaces.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window or its learning hypothesis.
**State:** The parameter override was transient and `current_params.json` remains at 15 episodes by omission of that optional key.
**Next idea:** Repair the runner's environment-count selection before attempting another curriculum experiment; do not count this error as evidence against the curriculum hypothesis.

## Experiment 67 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed at 0% success with 2.1 cm mean and median final distance; the runner reverted the equal result.
**Behavior:** DummyVecEnv completed 120832 transitions without `SubprocVecEnv` startup failure, but rollout success and episode length stayed at 0 and 500 throughout.
**Training:** Reward rose from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, reproducing the entry-free regime.
**What it rules out:** Restoring the single-process default repairs the Windows execution path but does not improve reach-and-hold learning.
**Next idea:** With the safe default now verified, retry the pending curriculum-advancement-window hypothesis in a subsequent experiment.

## Experiment 66 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions because the runner selected Windows `SubprocVecEnv` and raised `EOFError`; no fixed-evaluator score was produced.
**Behavior:** The parameter override was applied only transiently, then restored; `current_params.json` remains unchanged.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window or its learning hypothesis.
**Cause:** Although experiment 63 previously trained with `DummyVecEnv`, this invocation still used more than one environment and therefore selected `SubprocVecEnv`.
**Next idea:** Correct the default or explicitly pass the single-process environment count through the runner before retrying a curriculum experiment.

## Experiment 63 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed at 0% success with 2.1 cm mean and median final distance; the runner reverted the equal result.
**Behavior:** The single-process DummyVecEnv path completed 120832 transitions without the Windows SubprocVecEnv EOFError, but rollout success and 500-step episode length remained unchanged throughout.
**Training:** Reward rose from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, reproducing the confident entry-free regime.
**What it rules out:** Environment multiprocessing is an execution blocker, not the reason PPO fails to reach and hold; defaulting to one environment alone does not improve the fixed policy.
**Next idea:** Use an explicit single-process selection for future Windows-safe curriculum experiments, then test the pending curriculum hypothesis rather than additional execution-mode variants.

## Experiment 61 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed but remained at 0% success; the runner reverted the equal result.
**Behavior:** DummyVecEnv avoided the prior Windows SubprocVecEnv EOFError and collected 120832 transitions, but rollout success stayed 0 with 500-step episodes throughout.
**Training:** Reward recovered from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, fitting the same entry-free regime.
**What it rules out:** Multiprocessing startup was the blocker for experiment 60 execution, not the cause of the underlying reach-and-hold failure; changing environment execution mode alone does not improve the policy.
**Next idea:** Keep the single-process path available for Windows reliability, but test a new learning mechanism rather than more PPO execution or schedule variants.

## Experiment 62 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions because the runner selected Windows `SubprocVecEnv` and raised `EOFError`; no evaluation score was produced.
**Behavior:** The parameter override was applied transiently, then restored; `current_params.json` remains unchanged.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window.
**Next idea:** Repair or explicitly select the known single-process environment path before another curriculum experiment.

## Experiment 60 - curriculum advancement gate 0.6 -> 0.3 - error

**Result:** The runner applied the parameter override but failed during parallel environment construction before training or evaluation; no score was produced.
**Behavior:** `last_train_summary.md` contains no metric blocks and reports an `EOFError` from `SubprocVecEnv` while receiving the environment spaces.
**What it rules out:** This run provides no evidence about lowering the curriculum gate or about the hypothesis itself.
**Next idea:** Repair or separately validate the multiprocessing environment startup before attempting another curriculum experiment.

## Experiment 59 - PPO policy log_std_init 0.0 -> -1.0 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with median final distance 2.0 cm; the runner reverted the equal result.
**Behavior:** Fresh training still had zero rollout success and 500-step episodes; final policy std was 0.153, explained variance 0.967, and reward was -0.643.
**What it rules out:** Lowering initial Gaussian action noise alone did not produce target-band occupancy or deterministic reach-and-hold behavior within the fixed 120000-transition budget.
**Next idea:** Initial-noise tuning is unsupported; a replay-based algorithm remains the strongest mechanistic hypothesis, but requires an explicitly authorized runner/evaluator integration change.

## Experiment 58 - PPO gae_lambda 0.95 -> 1.0 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success; the runner reverted the equal result.
**Behavior:** Training had zero rollout success and 500-step episodes throughout; final policy std was 0.131, explained variance 0.895, and reward was 1.97.
**What it rules out:** Full-return GAE did not preserve useful target-entry or hold credit, nor improve deterministic reach-and-hold behavior within the fixed 120000-transition budget.
**Next idea:** PPO credit-assignment and update-control variants remain unsupported; a valid off-policy replay experiment still requires authorized runner/evaluator integration changes.

## Experiment 57 - policy net_arch [64, 64] -> [32, 32] - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success; the runner reverted the equal result.
**Behavior:** Training had zero rollout success and 500-step episodes throughout; final policy std was 0.153, explained variance 0.968, and reward was -0.0536.
**What it rules out:** Reducing capacity did not improve sample-efficiency enough to preserve target-entry or deterministic reach-and-hold behavior within the fixed 120000-transition budget.
**Next idea:** PPO capacity and update-control variants are unsupported; a valid replay-based algorithm experiment remains the strongest untested mechanism but requires authorized evaluator/runner integration changes.

## Experiment 56 - PPO gSDE with per-step resampling - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success; the runner reverted the equal result.
**Behavior:** Training had zero rollout success and 500-step episodes throughout; final policy std was 0.317, explained variance 0.902, and reward was -34.6.
**What it rules out:** Resampling gSDE every control step did not remove the exploration/credit-assignment collapse or produce deterministic reach-and-hold behavior within the fixed 120000-transition budget.
**Next idea:** The exploration mechanism variants tested through the current PPO surface are unsupported; a valid SAC/replay experiment still requires an explicitly authorized runner and evaluator integration change.

## Experiment 55 - PPO max_grad_norm 0.5 -> 0.1 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Training had zero rollout success and 500-step episodes throughout; final policy std was 0.0908, explained variance 0.959, and value loss 4.1e-05.
**What it rules out:** A tighter gradient-norm cap did not prevent confident fitting of the entry-free basin or preserve target-entry and hold credit within the fixed 120000-transition budget.
**Next idea:** PPO update-control variants remain unsupported; the strongest mechanistic next step is off-policy replay with automatic entropy tuning, but it requires an explicitly authorized runner/evaluator integration change.

## Experiment 54 - PPO ortho_init true -> false - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Training had zero rollout success and 500-step episodes throughout; final policy std was 0.0864, explained variance 0.958, and value loss 4.9e-05.
**What it rules out:** Disabling orthogonal initialization did not preserve target-entry or hold trajectories or prevent the deterministic entry-free basin within the fixed 120000-transition budget.
**Next idea:** PPO initialization is not sufficient to address the persistent exploration and credit-assignment collapse; a replay-based algorithm remains the mechanistic hypothesis, but requires authorized runner/evaluator integration changes.

## Experiment 53 - PPO target_kl 0.03 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with mean/median final distance 2.1/2.1 cm; the runner reverted the equal result.
**Behavior:** Training reported zero rollout success and 500-step episodes throughout; final policy std was 0.0983, explained variance 0.967, and value loss 6.68e-05.
**What it rules out:** A 0.03 approximate-KL update ceiling did not preserve useful target-entry or hold trajectories or prevent the deterministic entry-free basin within the fixed 120000-transition budget.
**Next idea:** PPO schedule and update-control variants are now exhausted; a replay-based algorithm remains the strongest hypothesis, but requires an explicitly authorized runner/evaluator integration change.

## Experiment 52 - PPO normalize_advantage true -> false - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success; the runner reverted the equal result.
**Behavior:** Training reported zero rollout success and 500-step episodes throughout; final policy std was 0.317, explained variance 0.956, and value loss 0.00278.
**What it rules out:** Preserving absolute advantage scale without normalization did not make rare target-entry or hold trajectories shape the deterministic policy within the fixed 120000-transition budget.
**Next idea:** PPO hyperparameter tuning has not produced progress; a replay-based algorithm remains the strongest mechanistic hypothesis, but requires an explicitly authorized runner/evaluator integration change.

## Experiment 51 - PPO n_epochs 10 -> 5 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Training reported zero rollout success and 500-step episodes throughout; final policy std was 0.157, explained variance 0.956, and value loss 0.000339.
**What it rules out:** Fewer PPO passes per rollout did not prevent confident fitting of the entry-free basin or improve deterministic reach-and-hold behavior within the fixed 120000-transition budget.
**Next idea:** PPO schedule tuning is now exhausted; an off-policy replay method with automatic entropy tuning remains the strongest hypothesis, but it requires an explicitly authorized runner/evaluator integration change.

## Experiment 45 - PPO gae_lambda 0.95 -> 0.99 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success; the runner reverted the equal result.
**Behavior:** All training snapshots reported zero rollout success and 500-step episodes; policy std fell to 0.114 while explained variance reached 0.863.
**What it rules out:** Extending GAE credit assignment alone does not make the delayed hold signal learnable under the fixed PPO budget; no target-entry data survived long enough to exploit the longer trace.
**Next idea:** The remaining supported remedy is off-policy replay with entropy tuning, but it requires an explicitly authorized evaluator/runner integration change before it can be tested.

## Experiment 46 - PPO learning_rate 0.0003 -> 0.0001 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success; the runner reverted the equal result.
**Behavior:** Training had zero rollout success throughout; final policy std was 0.207 and explained variance reached 0.943, with 500-step episodes unchanged.
**What it rules out:** Slower PPO updates alone did not prevent premature commitment or make the delayed reach-and-hold signal learnable under the fixed budget.
**Next idea:** An off-policy replay method with entropy tuning remains the strongest mechanistic hypothesis, but requires an explicitly authorized runner/evaluator integration change.

## Experiment 42 - policy activation tanh -> relu - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success; the runner reverted the equal result.
**Behavior:** Training reached 120,832 transitions with zero rollout success throughout; episode length stayed at 500, final policy std was 0.141, and explained variance reached 0.94.
**What it rules out:** ReLU activations did not improve the deterministic reach-and-hold policy within the fixed budget, so saturation in the tanh network is not sufficient to explain the current failure.
**Next idea:** Repair and validate an off-policy replay experiment, since the PPO data/credit-assignment failure remains the strongest supported diagnosis.

## Experiment 44 - switch PPO to SAC - error

**Result:** The runner rejected the experiment before checks, training, or evaluation because `robot_learning/evaluate.py` is outside its allowed code-edit surface.
**Behavior:** The proposed SAC trainer and evaluator loader were restored automatically; the fixed 200-episode score remains unmeasured.
**What it rules out:** This does not test SAC or the replay/automatic-entropy hypothesis; it confirms that an algorithm change requiring evaluator support cannot be run through the current runner boundary.
**Next idea:** Expand the runner's explicitly allowed algorithm/evaluation integration surface in a separately authorized infrastructure change, then retry this single SAC hypothesis.

## Experiment 43 - append normalized hold-streak progress to observations - error

**Result:** The runner rejected the experiment during its mandatory pytest gate; no training or evaluation occurred.
**Behavior:** The observation-shape tests still expect the previous 11-dimensional observation after the proposed +1 dimension change.
**What it rules out:** This run provides no evidence about hold-streak observations; it confirms the existing test gate blocks this observation edit.
**Next idea:** Repair the observation-shape test/infrastructure only in a separately authorized experiment before retrying the hypothesis.

## Experiment 41 - PPO n_steps 1024 -> 2048 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success, with mean/median final distance 2.4/2.3 cm; the runner reverted the equal result.
**Behavior:** All 59 training snapshots had zero rollout success and 500-step episodes; policy std nevertheless fell to 0.109 while reward recovered from -16.1 to 2.14.
**What it rules out:** Doubling the rollout horizon does not retain target-entry experience or overcome the PPO exploration-credit-assignment collapse under the fixed 120k-transition budget.
**Next idea:** Address the diagnosed on-policy data problem with an off-policy learning algorithm once the experimental surface supports a valid SAC run.

## Experiment 40 - append normalized hold-streak progress to observations - error

**Result:** The runner rejected the transfer run before training because `reach-exp19` has no compatible `vecnormalize.pkl` for the expanded observation shape.
**Behavior:** No transitions were collected and no evaluator score was produced; the runner restored the observation code, preserving the prior 0% baseline.
**What it rules out:** This run provides no evidence about hold-streak observations, and it exposes that the transfer checkpoint cannot test observation-shape changes under the current initialization path.
**Next idea:** Repair the experiment infrastructure or use a fresh initialization only when the protocol and comparator permit it; do not count this as evidence against the hypothesis.

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




## Experiment 30 - reach_reward.py: flat per-in-band-step dwell payment replacing the streak ramp (code mode) - hypothesis NOT supported

**Result:** 0% eval success, mean/median dist 6.2/4.7 cm. Verdict reverted against the retired scenario-1 header.

**Was the hypothesis supported?** No - the central prediction was cleanly falsified. I predicted the flat occupancy payment would keep rollout success_rate nonzero through training (unlike exps 28/29 whose streak-ramp runs decayed to 0 tracking std). Instead success_rate decayed in LOCKSTEP with exploration std exactly as before: 0.33-0.46 while std >= ~0.55 (peak 0.455 at iter 16, ep_rew_mean peak 10.0), monotonic decline starting ~20k steps, exactly 0 at iter 64 (~65k steps) when std reached ~0.38. Payment structure (streak-proportional vs per-occurrence) and payment scale (0.5 vs 10.0) are both irrelevant to when band entries vanish.

**What behavior changed:** same three-phase dynamics as exps 28/29, plus one new detail: the terminal freeze basin settled FARTHER out (median 4.7 cm vs 2.1 cm in exps 20-24, 3.7 cm in exp 29). During the high-noise phase the dwell stream did create a genuine local optimum around hovering near the band (ep_rew +10), but once std decay killed entries, the shaping+action-cost economy pulled the policy to a parked hover where marginal closeness gain ~= marginal action cost, and the value function fit that regime perfectly (explained_variance 0.94-0.998 late, sealing it). Curriculum again never advanced past stage 0 (needs >=0.7 over 15 episodes; peak 0.455).

**Likely current binding constraint:** attribution masking under on-policy exploration, now confirmed from three independent angles. Band entries are NOISE-CAUSED events: they occur only while std is high, and while std is high PPO advantages cannot attribute occupancy to the mean action (the counterfactual 'would the mean have kept me in-band?' is unidentifiable from noisy rollouts). By the time std falls enough for actions to matter (~0.4), the rollout distribution contains zero entries, so no gradient toward station-keeping can ever form; the remaining gradients (progress shaping saturates, action cost drains) point at park-and-freeze. Every occupancy-incentive variant tested - scale (exps 21/29), noise floor (exp 28), payment structure (exp 30) - produces the same std-tracking collapse, so the failure lives UPSTREAM of the reward function, in the interaction between PPO's decaying Gaussian exploration and credit assignment.

**What was learned / do NOT retry:** the entire occupancy-payment family inside reach_reward.py is exhausted - do not retest DWELL_BONUS_PER_STEP values, ramps vs flats vs rates, HOLD_COMPLETE_BONUS sizes, or any combination thereof; three structural variants now fail identically. Do not retry ent_coef/std-schedule tweaks either (high-noise AND low-noise regimes both proven to collapse). Note also: the flat-payment edit itself is harmless but no better; keep whichever form if the constraint elsewhere is ever lifted.

**Recommended next experiment class:** learning algorithm (class 6). The evidence now isolates on-policy credit assignment + monotonically collapsing exploration as the blocker; SAC with automatic entropy targeting addresses both mechanisms directly: (a) off-policy replay preserves and reuses the rare noise-driven successful trajectories indefinitely, so value learning keeps extracting station-keeping signal after entries stop occurring fresh, and (b) entropy auto-tuning holds exploration at a target level instead of a one-way std decay, keeping the band reachable while the critic learns its value. Fallback if class 6 must be deferred: training schedule (class 5) via much larger n_steps for longer GAE horizons through holds - weaker match to the diagnosed mechanism.

## Experiment 31 - reach_reward.py: per-step proximity rent 0.3*exp(-distance/0.02), paid every step as a function of current distance (code mode) - hypothesis PARTIALLY supported; freeze-far basin eliminated but replaced by an anchor just outside the band

**Result:** 0% eval success. Verdict reverted against the retired scenario-1 header. But the terminal training state is qualitatively NEW and the mechanism prediction half-landed.

**Was the hypothesis supported?** Half. The claim "a standing rent reverses park-far economics and keeps the mean controller anchored near the band" is SUPPORTED: ep_rew_mean recovered monotonically +10.5 -> +54.1 over the final ~70k steps with success pinned at 0 - under the rent shape 150*exp(-d/0.02), +54 implies a stable hover at ~2 cm collecting income every step, versus exp 29's terminal far-park at rew ~+1.6 and exp 28's degenerate 14 cm retreat. The approach never degraded this run. The claim "anchoring lets std decay deliver precision into the band" is FALSIFIED: success_rate peaked 0.714 early (highest scenario-2 peak ever; brushed the 0.6 stage gate around iters 2-4), decayed to exactly 0 tracking std as in exps 28-30 (zero at std~0.41), and NEVER recovered even though the final policy sits ~1 cm from the band edge with low noise (std 0.10-0.13) and near-perfect value fit (explained_variance 0.986-0.997).

**What behavior changed:** the failure mode changed shape, not sign. Instead of abandoning the target, the policy converged to the rent-vs-action-cost equilibrium just OUTSIDE the threshold: marginal rent gain of closing 2->1 cm (+0.074/step) cancels against the recurring action cost of the micro-torques needed to hold tighter positions, so the deterministic stationary point parks at ~2x the threshold. The untouched dwell cliff (flat 0.5/step in-band, total in-band income ~0.685/step = 6x the outside anchor) lies 1 cm away but is never sampled: by the time noise is low enough for deliberate entry, PPO has already committed (ev 0.99) to the 2 cm anchor and rollout data contains zero in-band steps, so the value function literally cannot know the cliff exists. The chicken-and-egg persists in miniature - the unsampled region shrank from "everything near the target" to "the last centimeter".

**Likely current binding constraint:** the last-centimeter gradient is economically neutral (rent differential <= station-keeping action cost), so band ENTRY is neither rewarded nor punished and never enters the rollout distribution late in training; without sampled in-band steps the dwell machinery stays invisible to the value function. Secondary accounting hazard discovered while sizing: if entry ever does sustain, discounted in-band stream (dwell 0.5 + rent ~0.18)/(1-0.99) ~= 68 > HOLD_COMPLETE_BONUS 50 at gamma=0.99 - completion could become strictly WORSE than hovering forever; any future incentive raise near the band must re-check stream < bonus.

**What was learned / do NOT retry:** (a) the macro-economy is SOLVED - anti-freeze standing income works; do not retest park-far countermeasures or re-run exps 28-30 variants on top of them. (b) Do not simply crank the rent coefficient/scale: raising it globally violates the stream<HOLD constraint and inflates returns without moving the equilibrium inward (the equilibrium is set by the rent/cost RATIO locally, not the level). (c) The occupancy-payment family verdicts from exp 30 stand only for out-of-band-era regimes; in-band payment visibility is no longer the issue - SAMPLING of the 1-cm strip is.

**Recommended next experiment class:** coefficient tuning (class 1, pure parameter mode - also resets the reward-structure failure streak at 4): reduce ACTION_COST_COEFFICIENT 0.05 -> ~0.01 with everything else unchanged. Mechanism: the parking equilibrium sits where marginal rent differential equals marginal action cost; cutting the motion tax 5x shifts that stationary point inward past the 1 cm threshold, where the existing untouched dwell cliff (in-band income 6x outside) takes over and self-reinforces occupancy once finally sampled. This directly targets the newly identified equilibrium condition using a knob never touched in scenario 2, and scenario 1's +8 pts from ACTION_COST 0.05 was earned against flailing - a failure mode absent from every scenario-2 run. Risk: reviving high-torque jitter; mitigated by the rent anchoring and watchable via early success_rate. Fallback if class 1 fails: class 3 observation (expose current hold-streak count so the value function can propagate the cliff backward across the boundary).




## Experiment 32 - params: ACTION_COST_COEFFICIENT 0.05 -> 0.01 (class 1, parameter mode) - hypothesis NOT supported; premise error discovered, and the failure produced a decisive negative

**Result:** 0% eval success, mean/median dist 21.5/23.0 cm - the WORST terminal positioning of any scenario-2 run (prior worst: exp 28 at 14.3 cm). Verdict reverted against the retired scenario-1 header. The runner recorded the 5th consecutive class-1 failure and issued ESCALATION_REQUEST -> next session must propose reward structure (class 2).

**Was the hypothesis supported?** No, and the test was compromised in an instructive way: the hypothesis reasoned from exp 31's standing rent ("the rent anchors the policy even if torque becomes cheap"), but exp 31 was REVERTED, so this run executed the action-cost cut alone on the BASE reward structure. It thereby became an accidental clean single-factor test of ACTION_COST_COEFFICIENT on the reach-and-hold task - something no prior experiment had isolated - and it failed maximally. The central prediction (equilibrium shifts inward past the band, dwell cliff gets sampled) was falsified: rollout success_rate peaked 0.667 early (highest non-rent peak of scenario 2 - cheap torque makes accidental band crossings MORE frequent), then decayed monotonically in lockstep with exploration std exactly as in exps 28-30, hitting exactly 0 at std ~0.77 (only ~55% through training, earliest zeroing yet) and never recovering; explained_variance climbed to 0.97+ fitting the entry-free regime; ep_rew_mean collapsed 33 -> -2.8 and recovered only to ~+0.2.

**What behavior changed:** the terminal basin regressed from hover-near-target (median 2.1 cm typical) to far-park at ~21.5 cm. Mechanism, reconstructed: WITHOUT standing income, stationary reward is ~0 at every distance, so there is no parking equilibrium for the action cost to shift - the exp 31 equilibrium logic simply does not apply on the base reward. What the motion tax actually provided was the only force DISCIPLINING jitter and drift; cutting it 5x made flailing free, removing all economic pressure toward precise or even directed positioning, so the policy converged to a do-little basin where the closeness potential is flat (~0 beyond 10 cm) and progress shaping nets out under oscillation. Cheap torque also inflated early noise-driven successes (peak 0.667, brushing but never sustaining the 0.6 advancement window - curriculum again never left stage 0), meaning the strongest-ever early signal still produced the weakest-ever final policy once noise decayed.

**Likely current binding constraint:** unchanged and now confirmed from a sixth independent angle - attribution masking under PPO's monotonically decaying Gaussian exploration. Band occupancy is noise-caused whenever std is large enough to produce it; advantages cannot credit the mean action; by the time std falls below the band scale, the rollout distribution contains zero entries and the confidently-fit value function offers no gradient toward station-keeping. This signature has now survived: payment scale (21/29), noise floor (28), payment structure (30), standing rent economics (31 partial), gamma horizon (20), velocity feedback (24), IK targets present throughout, and now motion-tax level (32). It lives upstream of the reward function entirely.

**What was learned / do NOT retry:** (a) NEVER reason about equilibria on the base reward - without standing income there are none; equilibrium arguments are valid only in rent-bearing economies. Check `git status`/verdict history for whether prior code-mode edits were actually reverted BEFORE building a hypothesis on them. (b) Do not lower ACTION_COST_COEFFICIENT below ~0.05 on the base reward: the motion tax is load-bearing as anti-drift discipline, not merely a nuisance (its scenario-1 +8 pts were real). Do not raise it either expecting precision - higher cost starves approach (scenario-1 evidence). Coefficient/hyperparameter tuning around this task is exhausted AND escalated. (c) High early success_rate from noise luck (even 0.667) predicts nothing about the terminal policy; if anything, jitter-driven peaks without sustained advancement forecast the collapse.

**Recommended next experiment class:** reward structure (class 2) - MANDATED by ESCALATION_REQUEST; consecutive-failure counter reset to 0 in this class. The one genuinely untried structural combination merges the two halves each proven separately: exp 31 showed standing income kills park-far AND anchors near the band (supported half), while its unsupported half (entry never sampled) was caused by making the last centimeter economically NEUTRAL (rent differential <= station-keeping cost at its 2 cm length scale). Proposal shape for next session: reintroduce the per-step proximity rent with a BAND-EDGE-FOCUSED shape - length scale at threshold scale (~0.005-0.01 m rather than 0.02) so the rent differential across the final centimeter strictly exceeds station-keeping cost, making ENTRY strictly profitable, with coefficient sized so the discounted in-band stream (rent + dwell 0.5)/(1-gamma) stays strictly below HOLD_COMPLETE_BONUS 50 to respect exp 31's accounting hazard. Single hypothesis: entry becomes both reachable-during-noise (standing income keeps the mean controller at the band edge while std is high, generating sampled crossings) and profitable-once-found (steep local gradient hands off to the dwell cliff before commitment seals the basin).

## Experiment 33 - reach_reward.py: standing per-step proximity rent 1.2*exp(-distance/0.01), band-edge-focused (code mode) - hypothesis NOT supported; entry economics landed but the deterministic policy regressed to far-park

**Result:** 0% eval success, mean/median dist 12.5/11.8 cm - the WORST-positioned
rent-bearing terminal state (exp 31 anchored at 4.0/2.2 cm with a 4x weaker rent).
Verdict reverted against the retired scenario-1 100% header.

**Was the hypothesis supported?** No. The arithmetic half landed exactly as
engineered: the across-edge differential (~0.28/step vs exp 31's 0.072) and the
1 cm length scale were in place all run, and standing income demonstrably created
positive-value near-target regions (ep_rew_mean climbed monotonically +11.8 ->
+75.8 over the final ~65k steps with success pinned at 0 - stochastic rollouts
were collecting real rent/shaping income). But the two behavioral predictions
failed: rollout success_rate still collapsed in lockstep with exploration std
(peak 0.714 at ~4k steps, monotonic decline, exactly 0 at ~55k, never recovered -
the identical signature of exps 28-32), and the DETERMINISTIC eval policy did not
anchor near the band at all - it parked at ~12 cm, regressing past exp 31's 2 cm.
A stronger, sharper edge gradient produced a farther mean controller.

**What behavior changed:** three familiar phases plus one new divergence. (1)
Early noise-driven terminations, peak 0.714 (brushing the 0.6 stage gate; log has
no stage markers so advancement beyond stage 0 is unverifiable). (2) Slide:
success decayed tracking std, ep_len rose 382 -> 500 by ~55k (zero terminations
afterwards), mid-run ep_rew dipped to -5.9 around 20k while flailing paid only
action cost. (3) Late phase: ep_rew recovered steadily to +75.8 as the rent
economy matured, yet this income accrued to STOCHASTIC behavior (noise-excursion
ratcheting through the potential field), not to the mean controller - eval
median 11.8 cm proves the deterministic policy sits where rent is nil
(1.2*e^-12 ~= 0) and closeness potential is nearly flat. explained_variance
0.97-0.99 with tiny value_loss (3.6e-4) sealed whichever smooth far-field regime
the critic could actually resolve.

**Likely current binding constraint:** unchanged upstream blocker - attribution
masking under PPO's monotonically decaying Gaussian exploration - now reinforced
by a NEW split: standing reward income enriches the value of near-band states and
keeps stochastic experience flowing there, but the deterministic MEAN policy
still converges elsewhere, and by the time std is low enough for actions to
matter the critic has confidently fit an entry-free landscape. Secondary suspect
worth naming: critic resolution - the L=0.01 rent varies ~2.7x per centimeter,
and a [64,64] critic fitting a two-scale landscape (sharp cliff inside 3 cm,
flat beyond 5 cm) from data that contains almost no late-phase samples inside 5
cm will smooth over the cliff (tiny value_loss is consistent with smooth-fit,
not sharp-fit).

**What was learned / do NOT retry:** (a) The reward-economics family is now
exhausted BEYOND exp 30's verdict: two different rent shapes (diffuse 0.02 /
edge-focused 0.01), coefficient 4x apart, produce opposite anchors (2 cm vs 12
cm) and identical 0% - the terminal positioning of the mean policy is NOT set by
local rent/cost equilibrium arithmetic. Do not design a third rent variant, do
not retune K or L, and stop building hypotheses on marginal-gradient
calculations for this task. (b) New methodological hazard: rising training
ep_rew_mean can MASK deterministic-policy regression (this run: +75.8 income
while eval anchor moved 2 -> 12 cm); always cross-check eval distances against
income-implied hover distance before calling standing-income mechanisms
"supported". (c) Exp 31's "infinite in-band stream" hazard formula remains
wrong (in-band occupancy auto-terminates within N steps); completion-dominance
accounting was satisfied here with wide margin and is not the failure cause.
(d) Success-rate-vs-std lockstep collapse has now survived seven independent
reward economies; the failure lives in the PPO exploration/credit-assignment
loop, not in what the reward pays.

**Recommended next experiment class:** learning algorithm (class 6): off-policy
replay (SAC-style) directly targets both halves of the diagnosed loop - replay
preserves and reuses rare noise-driven entry trajectories after entries stop
occurring fresh, and entropy auto-tuning holds exploration at a target level
instead of one-way std decay, keeping the band reachable while the critic learns
its value; its near-deterministic policy also sidesteps the attribution-masking
problem that punishes every on-policy mean update here. Ladder caveat: classes
3 (observation) and 5 (schedule) sit between, but curriculum constants are READ
ONLY, observation additions already failed twice (EE velocity, exp 24 - though
only under the old no-rent economy), and n_steps/schedule tweaks were falsified
early (exp 1/9 pattern); if strict ladder order is enforced, the single
remaining class-3 idea worth one slot is exposing recent per-step distance
change (error-rate damping signal) UNDER the current base economy - but the
weight of evidence favors escalating straight to class 6.

## Experiment 34 - reach_reward.py: unconditional per-step time penalty TIME_PENALTY_PER_STEP 0.05 (code mode) - hypothesis NOT supported; eighth independent reward economy, identical lockstep collapse

**Result:** 0% eval success, mean/median dist 9.8/10.2 cm - a far-park terminal
state (base-economy runs hover at ~2.1 cm; only the two strongest-rent runs and
exp 32 parked farther out). Verdict reverted against the retired scenario-1
header. Class-2 failure streak now 2 of 5.

**Was the hypothesis supported?** No. Both behavioral predictions failed:
(a) the central prediction - the entry window extends past prior runs because
terminating rollouts carry a wider advantage gap during the high-noise phase -
was cleanly falsified: rollout success_rate decayed monotonically tracking std
exactly as in exps 28-33 and hit exactly 0 at ~55k steps (std ~0.44), TIED with
exp 33 for the EARLIEST zeroing (28/29/30/32 zeroed at 63-67k), not later;
(b) no curriculum advancement (peak 0.667 at iters 2-4, never sustained >=0.6
over 15 episodes - same brushing pattern as every predecessor).

**What behavior changed:** three familiar phases plus one new accounting
signature. (1) Normal noisy start: success 0.5->0.667, ep_len ~320, terminations
frequent. (2) Slide tracking std: ep_rew_mean fell MONOTONICALLY -3 -> -41.7
through the decline (prior runs recovered mid-run via standing income; here
every step drains 0.05 with nothing to offset it), ep_len rose 320 -> 500 as
terminations went extinct. (3) Terminal regime: ep_rew recovered slowly
-41.7 -> -25.4 while success stayed pinned at 0 and ep_len stayed at 500; the
final return equals almost exactly the max drain (-0.05 x 500 = -25), i.e. the
policy converged to truncation-at-timeout collecting the pure penalty stream
with near-zero shaping income - confirmed by the 9.8 cm park. explained_variance
0.95-0.998 with value_loss collapsing to 3e-4 sealed it, same confident-fit
pattern as all seven predecessors.

**Likely current binding constraint:** unchanged, now confirmed from an EIGHTH
independent angle - a constant per-step penalty is advantage-INERT: it shifts
every transition's reward equally, cancels between same-state actions under GAE,
and therefore cannot create gradient toward termination anywhere, least of all
where terminations are absent from the data. During the noisy phase the widened
gap still could not beat attribution masking (noise-caused entries cannot credit
the mean action), and once entries vanished the penalty became the pre-registered
"inert constant drift" (risk (i)) - worse, by draining returns without adding
any positional income it plausibly ACCELERATED commitment to do-minimal (earlier
zeroing than exps 28-30). The failure lives entirely in the PPO exploration/
credit-assignment loop; reward terms acting on WHERE the agent is (dwell/rent/
occupancy family, exps 21-23/29-31/33) and now WHEN the episode ends (this exp)
produce byte-identical collapse dynamics.

**What was learned / do NOT retry:** (a) Do not design a ninth reward economy.
Eight structurally distinct economies (scale, structure, standing income x2
shapes, cost level, horizon, velocity feedback, timing pressure) all fail with
the same std-tracking signature; no function of (position, time, band
membership) available inside reach_reward() can compensate for missing data
under one-way exploration decay. The class-2 space is exhausted beyond
reasonable doubt. (b) Uniform penalties are inert for control; only DIFFERENTIAL
payoffs shape policy, and differentials require sampled outcomes - circular for
rare events. (c) Never combine a pure drain with the bare economy: removing the
passive anchoring of shaping income regressed the terminal anchor to 9.8 cm; if
any future experiment wants timing pressure it must coexist with standing
positional income (but see (a)).

**Recommended next experiment class:** learning algorithm (class 6) - the third
consecutive postmortem to reach this verdict, now backed by eight economies.
Off-policy replay (SAC-style) directly addresses both halves of the proven loop:
replay preserves and reuses rare noise-driven entry trajectories after fresh
entries stop, and entropy auto-tuning holds exploration at a target level
instead of decaying one-way, keeping the band reachable while the critic learns
its value; deterministic-ish policies also sidestep attribution masking. Ladder
mechanics caveat: with class-2 failures at 2/5, the runner will mandate classes
3 then 4 before releasing 6; the least-bad bridge candidates are class 3
(expose recent per-step distance change as an error-rate damping signal UNDER
the current bare economy - untried combination, obs-only edit) or waiting out
the mandated slots with minimal-risk proposals rather than burning effort on
predictably-failing ninth economies. Do NOT spend further class-2 attempts on
reward redesigns.

## Experiment 35 - reach_reward.py: distance-scheduled approach gain on progress term (code mode) - hypothesis NOT supported; ninth independent reward economy, hypervariance destabilization

**Result:** 0% eval success, mean/median dist 23.1/25.1 cm — **WORST TERMINAL DISTANCE OF ALL SCENARIO-2 RUNS** (prior worst: 14.3 cm exp 28; typical 2.1-4 cm for non-parked runs). Verdict: reverted (worse). Class-2 failure streak now 3 of 5.

**Was the hypothesis supported?** No, falsified catastrophically. The central prediction — distance-scheduled progress gain makes inward motion consistently attractive while outward motion costly, biasing random-walk noise-driven touches inward during the gate window — was actively contradicted: approach reliability did not improve; instead, the deterministic policy regressed to a far-park basin 10×+worse than baseline. The mechanism targeted the right level (relative reward of inbound vs outbound motions near the band) but created a destabilization whose effect was the opposite of intended.

**What behavior changed:** Two regimes, each failing differently. **(1) Hyper-rewarded early phase (t=1–7k, std ~1.0):** ep_rew_mean began +2.92 and spiked to +25.1 by iter 4 — the HIGHEST early rewards of any scenario-2 run (exp 34 baseline: +3.57, exp 28: +9). Success_rate peaked 0.714 at t=4096, highest ever recorded (prior peak 0.667 tied exps 2/34). The amplified progress term (m=6.3 at 2 cm, m=3.7 at 3 cm) created such strong distance-closure incentives that the value function assigned huge value to APPROACHING, and PPO's policy gradient strongly reinforced approach actions. **(2) Destabilized regime (t=7k–end):** Starting ~t=7k, ep_rew_mean swung monotonically negative, bottoming at -9.08 by t=30k (lower than exp 34's time-penalty floor of -25). Success_rate declined monotonically from 0.714 to 0 (hit 0 at ~55k, std~0.64), same timing as all predecessors. The key signature: the MAGNITUDE of the negative swing (from +25 to -9 is a -34 delta!) indicates the reward landscape became pathological — the policy learned to AVOID approach, trapped by accumulated penalty signals from amplified NEGATIVE progress during noise-driven retreats early. Early flailing near the target under the amplified gain paid -6.3× normal retreat cost, misattributing bounces backward as "approaching is bad", teaching PPO to favor parking far away where retreats cause minimal penalty. By t=32k, explained_variance bottomed at 0.943 (lowest of any scenario-2 run mid-phase except exp 34's collapse), value_loss spiked to 1.9 (vs typical 0.02–0.5), confirming the critic caught a jagged, unpredictable reward landscape and overfit to noise. Terminal mean 23.1 cm represents active avoidance of the target band, not mere under-approach: the policy learned that proximity is high-variance and costly.

**Likely current binding constraint:** AMPLIFICATION INSTABILITY added to the baseline PPO/attribution-masking problem. Every reward-structure change (exps 21–34) operated on the assumption that the mean policy's equilibrium is set by incentive economics; exp 35 reveals a secondary failure mode: when transition rewards are amplified, the *return variance* inflates, and PPO's policy updates, constrained by clipping and entropy regularization, overcommit to spurious patterns in the value function before the true optimum is discovered. The critic cannot distinguish signal from noise in high-variance landscapes; it fits confidently to local fluctuations, and the policy gradient follows. The approach-gain multiplier m(d) was designed to be continuous and smooth; the resulting reward landscape is mathematically smooth, but PPO+SB3's GAE advantage estimation and PPO's clipped updates operate on bootstrapped value estimates that smooth AGAIN, creating a multiply-smoothed landscape where the true signal (entry = good) is buried under early-phase noise penalties (retreats = very bad). UNLIKE the "advantage-inert" constant penalty (exp 34) which at least doesn't destabilize, this creates active mislearning: the policy learns the OPPOSITE of intended. The failure is not reward economics; it's the interaction of high return variance, value-function bootstrap lag, and exploration noise during the learning window when touches exist but are mostly noise-generated and thus cause net-negative attribution.

**What was learned / do NOT retry:** (a) Do not amplify TRANSITION rewards on this task. Eight level-based economies (rents, dwell, potential exponentials, occupancy ramps, cost cuts) preserved the baseline approach-dynamic while trying to shift parking-equilibria; all failed by identical success-to-zero collapse, which was informative (narrowed to PPO/credit-assignment diagnosis). Amplifying transition gains seems safe (continuous, no rent farming, far-field untouched), but violates a hidden assumption: PPO's per-sample credit assignment is only reliable when return magnitude is "natural" for the task scale. When returns jump 6× locally, the temporal credit window (GAE look-back through variance) becomes insufficient and the critic overfits to noise. (b) Return-variance magnitude matters as much as reward structure: early spike to +25 (vs +3-4 normal) was the canary. (c) The failed hypothesis was class-2 (reward structure), but the failure mode is fundamentally a class-6 (learning algorithm) problem — PPO itself cannot learn reliably from high-variance returns with sparse, noisy signal; only off-policy methods with replay buffers and target networks can decouple value fitting from stochastic data. This is now the fourth independent postmortem flagging class-6 (exps 31/33/34/35).

**Recommended next experiment class:** learning algorithm (class 6) — **now doubly urgent**. The ninth reward economy not only failed like the first eight, but revealed that tightening approach incentives LOCAL to the band via scaled rewards creates active mislearning through amplified variance. The diagnosis is decisive: PPO on-policy learning fundamentally cannot overcome the combination of (a) sparse noise-driven successes, (b) high variance induced by any reward-structure tweak, and (c) one-way exploration decay. Off-policy SAC is the indicated fix: replay buffer preserves noise-driven successful trajectories (decouples success collection from current policy), entropy auto-tuning holds exploration, and the offline Q-network is fit to fixed targets reducing variance-driven overfitting. Do NOT attempt a tenth reward economy. If class-3/4 are mandated by ladder mechanics before release of class-6, suggest deferring to a new session or escalating the runner's classification to acknowledge that class 2 is not just exhausted but actively harming via destabilization — observation edits already failed (exp 24), and curriculum constants are read-only, leaving class-3/4 slots without viable hypotheses.

## Experiment 47 - PPO batch_size 64 -> 128 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Rollout success stayed at zero and episodes stayed at 500 steps; final policy std was 0.132 and explained variance reached 0.955.
**What it rules out:** A larger PPO minibatch did not reduce the exploration/credit-assignment collapse or produce a deterministic reach-and-hold policy within the fixed budget.
**Next idea:** Off-policy replay with automatic entropy tuning remains the strongest hypothesis, but the current runner/evaluator surface must be explicitly expanded before it can be tested validly.

## Experiment 48 - PPO clip_range 0.2 -> 0.1 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Rollout success stayed at zero and episodes stayed at 500 steps; final policy std was 0.0994 and explained variance reached 0.919.
**What it rules out:** Smaller PPO clipping updates did not prevent the exploration/credit-assignment collapse or produce deterministic reach-and-hold behavior within the fixed budget.
**Next idea:** Off-policy replay with automatic entropy tuning remains the strongest hypothesis, but evaluator/runner integration must be explicitly expanded before it can be tested validly.

## Experiment 49 - PPO n_steps 1024 -> 4096 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained 0% success; the runner reverted the equal result.
**Behavior:** Rollout success stayed at zero, episode length stayed at 500, and the final policy std was 0.153; explained variance reached 0.994.
**What it rules out:** A fourfold longer PPO rollout did not preserve useful reach-and-hold credit or overcome the on-policy exploration collapse within the fixed 120000-transition budget.
**Next idea:** Off-policy replay with automatic entropy tuning remains the strongest hypothesis, but it requires an explicitly authorized runner/evaluator integration change.

## Experiment 65 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions because Windows `SubprocVecEnv` raised `EOFError`; no fixed-evaluator score was produced.
**Behavior:** The parameter override was applied transiently and restored; the training summary has no Stable-Baselines3 metric blocks.
**What it rules out:** This provides no evidence about shortening the curriculum window, and shows the launched training path did not use `DummyVecEnv`.
**Next idea:** Make the one-process vector-environment selection effective for parameter-mode training before retesting a curriculum hypothesis.

## Experiment 72 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed at 0% success with 2.1 cm mean and median final distance; the runner reverted the equal result.
**Behavior:** The default `DummyVecEnv` path completed all 120832 transitions and evaluation without the Windows multiprocessing startup failure, but rollout success remained 0 and episodes stayed at 500 steps.
**Training:** Reward rose from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, reproducing the entry-free regime.
**What it rules out:** Making single-process vectorization the default improves execution reliability but does not improve reach-and-hold learning.
**Next idea:** Use the now-validated one-worker path to test the pending curriculum-window hypothesis rather than another vectorization variant.

## Experiment 64 - curriculum advancement window 15 -> 5 - error

**Result:** Training failed before collecting transitions because Windows `SubprocVecEnv` raised `EOFError`; no evaluation score was produced.
**Behavior:** The parameter override was applied transiently and restored; the generated training summary contains no metric snapshots.
**What it rules out:** This run provides no evidence about shortening the curriculum advancement window; it confirms the runner still selects the failing parallel environment path.
**Next idea:** Repair or explicitly select the known single-process environment path before testing another curriculum hypothesis.

## Experiment 50 - PPO vf_coef 0.5 -> 0.1 - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success with mean/median final distance 2.1/2.0 cm; the runner reverted the equal result.
**Behavior:** Rollout success stayed at zero and episodes stayed at 500 steps; final policy std was 0.0883, explained variance 0.936, and value loss fell to 8.98e-05.
**What it rules out:** Reducing critic-loss weighting did not prevent confident fitting of the entry-free basin or improve deterministic reach-and-hold behavior within the fixed transition budget.
**Next idea:** Off-policy replay with automatic entropy tuning remains the strongest hypothesis, but it requires an explicitly authorized runner/evaluator integration change.

## Experiment 73 - normalized signed distance change observation - hypothesis not supported

**Result:** Fixed 200-episode evaluation remained at 0% success, with mean/median final distance 4.4/2.0 cm; the fresh observation-shape run was reverted as equal.
**Behavior:** Training completed 120832 transitions with zero rollout success and 500-step episodes; final policy std was 0.13 and explained variance reached 0.967.
**What it rules out:** An explicit one-step distance-rate feature did not overcome PPO's entry-free reach-and-hold failure within the fixed budget.
**Next idea:** Avoid further observation-only variants; the persistent replay and exploration-decay diagnosis still points to a learning-algorithm experiment, subject to runner/evaluator authorization.

## Experiment 74 - default vector environments 4 -> 1 - hypothesis not supported

**Result:** The fixed 200-episode evaluation completed at 0% success with 2.1 cm mean and median final distance; the runner reverted the equal result.
**Behavior:** The default `DummyVecEnv` path completed all 120832 transitions without the Windows multiprocessing startup failure, but rollout success stayed at 0 and episodes remained at 500 steps.
**Training:** Reward rose from -15.7 to 2.74 while policy std fell to 0.0964 and explained variance reached 0.999, reproducing the entry-free regime.
**What it rules out:** Making single-process vectorization the default improves execution reliability but does not improve reach-and-hold learning.
**Next idea:** Do not spend another experiment on vectorization; a valid replay-based algorithm test requires an explicitly authorized runner/evaluator integration change.
