# Scientific model of the two-joint reach-and-hold system

## System model

The robot is a planar, two-revolute-link arm. The shoulder is at
`(0, 0, 0.02)` m and the elbow is at the end of a 0.12 m upper arm. The
0.10 m forearm carries the end-effector site, so both joints rotate about the
world z axis and the end effector remains in the horizontal plane
`z = 0.02` m. With shoulder angle `q1` and elbow relative angle `q2`, its
kinematics are

```
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

The joint coordinates are initialized to `q = (0, 0)` with zero velocity.
Thus the initial end-effector position is `(0.22, 0, 0.02)` m, the
fully-extended configuration. The target is a kinematic mocap point in the
same plane, not a physical object that can push the arm. At reset its radius
is sampled uniformly from 0.06 to 0.20 m and
its angle uniformly over the full circle; the target is then fixed for the
episode.

The policy emits two values in `[-1, 1]`. Each value is applied directly to a
MuJoCo motor for ten physics steps. The physics step is 0.002 s, so the
policy has a 0.020 s control period (50 Hz). An episode lasts at most 500
control periods, or 10 s. The end-effector-to-target Euclidean distance is
measured after each control period. Success requires distance at most 0.01 m
for 100 consecutive control periods, which is an uninterrupted two-second
hold; one sample outside the tolerance resets the hold.

## Established facts

* The two hinge joints each have a range of -170 to 170 degrees, damping
  `0.5`, and armature `0.01`. Gravity is disabled. The actuators are direct
  motors with control range `[-1, 1]` and gear `5`; there is no action
  smoothing in the scenario code.
* The visual plane, arm geoms, and target have collision disabled. Therefore
  the task has no contact, grasp, obstacle, or support interaction. The target
  does not exert a physical force on the arm.
* The official target annulus lies inside the ideal two-link radial workspace:
  `|0.12 - 0.10| = 0.02 m` through `0.12 + 0.10 = 0.22 m`. The official
  threshold is a disk around the target, not a joint-space or orientation
  condition.
* The observation has 11 values: the two joint positions, two joint
  velocities, the three-dimensional end-effector-to-target displacement, and
  four wrapped joint errors to two analytic inverse-kinematic configurations.
  The two configurations use positive and negative elbow angles. The
  displacement's z component is zero for official targets.
* The official final panel contains 200 independently seeded episodes. Its
  binary outcome is the only final criterion: at least 196 complete holds are
  required for 98 percent success.

## Physical consequences

### Kinematic reach and alternatives

For a target with planar radius `r` and polar angle `phi`, the two nominal
inverse-kinematic branches satisfy

```
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2)).
```

They are the elbow-open and elbow-folded alternatives encoded in the
observation. The official annulus excludes both the inner and outer
singular boundaries, so every official target has two distinct geometric
solutions before joint limits are considered. At 0.06 m the elbow magnitude
is about 150 degrees; at 0.20 m it is about 49 degrees. The associated
shoulder offset from the target direction is about 56 degrees and 22 degrees,
respectively. These offsets leave a shoulder-limit margin at the angular
seam, so the full official angular range has at least one, and generally two,
joint-limit-valid branches. A policy can therefore solve an episode by
choosing either elbow posture; it does not need to reproduce one canonical
joint configuration.

The arm starts at maximum extension, so targets toward the base require a
large elbow fold and targets on the opposite side require a broad shoulder
rotation. Targets close to the initial position can still require precise
braking because success is evaluated only after the held-control interval
begins. Uniform radius sampling is not uniform over planar area: inner and
outer radial bands receive equal radial probability rather than probability
proportional to circumference.

### Actuation and dynamics

The motor command is a generalized torque command scaled by the actuator gear,
nominally providing up to 5 torque units per joint before any physical
configuration effects. The command remains constant for 20 ms while ten
MuJoCo integrations occur. The armature adds configuration-independent
rotor-like inertia at each joint, while the link geometry contributes
configuration-dependent composite inertia. Damping removes velocity but also
means that motion and stopping behavior depend on the joint velocities at the
end of each control interval. With gravity and contact absent, a stationary
configuration does not need to counter a static load; the main stabilization
problem is to remove transient velocity and avoid injecting motion while
inside the tolerance disk.

The resulting control problem is therefore not merely inverse kinematics.
Actions change joint accelerations and then velocities over several
decision intervals, and the end-effector position is the integrated result.
The policy must choose a branch, drive the arm there, and shape the residual
motion so that the distance stays below 1 cm for 2 s. The arm can fail after
apparently successful reaching through overshoot, oscillation, action-induced
drift, or a single sample crossing the tolerance boundary.

The planar Jacobian has determinant magnitude
`0.12 * 0.10 * |sin(q2)|`. It becomes poorly conditioned near a straight or
fully folded posture, where joint motion produces little motion in one
Cartesian direction. Official targets avoid the exact singular radii, but the
inner targets use a strongly folded posture and the outer targets use a
partly extended posture. Consequently, Cartesian precision and the amount of
joint motion required for a one-centimeter correction vary with radius and
with the selected branch. Near a target, radial and tangential errors also
map differently through this Jacobian; a controller that only reduces scalar
distance can still produce unfavorable tangential velocity.

### Sensing, control, and outcome

The observation exposes the complete simulated joint position and velocity
state and the target displacement, so under the specified deterministic
physics it is sufficient to reconstruct the current physical state relevant
to control. It does not expose forces, accelerations, actuator effort, model
parameters, or a future target. The analytic branch errors make the two
candidate joint goals explicit, but they do not force the policy to select
one. Wrapped angular errors also preserve the circular nature of the joint
coordinates rather than providing an absolute unwrapped seam.

The causal chain is: the fixed target and current state determine the
observation; the policy maps that observation to motor commands; the
commands are held for 20 ms and advance the MuJoCo state; the new state
determines distance and whether the consecutive-hold counter continues.
Reward terms used during research training provide progress, closeness, hold
progress, completion, and action-cost signals, but none changes the official
physical success definition. The final benchmark evaluates the same
uninterrupted distance condition without using reward.

## Unknowns

The source model does not explicitly state the compiled composite masses,
center-of-mass locations, or full link and actuator inertia tensors. They are
therefore not yet quantified, even though they determine the torque-to-motion
gain and the transient settling time. The exact numerical conditioning of the
mass matrix across the workspace and the resulting effective acceleration
under saturated commands remain unresolved.

It is not known before measurement how much of the 500-step horizon is needed
for each target geometry, which IK branch a learned policy will use, or
whether branch choice changes success near the inner and outer radial
regions. Reachability is analytically available, but dynamic reachability
within the 10 s horizon and reliable one-centimeter stabilization are not
established.

The decisive behavioral quantities are likewise unknown: time to first enter
the tolerance disk, maximum overshoot, end-effector and joint velocity at
entry, settling time, distance margin during the hold, longest uninterrupted
inside run, number and timing of hold interruptions, action/torque magnitude,
and work or dissipation. These should be related to target radius, target
angle, selected IK branch, and local Jacobian conditioning rather than
reduced to final success alone. No campaign evidence yet supports a claim
about their distributions or about the probability of meeting the 98 percent
criterion.
