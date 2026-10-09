## Established facts

### Task boundary and assessment

**Repository fact.** The official task samples a target at a radius of 0.06-0.20
m from the robot base over the full angular range. Success requires the end
effector to be within 0.01 m of the target for 2.0 s without interruption.
At the official control timing this is 100 consecutive control steps. An
episode is successful only when that complete hold is achieved; a partial hold
does not count. The official assessment uses 200 episodes, at most 500 control
steps per episode, and requires at least 196 successes (98%).

**Source references:** `contracts/scenario.md:7-32`;
`contracts/task_spec.py:6-11`.

**Repository fact.** The shared environment advances the simulator for ten
MuJoCo steps per action. The XML timestep is 0.002 s, so one action is held for
0.020 s and the nominal control rate is 50 Hz. The environment computes
`round(2.0 / 0.020) = 100` required hold steps and truncates at 500 control
steps.

**Source references:** `contracts/robots/two_joint_arm.xml:1-3`;
`contracts/task_spec.py:7-11`;
`robot_learning/scenario/environment.py:36-58,122-168`.

**Repository fact.** The baseline training environment samples radii only from
0.14-0.20 m, although the official task includes 0.06-0.20 m. In the accessible
environment, angle and radius are each sampled uniformly and the target is
placed at the end-effector plane height. The final official assessment semantics
remain the human-owned task contract.

**Source references:** `robot_learning/training/environment.py:14-19`;
`robot_learning/scenario/environment.py:83-97`;
`contracts/scenario.md:7-16`.

### Morphology and kinematics

**Repository fact.** The robot is a fixed-base, planar, serial two-revolute-joint
arm. The shoulder is at the base and the elbow is at the end of the 0.12 m
upper arm. The forearm is 0.10 m long and carries the end-effector site at its
tip. The joint axes are both the world z axis. The arm plane is z = 0.02 m;
the target is placed in that same plane.

**Source references:** `contracts/robots/two_joint_arm.xml:9-27`;
`contracts/robots/two_joint_arm.py:3-7`;
`robot_learning/scenario/environment.py:90-97`.

**Repository fact.** With shoulder angle q1 and relative elbow angle q2, the
end-effector position relative to the base is

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
    z = 0.02.

Both joints have the range [-170, 170] degrees. Reset sets both joint positions
and velocities to zero, so the initial end effector is at (0.22, 0, 0.02) m.

**Source references:** `contracts/robots/two_joint_arm.xml:12-20`;
`robot_learning/scenario/environment.py:102-120`.

**Reasoned implication.** Ignoring joint limits, the geometric workspace is the
annulus between radii |0.12 - 0.10| = 0.02 m and 0.12 + 0.10 = 0.22 m. The
official radial interval [0.06, 0.20] lies inside this annulus. The inverse
kinematic relation

    cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)

gives two elbow branches, q2 = +/- arccos(cos(q2)). Over the official radial
interval the elbow magnitude is approximately 49.5-150.3 degrees, within the
joint range. Choosing the branch that moves q1 toward the target bearing keeps
q1 within 170 degrees for every bearing. Thus every official target is
geometrically reachable by at least one limit-feasible posture, subject to the
simulator's treatment of the joint limits.

**Source references:** `contracts/robots/two_joint_arm.py:5-7`;
`contracts/robots/two_joint_arm.xml:13-18`;
`robot_learning/scenario/observations.py:18-35`.

**Decision relevance:** This establishes that official failures should not be
attributed to unreachable target geometry before examining dynamics, limits,
and control behavior.

**Assumptions:** The planar forward-kinematic convention and the specified
joint ranges are active in the compiled model.

**Discriminating evidence:** Analytic IK enumeration across the official
radius-angle domain, followed by compiled-model target sweeps, can confirm or
revise the limit-feasible reachability claim.

### Actuation, simulation, and physical state

**Repository fact.** Gravity is zero. The plane, base, arm geoms, and target
have no task-relevant collision interaction: the plane and base are
non-colliding, and the target geom has `contype="0"` and `conaffinity="0"`.
There is no grasp, contact, obstacle, or environmental force in the defined
task.

**Source references:** `contracts/robots/two_joint_arm.xml:1-11,25-27`.

**Repository fact.** Each joint is driven by a MuJoCo motor with control range
[-1, 1] and gear 5. The policy action is passed through unchanged and then
clipped to that range before being assigned to `data.ctrl`; it remains fixed
through the ten simulator substeps.

**Source references:** `contracts/robots/two_joint_arm.xml:30-33`;
`robot_learning/scenario/policy_io.py:11-16`;
`robot_learning/scenario/environment.py:122-133`.

**Repository fact.** The XML specifies joint damping 0.5 and armature 0.01 for
both joints. It does not specify body masses, inertial tensors, friction loss,
actuator dynamics, transmission limits beyond the control range, or solver
parameters. MuJoCo therefore supplies the omitted model quantities according to
its native defaults and compiled geometry model.

**Source references:** `contracts/robots/two_joint_arm.xml:12-19`;
`AGENTS.md` (native `mujoco==3.12.0` requirement).

**Repository fact.** The task state includes joint position, joint velocity,
target position, and the consecutive in-tolerance counter. The target is a
static mocap body after reset. On every control step, distance is measured in
3-D; distance <= 0.01 m increments the counter, while distance > 0.01 m resets
it to zero. The episode terminates at 100 held steps or truncates at 500 total
steps.

**Source references:** `robot_learning/scenario/environment.py:75-97,102-120,134-168`.

### Sensing and policy interface

**Repository fact.** The policy receives an 11-element observation consisting of
two qpos values, two qvel values, the three-vector end-effector-minus-target
position, and four wrapped joint-angle errors to the open-elbow and
folded-elbow inverse-kinematic solutions. There is no explicit sensor noise,
latency, actuator torque, acceleration, contact force, hold counter, or clock
component in this observation.

**Source references:** `robot_learning/scenario/observations.py:11-49`;
`robot_learning/scenario/environment.py:59-65`.

**Reasoned implication.** Given the known model, qpos determines the
end-effector position, and the relative position together with qpos determines
the target position. Therefore the instantaneous target geometry is observable
in principle even though the target coordinates are not sent as a separate
observation. The four angle-error features expose both inverse-kinematic branch
directions, not an additional physical degree of freedom.

**Source references:** `robot_learning/scenario/observations.py:18-47`;
`contracts/robots/two_joint_arm.py:5-7`.

**Decision relevance:** This can change whether target-coordinate features,
inverse-kinematic features, or additional geometric processing are treated as
the limiting sensing factor.

**Assumptions:** The policy receives the exact observation returned by
`reach_observation`, without an external sensor model that changes it.

**Discriminating evidence:** Reconstruct the target from qpos and the relative
position and compare it numerically with the mocap target over representative
states; reconstruction error would weaken the observability claim.

**Repository fact.** Evaluation resets recurrent policy state and calls the
policy deterministically. A saved policy may also contain observation
normalization statistics, which are applied before prediction.

**Source references:** `contracts/policy_runtime.py:153-177`;
`robot_learning/scenario/evaluation.py:42-60`;
`robot_learning/training/normalization.py:30-46`.

## Physical consequences

### Reach and uninterrupted stabilization are one coupled control problem

**Reasoned implication.** The policy must first reduce Cartesian error and then
keep both position and velocity sufficiently small that the end effector does
not leave a 1 cm ball during 100 successive 20 ms intervals. A trajectory that
reaches the target quickly but oscillates, drifts, or crosses the boundary once
fails exactly like a trajectory that never reaches. The relevant terminal
behavior is therefore convergence plus local stabilization, not minimum
first-arrival time.

**Decision relevance:** This can change whether early development is judged by
first reach, maximum continuous hold, or complete episode success, and whether
the learned controller needs explicit temporal memory or a stabilizing behavior.

**Assumptions:** The task contract and shared hold logic represent the official
semantics; no unobserved benchmark mechanism changes the 100-step hold.

**Source references:** `contracts/scenario.md:9-20`;
`contracts/task_spec.py:7-11`;
`robot_learning/scenario/environment.py:134-168`.

**Discriminating evidence:** Per-episode first-reach step, maximum held steps,
hold interruptions, final distance, and distance/velocity traces distinguish
slow-reach failures from post-reach stabilization failures.

### The reset state makes target bearing and radius shape the approach

**Reasoned implication.** The arm always starts fully extended along +x with zero
velocity. For a target of radius r and bearing phi, the initial Cartesian
distance is

    d0 = sqrt(0.22^2 + r^2 - 2 * 0.22 * r * cos(phi)).

Across the official domain this ranges from 0.02 m for an outer target near the
initial bearing to 0.42 m for an outer target at the opposite bearing. Thus
targets with the same radius can impose very different initial transients, and
the initial state is not a neutral sampling point for angular difficulty.

**Decision relevance:** This can change whether early evidence is aggregated
over radius alone or stratified by bearing and initial distance.

**Assumptions:** The reset state and target placement are those of the shared
environment, and the target remains fixed during an episode.

**Source references:** `robot_learning/scenario/environment.py:83-120`;
`contracts/robots/two_joint_arm.xml:12-20`.

**Discriminating evidence:** Report first-reach time, peak qvel, peak action,
and hold success against target bearing, radius, and computed initial distance.

### The two inverse-kinematic branches create distinct posture strategies

**Reasoned implication.** A target generally admits an elbow-open and an
elbow-folded posture. These postures have different joint angles and
configuration-dependent inertia and actuator leverage, even though they have
the same end-effector location. A policy can therefore succeed through
different joint-space trajectories; one branch is not physically privileged by
the task geometry. Branch switching during approach or hold would require
substantial joint motion and can itself create boundary excursions.

**Decision relevance:** This can change whether policy comparisons should be
conditioned on posture branch and whether a successful recipe is understood as
general tracking or as reliance on one branch.

**Assumptions:** The kinematic equations and joint ranges in the XML are the
effective model, and no additional posture cost or collision constraint exists.

**Source references:** `contracts/robots/two_joint_arm.xml:12-20`;
`robot_learning/scenario/observations.py:18-47`;
`robot_learning/training/reward.py:47-107`.

**Discriminating evidence:** Record q1, q2 and the sign of q2 at first reach and
through the hold, then compare success and hold interruptions by branch,
target radius, and target angle.

### Timing, damping, armature, and omitted inertia determine control authority

**Reasoned implication.** The motor command is a bounded joint torque request
with nominal transmission magnitude 5 times the normalized action. Damping
opposes velocity and armature adds joint-side inertia. The serial arm's
configuration-dependent mass matrix couples shoulder and elbow motion, so the
same action can produce different accelerations at different postures. Ten
substeps per decision also make the action a sample-and-hold controller rather
than a continuously updated torque loop. These effects directly determine
overshoot, settling time, and whether the 1 cm band can be maintained.

**Decision relevance:** This can change the first choice between improving
policy learning and characterizing or adapting control timing, action scale,
or stabilization behavior.

**Assumptions:** MuJoCo's compiled defaults for omitted inertial and solver
quantities are used without hidden external dynamics, and the motor gear
produces the standard MuJoCo hinge transmission.

**Source references:** `contracts/robots/two_joint_arm.xml:1-3,12-19,30-33`;
`robot_learning/scenario/environment.py:125-133`.

**Discriminating evidence:** Query the compiled model's body masses and joint
inertias, then measure step responses and free-decay responses at representative
postures. Compare commanded action, qvel, acceleration, peak error, and
settling time against the 20 ms decision interval.

### Official geometry and baseline training geometry are different

**Reasoned implication.** The baseline recipe does not expose the policy to the
official inner annulus from 0.06 to 0.14 m. Since the inner targets require
larger elbow angles and can have different joint-space sensitivity than
outer targets, success on the baseline training range cannot establish
generalization over the official distribution. The gap is geometric rather
than merely statistical: the policy must control postures that baseline
training may never visit.

**Decision relevance:** This can change the first campaign decision between
preserving the baseline target range and addressing coverage of the omitted
official region.

**Assumptions:** The accessible training environment is the recipe used for
the first candidate, and the official distribution is the contract's full
6-20 cm interval.

**Source references:** `contracts/scenario.md:7-16`;
`robot_learning/training/environment.py:14-19`;
`robot_learning/scenario/environment.py:83-97`.

**Discriminating evidence:** Evaluate success, first reach, maximum hold, and
joint-space trajectories in radial bins, especially 6-10, 10-14, and 14-20 cm,
while also stratifying by target angle.

### The observation exposes geometry but not hold history

**Reasoned implication.** The physical pose, velocity, and target-relative
geometry are available, but two episodes can present the same 11-element
observation with different hidden `held_steps` values. The hidden counter does
not alter the mechanical state, but it alters reward, termination, and whether
the current visit completes the task. A memoryless policy therefore cannot
condition its action directly on accumulated hold progress; it must use the
current physical state and its learned control behavior to remain inside the
band.

**Decision relevance:** This can change whether the first research question is
about state representation, temporal memory, or purely physical stabilization.

**Assumptions:** The policy input remains the declared observation and the
environment does not expose `info` fields to the policy.

**Source references:** `robot_learning/scenario/observations.py:11-49`;
`robot_learning/scenario/environment.py:134-168`;
`contracts/policy_runtime.py:23-27`.

**Discriminating evidence:** Compare otherwise matched episodes by maximum
continuous hold and interruption timing, and test whether a policy's action
depends on recent observation history or recurrent state when instantaneous
observations are matched.

### Reward shaping is not the physical success criterion

**Reasoned implication.** The reward combines distance progress, exponential
closeness, hold-progress increments, a small action cost, and a completion bonus.
The configured hold-exit forfeiture is zero, so leaving the tolerance band does
not erase accumulated reward capital; the official success flag nevertheless
resets the counter and requires a fresh uninterrupted hold. A policy can thus
maximize substantial shaped reward while still failing the episode objective.

**Decision relevance:** This can change whether reward totals or training success
are treated as evidence of progress, and whether hold-specific diagnostics are
required before selecting a candidate.

**Assumptions:** The current reward implementation is used by the learning
recipe and the protected assessment uses the contract success definition rather
than reward.

**Source references:** `robot_learning/training/reward.py:16-25,47-107`;
`robot_learning/scenario/environment.py:145-168`;
`contracts/scenario.md:17-32`.

**Discriminating evidence:** Compare reward components with official-style
episode success, maximum held steps, number of interruptions, and final
distance; disagreement between reward and complete hold is evidence against
using reward as a terminal proxy.

### The task is free-space tracking with deterministic mechanics

**Reasoned implication.** Because gravity and task contacts are absent, the
dominant physical problem is inertial joint control under a moving reference
in configuration space, not force closure, collision avoidance, or contact
compliance. Target variation is the principal task uncertainty in the defined
environment. This makes kinematic branch selection, damping, and settling
behavior more consequential than contact modeling.

**Decision relevance:** This can change which diagnostics are scientifically
useful and prevents attributing failures to grasping or obstacle interaction
mechanisms that are not present.

**Assumptions:** The XML is the complete robot and world model and no hidden
contact geometry is added by the protected evaluator.

**Source references:** `contracts/robots/two_joint_arm.xml:1-33`;
`robot_learning/scenario/environment.py:52-57,83-97`.

**Discriminating evidence:** Inspect contact counts and external-force terms
during representative rollouts; they should remain absent or physically
irrelevant, while qpos, qvel, torque command, and target error explain outcome.

### The causal loop exposes the quantities that define complete behavior

**Reasoned implication.** At each 20 ms boundary, the observation maps the
current qpos, qvel, and target-relative geometry to a bounded action. That
action is held for ten 2 ms dynamics steps, producing new qpos and qvel; the
new end-effector error updates the hold counter, reward, termination state, and
next observation. The scientifically meaningful trajectory quantities are
therefore target radius and bearing; qpos, qvel, and end-effector position;
Cartesian error and its minimum/final values; action and realized joint
response; inverse-kinematic branch distance; first-reach time; continuous hold
length; interruption count; and terminal success.

**Decision relevance:** These quantities separate geometry, actuation,
convergence, stabilization, and task-outcome mechanisms instead of collapsing
them into a single episode reward.

**Assumptions:** The shared environment's observation, action, stepping, and
hold update sequence is representative of the task interaction semantics.

**Source references:** `robot_learning/scenario/observations.py:14-49`;
`robot_learning/scenario/environment.py:122-168`;
`robot_learning/scenario/evaluation.py:45-106`.

**Discriminating evidence:** Preserve synchronized per-control-step records of
these quantities and compare their trajectories for successful episodes,
first-reach-but-failed-hold episodes, and never-reached episodes.

## Unknowns

### Effective compiled inertia and mass matrix

**Unresolved quantity.** The XML does not state body masses or inertial tensors.
The effective MuJoCo masses, link inertias, and configuration-dependent mass
matrix are therefore not established by the repository text alone.

**Decision relevance:** This can change the predicted acceleration, overshoot,
settling time, and the plausibility of any controller-timing or action-scale
decision.

**Assumptions:** MuJoCo native compilation from the XML is the runtime model;
the omitted values are not supplied elsewhere.

**Source references:** `contracts/robots/two_joint_arm.xml:12-20`;
`AGENTS.md` (native MuJoCo runtime requirement).

**Discriminating evidence:** Read the compiled `MjModel` mass and inertia
arrays, calculate the joint-space mass matrix at open and folded postures, and
compare predicted and observed step responses.

### Realized acceleration and settling envelope under saturated commands

**Unresolved quantity.** The control range and gear are explicit, but the
resulting acceleration, peak speed, and settling time over the official
workspace are not. Damping, armature, omitted inertia, and configuration
coupling jointly determine these quantities.

**Decision relevance:** This can change whether a 50 Hz policy has enough
control authority for fast targets and whether a failure is learnability-limited
or mechanically limited.

**Assumptions:** The motor has no unlisted force limit or actuator dynamics and
the action is held exactly for ten substeps.

**Source references:** `contracts/robots/two_joint_arm.xml:1-3,12-19,30-33`;
`robot_learning/scenario/environment.py:125-133`.

**Discriminating evidence:** Apply bounded step and reversal commands at
multiple q configurations and record qpos, qvel, acceleration, and end-effector
error at every simulator substep and control boundary.

### Joint-limit behavior near the feasible boundary

**Unresolved quantity.** The nominal joint ranges are specified, but the
effective limit constraint activation and solver reaction at the boundary are
not described in the repository. The analytic IK calculation shows an
interior feasible branch for the official annulus, but it does not establish
the transient behavior of limit forces or numerical behavior near +/-170
degrees.

**Decision relevance:** This can change whether rare angular failures are
interpreted as policy errors, branch-selection errors, or limit-induced
transients.

**Assumptions:** The range attributes are active MuJoCo joint limits and the
protected task uses the same XML.

**Source references:** `contracts/robots/two_joint_arm.xml:12-18`;
`robot_learning/scenario/observations.py:18-35`.

**Discriminating evidence:** Inspect compiled joint-limit flags and solver
parameters, then sweep targets and trajectories near the limiting bearings
while recording qpos, qvel, constraint forces, and end-effector error.

### Exact official target sampling density

**Unresolved quantity.** The contract states uniform sampling from 0.06-0.20 m
over the full angular range, while the accessible environment explicitly draws
radius and angle independently with uniform scalar draws and the baseline
training environment narrows the radius to 0.14-0.20 m. The protected
assessment's exact sampling implementation is not part of the accessible
scientific surface.

**Decision relevance:** This can change how much probability mass is assigned to
inner versus outer targets and therefore which training coverage or evaluation
strata are most decision-relevant.

**Assumptions:** The wording "uniformly" could be interpreted differently for a
planar annulus (uniform radius versus uniform area), and the protected
benchmark is authoritative if it differs from the shared research helper.

**Source references:** `contracts/scenario.md:7-16`;
`robot_learning/scenario/environment.py:83-97`;
`robot_learning/training/environment.py:14-19`.

**Discriminating evidence:** Obtain the protected benchmark's recorded target
radius and angle frequencies or compare a sufficiently large reference panel
against the independently-uniform-radius and uniform-area predictions.

### Whether the learned policy uses branch-stable or branch-switching motion

**Unresolved quantity.** The morphology permits at least two postures for each
official target, but no pre-campaign fact establishes which branch a learned
policy will select or whether it will switch branches during an episode.

**Decision relevance:** This can change whether a failure mode is addressed by
posture coverage, target-conditioned control, or stabilization analysis.

**Assumptions:** The policy is free to use either inverse-kinematic solution and
the physical model has no hidden posture preference.

**Source references:** `robot_learning/scenario/observations.py:18-47`;
`contracts/robots/two_joint_arm.xml:12-20`.

**Discriminating evidence:** Track q2 sign, distance to both analytic IK
solutions, joint travel, and hold interruptions over target angle and radius.

### Relationship between shaped reward and generalization

**Unresolved quantity.** The reward's distance, closeness, hold-progress, and
action-cost terms have known coefficients, but their learned-policy effect
under PPO and observation normalization is not known before campaign evidence.
In particular, it is unresolved whether maximizing shaped return reliably
selects policies that preserve the full 100-step hold on unseen inner targets.

**Decision relevance:** This can change whether the first candidate is selected
from reward/training metrics or only after hold- and geometry-stratified
development evaluation.

**Assumptions:** PPO and the current normalized observation pipeline are the
learning mechanism, and reward is the only optimization signal.

**Source references:** `robot_learning/training/reward.py:16-25,47-107`;
`robot_learning/training/current_params.json:1-23`;
`robot_learning/train.py:103-136`.

**Discriminating evidence:** Pair training return and reward components with
held-step distributions and success on a radius/angle panel that includes the
omitted 0.06-0.14 m region.

## Decision-relevant synthesis

### Official coverage versus baseline coverage

**Reasoned implication.** The baseline recipe trains only on 0.14-0.20 m while
the official task spans 0.06-0.20 m; the inner region is reachable but may
require substantially folded elbow postures.

**Decision relevance:** This is the most immediate scientific distinction for
the first campaign direction: apparent success on the baseline range does not
establish official-distribution success.

**Assumptions:** The baseline training helper and official scenario contract
remain the active definitions.

**Source references:** `contracts/scenario.md:7-20`;
`robot_learning/training/environment.py:14-19`;
`contracts/robots/two_joint_arm.xml:12-20`.

**Discriminating evidence:** Radius-binned success and complete-hold
diagnostics, with a separate 0.06-0.14 m slice, especially at the target
bearings that produce the largest joint excursions.

### Stabilization, not first arrival, determines success

**Reasoned implication.** A 1 cm tolerance must be maintained for 2 s, so
residual velocity and closed-loop settling behavior are part of the task
solution.

**Decision relevance:** The first campaign evidence should distinguish reach
from hold failure before attributing a deficit to representation, reward, or
training duration.

**Assumptions:** The contract's uninterrupted hold is authoritative and the
20 ms control interval is unchanged.

**Source references:** `contracts/scenario.md:9-20`;
`contracts/robots/two_joint_arm.xml:1-3`;
`robot_learning/scenario/environment.py:134-168`.

**Discriminating evidence:** First-reach step, maximum held steps, interruption
count, final distance, and qvel during the hold.

### Dynamics are partly specified and partly empirical

**Unresolved quantity.** Damping, armature, timestep, frame skip, and motor
range are explicit, but effective mass, inertia, acceleration, and settling
envelope are not.

**Decision relevance:** A policy failure cannot be scientifically assigned to
learning or control design until the available torque and settling limits are
characterized.

**Assumptions:** Native MuJoCo compilation supplies the omitted inertial model
and no protected evaluator changes the robot XML.

**Source references:** `contracts/robots/two_joint_arm.xml:1-3,12-19,30-33`;
`robot_learning/scenario/environment.py:52-58,125-133`.

**Discriminating evidence:** Compiled inertial quantities plus bounded-command
step and reversal responses at representative open and folded postures.

### Hold progress is physically relevant but not observed

**Unresolved quantity.** The controller sees physical pose, velocity, and target
geometry, but not the environment's consecutive-hold counter or elapsed time.
It is therefore unresolved whether the current policy class can reliably
preserve the required hold without an explicit temporal state representation.

**Decision relevance:** This can change the first decision between investigating
observation/memory limitations and investigating physical tracking dynamics.

**Assumptions:** The declared 11-element observation is the complete policy
input and `held_steps` remains available only to reward and episode logic.

**Source references:** `robot_learning/scenario/observations.py:11-49`;
`robot_learning/scenario/environment.py:136-168`.

**Discriminating evidence:** Matched-state trajectory comparisons, recurrent
versus memoryless policy behavior if available, and the distribution of
interruptions after first entry into tolerance.

### Posture branch is a measurable source of variation

**Reasoned implication.** The same Cartesian target can be reached with open or
folded elbow configurations, and their dynamic responses need not match.

**Decision relevance:** Candidate behavior should be interpreted by branch, not
only by aggregate success; otherwise a branch-specific weakness can be hidden
by averaging.

**Assumptions:** Both analytic branches remain feasible under the active joint
limits and no hidden contact or posture penalty exists.

**Source references:** `robot_learning/scenario/observations.py:18-47`;
`contracts/robots/two_joint_arm.xml:12-20`.

**Discriminating evidence:** Branch-conditioned qpos/qvel, target error,
first-reach, and complete-hold measurements across the official geometry.
