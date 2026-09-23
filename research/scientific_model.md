# Scientific model of the robot and task

## System and task definition

**Established fact.** The system is a planar two-link arm in the horizontal
`x-y` plane. The shoulder and elbow are revolute joints about the world `z`
axis. The upper arm has length 0.12 m and the forearm has length 0.10 m. The
end-effector site is the distal end of the forearm. The arm is mounted at the
origin at `z = 0.02 m`; the target is placed in that same plane. The target is
a stationary mocap body, not a physical obstacle or object to be grasped.

**Established fact.** The official target has an angle uniformly sampled over
the full circle and a radius uniformly sampled from 0.06 m to 0.20 m. The
radius is uniform in radius, not uniform in area. An episode permits at most
500 control steps. The end effector must be no more than 0.01 m from the target
at every checked control step for 100 consecutive steps. The control period is
0.02 s, so the required hold is 2 s. The final panel contains 200 independent
target episodes, and success is at least 196 complete holds.

**Physical or scientific consequence.** This is a reaching-and-stabilization
problem rather than an interaction problem: there is no target contact force,
collision event, or object dynamics to exploit. The controller must first
reduce Cartesian error and then keep a moving mechanical system inside a small
fixed-radius disk for a long interval. Since the initial state is outside the
disk, every episode requires a genuine approach before a successful hold.

**Unknown.** The implementation defines the task and dynamics but does not
determine which trajectories a learned policy will actually produce, which
inverse-kinematic branch it will use, or how much spatial or temporal margin it
will have during a hold.

## Morphology, kinematics, and workspace

**Established fact.** With joint angles `q1` (shoulder) and `q2` (elbow
relative to the upper arm), the end-effector position is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

Both joints are independently limited to `[-170, 170]` degrees. The arm has
two actuators for two joint coordinates, so it is fully actuated in its
configuration space, but each actuator is torque limited.

**Established fact.** Ignoring joint limits, the two-link workspace is the
annulus between radii `|0.12 - 0.10| = 0.02 m` and
`0.12 + 0.10 = 0.22 m`. The official radial interval lies strictly inside
that annulus. For a target radius `r`, inverse kinematics gives

```text
cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)
q1 = target_angle - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))
```

The observation implementation explicitly constructs both `q2 = +acos(...)`
and `q2 = -acos(...)` solutions.

**Physical or scientific consequence.** For the official radii, the two
solutions are generally distinct elbow-open and elbow-folded configurations.
They reach the same Cartesian point but have different joint angles, Jacobians,
velocity requirements, and configuration-dependent inertia. At a straight or
fully folded limiting configuration the branches merge and the Cartesian
Jacobian loses rank; the official radial interval avoids those exact workspace
limits, although a trajectory can still approach kinematic conditioning
boundaries. The shoulder limits do not remove the official circular target
set: at least one of the two branches provides a valid shoulder angle for each
official target direction.

**Unknown.** The implementation does not select a preferred branch or tell
which branch a policy will use, whether it will switch branches, or whether it
will take a direct or indirect path through joint space.

## Actuation and dynamics

**Established fact.** Each joint is driven by a MuJoCo `motor` actuator with
control range `[-1, 1]` and gear `5`. The policy action is passed through
unchanged, clipped to this range, and written to `data.ctrl`. Thus the
command is a bounded direct generalized motor command with a nominal
gear-scaled joint torque of `5 * action` per actuator. No actuator activation
dynamics, force filter, or command rate limit is declared.

**Established fact.** MuJoCo integrates at 0.002 s with gravity disabled. Each
policy action is held constant for 10 integration steps, giving a 50 Hz
zero-order-held control loop. Both joints have damping `0.5` and armature
`0.01`. The XML does not specify body masses or inertias explicitly; MuJoCo
derives them from the geoms and its default density. In the compiled model the
base, upper-arm, forearm, and target body masses are approximately
`0.2011`, `0.0990`, `0.0525`, and `0.00724` kg respectively. The plane, base, and target geoms have collision disabled. The link capsule
geoms retain MuJoCo's default collision settings, so any arm self-contact
permitted by the simulator's body-collision rules is distinct from contact with
the floor or target; the task supplies no external obstacle.

**Physical or scientific consequence.** With gravity and external contacts
absent, the mechanical evolution is determined by actuator torque,
configuration-dependent inertia and Coriolis effects, joint damping, armature,
any permitted link self-contact, and numerical integration. The same action
affects both the immediate joint acceleration and the velocity carried into
later control intervals. Damping dissipates motion but does not eliminate
overshoot when the bounded command has already created joint velocity. The
20 ms action interval is long relative to the 2 ms integration step: the
controller cannot correct within an interval, and the hold criterion only
samples the resulting state at control-step boundaries.

The arm is light and has no gravity load, but its effective joint inertia is
not constant: moving the forearm changes the shoulder's coupled inertia.
Torque authority and Cartesian authority also vary with posture through the
Jacobian. In particular, Cartesian motion in a direction associated with a
small Jacobian singular value requires large joint motion or is poorly
conditioned, subject to the torque and joint limits.

**Unknown.** Exact future motion under a policy action sequence is not
determined by the source description alone at the level of a behavioral
outcome: it depends on the realized sequence, numerical state evolution, and
the policy's timing. The implementation does determine the simulator dynamics,
but not the policy's velocity, acceleration, saturation, or settling profile.

## Initial state and task geometry

**Established fact.** Reset sets both joint angles and both joint velocities to
zero, forwards the model, and then samples the target. The initial end
effector is therefore `(0.22, 0, 0.02)`, with both links collinear along +x.
The target remains at `z = 0.02` and is sampled in `x-y` from its polar radius
and angle. The initial Cartesian distance is consequently

```text
d0 = sqrt(r^2 + 0.22^2 - 2 * r * 0.22 * cos(target_angle)).
```

**Physical or scientific consequence.** Initial difficulty is geometric as
well as dynamic: the arm always starts from one common stretched configuration,
while the target can be anywhere around the base and at several radii. The
minimum possible initial distance under the official range is 0.02 m, already
twice the tolerance; the maximum is 0.42 m for the farthest opposite-direction
case. The controller must infer the required direction and radius correction
from the initial state rather than from a reset-specific joint configuration.

## Capabilities required for success

**Established fact.** A successful episode requires the measured Euclidean
end-effector-to-target distance to be within 0.01 m at 100 consecutive
post-action checks. Any check outside the tolerance resets the hold counter to
zero. The episode terminates immediately on completion or truncates at 500
control steps.

**Physical or scientific consequence.** The required behavior has distinct
phases, even though the environment does not label them:

* **Reach:** choose a feasible joint configuration and move from the common
  initial state toward the target.
* **Trajectory control:** coordinate shoulder and elbow so that Cartesian error
  decreases without violating joint or torque bounds.
* **Convergence:** reduce residual position error below 1 cm, not merely pass
  near the target at speed.
* **Stabilization:** dissipate or counteract joint velocity so the end effector
  remains inside the tolerance disk.
* **Hold:** maintain the condition for 2 s despite the discrete action period.

A trajectory can therefore be geometrically successful at one instant yet fail
the task by crossing the tolerance boundary on a later checked step. The
success definition does not require a particular joint posture, path, reward,
or inverse-kinematic branch.

**Unknown.** No implementation-only analysis can establish the policy's
reaching time, settling time, hold margin, number of interruptions, or
distribution of completed versus truncated episodes.

## Sensing and observation

**Established fact.** The policy receives an 11-element vector containing:

1. the two joint positions `qpos`;
2. the two joint velocities `qvel`;
3. the three-dimensional vector from the end effector to the target; and
4. four wrapped angular errors from the current joints to the two inverse-
   kinematic solutions (one shoulder and elbow error for each branch).

Angles are wrapped to `[-pi, pi]`; the observation is represented as
`float32`. The action mapping in the current policy I/O is the identity.

**Physical or scientific consequence.** This is state-based sensing, not
vision. Joint configuration and velocity are directly observable, and the
relative Cartesian target vector supplies the task error. Together with the
known forward kinematics, these values contain the planar target position
needed for control; the four branch errors provide a redundant, task-oriented
representation of the same geometry. There is no hidden actuator state because
the declared actuators have no activation dynamics. The observation does not
directly expose torque, acceleration, contact force, prior action, or a target
trajectory.

The policy acts on an observation, and the action is then held for 20 ms while
MuJoCo advances the arm. The next observation contains the resulting joint
state and Cartesian error. The task outcome is computed from the resulting
distance, not from the policy's internal confidence or from the reward.

**Unknown.** The observation contract does not reveal which components a
learned policy actually uses, whether it internally reconstructs target polar
coordinates, or whether it relies primarily on direct Cartesian correction,
branch features, or joint-space feedback.

## Constraints and scientifically meaningful quantities

**Established fact.** The relevant hard constraints are the annular
two-link geometry, the two `+-170` degree joint ranges, bounded motor commands,
the 20 ms action hold, the 1 cm distance boundary, the 2 s uninterrupted
duration, and the 10 s episode limit. Gravity, floor/target collisions, and
external disturbances are absent from the declared task; possible link
self-contact follows the simulator's default arm-geometry rules.

**Physical or scientific consequence.** Behavior can be classified by
distinct physical boundaries: geometric reachability, joint-limit proximity,
Jacobian conditioning, torque saturation, residual velocity at target entry,
and tolerance-boundary crossings during the hold. These boundaries separate
reaching errors from stabilization errors without assuming that either occurs
for a particular policy.

Meaningful state and trajectory quantities are target radius and angle; joint
positions, velocities, and distance to joint limits; end-effector position and
velocity; radial and tangential Cartesian error; branch-specific joint errors;
commanded torque and saturation duration; minimum distance; first entry into
tolerance; settling time; longest uninterrupted in-tolerance run; number and
timing of hold interruptions; and final distance. These quantities connect the
observable state and bounded action to the physical outcome while respecting
the official success semantics.

**Unknown.** The source implementation alone cannot provide empirical values
for those trajectory quantities under a learned controller, nor identify which
constraint is active in any unobserved episode.
