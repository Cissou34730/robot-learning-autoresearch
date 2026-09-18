# Research postmortems

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Scientific strategy

**Current synthesis:** The campaign objective is at least 98% official episode
success on the two-joint reach-and-hold task. The strongest measured policy is
still experiment 8's `checkpoint-120832` (`working` and `best_known`): 197/200 =
98.5% on the protected task-reference panel and 194/200 = 97.0% on the researcher
panel, with a persistent six-episode researcher wedge {7, 56, 64, 75, 107, 145}
at rear angles -122 to -155 degrees and radii 8.0-19.5 cm. Ten experiments have
not moved it. Re-inspecting the experiment-9 joint-margin diagnostics reframes
the wedge: on the researcher panel 10 targets have a joint-infeasible open branch
and a feasible folded branch, yet at the closest-approach step the elbow is
positive (open sign) in every one of the 200 episodes and no episode ever reaches
tolerance with a folded (negative-elbow) posture; within the band the four
successes and six failures separate by how far the shoulder is pressed past the
nominal +/-170 degree limit (successes at 170.5-172.7 degrees, failures at
173.3-174.1 degrees). The residual therefore reads less like a branch-selection
error than like a soft joint-limit reach-and-precision wall the controller leans
on. Inference, not measurement: PPO's advantage estimator has an effective
horizon of roughly 1/(1 - gamma*lambda) ~ 17 steps at the active gamma=0.99,
lambda=0.95, while the candidate escape (a 60-110 degree shoulder reconfiguration
followed by a 100-step hold) is much longer, so a myopic estimate need not credit
it; this is consistent with two opposite near-limit signals (experiment 9's
penalty, experiment 10's folded-branch guidance) changing trajectories and the
protected failure set without moving deterministic outcomes. Method variance
remains large (seed 0: 97.0-98.5%; seed 1: 47.0-49.5%), so the near-threshold
level is one realized trajectory rather than a stable method property, and no
completed intervention has exceeded the seed-0 policy.

**Lessons and limits:** Full-radius coverage by transfer did not repair the
wedge (net +1 on task-reference, researcher failure set unchanged; experiment 8),
so it is not a region the policy never sampled. Editing occupied observation
slots is semantically incompatible with a transferred policy: writing 0.0 into,
or mirroring a feasible branch into, the infeasible branch's wrapped-error slots
keeps both-feasible behavior but collapses single-branch targets (experiments 3,
6), so unchanged tensor dimensions alone do not establish compatibility. Adding
observation content forces fresh training, and fresh 120k-step runs on altered
11- or 13-dimensional observations underconverged (experiments 4, 6), so the
fixed budget cannot cleanly test an added-dimension representation. A globally
tightened success tolerance degrades a competent transferred policy and erases
its fragile 6-14 cm generalization (experiment 7), and folded-target oversampling
was confounded with radius-support and draw-order changes (experiment 2). A weak
per-step joint-limit proximity penalty (experiment 9) and folded-branch
wrapped-error guidance (experiment 10) both fired on the actual failure states
yet left the deterministic failure set and success level unchanged, so those
signal magnitudes did not move the argmax policy. Run-to-run variability is large
(seed 0: 97.0%/98.0%; seed 1: 47.0%/49.5% at the same budget), so single runs
cannot establish a method property or attribute a change causally (experiments 1,
5). Training reward does not track task success (experiments 1, 7). All wedge
evidence rests on a few episodes per panel (about 3-14), every mechanism claim is
scoped to the seed-0 lineage, and the direct joint-posture evidence comes from
one diagnostic round on the experiment-9 endpoint and its parent.

**Open questions:** Whether the wedge is a myopic credit-assignment limit that a
longer effective planning horizon would relax, or a soft-limit reach-and-
precision limit independent of the horizon, is unresolved. Whether the folded
basin - which the policy never enters at closest approach - is learnable at all
within the fixed budget, and whether being exposed to it would change the
deterministic outcomes, is unmeasured. Whether a fresh policy trained on the full
official support from the start would place its branch boundary differently from
the transfer-inherited one is open. The method's run-to-run distribution is
characterised by only two seeds, so whether any seed reliably reproduces the
97-98% level, and whether the wedge is seed-stable, is unknown. It is also
unknown why the seed-0 policy peaks near 100k steps and then degrades, and
whether a continuous two-second hold at the limit posture is dynamically
comfortable for a learned controller.

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

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 6

**Result:** A fresh, seed-0 run whose only change mirrored the joint-feasible analytic
inverse-kinematics branch into the infeasible branch's observation slots (11
dimensions, no other change) measured 110/200 = 55.0% on the researcher panel and
101/200 = 50.5% on task-reference-v1, far below `working`'s 97.0%/98.0% and with
zero exclusive successes. The folded-required band was not repaired (0/31) and
single-branch targets collapsed (0/29 open-only, 0/31 folded-only). The mirrored
recipe is not useful, so `working` remains the selected policy and the
`observations.py` change is reverted.

**Observed behavior:** Experiment 6 was a diagnostic fresh `training` run, seed 0,
120,000 requested / 120,832 completed steps, 24 checkpoints, with the only code
change in `robot_learning/scenario/observations.py`: adding `JOINT_LIMIT` and,
when exactly one analytic branch is joint-feasible, copying the feasible branch's
shoulder/elbow angles into the infeasible branch's slots before computing the four
wrapped joint errors; `OBSERVATION_SIZE` stayed 11, and both-feasible and
neither-feasible episodes kept their existing observation. One checkpoint was
measured: `checkpoint-120832` scored 110/200 = 55.0% on the researcher panel
(seed 20260918, semantics 6ba3ba6d7654) and 101/200 = 50.5% on task-reference-v1.
Paired on the shared 200-episode researcher panel against `working`
(`checkpoint-100352`, experiment 1): 0 episodes where experiment 6 succeeds and
`working` fails, 84 where `working` succeeds and experiment 6 fails, 110 both
succeed, 6 both fail (net -84, exact p ~ 1.0e-25). On task-reference the pairing is
0 exclusive / 95 lost / 101 shared / 4 both fail. Recomputing both analytic IK
branches for every researcher-panel target splits it into 140 both-feasible, 29
open-feasible-only and 31 folded-feasible-only episodes. Experiment 6 succeeds on
110/140 both-feasible but 0/29 open-only and 0/31 folded-only; `working` succeeds
on 140/140, 29/29 and 25/31 respectively. Every experiment-6 success therefore
falls on an episode whose observation the edit leaves unchanged, and it fails all
60 single-branch episodes. Its 90 failures are dominated by non-arrival: 81 never
enter the tolerance (`max_held_steps` 0) with minimum distances mostly 1.5-4.6 cm,
and 9 enter and are interrupted; the six episodes `working` misses (all
folded-only) are failed at minimum distances 2.65-4.61 cm with `max_held_steps` 0,
i.e. no arrival rather than `working`'s near-limit stall. The raw log shows
`success_rate` 0 through 96,256 steps, 0.03 at 97,280, 0.04 at 100,352, 0.08 at
105,472, 0.13 at 106,496, 0.20 at 110,592, 0.34 at 114,688-115,712 and 0.46 at
120,832, with `ep_len_mean` falling 500 to 357 and `ep_rew_mean` rising from ~116
to ~131 over the same span - still improving at the budget end. For comparison,
experiment 1 (same fresh seed-0 unchanged recipe) reached training success 0.97 at
100,352 and 0.95 at 120,832, while experiment 5 (unchanged seed 1) reached 0.04 at
100,352 and 0.13 at 120,832 and measured 47.0%; experiment 6 is roughly 60-80k
steps behind experiment 1 and modestly ahead of experiment 5 (paired: experiment 6
adds 38 episodes and loses 22).

**Hypothesis assessment:** Contradicted for the tested intervention, with the
underlying diagnostic left inconclusive. The proposal predicted a fresh
canonicalized policy would reach baseline competence, solve most folded-required
band targets, and raise researcher success toward or above 98% while leaving
both-feasible and open-only outcomes essentially unchanged. Observed instead: no
baseline competence (55.0%/50.5%), no band repair (0/31 folded-only, and
`working`'s six band failures remain failures), and a collapse rather than
preservation of open-only episodes (0/29). This is precisely the proposal's stated
contradicting observation - a run that underconverges broadly with no
band-specific improvement - which favors the optimization/precision alternative
over the representation-attraction proposition, and it weakens the case that
presenting only a joint-feasible branch redirects the policy. Limits: the training
curve was still rising steeply and episodes still lengthening at the budget end,
so the run never reached the competence at which the band question could be
cleanly tested; the representation-versus-optimization diagnostic therefore
remains unresolved. Only 1 of 24 checkpoints plus one task-reference panel were
measured, the run is a single fresh seed-0 trajectory, and its measured level sits
between the two characterized unchanged seeds (seed 0 97.0%, seed 1 47.0%), so the
causal attribution of the level to the mirroring edit is not established by this
run; only the within-policy failure structure is directly observed.

**Interpretation:** Within the fixed 120k-step budget the mirrored representation
did not provide a usable target signal. The within-policy contrast is sharp: the
policy succeeds only where the edit did not touch the observation (both-feasible
episodes) and fails every episode where one branch was infeasible, including the
29 open-only episodes that are otherwise easy. This parallels experiment 3, where
setting the infeasible branch's wrapped errors to 0.0 also left both-feasible
behavior intact while collapsing open-only episodes (0/29). Two different edits to
the same infeasible-branch slots - one to zero, one to a copy of the feasible
branch - both break single-branch targets and neither repairs the band, which
suggests the learned controller depends on the distinct per-branch wrapped-error
signal and that remapping the infeasible slot is not a viable route to the band.
Because this run never converged, these structural observations are confounded
with undertraining and do not establish the band's cause or show the mirrored
representation to be harmful in principle. The mirrored recipe is reverted and no
experiment-6 artifact is retained.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-6-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-6-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-5-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-6/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-6/parameters.json, research/results.jsonl, research/brief.md, robot_learning/scenario/observations.py, training log for experiment 6 (research/query_training_log.py).

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 7

**Result:** Transfer from `working` with a tighter 7 mm training success-and-hold
tolerance repaired none of the residual near-limit band and measured lower
official-tolerance success at every measured checkpoint (`checkpoint-50176`
181/200 = 90.5%, `checkpoint-100352` 168/200 = 84.0%, `checkpoint-120832`
157/200 = 78.5% on the researcher panel; `checkpoint-120832` 162/200 = 81.0% on
task-reference-v1), all strictly below `working`'s 97.0%/98.0%. The tolerance
recipe is reverted and `working` remains the selected policy.

**Observed behavior:** Experiment 7 was a diagnostic `training` run, transfer
from `working`, seed 0, 120,000 requested / 120,832 completed steps and 24
checkpoints. The only code change added
`robot_learning/scenario/training_environment.py` (`TRAINING_SUCCESS_THRESHOLD =
0.007`, unchanged 14-20 cm radius support) and pointed `robot_learning/train.py`
at it; the environment class, 11-dimensional observation, PolicyIO, action
space, reward form and PPO parameters were unchanged, and `make_evaluation_env`
plus the protected benchmark kept the official 10 mm tolerance. On the
researcher panel (seed 20260918, semantics 6ba3ba6d7654) the three measured
checkpoints scored 90.5%, 84.0% and 78.5%; on task-reference-v1 the endpoint
scored 81.0%. Paired against `working` on the identical panels, no measured
experiment-7 checkpoint added a single exclusive success: net -13, -26 and -37
on the researcher panel and -34 on task-reference, and the episodes both
policies miss are exactly `working`'s 6 researcher-panel and 4 task-reference
failures. The four task-reference band failures of `working` (episode 0 r 6.73 cm
a -116.4 degrees; episode 10 r 7.24 cm a -125.4 degrees; episode 84 r 9.91 cm
a -122.9 degrees; episode 102 r 9.36 cm a -127.9 degrees) all remain failures,
and episodes 10 and 102 now terminate 16.3 cm and 19.6 cm from the target instead
of `working`'s 0.99-1.33 cm stalls. Every experiment-7 task-reference failure has
target radius at most 10.26 cm; all 23 targets at 12-14 cm and all 95 at 14-20 cm
succeed, and the failures span all angular sectors (-177 to +117 degrees).
`working` fails 4/31 at r 6-8 cm and 2/26 at r 8-10 cm; experiment 7 fails 27/31
and 10/26 in the same bins, while `working`'s 4 failures are confined to -115 to
-128 degrees. The 7 mm training proxy saturated early and stayed high (0.97 at
`checkpoint-50176`, 0.94 at `checkpoint-100352`, 0.98 at `checkpoint-120832`)
while official-tolerance success declined monotonically with further training,
and on the trained 14-20 cm support experiment 7 succeeds on 95/95
task-reference targets, so the proxy/measured gap tracks the untrained
inner-radius region rather than a proxy inconsistency. On the 162 shared
task-reference successes, experiment 7 terminates at larger final distances than
`working` (mean 0.49 versus 0.31 cm) and 31 versus 5 terminate between 7 and
10 mm, so its successful holds are not deeper despite the tighter training
tolerance.

**Hypothesis assessment:** Contradicted. The proposal predicted that the 7 mm
tolerance would make the policy reach inside the band, repair the folded-required
near-limit failures and lift success toward or above 98% while leaving
already-deep episodes unchanged. Observed instead: a strict subset of the
parent's successes (0 exclusive wins), success fell 6.5-19.5 points on the
researcher panel and 17 points on task-reference, and the band was not repaired -
the proposal's own stated contradicting observation. This supports the stated
alternative that the residual band is not a tolerance or precision-magnitude
limit and that forcing tighter holds degrades the competent representation.
Limits: the transferred run also lost competence broadly on every target with
radius below the 14 cm training minimum, and the four band targets (r 6.7-9.9 cm)
lie inside that same untrained region, so the band-specific claim is confounded
by the general inner-radius regression and remains inconclusive; only 3 of 24
checkpoints plus one task-reference panel were measured, and one seed-0 transfer
run cannot causally attribute the success level to the tolerance change beyond
the observed strict-subset dominance.

**Interpretation:** The tighter training tolerance changed the reward's hold
condition - hold progress and termination require the end effector within 7 mm,
and the outside-band penalty is scaled from that threshold - so within the
trained 14-20 cm support the finetuned policy still holds, while it lost the
parent's generalization to the untrained 6-14 cm radii and became a strict subset
of the parent. The residual near-limit band lives inside that unsampled inner
region (task-reference radii 6.7-9.9 cm), so this run masks the band behind a
broad inner-radius regression rather than testing it: the curriculum neither
confirms precision as the band's cause nor delivers a usable policy. That the
successful holds are not deeper, and that the high 7 mm proxy coexists with low
official success, argue against a simple precision-gain mechanism. Because
`working` dominates every comparable measurement and no experiment-7 checkpoint
offers a better continuation base, the tolerance change is reverted,
`working`/`best_known` stay selected, and no experiment-7 artifact is retained.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-7-checkpoint-50176-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-7-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-7-checkpoint-120832-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-7-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-200ep-seed20260918-6ba3ba6d7654.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-7/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-7/parameters.json, research/results.jsonl, research/brief.md, robot_learning/scenario/training_environment.py, robot_learning/scenario/environment.py, robot_learning/scenario/reward.py, robot_learning/train.py

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 8

**Result:** Full-radius training by transfer from `working` left the researcher
panel exactly unchanged (194/200 = 97.0% at both measured checkpoints, with the
parent's identical six failures) and raised the protected task-reference panel
from 196/200 = 98.0% to 197/200 = 98.5% at the endpoint, repairing the two
smallest-radius task-reference failures (episodes 0 and 10) while adding one new
failure at 18.2 cm (episode 175). The full-radius recipe is kept and
`checkpoint-120832` is the strongest measured policy.

**Observed behavior:** Experiment 8 was a diagnostic transfer `training` run from
`working`, seed 0, 120,000 requested / 120,832 completed steps, 24 checkpoints;
the only change was `TRAINING_TARGET_RADIUS_RANGE` in
`robot_learning/scenario/environment.py` from (0.14, 0.20) to the official
(0.06, 0.20). Training-time success was 0.93 at 10,240 and stayed 0.94-1.0 for
the rest of the run (1.0 at 105,472, 0.94 at the 120,832 endpoint), reflecting
immediate competence on the harder distribution, while `ep_len_mean` rose from
124 (105,472) to 149 (120,832). On the researcher 200-episode panel (seed
20260918, semantics ffdccdbf3357) the re-measured parent `working` and both
measured checkpoints all score 194/200 = 97.0% and fail exactly the same six
episodes {7, 56, 64, 75, 107, 145}; the paired comparisons are 0 candidate wins,
0 losses and 0 discordant episodes for both checkpoints against `working`. Those
six failures are the familiar rear wedge (angles -122.3 to -154.6 degrees) at
radii 7.99-19.47 cm, and four of them (r 13.97, 14.92, 15.96 and 19.47 cm) lie
inside the trained 14-20 cm support. On task-reference-v1 the parent scores
196/200 = 98.0% (failures 0, 10, 84, 102), `checkpoint-105472` scores 196/200 =
98.0% (failures 0, 84, 102, 175) and `checkpoint-120832` scores 197/200 = 98.5%
(failures 84, 102, 175). The transfer therefore repaired the two smallest-radius
inner-band failures (episode 0, r 6.73 cm, a -116.4 degrees; episode 10, r 7.24
cm, a -125.4 degrees) by the endpoint, but added episode 175 (r 18.24 cm,
a -154.8 degrees, inside the trained support) and left the r 9.4-9.9 cm wedge
failures 84 and 102 unrepaired. All measurements are single deterministic
200-episode panels.

**Hypothesis assessment:** Partially supported, with the radius-coverage
mechanism weakened for the residual wedge. The proposal predicted that covering
the official 6-20 cm radius support would repair folded-required inner-radius
failures, especially the four task-reference failures at 6.7-9.9 cm, raise
success toward or above 98%, and add no failures at the trained 14-20 cm radii.
Observed: two of the four task-reference inner-band failures were repaired and
task-reference success rose above the 98% objective to 98.5%, but the researcher
panel was exactly unchanged at 97.0% with the identical failure set - including
its own inner-radius failures at r 7.99 and 8.74 cm - and one new failure was
added at r 18.24 cm inside the trained support, which is the proposal's stated
contradicting condition. The prediction of a radius-coverage repair is thus
supported on one panel and only at the two smallest radii, and the prediction of
no added trained-radius failures is contradicted. Limits: the two measured
checkpoints are the run's plateau and endpoint (22 of 24 unmeasured); the
task-reference gain is a net +1 episode (2 repaired, 1 added) on one fixed
200-episode panel, within single-episode noise; and `working` and both
experiment-8 checkpoints are indistinguishable on the researcher panel, so no
within-run checkpoint effect is established there.

**Interpretation:** Exposing the transferred policy to the full official radius
support changed almost nothing about the residual failure structure. On the
researcher panel the policy is behaviorally identical to its parent at both the
proxy-best plateau and the endpoint, and the persistent failures include targets
well inside the trained 14-20 cm support, so the wedge cannot be explained by the
untrained inner-radius band. The task-reference improvement is real but thin and
not spatially systematic: it repairs two targets at r 6.7-7.2 cm while leaving
the r 9.4-9.9 cm wedge failures, adding a failure at r 18.2 cm, and leaving the
researcher-panel inner-radius failures at r 7.99 and 8.74 cm untouched. This is
most consistent with a small, idiosyncratic reallocation of the decision
boundary rather than a radius-coverage mechanism, and it strengthens the
branch-selection/precision interpretation of the wedge. The full-radius recipe is
nevertheless safe and semantically aligned with the official task, so it is
kept; it does not by itself move the official-distribution estimate toward the
98% objective, and the next investigation should target the angular/branch
selection residual rather than radius coverage.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-working-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-105472-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-105472-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-1-checkpoint-100352-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-8/inventory.json, research/results.jsonl, research/brief.md, robot_learning/scenario/environment.py, training log for experiment 8 (research/query_training_log.py)

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 9

**Result:** A training-only per-step joint-limit proximity penalty, applied by
transfer from `working`, left the researcher panel exactly unchanged (194/200 =
97.0% with the parent's identical six failures {7, 56, 64, 75, 107, 145} at
20,480, 100,352 and 120,832 steps) and tied the protected task-reference panel
(197/200 = 98.5%, failures {84, 102, 175}). Newly recorded joint-margin
diagnostics show the penalized state is actually reached: every wedge failure
drives the closest joint 3.3-4.1 degrees past the +/-170 degree limit and incurs
the maximum 0.05 per-step penalty, yet no outcome changes. The reward change is
reverted and `working` (experiment 8 `checkpoint-120832`) remains the selected
policy.

**Observed behavior:** Experiment 9 was a diagnostic transfer `training` run
from `working`, seed 0, 120,000 requested / 120,832 completed steps, 24
checkpoints. The only change added a per-step joint-limit proximity term to
`robot_learning/scenario/reward.py` (soft 6-degree margin, `JOINT_LIMIT_PENALTY =
0.05`, summed over the two joints, saturating linearly) and passed the current
joint positions from `robot_learning/scenario/environment.py`; observation,
PolicyIO, action space, environment class, success and hold semantics, PPO
parameters and the protected benchmark were unchanged. Training-time success was
0.99 at 20,480 and 0.97 at 120,832, `ep_rew_mean` 113.38 at 20,480 and 103.23 at
120,832. On the researcher panel (seed 20260918, semantics 9ea08384b3a2) all
three measured checkpoints score 194/200 = 97.0% and fail exactly {7, 56, 64, 75,
107, 145}, the parent's failure set. On task-reference-v1 the endpoint scores
197/200 = 98.5% (failures {84, 102, 175}), identical to the experiment-8
endpoint. A second measurement round added per-episode joint-limit diagnostics
(semantics 6db0b3ca786d) for the experiment-9 endpoint (fingerprint 29e91fb8) and
the parent (fingerprint a1ed461); both score 97.0% with the same six failures.
For every failure, the maximum absolute joint angle over the episode is 173.0-174.1
degrees, i.e. 3.3-4.1 degrees beyond the +/-170 limit (`min_joint_margin_degrees`
-3.28 to -4.07), and `max_joint_limit_penalty` saturates at 0.05. Across the
panel the parent exceeds the limit on 11/200 episodes and enters the 6-degree
margin on 15/200; all 6/6 failures and 9/194 successes incur the penalty. The
endpoint exceeds the limit on 11/200, enters the margin on 16/200, and has 6/6
failures and 10/194 successes incurring the penalty. Endpoint and parent
trajectories differ slightly at the failures (for example episode 56 minimum
distance 1.51 versus 1.69 cm, episode 145 0.52 versus 0.63 cm) but no episode
changes outcome.

**Hypothesis assessment:** Weakened, and the proposal's own stated contradicting
observation was observed. The proposal predicted that a per-step penalty on
joint-limit proximity would move the deterministic policy off the shoulder stall
onto the feasible folded branch - researcher panel above 194/200, the six wedge
episodes entering tolerance, no new failures, task-reference not below 197/200 -
and named the alternative that the wedge is an optimization or precision limit
at the shoulder boundary independent of the stalled configuration. Observed: the
penalty's target state is genuinely reached and fully penalized (6/6 failures,
margin negative, penalty saturated), the failure set and success level are
bit-identical to the parent on both panels at three checkpoints spanning early,
proxy-plateau and endpoint steps, and only small trajectory perturbations
distinguish the transferred policy. This refutes the "penalty never touches the
stall" explanation and leaves the optimization/precision alternative standing.
Limit: exactly one penalty magnitude and shape was tested (linear, saturating at
0.05 per step, far smaller than the progress coefficient 10, closeness 4 and
hold bonuses 50), so the result establishes the insufficiency of this signal, not
that joint-limit behaviour is irrelevant; all evidence is three deterministic
200-episode panels on the single seed-0 lineage.

**Interpretation:** The experiment separates two explanations the earlier
geometry-based inference could not. The stall is real and reaches the joint
limit - the closest joint sits 3-4 degrees past +/-170 at every failure - so the
penalty was not a no-op; it fires on essentially only the failing states (6/6
versus 9-10 of 194 successes) and at its maximum value, yet the deterministic
behavior is unchanged. Given that a full-magnitude penalty of 0.05 per step is
roughly an order of magnitude below a single hold-progress increment and two
orders below the hold-complete bonus, the result is most consistent with the
penalty being too weak to outweigh the reach-and-hold shaping the policy already
optimized, i.e. an optimization/credit-assignment limit at the shoulder boundary
rather than the absence of any signal against parking a joint at its limit. It
also establishes that the wedge is not a region the policy never reaches: the
competent parent already drives joints past the nominal range on about 5% of
episodes, most of which still succeed. The new per-episode joint-margin
instrumentation closes the earlier gap where the stalled configuration was
inferred rather than observed. `working`/`best_known` (experiment 8
`checkpoint-120832`) remains the strongest measured policy, no experiment-9
artifact is preferred to it, and the reward change is reverted.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-checkpoint-20480-200ep-seed20260918-9ea08384b3a2.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-checkpoint-100352-200ep-seed20260918-9ea08384b3a2.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-checkpoint-120832-200ep-seed20260918-9ea08384b3a2.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-checkpoint-120832-200ep-seed20260918-6db0b3ca786d.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-working-200ep-seed20260918-6db0b3ca786d.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-9-checkpoint-120832-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-9/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-9/parameters.json, research/results.jsonl, research/research_state.json, research/brief.md, robot_learning/scenario/reward.py, robot_learning/scenario/environment.py, robot_learning/scenario/evaluation.py, robot_learning/robots/two_joint_arm.xml, training log for experiment 9 (research/query_training_log.py)

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 10

**Result:** A training-only potential that rewards reducing the summed wrapped
joint error to the joint-feasible analytic branch, applied by transfer from
`working`, left the researcher panel exactly unchanged (194/200 = 97.0% with the
parent's identical six failures {7, 56, 64, 75, 107, 145} at both 20,480 and
120,832 steps) and net-regressed the protected task-reference panel to 196/200 =
98.0%, down from the parent's 197/200 = 98.5%. On the protected panel the
endpoint repaired near-limit failure episode 175 and newly failed near-limit
episodes 0 and 10. The branch-guidance reward is reverted and `working`
(experiment 8 `checkpoint-120832`) remains the selected policy.

**Observed behavior:** Experiment 10 was a diagnostic transfer `training` run
from `working`, seed 0, 120,000 requested / 120,832 completed steps, 24
checkpoints. The change computed both analytic inverse-kinematics branches in
`robot_learning/scenario/environment.py`, selected the folded branch when the
open branch was joint-infeasible (shoulder or elbow outside +/-170 degrees) and
the folded branch feasible, and added a potential term `BRANCH_GUIDANCE_COEFFICIENT
= 20.0` times the per-step decrease of the summed absolute wrapped joint error to
that branch in `robot_learning/scenario/reward.py`; observation, PolicyIO, action
space, target distribution, success and hold semantics, PPO parameters and the
protected benchmark were unchanged. Training-time success was 0.99 at 20,480 and
0.94 at 120,832 (`ep_rew_mean` 110.22 and 119.62). On the researcher panel (seed
20260918, semantics 36aff4660c2d) both measured checkpoints score 194/200 = 97.0%
and fail exactly {7, 56, 64, 75, 107, 145}, the parent's failure set; a recorded
paired comparison of the two checkpoints shows 0 discordant episodes (p = 1.0)
even though all 200 per-episode reward totals differ, so the weights and
trajectories changed while the deterministic success outcomes did not. On
task-reference-v1 the endpoint scores 196/200 = 98.0% with failures {0, 10, 84,
102}, against the parent's 197/200 = 98.5% with {84, 102, 175}. Recomputing the
branches from the recorded per-episode geometry shows all six researcher-panel
failures and all of episodes {0, 10, 175, 84, 102} lie in the guidance-active
band: the open branch is joint-infeasible (open shoulder -172.8 to -185.4
degrees) while the folded branch is feasible, so the added term was active on
every one of these targets. At the researcher-panel failures the policy stalls
0.5-1.7 cm outside the 1 cm tolerance with 0-2 held steps; the newly failed
task-reference episodes 0 and 10 stall at 1.05 and 1.03 cm, and repaired episode
175 now succeeds at 0.998 cm in 123 steps. `working`/`best_known` and the
experiment-8 recipe are restored; no experiment-10 artifact is retained.

**Hypothesis assessment:** Contradicted for the stated prediction. The proposal
predicted that the six researcher-panel wedge episodes would move onto the
joint-feasible folded branch, complete the 100-step hold, raise researcher success
above 194/200, and leave the protected panel not below 197/200, and it named the
alternative that the wedge is an optimization or precision limit the reward
branch gradient would not repair. Observed: none of the six wedge episodes
changed outcome at either checkpoint, researcher success stayed at 194/200, and
the protected panel recorded the proposal's own stated contradicting observation
by adding new failures (episodes 0 and 10) on targets the parent solves. The
alternative is left standing. The result is not complete inertness: the reward
changed every per-episode researcher reward total and the protected-panel failure
set, so the term influenced the policy; that influence redistributed which
near-limit targets are solved rather than repairing the wedge, and its net
protected-panel effect was negative. Scope: two measured checkpoints (the
training-proxy peak and the endpoint), one seed-0 lineage, one coefficient and
potential shape, and deterministic 200-episode panels.

**Interpretation:** The experiment weakens the simplest "no branch gradient"
explanation for the wedge. A potential-based term that is active precisely on the
near-limit band, and that measurably altered trajectories and the protected failure
set, still left the six researcher-panel failures at exactly the same success
outcomes, while shifting protected-panel borderline results (repairing one 18.2 cm
near-limit target and breaking two 6.7-7.2 cm near-limit targets). Combined with
experiment 9's fully-active but outcome-inert joint-limit penalty, two oppositely
directed near-limit signals - a penalty for the infeasible posture and a reward for
the feasible branch - have now both failed to move the deterministic wedge. This
is most consistent with an optimization/credit-assignment or precision limit at the
shoulder boundary that the reach-and-hold shaping dominates, though the tested
coefficient of 20 per radian may still be too weak relative to the progress term
(10 per metre) and the hold bonuses (50), or the potential may be evaluated along a
path that does not cross the barrier toward the folded configuration, so a stronger
or differently shaped branch signal is not excluded. The protected-panel trade also
shows the branch boundary is sensitive to a near-limit reward term, and that its
sensitivity is not aligned with aggregate task success. `working`/`best_known`
(experiment 8 `checkpoint-120832`) remains the strongest measured policy, is not
exceeded by any experiment-10 artifact, and the reward change is reverted.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-10-checkpoint-120832-200ep-seed20260918-36aff4660c2d.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-10-checkpoint-20480-200ep-seed20260918-36aff4660c2d.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-10-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-10/inventory.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-10/parameters.json, research/results.jsonl, research/research_state.json, research/brief.md, robot_learning/scenario/environment.py, robot_learning/scenario/reward.py, robot_learning/scenario/observations.py, robot_learning/robots/two_joint_arm.xml

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Experiment 11

**Result:** Raising PPO's effective advantage-estimation horizon by transfer from
`working` (ppo.gamma 0.99 -> 0.999, ppo.gae_lambda 0.95 -> 0.99) repaired none of
the six researcher-panel wedge episodes and degraded task success monotonically
with training: measured 192/200 = 96.0% at 25,600, 184/200 = 92.0% at 50,176 and
173/200 = 86.5% at 120,832 on the researcher panel, and 96.0%/93.5%/88.0% on
task-reference-v1, all below the parent's 97.0%/98.5%. Every measured checkpoint
retains the parent's wedge {7, 56, 64, 75, 107, 145} and adds failures. The
parameter change is reverted and `working`/`best_known` (experiment 8
`checkpoint-120832`) remain selected.

**Observed behavior:** Experiment 11 was a parameter-only diagnostic transfer
`training` run from `working`, seed 0, 120,000 requested / 120,832 completed
steps, 24 checkpoints, with `code_changes` empty and only `ppo.gamma` and
`ppo.gae_lambda` overridden, so gamma*lambda moved 0.9405 -> 0.989 and the nominal
effective horizon 1/(1 - gamma*lambda) moved from about 17 to about 91 steps. The
raw log shows `success_rate` peaking at 0.97-0.98 around 24,576-25,600 steps and
then declining monotonically to 0.54 at 120,832, while `ep_len_mean` rose from
122 (1,024 steps) to 343 (120,832) and `ep_rew_mean` rose from 110 to 172; over
the same span `entropy_loss` grew more negative (-0.13 to -0.58) and the policy
`std` rose from 0.258 to 0.324. On the researcher 200-episode panel (seed
20260918, semantics ffdccdbf3357) the three measured checkpoints score 96.0%,
92.0% and 86.5%: `checkpoint-25600` fails {7, 56, 64, 75, 107, 136, 145, 169},
`checkpoint-50176` fails 16 episodes including all six wedge episodes plus
{0, 2, 23, 25, 58, 133, 136, 148, 154, 175}, and `checkpoint-120832` fails 27
episodes including all six wedge episodes and widespread new rear-radius and
rear-angle failures. The parent `working` scores 194/200 = 97.0% failing exactly
{7, 56, 64, 75, 107, 145}. On task-reference-v1 the checkpoints score 96.0%, 93.5%
and 88.0% against the parent's 98.5%; `checkpoint-25600` fails 8 episodes
including the parent's {84, 102, 175} plus {10, 91, 111, 139, 149}, and the
endpoint fails 24 including 10 and 18 at the smallest radii and new failures at
r 18-20 cm. All measured episodes are single deterministic 200-episode panels;
the recorded paired comparisons against `working` give 0 candidate wins and net
-2 (p = 0.5), -10 (p = 0.0020) and -21 (p = 9.5e-7) at the three checkpoints. On
the researcher panel the success step count rose (mean 111.4 to 123.2, maximum
339) and the mean failure reward total rose from -6.66 for the parent to 65.43 at
the endpoint, with every failure still a 500-step truncation: the endpoint's
successes are a subset of the parent's with 21 losses and 0 gains.

**Hypothesis assessment:** Contradicted. The proposal predicted that the longer
horizon would let the transferred policy credit the multi-step shoulder
reconfiguration toward the joint-feasible folded branch, converting at least one
of the six wedge episodes {7, 56, 64, 75, 107, 145} to success without losing
existing successes. Observed instead: none of the six wedge episodes converted at
any of the three measured checkpoints - all six fail at 25,600, 50,176 and
120,832 - the researcher panel fell to 96.0% and then steadily to 86.5%, the
protected panel fell to 96.0% and then to 88.0%, and new failures appeared at
every checkpoint on both panels, which is the proposal's own stated contradicting
observation (a broad regression with no wedge repair). The alternative that the
wedge is a soft joint-limit reach-and-precision wall that no change in the
advantage horizon moves is favored. Limits: exactly one intermediate-and-long
horizon pair was tested (gamma*lambda 0.9405 -> 0.989) in a single seed-0
transfer run; only 3 of 24 checkpoints were measured; the decline was still
ongoing at the budget end, so the run establishes that this horizon increase is
harmful to the competent policy and does not repair the wedge, not that no
credit-assignment formulation could ever do so.

**Interpretation:** The horizon increase did not merely fail to help - it
converted the policy's objective from reaching and completing the terminating
hold to prolonging and hovering near the target. The success step count and the
failure reward totals rose together across checkpoints while completion fell, and
`ep_len_mean` roughly tripled, the signature expected when a longer discount
horizon makes accumulating per-step shaping and proximity reward preferable to
terminating. Read together with experiment 9 (a fully active joint-limit penalty
that changed trajectories but not outcomes) and experiment 10 (a branch-guidance
potential that changed the protected failure set but not the researcher wedge),
three distinct interventions over signals and credit assignment have now each
left the deterministic wedge intact, while the direction that changed the
effective horizon most aggressively produced the largest task-level regression.
This strengthens the soft-limit / precision-wall reading of the residual and
weakens the myopic-credit-assignment explanation; it does not exclude an
intermediate horizon or a different return decomposition, which were not tested.
Because no experiment-11 artifact is measured at or above the parent on either
panel, the parameter change is reverted and the experiment-8 recipe and policy
are kept.

**Evidence inspected:** research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-25600-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-50176-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-120832-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-25600-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-50176-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-11-checkpoint-120832-task-reference-v1.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/evaluation-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-200ep-seed20260918-ffdccdbf3357.json, research/evaluations/603a61bf-d5d0-437a-9aea-3d5988940d85/task-reference-603a61bf-d5d0-437a-9aea-3d5988940d85-experiment-8-checkpoint-120832-task-reference-v1.json, research/checkpoints/challengers/603a61bf-d5d0-437a-9aea-3d5988940d85/experiment-11/inventory.json, research/results.jsonl, research/brief.md, research/current_params.json, training log for experiment 11 (research/query_training_log.py)
