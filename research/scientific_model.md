# Scientific model of the robot and task

## Embodied plant and geometry

**Established fact.** The robot is a fixed-base, planar two-revolute-joint arm.
Both hinge axes are the world z axis, so the motion plane is z = 0.02 m above
the world origin. The shoulder-to-elbow length is 0.12 m and the
elbow-to-end-effector length is 0.10 m. The base is fixed at the origin. The
shoulder and elbow ranges are both -170 to +170 degrees. The end effector is a
site at the distal end of the forearm; the target is a static mocap body.

With shoulder angle q1 and relative elbow angle q2, the end-effector
coordinates are

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
    z = 0.02

There is no gravity. The plane and target sphere are non-colliding, and the
task has no object contact or manipulation dynamics.

**Physical/scientific consequence.** The unconstrained two-link geometry has a
radial envelope from 0.02 m to 0.22 m. With the 170-degree elbow limits, the
smallest radius at the limiting fold is about 0.0276 m, while the maximum
remains 0.22 m. Joint limits also restrict which configurations realize each
point. The official target annulus, 0.06 to 0.20 m, is inside the arm's
geometric capability. For every official radius there are generally
configurations on both sides of the arm, and at least one of those branches
can keep the shoulder and elbow within their stated limits over the full
target angular range.

The fully extended initial posture is a kinematic singularity. At q1 = q2 =
0, the Jacobian has rank one: infinitesimal joint motion initially produces
tangential end-effector velocity but no first-order radial velocity. Radial
retraction therefore requires a finite reconfiguration rather than a
directly available infinitesimal motion along the initial target-to-end
effector line.

**Unknown.** The implementation determines the available configurations and
the singular geometry, but not which inverse-kinematic branch an actual policy
uses, which path it takes between branches, or how closely it approaches a
joint limit during an episode.

## Actuation, timing, and dynamics

**Established fact.** Each action has two components in [-1, 1]. The current
action mapping is the identity, and the environment clips the resulting
commands before writing them to the two MuJoCo motor actuators. Each motor has
gear 5, so a command corresponds to a bounded joint torque of approximately
5 times the command magnitude in the actuator's torque coordinate. This is
direct torque control, not a position or velocity servo. One action is held
constant for ten MuJoCo steps. The model timestep is 0.002 s, giving a 0.020 s
control interval and a 50 Hz policy loop. The official 500-step episode limit
therefore spans at most 10 s.

The joints have 0.5 N m s/rad damping and 0.01 kg m^2 armature. MuJoCo's
compiled model gives the upper-arm and forearm bodies masses of approximately
0.09896 kg and 0.05248 kg, respectively, with local planar inertias
approximately 1.68e-4 kg m^2 and 6.11e-5 kg m^2 about their transverse axes.
The base mass is approximately 0.20106 kg. These inertial quantities arise
from the capsule and base geometry under the simulator's compiled defaults.
The rigid-body inertia seen at the joints is configuration-dependent because
the two links are coupled. Joint ranges are active simulator limits.

**Physical/scientific consequence.** An action changes velocity and position
through the coupled two-link dynamics over a 20 ms zero-order-hold interval.
The shoulder must move the combined downstream mechanism, while elbow torque
changes the forearm configuration and also changes the shoulder's effective
inertia and end-effector lever geometry. Damping removes velocity in the
absence of continued drive. Because gravity and contact forces are absent, a
zero-velocity configuration can be a static equilibrium with zero command;
holding a target is therefore primarily a problem of entering the small
spatial band with sufficiently controlled residual motion and compensating for
action-induced motion, not of balancing a gravitational load.

The finite action interval and torque saturation make approach and
stabilization one coupled process. A command that is useful for reducing
position error can leave nonzero joint velocity at band entry; the same
velocity can carry the end effector outside the band on a later control
interval. Conversely, damping and small corrective torques can reduce that
motion, but their effect depends on configuration and the coupled inertia.

**Unknown.** The source defines the plant and its control authority, but it
does not determine the trajectory, peak velocities, settling time, torque
usage, or whether a particular policy reaches the target with enough dynamic
margin to remain inside the band.

## Initial state and target task

**Established fact.** Every episode resets q = [0, 0] and qdot = [0, 0], then
places the target at a newly sampled angle uniformly over [-pi, pi] and radius
uniformly over [0.06, 0.20] m. The target z coordinate is set to the current
end-effector z coordinate, so the three-dimensional distance is genuinely the
planar distance. The initial end effector is at (0.22, 0, 0.02) m. The target
does not move after reset.

The end effector must satisfy Euclidean distance <= 0.01 m from the target
for 100 consecutive control steps. At 0.020 s per step this is exactly 2 s.
Leaving the band resets the consecutive counter to zero. Success terminates
the episode; otherwise the episode is truncated at 500 control steps. The
official assessment uses 200 fixed-seed episodes and regards at least 196
successes as the 98 percent objective.

**Physical/scientific consequence.** The initial distance is determined by
both target radius and angle. In the target's outward initial direction it
can be as small as 0.02 m for the largest-radius target, whereas a target in
the opposite direction can be as far as 0.42 m. Thus the same plant begins
with different required amounts of retraction and angular reorientation.
The objective is not merely point-to-point reaching: the controller must
approach, enter a 1 cm disk, reduce or manage residual motion, and sustain
the entire 2 s interval without one sampled distance exceeding the
threshold. A crossing into the disk without a stable continuation is not a
successful task outcome.

**Unknown.** Reset logic specifies the distribution and state, but the
implementation alone cannot say how long an actual trajectory takes to first
enter tolerance, whether it settles before entry, how many times it exits,
or which target geometries produce which trajectories.

## Observation, control, and outcome

**Established fact.** The policy receives an 11-dimensional, float32 vector:

    [q1, q2,
     qdot1, qdot2,
     ee_x - target_x, ee_y - target_y, ee_z - target_z,
     wrap(q1_open - q1), wrap(q2_open - q2),
     wrap(q1_folded - q1), wrap(q2_folded - q2)]

Here `open` uses the positive elbow inverse-kinematic solution and `folded`
uses the negative solution. The shoulder values are computed from the target
angle and the corresponding elbow angle. The observation is built directly
from MuJoCo state; no sensor noise, filtering, or observation delay is
defined. The third relative-position component is structurally zero because
the target and arm share a plane. The target is not supplied as a separate
world-coordinate field, but its relative position is supplied and the model
and joint state are fixed and known.

The action is read once per policy step, clipped to the actuator command
range, and applied for ten simulator integrations. The resulting end-effector
distance is then measured. The success counter is updated from that measured
distance, so task outcome depends on the closed loop formed by observation,
torque, integrated motion, and threshold evaluation.

**Physical/scientific consequence.** Joint positions and velocities expose
the mechanical state needed to distinguish configuration from motion. The
relative target vector supplies Cartesian error, while the four inverse-
kinematic residuals explicitly represent the two alternative elbow branches.
Together, these signals make branch selection, approach direction, and
velocity-aware stabilization representable by the controller. The inverse-
kinematic residuals are partly redundant with the joint state and Cartesian
error, but they make the branch geometry explicit.

The observation is sufficient to reconstruct the target's planar location
from the known forward kinematics and the relative vector. It does not,
however, label an inverse-kinematic branch as preferred or guarantee that
both computed branch configurations are inside joint limits. The clipped
inverse-kinematic cosine also provides a numerical continuation for
out-of-envelope inputs, though official targets are inside the geometric
envelope.

**Unknown.** No actual policy behavior is established by the observation
definition. It remains unknown whether a policy uses joint-space or
Cartesian-space information, which branch it selects, how it uses velocity,
and whether its action sequence preserves tolerance for the required
duration.

## Alternative configurations and complete physical capability

**Established fact.** For a reachable non-singular target, the planar
two-link inverse kinematics generally offers two solutions: positive and
negative relative elbow angle. The observation computes both. The same
target can therefore be reached with an elbow-open or elbow-folded posture,
subject to the shoulder and elbow limits. The arm has no environmental
obstacle that would force one route, but its joint limits and the initial
fully extended singularity still constrain admissible motion.

**Physical/scientific consequence.** Reaching is coupled to configuration:
the selected branch changes the Jacobian, lever arms, joint velocities, and
the dynamic response to the same torque. Approach, convergence, and hold
cannot be treated as independent labels. A trajectory can have small
Cartesian error while retaining enough joint velocity to leave the tolerance
disk, and a branch/configuration that is statically valid can still require
different transient torque and damping behavior to enter it cleanly.
Sustained completion is the conjunction of spatial accuracy and temporal
continuity, evaluated at every 20 ms sample.

**Unknown.** The code does not reveal which alternative configurations are
used in actual episodes, whether a policy changes branch during motion, or
whether observed completion or interruption is caused by geometry, dynamics,
control timing, or another aspect of the trajectory. Those are behavioral
properties, not consequences that can be assigned from the task definition
alone.

## Scientifically meaningful physical quantities

**Established fact.** The implementation exposes or determines the quantities
needed to describe the full embodied process: target radius and angle, joint
positions and velocities, end-effector position, Cartesian error, inverse-
kinematic branch residuals, applied commands and corresponding bounded
torques, simulator time, distance-to-target, first tolerance entry, consecutive
held steps, interruptions, and final termination cause.

**Physical/scientific consequence.** Across a complete behavior, meaningful
measurements include the joint-space and Cartesian trajectory, radial and
tangential error, end-effector and joint velocity at first entry, peak and
settled velocity, time to first entry, longest uninterrupted in-tolerance
streak, total in-tolerance time, number and timing of exits, command
magnitude and variation, and proximity to joint limits or kinematic
singularities. These quantities connect the commanded torque to motion and
separate geometric reach, convergence, settling, and sustained hold without
assuming that a task-stage label identifies the underlying cause.

**Unknown.** Their values and distributions for any learned controller are
not specified by the human-authored robot and benchmark. The implementation
defines how such physical quantities relate to success, but only observed
trajectories can establish their actual values.
