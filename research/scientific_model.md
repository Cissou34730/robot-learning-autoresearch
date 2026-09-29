# Scientific model of the two-joint reach-and-hold system

The system is a deterministic, planar, torque-controlled two-link arm with a
stationary point target. The learned controller does not need to make contact
with or transport the target. It must steer the end effector into a small
three-dimensional distance ball and keep it there for the full hold duration.
Consequently, success is a coupled reach, braking, convergence, and
disturbance-free regulation problem rather than a point-reaching problem.

## Established facts

The human-authored model fixes the arm geometry, physical parameters, simulator
timing, observation contract, target distribution, and complete-hold outcome
semantics described below. These are repository facts; their behavioral
implications are kept separate in the Physical consequences register.

### Robot geometry and kinematics

The shoulder and elbow are revolute joints about the world z axis. The upper
arm length is 0.12 m and the forearm length is 0.10 m. Let `q1` be the
shoulder angle and `q2` the elbow angle relative to the upper arm. The end
effector position in the horizontal plane is

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)

Both joints have a stated range of -170 to 170 degrees. The arm plane is at
z = 0.02 m; the target is placed at that same height. The nominal
unconstrained workspace is the annulus from `|0.12 - 0.10| = 0.02 m` to
`0.12 + 0.10 = 0.22 m`, with the joint limits removing configurations near
some angular wrap boundaries.

At reset, `q1 = q2 = 0` and both joint velocities are zero. The arm is fully
extended along +x, so the end effector starts at `(0.22, 0, 0.02)`. The
official target has angle uniformly distributed over the full circle and
radius uniformly distributed from 0.06 to 0.20 m. This is uniform in radius,
not uniform in planar area. Every official target radius is inside the nominal
workspace; the target distribution is therefore not intended to contain
unreachable points, although legal inverse-kinematic branches can differ near
the joint limits.

### Actuation, dynamics, and timing

The XML uses two direct MuJoCo motor actuators. The policy action is clipped to
`[-1, 1]^2`, held constant for ten physics steps, and applied directly as the
two actuator controls. With gear 5, this gives a nominal joint torque of
`5 * action` in the corresponding generalized coordinate, subject to
saturation. There is no position or velocity servo between the policy and the
plant.

The physics timestep is 0.002 s and the policy control interval is 0.020 s
(50 Hz). The official two-second hold is therefore 100 consecutive
post-control-step tolerance observations. An episode can last at most 500
control steps. Gravity is zero. The moving upper-arm and forearm bodies
compiled from the XML have masses of approximately 0.099 kg and 0.052 kg.
Each joint has armature 0.01 and viscous damping 0.5 in MuJoCo's joint units.
The effective inertia seen at each joint varies with elbow configuration
because the links are coupled; velocity-dependent coupling is also present.
No task-relevant contact forces are modeled: the plane, base, and target
geometry are non-colliding for this task.

### Task outcome and controller information

After each ten-step integration burst, the simulator computes the Euclidean
three-dimensional distance between the end-effector site and the mocap target.
The official success condition is distance at most 0.01 m for 100 consecutive
control steps. A single outside sample resets the consecutive hold count.
Proximity, reward, and merely terminating at the time limit are not success.
The benchmark's operational check is at the control samples, even though the
physical intention is an uninterrupted two-second hold; excursions between
samples are not independently evaluated by the benchmark.

The observation has 11 values: the two joint positions, two joint velocities,
the three components of the end-effector-to-target displacement, and four
wrapped angular errors to the two analytical inverse-kinematic branches
(elbow-positive and elbow-negative). The target is stationary and there is no
observation noise, target velocity, contact sensing, force sensing, or
explicit actuator-state observation. Given the known base frame, joint
positions, and relative displacement, the target position is effectively
recoverable; the branch-error features additionally expose the geometry of
the two candidate solutions. Angle wrapping introduces a representation
discontinuity at the +/-pi boundary.

The current training reward is shaped by distance progress and closeness,
adds incremental hold-progress reward, charges a small action cost, and gives
a completion bonus. It is not the official outcome definition. In particular,
the current hold-exit forfeiture is zero, so partial or repeatedly interrupted
holds can be attractive to the reward while still being failures under the
task contract.

## Physical consequences

The arm begins at a kinematic singularity: at `q1 = q2 = 0`, the planar
Jacobian has rank one. An infinitesimal joint motion initially produces only
transverse end-effector motion; radial motion requires first creating an elbow
deflection. This makes the first part of a trajectory qualitatively different
from regulation near a non-singular target configuration. The controller must
choose a shoulder direction and bend the elbow before it can efficiently
change range.

For a target at planar polar coordinates `(r, phi)`, the two mathematical
inverse-kinematic branches can be written as

    q2 = +/- arccos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
    q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2)).

The official radius range gives elbow magnitudes of roughly 49 to 150 degrees,
so the target itself is away from the exact fully extended and fully folded
singularities. Both branches exist mathematically, but the shoulder limit can
remove one branch for some target angles. A policy can therefore solve the
same target with different elbow posture, path, velocity profile, and torque
history. It is not required to select the branch suggested by the observation
ordering.

The initial target distance is angle-dependent: it is
`sqrt(0.22^2 + r^2 - 2*0.22*r*cos(phi))`, ranging approximately from 0.02 to
0.42 m over the official distribution. The policy must infer direction and
range from the relative displacement and move from the extended singular
posture. Since the target has no orientation and does not exert forces, the
task has no grasp, collision-avoidance, or force-control requirement.

A successful trajectory needs more than inverse kinematics. It must generate
enough torque to accelerate the coupled links, avoid joint-limit interference,
then dissipate kinetic energy before entering the 1 cm ball. The 20 ms
zero-order-held command and torque saturation make this a sampled-data
regulation problem: a command that is appropriate for approach can cause a
post-entry overshoot. Near the target, damping helps remove velocity, but it
does not guarantee a hold if residual velocity carries the end effector across
the tolerance boundary. An ideal stationary configuration needs no sustaining
torque in this zero-gravity model; the difficult quantity to control is
therefore residual motion and its coupled correction, not static load.

The tolerance ball translates into different joint tolerances depending on
the Jacobian at the chosen solution. Tangential errors are generally
first-order in joint error, while radial sensitivity becomes poorly
conditioned near extended or folded postures. Thus equal end-effector
accuracy does not imply equal joint accuracy or equal control effort across
targets and IK branches. A policy can also remain successful while moving
inside the ball; zero velocity is physically sufficient but not required by
the benchmark. The decisive behavioral property is a 100-sample uninterrupted
streak, not the minimum distance reached.

The baseline training radius range is 0.14 to 0.20 m, while the official
range includes 0.06 to 0.20 m. A policy trained only on the baseline therefore
faces a systematic inner-radius and corresponding posture/conditioning shift
at assessment. This is a distribution issue, not evidence that the inner
targets are physically impossible.

## Unknowns

Before campaign evidence exists, the plant equations and nominal geometry are
known, but the learned closed-loop behavior is not. The important unresolved
quantities are:

- whether the policy reliably chooses a legal IK branch across the full angle
  range, especially where one branch approaches the shoulder limit;
- time to first enter the tolerance ball, approach overshoot, settling time,
  and residual end-effector speed at entry;
- the longest uninterrupted in-tolerance streak and the mechanisms of any
  interruption, separated by target radius, angle, and selected branch;
- how torque saturation, damping, configuration-dependent inertia, and the
  20 ms action hold interact during acceleration and braking;
- whether the policy has learned a genuine local regulator or only a
  repeated crossing/hovering behavior that receives shaped reward;
- sensitivity of the final hold to the one-centimeter boundary and to
  post-step versus between-step excursions;
- the distribution of joint-limit margin, action magnitude, action changes,
  joint velocity, end-effector velocity, and accumulated control effort over a
  complete successful or failed episode.

The scientifically meaningful record of a complete behavior is therefore not
just success percentage. It includes target radius and angle, joint trajectory
and branch identity, end-effector displacement and distance, time to first
entry, velocity and control during entry, longest consecutive hold, number of
interruptions, joint-limit margin, saturation, and the final distance. These
quantities distinguish unreachable or poorly conditioned geometry, inadequate
trajectory control, late braking, and failure to stabilize, without confusing
those mechanisms with the binary official verdict.
