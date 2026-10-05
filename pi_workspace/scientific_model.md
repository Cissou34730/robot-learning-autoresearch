# Scientific model of the two-joint arm reach-and-hold task

The system is a planar, fully actuated two-link arm whose only physical task is
to move its distal site to a stationary point and keep that site within a
10 mm Euclidean tolerance for the full two seconds.  It is not a grasping or
contact task: the target is a non-colliding mocap body, and success is computed
from the end-effector site position.  The central control problem is therefore
to select a reachable inverse-kinematic configuration, drive the arm there
without leaving residual motion, and reject that motion for the entire sampled
hold interval.

## Morphology and kinematics

The base is fixed at the world origin.  The shoulder and elbow are revolute
joints about the world z axis, so both links move in the horizontal plane at
z = 0.02 m.  The upper-arm and forearm lengths are 0.12 m and 0.10 m.  If
`q1` is the shoulder angle and `q2` is the elbow angle relative to the upper
arm, the end-effector position in that plane is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
z = 0.02
```

Both joints are limited to [-170, 170] degrees.  Without those limits, the
two-link workspace is the annulus from 0.02 m to 0.22 m.  The official target
radii, 0.06--0.20 m, lie inside this nominal annulus and are in the same plane,
so the target is kinematically reachable in principle.  The joint limits can
remove one inverse-kinematic branch or make a configuration poorly conditioned
near angular and radial workspace boundaries; they do not add a third
translational degree of freedom.

For a reachable target at polar angle `theta` and radius `r`, the observation
code explicitly constructs the two usual solutions:

```text
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q1 = theta - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))
```

These are the elbow-open and elbow-folded alternatives.  The controller can
choose either branch, subject to both joint limits.  Near full extension the
Jacobian loses authority in some Cartesian directions, so a small position
error can require relatively large joint motion even though the target remains
reachable.

## Actuation, timing, and dynamics

Each joint is driven directly by a MuJoCo motor.  The policy action is passed
through unchanged, clipped to [-1, 1], and held constant for ten physics
steps.  The XML gives each motor gear 5, so the commanded joint torque is
approximately `5 * action` in the simulator's torque units, with an available
range of [-5, 5] per joint.  There is no position servo, action smoothing, or
low-level trajectory generator between the policy and the motors.

The physics timestep is 0.002 s and the loaded model uses the default Euler
integrator.  Consequently, one policy action spans 0.020 s and the official
500-step episode spans at most 10 s.  The joint damping is 0.5 and the
armature is 0.01 for each joint.  Gravity is explicitly zero.  Thus the
dominant passive effects are velocity damping, configuration-dependent
coupled inertia, and the motor torque; there is no gravitational torque to
balance during the hold.

MuJoCo derives link inertias from the capsule geometry and its default
material density rather than from explicit mass declarations.  In the loaded
model the upper-arm and forearm masses are approximately 0.0990 kg and
0.0525 kg.  The generalized mass matrix at the initial straight posture is
approximately

```text
[0.012102  0.000507]
[0.000507  0.010192] kg m^2
```

and changes with elbow posture.  At the initial posture, simultaneous
full-scale positive torques correspond to an initial acceleration of roughly
(393, 471) rad/s^2 before damping and other state effects.  This is an
authority scale, not a guaranteed trajectory acceleration: the coupled
inertia, damping, discrete integration, joint limits, and changing
configuration determine the actual motion.

## Initial state and task geometry

On reset, both joint positions and velocities are zero.  The links are
therefore collinear along +x and the end-effector site starts at
(0.22, 0, 0.02) m.  A target is then sampled once and remains fixed:
the radius is uniform over [0.06, 0.20] m and the polar angle is uniform over
[-pi, pi].  The target z coordinate is set to the end-effector plane, making
the three-dimensional distance used for success equivalent to the planar
distance in this task.

The target marker has no collision interaction, and the ground plane also has
collisions disabled.  The arm therefore has no environmental contact,
obstacle avoidance, or force-control requirement.  The end-effector site must
be at most 0.01 m from the target after each control interval.  It must satisfy
that condition on 100 consecutive control steps, because 2 s / 0.020 s = 100.
Leaving the tolerance resets the consecutive count to zero, so intermittent
visits, even if they accumulate 100 in-tolerance samples, do not succeed.

The current baseline training constructor samples only [0.14, 0.20] m,
whereas the official evaluation distribution is [0.06, 0.20] m.  This is a
fact about the learning setup, not a change to the physical task: the inner
part of the official workspace is not represented by that baseline training
distribution.

## Observation, action, and outcome coupling

The policy receives an 11-element instantaneous observation:

* the two joint positions and two joint velocities;
* the three-dimensional end-effector-to-target displacement; and
* four wrapped joint errors, one for each of the two inverse-kinematic
  solutions.

The joint state and known link geometry determine the end-effector position,
so the displacement also makes the stationary target's planar position
recoverable.  The z displacement is identically zero under the reset and
target construction.  The observation contains no force, contact, motor-current,
target-velocity, disturbance, or explicit hold-timer measurement.  It also has
no action history.  A policy with temporal state could infer recent behavior,
but the environment itself exposes only the current physical observation.
There is no sensor noise or modeled external disturbance in the implementation.

The causal loop is therefore: observation reveals pose, velocity, target error,
and both candidate configurations; the action produces joint torque for 20 ms;
the coupled arm evolves for ten physics steps; the resulting site position is
tested against the tolerance; and the next observation exposes the new state.
A successful hold requires both convergence and low enough residual velocity
that this loop does not carry the site outside the tolerance.  With gravity
and external contact absent, an exactly reached configuration with zero
velocity requires no steady torque, but arriving with velocity still requires
active braking and damping.

The training reward provides progress and closeness shaping, incremental hold
progress, a completion bonus, and a small action cost.  The environment's
termination remains the authoritative outcome: reward accumulation or a
near-miss is not an episode success.  An exit from the tolerance resets hold
progress and can receive the configured outside-band penalty.

## Behavior classes and meaningful physical quantities

The main physically distinct behavior classes are:

1. **Reach failure:** the policy selects inadequate or saturated torques,
   chooses a poor branch, or cannot converge within the episode horizon.
2. **Convergence/overshoot failure:** the site crosses the target but residual
   joint velocity, delayed action updates, or poor braking repeatedly carries
   it outside the 1 cm band.
3. **Hold failure:** the policy reaches the band but produces oscillation or
   drift, causing one of the 100 required samples to fail.
4. **Constraint failure:** a desired inverse-kinematic solution is outside a
   joint limit or is approached near a poorly conditioned Jacobian, producing
   saturation, slow motion, or branch-dependent behavior.
5. **Successful branch choice:** either valid elbow configuration can solve the
   position task; the dynamically preferable branch may differ with target
   angle, current posture, and remaining distance.

The most informative physical quantities for separating these mechanisms are
target radius and angle; both joint positions and velocities; end-effector
position error and its time derivative; selected inverse-kinematic branch and
distance to joint limits; action magnitude and saturation; time to first enter
the tolerance; minimum distance; maximum consecutive in-tolerance duration;
number and timing of tolerance exits; and the complete hold trajectory.  These
quantities connect actuation and dynamics to the binary episode outcome
without treating the reward as a substitute for the task criterion.

## Established facts

- The robot has two planar revolute degrees of freedom with link lengths
  0.12 m and 0.10 m, joint ranges of ±170 degrees, and an end-effector site at
  the forearm tip.
- Reset sets both joint positions and velocities to zero; the initial site is
  at (0.22, 0, 0.02) m.
- Gravity is zero, the physics timestep is 2 ms, and ten physics steps are
  taken per policy action.
- Motors map clipped actions in [-1, 1] through gear 5 to the two joints.
  Joint damping and armature are 0.5 and 0.01 respectively.
- Targets are fixed at reset, sampled with radius [0.06, 0.20] m and angle
  [-pi, pi], and placed in the arm plane.
- Success is site-target distance <= 0.01 m for 100 consecutive control steps;
  the maximum episode duration is 500 control steps.
- The observation has 11 values: joint position, joint velocity, target-relative
  site displacement, and errors to both analytic inverse-kinematic solutions.
- The baseline training target range [0.14, 0.20] m is narrower than the
  official range.

## Physical consequences

- The task is a free-space position-and-stabilization problem, not a contact,
  grasp, or force-regulation problem.
- The controller must manage acceleration and braking, not merely choose a
  target pose: the 20 ms action hold and configuration-dependent inertia create
  unavoidable state evolution between observations.
- Zero gravity removes a persistent holding load.  Once exactly stationary at a
  valid pose, zero action is physically consistent; the difficult part of the
  hold is suppressing arrival velocity and correcting errors without inducing
  oscillation.
- Both inverse-kinematic branches can be physically meaningful.  Joint limits,
  current posture, torque saturation, and Jacobian conditioning can make their
  transient behavior different even when their final site position is the same.
- The one-centimeter band is small relative to the 0.06--0.20 m target-radius
  range, so a policy can have good first contact with the target yet fail the
  episode through repeated boundary crossings.
- The inner official radii are absent from the current baseline training
  distribution, so baseline performance cannot by itself establish competence
  across the complete official geometry.

## Unknowns

- The exact transient basin of attraction and maximum reliably controllable
  target set under the discrete policy loop are not established by geometry
  alone.
- The relative frequency of elbow-branch selection, branch switching, and
  joint-limit interaction is unknown before trajectory evidence exists.
- The effective settling time, overshoot, and tolerance-exit probability as
  functions of radius, angle, approach direction, and residual velocity are
  unknown.
- The model's geometry-derived masses and inertias are known for the loaded
  simulator, but their practical effect on learned behavior, including
  configuration-dependent controllability under torque saturation, is not yet
  measured across the official target distribution.
- It is unknown whether the 20 ms sampling interval and observation
  representation allow a policy to infer enough recent motion to stabilize
  every reachable target without explicit recurrence or other temporal
  information.
- No campaign evidence yet determines whether failures will be dominated by
  reaching, convergence, hold stability, branch/limit constraints, or the
  training-distribution gap.
