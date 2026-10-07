# Scientific model: two-joint arm reach-and-hold

This is the pre-campaign physical model. It distinguishes facts fixed by the
human-authored implementation from deductions and quantities that have not yet
been measured. There is no campaign evidence yet; all evidence named below is
either source code or a proposed discriminating observation.

## System boundary and coordinates

The robot is a planar two-revolute-joint serial arm. The shoulder and elbow
hinges rotate about the world z axis. The arm lies at z = 0.02 m, while its
motion is in the x-y plane. The target is a fixed mocap point sampled in that
same plane. Gravity is disabled, so this is not a gravity-compensation problem;
it is principally a commanded inertial, damped motion and stabilization
problem.

Let q = (q1, q2) denote shoulder and relative elbow angles. With link lengths
L1 = 0.12 m and L2 = 0.10 m, the end-effector position relative to the base is

    x = L1 cos(q1) + L2 cos(q1 + q2)
    y = L1 sin(q1) + L2 sin(q1 + q2)
    z = 0.02 m.

The relevant planar Jacobian is therefore

    J(q) = d(x,y)/d(q1,q2).

This relation is the mechanical bridge between joint control, Cartesian error,
and the hold requirement.

## Established facts

### E1. Morphology, geometry, and task distribution

The upper arm is 12 cm and the forearm is 10 cm. Each hinge declares a range
of -170 to +170 degrees. The end-effector site is at the forearm tip. The
official target radius is uniform from 6 to 20 cm and its angle is uniform over
the full [-pi, pi] range; the target is not sampled uniformly by area
(`contracts/robots/two_joint_arm.xml:12-20,25-27`;
`contracts/robots/two_joint_arm.py:5-7`;
`contracts/scenario.md:9-14`;
`robot_learning/scenario/environment.py:83-97`).

The target sphere is non-colliding, and the plane is non-colliding. The task
therefore has no grasp, contact, obstacle avoidance, or force-control
requirement. Success uses distance to the target mocap point, not overlap with
the visible sphere (`contracts/robots/two_joint_arm.xml:6-7,25-27`;
`robot_learning/scenario/environment.py:75-80`).

**Decision relevance:** The first campaign problem is full-angle Cartesian
reaching followed by stabilization, not contact-rich manipulation. Any
interpretation that attributes failure to collision, gravity, or object
interaction is inconsistent with the model.

**Assumptions:** The declared joint ranges are the intended compiled joint
limits, and the site and body frames have the usual MuJoCo interpretation.

**Discriminating evidence:** A model-introspection measurement of compiled
joint-limit flags, site position, and sampled target coordinates would support
these assumptions; a target z mismatch or active contact force would revise
the planar, non-contact model.

### E2. Initial state and episode timing

At reset, q = (0, 0), qdot = (0, 0), the model is forwarded, and then the
target is sampled. The initial end effector is at (0.22, 0, 0.02) m, the
arm's maximum radial extension. The arm state is deterministic across episodes;
only the target changes (`robot_learning/scenario/environment.py:102-120`;
`contracts/robots/two_joint_arm.xml:12-20`).

The MuJoCo integrator step is 0.002 s. Each policy action is clipped to
[-1, 1], held constant for 10 simulator steps, and replaced every 0.020 s.
The episode horizon is 500 control steps (10 s). A target distance of at most
0.01 m must be observed for 100 consecutive control steps, corresponding to
2 s (`contracts/robots/two_joint_arm.xml:2`;
`contracts/task_spec.py:6-11`;
`robot_learning/scenario/environment.py:55-58,122-168`).

**Decision relevance:** The initial displacement can be large and directional,
but there is no initial-momentum uncertainty. The policy must solve both
transient travel and a 2-second sampled hold within a 10-second budget. A
policy that reaches briefly is not a task solution.

****Assumptions:** The benchmark and shared environment use the stated frame
skip and post-frame-skip distance check. The phrase "continuous" in the task
contract is operationalized by consecutive control observations, not by
recording every intermediate solver state.

**Discriminating evidence:** A trace at all MuJoCo substeps versus control
boundaries would show whether substep excursions materially differ from the
authoritative sampled criterion; timing traces would support or revise the
effective 20 ms and 2 s values.

### E3. Actuation and simulator dynamics

Each joint has a direct MuJoCo motor with control range [-1, 1] and scalar gear
5. The policy action is passed through unchanged apart from clipping; no
additional controller, action scaling, or action delay is implemented
(`contracts/robots/two_joint_arm.xml:30-33`;
`robot_learning/scenario/policy_io.py:11-16`;
`robot_learning/scenario/environment.py:122-133`).

The joints have damping 0.5 and armature 0.01. Gravity is zero. The XML does
not explicitly state body masses or inertias, so MuJoCo derives them from the
geometries and compiled defaults. In generalized coordinates the local
mechanical picture is consequently

    M(q) qddot = tau_motor(q, action) - C_damp qdot - other_model_terms,

with the armature contributing to effective joint inertia. For the scalar
hinge transmission, gear 5 gives a bounded actuator contribution proportional
to the normalized command, but the resulting acceleration is configuration
dependent through M(q) and the coupled Jacobian.

**Decision relevance:** The action is torque-like bounded drive, not a desired
joint position. Damping removes velocity but does not make a command a
position servo. The 20 ms hold can produce overshoot or delayed correction,
especially when the policy changes branch or approaches the target with
velocity. Training outcomes must therefore be interpreted as closed-loop
trajectory and stabilization behavior, not as static inverse-kinematics
accuracy.

**Assumptions:** MuJoCo's compiled defaults provide the only omitted mass,
inertia, friction, and solver properties; there are no material contacts in
the task. The nominal motor transmission is the scalar gear interpretation.

**Discriminating evidence:** Runtime introspection of `body_mass`,
`body_inertia`, `dof_armature`, actuator moment, and solver settings, plus a
single-action step-response sweep, would establish torque-to-acceleration,
damping, settling time, and configuration dependence. Evidence of substantial
unmodeled friction, contacts, or actuator state would revise this dynamic
model.

### E4. Observation and action-state relationship

The observation has 11 values: q (2), qdot (2), the three-dimensional
end-effector-minus-target vector (3), and wrapped angular errors to the two
analytical inverse-kinematic branches (4). The target position itself is not
included as an absolute vector, but q plus the relative Cartesian error
determines it in this deterministic model. No force, acceleration, actuator
torque, contact, or intermediate-substep state is observed
(`robot_learning/scenario/observations.py:11-49`).

For target radius r, the observation computes

    cos(q2*) = (r^2 - L1^2 - L2^2) / (2 L1 L2),

then q2* = +/- acos(cos(q2*)) and the corresponding shoulder angle. Thus it
exposes errors to the elbow-open and elbow-folded solutions, with angular
wrapping to [-pi, pi]. The target is stationary after reset, and the policy
I/O layer has no action transformation or recurrent state in the current
implementation (`robot_learning/scenario/observations.py:18-35`;
`robot_learning/scenario/policy_io.py:11-16`;
`robot_learning/scenario/environment.py:83-97`).

**Decision relevance:** The controller receives enough nominal state to infer
the target-relative Markov state, but not enough to directly diagnose why a
hold failed. The four branch errors make the two-solution structure available
to learning, while qdot is essential for distinguishing position error from
unstable arrival. Lack of torque and substep sensing makes actuator saturation
and within-interval oscillation latent.

**Assumptions:** The model parameters used by the observation function match
the compiled XML, and target motion is zero after sampling.

**Discriminating evidence:** Compare observation-reconstructed target and
branch solutions against forward kinematics over the full task distribution.
Record actions, qdot, qddot, and substep distance alongside observations to
test whether failures are observable from the supplied state or arise from
unobserved transient dynamics.

### E5. Learning is shaped by distance and hold progress, but success remains
binary and uninterrupted

The current reward combines distance progress, an exponential closeness
potential, incremental hold progress, a small action cost, a penalty after
leaving the tolerance band, and a completion bonus. The environment terminates
only when the held-step count reaches the required 100 steps; reward does not
alter that physical success rule
(`robot_learning/training/reward.py:16-25,47-107`;
`robot_learning/scenario/environment.py:145-168`).

**Decision relevance:** A learned policy may be attracted to approach and
partial hold behavior without reliably completing the physical objective.
Learning curves or return therefore cannot substitute for complete-episode
success and phase-resolved mechanics. The relative value of reach versus hold
behavior is a learning-dynamics uncertainty layered on top of the robot's
physical dynamics.

**Assumptions:** The current reward implementation is the active training
signal, while evaluation uses the environment's termination and success
fields rather than reward total.

**Discriminating evidence:** Compare reward components with first entry,
maximum held steps, interruptions, and final success over episodes. If high
return reliably predicts uninterrupted completion, the reward is aligned in
practice; if not, its optimization target is physically misaligned with the
human goal.

## Physical consequences

### P1. The official radial task is reachable and avoids the two radial
kinematic singularities

The unconstrained two-link workspace is the annulus
|L1 - L2| <= r <= L1 + L2, namely 2 to 22 cm. The official 6 to 20 cm
interval lies strictly inside it. The open and folded elbow solutions are
distinct throughout this interval: q2 ranges approximately from +/-150
degrees at 6 cm to +/-49 degrees at 20 cm. The corresponding shoulder
offset has magnitude approximately 56 to 22 degrees. Hence both analytical
branches can be represented within the declared +/-170 degree joint ranges
for every target angle, with the largest shoulder magnitude occurring near
the angular wrap and remaining below about 158 degrees.

**Decision relevance:** A systematic failure across the distribution should
not initially be explained by unreachable targets. The likely physical
distinctions are trajectory generation, branch selection, control authority,
or hold stability. This supports evaluating by radius and angle rather than
treating all failures as equivalent.

**Assumptions:** The analytical planar equations apply, joint ranges are
active as intended, and the target is exactly in the arm plane.

**Sources:** `contracts/robots/two_joint_arm.xml:12-20`;
`contracts/robots/two_joint_arm.py:5-7`;
`robot_learning/scenario/observations.py:18-35`;
`robot_learning/scenario/environment.py:90-97`.

**Discriminating evidence:** Numerical IK enumeration over the official
radius-angle domain and compiled-limit checking support the claim. A failed
IK solution, a target z offset, or a concentration of failures only at the
radial limits would weaken or revise it.

### P2. Branch choice changes the transient without changing the endpoint

For most official targets, the two configurations have the same Cartesian
endpoint but opposite elbow bend. They have different joint paths from the
fixed initial straight configuration, different Jacobians, and potentially
different inertial coupling and actuator effort. A policy may also switch
between branch neighborhoods; wrapped angular errors can make such a switch
look like a large local angular transition even when Cartesian error is small.

**Decision relevance:** Endpoint distance alone cannot identify a poor
trajectory. Branch occupancy, branch transitions, joint path length, peak
speed, and action saturation can determine whether a candidate fails during
reach or during settling. This could change whether the first scientific
focus is representation/branch behavior or dynamic control.

**Assumptions:** The two solutions remain dynamically distinguishable under
the compiled inertias, and the policy uses the branch-error channels
meaningfully rather than ignoring them.

**Sources:** `robot_learning/scenario/observations.py:18-47`;
`contracts/robots/two_joint_arm.xml:12-20`;
`robot_learning/scenario/environment.py:122-143`.

**Discriminating evidence:** Per-episode q1, q2, qdot, action, Jacobian
condition, and branch-distance traces would support branch-conditioned
failure classes. Similar traces with no branch separation would weaken this
explanation.

### P3. Holding is a velocity and disturbance-tolerance requirement

At a static target configuration, gravity and target forces do not require
continuous nonzero torque, but residual qdot must decay before the Cartesian
error leaves the 1 cm ball. With damping 0.5 and bounded drive, an arrival
with excess momentum can cross the tolerance boundary repeatedly. Because an
exit resets the held-step counter to zero, one missed control sample discards
the entire accumulated hold (`robot_learning/scenario/environment.py:134-159`).

**Decision relevance:** The human objective weights convergence and
stabilization as heavily as reaching. Meaningful progress measures include
first entry, time to low speed, maximum uninterrupted hold, interruption
count, final distance, and qdot at first entry; success rate alone hides the
mechanism.

**Assumptions:** There are no external disturbances and the 1 cm ball is
centered on the mocap point. The action remains constant between control
updates.

**Sources:** `contracts/scenario.md:11-20`;
`contracts/task_spec.py:8-11`;
`robot_learning/scenario/environment.py:122-168`;
`contracts/robots/two_joint_arm.xml:2,13-18`.

**Discriminating evidence:** Distance and velocity traces through the full
2-second hold would support a settling-limited explanation; early entry with
low qdot but repeated exits would instead implicate discrete action timing,
branch switching, or an observation/control implementation mismatch.

### P4. Reach and hold are coupled by the finite horizon and actuator bound

The arm has 500 control opportunities, but the target may initially be far
from the 22 cm starting extension and at any angle. A fast approach consumes
the same bounded actuator authority that must later brake and stabilize. The
policy is not given a separate reach and hold controller, so a behavior that
optimizes only distance can trade settling margin for early arrival.

**Decision relevance:** A candidate can have good minimum distance and poor
episode success. Decisions about learning signals or controller structure
should be judged against complete episode outcomes and phase-resolved
kinematics, not minimum distance alone.

**Assumptions:** The motor's effective authority and inertia are in the
nominal compiled range, and no hidden controller changes the action semantics.

**Sources:** `contracts/scenario.md:9-20`;
`contracts/task_spec.py:7-11`;
`contracts/robots/two_joint_arm.xml:30-33`;
`robot_learning/scenario/environment.py:125-159`.

**Discriminating evidence:** Compare first-reach time, peak qdot, action
saturation, and subsequent hold interruptions over target geometry. A strong
relationship between fast entry and failure would support this coupling;
failure independent of approach speed would weaken it.

### P5. The training distribution is narrower than the official distribution

The current training environment samples radius 14 to 20 cm, while the
official task samples 6 to 20 cm. Both retain the full angular range
(`robot_learning/training/environment.py:10-19`;
`contracts/scenario.md:9-14`).

**Decision relevance:** Training evidence can overstate performance on the
near-base 6 to 14 cm region and cannot by itself establish the 98% objective.
Radius-stratified evaluation is needed to distinguish generalization from
training-distribution competence.

**Assumptions:** The current training environment is the active recipe and
the official evaluator preserves the contract distribution.

**Sources:** `robot_learning/training/environment.py:14-19`;
`contracts/scenario.md:9-14`.

**Discriminating evidence:** A paired panel stratified by radius, with the
same policy and seeds where possible, would support or weaken a radial
generalization explanation.

## Unknowns

### U1. Compiled mass, inertia, friction, and numerical response are not
specified explicitly

The XML gives link geometry, damping, armature, timestep, and motors, but not
explicit body mass or inertia. The runtime therefore supplies geometry/default
derived inertial quantities and solver behavior.

**Decision relevance:** These values determine acceleration, braking distance,
branch asymmetry, and whether the 20 ms action interval is dynamically coarse.
They could change whether a failure is scientifically a control problem or a
misunderstood simulator response.

**Assumptions:** MuJoCo compilation is deterministic and its defaults are
stable under the locked runtime described by the repository contract.

**Sources:** `contracts/robots/two_joint_arm.xml:1-3,12-20`;
`AGENTS.md` (locked MuJoCo runtime).

**Discriminating evidence:** Record compiled masses, inertias, damping,
armature, actuator moment, qacc, and free-response/action-step trajectories.
If measured response agrees with the nominal model, this unknown can be
retired; otherwise the scientific model must include the measured quantities.

### U2. The dominant failure phase and geometry are unknown

No campaign outcome exists to establish whether failures, once a policy is
available, will be caused mainly by slow reach, overshoot, branch selection,
near-base conditioning, near-outer-radius conditioning, or angular coverage.

**Decision relevance:** These alternatives lead to different first inquiries
and make different measurements decisive. Choosing among them from reward or
success rate alone would be underdetermined.

**Assumptions:** The existing evaluation diagnostics are recorded faithfully
and are not themselves a substitute for joint/action traces.

**Sources:** `robot_learning/scenario/evaluation.py:40-125`;
`contracts/scenario.md:18-32`.

**Discriminating evidence:** For each episode, retain target radius/angle,
first entry, minimum and final distance, in-tolerance steps, interruptions,
q/qdot, actions, and branch/Jacobian descriptors. Consistent phase- or
geometry-specific patterns would resolve the ambiguity.

### U3. It is unknown whether control-boundary observations hide harmful
substep excursions

The environment advances ten MuJoCo steps and then evaluates distance. The
implementation does not expose or score the nine intermediate positions.

**Decision relevance:** If substep excursions are common, a controller may
appear to hold under the task metric while having a physically oscillatory
trajectory; if they are absent, control-boundary diagnostics are sufficient.
This changes which physical quantity best predicts official success.

**Assumptions:** The protected assessment uses the same post-frame-skip
semantics described by the shared environment.

**Sources:** `contracts/task_spec.py:8-11`;
`robot_learning/scenario/environment.py:130-168`.

**Discriminating evidence:** Log distance and qdot at every simulator step
during successful and interrupted holds. Large hidden excursions support a
substep issue; close agreement weakens it.

### U4. The practical observability of actuator saturation and model mismatch
is unknown

The policy observes q, qdot, relative Cartesian error, and branch errors, but
not applied torque, qacc, or solver forces. A saturated action and a
low-authority unsaturated action can look identical in the observation until
their motion diverges.

**Decision relevance:** This determines whether behavior can be diagnosed from
policy-visible data alone or requires an external scientific trace. It affects
confidence in mechanistic explanations of slow reach and overshoot.

**Assumptions:** The action recorded by evaluation is the clipped command and
the simulator can expose actuator/generalized-force quantities without
altering the task.

**Sources:** `robot_learning/scenario/observations.py:37-49`;
`robot_learning/scenario/environment.py:125-133`;
`contracts/robots/two_joint_arm.xml:30-33`.

**Discriminating evidence:** Jointly record clipped action, actuator force,
qacc, and qdot over representative configurations. Persistent action bounds
with insufficient acceleration support an authority limit; low commands with
large motion error support a different explanation.

## Scientifically meaningful physical quantities

Across the complete behavior, the most informative quantities are target
radius and angle; initial, minimum, first-entry, and final Cartesian distance;
distance and velocity throughout the hold; q, qdot, qacc, action, actuator
force, and action saturation; time to first entry and time to low speed;
uninterrupted held-step length and interruption count; branch identity or
distance to each IK solution; Jacobian determinant/conditioning; joint path
length; and phase-resolved mechanical work or squared command. These quantities
separate endpoint reachability, trajectory quality, convergence, stabilization,
and sensing/actuation limitations. They are measurement targets, not claims
that any one is already causal.

## Decision-relevant synthesis

1. **Reachability is not the leading prior failure explanation.** The official
   6-20 cm annulus lies inside the 2-22 cm planar workspace, and both
   elbow branches are analytically available within the declared joint ranges.
   This depends on the planar site/target geometry and active limits
   (`contracts/robots/two_joint_arm.xml:12-20,25-27`;
   `robot_learning/scenario/observations.py:18-35`). Numerical IK and compiled
   limit inspection would revise it if any official target lacks a valid
   branch.

2. **Complete success is a stabilization problem coupled to approach.** Actions
   are bounded motor commands held for 20 ms; one post-frame-skip sample
   outside the 1 cm ball resets a 2-second hold
   (`contracts/task_spec.py:8-11`;
   `robot_learning/scenario/environment.py:125-159`). This assumes the shared
   sampling semantics are authoritative. Full q/qdot/action/distance traces,
   especially qdot at first entry and during interruptions, discriminate
   overshoot and slow convergence from other failure classes.

3. **The two IK branches are physically consequential alternatives, not just
   feature labels.** They have different joint trajectories, Jacobians, and
   inertial coupling despite the same endpoint
   (`robot_learning/scenario/observations.py:18-47`). This matters if failures
   cluster by branch or branch switching. Branch-conditioned traces and
   Jacobian/effort measurements support or weaken that interpretation.

4. **The simulator's effective dynamics remain a first-order uncertainty.**
   Damping, armature, gear, timestep, and geometry are specified, but masses,
   inertias, defaults, and solver response are not explicit
   (`contracts/robots/two_joint_arm.xml:1-3,12-20,30-33`). Any early decision
   that depends on control authority or braking must assume these compiled
   values. Runtime model introspection and action/free-response sweeps are the
   discriminating evidence.

5. **Current training evidence would not cover the official radial domain.**
   Training samples 14-20 cm while assessment samples 6-20 cm
   (`robot_learning/training/environment.py:14-19`;
   `contracts/scenario.md:9-14`). This matters whenever performance is
   attributed to the full task. Radius-stratified held-out measurements are
   the evidence that can support or falsify near-base generalization.

6. **Policy-visible observations are nominally state-sufficient but
   diagnostically incomplete.** q, qdot, relative target error, and both IK
   errors describe the deterministic target-relative state, but torque,
   acceleration, and substep motion are unavailable
   (`robot_learning/scenario/observations.py:11-49`). This matters whenever
   two failures have the same observed error but different dynamic causes.
   External traces of actuator force, qacc, and every simulator-step distance
   are the evidence needed to resolve that ambiguity.
