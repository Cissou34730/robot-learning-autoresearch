# Scientific model of the robot and task

## Physical system

**Established fact.** The robot is a fixed-base, planar serial arm with two
revolute degrees of freedom. The shoulder joint angle is `q1` and the elbow
joint angle is `q2`; both rotate about the world z axis. The upper arm has
length `L1 = 0.12 m` and the forearm has length `L2 = 0.10 m`. The arm lies in
the horizontal plane `z = 0.02 m`. The end-effector site is at the distal end
of the forearm. Both joints have declared limits of -170 to 170 degrees.

The end-effector position is therefore

```text
x = L1 cos(q1) + L2 cos(q1 + q2)
y = L1 sin(q1) + L2 sin(q1 + q2)
z = 0.02 m.
```

The base is fixed; there is no base translation or rotation state available to
the controller. At reset, `q1 = q2 = 0` and both joint velocities are zero.
The arm is then fully extended along positive x, so the end effector starts at
`(0.22, 0, 0.02)`.

**Physical or scientific consequence.** With unconstrained joint angles, the
planar workspace is the annulus between radii `|L1-L2| = 0.02 m` and
`L1+L2 = 0.22 m`. Joint limits remove only configurations near certain
orientations. The official target annulus, 0.06 to 0.20 m, is inside the
geometric workspace. Every target direction in that annulus has at least one
inverse-kinematic configuration compatible with the declared joint limits.

The reset configuration is a kinematic singularity. Its end-effector
Jacobian is

```text
J(0, 0) = [[0,    0   ],
            [0.22, 0.10]] m/rad.
```

Thus an infinitesimal joint velocity initially produces tangential motion but
no first-order radial motion. Moving from the fully extended reset state to a
target with a different radius requires the arm first to leave this
singularity. Targets near 0.20 m require relatively extended configurations;
targets near 0.06 m require relatively folded configurations. The Jacobian
also becomes poorly conditioned as the elbow approaches either collinear
configuration, so the same Cartesian error does not have the same joint-space
or velocity implications throughout the task.

**Unknown.** The implementation determines which configurations are
kinematically available, but not which inverse-kinematic branch a policy will
use or whether its motion will remain within one branch. Actual trajectories,
joint-limit interactions, and realized approach behavior require observing the
robot.

## Actuation and dynamics

**Established fact.** Each joint is driven by a MuJoCo motor with control range
`[-1, 1]` and gear `5`. The policy action is passed through unchanged and then
clipped to this range. In the current model this is a direct torque-like
command: a scalar command of magnitude one produces an ideal generalized
motor torque of up to approximately 5 N m, subject to the simulated dynamics.
There is no position servo, action filter, or separate actuator state in the
human-defined model.

MuJoCo integrates at 0.002 s with gravity disabled. Each policy action is held
constant for ten integration steps, giving a 0.020 s control interval. The
controller consequently acts at 50 Hz, observes the state only at those
intervals, and cannot change the torque during the ten internal steps.

Each joint has viscous damping `0.5` and armature inertia `0.01` in the
compiled model. MuJoCo's compiled masses are approximately 0.099 kg for the
upper-arm body and 0.052 kg for the forearm body; the fixed base is
approximately 0.201 kg. The capsule radii are 0.015 m and 0.012 m. The
resulting link inertias, together with the armature, determine the angular
acceleration produced by a commanded torque. The shoulder and elbow dynamics
are coupled because elbow motion changes the forearm's position relative to
the shoulder.

The plane and target are non-contacting in the XML. The target is a mocap body
whose position is set externally; it is a visual reference, not an object the
arm can push or grasp. There is no gravity, payload, frictional contact, or
external disturbance in the defined task.

**Physical or scientific consequence.** A command changes joint acceleration
through the configuration-dependent inertia matrix, then damping removes
velocity over time. Since there is no gravity, holding a static configuration
does not require gravity compensation. It does require avoiding or dissipating
residual joint velocity, and it can require opposing torque while the arm is
moving. Large torque can produce rapid approach but can also create momentum
that must be removed before the end effector can remain in the small target
region. Damping helps dissipate motion but also changes the response speed.

The discrete 20 ms action interval is long compared with the 2 ms integration
step but short compared with the 2 s hold. The simulator resolves the
continuous dynamics within each interval, while success is sampled only after
each ten-step action application. A 500-step episode represents at most 10 s
of simulated control time.

**Unknown.** The model specifies the deterministic response to a given state
and command, but the implementation alone does not reveal the commands a
learned policy will generate, its velocity profile, or how much torque and
energy it will use. It also does not establish any empirical settling time or
robustness to numerical or control discretization effects.

## Target geometry and success

**Established fact.** For each episode, the target angle is sampled uniformly
over the full range `[-pi, pi]`, and its radius is sampled uniformly from
0.06 to 0.20 m in the official task. The radius is uniform, rather than
uniform area density in the plane. The target z coordinate is set equal to
the end-effector z coordinate, so the task distance is genuinely planar even
though it is computed as a three-dimensional Euclidean norm.

The target tolerance is the closed ball

```text
||p_end_effector - p_target|| <= 0.01 m.
```

After every 20 ms control interval, the environment increments a consecutive
hold counter if this condition is true and resets it to zero otherwise.
Success occurs on the 100th consecutive in-tolerance control step, which is
2.0 s. Leaving the tolerance even once restarts the hold. An episode can also
truncate at 500 control steps, but truncation is not success.

The official final assessment uses 200 fixed-seed episodes from this
distribution. Its outcome is the fraction of episodes with a complete
uninterrupted hold; 196 or more successes corresponds to the stated 98%
criterion. The training environment shown in the human-authored code samples
the narrower 0.14 to 0.20 m annulus, while the protected official benchmark
uses the full 0.06 to 0.20 m annulus.

**Physical or scientific consequence.** Approach, tolerance entry, settling,
and sustained completion are one coupled control problem. Crossing the
tolerance boundary is insufficient: the end effector must have a position and
velocity evolution that remains inside the 1 cm region for 100 observations.
Cartesian tolerance corresponds to different joint tolerances at different
configurations through the Jacobian. Near an extended or folded
configuration, a small Cartesian displacement can require a comparatively
large or directionally sensitive change in joint coordinates. Conversely,
small joint motion can produce substantial tangential end-effector motion in
other configurations.

For a target at polar angle `theta`, the two geometric inverse-kinematic
branches are represented by

```text
q2 = +/- acos((r^2 - L1^2 - L2^2) / (2 L1 L2)),
q1 = theta - atan2(L2 sin(q2), L1 + L2 cos(q2)).
```

Across the official radial range, the magnitude of `q2` is approximately 49.5
to 150 degrees. These are the elbow-open and elbow-folded alternatives. The
joint limits can exclude one branch for some target orientations, while the
other branch remains available. Switching between branches is itself a
substantial joint-space maneuver and is not required by the geometry when a
valid branch is maintained.

**Unknown.** The target distribution and success test specify what is
measured, not how a policy will trade approach speed against settling or
whether it will use the open or folded solution. They do not identify the
cause of an unsuccessful episode from a task-stage label alone.

## Observation, action, and task outcome

**Established fact.** The policy receives an 11-dimensional observation:

1. the two joint positions `q1, q2`;
2. the two joint velocities;
3. the three-dimensional vector from the target to the end effector;
4. four wrapped angular residuals, comparing the current joint angles with
   the open and folded inverse-kinematic solutions.

The action is a two-dimensional vector in `[-1, 1]^2`, mapped identically to
the two motor controls. The environment clips it, writes it to `data.ctrl`,
integrates ten MuJoCo steps, computes the new end-effector-target distance,
updates the hold state, and returns the next observation.

The joint state and end-effector-target vector provide the physical state
needed to reconstruct the current target relation and arm configuration. The
inverse-kinematic residuals are derived features that expose both geometric
solutions and their wrapped angular errors. The target is static during an
episode, so target velocity is not a missing dynamic input.

The observation does not contain joint acceleration, commanded torque,
contact forces, Jacobian values, distance as a separate scalar, the previous
action, or the current hold-counter value. It also does not report whether the
current in-tolerance interval is one step old or nearly complete. Consequently
the physical configuration and velocity can be observable while the full
task state relevant to reward and termination is not: two identical physical
observations can occur with different hidden consecutive-hold histories.

**Physical or scientific consequence.** The observation supports state-based
feedback for reaching and local stabilization, but sustained completion also
depends on unobserved recent history. The action-to-outcome relationship is
mediated by torque, coupled joint dynamics, end-effector kinematics, the
distance threshold, and the discrete hold counter. A policy that only reduces
instantaneous distance need not have reduced end-effector velocity enough to
remain inside the tolerance.

The research environment's scalar reward combines distance progress,
exponential closeness, hold-progress increments, a small squared-action cost,
and a completion bonus. The protected benchmark does not use reward to decide
success; it applies the physical transition and uninterrupted-hold rule
directly. Thus reward attribution can influence learned control during
training, but it is not itself a physical capability or an official outcome.

**Unknown.** The implementation does not establish whether the observation
representation is sufficient for a particular policy to infer its hidden
hold history, nor whether a policy will exploit the derived inverse-kinematic
features consistently. Those are behavioral properties, not deductions from
the task definition.

## Coupled capabilities and scientifically meaningful quantities

**Established fact.** The complete behavior can be described by a target
configuration, a joint trajectory, motor commands, and the resulting
end-effector trajectory. The implementation exposes or can deterministically
derive quantities including target radius and angle, joint positions and
velocities, end-effector position, target error, in-tolerance status,
consecutive hold length, episode termination, and truncation.

**Physical or scientific consequence.** Meaningful measurements over the
complete behavior include:

- target geometry, inverse-kinematic branch, joint-limit margin, and Jacobian
  singular values or conditioning;
- commanded torque, joint speed and acceleration, mechanical work or power,
  and the timing of control changes;
- initial separation, approach time, first-entry distance, end-effector speed
  and direction at entry, minimum distance, and distance variation during
  holding;
- the longest uninterrupted in-tolerance interval, all tolerance exits,
  total time in tolerance, final distance, and whether completion occurred
  before timeout.

These quantities connect reaching, convergence, stabilization, and sustained
success without treating a stage label as a causal diagnosis. For example,
approach torque, configuration-dependent leverage, residual velocity, and
hold interruption are physically linked; changing one realized capability
can change the others through the same dynamics.

**Unknown.** No actual trajectory, action sequence, branch selection,
settling profile, energy use, or distribution of outcomes follows from the
human-authored implementation alone. Those quantities require observing
executed behavior, while the model above defines the physical constraints and
the measurements by which that behavior can be understood.
