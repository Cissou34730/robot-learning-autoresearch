# Research postmortems

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Scientific strategy

**Current synthesis:** The objective is at least 98% official success on the
reach-and-hold task; only the unchanged PPO recipe (64x64 tanh, n_steps 1024,
ent_coef 0.01, trained on targets 14-20 cm from the base) has produced a
competent measured policy. Experiment 1 (`checkpoint-100352`, seed 0) measured
194/200 = 97.0% on the researcher panel and 196/200 = 98.0% on the protected
task-reference panel and is `working`/`best_known`; experiment 5, a seed-1
replication of the same recipe and budget, reached only 47.0%/49.5%, so
experiment 1's near-threshold level is one realized trajectory of a strongly
seed-sensitive learning process rather than a stable method property.
Re-analysing the experiment-1 researcher panel, all six residual failures are
folded-required targets whose elbow-open analytic inverse-kinematics branch lies
just outside the +/-170 degree shoulder range (about -176 to -181.5 degrees)
while the folded branch lies inside it and reaches the target exactly; the
failures span radii 8.0-19.5 cm and stall 0.81-1.42 cm outside the 1 cm
tolerance (five of six never enter it). A geometric check of each failure
compares the observed closest approach with the best reachable configuration
under the joint limits and with the exact folded solution: the policy comes
close to the best shoulder-pinned configuration and the folded solution is
essentially exact, i.e. it settles near the limit instead of adopting an
available feasible branch. The near-limit shell is roughly 3.9% of the 14-20 cm
training distribution, so the residual is not plausibly a sample-coverage gap,
and raising the folded-target sampling rate left folded failures unchanged
(experiment 2). Three interventions have failed to remove the band: full-radius
support with folded oversampling (experiment 2), zeroing the infeasible branch's
wrapped joint errors (experiment 3, which also collapsed the transferred
policy), and added per-branch joint-limit features at 13 dimensions (experiment
4, fresh, which underconverged). The failures therefore remain consistent with
the observation presenting the joint-infeasible open branch as an attractive
target, with an optimization or precision limit at the shoulder boundary
independent of that presentation, or with both; the campaign's tests do not
separate these.

**Lessons and limits:** Run-to-run variability of the unchanged method is
large: at the same 120k-step budget seed 0 reached 97.0%/98.0% while seed 1
reached 47.0%/49.5% and was still improving at the budget end, so single-run
measurements cannot establish a method property or attribute a change causally
(experiments 1, 5). Within experiment 1's seed-0 run the policy was strongest
near 100k steps (97.0%) and had degraded by 120832 (94.5%, with added
oscillation failures), so the useful level is a within-run transient rather than
a stable endpoint. A dimension-preserving edit to the values of the existing
IK-branch observation features is not semantically compatible with a transferred
policy: zeroing the infeasible branch's wrapped errors immediately dropped the
transferred policy to 71.0-74.0% and destroyed the open-only episodes (0/29)
while leaving both-feasible behavior intact, because a zero is itself a valid
"at goal" reading of a feature the policy had come to rely on (experiment 3).
Adding observation dimensions forces fresh training, and a fresh 120k run on the
13-dimensional observation underconverged (36.0-36.5%), so the fixed budget
cannot cleanly test an added-dimension representation (experiment 4). Folded
target oversampling at roughly six times the natural rate did not reduce folded
failures, but that run also changed the radius support and target draw order and
used transfer, so it does not isolate coverage (experiment 2). Training reward
does not track task success (163.85 at 0.42 training success versus 129.26 at
0.93) and is usable only as a shaped signal. All band evidence still rests on
the single seed-0 run: only about 6-14 episodes per
panel are involved, no joint trajectories are recorded, the position of the arm
during a stall is inferred from target geometry rather than observed, and every
mechanism claim remains scoped to that one run.

**Open questions:** Whether the residual near-limit band is caused by the
observation advertising a joint-infeasible open branch as an attractive target,
or by an optimization or branch-selection limit at the shoulder boundary
independent of that advertisement, is unresolved: experiments 3 and 4 each
tested a single encoding and were confounded by transfer collapse and
underconvergence respectively, so neither isolated the representation. It is
unknown whether a representation that presents only a joint-feasible target can
be learned within the fixed 120k-step budget, and whether such a policy would
remove the band or merely move the failure. The method's run-to-run distribution
is characterized by only two seeds, so whether any seed reliably reproduces the
97-98% level, and whether the band is seed-stable, is unknown. The folded-branch
solution is exact in joint space and statically reachable, but it is unknown
whether a continuous two-second hold through it is dynamically comfortable for a
learned controller, and how the learned observation normalizer couples the two
branches. It is also unknown why the seed-0 policy peaks near 100k steps and
then degrades.

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 1

**Result:** The fresh 120k-step baseline trained a policy that reaches 97.0%
(researcher panel) and 98.0% (task-reference panel) on the official
reach-and-hold task, with all residual failures localized to one angular wedge.

**Observed behavior:** 24 checkpoints were produced over 120,832 completed
training steps. Training-time success was 0 through 70,656, rose through
80,896 (0.17) and 86,016 (0.42), peaked at `checkpoint-100352` (0.97), and
settled at 0.93-0.95 for later checkpoints (105,472 to 120,832). Training
reward diverged from success, reaching 163.85 at 86,016 (0.42 success) and
129.26 at 95,232 (0.93). `checkpoint-100352` measured 194/200 = 97.0%
(research_evaluation, seed 20260918) and 196/200 = 98.0% (task_reference,
task-reference-v1); `checkpoint-120832` measured 189/200 = 94.5% on the same
research_evaluation seed and panel. On the shared 200-episode panel the two
checkpoints agreed on 189 successes and 6 failures; `checkpoint-120832` added 5
failures that `checkpoint-100352` did not have. All 6 failures of
`checkpoint-100352` had target angles -122.7, -154.6, -139.7, -135.3, -122.3
and -137.4 degrees (the 210-240 and 240-270 degree sectors) and all other 30
degree sectors had zero failures; 5 of the 6 never entered tolerance
(max_held_steps 0) despite minimum distances of 0.81-1.42 cm. The task-reference
failures had angles -116.4, -125.4, -122.9 and -127.9 degrees (all in one
sector) at target radii 6.7-9.9 cm, and the band [-130, -115] degrees failed
4 of 10 episodes while every other sector failed none. The 5 added
`checkpoint-120832` failures were of a different kind: two near angle 0
(-9.9 and -3.4 degrees) with one interruption each, and three with many
interruptions (30 to 244) whose reward totals were high (up to 138.4) - i.e.
oscillation across the tolerance boundary rather than a failure to arrive.

**Hypothesis assessment:** The automatic baseline carried no Researcher
proposal, so there is no explicit proposition to test; assessed against the
implicit expectation that the unchanged method learns the task, the expectation
is supported (success rose from 0% to 97% and the task-reference panel reached
98%), while the campaign threshold of >=98% on the official distribution is
only partially supported: the researcher panel places the estimate just below
it and the failure mode is systematic rather than random, so a 200-episode
official panel could sample the wedge and land below 98%. This assessment is
limited to two development panels and two measured checkpoints, and no causal
claim is made about the recipe.

**Interpretation:** The policy has learned the task almost everywhere but has a
reproducible directional blind spot in the lower-left angular wedge where it
converges just outside the 1 cm tolerance; that the minimum distances sit
barely above 1 cm suggests a coverage/precision deficit rather than an inability
to move into that region. Separately, the drop from 97.0% to 94.5% between
100,352 and 120,832 steps indicates the useful training peak is near 100k steps
and that later updates hurt hold stability. Neither observation can be
attributed to a specific recipe component because the recipe was unchanged.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-1/inventory.json, research/brief.md

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 2

**Result:** Training with the full 6-20 cm radius support and 30% folded-target
oversampling by transfer from `working` did not reduce the residual failures.
The best measured experiment-2 policy is slightly worse than its parent, so
`working` remains the best-known policy and the recipe change is reverted.

**Observed behavior:** Experiment 2 trained 120,832 steps (24 checkpoints,
checkpoint_every 5,000) from the `working` parent. Two checkpoints were
measured. `checkpoint-10240` scores 189/200 = 94.5% on the researcher panel
(seed 20260918, semantics 9bbd51019e5e) and 196/200 = 98.0% on
task-reference-v1; `checkpoint-120832` scores 188/200 = 94.0% and 194/200 =
97.0%. The parent `working` re-measured in the same context scores 191/200 =
95.5% on the researcher panel, and its task-reference result remains 196/200 =
98.0%. Paired on the shared 200-episode panel, `working` vs `checkpoint-10240`
has 2 discordant episodes, net -2 (exact p = 0.5); `working` vs
`checkpoint-120832` has 3 discordant episodes, net -3 (exact p = 0.25) - i.e.
the transfer checkpoints are equal-or-worse, not better. Recomputing the
elbow-open inverse-kinematics solution for every measured episode (shoulder or
elbow outside the +/-170 degree joint range) shows the failure set is still
almost entirely folded-required: on the experiment-2 panel, of 16 folded
targets, `working` fails 9 (7 succeed) while `checkpoint-10240` and
`checkpoint-120832` each fail 11 (5 succeed); `checkpoint-120832` additionally
fails one open-feasible target (episode 160, radius 16.4 cm, angle +19.5
degrees) that the parent reaches. On task-reference (13 folded targets of
200), `working` fails 4, `checkpoint-10240` fails 4 (episode 0 fixed, episode
100 added) and `checkpoint-120832` fails 4 (a different set). The
environment.py edit also reversed the target-sampler draw order (radius before
angle instead of angle before radius) while keeping the uniform official
distribution, so the seed-to-target mapping changed: the same `working`
artifact scores 194/200 under the experiment-1 panel (semantics 6ba3ba6d7654)
and 191/200 under the experiment-2 panel (semantics 9bbd51019e5e). This is a
panel-composition effect, not a policy change - its folded-target count rose
from 10 to 16. Exp-2 training-time success never exceeded the parent's 0.97; it
was 0.8846 at step 10,240 and 0.86 at 120,832, on the run's harder training
distribution.

**Hypothesis assessment:** Contradicted within the measured evidence. The
hypothesis predicted fewer folded-required failures than the parent's 6/200
(researcher) and 4/200 (task-reference) and pooled success moving toward or
beyond 98%, without new open-feasible failures. On a shared panel the
folded-required failures did not decrease (9 to 11 at both measured
checkpoints), overall researcher success fell (95.5% to 94.5%/94.0%) and
`checkpoint-120832` added one open-feasible failure - exactly the proposal's
stated contradicting observation, which favors the intrinsic-precision or
wrapped-solution-conflict alternative over a pure sample-count deficit. Limits:
only 2 of 24 checkpoints were measured; the paired differences are 2-3 episodes
(p = 0.25-0.5) over a 16-episode folded subset, so the evidence establishes
that this intervention produced no measurable improvement, not that the
mechanism is impossible; unmeasured checkpoints remain unmeasured, and the
two changed components (full-radius sampling, folded oversampling) are not
separated.

**Interpretation:** Oversampling the folded-required region at roughly six
times its natural rate, while also extending training to the full official
radius support, was not enough to move the residual failures; the transferred
policy if anything lost a small amount of hold stability, and a previously
clean open-feasible target began failing at the later checkpoint. The failure
mode stays a near-constant roughly 1 cm stall just outside the tolerance across
radii 6-19 cm, which is more consistent with a precision or solution-branch
limitation than with a region the policy has simply never sampled. Because the
parent still dominates every comparable measurement, the changed recipe is
reverted; the full-radius-coverage component cannot be credited or blamed in
isolation from this run and remains untested on its own.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-2-working-200ep-seed20260918-9bbd51019e5e.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-2-checkpoint-10240-200ep-seed20260918-9bbd51019e5e.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-2-checkpoint-120832-200ep-seed20260918-9bbd51019e5e.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-2-checkpoint-10240-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-2-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-2/inventory.json, research/results.jsonl, robot_learning/scenario/environment.py, robot_learning/robots/two_joint_arm.xml

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 3

**Result:** Gating the joint-infeasible inverse-kinematics branch's wrapped
joint-error features to 0.0 did not remove the near-limit band deficit and
collapsed measured success from the parent's 97.0% (researcher panel) and 98.0%
(task-reference) to 71.0-74.0% and 72.0%. The change is not useful, so the
working recipe is restored.

**Observed behavior:** Transfer from `working` trained 120,832 steps (24
checkpoints). Three checkpoints were measured on the researcher 200-episode
panel (seed 20260918, semantics 6ba3ba6d7654): `checkpoint-10240` 142/200 =
71.0%, `checkpoint-70656` 142/200 = 71.0%, `checkpoint-120832` 148/200 = 74.0%;
`checkpoint-120832` measured 144/200 = 72.0% on task-reference-v1. Paired on the
shared panel against `working`, every checkpoint loses net:
`checkpoint-10240` and `checkpoint-70656` are -52 (0 wins, 52 losses, exact p
~ 4.4e-16) and `checkpoint-120832` is -46 (0 wins, 46 losses, p ~ 2.8e-14). All
failures are 500-step truncations with negative reward - no arrival - not the
parent's just-outside-tolerance stall. Recomputing both analytic
inverse-kinematics branches for every measured episode splits the researcher
panel into 140 both-feasible, 29 open-feasible-only, 24 folded-feasible-only and
7 near-limit-band episodes. The parent succeeds 140/140, 29/29, 24/24 and fails
6/7 band; the gated checkpoints keep 140/140 (or 138/140 at `checkpoint-70656`)
on both-feasible episodes but fail 29/29 open-only, 22/24 then 20/24 then 16/24
folded-only, and 7/7 band. The independent task-reference panel reproduces the
split: both-feasible 135/135 for both models; open-only parent 31/31 versus
gated 0/31; folded-only parent 27/27 versus gated 9/27; band parent 3/7 versus
gated 0/7. The training log's `success_rate` is already 0.75 at the first logged
1,024 steps and never exceeds 0.81 over the run, so the transferred parent was
immediately ~70-75% under the changed observation and 120k further steps did not
recover it.

**Hypothesis assessment:** Contradicted. The hypothesis predicted the band would
improve from 1/7 toward the ceiling and total success would rise past the parent
while open-feasible and deep-folded behavior was preserved. Instead the band
stayed at 0-1/7 and success fell far below the parent. The proposal's own stated
contradicting observation flagged that unchanged band success with preserved
other behavior would favor the observation-independent precision-limit
explanation, and that new open-feasible failures would instead indicate the edit
damaged the learned representation; the observed collapse of the
single-infeasible-branch episodes is the latter, stronger outcome. Limits: only
3 of 24 checkpoints were measured (plus one task-reference), no joint
trajectories were recorded, and the tested encoding sets the infeasible branch's
errors to 0.0, which the policy can read as an already-satisfied branch; other
encodings of "suppression" (dropping the features, or adding an explicit
infeasibility flag) remain untested, so this is evidence about this
implementation, not about all possible branch gating.

**Interpretation:** The within-experiment contrast is sharp: on episodes whose
observation is unchanged (both branches feasible) the gated policy behaves like
the parent, while on episodes where either branch was gated it fails almost
always, even when the one retained branch is itself feasible. This indicates the
learned policy relies on the wrapped joint error of the near-infeasible branch
for those targets, so replacing it with a zero - which is itself a valid "at
goal" reading - removed signal the representation had come to depend on, rather
than merely removing one attractive distractor. The band, the parent's only
failure mode, gained nothing at all, which weakens the infeasible-branch
attraction explanation and is more consistent with a precision or optimization
limit at the shoulder boundary that is independent of the observation. This does
not establish that the representation is irrelevant; it shows the tested
suppression is harmful and leaves the band cause unresolved.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-3-checkpoint-10240-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-3-checkpoint-70656-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-3-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-3-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-3/inventory.json, research/results.jsonl, robot_learning/scenario/observations.py, research/brief.md

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 4

**Result:** A fresh 120k-step run that added two per-branch joint-limit-violation
features to `reach_observation` (OBSERVATION_SIZE 11 to 13) trained a policy far
below the baseline: 36.5% and 36.0% on the researcher 200-episode panel and 42.0%
on task-reference-v1, versus 97.0% and 98.0% for `working`. It repaired none of
the parent's failures, so the experiment-4 observation change is reverted and
`working` remains the selected policy.

**Observed behavior:** Two checkpoints were measured on the researcher panel
(seed 20260918, semantics 6ba3ba6d7654): `checkpoint-115712` 73/200 = 36.5% and
`checkpoint-120832` 72/200 = 36.0%; `checkpoint-120832` measured 84/200 = 42.0%
on task-reference-v1. Paired on the shared 200-episode researcher panel,
`checkpoint-120832` succeeds on 72 episodes against `working`'s 194: it adds 0
episodes `working` misses and loses 122 episodes `working` solves, while the 6
episodes neither solves are exactly `working`'s near-limit band failures. On
task-reference it likewise adds 0 exclusive successes and loses 112. Classifying
each researcher-panel target by analytic inverse-kinematics feasibility, 177
episodes are both-feasible (`working` 177/177, experiment 4 71/177), 13 are
open-feasible-only (13/13 versus 1/13) and 10 are folded-feasible-only / near-limit
band (4/10 versus 0/10). Experiment 4's 128 researcher-panel failures span all
angle sectors (42 with |angle| < 60 degrees, 28 in 60-120, 58 in 120-180); 60
never enter tolerance (max_held_steps 0, minimum distance above 2 cm), 47 stall
just outside tolerance and 21 are interrupted holds, whereas all 6 `working`
failures are in the 120-180 degree sector and are near-tolerance stalls or
interruptions with no no-arrival case. The raw training log shows success_rate
rising slowly from 0 at 70,656 steps to 0.49 at 120,832, with `ep_len_mean` still
falling (486 at 100,352 to 347 at 120,832) and reward 135 at 0.49 success; under
the same fresh, seed-0, 120k-step recipe, experiment 1 reached 0.97 training
success at 100,352 and 0.95 at 120,832 with reward 112. At the budget end
experiment 4's training-success curve is comparable to experiment 1 at roughly
90,000 steps.

**Hypothesis assessment:** Contradicted for the tested intervention. The
hypothesis predicted that explicit per-branch joint-limit feasibility would let a
fresh policy select the feasible folded branch, resolving the near-limit band and
moving overall success toward or above 98% with no new failures among
both-feasible or open-only targets. Instead the fresh run did not reach baseline
competence - the proposal's own stated contradicting observation - and it fixed
neither the band (0/10 and 0/13) nor any other episode, while failing broadly
including on both-feasible targets. Limits: only 2 of 24 research-panel
checkpoints plus one task-reference measurement were taken; the run's
training-success curve was still rising at the budget end; and with one fresh run
per recipe the slowdown cannot be causally attributed to the added features
rather than to optimization variance, so the band-specific representational
versus precision question is left unresolved rather than tested.

**Interpretation:** Adding the two joint-limit-violation features did not supply
a usable feasibility signal: no previously failing episode was repaired, and the
policy lost competence on the majority of both-feasible targets the baseline
solves. The comparison is comparatively controlled (both runs fresh, seed 0,
120,000 requested steps, identical algorithm and parameters, only the observation
differs), which makes the observation change a plausible cause of the slower
learning, but a single run cannot establish that causally. The measured success
below training success (0.36 versus 0.49) is consistent with a policy that was
still far from converged rather than with one specific failure mode, so this run
does not isolate the near-limit band cause. Whether a different feasibility
encoding, or simply more steps on this observation, would help remains untested.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-4-checkpoint-115712-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-4-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-4-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-4/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-1/inventory.json, research/results.jsonl, research/research_state.json, robot_learning/scenario/observations.py, robot_learning/robots/two_joint_arm.xml, training logs for experiments 1 and 4 (research/query_training_log.py).

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 5

**Result:** A fresh replication of the unchanged recipe at training seed 1 (120k
steps) reached only 30.5% at `checkpoint-100352` and 47.0% at
`checkpoint-120832` on the researcher panel, and 49.5% on task-reference-v1 at
`checkpoint-120832`, far below experiment 1's seed-0 97.0% and 98.0%. The seed-1
training curve was still rising at the budget end, so the run reads as much
slower learning rather than a distinct convergent failure mode. `working`
remains the only competent measured policy; no seed-1 checkpoint is retained.

**Observed behavior:** Experiment 5 was a `replication` of experiment 1 with
`training_seed` 1, fresh initialization, unchanged code (`code_changes` empty)
and parameters, 120,000 requested / 120,832 completed steps and 24 checkpoints.
On the researcher 200-episode panel (seed 20260918, semantics 6ba3ba6d7654):
`checkpoint-100352` 61/200 = 30.5% and `checkpoint-120832` 94/200 = 47.0%;
`checkpoint-120832` measured 99/200 = 49.5% on task-reference-v1. The raw log
shows success_rate 0 through 86,016 steps, 0.01 at 94,208, 0.04 at 100,352 and
0.13 at 120,832; `ep_len_mean` stays 500 through 86,016 and falls to 462 at
120,832, while `ep_rew_mean` rises from 24.9 (70,656) to 107.4 (120,832).
Experiment 1's seed-0 run instead reached training success 0.97 at 100,352 and
0.95 at 120,832 with reward 112-129, and measured 97.0%/98.0%. On the shared
researcher panel every one of experiment 5's 61 (100,352) and 94 (120,832)
successes is also an experiment-1 success: it adds 0 exclusive successes and
loses 133 and 100 of experiment 1's successes, and the 6 episodes neither policy
solves are exactly experiment 1's near-limit band. On task-reference it shares
98 successes, adds 1 exclusive success (episode 0, a band target at radius
6.7 cm, angle -116 degrees, where experiment 1 stalls 0.99 cm out) and leaves 3
shared failures. Experiment 5's 106 researcher-panel failures at
`checkpoint-120832` are all 500-step truncations with reward below 50 (no
arrival); none is a high-reward interrupted hold, whereas `checkpoint-100352`
had 6 such high-reward failures. On task-reference only 6 of its 101 failures
end within 2 cm of the target (the rest 2-40 cm away), and failures span sectors
-180 (19/19), -150 (13/17), 0 (2/13), 30 (5/13), 60 (9/11), 90 (15/15), 120
(24/24) and 150 (14/14) while sectors -120 through -30 succeed fully.

**Hypothesis assessment:** The proposal's hypothesis - that the near-limit-band
residual and the roughly 97% level are stable properties of the unchanged
learning method rather than of the seed-0 run - is contradicted within the
tested 120k-step budget: the seed-1 policy's success level is far lower and its
failure set is broad and angularly structured, predominantly a failure to
arrive, not concentrated in the near-limit band. This is the proposal's own
stated contradicting observation (a clearly different success level and a
failure set not concentrated in the band). Limits: the seed-1 training-success
curve was still rising and its episodes still lengthening at the budget end, so
the evidence establishes that experiment 1's level is seed-sensitive and not
reproduced at this budget, but it does not distinguish a lower seed-1 ceiling
from slower convergence, nor does it test the band against a converged seed-1
policy. Only 2 of 24 checkpoints plus one task-reference panel were measured,
and two training seeds are not a variance estimate.

**Interpretation:** Run-to-run variability of the unchanged method is large: on
the same recipe and budget, seed 0 measured 97.0%/98.0% while seed 1 measured
47.0%/49.5%, so experiment 1's near-threshold result is best read as one
favorable realized trajectory, not the method's expected performance. The
seed-1 failure profile is an undertraining signature rather than a narrow
precision deficit: failures are almost all failures to reach anywhere near the
target, they spread across the upper and rear angular sectors, and its successes
are essentially a subset of experiment 1's. Experiment 1's six-episode band is
unaddressed here (both policies fail those six), but with the seed-1 policy
still improving at the budget end this experiment cannot cleanly test whether a
converged seed-1 policy would exhibit the band. The gap between experiment 5's
training success (0.13) and its deterministic measured success (47.0%) at the
same checkpoint is recorded as an observation; it may reflect the stochastic
training policy and a marginal hold margin, but it is unexplained here. Prior
band-mechanism claims remain conditioned on the single seed-0 run, and the
primary practical uncertainty is now the stability of the learning process
itself.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-5-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-5-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-5-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-5/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-5/parameters.json, research/results.jsonl, research/research_state.json, research/brief.md, training log for experiment 5 (research/query_training_log.py).
