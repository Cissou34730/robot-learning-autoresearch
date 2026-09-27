# Scientific model of the robot and task

## Embodied configuration and workspace

**Established fact.** The robot is a fixed-base, planar two-link arm. The
shoulder and elbow are hinge joints whose axes are both the world `z` axis.
The upper arm is 0.12 m long and the forearm is 0.10 m long; the end-effector
site is at the forearm tip. The arm moves in the horizontal `x-y` plane at
`z = 0.02 m`. Its configuration is
`q = (q_s, q_e)`, with two positions and two velocities. Each joint is limited
to `[-170, 170]` degrees. The base is fixed at the world origin.

**Physical or scientific consequence.** Ignoring the joint limits, the
end-effector position relative to the base is

```text
x = 0.12 cos(q_s) + 0.10 cos(q_s + q_e)
y = 0.12 sin(q_s) + 0.10 sin(q_s + q_e).
```

The ideal planar workspace is therefore an annulus from
`|0.12 - 0.10| = 0.02 m` to `0.12 + 0.10 = 0.22 m`. Official target radii
are 0.06–0.20 m, so they lie strictly inside this ideal outer boundary and
outside the inner boundary. The target plane is deliberately the same as the
arm plane, so the three-dimensional distance criterion reduces to planar
distance for these targets.

For a target `(x_t, y_t)` with radius `r`, the two geometric inverse-kinematic
branches are represented by

```text
q_e = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q_s = atan2(y_t, x_t)
     - atan2(0.10 sin(q_e), 0.12 + 0.10 cos(q_e)).
```

The observation implementation explicitly computes both signs. The official
radial interval makes the elbow angle range approximately 49.5–150.5 degrees
in magnitude, before joint-limit selection. Thus the arm can use
elbow-up or elbow-down geometry, although the shoulder limit can make one
branch inadmissible for some angular sectors. The full angular target range
therefore requires branch and angle-wrap handling rather than a single
fixed posture.

**Unknown.** The implementation determines which configurations are
kinematically available, but it does not determine which inverse-kinematic
branch a learned controller will use, whether it will switch branches, or how
close its trajectories will pass to a singular or joint-limit configuration.

## Actuation, timing, and dynamics

**Established fact.** Each joint is driven by a MuJoCo `motor` actuator with
gear 5 and control range `[-1, 1]`. The policy action has two components and
the current physical action mapping is the identity. The environment clips the
result to the actuator range and writes it directly to `data.ctrl`; there is no
position target, inverse-kinematics servo, or action interpolation in this
interface. In the loaded model, a unit control corresponds to a nominal
generalized motor torque of 5 in MuJoCo's hinge convention, with a maximum
magnitude of 5 per joint.

MuJoCo integrates at `0.002 s`. One policy action is held for 10 physics
steps, giving a `0.020 s` control interval and a 50 Hz policy update rate.
The target is a static mocap body during an episode. The model has zero
gravity. The plane and all listed geoms have collision disabled, so there are
no contact reactions, impacts, or frictional interactions with the plane or
target.

The XML specifies 0.5 joint damping and 0.01 armature for each joint. Loading
the model gives body masses of approximately 0.2011 kg for the base, 0.0990 kg
for the upper-arm body, and 0.0525 kg for the forearm body. The corresponding
local diagonal body inertias for the upper arm and forearm are approximately
`(1.683e-4, 1.683e-4, 1.081e-5)` and
`(6.110e-5, 6.110e-5, 3.674e-6)` kg m^2; the base inertia is
`(1.072e-4, 1.072e-4, 1.608e-4)` kg m^2. These inertial properties are
derived by MuJoCo from the specified geometry and model defaults. The target
body is mocap-controlled and its mass does not drive the arm.

**Physical or scientific consequence.** The motion is a coupled two-link
dynamical system. In schematic form its joint dynamics are

```text
M(q) q_ddot + C(q, q_dot) q_dot + D q_dot = tau,
```

with configuration-dependent link inertia and coupling, specified viscous
damping, armature inertia, and bounded motor torque. With gravity and contact
removed, damping and inertial coupling are the principal passive and
interaction effects. A command must create acceleration, then deceleration
and corrective torque; it does not instantaneously place the end effector at a
new point. The same torque authority, inertia, and damping that determine
approach also determine residual velocity and the ability to remain in the
tolerance region. A small endpoint error is consequently not equivalent to a
stable endpoint state.

**Unknown.** The code specifies the deterministic equations and parameters but
not the behavior of a particular policy: its transient duration, overshoot,
velocity at tolerance entry, actuator saturation, settling time, and steady
holding motion require observing the resulting trajectory.

## Initial state and target geometry

**Established fact.** Every official episode resets both joint positions and
velocities to zero and runs a forward update. The initial end effector is
`(0.22, 0, 0.02) m`, the fully extended, positive-`x` configuration. A target
is then sampled with angle uniformly in `[-pi, pi]` and radius uniformly in
`[0.06, 0.20] m`, and is placed at
`(r cos(theta), r sin(theta), 0.02)`. It remains fixed thereafter.

**Physical or scientific consequence.** The initial state is identical across
target draws except for the target displacement. The arm starts at its outer
kinematic radius with zero kinetic energy, while targets can occur anywhere
around the base and at radii both near and well inside the initial radius.
The initial endpoint error therefore combines radial and angular displacement;
targets on the opposite side require coordinated motion through a large
angular change. Because the target distribution is uniform in radius rather
than uniform in planar area, radial cases are not weighted by annular area.

**Unknown.** The implementation does not reveal the time or path a policy
will require from this common initial condition for any particular target
geometry.

## Observation and control loop

**Established fact.** The policy receives an 11-element, noiseless
`float32` observation containing:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional end-effector-minus-target vector; and
4. four wrapped angular errors, one for each shoulder/elbow pair in the
   open and folded inverse-kinematic constructions.

The target's absolute mocap coordinates, target velocity, joint acceleration,
actuator torque, contact force, and energy are not returned. The target is
static, and no sensor noise or delay is implemented. At each control interval
the policy maps the current observation to two bounded commands. The simulator
then advances ten substeps, after which the new state and endpoint error are
observed.

**Physical or scientific consequence.** Because joint position and velocity
are observed, the endpoint-to-target vector is observed, and the arm
kinematics are fixed and known, the policy has the state information needed to
reconstruct target geometry from the relative error and current configuration.
There is no hidden actuator state or moving-target state in this model. The
four branch errors make the alternative geometric solutions explicit, but do
not remove the need to choose a dynamically controllable branch. Unobserved
accelerations and torques must be inferred from successive observations and
the known dynamics.

The causal loop is therefore: observation of configuration, velocity, and
relative target geometry -> bounded joint torques held for 20 ms -> coupled
physical motion -> updated endpoint distance and observation -> task outcome.

**Unknown.** Whether this information is used effectively, and whether
discrete 20 ms updates are sufficient for a given policy to estimate and
counter residual motion, cannot be established from the observation contract
alone.

## Task outcome as a coupled behavior

**Established fact.** At every control step, success-progress state is updated
from the Euclidean endpoint distance. The endpoint must be at most 0.01 m from
the target. An inside step increments the current hold count; one outside step
resets that count to zero. An episode terminates only after 100 consecutive
inside steps, exactly 2.0 s at the official control interval. It truncates at
500 control steps, or 10 s, if that termination has not occurred. The official
assessment uses one frozen policy on 200 fixed-seed episodes and requires at
least 196 complete successes, or 98%.

**Physical or scientific consequence.** Success is one continuous embodied
process rather than independent reach and hold subtasks. The controller must
select a feasible configuration, move the endpoint into a 1 cm disk, reduce
or manage velocity sufficiently to avoid crossing the boundary, and maintain
the endpoint there for the full hold. An approach that enters quickly with
large residual velocity can be worse for the outcome than a slower approach
that leaves a stable state; conversely, damping that aids settling also removes
energy during approach and changes the torque needed to move. Joint coupling
means a correction at one joint can alter both endpoint position and the
other joint's required motion. Leaving the disk at any point makes the prior
partial hold non-successful, regardless of how close the endpoint was
previously.

**Unknown.** The implementation alone cannot establish the policy's actual
reach time, tolerance-entry count, longest uninterrupted hold, number of
boundary crossings, final distance, or success probability over the target
distribution. A label such as failure before entry or interrupted hold would
describe the observed trajectory, not identify its physical cause.

## Available alternatives and constraints

**Established fact.** The arm has two elbow-sign inverse-kinematic
configurations for ordinary targets in the official annulus, subject to the
`±170` degree joint limits. Joint angles are wrapped when branch errors are
formed, so equivalent angular representations must be handled consistently.
Actions are bounded, and there are no explicit joint-velocity or
joint-acceleration limits. The endpoint tolerance is finite but small relative
to the 0.22 m reach.

**Physical or scientific consequence.** Behavior can fall into qualitatively
different physical classes: a geometrically infeasible target would be
unreachable even with perfect control; a feasible but limit-constrained
configuration requires a valid branch and path; an approach can be
kinematically accurate but dynamically unsettled; and a settled approach can
still fail through a single boundary excursion. The official targets avoid
the ideal inner and outer workspace boundaries, but joint limits, Jacobian
conditioning, torque saturation, inertia, and damping can still shape the
motion used to reach them. These constraints are coupled, so a stage label
alone does not distinguish geometric, dynamic, or control causes.

**Unknown.** No current behavior class, branch preference, saturation pattern,
or dominant constraint can be inferred without trajectories. The code defines
the possible mechanisms, not their realized frequency or severity.

## Scientifically meaningful physical quantities

**Established fact.** The implementation exposes or permits calculation of
target radius and angle, joint positions and velocities, endpoint position and
error, action and implied actuator torque, distance-to-target over time,
inside/outside tolerance status, consecutive hold length, and episode
termination. The simulator additionally defines accelerations, generalized
forces, inertial coupling, and energy-related quantities.

**Physical or scientific consequence.** These quantities describe the complete
behavior without reducing it to a single success label: geometry and branch
choice describe where the task is posed; joint and endpoint trajectories
describe the motion; torque, saturation, velocity, acceleration, and damping
loss describe the dynamic effort; and distance histories, entry time,
boundary exits, and uninterrupted hold length describe convergence and
stability.

**Unknown.** Their values over actual policy trajectories, and the relationship
between any such quantity and episode success, are empirical properties of
the realized controller and are not determined by the human-authored
implementation.
