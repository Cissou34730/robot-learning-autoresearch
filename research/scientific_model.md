# Scientific model of the two-joint arm reach-and-hold task

This is the pre-campaign physical model. `Established facts` are stated by the
scenario or human-authored implementation. `Physical consequences` are
mechanical implications of those facts. `Unknowns` are quantities that cannot
be settled from the repository description alone; no campaign evidence exists
yet.

## System model

The robot is a planar serial manipulator with two revolute joints. Its motion
plane is horizontal at approximately `z = 0.02 m`. The shoulder rotates about
the vertical axis through the base, and the elbow rotates about the same
vertical axis at the end of the upper arm. The link lengths are
`l1 = 0.12 m` and `l2 = 0.10 m`. If the joint coordinates are shoulder angle
`q1` and relative elbow angle `q2`, the end-effector position in the plane is

```text
x = l1 cos(q1) + l2 cos(q1 + q2)
y = l1 sin(q1) + l2 sin(q1 + q2)
z = 0.02 m
```

The arm therefore has two controllable configuration coordinates and no
out-of-plane degree of freedom. The end effector is a site rather than a
contacting tool. The base, links, and target are visual or inertial geometry;
the plane and target have collisions disabled.

## Established facts

### Morphology and workspace

- The upper arm is a `0.12 m` capsule and the forearm is a `0.10 m` capsule.
  The shoulder and elbow each have a `[-170, 170]` degree hinge range.
- With unconstrained joint angles, the planar radial workspace is the annulus
  from `|l1-l2| = 0.02 m` to `l1+l2 = 0.22 m`. The official target radii are
  `0.06--0.20 m`, so every target radius is inside the nominal annulus and
  leaves only `0.02 m` of radial margin at the outer end.
- The target angle spans the full circle. The target is placed in the arm's
  plane, so the relevant success distance is genuinely a planar distance even
  though it is computed as a three-dimensional norm.

### Actuation, timing, and dynamics

- Each joint is driven by a MuJoCo motor with control range `[-1, 1]` and gear
  `5`. The policy action is passed through unchanged apart from clipping to
  that range. Thus the nominal actuator torque command is proportional to
  `5 * action` in each joint; there is no policy-side position or velocity
  controller.
- The MuJoCo integration timestep is `0.002 s`. The official frame skip is
  `10`, so one action is held for `0.020 s` while ten physics steps execute.
  The controller therefore acts at `50 Hz`, and a 500-step episode spans at
  most `10 s`.
- Each joint has damping `0.5` and armature `0.01`. Gravity is disabled. No
  joint friction, contact reaction, or external task force is specified.
  Link mass and inertia are derived by MuJoCo from the declared capsule
  geometry and model defaults rather than explicitly given as robot
  parameters.
- The target is a mocap body and does not move after reset. Its visible sphere
  has no collision role.

### Initial state and task semantics

- Reset sets both joint positions and velocities to zero, then samples a new
  target. The initial arm is fully extended along positive `x`, with its end
  effector at approximately `(0.22, 0, 0.02)`.
- The official target is sampled with radius in `[0.06, 0.20] m` and angle in
  `[-pi, pi]`. The training-only environment currently samples the narrower
  outer range `[0.14, 0.20] m`; evaluation uses the official range.
- An end-effector center distance of at most `0.01 m` is the tolerance.
  The environment increments a hold counter after each 20 ms control
  interval whose post-integration distance is within that tolerance. A reset
  to zero occurs on an outside sample. Success requires `100` consecutive
  in-tolerance control samples, corresponding to `2 s`, and the episode can
  terminate at that point.

### Observation and control information

The policy receives 11 floating-point values:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional end-effector-to-target displacement; and
4. four wrapped angular errors to the two geometric inverse-kinematic
   configurations, one error for each joint and branch.

The inverse-kinematic features use the known link lengths and the standard
two-link solution. For a target at radius `r`, the elbow solutions satisfy

```text
cos(q2) = (r^2 - l1^2 - l2^2) / (2 l1 l2),
```

with `q2 = +/- arccos(cos(q2))`, and the corresponding shoulder angle is
chosen for the target direction. The observation contains no sensor noise,
latency, actuator measurement, or explicit target radius/angle field.

## Physical consequences

### Reachability and configuration choice

The target position determines a two-dimensional pose constraint for a
two-degree-of-freedom arm. Away from the inner and outer singular
configurations, a target generally has an elbow-open and an elbow-folded
solution. For the official radial interval, the geometric elbow magnitude
varies from about `49` degrees at `r = 0.20 m` to about `150` degrees at
`r = 0.06 m`. The two branches are therefore both physically meaningful,
although joint-limit validity must be considered at the exact target angle.
The policy can reach the same target through distinct joint trajectories and
can switch its preferred branch across episodes.

The reset configuration is always the outer, positive-`x` extension. Targets
near that direction and radius `0.20 m` require little displacement, while
targets on the opposite side require a large coordinated rotation. A policy
that only learns short motions from the reset direction is consequently not
solving the full angular task. The full-circle distribution also makes
shoulder-angle wrapping a physical representation issue rather than merely a
feature-format issue.

### Motion generation and stabilization

An action changes joint acceleration and then joint velocity and position over
ten integration substeps; it does not place the end effector at a requested
point. The coupled Jacobian maps joint velocity into Cartesian velocity, so
the same joint command has different radial and tangential effects depending
on configuration. Near a kinematic singularity, one Cartesian direction has
weak or vanishing authority and large joint motion can produce little useful
end-effector motion. The outer-radius targets are the more singular side of
the task.

The arm has no gravity or object load to balance. At a precisely reached,
zero-velocity configuration, zero motor command is an equilibrium because
there is no load torque. In practice, entry velocity, discretization, and
residual error determine whether the arm crosses the 1 cm disk before
damping removes motion. Damping helps dissipate velocity but does not
replace a trajectory that brakes early enough. During the hold, the policy
must keep the configuration inside a small Cartesian set for 100 controller
updates; reach and hold are therefore coupled through terminal velocity,
local Jacobian conditioning, and the branch selected.

The success counter samples only after each frame-skipped integration block.
The implementation does not independently reject an excursion that leaves
the tolerance and returns within the same 20 ms block. Thus the operational
criterion is 100 consecutive post-action observations, while substep motion
still affects the next observed state and can determine later failure.

### Observability and task outcome

The joint positions and velocities expose the simulator's relevant mechanical
state. Given fixed link lengths, joint positions also determine the absolute
end-effector position; combined with the displacement feature, they determine
the target's planar position. Consequently the target is not hidden from the
policy despite not being supplied as an explicit radius-angle pair. The
observation is sufficient for a deterministic Markov description of the
physical state under a fixed target.

The four branch errors make the nearest geometric terminal configurations
explicit, but they do not prescribe which branch to use or how to brake into
it. They also do not directly reveal torque, acceleration, actuator
saturation, or the unobserved path between controller observations. The
reward supplies progress and closeness shaping, a hold-progress signal, an
action cost, and a completion bonus, but the binary episode outcome remains
entirely determined by uninterrupted tolerance occupancy.

The analytic geometry also constrains branch feasibility. Over the official
radial interval, the elbow magnitude remains below `170` degrees and the
shoulder offset from the target direction is approximately `22--56` degrees.
Each branch therefore loses validity near a shoulder-limit sector for some
target angles, but the two sectors do not overlap: at least one analytic
configuration is joint-limit-valid for every official target position.

## Scientifically meaningful quantities

The complete behavior is best characterized by quantities that separate
geometric reach from dynamic convergence and hold robustness:

- target radius and angle, selected inverse-kinematic branch, joint-limit and
  singularity margins, and the target's initial distance;
- joint position, velocity, acceleration, and commanded actuator torque over
  time, including saturation and action changes;
- Cartesian error decomposed into radial and tangential components, Cartesian
  speed, and distance at every controller sample;
- time to first enter tolerance, entry velocity, minimum distance, maximum
  consecutive hold length, number and timing of exits, and the distance after
  an exit;
- within-frame or substep excursions when available, because the success
  contract samples at the control rate;
- success conditioned on radius, angle, branch, and initial displacement, not
  only pooled success rate.

These quantities distinguish failure to reach, failure to settle, and failure
to maintain the hold, which are physically different mechanisms even when all
produce the same episode failure.

## Unknowns

- The compiled MuJoCo masses, centers of mass, and joint inertias are not
  explicitly stated in the XML. Their exact values, and therefore the
  acceleration and settling time produced by a unit action, remain unresolved.
- The effective torque-to-motion relationship depends on those inertias, the
  simulator's actuator transmission, damping, and discrete integration. It is
  not justified to infer a settling time or a uniform Cartesian control
  authority from the nominal gear value alone.
- It is not yet known how often the learned policy approaches a target with
  appreciable residual velocity, how strongly it saturates actuators, or
  whether it consistently chooses one branch.
- It is not yet known whether failures will be dominated by outer-radius
  conditioning, large-angle travel from the reset, branch selection,
  discretization-induced exits, or learning variability. The current training
  distribution also leaves the inner official radii unseen during baseline
  training, but its behavioral consequence is unknown before evidence.
- No campaign evidence yet establishes the policy's success probability under
  the official distribution. In particular, a high reach rate or a long
  average hold cannot substitute for the required per-episode complete hold
  or establish the `98%` objective.
