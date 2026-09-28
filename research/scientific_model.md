# Scientific model of the two-joint arm reach-and-hold task

This is a model of the embodied system before campaign evidence exists. It
separates quantities fixed by the human-authored task and simulator from
physical implications and from quantities that remain to be measured.

## System model

The robot is a planar serial arm with a fixed base and two revolute degrees of
freedom. The upper arm is 12 cm long and the forearm is 10 cm long. Both
hinges rotate about the vertical axis, so the end effector moves in the
horizontal plane at approximately `z = 2 cm`. The shoulder angle `q1` is
measured from the positive x direction and the elbow angle `q2` is relative to
the upper arm. Ignoring the small site radius, the end-effector position is

```
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2)
```

The declared range of each hinge is -170 to 170 degrees. The fully extended
configuration has a 22 cm reach. With the elbow constrained to 170 degrees
from extension, the smallest radial distance permitted by the two link
lengths is approximately 2.8 cm, before considering the shoulder bound. The
official targets, at radii 6 to 20 cm, therefore lie inside the nominal
kinematic annulus rather than at its singular outer boundary.

For a target with radius `r` and polar angle `phi`, inverse kinematics gives

```
cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10)
q1 = phi - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2))
```

The positive and negative values of `q2` are the elbow-open and elbow-folded
branches. They produce different joint trajectories and different proximity
to the joint limits while reaching the same Cartesian target. Across the
official radial interval, at least one branch is geometrically compatible
with the shoulder range for every target direction; near particular directions
one branch can be less available or less dynamically convenient. The target
distribution therefore tests more than a single memorized posture.

The target is a non-colliding mocap point fixed after reset. The plane and
target are also non-colliding, so this is free-space motion: neither contact
forces nor a grasping constraint helps the arm reach or hold. Success is based
on the distance between the end-effector site and the target point, not on
contact with the visible target sphere.

## Actuation, timing, and dynamics

Each joint is driven by a MuJoCo motor with control range -1 to 1 and gear 5.
The action is passed directly to the two actuator controls, clipped to that
range, and held constant for ten physics steps. The physics timestep is 2 ms,
so the policy acts at a 20 ms control interval (50 Hz) while the simulator
integrates at 500 Hz. A change in action changes generalized joint effort,
which changes acceleration; velocity and position then evolve through the
ten substeps before the next observation and action.

The model has zero gravity. Each joint has explicit damping 0.5 and armature
0.01, while the capsule geometry supplies the link mass and rotational
inertia through MuJoCo's model construction. Consequently, holding a
stationary configuration does not require gravity compensation or contact
support. Motion still requires acceleration and, critically, braking:
overshoot caused by residual velocity can leave the 1 cm band even when the
static target configuration is exactly known. Damping dissipates motion but
also limits how quickly a moving arm can settle. The gear and control bound
limit available acceleration, especially when both joints must change
simultaneously.

The control loop only evaluates task distance after each 20 ms action
interval. The physical state evolves during the ten internal steps, but an
intra-interval excursion is not separately recorded by the success counter.
Operationally, the uninterrupted hold is therefore 100 consecutive
in-band control observations, corresponding to 2 seconds at the official
timing. An out-of-band observation resets the counter, regardless of how much
prior hold time has accumulated. An episode has at most 500 such intervals,
or 10 seconds.

## Initial state and task geometry

Every episode resets both joint positions and velocities to zero. The arm
starts fully extended along positive x, with its end effector at approximately
`(0.22, 0, 0.02)`. A target is then sampled with angle uniformly over the
full circle and radius uniformly from 6 to 20 cm. This is uniform in radius
and angle, not uniform by Cartesian area. The target is placed at the
end-effector height, so the task has no out-of-plane component.

The initial state is not target dependent. For targets away from the positive
x direction, the policy must rotate the arm from the same extended posture;
for targets near the start direction it must still shorten the radius when
the target is inside 22 cm. Thus the episode combines a target-conditioned
transient with a target-conditioned final posture. At a radius of 6 cm the
two links are substantially folded, whereas at 20 cm they are closer to
extended. The angular precision required by a fixed Cartesian tolerance is
also radius dependent: a 1 cm lateral error corresponds to roughly 9.6
degrees at 6 cm but only roughly 2.9 degrees at 20 cm.

## Observation, action, and outcome

The policy receives 11 values:

* the two joint positions and two joint velocities;
* the three-dimensional end-effector-to-target displacement;
* four wrapped angular residuals to the two inverse-kinematic branches,
  consisting of shoulder and elbow residuals for the open and folded
  solutions.

The displacement and current end-effector position implied by the joint
positions make the fixed target recoverable in principle. The observation
contains velocity, so the policy can distinguish a settled posture from one
that is passing through it. It does not expose acceleration, actuator effort,
the internal hold counter, the previous action, or the physics state beyond
the represented positions and velocities. Hold progress is therefore hidden,
although maintaining a stationary target posture does not require knowing the
counter. Wrapped angular residuals avoid unbounded angle differences but can
make equivalent boundary representations appear discontinuous at the
`-pi/pi` wrap.

At each control decision, the action determines the next short segment of
joint motion. The resulting end-effector distance is the physical variable
that gates hold progress. Reaching is not enough: the policy must first
converge into the tolerance, then suppress velocity and corrective
oscillation sufficiently that every subsequent sampled distance remains at
most 1 cm for 100 intervals. A policy can therefore fail despite reaching the
correct inverse-kinematic branch if it arrives too fast, oscillates across the
boundary, saturates while braking, or chooses a posture close to a joint
limit. Conversely, the two branches provide alternative ways to trade
shoulder motion, elbow motion, limit margin, and transient dynamics.

## Coupled capabilities required for success

Success is a coupled sequence rather than a collection of independent skills:

1. **Reachability and branch selection:** infer the target and choose a valid
   joint solution while respecting the hinge ranges.
2. **Coordinated transport:** produce shoulder and elbow effort whose combined
   endpoint motion follows a useful trajectory instead of relying on one-joint
   corrections that create unnecessary coupling.
3. **Convergence:** reduce Cartesian position error and joint velocity within
   the available torque and 20 ms action resolution.
4. **Stabilization:** regulate the final posture with enough margin that
   damping and small corrective actions do not carry the endpoint outside the
   tolerance.
5. **Persistence:** repeat that regulation for the complete hold without an
   excursion. A near-perfect final distance or a long but interrupted partial
   hold is still failure.

The arm's Jacobian couples these requirements. Near an extended posture,
changes in the two joint angles can produce similar endpoint directions and
the inverse map becomes poorly conditioned for some corrections. Near a
folded posture, the endpoint has different leverage and a small joint change
can have a different Cartesian effect. These configuration-dependent
sensitivities, together with damping, inertia, and actuator saturation,
determine whether a controller can brake without crossing the tolerance
boundary. Zero gravity makes the final equilibrium simple, but it does not
remove transient coupling or the need to manage velocity.

## Scientifically meaningful quantities

The physically informative trajectory is more than binary success. Important
quantities include target-conditioned time to first enter the tolerance,
minimum distance, final distance, radial and angular error, endpoint speed,
joint speeds, acceleration proxies, actuator saturation and effort, joint-limit
margin, inverse-kinematic branch and branch switching, overshoot after first
entry, number and duration of hold interruptions, longest consecutive
in-band run, and distance margin to the 1 cm boundary. These should be
examined by target radius and angle. They distinguish a kinematic failure
from an underpowered or poorly damped transient, and a failure to reach from
a failure to stabilize.

## Established facts

- The human-defined task samples a fixed target in the 6-20 cm radial
  interval over the full angular range.
- The robot is a two-link, planar, 12 cm plus 10 cm arm with two hinge joints
  declared over -170 to 170 degrees.
- The simulator uses zero gravity, a 2 ms timestep, joint damping 0.5,
  armature 0.01, and direct motor controls with gear 5 and control range
  -1 to 1.
- The initial joint positions and velocities are zero, and the target shares
  the arm's horizontal plane.
- The policy observes positions, velocities, Cartesian target displacement,
  and residuals to both analytic inverse-kinematic branches.
- Official success requires distance at most 1 cm for 100 consecutive
  20 ms control steps; the episode limit is 500 control steps.
- The final assessment uses 200 fixed episodes, and at least 196 complete
  holds are required for the 98% objective.

## Physical consequences

- The official target annulus is inside the arm's nominal reachable region,
  so failure need not be caused by static kinematic impossibility.
- Every target requires a transient from the same fully extended initial
  state, followed by a precision regulation problem.
- The two inverse-kinematic branches create physically distinct solutions;
  branch choice can change joint-limit margin, Jacobian conditioning,
  required motion, and braking difficulty.
- Because gravity and contact are absent, sustained success is active
  endpoint regulation rather than load support. Residual velocity and
  action timing are central to uninterrupted hold.
- A fixed 1 cm Cartesian band is stricter in angular terms at larger radii,
  while folded targets demand a larger change from the initial posture.
- The environment's hold state is a run-length condition: one sampled
  excursion erases prior progress, so average proximity cannot substitute
  for uninterrupted stabilization.

## Unknowns

- The effective masses, inertia tensors, and exact coupled generalized
  dynamics produced by MuJoCo's geometry-derived inertial construction are
  not stated explicitly in the human-authored model.
- The acceleration, stopping distance, settling time, and endpoint
  oscillation produced by saturated actions are unknown across the target
  distribution.
- It is not known whether one inverse-kinematic branch is consistently
  easier to learn or control, or whether a policy can switch branches
  without entering a high-error transient.
- The distribution of first-entry time, hold margin, boundary crossings,
  and longest uninterrupted hold is unknown by radius and angle.
- It is unknown how often the 20 ms observation/action discretization hides
  physically undesirable intra-interval motion, even though the official
  success counter does not observe it.
- The relationship between the supplied observation and the policy's
  learned state estimate is unresolved: the physical state is largely
  represented for a fixed target, but hold progress, action history, and
  unmeasured dynamic quantities are absent.
- Before evidence exists, no claim can be made that the reachable geometry,
  control authority, or current observation representation is sufficient for
  98% complete-hold success; that must be established by trajectory-level
  measurements and the official frozen-policy assessment.
