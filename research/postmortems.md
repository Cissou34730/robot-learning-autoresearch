# Research postmortems

## ff836c6c-01b3-4764-9bf2-e4f349ac707b / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% success on the
official 200-episode reach-and-hold panel. The fresh unchanged PPO baseline
reached 89.5% on research evaluation and 92.0% on the reused task-reference
panel. Unchanged continuation produced the strongest development result,
96.5% (193/200), and the incumbent reproduced that result on the seed-2,
seed-3, and seed-4 research panels. The incumbent's seven failures recur at
the same target geometries: six in the 120-165 degree sector and one near
-103 degrees. The lower-rate transfer, fresh replication, focused-angle
coverage transfer, and explicit target-geometry representation all failed to
exceed the incumbent under their measured conditions. The current working and
best-known policy is therefore the unchanged-recipe incumbent at 96.5%,
which remains below the objective and lacks terminal-readiness evidence.
Experiment 7's 74.0% and 81.0% challengers on a matched fresh panel weaken
that representation result without showing that the added features are
intrinsically harmful. Experiment 8's two quadratic hold-credit challengers
also failed to exceed the incumbent: both scored 88.5% on a matched seed-1003
panel versus 92.0% for the incumbent, and each had 4 versus 11 paired wins.
This weakens the tested hold-credit explanation without establishing that
quadratic shaping is intrinsically harmful or that the incumbent's 96.5%
result generalizes unchanged to every panel. This synthesis is provisional
memory, not a prescribed direction.

**Lessons and limits:** Measured saved-policy success, not training reward or
proxy success, governs progress. Proxies are non-monotonic: continuation
improved before declining, the lower-rate run preserved stronger late proxies
without preserving task success, and the fresh replication improved reward
while remaining far below the incumbent. All detailed failures exhausted the
500-step horizon, and the incumbent generally approached the 1 cm threshold
without sustaining the required hold. The repeated positive-angle failures
are a coverage signal, not proof of a coverage cause; focused coverage did not
reduce them. The current reward already contains distance progress, a linear
hold-progress potential, an exit forfeiture, and a completion bonus
(`robot_learning/scenario/reward.py`), but reward shaping has not been
separated from representation, optimization trajectory, or mechanics. The
quadratic hold-credit run reached a proxy peak without saved-policy
improvement, and its measured challengers did not reduce the 120-165 degree
failure sector relative to the matched incumbent. Fresh training variability
is demonstrated by the 89.5% baseline and 83.0% replication, not characterized
as a seed distribution. Development measurements remain selection evidence
rather than the official verdict.

**Open questions:** It remains unknown whether the residual failures are
limited by temporal credit for completing the hold, state representation,
optimization trajectory, target coverage, or task mechanics. It is also
unknown whether another reward design or a different intervention can address
the residual failures; the tested quadratic hold profile did not. The
unmeasured experiment-7 checkpoints remain unmeasured, and no
terminal-readiness assessment has been established for the current best-known
designation.

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
