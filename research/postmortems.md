# Research postmortems

## 603a61bf-d5d0-437a-9aea-3d5988940d85 / Scientific strategy

**Current synthesis:** The unchanged baseline recipe (PPO, 64x64 tanh, n_steps
1024, ent_coef 0.01, 120k-step budget) learns the reach-and-hold task broadly
but not completely. Its selected checkpoint `checkpoint-100352` scores 97.0% on
the researcher 200-episode panel (seed 20260918) and 98.0% on the protected
task-reference panel (task-reference-v1), close to but not safely above the 98%
objective. Re-reading both panels' per-episode geometry shows the residual
failures are not a broad angular wedge: all 6 research-panel and all 4
task-reference failures are targets whose elbow-open inverse-kinematics
solution violates the shoulder joint range (-170 to 170 degrees), so only the
elbow-folded configuration reaches them. The 190 and 187 episodes whose
elbow-open solution is feasible contain zero failures. Within the
folded-required set failures are partial (6 of 10 and 4 of 13) and the stalled
end effector stops about 0.8-1.4 cm outside the 1 cm tolerance without ever
completing a hold, while folded-required episodes that succeed enter tolerance
normally. That set is a thin, radius-dependent arc of roughly 5% of the
official target area, moving from about -124 degrees at 6 cm to about -155
degrees at 20 cm. The recipe's training distribution samples radii only in
14-20 cm while the official task samples 6-20 cm, so the near-field part of
this arc was never trained. A later checkpoint, `checkpoint-120832`, scores
lower (94.5%) and adds oscillation failures outside this region, so training
this recipe further, unchanged, degraded hold stability while the
folded-required failures persisted.

**Lessons and limits:** The folded-required explanation is a re-reading of two
existing development panels and joint-limit geometry, not an independent
confirmation, and the task-reference panel remains a repeated development
measurement rather than held-out evidence. The association is exact over the
400 measured episodes, but the region holds few episodes per panel (10 and 13),
the 1 cm tolerance is close to the observed stall distance, and the mechanism
is inferred rather than demonstrated. Within the measured evidence, task
success and the training-time success proxy agree near the peak (0.97 ->
97.0%), while training reward does not track success (e.g. 86,016: reward
163.85 at 0.42 success; 95,232: reward 129.26 at 0.93), so reward is usable
only as a shaped training signal. The recipe was trained unchanged in
experiment 1, so no component of it can be causally credited for the
folded-required deficit or for the post-peak degradation.

**Open questions:** Whether the folded-required deficit is a training-density
deficit (too few folded targets, especially near field), a precision limitation
near the shoulder joint limit, or an artifact of the observation's two wrapped
inverse-kinematics solutions conflicting at the limit is unresolved. It is
unknown how much of the deficit raising folded-target density would remove and
whether it would trade failures elsewhere. The exact angular extent and radius
dependence of the region are computed from geometry, not directly measured.

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
