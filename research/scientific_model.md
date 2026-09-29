# Scientific model of the two-joint arm reach-and-hold task

This is the campaign-start physical model. It distinguishes what is directly
specified by the human-authored implementation from consequences inferred from
that specification and from quantities that are not yet resolved. The task is
not a static inverse-kinematics problem: success requires selecting and
executing a dynamically feasible trajectory, dissipating motion, and keeping
the end effector inside a small target neighborhood for the entire measured
hold.

## Established facts

The human-authored implementation establishes a deterministic planar two-joint
MuJoCo arm, its reset state, direct motor interface, observation contract, and
the official target, timing, tolerance, hold, and assessment rules described
below.

### Robot geometry and state

- The robot is a planar serial arm with two revolute joints. The shoulder is at
  the world origin and both joint axes are the world z axis. The upper arm
  length is 0.12 m and the forearm length is 0.10 m, so the end-effector site
  is at the end of a 0.22 m two-link chain. The arm plane is z = 0.02 m.
- The shoulder and elbow joint ranges are declared as -170 to 170 degrees.
  The joint coordinates are the shoulder angle `q1` and the elbow angle `q2`
  relative to the upper arm. The end-effector position is therefore
  `x = 0.12 cos(q1) + 0.10 cos(q1 + q2)`,
  `y = 0.12 sin(q1) + 0.10 sin(q1 + q2)`,
  `z = 0.02`.
- The reset state is `q = (0, 0)` with zero joint velocity. The initial
  end-effector position is consequently (0.22, 0, 0.02). Reset samples one
  fixed target with radius uniformly from 0.06 to 0.20 m and angle uniformly
  over -pi to pi, then places it in the arm plane.
- The target is a kinematic mocap body and its geom is non-colliding. The plane
  and base geom are also explicitly non-colliding. The link geoms retain their
  default contact settings.

### Actuation, simulation, and timing

- There are two independent MuJoCo motor actuators, one per joint. The action
  has two components, is clipped to [-1, 1], is written directly to
  `data.ctrl`, and is held constant for 10 physics steps. Each physics step
  uses a 0.002 s timestep, so the policy acts at 0.020 s intervals (50 Hz).
- Each motor has gear 5 and a control range of [-1, 1]. Thus the normalized
  command is a direct joint-torque command through a fixed gear transmission,
  with the available torque scale set by that transmission and by the
  compiled MuJoCo actuator semantics.
- Gravity is zero. Each joint has explicit damping 0.5 and armature 0.01.
  No spring or joint friction-loss term is specified. The XML does not
  explicitly specify link inertials, density, integrator, or solver settings.

### Task and assessment

- A target is inside tolerance when the three-dimensional Euclidean distance
  from the end-effector site to the target is at most 0.01 m. Because target
  z is set to the end-effector plane, the measured error is physically planar.
- The official implementation updates distance only after each 10-substep
  control interval. A hold is 100 consecutive in-tolerance control samples,
  equivalent to 2.0 s at the stated timing. Any sampled excursion outside the
  threshold resets the streak. An episode truncates after 500 control steps,
  or 10 s, unless the hold terminates it first.
- The official assessment uses one frozen policy on 200 fixed-seed episodes
  from the official distribution. At least 196 successes are required for the
  98% objective.
- The baseline training environment currently samples radii from 0.14 to
  0.20 m, while official evaluation samples 0.06 to 0.20 m. The mechanics and
  hold definition are shared, but this is a distribution difference in the
  default learning setup.

### Observation and policy interface

- The policy receives 11 float32 values: the two joint positions, two joint
  velocities, the three-vector from end effector to target, and four wrapped
  joint errors to the two analytic inverse-kinematics branches.
- For a target with polar angle `phi`, the analytic elbow solutions are
  `q2 = +/- acos((r^2 - L1^2 - L2^2)/(2 L1 L2))`, with the corresponding
  shoulder angle
  `q1 = phi - atan2(L2 sin(q2), L1 + L2 cos(q2))`. The observation supplies
  errors to both branches. The target vector, together with joint positions
  and known link lengths, also makes the target position reconstructible; no
  camera or noisy sensor model is used.
- The observation contains no action history, actuator state, hold-streak
  counter, or explicit elapsed time. The final benchmark supplies zero reward;
  the research environment supplies progress, closeness, hold-progress,
  action-cost, and completion terms, but the physical success test is the same.

## Physical consequences

These established mechanics imply that the policy must solve a coupled
reach-and-regulate problem: it must choose a feasible configuration, control
transient motion, and remain inside the tolerance region at every measured
hold boundary.

### Reachability and kinematic alternatives

For link lengths `L1 = 0.12` and `L2 = 0.10`, the unconstrained planar
reachable radii are 0.02 to 0.22 m. The official interval 0.06 to 0.20 m is
inside this annulus, but its outer edge is only 0.02 m short of full extension
and its inner edge is only 0.04 m beyond the folded-radius boundary. The
official targets are therefore reachable in position, while the two ends of
the radial interval retain different sensitivities to configuration and
velocity errors.

Except at a kinematic singularity, each target has two inverse-kinematic
configurations: positive and negative relative elbow angle, corresponding to
the two sides of the shoulder-elbow geometry. Across the official radial
range, the magnitude of `q2` is approximately 49 to 150 degrees. The shoulder
angle required by a given target direction differs between these branches;
the +/-170 degree limits can exclude one branch for some directions while
leaving the other available. Branch selection is consequently a real
behavioral choice, not merely an observation feature. Switching branches
requires a large configuration motion and is not a harmless local correction.

The planar position Jacobian maps joint velocity to end-effector velocity.
Its determinant is proportional to `L1 L2 sin(q2)`, so radial and tangential
control authority depends on the selected elbow configuration. Nearer
full-extension or folded geometries, small joint errors can produce
direction-dependent Cartesian errors and the same Cartesian correction can
require different joint torques. The official range avoids the exact
singular radii but does not make the two branches dynamically equivalent.

### Motion and stabilization

The action does not specify a desired position or velocity. It applies a
piecewise-constant torque command to a second-order arm whose acceleration
depends on configuration-dependent link inertia, coupled Coriolis/centripetal
terms, armature, damping, and the 50 Hz command schedule. A useful physical
description is

`M(q) qdd + C(q, qdot) qdot + D qdot = B u`,

with gravity absent, explicit damping in `D`, reflected armature in `M`, and
the motor gear in `B`. Reaching therefore requires both selecting a
configuration and shaping velocity; a command that reduces instantaneous
position error can still carry enough kinetic energy to cross the 1 cm region.

At the target there is no gravity to counterbalance and no specified
disturbance. A stationary exact configuration can require nearly zero torque,
but arriving with residual velocity is not equivalent to holding: damping
must dissipate that velocity before the end effector leaves the tolerance
ball. The hold is consequently a convergence and local regulation problem,
not just a first-entry event. Because the success counter is reset by any
sampled miss, a brief overshoot, oscillation, or branch-side correction
interrupts the complete hold.

The reset state is fully extended along positive x, with the target anywhere
on the official annulus. Initial distance can be as small as about 0.02 m and
as large as about 0.42 m. Targets on the opposite side therefore require a
large coordinated reorientation before stabilization, while near-positive-x
targets test precise braking from an already extended configuration. The
uniform-radius distribution is not uniform over workspace area: it gives
equal probability to radial intervals rather than equal probability per unit
area.

The measured hold is discrete at 20 ms boundaries even though MuJoCo advances
the dynamics at 2 ms. Sub-control-interval excursions are simulated and can
alter the next sampled state, but they are not independently counted as
failures. Conversely, a sampled miss resets the hold even if the continuous
trajectory was inside for most of that interval.

### Observation, control, and outcome coupling

The joint positions and velocities plus the target-relative vector make the
instantaneous physical state effectively observable under the deterministic
simulator model. The branch errors make the two nominal goal configurations
explicit, reducing the need for the policy to infer inverse kinematics from
trial and error. The observation still does not reveal how long the current
in-tolerance streak has lasted. Two episodes can have identical physical
observations and require different remaining hold times; the policy must
therefore execute a stationary or stabilizing behavior that succeeds
independently of that hidden task-progress state.

The causal chain is: target sampling and reset determine a goal and initial
state; the policy maps the current observation to two normalized torques;
MuJoCo integrates those torques for 20 ms; the resulting site position is
compared with the fixed target; and only the resulting consecutive
in-tolerance sequence determines task success. A policy can reach the target
quickly yet fail the episode through poor velocity regulation, branch
switching, torque saturation, or recurrent tolerance-boundary crossings.

### Scientifically meaningful behavior quantities

Across a complete episode, the physically informative quantities are target
radius and angle; joint position and velocity trajectories; commanded and
effective joint torques; action saturation and variation; end-effector
position and Cartesian velocity; radial and tangential target error; Jacobian
conditioning or manipulability; inverse-kinematic branch and distance to
joint limits; kinetic energy; first entry time; velocity and error at entry;
longest consecutive in-tolerance streak; number and timing of hold
interruptions; and the final distance. Contact generation and forces, if
present for link geometries, are also meaningful because they would change
the available motion rather than represent a learning-only failure.

## Unknowns

- The compiled link masses, centers of mass, and inertia tensors are not
  stated in the XML. They are inferred by MuJoCo from the geom definitions
  and defaults, so the exact mass matrix, acceleration under a saturated
  command, and configuration-dependent bandwidth are unresolved from the
  source alone.
- The XML leaves the MuJoCo integrator and solver configuration at defaults.
  The exact discrete damping, numerical energy behavior, and effects of the
  2 ms integration step therefore remain runtime quantities rather than
  analytically fixed properties of the written task.
- Gear transmission establishes the command scale, but the precise effective
  actuator torque after MuJoCo transmission, control clipping, joint limits,
  and any compiled actuator constraints has not been measured. The resulting
  time-to-reach and braking margin are unknown.
- Link geoms do not disable contact. It is unresolved whether MuJoCo's
  collision filtering generates relevant adjacent-link contacts in the folded
  configurations and, if so, whether contact impulses create a distinct
  failure class. The plane, base, and target cannot provide such contacts
  under their explicit settings.
- The observation code is exact and deterministic, but there is no empirical
  characterization yet of numerical sensitivity in the wrapped angles,
  target-relative vector, or analytic branch errors near joint limits. The
  practical policy sensitivity to these representations is unknown.
- The attainable hold margin is unknown: no campaign evidence yet establishes
  the distribution of entry velocities, boundary crossings, settling times,
  torque saturation, or branch preference under a learned policy. These
  determine whether failures are primarily reachability, transient control,
  stabilization, or distribution-generalization failures.
- The default training distribution does not include official radii from
  0.06 to 0.14 m. Before evidence, it is unknown whether the representation
  and learned dynamics generalize from the trained outer annulus to those
  inner configurations, or whether their distinct inverse-kinematic and
  braking geometry causes a disproportionate loss in official success.
- The success contract observes only control-boundary distances. The extent
  to which sub-20 ms excursions occur without being sampled, and whether
  those excursions materially precede later hold interruptions, is unknown.
- There is no observation noise, external disturbance, or target motion in the
  human-authored simulator. Thus robustness to those phenomena is outside the
  established task model, while the policy's robustness to simulator
  discretization, initial geometry, and target distribution remains to be
  established by campaign evidence.
