# Scientific model: two-joint arm reach-and-hold

This model describes the pre-campaign physical and scientific problem. It
separates facts fixed by the human-authored contracts and implementation from
mechanistic consequences and quantities that still need evidence. The relevant
coordinates are planar joint angles in radians, Cartesian distances in metres,
and control time in 20 ms steps unless stated otherwise.

## Established facts

### Embodied geometry and kinematics

The robot is a serial planar two-revolute-joint arm. The shoulder joint is at
the base origin, at height `z = 0.02 m`; the upper arm has length
`l1 = 0.12 m`, and the forearm has length `l2 = 0.10 m`. Both hinge axes are
the world z axis, so the end effector remains in the horizontal plane
`z = 0.02 m`. With shoulder angle `q1` and relative elbow angle `q2`, its
position is

```
x = l1 cos(q1) + l2 cos(q1 + q2)
y = l1 sin(q1) + l2 sin(q1 + q2)
z = 0.02
```

The XML declares `q1, q2` ranges of -170 to 170 degrees. The unconstrained
two-link workspace is the annulus from `|l1-l2| = 0.02 m` to
`l1+l2 = 0.22 m`; the declared joint ranges slightly trim that ideal boundary.
These facts come from `contracts/robots/two_joint_arm.xml:9-20` and
`contracts/robots/two_joint_arm.py:3-8`.

Every official target has radius 0.06-0.20 m and any polar angle
`[-pi, pi]` (`contracts/scenario.md:9-12`,
`contracts/task_spec.py:6-11`). Thus the target annulus is strictly inside the
nominal reach limits, with 0.02 m radial clearance from the ideal outer
boundary and 0.04 m clearance from the ideal inner boundary. The target is
placed at the end-effector plane, not above or below it
(`robot_learning/scenario/environment.py:83-97`).

### Actuation, simulation, and timing

Each action has two components in `[-1, 1]`. The action is passed through
unchanged, clipped to that interval, written directly to the two MuJoCo motor
controls, and held for ten simulator steps
(`robot_learning/scenario/policy_io.py:11-16`,
`robot_learning/scenario/environment.py:122-133`). Each simulator step is
0.002 s, so the policy acts at 0.020 s intervals, or 50 Hz
(`contracts/robots/two_joint_arm.xml:1-3`,
`contracts/task_spec.py:8`). A motor has gear 5 and control range `[-1, 1]`;
under MuJoCo motor semantics this gives a nominal joint torque command of up
to 5 in either direction before the joint dynamics respond
(`two_joint_arm.xml:30-33`).

Gravity is disabled. The moving links are capsules with radii 0.015 m and
0.012 m. Joint damping is 0.5 at both joints and joint armature is 0.01 at
both joints. The model supplies no controller-side position or velocity
feedback, action filtering, observation delay, actuator saturation beyond the
motor control range, or contact interaction. The plane and visible target have
collision disabled, and the target is a kinematic mocap body
(`two_joint_arm.xml:1-3, 6, 12-20, 25-32`). Link mass and inertia are therefore
simulator-derived from the geom definitions and MuJoCo defaults rather than
explicit values in this XML.

The initial state resets both joint positions and velocities to zero, advances
the model, and then samples a stationary target. At reset the arm is straight
along positive x and the end effector is at `(0.22, 0, 0.02)`. The target angle
is uniform over the full circle and its radius is uniform over `[0.06, 0.20]`
m, not area-uniform over the annulus
(`robot_learning/scenario/environment.py:102-120`,
`contracts/task_spec.py:6-11`). The target is not a dynamical object and
does not move after reset.

### Task and observation

The end effector must be no more than 0.01 m from the target for 100
consecutive control observations. Ten simulator integrations occur between
observations, so this is 2 s at the official 50 Hz control rate. Exiting the
tolerance resets the held-step count; success is declared only when the count
reaches 100. An episode truncates at 500 control steps, or 10 s
(`robot_learning/scenario/environment.py:55-58, 134-168`,
`contracts/scenario.md:12-26`).

The policy observation has 11 values:

1. the two joint positions and two joint velocities;
2. the three-dimensional end-effector-minus-target displacement; and
3. four wrapped angular errors to the two analytic inverse-kinematics branches.

The IK calculation uses the target Cartesian position and
`arccos((r^2-l1^2-l2^2)/(2 l1 l2))` to construct positive-elbow and
negative-elbow solutions. The observation therefore presents both branch
errors, rather than forcing a single posture choice
(`robot_learning/scenario/observations.py:11-49`). In this noiseless model,
joint state and target-relative position expose the state needed for the
deterministic two-link dynamics; there is no camera inference, force sensing,
measurement noise, or hidden target motion in the environment.

## Physical consequences

### The official problem is a coupled acquisition-and-stabilization problem

**Consequence.** Reaching the 1 cm ball is not sufficient. The policy must
first create a feasible joint trajectory from the straight initial posture,
then reduce both Cartesian error and end-effector velocity, and finally keep
the closed-loop state inside a small tolerance for 100 samples. The same
torque action that improves position can create exit velocity near the target.

**Decision relevance.** This changes whether early research decisions should
be judged primarily by first arrival or by complete episode success, and
whether policy inputs and diagnostics need to distinguish acquisition from
post-arrival regulation. It also determines whether a method that reaches
quickly but oscillates is scientifically competitive with a slower stable
method.

**Assumptions.** The tolerance is small relative to the link lengths, the
target is stationary, and the motor is direct torque control with no hidden
servo. These are supported by `two_joint_arm.xml:1-3, 30-33` and
`environment.py:134-168`.

**Discriminating evidence.** Per-episode first-in-tolerance step, maximum
consecutive held steps, interruption count, final distance, and velocity at
first entry would support this decomposition. A policy that reaches the ball
reliably but has low completed-episode success would support stabilization as
the limiting behavior; failures before entry would weaken that explanation.

### The target geometry is reachable but near-target conditioning is harder

**Consequence.** The official radii lie well inside the ideal annular
workspace, so gross reachability is not expected to be the dominant
constraint. However, the planar Jacobian changes with posture and becomes
ill-conditioned near both straight and folded configurations. At `q2 = 0` (and
similarly near `q2 = pi`), first-order joint motion is predominantly
tangential; radial correction requires coordinated finite motion away from the
singular posture. The same Cartesian error can consequently require different
joint corrections and torque effort.

**Decision relevance.** This can change decisions about whether a Cartesian
error-only controller representation is adequate, whether joint state and
branch information are essential, and whether performance must be stratified
by target radius and angle rather than summarized by one success rate.

**Assumptions.** The standard two-link forward kinematics apply, the joints
remain in their declared ranges, and torque authority is not saturated before
the desired correction is made. The kinematics and ranges are sourced from
`two_joint_arm.xml:12-20` and the link constants from
`contracts/robots/two_joint_arm.py:5-8`.

**Discriminating evidence.** A sweep of target radius and angle with joint
trajectories, Jacobian conditioning, action saturation, and terminal
Cartesian velocity would support or weaken the conditioning explanation.
Similar errors with materially different outcomes by posture would support a
configuration-dependent control limitation rather than simple target
distance as the cause.

### Two postures are physically available for almost every official target

**Consequence.** The two IK branches are the positive- and negative-elbow
solutions. For the official radial interval, both branches have nondegenerate
solutions away from the workspace boundaries, and the 170-degree joint limits
leave substantial margin at the specified maximum radius. A policy can
therefore solve the task by selecting a branch, switching branches only by
passing through a dynamically meaningful configuration, or using different
branches for different target sectors. Branch switching is not a harmless
representation change: it requires coordinated joint motion and can disturb a
hold.

**Decision relevance.** This changes whether a first campaign decision treats
multimodality as an output-selection problem, a trajectory-control problem, or
an ambiguity in the observation. It also affects interpretation of apparent
failure clusters: a policy may be reaching a valid alternate posture rather
than failing geometrically.

**Assumptions.** The analytic IK equations in `observations.py:18-35` describe
the same relative elbow convention as the MuJoCo hinges, and target radii
remain within the official interval. The observation source explicitly
constructs both branches and reports their wrapped errors
(`robot_learning/scenario/observations.py:36-49`).

**Discriminating evidence.** Comparing final joint angles with both analytic
solutions, branch occupancy by target sector, branch transitions during
holds, and success conditioned on branch would support or revise this
multimodal account. If all successful trajectories converge to one branch
without loss elsewhere, branch choice is available physically but may not be
the limiting learned behavior.

### Torque and damping determine whether arrival can be converted into a hold

**Consequence.** The robot has bounded direct torque, joint viscous damping,
and armature, but no gravity load. The links and their simulator-derived
inertias determine acceleration and braking. Consequently, the relevant
closed-loop time scale is not just the 20 ms policy period: a policy must
shape momentum over multiple action intervals. An action that is adequate for
large-range motion may be too coarse near the 1 cm boundary, while low action
may be unable to reject residual velocity quickly enough.

**Decision relevance.** This can change decisions about policy action
parameterization, temporal abstraction, and the amount of state or history
needed for stable control. It also determines whether apparent learning
failure is likely to be a physical authority limit or an exploration and
credit-assignment issue.

**Assumptions.** Motor gear maps control to joint torque as specified by native
MuJoCo semantics, and the implicit mass/inertia values are those produced by
the loaded model. Explicit actuator and damping parameters are in
`two_joint_arm.xml:12-14, 17-18, 30-32`; the integration schedule is in
`two_joint_arm.xml:1-3` and `task_spec.py:8`.

**Discriminating evidence.** Compiled-model masses and inertias, measured
joint acceleration under known actions, action saturation frequency, settling
time after entry, and velocity at tolerance crossings would support or
weaken this mechanism. If the arm settles rapidly with large authority and
failures remain angle- or branch-specific, dynamics are less likely to be the
first limiting factor.

### Official evaluation is a discrete sampled hold, not an independently
verified continuous-time tube

**Consequence.** The implementation checks distance after each ten-step
MuJoCo integration and increments or resets the hold counter at that sample.
The 100-sample condition is authoritative for the task, but internal motion
between checks is not separately recorded by the success logic. A trajectory
can therefore have an unobserved within-interval excursion while passing the
operational test, whereas a one-sample post-integration exit definitely breaks
the hold.

**Decision relevance.** This changes whether robustness is assessed only by
official success or also by substep trajectory margins, and prevents
confusing official semantics with a stronger continuous-time safety claim.

**Assumptions.** The environment is evaluated exactly through the shared
`step` path and the official timing remains 10 simulator steps per action.
The check and reset logic are in `environment.py:130-159`; the contract fixes
the corresponding 100 control steps in `scenario.md:9-20`.

**Discriminating evidence.** Recording maximum substep distance and distance
margin within each control interval would reveal hidden excursions. Agreement
between substep margins and sampled success would weaken the distinction but
would not change the official criterion.

### The training distribution currently omits the inner official radii

**Consequence.** Official targets span 0.06-0.20 m, while the current
training constructor samples only 0.14-0.20 m
(`robot_learning/training/environment.py:14-19`). The physical robot can reach
the omitted region, but the learned policy has no baseline exposure there.
Inner targets also require more folded configurations and can change the
relative importance of the two branches and braking dynamics.

**Decision relevance.** This is a direct choice point for the first campaign:
performance on the official distribution may be limited by distributional
coverage rather than robot feasibility. It changes how development evidence
should be interpreted and whether a training-distribution decision is needed
before attributing failures to control or dynamics.

**Assumptions.** The training environment is the one used by the current
trainer and evaluation uses the fixed official range. This separation is
explicit in `training/environment.py:1-19` and
`scenario/environment.py:171-178`; the immutable official range is in
`task_spec.py:6`.

**Discriminating evidence.** Success and trajectory diagnostics binned by
radius, especially 0.06-0.14 m versus 0.14-0.20 m, would support a coverage
explanation if the inner bins fail disproportionately while their torque and
settling profiles remain feasible. Uniform performance by radius would weaken
it.

## Unknowns

### Compiled inertial quantities and actual control authority

The XML gives capsule geometry, damping, armature, and motor gear but not
explicit body mass, center-of-mass, or full inertia tensors. MuJoCo will
derive these from geometry and its defaults, but their numerical values have
not been recorded in this pre-campaign model. This matters because it sets
angular acceleration, coupled inertia, and braking distance.

**Decision relevance.** These values could change the first choice between
methods that rely on fast direct torque correction and methods that require
longer-horizon trajectory regulation. The relevance assumes the observed
policy failures are dynamic rather than representational.

**Sources and assumptions.** Geometry and explicit dynamic parameters are in
`contracts/robots/two_joint_arm.xml:12-20`; no mass or inertia attributes
appear there. The inference assumes native MuJoCo model compilation.

**Discriminating evidence.** The loaded `body_mass`, `body_inertia`, joint
armature, actuator gear/force values, and acceleration response to controlled
actions would resolve the quantity. A comfortably large measured authority
relative to required corrections would revise its priority.

### Whether the joint range is encountered as a hard behavioral boundary

The joints declare +/-170 degree ranges, but the pre-campaign model does not
yet quantify how often successful or failed trajectories approach the limits,
nor whether limit contacts materially alter motion under the loaded MuJoCo
defaults. Official target geometry appears to leave kinematic margin, but
dynamic overshoot could still encounter a limit during acquisition or holding.

**Decision relevance.** This could change whether limit avoidance is treated as
a central control constraint or merely a rare failure mode, and whether angle
or target-sector stratification is necessary.

**Sources and assumptions.** Joint ranges are in
`two_joint_arm.xml:12-18`; target construction and reset are in
`environment.py:83-119`. The relevance assumes the declared range is active
under the simulator defaults.

**Discriminating evidence.** Minimum distance to each joint limit, limit
activation events, and their timing relative to tolerance exits would support
or weaken this constraint.

### The dominant source of hold interruption

The implementation records distance and held-step state, but no campaign
evidence yet identifies whether interruption is caused mainly by Cartesian
position bias, residual velocity, branch transitions, torque saturation,
near-limit behavior, or numerical/sample timing. These mechanisms can produce
the same binary episode failure.

**Decision relevance.** This is the most consequential unresolved scientific
quantity because it determines which family of learning or control decisions
is justified first. The success metric alone cannot distinguish them.

**Sources and assumptions.** Success and counter reset are defined in
`environment.py:134-168`; available research diagnostics include first reach,
maximum hold, interruptions, and distances in `scenario/evaluation.py:40-125`.
The relevance assumes those diagnostics are representative of the official
panel.

**Discriminating evidence.** Joint velocities, action norms and saturation,
distance margin over the final 100 steps, branch error, and target geometry
conditioned on every interruption would distinguish the mechanisms. Stable
near-zero velocity with persistent offset would support a bias/representation
explanation; high velocity or repeated boundary crossings would support a
dynamic regulation explanation.

### The practical value of the full observation for a feedforward policy

The environment exposes positions, velocities, target-relative displacement,
and both IK errors, but it is unresolved whether a memoryless policy can infer
all useful phase information from this state at 50 Hz. The physical state is
Markov under the nominal deterministic model, yet the relevant information for
learning may still be poorly conditioned or redundant.

**Decision relevance.** This could change the first choice between a
memoryless state policy and a policy with temporal memory or a different
state representation. It does not imply that memory is physically required.

**Sources and assumptions.** Observation construction is in
`observations.py:14-49`; action identity is in `policy_io.py:11-16`; the
current trainer uses a feedforward MLP configuration in
`training/current_params.json:1-23`. The relevance assumes the policy runtime
does not add hidden state beyond its declared interface.

**Discriminating evidence.** Compare outcomes and hold interruptions while
conditioning on identical instantaneous observations, and inspect whether
velocity plus position predicts subsequent tolerance exits. Predictive
ambiguity would support temporal information as relevant; deterministic
state-conditioned outcomes would weaken that need.

## Decision-relevant synthesis

1. **Reach versus hold is the primary physical decomposition.** The arm starts
   straight and must move under bounded direct torque, then remain inside a
   1 cm ball for 2 s. This changes whether first decisions and diagnostics
   optimize complete success or only acquisition. It assumes the stationary
   target, 50 Hz sampling, and direct motor semantics
   (`scenario.md:9-20`; `two_joint_arm.xml:1-3, 30-33`;
   `environment.py:122-168`). First-entry time, terminal velocity, hold
   interruptions, and maximum held steps discriminate acquisition from
   stabilization.

2. **Kinematic feasibility is broad, but posture and conditioning remain
   consequential.** Official radii 0.06-0.20 m sit inside the two-link
   workspace, with two analytic IK branches represented in the observation.
   This can change decisions about branch-aware state/action representations
   and radius/angle-stratified analysis. It assumes the stated kinematics and
   active joint ranges (`two_joint_arm.xml:12-20`;
   `two_joint_arm.py:5-8`; `observations.py:18-49`). Joint solutions,
   Jacobian conditioning, branch occupancy, and action saturation by geometry
   are the discriminating evidence.

3. **The dynamic time scale is unresolved and may govern hold reliability.**
   Damping, armature, implicit inertia, and +/-5 nominal torque authority
   determine whether the controller can brake inside the tolerance at 50 Hz.
   This can change decisions about temporal abstraction, action representation,
   and whether failures should be attributed to dynamics or learning. It
   assumes native MuJoCo compilation of the XML
   (`two_joint_arm.xml:12-18, 30-32`). Compiled inertias, acceleration,
   saturation, and settling measurements resolve it.

4. **Official coverage and physical feasibility are different questions.**
   The robot can geometrically reach the full official annulus, but the
   current training range begins at 0.14 m rather than 0.06 m. This can change
   the first campaign decision about whether an official failure is a
   distribution-coverage effect or a control limitation
   (`task_spec.py:6`; `training/environment.py:14-19`). Radius-binned success,
   hold diagnostics, and effort/settling comparisons discriminate the causes.

5. **The binary criterion hides within-interval robustness.** Official success
   samples the distance every 20 ms and requires 100 uninterrupted samples;
   it does not independently test the ten internal integrations. This can
   change whether development evidence includes substep margin, while leaving
   the official success definition unchanged
   (`scenario.md:12-20`; `environment.py:130-159`). Substep distance and
   velocity traces would support or revise concerns about unobserved
   excursions.
