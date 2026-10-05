# Scientific model of the two-joint reach-and-hold system

This is a planar, torque-actuated two-link arm whose endpoint must reach a
stationary point and remain inside a small disk for the whole hold interval.
The central scientific difficulty is therefore not merely inverse kinematics:
the policy must choose a reachable posture, move there from the same
fully-extended initial state, dissipate the resulting motion, and preserve a
small endpoint-error margin for 100 consecutive control decisions.

## Established facts

### Robot and task geometry

The human-authored model has a fixed base and two revolute joints rotating
about the world z axis. The upper arm length is 0.12 m and the forearm length
is 0.10 m. With shoulder angle `q1` and relative elbow angle `q2`, the
endpoint position in the horizontal plane is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2).
```

The endpoint and target share the arm plane; their z coordinates are equal.
Each joint has a -170 to +170 degree range. The unconstrained two-link
workspace has radii from 0.02 m to 0.22 m. The joint limits make the exact
angular workspace posture-dependent, but the official 0.06-0.20 m target
range lies inside the principal radial workspace.

An episode starts with `q1 = q2 = 0` and both joint velocities zero. The arm
is consequently fully extended at approximately `(0.22, 0, 0.02)`. The
target is then fixed for the episode. The implementation samples its angle
uniformly over the full circle and its radius uniformly between 0.06 and
0.20 m, so this is uniform in radius and angle rather than uniform in
Cartesian area.

The success region is the endpoint-centered disk of radius 0.01 m around the
target; the visible target sphere is not a contact object and does not define
success. A successful episode requires 100 successive in-tolerance control
steps, corresponding to 2 s, before the 500-step episode limit. The official
frozen-policy assessment uses 200 episodes, so at least 196 complete holds are
required for the 98% campaign objective.

### Actuation, integration, and control

Each action has two components in `[-1, 1]`. The policy output is passed
through unchanged and then clipped to that interval. Each component drives a
MuJoCo motor with gear 5, so the command is a bounded direct joint torque
command in the simulator's SI convention, rather than a desired angle or
velocity. There is no separate position servo or actuator state in the
human-authored model.

MuJoCo integrates at 0.002 s. One policy action is held constant for ten
physics steps, giving a 0.020 s control interval and a 50 Hz decision rate.
Joint damping is 0.5 and joint armature is 0.01 for both joints. Gravity is
zero. The plane and target are collision-disabled, and no external contact
force is specified for the task. The relevant motion is therefore free planar
joint dynamics with actuator torque, damping, link inertia, and coupled
two-link motion; any arm self-contact behavior is not part of the stated task
semantics.

The success counter is updated after each 20 ms control interval. Thus
"continuous" is operationally represented by 100 consecutive post-action
endpoint checks; the success logic does not inspect the ten intermediate
physics states separately. Leaving the tolerance after any counted step
resets the hold count to zero.

### Sensing and policy interface

The observation contains 11 values:

* the two joint positions and two joint velocities;
* the three-dimensional endpoint-to-target displacement; and
* wrapped angular errors from the current posture to both elbow-up and
  elbow-down inverse-kinematic solutions.

The target is stationary and there is no sensor noise, target motion, explicit
measurement delay, or unobserved actuator dynamics in this interface. Since
the endpoint is determined by the observed joint positions, the displacement
also makes the target position reconstructible. For the deterministic
simulator, the observation is therefore effectively a full state for control,
augmented by deliberately supplied geometric alternatives. It does not
directly report torque, acceleration, endpoint velocity, distance history, or
the simulator's effective mass and inertia parameters.

## Physical consequences

At the reset posture, the arm is at the outer radial singularity:
`q2 = 0` makes the planar Jacobian rank one. Infinitesimal joint motion
initially produces tangential endpoint motion much more readily than radial
motion. Every official target is inside the initial 0.22 m radius, so the
first task is necessarily to bend away from this singular configuration while
also rotating toward the target. The outer targets require only a small radial
retraction and are consequently especially sensitive to how the controller
breaks the initial singularity and limits momentum.

For a non-singular posture, endpoint velocity is

```text
v = J(q) qdot,
det(J) = 0.12 * 0.10 * sin(q2).
```

The determinant shows why the elbow configuration matters. The two
kinematic branches use opposite signs of `q2`; they can place the endpoint at
the same target with different shoulder angles and different local mappings
from joint velocity to endpoint velocity. For the official radii, the
elbow-angle magnitude is roughly 49 to 150 degrees, so at least one branch
can satisfy the shoulder limits for every target direction, while the other
branch can be excluded near some angular extremes. The policy must therefore
select a valid branch, not simply regress a single global joint target.

Reaching and holding are coupled. A trajectory that reaches the disk with
large joint velocity can cross the 1 cm boundary on the next control step;
the same action that moves the endpoint toward the target can create
unacceptable tangential or radial velocity near the target. Conversely, once
the arm is exactly stationary at a valid posture, zero gravity and zero
velocity-dependent damping torque mean that no sustained torque is required
to hold that posture. In practice the controller must still remove residual
velocity and correct numerical or policy-induced deviations. The tolerance
disk maps through the Jacobian to a posture-dependent joint-error region, so
the available hold margin is anisotropic and becomes poor near singular
configurations.

The direct torque limit, damping, armature, and implicit link inertias set the
reachable acceleration and the stopping distance. They determine whether a
policy can approach a target quickly without overshooting, and whether it can
remain inside the tolerance disk with bounded corrective actions. Because the
action is held for 20 ms, a policy cannot react to intermediate motion inside
that interval. This makes endpoint speed and distance-to-boundary margin more
important than a single minimum-distance measurement.

The current training implementation samples only radii 0.14-0.20 m, whereas
official evaluation includes 0.06-0.20 m. A policy trained without other
changes therefore receives no direct target experience in the inner 0.06-0.14
m band, where the required elbow fold is larger and the posture/velocity
relationship differs. The shaped training reward supplies progress and
closeness signals, hold-progress and completion bonuses, and a small action
cost, but the official outcome remains the uninterrupted hold rather than
reward accumulated during approach.

The physically meaningful behavior classes include: failure to leave the
initial singularity effectively; selecting a branch that violates a joint
limit or takes an inefficient route; reaching the disk but carrying too much
momentum; entering and repeatedly exiting the disk; and converging to a
stable posture that maintains the full hold. These are distinct mechanisms
even when their episode-level result is the same failure.

## Unknowns

The XML does not explicitly state link density, body mass, or the complete
inertia tensors. MuJoCo derives effective inertial quantities from the
geometries and model defaults at load time, but their exact compiled values
and the resulting coupled inertia matrix have not been established here.
Likewise, no pre-campaign measurement establishes maximum joint speed,
endpoint speed, acceleration, stopping distance, settling time, or the
amount of endpoint excursion between control checks for each target class.

It is unresolved which elbow branch gives the greatest robustness, rather
than merely reachability, across radius and angle. The answer may depend on
the initial singularity, shoulder-limit proximity, torque saturation, and
the stopping margin required by the 1 cm disk. It is also unresolved whether
the inner-target gap in the current training distribution produces a
generalization failure, a branch-selection failure, or mainly a
stabilization failure.

Before campaign evidence, the policy's learned timing and correction
strategy are unknown: it may optimize fast arrival, low endpoint velocity,
posture stabilization, or a brittle sequence that only passes sampled
control-boundary checks. No claim about any of these behaviors, or about the
98% objective, follows from the mechanics alone.

The most informative physical quantities over a complete episode are target
radius and angle; both joint positions and velocities; endpoint position,
velocity, and distance-to-target; action/torque magnitude and saturation;
inverse-kinematic branch and joint-limit margins; Jacobian conditioning; time
to first entry; time to low-velocity convergence; the maximum uninterrupted
hold length; the number and timing of hold interruptions; and the minimum,
final, and boundary-margin distances. Together these distinguish geometric
reachability, dynamic stopping, stabilization, and true uninterrupted-hold
failure rather than treating all failures as one scalar outcome.
