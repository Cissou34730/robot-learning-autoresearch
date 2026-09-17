# Research postmortems

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Scientific strategy

**Current synthesis:** The unchanged baseline recipe (PPO, 64x64 tanh, n_steps
1024, ent_coef 0.01) remains the strongest measured policy:
`working`/`best_known` (`checkpoint-100352`, experiment 1) scores 194/200 =
97.0% on the researcher panel (seed 20260918) and 196/200 = 98.0% on the
protected task-reference panel. Experiment 2 (full 6-20 cm radius support plus
30% folded-target oversampling) and experiment 3 (setting a joint-infeasible
inverse-kinematics branch's two wrapped joint errors to 0.0), both trained by
transfer from `working`, neither removed the residual failures nor beat the
parent and both were reverted; experiment 3 additionally collapsed measured
success to 71.0-74.0% (researcher) and 72.0% (task-reference). The single
systematic failure mode is a narrow near-limit band: targets whose elbow-open
analytic shoulder solution exceeds the +/-170 degree joint limit by a small
margin (|shoulder_open| roughly (170, 184]). On the experiment-1 panel
`working` fails 6 of the 10 episodes in that band, stalling 0.81-1.42 cm
outside the 1 cm tolerance, mostly without entering tolerance at all.
Recomputing the folded inverse-kinematics solution for those six failures
places its shoulder at -67 to -130 degrees and its elbow at -56 to -139
degrees, all inside the joint range, and that folded configuration reaches the
target to within 0.0000 mm; every measured episode has at least one in-range
analytic branch. The band is therefore a failure to select an available
feasible solution, not a hard reachability limit. Experiment 3 showed the
policy consumes the analytic branch errors and that replacing an infeasible
branch's errors with a zero that reads as "already at goal" is harmful when
transferred, so the leading explanation remains representational: the
near-limit infeasible branch supplies a small wrapped joint error that attracts
the policy to the shoulder limit while an exact folded solution exists. A
competing explanation is an optimization or precision limit at the joint
boundary that is independent of the observation's branch information.

**Lessons and limits:** The band reading is a re-analysis of deterministic
development panels and analytic joint-limit geometry, not a new independent
measurement; it holds only 7-14 episodes per panel and no joint trajectories
are recorded, so the branch-attraction mechanism is inferred rather than
observed. The reachability computation uses the analytic two-link solution and
the model's joint ranges; it establishes that a feasible branch exists and is
exact in joint space, not that a continuous 2 second hold through that branch
is dynamically comfortable. Experiment 3 is direct evidence that a
dimension-preserving observation change is not semantically compatible with the
parent's learned representation: transferred from `working`, the gated policy
kept behavior only on episodes whose observation was unchanged (140/140
both-feasible) and failed 29/29 open-only, most folded-only and 7/7 band
episodes. Experiment 2's folded-target oversampling at roughly six times the
natural rate did not reduce the band, so a training-density deficit is not
supported. Training reward does not track task success (reward 163.85 at 0.42
training success versus 129.26 at 0.93) and is usable only as a shaped signal.
This recipe peaks near 100k steps; training past about 100k reduced hold
stability and added oscillation failures on open-feasible targets.

**Open questions:** Whether the near-limit band deficit is caused by the
observation presenting the joint-infeasible branch as an attractive target, or
by an optimization/precision limit at the shoulder boundary independent of the
observation, remains unresolved. It is unknown whether making each analytic
branch's joint-limit feasibility explicit lets a policy learn to select the
feasible folded solution, or whether it still follows the small wrapped error
of the infeasible branch. It is unknown how the two branches interact through
the learned observation normalizer, whether the residual near-limit targets are
reachable under a fixed 2 second continuous hold even though their
configuration is reachable, and how the affected band's boundary and radius
dependence behave.

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
