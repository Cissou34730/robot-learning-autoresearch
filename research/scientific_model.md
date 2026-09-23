# Scientific model of the robot and task

## Physical structure and reachable workspace

**Established fact.** The robot is a planar two-revolute-joint serial arm. The
shoulder and elbow axes are parallel to the world z axis, so both joints change
the arm's x-y configuration without changing z. The upper arm is 0.12 m long
and the forearm is 0.10 m long. The end-effector site is at the forearm tip.
Both joints have limits of -170 to +170 degrees.

**Physical or scientific consequence.** With shoulder angle \(q_1\) and
relative elbow angle \(q_2\), the end-effector position in the arm plane is

\[
x = 0.12\cos q_1 + 0.10\cos(q_1+q_2),\qquad
y = 0.12\sin q_1 + 0.10\sin(q_1+q_2).
\]

Ignoring the joint limits, the two-link workspace is the annulus from
\(|0.12-0.10|=0.02\) m to \(0.12+0.10=0.22\) m. The official target radii
of 0.06–0.20 m therefore lie strictly inside this geometric annulus rather
than at its singular outer or inner boundary. For a target radius in this
range, inverse kinematics gives two nominal elbow configurations,
\[
q_2=\mathord\pm\arccos\left(
\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}
\right).
\]
The elbow magnitude varies from about 49.5 degrees at 0.20 m to about
150.1 degrees at 0.06 m, within the joint limit. The two branches provide
elbow-up and elbow-down alternatives; shoulder limits can reject one branch
for some angular positions, but the branch separation and the target radii
leave a valid branch over the task annulus.

**Unknown.** The implementation establishes kinematic alternatives and
geometric reachability, but not which branch an observed or learned controller
will select, whether it will switch branches, or how close it will operate to a
joint limit.

## Actuation, timing, and dynamics

**Established fact.** Each joint is driven by a MuJoCo `motor` actuator with
control range [-1, 1] and gear 5. The environment clips each commanded
two-element action to this range, writes it to both actuator controls, and
holds it while advancing the simulator for 10 physics steps. The model
timestep is 0.002 s, so the policy acts at 0.020 s intervals (50 Hz).

**Physical or scientific consequence.** The action is a zero-order-held joint
motor command, not a desired joint position, velocity, or end-effector pose.
Under MuJoCo's motor semantics, the command produces a generalized motor
torque scaled by the gear, with nominal magnitude up to 5 actuator units per
joint before damping and inertial effects. The controller must therefore
coordinate torque over time to create both the required movement and the
counter-torque needed to remain inside a 1 cm Cartesian ball.

**Established fact.** Gravity is disabled. Each hinge has damping 0.5 and
armature 0.01. No explicit masses or inertias are specified in the XML;
MuJoCo derives body inertial properties from the modeled geoms and its
defaults. The plane, base, and target are non-colliding, and the target is a
mocap body.

**Physical or scientific consequence.** There is no gravitational sag or
gravity-induced direction asymmetry. Damping dissipates joint velocity and
armature adds reflected rotational inertia, so rapid commands produce
transient motion rather than instantaneous changes in configuration. Because
the action is held for 20 ms, the relevant closed-loop object is the
sampled-data arm: each command affects several internal integration steps
before the next observation and correction. Exact acceleration, settling time,
overshoot, and the effective torque-to-motion response depend on the derived
inertial quantities and the current configuration.

**Unknown.** The XML alone does not identify the resulting numerical masses,
full configuration-dependent inertia matrix, or the transient response of a
particular command sequence. It also does not establish how a controller will
trade speed against overshoot or residual oscillation.

## Initial state and task geometry

**Established fact.** At reset, both joint positions and velocities are set to
zero and MuJoCo is forwarded before sampling the target. The upper-arm plane is
at z = 0.02 m, so the initial end effector is at approximately
(0.22, 0, 0.02) m. The target is sampled with radius uniformly in [0.06, 0.20]
m and angle uniformly over [-pi, pi], then placed at the same z coordinate.

**Physical or scientific consequence.** The arm always starts fully extended
along +x, while the target can be anywhere on a complete planar annulus. The
initial end-effector-to-target distance can range approximately from 0.02 m
to 0.42 m. The controller must first solve a large-range planar repositioning
problem for targets with arbitrary direction, then transition from motion to
low-error regulation.

**Established fact.** An episode has at most 500 control steps. A step is
successful only when the three-dimensional end-effector/target distance is at
most 0.01 m, and success requires 100 consecutive successful control steps.
At 50 Hz this is a continuous 2 s hold. Leaving the tolerance region resets
the consecutive count.

**Physical or scientific consequence.** Reaching the vicinity is not
sufficient: the controller must establish a locally stable closed-loop
configuration whose Cartesian error remains below the tolerance for 2 s.
The tolerance is a small fraction of the link lengths, so joint errors are
converted into materially different Cartesian errors depending on
configuration. A transient crossing of the target, oscillation, or a small
uncompensated drift can prevent completion even after a geometrically valid
pose is reached.

## Required capabilities and physical solution classes

**Established fact.** The measured outcome is based only on the sampled
end-effector distance and the consecutive-hold rule. There is no contact,
grasp, obstacle, or force requirement; the target is not a physical object
that the arm must push or carry.

**Physical or scientific consequence.** The physical capabilities needed are:
planar gross reaching; coordinated shoulder/elbow trajectory generation;
handling of the two-link inverse-kinematics branch choice; approach with
sufficiently low residual velocity; and stabilization of Cartesian position
despite the arm's coupled dynamics. The last capability is distinct from
point-to-point reachability and dominates the final two-second requirement.

**Established fact.** The two inverse-kinematics signs for \(q_2\) describe
elbow-up and elbow-down solutions for the same target. The observation
implementation explicitly computes both corresponding desired joint
configurations and reports their wrapped joint residuals.

**Physical or scientific consequence.** A controller can solve the same
Cartesian task through different joint trajectories and terminal poses.
Branch selection changes the required shoulder/elbow motion, local
Jacobian, and dynamic response. Near the workspace's geometric boundaries
the branches approach each other or require large elbow angles, so the
configuration choice can affect conditioning even when the target remains
reachable.

**Unknown.** The implementation does not reveal which solution class is
actually used on any episode, whether a controller exploits branch symmetry,
or whether its trajectory is dynamically efficient or unnecessarily
oscillatory.

## Sensing and observability

**Established fact.** The observation has 11 float32 values: the two joint
positions, two joint velocities, the three-dimensional vector from the target
to the end effector, and four wrapped joint residuals. The residuals are the
current joint error relative to both the elbow-open and elbow-folded inverse
kinematic solutions. There is no sensor noise, delay, occlusion, or explicitly
hidden actuator state in the implementation.

**Physical or scientific consequence.** Joint configuration and velocity are
directly available, and the end-effector error is directly available. Since
the arm kinematics are known and the current end-effector position is
determined by the joint positions, the target's planar location is
reconstructible from the observation even though its absolute x-y coordinates
are not listed as separate fields. The target is fixed during an episode, so
the observation supplies the information needed for both feed-forward
configuration selection and feedback regulation. The wrapped residuals make
both nominal IK branches explicit, while the wrap operation represents
angular error on a circle rather than a Euclidean angle.

**Established fact.** The target and end effector share z, so the z component
of their relative displacement is zero after reset; the success distance is
nevertheless computed as a three-dimensional norm.

**Physical or scientific consequence.** The task's effective error dynamics
are planar, and success reduces physically to staying within a 1 cm disk in
the arm plane. The redundant z measurement does not provide an additional
control objective.

**Unknown.** Observability of the simulator state does not establish the
quality of a learned policy's internal prediction, its use of velocity, or
whether it has inferred a stable local model from the available signals.

## Constraints and scientifically meaningful quantities

**Established fact.** The hard constraints are the two joint ranges, bounded
motor commands, 20 ms control sampling, the 1 cm distance threshold, the
100-step uninterrupted hold, and the 500-step episode limit. The simulator
has no gravity and no task contact mechanics.

**Physical or scientific consequence.** Meaningful physical descriptions of
behavior should separate:

- Cartesian position error and its radial/tangential components;
- joint position and velocity, including distance to each joint limit;
- end-effector speed and acceleration during approach and hold;
- the chosen IK branch and branch switches;
- action magnitude, action changes, and implied joint torque;
- time to enter the tolerance region;
- maximum overshoot and longest uninterrupted in-tolerance interval;
- residual error and velocity during the 2 s hold; and
- sensitivity of the hold to target radius and angular direction.

These quantities distinguish geometric reachability from dynamic tracking and
stabilization, which the binary episode outcome intentionally combines.

**Unknown.** Without observing executions, the implementation cannot determine
the actual distributions of settling time, overshoot, hold robustness, branch
usage, joint-limit proximity, or action effort. Those are behavioral
properties, not consequences that can be inferred from the robot and task
definitions alone.
