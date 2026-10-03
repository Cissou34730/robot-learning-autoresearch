# Scientific model of the two-joint arm reach-and-hold task

This is the campaign-start physical model. Repository facts are separated from
their mechanical implications and from quantities that cannot be established
before campaign evidence or direct measurement.

## Established facts

### Robot, geometry, and state

The robot is a planar serial two-revolute-joint arm. The shoulder joint is
anchored at the world origin, and the arm plane is at `z = 0.02 m`. The upper
arm and forearm lengths are 0.12 m and 0.10 m. With shoulder angle `q1` and
relative elbow angle `q2`, the end-effector position is

```text
p(q) = (0.12 cos(q1) + 0.10 cos(q1+q2),
        0.12 sin(q1) + 0.10 sin(q1+q2),
        0.02).
```

Both hinge joints have ranges of -170 to 170 degrees. The end effector is a
site at the distal end of the forearm. The target is a stationary mocap body;
it is not a physical object that the arm must contact.

At reset, both joint positions and velocities are set to zero. Thus the arm
starts fully extended along positive world `x`, with its end effector at
`(0.22, 0, 0.02)`. The target is then sampled with angle uniform on
`[-pi, pi]` and radius uniform on `[0.06, 0.20]` m, and its `z` coordinate is
set to the end-effector plane.

### Actuation and simulation

Each joint is driven by a MuJoCo motor with normalized control in `[-1, 1]`
and gear `5`. The policy action is passed through unchanged apart from this
range clipping. It is therefore direct joint actuation rather than a position
or velocity command; for these scalar hinge transmissions the nominal motor
torque range is approximately `[-5, 5]` in model torque units.

MuJoCo integrates at 0.002 s with zero gravity. Each policy action is held
constant for 10 simulation steps, giving a 0.020 s control interval (50 Hz).
Both joints have damping `0.5` and armature `0.01`. The link capsule geometry,
joint limits, and those explicit damping and armature terms define the
simulated mechanical system; there are no actuator state dynamics or target
dynamics in the model.

The shared environment advances the same physical model for training and
evaluation. An episode may last at most 500 control steps, or 10 seconds.
After each control interval, the 3-D end-effector distance to the target is
tested. A sample is in tolerance when that distance is at most 0.01 m. The
held counter increments on an in-tolerance sample and resets to zero on any
outside sample. Success terminates the episode after 100 consecutive
in-tolerance samples, corresponding to 2 seconds.

### Observation and learning interface

The policy receives 11 values:

* the two joint positions and two joint velocities;
* the three components of end-effector minus target position;
* four wrapped angular errors to the two analytical inverse-kinematic
  configurations, using positive and negative elbow angles.

The target is fixed during an episode. Since joint positions and the
end-effector-to-target vector are observed, its position is effectively
recoverable even though it is not supplied as a separate absolute field. The
observation contains no measurement noise, actuator state, contact state,
previous action, or explicit hold counter. The physical action is the two
component observation-to-motor command described above.

The scalar learning signal combines distance progress, an exponential
closeness potential, incremental hold progress, a small action cost, and a
small penalty after leaving the tolerance band. It also gives a completion
bonus. This is an interface to learning, not an additional physical success
condition: the authoritative outcome is the uninterrupted hold.

## Physical consequences

### Workspace and inverse kinematics

The planar radial distance satisfies

```text
r^2 = 0.12^2 + 0.10^2 + 2(0.12)(0.10) cos(q2).
```

With unrestricted shoulder orientation, the two-link workspace is bounded by
0.22 m at full extension and about 0.02 m at exact opposition. The actual
elbow range stops at 170 degrees, making the smallest radius about
`sqrt(0.12^2 + 0.10^2 - 2(0.12)(0.10)cos(10 degrees)) = 0.0277 m`.
The official 0.06-0.20 m annulus is therefore inside the radial workspace and
away from the two exact radial singularities. The shoulder range removes some
joint configurations, but for every official target there is analytically at
least one elbow branch whose shoulder angle can be represented within
[-170, 170] degrees. The task is consequently not intrinsically blocked by
reachability, although the two branches are not equally available near the
shoulder limits.

For a target `(x,y)` at radius `r`, the analytical branches are

```text
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2(0.12)(0.10)))
q1 = atan2(y,x) - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2)).
```

These are the elbow-open and elbow-folded alternatives represented in the
observation. They provide multiple valid final postures and therefore multiple
valid stabilizing torque policies. A policy need not follow a unique path or
choose one global branch; it can use either branch where joint limits and
transient dynamics make it advantageous.

The endpoint Jacobian is

```text
J(q) = [[-0.12 sin(q1)-0.10 sin(q1+q2), -0.10 sin(q1+q2)],
        [ 0.12 cos(q1)+0.10 cos(q1+q2),  0.10 cos(q1+q2)]].
```

Its determinant is `0.12*0.10*sin(q2)`. Thus endpoint direction control
degrades as the elbow approaches a straight or fully opposed posture. The
inner official targets require an elbow angle near the opposed limit (about
150 degrees at 6 cm), so they are mechanically more sensitive than targets
near the middle of the annulus even though they remain reachable.

### Motion and stabilization

The motors apply bounded joint torque, and the two joints are dynamically
coupled through the configuration-dependent two-link inertia. Moving one
joint changes both the endpoint position and the inertial load seen by the
other joint. Damping dissipates velocity, while armature adds reflected
rotational inertia; neither creates a position-restoring force. With gravity
disabled and no target contact, the controller must actively bring the endpoint
to the target and regulate it there.

The starting posture is not a neutral posture for the task. The arm begins at
maximum extension, whereas every official target is at most 0.20 m from the
base. Even the closest possible start-target displacement is 0.02 m, outside
the 0.01 m tolerance. The initial motion must therefore be a deliberate
convergence rather than an immediate hold. Targets at the opposite angle can
initially be nearly 0.28 m away, and target angle changes the required
shoulder motion and the transient torque demand.

Success is a hybrid reach-and-regulate problem:

1. select a feasible final configuration and move from the extended reset
   posture;
2. control the coupled trajectory without excessive endpoint speed or
   overshoot;
3. enter the 1 cm ball; and
4. dissipate or counter residual motion while maintaining the endpoint inside
   that ball for 100 consecutive 20 ms observations.

The last step is stricter than merely reaching the target. One sampled
outside excursion resets all accumulated hold time, including an excursion
caused by a high-speed crossing, delayed torque response, branch transition,
or discretization between control updates. A successful policy must therefore
regulate endpoint position and velocity, not just produce a low minimum
distance. The 1 cm Cartesian ball also maps to different joint-space
tolerances depending on the local Jacobian, so the same endpoint margin does
not imply the same angular margin at all targets.

The observation makes the instantaneous physical state close to fully
observable for this model: positions, velocities, and target-relative
position are available, and the target is stationary. The omitted hold counter
does not hide a mechanical variable, but it does hide whether a prior
in-tolerance interval was already accumulated. Since the target does not move,
maintaining the physical state inside the tolerance region is sufficient to
continue a hold; the policy nevertheless cannot infer hold progress from the
observation alone.

### Behaviorally meaningful quantities

The scientifically meaningful description of a complete behavior includes
target radius and angle; selected IK branch and joint-limit margins; joint
positions, velocities, and accelerations; endpoint position error and its
radial and tangential components; endpoint speed at entry; time to first
entry; maximum uninterrupted in-tolerance run; every hold interruption and
its excursion distance; distance and speed during the hold; motor commands,
torque saturation, and action changes; and the Jacobian conditioning or
`|sin(q2)|` along the trajectory. These quantities connect the binary episode
outcome to reachability, transient control, convergence, and sustained
stability rather than treating all failures as equivalent.

## Unknowns

The following are not established by the repository description alone:

* The capsule geom mass and inertia are not explicitly listed. MuJoCo derives
  them from compiled geom properties and defaults, so the exact generalized
  mass matrix, natural response, acceleration under a saturated command, and
  damping-to-inertia time scales remain unquantified here.
* The exact behavior near the 170-degree limits, including limit constraint
  forces and numerical solver effects, has not been measured. This matters
  most for inner-radius targets and for trajectories that choose the folded
  branch.
* The analytical kinematics predict reachability for the official annulus,
  but the effective reachable set under torque limits, finite-rate actions,
  and the 500-step horizon is not yet known. In particular, it is unknown
  whether any target sectors systematically require saturation or a
  longer-than-available convergence transient.
* It is unknown which IK branch a learned policy will select, whether it will
  switch branches during motion, and whether branch choice correlates with
  target radius, angle, endpoint speed, or hold reliability.
* The relative contributions of inertial coupling, damping, action
  discretization, and control saturation to hold interruptions are unknown.
  The same distance trace could arise from different combinations of these
  mechanisms without joint, velocity, torque, and Jacobian measurements.
* The observation is nominally sufficient for the stationary simulated state,
  but it is not yet established whether policy inference and the chosen
  learning algorithm exploit velocity and branch information reliably. The
  effect of omitting hold history and previous action is a learning question,
  not a proven observability failure.
* No pre-campaign evidence establishes success probability, target-geometry
  dependence, time-to-reach distribution, or the frequency and mechanism of
  hold failure. The 98% objective therefore remains an untested campaign
  outcome, not a consequence of analytical reachability or of the shaped
  reward.
