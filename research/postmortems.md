# Research postmortems

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 200-episode reach-and-hold panel. Unchanged PPO improved from the fresh
baseline's 89.5% to a best development result of 96.5% (193/200) after
continuation, and that incumbent reproduced 96.5% on the seed-2, seed-3, and
seed-4 panels while scoring 92.0% on seed-1004 and seed-1005 and 95.5% on
seed-1205. A fresh unchanged-PPO replication measured 88.0% and 90.5% at its
selected checkpoints on seed-1206, so the incumbent-level trajectory was not
recovered under the tested fresh seed. The incumbent's residual failures
include a recurring 120-165 degree sector pattern, low-radius concentration,
no-reach episodes, and tolerance interruptions, so angle and radius are signals
rather than complete explanations. Lower-rate transfer, the fresh replication,
focused-angle coverage, explicit target geometry, quadratic hold credit,
gamma-0.995 transfer, in-tolerance velocity penalization, and 6-10 cm
oversampling each failed to exceed the unchanged incumbent under the measured
conditions. Training proxies and reward remain unreliable indicators of
saved-policy success. The current working and best-known policy is therefore
meaningful development progress but remains below the objective and has no
terminal-readiness evidence.

**Lessons and limits:** Saved-policy task success, not training reward or proxy
success, governs progress. The strongest policy's measured failures exhaust
the 500-step horizon, and diagnostics mix no-reach and interrupted-hold
episodes; the evidence does not identify one sufficient failure mechanism.
Reward shaping, target coverage, representation, discounting, and the tested
stability penalty have each been weakened only under their particular recipes,
transferred trajectories, or panels, not universally disproven
(`research/postmortems.md`, Experiments 4 and 6-11). Fresh learning variance
is material: Experiment 1 reached 89.5%, Experiment 5 reached 83.0%, and
Experiment 12 reached 90.5%, while the incumbent's transferred policy was much
stronger across several evaluation panels (Experiments 1, 2, 5, 12). This
supports high variance under the tested seeds but does not estimate its
distribution or establish a universal failure of fresh training. Experiment 12
also shows that late proxy improvement can reduce no-reach failures while
increasing interrupted holds; this is a diagnostic association, not a causal
mechanism. Development measurements are selection evidence, not the official
verdict, and unmeasured checkpoints remain unmeasured.

**Open questions:** Experiment 12 weakens, but does not fully resolve, whether
fresh unchanged PPO can reproduce incumbent-level behavior; the result is one
additional seed with two measured checkpoints and 22 unmeasured checkpoints.
The residual failures may still involve temporal credit, control stability,
reachability, representation, target coverage, or task mechanics, and their
relative contributions are unknown. The recurring sector and low-radius
patterns may not generalize beyond the measured panels. The current best-known
designation also lacks terminal-validation evidence.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 1

**Result:** The baseline produced a useful but not objective-satisfying
policy. Checkpoint-120832 is selected as the working and best-known lineage.

**Observed behavior:** Training proxies improved late: training success rose
from 0.00 at step 100352 to 0.05 at 110592 and 0.11 at 120832, while mean
episode reward improved from -479.3 to -168.5. The latest checkpoint achieved
179/200 (89.5%) on the research-evaluation panel; the preceding measured
checkpoint achieved 171/200 (85.5%) under the same evaluation semantics,
an 8-episode / 4-point improvement. The paired comparison had 9 latest-policy
wins versus 1 predecessor win across 10 discordant episodes. On the fixed
task-reference panel, checkpoint-120832 achieved 184/200 (92.0%). Every
failure in both detailed outcome sets truncated at 500 steps rather than
terminating successfully.

**Hypothesis assessment:** Partially supported. The baseline's measurement
question was whether late proxy improvement transferred to uninterrupted
reach-and-hold success and whether the latest checkpoint surpassed the prior
late checkpoint. Both observations occurred on the matched research panel,
so the transfer and relative-improvement claims are supported under those
settings. The result does not support claiming that the policy satisfies the
human objective: 89.5% and 92.0% development measurements are below 98%,
and neither development panel is the official verdict. The task-reference
result is consistent with the research evaluation but uses a reused panel,
and no causal claim about training duration or failure geometry is warranted.

**Interpretation:** The latest checkpoint is the best evidenced available
candidate and represents meaningful progress toward the human objective, but
the remaining failures are too frequent for terminal assessment to be
scientifically useful now. The baseline recipe should be kept with this
checkpoint so a later experiment can target the residual failures; the
baseline itself establishes behavior, not reproducibility or a causal
explanation.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-1/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-110592-200ep-seed0-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/task-reference-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-1-checkpoint-120832-task-reference-v1.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 2

**Result:** Continuing the unchanged PPO recipe produced a useful
improvement, but did not establish the 98% objective. Checkpoint-100352 is
selected as the working and best-known lineage; checkpoint-120832 is retained
as a near-tied alternative.

**Observed behavior:** The continuation's training proxies peaked at
checkpoint-100352: training success was 0.95, mean reward was 329.1, and mean
episode length was 158. At checkpoint-120832 they were 0.87, 282.5, and 187.
On the matched 200-episode research panel with seed 1, checkpoint-100352
achieved 193/200 (96.5%) and checkpoint-120832 achieved 192/200 (96.0%).
The prior working policy achieved 179/200 (89.5%) under the same evaluation
semantics. All 7, 8, and 21 failures respectively exhausted the 500-step
horizon. Paired comparisons had 2 versus 1 discordant wins for
checkpoint-100352 versus checkpoint-120832, 15 versus 1 for
checkpoint-100352 versus the prior working policy, and 15 versus 2 for
checkpoint-120832 versus the prior working policy.

**Hypothesis assessment:** Partially supported. The prediction that unchanged
continuation could improve measured task behavior was supported: both measured
continuation checkpoints substantially exceeded the prior working policy on
the matched research panel. The prediction that later optimization would
continue reducing horizon-exhaustion failures was not supported by the
observed endpoint relative to checkpoint-100352: the endpoint had one more
failure and one fewer success. The proxy decline is evidence of a late
training change, but the one-panel, single-seed measurements do not establish
policy degradation or a plateau across the task distribution.

**Interpretation:** Training-time proxies and measured task success were not
monotonic: the proxy peak was the strongest measured policy, while the later
endpoint retained nearly the same task performance. The continuation therefore
validated additional useful progress from the retained representation under
these settings, without showing that extending the unchanged recipe past
checkpoint-100352 is beneficial. The 96.5% research measurement is meaningful
development progress but remains below the 98% human objective, and it is not
official terminal evidence. Retaining checkpoint-120832 preserves a plausible
near-equivalent branch for future development without treating the reused
task-reference panel or checkpoint ordering as a lineage criterion.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-2/inventory.json`;
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-2-attempt-1.log`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-checkpoint-100352-200ep-seed1-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-checkpoint-120832-200ep-seed1-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-2-working-200ep-seed1-a69293a214ad.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 3

**Result:** Further unchanged PPO continuation did not improve the incumbent
and produced lower-scoring measured checkpoints. The existing working lineage
remains the useful policy and best-known designation.

**Observed behavior:** The experiment-3 proxy peak at checkpoint-70656
(training success 0.99, reward 342.54) achieved 173/200 (86.5%) on the fresh
seed-2 research panel. The late proxy rebound at checkpoint-110592
(success 0.97, reward 335.33) achieved 179/200 (89.5%), and the endpoint
checkpoint-120832 (success 0.94, reward 318.24) achieved 172/200 (86.0%).
The retained working policy achieved 193/200 (96.5%) on that same seed-2
panel. The paired comparison between working and checkpoint-110592 had 15
working wins versus 1 checkpoint win. Every failure in these four measurements
truncated at the 500-step horizon.

**Hypothesis assessment:** Partially supported. The original prediction allowed
either further improvement or a plateau/degradation after checkpoint-100352.
No continuation checkpoint exceeded the incumbent, and the same-panel paired
result supports a policy-specific loss for checkpoint-110592 under these
evaluation conditions. The proxy peak and rebound did not transfer to higher
measured task success, weakening the continued-optimization branch. Because
the evidence is one seed-2 panel from one continuation trajectory, it does not
establish distribution-wide degradation or disprove that another recipe could
improve the remaining gap.

**Interpretation:** Experiment 3 provides measured evidence against selecting
its continued checkpoints over the incumbent, while preserving the earlier
96.5% policy as meaningful progress toward the 98% objective. Training proxies
were again orthogonal to saved-policy task success: the strongest proxy
checkpoint was not the strongest measured policy. The working lineage and its
unchanged recipe should therefore be kept for the next investigation; the
development evidence is not terminal evidence and does not justify requesting
the irreversible official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-3/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-70656-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-110592-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-checkpoint-120832-200ep-seed2-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-3-working-200ep-seed2-a69293a214ad.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 4

**Result:** The transferred lower-learning-rate recipe did not improve the
incumbent. The incumbent remains the working and best-known lineage, and the
experiment recipe is reverted.

**Observed behavior:** The lower-rate run's strongest training proxies were at
checkpoint-70656: training success 1.00 and mean reward 349.57. Its endpoint
checkpoint-120832 retained training success 0.97 and mean reward 329.10, but
both checkpoints were below the incumbent on saved-policy task measurement.
On the same 200-episode seed-3 research panel, checkpoint-70656 achieved
188/200 (94.0%), checkpoint-120832 achieved 171/200 (85.5%), and the working
policy achieved 193/200 (96.5%). The paired comparisons had 1 lower-rate win
versus 6 incumbent wins for checkpoint-70656 and 1 versus 23 for
checkpoint-120832. All 12 and 29 lower-rate failures, respectively, exhausted
the 500-step horizon. The other 22 experiment-4 checkpoints remain unmeasured,
not failed measurements.

**Hypothesis assessment:** Weakened. The lower-rate run retained higher
training-time proxies at its endpoint than the earlier unchanged-rate
endpoints, but it still declined from its own proxy peak, and neither measured
saved policy preserved the incumbent's 96.5% task success or reduced
horizon-exhaustion failures. The proxy preservation therefore did not support
the objective-relevant part of the hypothesis. This conclusion is limited to
one transferred trajectory and one research panel; it does not establish that
every lower learning rate is ineffective or that representation or task
coverage is the cause.

**Interpretation:** Measured task behavior, rather than the proxy peak, argues
against selecting the lower-rate candidates or keeping their recipe. The
incumbent's 96.5% result is meaningful progress toward the 98% objective but
is still development evidence below the target and is not terminal evidence.
The lower-rate intervention does not justify an official benchmark request.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-4/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-4-checkpoint-70656-200ep-seed3-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-4-checkpoint-120832-200ep-seed3-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-4-working-200ep-seed3-a69293a214ad.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 5

**Result:** The fresh replication did not reproduce the incumbent's learned
behavior. The existing working and best-known lineage remains the useful
policy; the unchanged scientific recipe is kept and the replication
checkpoints are not retained.

**Observed behavior:** The seed-4 training log reports training success of 0
at every logged point from 5,120 through 120,832 steps. Mean episode reward
improved from about -2,420 to -568.3, with the endpoint the run's best reward
proxy; the policy standard deviation also declined from 0.991 to 0.621. On
research evaluation, checkpoint-100352 scored 132/200 (66.0%) on seed 3 and
checkpoint-120832 scored 166/200 (83.0%) on seed 3. The endpoint also scored
166/200 (83.0%) on the independent seed-4 panel. The incumbent scored 193/200
(96.5%) on both seed-3 and seed-4 panels. Paired comparisons favored the
incumbent 64 to 3 against checkpoint-100352 and 33 to 6 against the
replication endpoint on the matched panel; the independent-panel comparison
also favored the incumbent 33 to 6 over 201 shared episode identities. Every
failure in these measurements truncated at the 500-step horizon.

**Hypothesis assessment:** Weakened. Under the tested fresh seed-4
trajectory, neither measured checkpoint reached the incumbent's approximately
96.5% development result or exceeded the prior fresh baseline range, and the
endpoint's large reward-proxy improvement did not transfer to comparable
saved-policy success. The independent seed-4 evaluation reproduced the
endpoint's 83.0% result, weakening the explanation that the matched seed-3
panel alone caused the gap. This is evidence about one replication trajectory
and does not estimate the full seed distribution, identify a causal mechanism,
or show that the unchanged recipe can never rediscover the incumbent regime.

**Interpretation:** Measured task success supports retaining the incumbent as
meaningful progress toward the 98% objective, but 193/200 remains below the
official 196/200 criterion and all these measurements are development
evidence, not the official verdict. The replication makes the incumbent's
saved-policy behavior more credible across evaluation panels while making the
learning process less reproducible under the tested seed. The unmeasured
replication checkpoints remain unmeasured rather than failed. No final
benchmark is requested because the selected policy is below the objective and
has no predeclared terminal-validation evidence.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`; `research/current_params.json`;
`research/research_state.json`;
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-5-attempt-1.log`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-5/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-5-checkpoint-100352-200ep-seed3-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-5-checkpoint-120832-200ep-seed3-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-5-checkpoint-120832-200ep-seed4-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-5-working-200ep-seed3-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-5-working-200ep-seed4-a69293a214ad.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 6

**Result:** Redirecting focused training coverage to 120-165 degrees did not
resolve the residual sector or exceed the incumbent. The working and
best-known lineages remain unchanged, and the focused-angle code change should
be reverted.

**Observed behavior:** Training proxies peaked at checkpoint-75776 with
training success 0.96 and mean reward 329.904, then declined to 0.89 and
283.051 at checkpoint-120832. Checkpoint-75776 measured 91.0% (182/200),
checkpoint-70656 measured 93.5% (187/200) on both seed-1000 and seed-1001
panels, and checkpoint-120832 measured 92.5% (185/200). The incumbent scored
92.0% (184/200) on both fresh panels. Each panel contained 30 episodes in the
120-165 degree sector: checkpoint-70656 failed 11 there, exactly matching the
incumbent; it had 2 failures outside the sector versus the incumbent's 5.
Checkpoint-75776 and checkpoint-120832 failed 11 and 12 sector episodes,
respectively. The detailed failures exhausted the 500-step horizon.

**Hypothesis assessment:** Weakened. The predicted reduction in targeted
120-165 degree failures and improvement above the incumbent's 96.5% development
result were not observed. Checkpoint-70656 did reproduce 93.5% on an
independent panel and showed fewer outside-sector failures than the incumbent
on the matched fresh panels, so the intervention produced a useful
objective-relevant signal under those panels. That signal is insufficient to
support selecting the candidate, and the single transferred trajectory does
not establish that the angle shift caused the outside-sector difference.

**Interpretation:** Measured task behavior, rather than the proxy peak, argues
against replacing the incumbent with an experiment-6 checkpoint. The exact
targeted residual count remained unchanged for the best challenger, while the
endpoint's lower proxy and 92.5% success again show that training proxies do
not determine saved-policy task behavior. The intervention weakens the tested
target-coverage explanation for the residual sector, but does not separate
coverage from representation, optimization trajectory, or task mechanics. The
incumbent remains meaningful progress toward 98%, but the development evidence
is below the objective and is not terminal evidence.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-6/inventory.json`;
`robot_learning/scenario/training_environment.py`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-checkpoint-75776-200ep-seed1000-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-checkpoint-70656-200ep-seed1000-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-checkpoint-70656-200ep-seed1001-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-checkpoint-120832-200ep-seed1000-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-working-200ep-seed1000-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-6-working-200ep-seed1001-a69293a214ad.json`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 7

**Result:** Adding explicit target radius and sine/cosine target-angle
features did not improve the measured saved policy. The experiment-7 recipe
should be reverted; the existing working and best-known lineages remain
unchanged.

**Observed behavior:** The added representation increased the observation
from 14 to 17 features while preserving the state, error, velocity, action,
reward, and task mechanics. Training proxies improved throughout the late
run: training success rose from 0.00 at step 90112 to 0.20 at step 120832,
mean reward improved from -361.89 to -125.85, and mean episode length fell
from 500 to 447. On the same fresh 200-episode research panel, checkpoint
115712 achieved 162/200 (81.0%) and checkpoint 120832 achieved 148/200
(74.0%), while the incumbent achieved 184/200 (92.0%). The incumbent had
25 versus 3 discordant wins over checkpoint 115712 and 39 versus 3 over
checkpoint 120832; checkpoint 115712 had 22 versus 8 discordant wins over
checkpoint 120832. The measured failures were horizon truncations: 38 for
checkpoint 115712, 52 for checkpoint 120832, and 16 for the incumbent. The
remaining 22 experiment-7 checkpoints were not measured.

**Hypothesis assessment:** Weakened. The experiment's question was whether
explicit target geometry would improve saved-policy reach-and-hold success
and whether the late proxy improvement would identify a useful checkpoint.
Neither measured challenger exceeded the matched incumbent, and the
strongest-proxy endpoint was worse than the preceding measured checkpoint.
This weakens both claims under the tested fresh trajectory and evaluation
panel. It does not establish that the features are intrinsically harmful:
the experiment changed the representation and fresh learning trajectory
together, only two challengers were measured, and the research panel is
development evidence rather than the official assessment.

**Interpretation:** Measured task behavior supports retaining the incumbent as
meaningful progress toward the 98% objective, but the experiment-7 candidates
do not support changing the working lineage or requesting the irreversible
official benchmark. The discrepancy between improving training proxies and
declining saved-policy success is an orthogonal signal consistent with the
campaign's earlier non-monotonic proxy behavior. The experiment does not
separate representation from optimization variability or explain the
incumbent's residual failures, so those questions remain open for a later
experiment.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-7/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-7-checkpoint-115712-200ep-seed1002-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-7-checkpoint-120832-200ep-seed1002-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-7-working-200ep-seed1002-a69293a214ad.json`;
`robot_learning/scenario/observations.py`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 8

**Result:** Quadratic hold-progress credit did not improve the measured saved
policy. The existing working and best-known incumbent remain selected, and
the reward-only experiment recipe should be reverted.

**Observed behavior:** The training log and candidate inventory show a proxy
peak at checkpoint-65536 (training success 1.00, mean reward 355.1 and mean
episode length 120), followed by a later proxy checkpoint at 105472 with
training success 0.98 and mean reward 339.3; the endpoint had training success
0.97 and mean reward 334.2. On the matched 200-episode seed-1003 research
panel, both measured challengers scored 177/200 (88.5%), while the incumbent
scored 184/200 (92.0%). Each challenger had 4 versus 11 discordant wins
against the incumbent, and the two challengers were tied at 10 versus 10.
All 23 challenger failures and all 16 incumbent failures truncated at 500
steps. The 120-165 degree sector contained 11 failures for checkpoint-65536,
10 for checkpoint-105472, and 11 for the incumbent.

**Hypothesis assessment:** Weakened. The diagnostic expected convex
hold-progress credit to produce fewer uninterrupted-hold failures and higher
saved-policy success, with the strongest result at either the proxy peak or
the later high-reward checkpoint. Neither challenger improved over the matched
incumbent, neither reduced the targeted sector failures, and the two proxy
choices had identical measured success. The result weakens the hold-credit
explanation under this transferred trajectory and panel, but does not show
that quadratic shaping is intrinsically harmful, establish a general
distribution-wide effect, or separate reward shaping from trajectory
variability.

**Interpretation:** Measured task behavior, rather than the stronger training
proxies, argues against selecting either experiment-8 candidate. The
quadratic profile did not provide objective-relevant progress, while the
incumbent remains meaningful progress toward 98% at its previously measured
96.5% and is still below the objective. The seed-1003 incumbent result is a
matched comparator, not evidence that the incumbent has degraded from its
earlier 96.5% panels. These development measurements are not terminal
evidence, so the experiment closes without requesting the official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-8/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-8-checkpoint-65536-200ep-seed1003-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-8-checkpoint-105472-200ep-seed1003-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-8-working-200ep-seed1003-a69293a214ad.json`;
`robot_learning/scenario/reward.py`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 9

**Result:** Increasing PPO gamma from 0.99 to 0.995 did not improve the
saved-policy task behavior. The incumbent remains the working and best-known
lineage, and the gamma change should be reverted.

**Observed behavior:** The gamma-0.995 training run reached training success
1.0 by step 68608. Its highest recorded mean reward was 353.746 at checkpoint
105472, with training success 1.0; the endpoint at step 120832 also had
training success 1.0 but lower mean reward 349.215. On the same fresh
200-episode seed-1004 research panel, checkpoint-105472 achieved 162/200
(81.0%), checkpoint-120832 achieved 156/200 (78.0%), and the incumbent
achieved 184/200 (92.0%). Paired comparisons favored the incumbent 26 to 4
against checkpoint-105472 and 32 to 4 against checkpoint-120832. The two
gamma checkpoints had 14 versus 8 discordant wins for checkpoint-105472
against checkpoint-120832. All 38, 44, and 16 failures respectively
truncated at the 500-step horizon. The research evaluator did not emit target
geometry, so this round did not directly measure the proposed 120-165 degree
sector.

**Hypothesis assessment:** Contradicted under the tested transferred
trajectory and matched panel. Neither gamma checkpoint improved saved-policy
success or reduced horizon-exhaustion failures relative to the incumbent, and
the lower endpoint result did not follow the training-proxy peak. This is
evidence against the tested gamma change under these conditions, not proof
that every discount change is ineffective or that temporal credit is unrelated
to the residual sector. The incumbent's 92.0% on this fresh panel is also not
evidence that its earlier 96.5% panels degraded; it is a matched-panel
observation with different episode coverage.

**Interpretation:** Measured task behavior supports keeping the incumbent as
meaningful progress toward the 98% objective, while the gamma intervention
does not provide a useful policy or recipe. The strong training proxies and
weak saved-policy results reinforce that proxy success and reward are
orthogonal to objective-relevant policy selection in this run. The result is
below the objective and lacks terminal-validation evidence, so no official
benchmark is requested.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-9/inventory.json`;
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-9-attempt-1.log`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-9-checkpoint-105472-200ep-seed1004-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-9-checkpoint-120832-200ep-seed1004-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-9-working-200ep-seed1004-a69293a214ad.json`;
`research/query_training_log.py`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 10

**Result:** The training-only in-tolerance end-effector velocity penalty did
not produce a replacement policy. The unchanged incumbent remains the working
and best-known lineage, and the experiment-10 reward and environment changes
should be reverted.

**Observed behavior:** The run completed 120832 steps. Training proxies peaked
at checkpoint-65536 with training success 1.00 and mean episode reward
-150.45; checkpoint-110592 had 0.98 and -166.18, checkpoint-115712 had 0.97
and -159.94, and the endpoint checkpoint-120832 had 0.95 and -204.36. On the
same 200-episode seed-1005 research panel, checkpoint-65536 achieved 185/200
(92.5%) versus 184/200 (92.0%) for the working policy, with 4 versus 3
discordant wins. Both had 11 failures in the 120-165 degree sector; the
challenger had 9 episodes with hold interruptions versus 7 for the incumbent,
and 15 versus 16 horizon-truncated failures. Checkpoint-110592 then achieved
162/200 (81.0%), with 4 versus 26 discordant wins against working, 13 sector
failures, and 34 interruption-bearing episodes. Checkpoint-115712 achieved
147/200 (73.5%), with 3 versus 40 discordant wins, 18 sector failures, and 35
interruption-bearing episodes. All measured challenger failures truncated at
the 500-step horizon. The other 21 candidates were not measured and remain
unmeasured, not failed measurements. No task-reference or official benchmark
measurement was made.

**Hypothesis assessment:** Weakened under the tested transferred trajectory and
seed-1005 panel. The proxy-peak checkpoint provided a small saved-policy
improvement and one fewer horizon failure, but it did not reduce the recurring
sector failures or interruption-bearing episodes. The intermediate and late
high-proxy checkpoints were substantially worse and showed that the endpoint
collapse was not isolated to one final checkpoint. This contradicts the
objective-relevant stability pattern expected by the proposal, while the
single transferred trajectory and development panel do not establish that all
velocity penalties or stability objectives are ineffective.

**Interpretation:** The measured policy result supports retaining the
unchanged incumbent as meaningful progress toward the 98% objective, but not
claiming that the objective is met: its strongest development result remains
96.5% (193/200), and the current matched panel result is 92.0% (184/200).
The strong and non-monotonic training proxies are orthogonal to saved-policy
selection here; reward totals are not used as cross-recipe policy evidence.
The velocity penalty did not resolve the hold-stability branch, so the
experiment recipe has no saved-policy or scientific-selection value. The
current best-known designation has no terminal-validation evidence and remains
below the objective, so the official benchmark is not requested.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-10/inventory.json`;
`research/training_logs/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-10-attempt-1.log`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-10-checkpoint-65536-200ep-seed1005-c47446effb50.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-10-checkpoint-110592-200ep-seed1005-c47446effb50.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-10-checkpoint-115712-200ep-seed1005-c47446effb50.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-10-working-200ep-seed1005-c47446effb50.json`;
`robot_learning/scenario/reward.py`;
`robot_learning/scenario/environment.py`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 11

**Result:** Oversampling the 6-10 cm training-radius band did not produce a
replacement policy. The unchanged incumbent remains the working and
best-known lineage, and the experiment-11 training-environment change should
be reverted.

**Observed behavior:** The run produced 24 checkpoints through 120832 steps.
Training proxies rose from 0.8966 success and 290.234 mean reward at
checkpoint-5120 to a proxy peak of 1.00 success and 348.103 reward at
checkpoint-95232, then fluctuated: checkpoint-100352 had 1.00 and 346.062,
while the endpoint had 0.99 and 343.943. Twenty-two checkpoints were not
measured and remain unmeasured, not failed measurements. On the same fresh
200-episode seed-1205 research panel, the proxy peak achieved 185/200
(92.5%), the endpoint achieved 175/200 (87.5%), and the incumbent achieved
191/200 (95.5%). The paired comparison recorded 5 versus 11 discordant wins
for checkpoint-95232 versus the incumbent, and 5 versus 21 for
checkpoint-120832 versus the incumbent.

The incumbent had 5 failures in the 6-10 cm band and 4 in the 10-20 cm band;
the proxy peak had 7 and 8, and the endpoint had 3 and 22. In the
120-165-degree sector, the incumbent and proxy peak each had 3 failures,
while the endpoint had 2; in the sector's 6-10 cm subset, the counts were 1,
1, and 0 respectively. Failure modes also shifted: the incumbent had 5
no-reach and 4 interruption-bearing failures, the proxy peak had 9 and 6,
and the endpoint had 2 and 23. The endpoint therefore showed a partial
low-radius signal but a large loss on 10-20 cm targets and many more
interruption-bearing episodes.

**Hypothesis assessment:** Weakened under this transferred trajectory and
seed-1205 development panel. The proxy peak did not reduce the recurring
sector failures or improve either radius band relative to the incumbent. The
endpoint had fewer low-radius failures and slightly fewer sector failures,
but lost substantially more 10-20 cm episodes and had much worse overall
reach-and-hold success. This does not establish that radial coverage is never
useful, but it weakens it as the actionable explanation for the current
objective gap under the tested recipe and shows that the training proxies do
not identify a useful saved-policy checkpoint here.

**Interpretation:** Measured task behavior supports retaining the incumbent as
the best available development policy, but it remains below the 98% objective
and has no terminal-validation evidence. The high and non-monotonic training
proxies are orthogonal to saved-policy selection in this experiment. The
endpoint's failure-mode shift toward interrupted holds leaves hold stability,
reachability, representation, and optimization trajectory unresolved; the
fresh panel is development evidence and is not the official benchmark.

**Evidence inspected:** `research/brief.md`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-11/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-11-checkpoint-95232-200ep-seed1205-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-11-checkpoint-120832-200ep-seed1205-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-11-working-200ep-seed1205-a69293a214ad.json`;
`robot_learning/scenario/training_environment.py`.

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Experiment 12

**Result:** The fresh unchanged-PPO replication did not reproduce the
incumbent-level saved policy. The existing working and best-known lineage
remains the useful development policy, the unchanged recipe is kept, and the
replication candidates are not retained.

**Observed behavior:** The fresh seed-6 run completed 120,832 steps and
produced 24 checkpoints. Training proxies improved through the measured run:
training success rose from 0.00 at early checkpoints to 0.41 at
checkpoint-100352 and 0.78 at checkpoint-120832, while mean reward rose from
-1969.7 to 72.5 and then 244.2. Twenty-two checkpoints were not measured and
remain unmeasured, not failed measurements. On the independent 200-episode
seed-1206 research panel, checkpoint-100352 achieved 176/200 (88.0%) and the
endpoint achieved 181/200 (90.5%). The paired comparison between these two
fresh candidates had 15 versus 10 discordant wins for the endpoint, a 2.5
percentage-point improvement.

Among failed episodes, checkpoint-100352 had 19 episodes with no recorded
first reach and 5 with hold interruptions; the endpoint had 9 no-reach and 10
interruption-bearing failures. The endpoint also had fewer failed episodes in
the 120-165 degree sector (2 versus 8) and the 6-10 cm radius band (12 versus
21), but more failed episodes in the 10-20 cm band (7 versus 3). These
diagnostic counts overlap where applicable and describe this panel only.
All failures in both measurements reached the 500-step horizon.

**Hypothesis assessment:** Weakened under the tested fresh seed and selected
checkpoints. The endpoint's proxy improvement transferred to a modest
saved-policy improvement over the fresh run's earlier checkpoint, but neither
checkpoint approached the incumbent's 193/200 (96.5%) development result.
This supports the alternative that the incumbent-level trajectory is not
reliably recovered from scratch under the current recipe, while the single
fresh seed and two measured checkpoints do not establish a seed distribution
or rule out a later unmeasured peak.

**Interpretation:** Measured task behavior supports retaining the incumbent as
meaningful progress toward the human objective, but the replication supplies
no replacement policy and does not meet the 98% objective. The late endpoint
is a partial and unexpected signal: its fewer no-reach and sector failures did
not yield incumbent-level success because interruption-bearing failures
increased. The proxy-to-policy gap and the failure-mode shift are diagnostic
associations; they do not identify whether optimization, control stability,
reachability, or another mechanism caused the outcome. The selected
development evidence is not terminal-validation evidence, so no official
benchmark is requested.

**Evidence inspected:** `research/brief.md`;
`research/results.jsonl`;
`research/research_state.json`;
`research/checkpoints/challengers/ff836c6c-01b3-4764-9bf2-e4f349ac707b/experiment-12/inventory.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-12-checkpoint-100352-200ep-seed1206-a69293a214ad.json`;
`research/evaluations/ff836c6c-01b3-4764-9bf2-e4f349ac707b/evaluation-ff836c6c-01b3-4764-9bf2-e4f349ac707b-experiment-12-checkpoint-120832-200ep-seed1206-a69293a214ad.json`.
