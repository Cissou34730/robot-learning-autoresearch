# Scientific model of the robot and task

## System boundary and physical state

**Established fact.** The simulated robot is a planar serial arm with two
revolute joints. The shoulder joint rotates about the world `z` axis at the
base; the elbow joint is a relative hinge about the same axis. The upper arm
has length 0.12 m and the forearm has length 0.10 m. The end-effector site is
at the forearm tip. The arm's plane is at `z = 0.02 m`. The base is fixed at
the world origin. The plane and target marker are non-contact geoms for this
task; success is based on site-to-target distance, not contact.

Let `q = (q1, q2)` denote shoulder and relative elbow angles. Forward
kinematics in the task plane are

```
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

Both joints have the range -170 to +170 degrees. The reset state is
`q = (0, 0)` with zero joint velocity. Thus the arm initially lies fully
extended along positive `x`, and the initial end effector is 0.22 m from the
base.

**Physical or scientific consequence.** Ignoring the joint limits, the
two-link workspace is the annulus from 0.02 m to 0.22 m. With the 170-degree
elbow limit, the smallest radius obtainable by maximum folding is about
0.0276 m; the largest is 0.22 m. The official target radii, 0.06 to 0.20 m,
therefore lie inside the available radial workspace. The shoulder and the two
elbow branches provide valid configurations across the sampled angular range;
for a typical interior target there are two inverse-kinematic configurations,
one with positive and one with negative relative elbow angle. The initial
fully extended configuration is a kinematic singularity: its instantaneous
Jacobian cannot produce radial motion to first order, so a general reach must
first involve coordinated reconfiguration rather than simply translating the
tip along the target ray.

**Unknown.** The implementation establishes geometric reachability, but not
which inverse-kinematic branch a policy will use, which path it will take, or
whether its finite-torque, discrete-time motion will reach and settle at every
target.

## Actuation, timing, and dynamics

**Established fact.** Each joint is driven by a MuJoCo motor with control range
`[-1, 1]` and gear 5. The policy action has two components, is clipped to that
range, and is passed through unchanged to the physical controls. In the
MuJoCo motor model this is a direct joint effort with a nominal gear-scaled
moment, so the control authority is bounded by approximately 5 torque units at
each joint. The XML specifies zero gravity, joint damping 0.5, and armature
0.01 for both joints. The simulator timestep is 0.002 s. One policy action is
held constant for 10 simulator steps, giving a 0.020 s control interval
(50 control decisions per second).

No external load, moving target, or gravitational torque acts on the arm. No
explicit body masses or inertias are written in the XML; MuJoCo consequently
constructs inertial properties from the modeled geometry and its defaults.
The arm links are capsules and the base is a cylinder. The target is a
kinematic mocap sphere and does not push on the end effector.

**Physical or scientific consequence.** The motion is a coupled two-joint
dynamical response, not an instantaneous inverse-kinematic assignment. The
same joint effort produces different Cartesian effects depending on `q`
through the Jacobian and on the configuration-dependent inertia. Joint
damping dissipates velocity, while armature increases effective resistance
to joint acceleration. During approach, effort must create and then remove
kinetic energy; during the hold, feedback must keep position error within the
small Cartesian disk without relying on gravity or contact to provide
restoring forces. Since the target is stationary and there are no sustained
external loads, a zero-velocity configuration can be statically maintained
without a nonzero gravity-compensation torque, but motion and disturbances
still require active control and damping.

The Jacobian of the planar tip position is

```
J = [ -0.12 sin(q1) - 0.10 sin(q1+q2),  -0.10 sin(q1+q2) ]
    [  0.12 cos(q1) + 0.10 cos(q1+q2),   0.10 cos(q1+q2) ]
```

Its rank and conditioning change with elbow configuration. Near extended or
folded postures, small joint changes can have poorly conditioned Cartesian
effects; away from those postures, the two joint coordinates independently
span the planar tip velocity more effectively.

**Unknown.** The source specifies the simulator equations and qualitative
parameters, but it does not reveal behavior such as transient overshoot,
settling time, velocity at tolerance entry, limit interaction, or the exact
effort needed along a particular trajectory. Those depend on the generated
inertial model, MuJoCo integration and constraint details, and the policy's
closed-loop actions.

## Target geometry and success process

**Established fact.** At reset, the target angle is sampled uniformly over
`[-pi, pi]` and its radius uniformly over [0.06, 0.20] m. Its `z` coordinate
is set to the end effector's plane, so the target is stationary and planar.
The measured error is the three-dimensional Euclidean distance from the
end-effector site to the mocap target; here its `z` component is zero, so it
is exactly planar distance. A control step is inside the tolerance when that
distance is at most 0.01 m.

After every 20 ms control interval, the environment updates a consecutive
inside-tolerance counter. Any outside sample resets that counter. Success is
termination after 100 consecutive inside samples, which represents 2 seconds.
Thus "continuous" is operationally continuity at the 50 Hz control samples;
the tolerance is not checked separately at each of the ten internal
2-millisecond integration steps. An episode otherwise ends after 500 control
steps, or 10 seconds. The official assessment uses 200 fixed-seed episodes and
requires at least 196 complete holds (98 percent).

**Physical or scientific consequence.** Reaching, tolerance entry, settling,
and sustained completion are one coupled control problem. A trajectory can
cross the target disk with too much velocity and leave it before the next
sample; a small static error can be acceptable while a small oscillation is
not, because either event breaks continuity. Conversely, a trajectory that
approaches slowly may have more opportunity to dissipate energy but must
still produce enough controlled displacement within the episode horizon.
Changing configuration, branch, or approach direction changes the Jacobian
and inertia, which changes how the same action affects both approach and
holding. The stage labels "not reached" and "interrupted hold" would describe
outcomes, not identify whether geometry, actuation, timing, or feedback caused
them.

**Unknown.** The implementation determines the exact binary success semantics
but not the distribution of actual approach times, tolerance-entry velocities,
hold excursions, or causes of an unsuccessful episode.

## Observation and control information

**Established fact.** The observation has 11 values:

1. the two joint positions `q`;
2. the two joint velocities `qdot`;
3. the three Cartesian components of end-effector minus target position; and
4. four wrapped joint-angle errors to analytic inverse-kinematic solutions:
   shoulder and elbow errors for the positive-elbow and negative-elbow
   branches.

The inverse-kinematic elbow angle is computed from the target radius using the
two-link cosine law, and the corresponding shoulder angle is computed from the
target bearing and the forearm offset. The cosine input is clipped before
`arccos`. Observations are produced after reset and after each ten-substep
action interval. The observation contains no explicit action history, hold
counter, acceleration, actuator effort history, or simulator integration
substep state.

**Physical or scientific consequence.** Joint positions and fixed morphology
are sufficient to reconstruct the absolute end-effector position. Combined
with the observed Cartesian error, they also determine the target position,
so target bearing and radius are not physically hidden even though they are
not separate observation fields. Joint velocities expose first-order motion
state, while the branch errors expose the relation of the current posture to
both kinematic solutions. The controller therefore receives the principal
instantaneous configuration, velocity, and target-error information needed
for feedback, but only at the 50 Hz decision rate.

The observation does not directly report acceleration, current torque after
clipping, model-generated constraint forces, or the unobserved motion between
decision samples. Such quantities must be inferred from successive
observations and known actions, and discrete sampling can make fast excursions
ambiguous.

**Unknown.** Whether the observation and action history are sufficient for a
particular policy to infer all practically relevant dynamic state, especially
during fast transients, cannot be established from the interface alone.

## Coupled capabilities and scientifically meaningful quantities

**Established fact.** The task requires bounded two-joint actuation to move
from the reset singular posture to a target-dependent configuration, regulate
Cartesian error, dissipate approach velocity, and maintain a continuous
100-sample tolerance streak. The benchmark measures only the resulting
complete-hold success, while the environment also exposes instantaneous
distance and held-step state.

**Physical or scientific consequence.** Meaningful quantities over the whole
behavior include joint angles and velocities; joint accelerations and applied
controls; proximity to joint limits; end-effector position, velocity, and
acceleration; radial and tangential target error; Jacobian rank or
conditioning; distance-to-target over time; time to first tolerance entry;
velocity and effort at entry; maximum excursion during the hold; longest
continuous inside streak; and control effort or energy. Together these
quantities distinguish geometric configuration, dynamic approach, convergence,
stabilization, and uninterrupted completion without treating a task-stage
label as a physical explanation.

**Unknown.** The human-authored implementation cannot determine the realized
values of those quantities for a learned policy, the branch or trajectory it
selects, or the physical mechanism behind any future success or failure.
