# Scientific model of the two-joint reach-and-hold system

This is the pre-campaign physical model. Statements in **Established facts** are
implemented or contracted repository facts. **Physical consequences** are
mechanistic implications of those facts, not campaign findings. **Unknowns** are
quantities that cannot be settled from the implementation alone.

## Established facts

- The robot is a planar two-link serial arm with two revolute joints. The
  shoulder and elbow axes are both the world z axis. The upper arm is 0.12 m
  long and the forearm is 0.10 m long, with the end-effector site at the
  forearm tip. The arm lies at approximately z = 0.02 m; the task target is
  placed in that same plane.
- Joint coordinates are shoulder angle `q1` and relative elbow angle `q2`,
  each nominally limited to -170 to 170 degrees. With link lengths `l1` and
  `l2`, the planar forward kinematics are
  `x = l1 cos(q1) + l2 cos(q1 + q2)` and
  `y = l1 sin(q1) + l2 sin(q1 + q2)`.
- In the ideal unconstrained planar geometry, the reachable radial workspace is
  the annulus from `|0.12 - 0.10| = 0.02 m` to `0.22 m`. Official targets have
  radius uniformly sampled from 0.06 to 0.20 m and bearing uniformly sampled
  over the full circle, so they are inside this nominal workspace. The
  finite joint limits change the margin to that workspace; at some bearings
  they may remove one of the two ideal inverse-kinematic alternatives, but the
  official target set remains nominally reachable.
- Reset deterministically sets `q = (0, 0)` and joint velocity to zero, then
  samples the target radius and bearing. The initial end effector is therefore
  at approximately `(0.22, 0, 0.02)` while the target is random.
- MuJoCo advances at a 0.002 s physics timestep. Each policy action is held
  for 10 physics steps, giving a 0.020 s control interval. The official
  2-second hold is consequently 100 consecutive control observations after
  stepping. An episode can last at most 500 control steps.
- Each action has two components in `[-1, 1]` and is passed directly to one
  motor per joint. Each motor has gear 5, so the nominal commanded joint
  torque is bounded by approximately +/-5 in simulator torque units. There is
  no position servo in the XML; the policy commands motor effort.
- Gravity is zero. The XML specifies 0.5 joint damping and 0.01 joint armature
  for both joints. The target is a non-contact mocap body, and the plane and
  target geometry are disabled for contact. The arm therefore has no modeled
  task interaction force to support or resist it.
- The observation has 11 values: the two joint positions, two joint
  velocities, the three-dimensional end-effector-minus-target vector, and four
  wrapped angular residuals to the open-elbow and folded-elbow inverse
  kinematic solutions. The action mapping is currently identity. There is no
  observation noise or explicit force, acceleration, actuator-state, time, or
  hold-counter measurement.
- After every control interval, success distance is evaluated as the
  three-dimensional end-effector distance to the target. A distance above
  0.01 m resets the consecutive hold count to zero. Success is only declared
  after one uninterrupted 100-step streak; the official assessment is 200
  independent seeded episodes and requires at least 196 successes.

## Physical consequences

The reset is not a neutral configuration. At `q2 = 0`, the arm is fully
extended and its planar Jacobian has determinant
`l1*l2*sin(q2) = 0`. Infinitesimal joint motion cannot produce arbitrary
instantaneous Cartesian motion there: lateral target motion first requires
folding the elbow, while the initial target can lie in any direction. This
creates a common initial maneuver consisting of breaking the singular
configuration, rotating the arm, and selecting a suitable elbow branch rather
than simply translating the end effector toward the target.

For a target radius `r`, ideal inverse kinematics satisfy

`cos(q2) = (r^2 - l1^2 - l2^2)/(2*l1*l2)`.

The official radial range corresponds approximately to `|q2|` from 49 to
150 degrees. The positive and negative solutions are elbow-open and
elbow-folded configurations. Where the joint limits admit both branches, the
same target can therefore be reached through two dynamically different paths.
The branch choice changes joint velocities, proximity to the +/-170 degree
limits, and the local Cartesian Jacobian even though the target position is
identical. Smaller target radii require a more folded elbow and approach the
folded-side joint limit; larger target radii approach the extended
configuration and its weaker lateral leverage. These margins also vary with
target bearing.

The target is reachable in position, but reaching is not the whole task.
Motor effort must first create joint motion, then remove angular velocity
before the end effector crosses the 1 cm boundary. Damping dissipates motion,
but the controller still has to regulate a two-joint coupled system: shoulder
torque affects both links, elbow torque affects only the distal link, and the
Cartesian error is a configuration-dependent combination of both. Saturation
can make the fastest path different from the easiest path to stabilize.

The 20 ms zero-order-held action is the effective control bandwidth. The arm
evolves for ten physics steps without a policy update, so a command that looks
appropriate at the start of an interval can produce an overshoot before the
next observation. Once the end effector is stationary at the target, zero
gravity and zero external force make that configuration an equilibrium under
zero motor effort; however, residual joint velocity or an incorrectly timed
command can carry it outside the tolerance. Thus the uninterrupted hold is a
convergence-and-stabilization requirement, not merely a reachability test.

The current observation is close to a Markov description of the task state.
The joint positions determine the end-effector position through the known
kinematics, and the Cartesian error then determines the target position
relative to that state. The four inverse-kinematic residuals expose both
position solutions explicitly. Nevertheless, the observation does not expose
the remaining hold time or previous boundary crossings, so a memoryless policy
must infer the correct behavior from current position and velocity alone. No
unmodeled disturbance is present to force active disturbance rejection; hold
failures should instead be interpretable through residual motion, command
timing, saturation, configuration, and numerical dynamics.

The meaningful physical trajectory is therefore the coupled sequence
`target -> joint configuration and velocity -> motor effort -> end-effector
error -> consecutive in-tolerance time`. A high success rate requires this
sequence to work across bearing, radius, and both feasible kinematic regions,
not only to produce a small minimum distance on selected targets. Useful
measurements over the complete behavior are target radius and bearing, joint
positions and velocities, commanded effort and saturation, end-effector
position and Cartesian error (including radial and tangential components),
time to first enter tolerance, minimum distance, maximum speed near the
target, longest uninterrupted in-tolerance streak, number and timing of hold
interruptions, and terminal distance.

## Unknowns

- The XML does not state link masses, body inertias, geom density, or the
  resulting coupled inertia matrix explicitly. Their effective numerical
  values, and hence acceleration and stopping distance under a saturated
  command, must be established from the loaded MuJoCo model or trajectories.
- The exact transient response from each bounded motor command is not known
  from the task description. In particular, the relative importance of motor
  authority, armature, damping, joint-limit behavior, and MuJoCo integration
  at the 20 ms control interval is unresolved.
- It is not known whether the dominant difficulty under the official
  distribution is initial singularity escape, long-distance reorientation,
  branch selection, near-boundary kinematics, terminal overshoot, or hold
  regulation. The implementation identifies these mechanisms as possible
  classes, but provides no evidence for their frequency.
- The stable basin around each inverse-kinematic solution is unknown: how much
  joint velocity can be present while remaining inside the 1 cm ball, and how
  much corrective authority remains after entry, depend on the effective
  dynamics and the learned feedback law.
- It is unknown whether the learned controller will consistently choose one
  inverse-kinematic branch or switch branches, and whether either choice causes
  systematic failures by target bearing or radius. The two branches are
  physically available, not evidence that either is preferable.
- The observation is mathematically sufficient for the modeled deterministic
  state under exact arithmetic, but the practical effects of scaling,
  normalization, finite policy precision, and the absence of an explicit
  hold state are unknown. No claim about learnability or 98% success follows
  from observability or nominal reachability alone.
- Before campaign measurements, the distribution of joint effort, velocity,
  Cartesian tracking error, settling time, hold interruptions, and failure
  geometry is unknown. These quantities are the necessary evidence for
  separating reach, convergence, and stabilization failures.
