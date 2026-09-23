# Scientific model of the robot and task

## System abstraction

The system is a two-degree-of-freedom planar manipulator whose endpoint must
reach a stationary point target and remain there.  The task is therefore not
only inverse kinematics: it is a sampled-data torque-control problem involving
motion from a fixed initial configuration, deceleration, and regulation inside a
small Cartesian tolerance.

### Established facts

- The shoulder and elbow are hinge joints about the world `z` axis.  The upper
  arm is 0.12 m long and the forearm is 0.10 m long.  The endpoint is a site at
  the distal forearm.
- The shoulder and elbow coordinates are relative joint angles, each limited to
  -170 to +170 degrees.  With joint angles `q1` and `q2`, the endpoint
  kinematics are
  `x = 0.12 cos(q1) + 0.10 cos(q1 + q2)` and
  `y = 0.12 sin(q1) + 0.10 sin(q1 + q2)`.
- The arm moves in the horizontal `x-y` plane at `z = 0.02` m.  The target is
  placed at that same height.  The target visual sphere and all arm geometry
  have collisions disabled, so the task contains no contact, grasping, or
  obstacle interaction.
- Official targets have a polar angle uniformly distributed over the full
  circle and a radius uniformly distributed from 0.06 to 0.20 m.  Success is
  endpoint-to-target Euclidean distance no greater than 0.01 m for 2.0 s.
- The MuJoCo integration timestep is 0.002 s.  One policy action is held for
  ten integration steps, giving a 0.020 s control interval (50 Hz).  The
  official hold is consequently 100 consecutive control intervals, and an
  episode is capped at 500 intervals.

### Physical or scientific consequence

- Ignoring joint limits, the planar workspace is the annulus between
  `|0.12 - 0.10| = 0.02` m and `0.12 + 0.10 = 0.22` m.  The official radial
  interval lies strictly inside these geometric boundaries.  For the stated
  range, at least one of the two ordinary planar inverse-kinematic branches can
  be selected without approaching the nominal 170-degree wrap limits.
- The initial arm is fully extended along positive `x`: `q = [0, 0]`,
  `qdot = [0, 0]`, and the endpoint is `(0.22, 0, 0.02)` m.  Its initial
  distance to a target at radius `r` and angle `theta` is
  `sqrt(0.22^2 + r^2 - 2*0.22*r*cos(theta))`.  Thus the initial geometric
  displacement ranges from a nearby correction to a roughly opposite-side
  transfer, depending on target geometry.
- The fully extended initial posture is a kinematic singularity for planar
  endpoint motion: the Jacobian has rank one at `q2 = 0`.  Endpoint motion in
  the tangential direction is first-order in joint velocity, whereas changing
  the reach radius initially requires bending and coordinated motion.  This is
  a structural property of the start state, not a statement about observed
  policy behavior.
- The target is sampled uniformly in radius rather than uniformly in disk area.
  This gives equal sampling weight to equal radial intervals, not equal spatial
  area.  Angular directions are not privileged by the task definition.

### Unknown

The implementation does not determine which inverse-kinematic branch a policy
will use, how quickly it will move, whether it will saturate an actuator, or
how much of the available episode it will spend reaching versus holding.

## Actuation and dynamics

### Established facts

- Each joint has a direct MuJoCo motor with control range `[-1, 1]` and gear
  value 5.  The policy action is passed through unchanged as the physical
  command, then clipped to this range by the environment.
- There is no position servo or trajectory generator between the action and
  MuJoCo.  The same joint motor command is applied during all ten internal
  integration steps in a control interval.
- Gravity is disabled.  Each joint has damping 0.5 and armature 0.01.  The
  XML does not explicitly specify body masses or inertial tensors; MuJoCo
  derives them from the geoms and its model defaults.  The link capsules,
  endpoint site, base cylinder, and non-colliding plane define the geometry
  used by that model construction.
- The target is a mocap body.  It is repositioned at reset and remains fixed
  during an episode.  No actuator, target, or contact dynamics introduce an
  additional moving object.

### Physical or scientific consequence

- The gear scales the direct motor transmission, so action magnitude directly
  controls joint torque authority up to the motor's bounded command.  The
  action is not a desired angle or velocity.  Motion results from torque,
  reflected armature inertia, link inertia, viscous damping, and the
  configuration-dependent two-link dynamics.
- The 20 ms zero-order-hold interface creates a sampled-data controller.  A
  policy must account for motion that continues for ten physics steps after
  each decision; rapid action changes cannot be applied at the 2 ms simulator
  resolution.
- Damping removes kinetic energy and supports settling, while finite torque and
  inertia limit how rapidly the endpoint can change velocity.  Because gravity
  and collision forces are absent, holding a posture is governed primarily by
  motor torque, damping, and the manipulator's inertial coupling.
- Near a target, Cartesian stabilization requires coordinated joint torques:
  the two motors must regulate both endpoint coordinates while also suppressing
  joint velocity.  Position accuracy alone is insufficient if residual velocity
  carries the endpoint outside the tolerance disk on a later control sample.

### Unknown

The human-authored XML does not state numerical link masses, inertia matrices,
or the resulting maximum endpoint speed and acceleration.  Those values are
deterministically available from the compiled MuJoCo model, but the actual
trajectory, torque usage, saturation, overshoot, and settling time require
observing a controller.

## Task geometry and required capabilities

### Established facts

- The target is a point for success measurement: the benchmark computes the
  three-dimensional distance between the endpoint site and the target mocap
  position.  The target sphere's 0.012 m visual radius is not the success
  tolerance.
- A sample is counted inside the tolerance only after a control interval has
  been simulated.  Any outside sample resets the hold counter to zero.  The
  final benchmark requires an uninterrupted run of 100 inside samples and
  accepts at most 500 samples per episode.
- The research environment's reward contains distance progress, an exponential
  closeness term, hold-progress terms, a small action cost, and a completion
  bonus.  The protected final benchmark uses the same physical success
  semantics but does not use reward to determine success.

### Physical or scientific consequence

Successful behavior has distinct phases even though the implementation does
not label them: select a feasible configuration, generate a reaching motion,
brake before crossing the target, converge inside the 1 cm disk, and regulate
there for two seconds.  A transient pass through the disk is not sufficient.

The benchmark's word "continuous" is implemented as uninterrupted control-step
membership.  Motion between the ten internal MuJoCo samples is not separately
tested by the success counter, so the scientific temporal observable is the
50 Hz distance sequence rather than an unbroken 2 ms collision-style trace.

The same endpoint can be reached by two elbow configurations.  In standard
planar inverse kinematics, for a target `(x, y)` the elbow candidates satisfy

`q2 = +/- arccos((x^2 + y^2 - 0.12^2 - 0.10^2)/(2*0.12*0.10))`,

with the corresponding shoulder angle determined by the target direction and
the forearm offset.  These are the elbow-open and elbow-folded branches exposed
by the observation code.  The branches have different joint velocities,
torques, and local Cartesian conditioning even when their endpoint positions
match.

### Unknown

The code cannot establish whether a policy will switch branches, remain on one
branch, exploit the 1 cm tolerance as a region of acceptable joint states, or
produce within-interval excursions that are invisible to the sampled success
test.

## Sensing and observability

### Established facts

The default observation is an 11-element float vector containing:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional endpoint-minus-target displacement; and
4. four wrapped angle errors, two relative to the elbow-open inverse-kinematic
   solution and two relative to the elbow-folded solution.

The observation space is unbounded apart from its fixed length.  The target
itself is stationary and its position can be reconstructed from the endpoint
position and the observed displacement.  The observation includes no explicit
target velocity, actuator torque, actuator saturation flag, contact signal,
hold counter, episode time, previous action, or within-step trajectory.

### Physical or scientific consequence

For this non-contact, fixed-target model, joint position, joint velocity, and
target displacement provide the main physical state needed to predict future
rigid-body motion under a command.  The branch errors supply an explicit
representation of both geometric solutions, while the endpoint displacement
supplies direct Cartesian control error.

The task automaton is not fully observed: two physically identical states can
have different hidden hold counters depending on the preceding distance
sequence.  Consequently the physical plant can be effectively state-observed
while the complete success condition is history-dependent.  The controller
must maintain the geometric condition without receiving direct feedback about
how many hold samples have already accumulated.

### Unknown

The representation alone does not reveal what information a learned policy
will actually use, whether it will infer phase from joint velocities and
errors, or whether it will exploit regularities in target geometry.  It also
does not reveal behavior between observation times.

## Meaningful physical measurements

The scientifically relevant quantities are:

- endpoint distance to target, with radial and tangential Cartesian error
  components;
- target radius and angle, because they determine transfer geometry and
  inverse-kinematic branch configuration;
- joint positions and velocities, especially distance from joint limits and
  velocity at first entry into tolerance;
- the planar Jacobian and its conditioning, including proximity to the
  extended or folded singular configurations;
- applied actions, inferred motor saturation, joint acceleration, and the
  duration of any zero-order-held command;
- time to first tolerance entry, longest consecutive in-tolerance streak,
  number and size of exits, and final distance;
- endpoint speed and distance variation throughout the 100-sample hold;
- action magnitude or integrated squared action as an effort measure, kept
  separate from task success.

These measurements distinguish geometric reachability from dynamic control and
distinguish reaching from stabilization.  They do not, by themselves, explain
the cause of a behavior: the actual branch, trajectory, saturation pattern,
and physical response remain empirical properties of a particular controller.
