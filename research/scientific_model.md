# Scientific model of the robot and task

## Embodied system

The system is a planar, two-link revolute arm simulated by MuJoCo. The shoulder
and elbow are the only generalized coordinates. Let `q1` be the shoulder angle
and `q2` the elbow angle relative to the upper arm. With link lengths
`l1 = 0.12 m` and `l2 = 0.10 m`, the end-effector position is

```text
p(q) = (l1 cos(q1) + l2 cos(q1 + q2),
        l1 sin(q1) + l2 sin(q1 + q2),
        0.02 m).
```

**Established fact.** Both joints rotate about the world z axis. Their ranges
are -170 to +170 degrees. The upper arm is 12 cm long, the forearm is 10 cm
long, and the end-effector site is at the forearm tip. The visual arm has finite
capsule radii, but the task uses the site position rather than a surface point.
The base, target, and plane have collision disabled; the target is a mocap body.

**Physical or scientific consequence.** The reachable position workspace of an
unlimited two-link arm is the annulus from 2 cm to 22 cm about the shoulder.
The official target radii, 6-20 cm, lie inside this annulus. The joint limits
still shape the angular workspace, but for this target annulus at least one
joint-limited inverse-kinematic configuration is available at every target
angle. The problem is therefore not target existence; it is selecting and
moving through a valid configuration while controlling the transient motion.

**Unknown.** The source does not establish which valid configuration a learned
controller will use, how often it will change configurations, or what paths it
will take between them.

## Kinematic structure and alternative configurations

**Established fact.** The observation code solves

```text
cos(q2) = (r^2 - l1^2 - l2^2) / (2 l1 l2)
```

and constructs both `q2 = +acos(cos(q2))` and
`q2 = -acos(cos(q2))`, with the corresponding shoulder angles. These are the
open and folded elbow branches. For radii from 6 to 20 cm, the magnitude of the
elbow angle is approximately 150 to 49 degrees, before considering the target
angle. The shoulder solution is wrapped when represented as an error, so
equivalent angular descriptions do not create an artificial discontinuity in
the supplied residuals.

**Physical or scientific consequence.** Except at the kinematic boundary where
the branches merge, the same Cartesian target generally has two postures.
They have different joint angles, Jacobians, link orientations, and dynamic
responses. A controller can approach the tolerance disk through either branch.
Near a singular straight-arm posture, small Cartesian changes can require
substantially different joint motions than they do in a well-conditioned
posture.

**Unknown.** The implementation does not determine which branch is dynamically
preferred for any target, nor whether a policy will consistently maintain one
branch during approach and hold.

## Initial state and task geometry

**Established fact.** Every official reset sets both joint positions and
velocities to zero, forward-solves the model, and then samples a fixed target.
The initial end effector is at `(0.22, 0, 0.02) m`, the fully extended
configuration. The target angle is uniform over `[-pi, pi]` and its radius is
uniform over `[0.06, 0.20] m`; its z coordinate is set equal to the arm plane.
The target is stationary after reset.

**Physical or scientific consequence.** The first action begins from the same
mechanical state but with a potentially large Cartesian displacement and a
target-dependent direction. The initial straight configuration is a kinematic
singularity: its planar position Jacobian has rank one, so the instantaneous
end-effector velocity initially has less directional freedom than a bent
configuration. Bending the arm changes that Jacobian and can create the
directional authority needed for the remaining approach.

The success region is the disk of center-to-center distance at most 1 cm around
the target. It is not the visible target sphere's radius and does not involve
contact. A control update represents 10 physics steps, so the policy interval is
`10 * 0.002 = 0.020 s`. Success requires 100 consecutive in-band updates,
which is 2 s, and an episode can last at most 500 updates (10 s).

**Unknown.** The reset implementation determines the initial state and target
distribution, but not the time or trajectory by which a particular controller
will enter the disk, nor whether it will remain there for the complete interval.

## Actuation and dynamics

**Established fact.** Each action has two components in `[-1, 1]` and is passed
unchanged to the two motor actuators after clipping. Each motor is attached
directly to one hinge with gear value 5, so the command is a bounded generalized
motor effort with a nominal magnitude of 5 in the joint torque units at full
scale. The command is held constant over the 10 MuJoCo integrations until the
next observation. There is no position-servo target, action-rate state, or
motor command filter in the human-authored model.

The world has zero gravity. Each joint has damping `0.5` and armature `0.01`.
The link capsules define the geometry from which MuJoCo derives body mass and
inertia because no explicit inertial elements are supplied. No task force is
applied by the mocap target.

**Physical or scientific consequence.** Joint acceleration is determined by
the coupled articulated inertia, motor effort, damping, armature, and any
active joint-limit constraints. Because the links are coupled, a torque at one
joint changes both the joint state and the end-effector motion, while the
other joint's motion changes the effective leverage. With gravity absent, a
stationary pose away from a joint limit does not need gravity compensation;
stabilization instead concerns residual velocity, actuator inputs, damping, and
discrete-time overshoot. A large effort can produce rapid approach but can also
leave kinetic energy that must be dissipated before a 1 cm hold is possible.

**Unknown.** The XML does not state the compiled numerical masses, inertias, or
constraint impulses explicitly, and it does not establish the transient torque,
velocity, or overshoot produced by a policy. Those quantities depend on the
compiled MuJoCo model and the action sequence.

## Control loop, observation, and information

**Established fact.** The policy observes an 11-element vector containing:
the two joint positions, two joint velocities, the three-dimensional
end-effector-to-target displacement, and four wrapped joint errors to the two
analytic inverse-kinematic branches. Observations are produced after each
20 ms action interval. There is no observation noise, delay, camera processing,
contact sensing, acceleration sensing, or direct target-position field in the
implementation.

**Physical or scientific consequence.** The current mechanical state is
proprioceptively available, and the relative Cartesian error supplies the
instantaneous task error. Given the known link geometry and current joint
positions, the policy can reconstruct the end-effector position and therefore
the target position from the relative displacement, even though the target
coordinates are not sent as a separate field. The target is fixed, so there is
no hidden target dynamics to estimate. Joint velocities expose motion relevant
to convergence and settling, while the branch residuals expose alternative
posture goals but do not force either one to be selected.

The observation-action-state relationship is therefore a sampled feedback
loop: an observation describes `q`, `qdot`, and target error; the action applies
joint efforts for 20 ms; MuJoCo advances the coupled state at 2 ms resolution;
the resulting end-effector distance determines the next observation and whether
the hold streak continues.

**Unknown.** The implementation establishes what is observable, but not whether
the learned policy uses all of it, how it resolves angular ambiguity, or how
robustly it converts error and velocity information into bounded effort.

## Coupled success process and behavior classes

**Established fact.** Approach, tolerance entry, and hold are evaluated from the
same sequence of end-effector distances. Entering the 1 cm disk increments a
consecutive counter; one sample outside resets it. The official benchmark
declares success only when the counter reaches 100 before the 500-step limit.
The protected benchmark does not use a reward to redefine this outcome.

**Physical or scientific consequence.** Reaching is a trajectory problem, not
just a static inverse-kinematics problem. The controller must generate a
reachable path, reduce position error, reduce enough joint motion to avoid
leaving the disk, and maintain the end effector inside the disk despite
sampled actuation. A capability change can affect another capability: greater
acceleration can shorten approach time while increasing settling demand;
choosing a posture with a different Jacobian changes both Cartesian control
authority and the effort needed to correct motion; and residual velocity at
entry can turn an apparently accurate reach into an interrupted hold. These
are coupled physical consequences, not separate causal diagnoses.

The principal qualitative behavior classes are: motion that remains outside
the tolerance disk; entry followed by exit due to residual motion or control
error; intermittent entries with repeated counter resets; and a sustained
in-band trajectory. The labels describe observable trajectories and do not by
themselves identify whether kinematics, dynamics, control sampling, or
configuration choice produced them.

**Unknown.** No policy trajectory or behavioral evidence is available in this
preliminary model, so the prevalence of any class, the attained success rate,
and the cause of any future unsuccessful episode are undetermined.

## Scientifically meaningful physical quantities

For a complete behavior, meaningful quantities include target radius and angle;
joint positions, velocities, and proximity to joint limits; end-effector
position and Cartesian error; the Jacobian and its conditioning along the path;
commanded effort and effort saturation; path length, speed, acceleration, and
settling motion; time to first tolerance entry; minimum distance; longest
continuous in-band duration; number and timing of tolerance exits; and the
final distance. These quantities connect the sampled observations and actions
to the continuous physical trajectory and to the binary hold outcome.

**Established fact.** The environment directly records distance, held-step
count, termination, and truncation, while the remaining quantities are defined
by the model state, geometry, and applied controls.

**Physical or scientific consequence.** Together they distinguish geometric
reachability, transient trajectory control, convergence, and sustained
stabilization without treating a stage label as a physical explanation.

**Unknown.** Their realized values over the official target distribution cannot
be known without observing action-state trajectories; no such behavioral
measurements are used here.
