# Scientific model of the robot and task

## Evidence convention

Each conclusion is separated into **Established fact**, **Physical or scientific
consequence**, and **Unknown**. Established facts come from the human-authored
MuJoCo model, environment, observation code, and benchmark contract. Consequences
are deductions from those facts. Unknowns require observing a controller or a
trajectory; they are not inferred here.

## Embodied mechanism and geometry

**Established fact.** The robot is a planar serial two-revolute-joint arm. The
shoulder and elbow axes are both the world `z` axis. The shoulder is the first
joint and the elbow is mounted at the end of the 0.12 m upper arm, so the elbow
angle is relative to the upper arm. The forearm is 0.10 m long and the
end-effector site is at its endpoint. Both joint positions are limited to
[-170, 170] degrees. The arm is located at `z = 0.02 m`; the plane, base
cylinder, and target are explicitly non-contacting. The upper-arm and forearm
geometries are capsules, with no external obstacle in the task.

**Physical or scientific consequence.** With joint coordinates
`q = (q1, q2)`, the end-effector position is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

The unrestricted two-link workspace is the annulus from 0.02 m to 0.22 m.
The joint limits trim that ideal workspace, but the official target radii
0.06-0.20 m remain inside the annulus and admit inverse-kinematic solutions
over the full target angle range. The end-effector orientation is not a task
variable; it is the sum `q1 + q2`.

For a target at radius `r` and angle `phi`, the two ordinary planar solutions
are represented by

```text
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))
```

when the resulting joint values satisfy their limits. Thus the same Cartesian
target can generally be reached with an elbow-open or elbow-folded posture.
The branches merge at full extension or full folding, where the planar
Jacobian loses rank.

**Unknown.** The controller's selected posture branch, path between postures,
and use of the available workspace are not determined by the implementation.

## Actuation and simulated dynamics

**Established fact.** The MuJoCo integration timestep is 0.002 s and gravity is
zero. Each action has two components and is held while ten MuJoCo steps are
integrated, giving a 0.020 s control interval (50 control decisions per
second). The action is passed through unchanged apart from clipping to [-1, 1]
and is assigned directly to the two motor controls. Each motor is attached to
one hinge with gear 5 and control range [-1, 1]. There is no explicit
position- or velocity-servo layer in the task environment.

**Physical or scientific consequence.** The action is a bounded torque-like
command, not a desired joint angle. With the MuJoCo motor gear, its nominal
joint torque authority is approximately +/-5 in the model's torque units.
Torque changes acceleration through the coupled two-link inertia, while
viscous joint damping of 0.5 and armature inertia of 0.01 are applied at both
joints. The action is therefore held open-loop for 20 ms at a time: the arm
can move, accelerate, and overshoot between observations even though the
controller only changes the command at control boundaries.

The XML specifies geometry rather than explicit body masses and inertias.
MuJoCo compiles the capsule and cylinder geometry using its model defaults;
the compiled model has approximately 0.0990 kg for the upper-arm body and
0.0525 kg for the forearm body. Their local diagonal inertias are approximately
`(1.68e-4, 1.68e-4, 1.08e-5)` and
`(6.11e-5, 6.11e-5, 3.67e-6)` kg m2, respectively. The effective generalized
inertia changes with elbow configuration because the links move together.
With gravity disabled, there is no gravitational torque to compensate; motion
is governed by actuation, configuration-dependent inertia, damping, and
velocity-dependent numerical dynamics.

**Unknown.** The action sequence required for a particular target, the actual
settling time, peak speeds, saturation duration, and the controller's ability
to reject residual motion cannot be established without observing behavior.

## Initial state and target geometry

**Established fact.** Reset sets both joint positions and velocities to zero,
runs forward dynamics, then samples an angle uniformly over `[-pi, pi]` and a
radius uniformly over [0.06, 0.20] m. The target is placed at
`(r cos(phi), r sin(phi), 0.02)`, matching the arm plane. The target's initial
position in the XML is therefore overwritten at reset. The initial end
effector is at `(0.22, 0, 0.02)` and is stationary.

**Physical or scientific consequence.** The arm starts fully extended along
positive `x`, while the target can lie anywhere around the base. The initial
distance is

```text
d0 = sqrt(0.22^2 + r^2 - 2 * 0.22 * r * cos(phi))
```

and ranges from 0.02 m for the nearest sampled boundary to 0.42 m for the
opposite outer boundary. A uniform radius is not a uniform distribution over
area: radial bands receive equal probability rather than probability
proportional to circumference. The initial posture is also a kinematic
singularity for radial motion: at `q2 = 0`, the end-effector Jacobian has no
first-order `x` velocity for either joint, although it has a nonzero tangential
direction.

**Unknown.** No physical conclusion about which target angles or radii are
harder for an eventual policy follows from initialization alone.

## Control, sensing, and observability

**Established fact.** The observation has 11 float32 values:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional vector from the target to the end effector;
4. four wrapped angular residuals, comparing the current joint angles with the
   two analytic inverse-kinematic branches (open and folded).

The target is a stationary MuJoCo mocap body. The observation directly exposes
joint configuration and velocity and exposes Cartesian target error. The action
mapping used by the environment is the identity, so the two policy outputs are
the two physical motor commands.

**Physical or scientific consequence.** The current joint state plus target
relative position is sufficient to reconstruct the instantaneous task geometry
and, with the known model, the end-effector position and Jacobian. The
branch-residual features provide a coordinate-aware representation of
alternative postures rather than requiring the controller to discover both
inverse-kinematic solutions from raw Cartesian error alone. Wrapped angles
identify angular differences modulo `2*pi`; the joint limits remove most but
not all general angular-coordinate ambiguity.

The observation does not contain the hold counter, previous action, actuator
torque, acceleration, contact state, or an explicit target velocity. The
target velocity is nevertheless known to be zero from the environment
mechanics, and the task provides no external obstacle or contact interaction.
Hold progress is therefore a temporal quantity not directly encoded in one
observation.

**Unknown.** Whether the available state representation is used consistently,
whether a policy exploits both branches, and whether unobserved history is
needed by a particular controller are behavioral questions.

## Task outcome and required capabilities

**Established fact.** After each 20 ms control interval, success distance is the
three-dimensional Euclidean distance between the end-effector site and target.
Distance at or below 0.01 m increments a consecutive hold counter; any sampled
distance above the threshold resets it to zero. A complete hold requires 100
consecutive control samples, equivalent to 2 seconds at the official timing.
An episode is capped at 500 control steps, or 10 seconds. The official
assessment uses 200 episodes from the fixed target distribution, and the
98 percent objective requires at least 196 complete holds.

**Physical or scientific consequence.** Successful behavior requires several
distinct capabilities:

- inverse-kinematic reaching from the fully extended start;
- trajectory control under bounded joint torques and 20 ms action holds;
- convergence of Cartesian position to a 1 cm ball;
- low enough residual joint and end-effector motion to remain inside that ball;
- maintaining the selected posture for the full hold interval.

The final requirement is a stabilization problem, not merely a point-to-point
reach. The official implementation samples the distance only after each block
of ten 2 ms integrations. Consequently, the authoritative hold is continuous
at the 20 ms control-sample sequence; an excursion between those checks is not
itself recorded by the success counter if both neighboring checked states are
inside.

**Unknown.** The implementation does not reveal the trajectory shape, whether
the controller reaches through the open or folded solution, how much margin it
maintains inside the 1 cm ball, or whether any hold is actually completed.

## Constraint classes and meaningful physical quantities

**Established fact.** The relevant hard constraints are the two joint limits,
the two bounded motor commands, the planar fixed-height geometry, the sampled
20 ms control loop, the 1 cm distance threshold, the uninterrupted 100-sample
hold, and the 500-step episode horizon. The plane, base cylinder, and target
have collision disabled, and the task contains no external obstacle requiring
avoidance or contact reaction.

**Physical or scientific consequence.** Qualitatively distinct states include
near-singular extended or folded configurations, configurations near either
joint limit, moving states with substantial kinetic energy, and settled states
with small Cartesian error but insufficient hold margin. The Cartesian
Jacobian, its conditioning, radial/tangential error decomposition, and
configuration-dependent generalized inertia distinguish these classes more
directly than distance alone.

Scientifically meaningful quantities for describing a trajectory are joint
positions and velocities; motor commands and saturation; end-effector position,
velocity, and target distance; radial and tangential target error; joint-limit
margin; Jacobian rank or conditioning; inverse-kinematic branch; time to first
enter the tolerance; longest consecutive in-tolerance streak; distance margin
through the hold; and motion or action effort during stabilization. These
quantities describe the physical relationship between observation, command,
motion, and the binary task outcome without assuming a particular controller
or cause of failure.

**Unknown.** Actual values of these quantities, their variation across target
geometry, and any empirical relationship to episode success require recorded
robot trajectories and are not determined by the human-authored system
definition.
