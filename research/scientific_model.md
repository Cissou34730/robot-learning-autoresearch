# Scientific model of the robot and task

## Physical system and geometry

**Established fact.** The robot is a fixed-base, planar, two-revolute-joint arm.
The shoulder and elbow axes are both the world `z` axis. The shoulder is at
approximately `(0, 0, 0.02)` m, the upper arm is 0.12 m long, and the forearm
is 0.10 m long. The end-effector site is at the forearm tip, so its nominal
height is 0.02 m. Joint coordinates are the shoulder angle `q1` and the elbow
angle `q2`, where the elbow angle is relative to the upper arm. Each joint is
limited to -170 to +170 degrees.

**Physical or scientific consequence.** Ignoring the angular limits, the
end-effector position is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

Thus the radial workspace is the annulus from 0.02 m to 0.22 m. The official
target radii, 0.06 to 0.20 m, lie inside this annulus rather than at its
kinematic boundaries. A target normally has two inverse-kinematic
configurations: an elbow-positive and an elbow-negative solution. The joint
limits remove configurations near the forbidden angular ends, so the available
branch must also respect both limits. The two branches are a genuine
alternative physical way to reach the same Cartesian target, not merely two
representations of one pose.

**Unknown.** The implementation does not state the actual compiled masses,
center-of-mass locations, or inertia tensors numerically. The capsule
geometries therefore supply inertial properties through MuJoCo's model
compilation defaults, but exact accelerations and torque-to-motion gains cannot
be obtained from the XML declarations alone.

## Actuation and dynamics

**Established fact.** There is no gravity (`gravity="0 0 0"`), and the base is
fixed. Each hinge is driven by a MuJoCo motor with control range [-1, 1] and
gear 5. The environment clips the policy command to that range and writes it
directly to `data.ctrl`. The joint damping is 0.5 and the joint armature is
0.01 for both joints. No task object contacts the arm: the target is a mocap
body, and the visible plane is non-colliding.

**Physical or scientific consequence.** A command is a bounded joint-motor
input, with nominal motor torque proportional to `5 * ctrl` in each hinge
(subject to MuJoCo's actuator dynamics and the compiled joint state). Since
there is no gravity or contact load, the arm is a free-space inertial system.
Damping dissipates motion, armature contributes reflected rotational inertia,
and the controller must supply torque to accelerate, decelerate, and hold
against residual velocity and inertial effects rather than against link weight.
Holding a Cartesian point is consequently a dynamic stabilization problem, not
just an inverse-kinematics pose selection.

**Established fact.** MuJoCo integrates at a 0.002 s physics step. The same
motor command is held for 10 physics steps, so the policy acts at 0.020 s
(50 Hz) intervals. The next observation is produced only after those 10
integration steps.

**Physical or scientific consequence.** The policy controls a sampled,
zero-order-held dynamical system. A command can create motion during the whole
20 ms interval before corrective information arrives. Reaching requires
coordinated shoulder and elbow timing; convergence requires reducing both
Cartesian error and joint velocity; stabilization requires commands whose
closed-loop effect remains inside a 1 cm region despite the delayed sampling
of the resulting state.

**Unknown.** The source defines the equations, limits, damping, armature, and
timing, but not the realized policy trajectory: peak velocities, saturation,
overshoot, settling time, and which inverse-kinematic branch is used require
observing a rollout.

## Initial condition and target geometry

**Established fact.** Every episode resets both joint positions and velocities
to zero. At that pose the end effector is at `(0.22, 0, 0.02)` m, the
straight, fully extended configuration. A target is then sampled with angle
uniform on `[-pi, pi]` and radius uniform on `[0.06, 0.20]` m. Its height is
set to the arm's plane, so the target and end effector are coplanar. The
target remains fixed throughout the episode.

**Physical or scientific consequence.** The starting pose is not a neutral
mid-range pose: it is the maximum-reach, zero-velocity pose. Initial Cartesian
distance ranges from 0.02 m (target directly inward at 0.20 m) to 0.42 m
(target directly behind the arm at 0.20 m). The controller must therefore
perform both small inward corrections and large reorienting motions. The
target distribution is uniform in radius and angle, not uniform in planar
area; per-unit-area sampling density is consequently higher at smaller
radii.

**Established fact.** The success distance is the three-dimensional Euclidean
distance between the end-effector site and mocap target, with threshold
0.01 m. The visible target sphere has radius 0.012 m but has no collision
semantics and does not define success.

**Physical or scientific consequence.** Because both bodies are constrained
to the same plane, the measured distance is effectively planar. The allowable
Cartesian set is a disk of radius 1 cm around the target. A trajectory that
passes through this disk but leaves it before the hold completes has not
solved the task.

## Required behavior and outcome semantics

**Established fact.** The end effector must be within the 1 cm disk for 100
consecutive control steps. At 0.020 s per control step, this is exactly 2 s.
One out-of-tolerance step resets the consecutive count to zero. An episode
truncates after 500 control steps (10 s), while reaching the hold count
terminates successfully immediately.

**Physical or scientific consequence.** Success has distinct phases:
reorientation and reach, deceleration and convergence, then uninterrupted
stabilization. Minimum distance alone is insufficient: a fast pass, a
near-target oscillation, or repeated entries into the disk can all fail the
complete task. The policy must regulate a bounded Cartesian error over a
longer interval than the arm's individual motion command interval.

**Unknown.** The implementation cannot establish how a learned controller
divides behavior between the two IK branches, how early it begins braking, or
whether any particular target angle or radius produces a particular trajectory.
Those are properties of the learned closed-loop behavior, not of the task
definition.

## Sensing and observability

**Established fact.** The policy receives 11 float values:

1. the two joint positions;
2. the two joint velocities;
3. the three-component vector from the target to the end effector; and
4. four wrapped joint-angle errors, consisting of shoulder and elbow errors
   to each of the elbow-positive and elbow-negative IK solutions.

The IK features are computed from the known link lengths using the target's
planar coordinates. The elbow solutions are `+acos(cos(q2))` and
`-acos(cos(q2))`; the corresponding shoulder angles are calculated
analytically. Angle errors are wrapped to `[-pi, pi]`.

**Physical or scientific consequence.** This is not raw visual sensing. It is
model-based state information: joint configuration and velocity are exposed
directly, while target geometry is supplied through a relative Cartesian
error and branch-specific desired-angle errors. Given the deterministic
kinematics, joint position plus the relative vector is enough in principle to
recover the target position relative to the base. The observation therefore
contains the information needed to choose a branch, move toward it, and
regulate motion, while avoiding the need to infer target location from images.
The relative `z` component should remain zero under the planar construction.

**Established fact.** The physical action mapping is the identity. The policy's
two outputs are the two joint commands, and no action smoothing or target
motion is added by the scenario interface beyond clipping and the 20 ms
zero-order hold.

**Physical or scientific consequence.** Observation, action, and outcome form
a direct feedback loop: the policy reads pose, velocity, and target-relative
error; applies bounded shoulder and elbow motor commands; the arm evolves for
20 ms; and the new end-effector distance determines hold continuation or
reset. The observation includes velocity, so stabilization can respond to
approach speed rather than position error alone.

**Unknown.** Although the physical state relevant to this deterministic model
is substantially exposed, the implementation alone does not reveal what
information a learned policy actually uses, whether it maintains a stable
internal branch choice, or whether its closed-loop state estimate is robust
near the joint limits and rapidly changing directions.

## Scientifically meaningful physical quantities

**Established fact.** The benchmark exposes distance, held-step count,
termination, and truncation; the model exposes joint positions and velocities,
target-relative Cartesian error, and the two IK error pairs.

**Physical or scientific consequence.** The most informative quantities for
understanding behavior are: target radius and angle; Cartesian distance and
signed planar error; time to first enter the tolerance disk; maximum and
terminal joint speed; peak and saturated motor commands; branch-consistent
joint error; overshoot and settling time; and the longest uninterrupted
in-tolerance interval. Together these separate reachability and branch choice
from transient control, convergence, and sustained stabilization.

**Unknown.** No source-level analysis can assign values to those trajectory
quantities or determine which one limits a particular episode. They belong to
the realized robot-policy interaction rather than to the physical task
specification.
