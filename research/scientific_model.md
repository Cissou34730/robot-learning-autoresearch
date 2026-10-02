# Scientific model of the two-joint reach-and-hold task

The system is a planar, torque-actuated two-link arm whose controller must
convert a target-relative state into a transient reach and then into a
low-velocity equilibrium inside a small spatial tolerance. The episode outcome
is therefore not determined by reaching alone: any excursion outside the
tolerance resets the hold.

## Established facts

### Physical structure and initial state

The shoulder joint angle \(q_1\) rotates the upper arm about the vertical
world axis. The elbow angle \(q_2\) is relative to the upper arm, so the
end-effector position in the arm plane is

```text
x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
y = 0.12 sin(q1) + 0.10 sin(q1 + q2).
```

The links are 12 cm and 10 cm long. Both hinge joints have limits of -170 to
170 degrees. The arm plane is at z = 0.02 m; the target is placed in that
plane, so the task is planar even though distance is evaluated as a 3-D
Euclidean distance. The target and the floor do not provide contact forces.

Every episode starts at \(q_1=q_2=0\) with zero joint velocity. The links are
then collinear along positive x and the end effector is at (0.22, 0, 0.02) m.
The target radius is sampled between 0.06 and 0.20 m and its angle covers the
full circle. In the implementation, radius and angle are sampled
independently and uniformly. The official evaluation uses this 0.06--0.20 m
range; the current training environment samples only 0.14--0.20 m.

### Actuation, integration, and dynamics

The policy emits two values in [-1, 1]. The current physical action mapping is
the identity, after which the environment clips the values and holds them in
the MuJoCo control vector. Each motor drives one joint with gear 5, giving a
command-proportional generalized torque with a nominal range of approximately
[-5, 5] in the model's torque units. There is no lower-level position or
velocity controller.

MuJoCo integrates at 0.002 s. Each policy action is held for 10 simulation
steps, making the policy control interval 0.020 s. The joints have damping
0.5 and armature 0.01. Gravity is disabled. Link masses and inertias are
generated from the capsule geometries and MuJoCo's implicit density defaults,
rather than specified as explicit physical parameters; the loaded model gives
approximately 0.099 kg for the upper-arm geometry and 0.052 kg for the
forearm geometry. Consequently, acceleration depends on configuration through
the coupled link inertia as well as on damping and armature.

### Task and sensing semantics

The target is a fixed mocap point, not a dynamic object. Success distance is
at most 0.01 m. After each 0.020 s control interval, the environment increments
the held-step count if the sampled distance is within tolerance and resets it
to zero otherwise. One hundred consecutive in-tolerance samples are required,
corresponding to two seconds. The episode can run for at most 500 control
steps. Operationally, “uninterrupted” is checked at these post-action samples;
the implementation does not inspect the trajectory between the ten internal
MuJoCo integration steps.

The observation has 11 values:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional end-effector-to-target displacement;
4. four wrapped joint-angle errors to the two inverse-kinematic solutions,
   one with positive and one with negative elbow angle.

Because the target is fixed in the arm plane, its position can be reconstructed
from the end-effector position and the relative displacement. The z
displacement is consequently expected to be identically zero in this task.
The observation contains no torque, acceleration, contact signal, previous
action, or hold counter.

## Physical consequences

### Workspace and kinematic alternatives

Ignoring joint limits, the radial workspace is the annulus from
\(|0.12-0.10|=0.02\) m to \(0.22\) m. With the 170-degree elbow limit, the
smallest radial distance is about 0.0277 m, still inside the official target
range. Thus all official radii are kinematically reachable, although the
limits can remove one solution for some target directions near the angular
boundary.

For a target radius \(r\), the two nominal inverse-kinematic branches are

```text
q2 = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q1 = target_angle - atan2(0.10 sin(q2), 0.12 + 0.10 cos(q2)).
```

At 6 cm, the elbow is about +/-150 degrees; at 20 cm, it is about +/-49
degrees. The two branches place the elbow on opposite sides of the shoulder
target ray. They are geometrically equivalent in endpoint position but not
dynamically equivalent: their joint configurations, inertia coupling, torque
directions, and approach velocities differ. The four IK errors expose both
alternatives, while the policy still has to choose and stabilize one.

The reset posture is fully extended, where the planar Jacobian has rank one.
An instantaneous joint change can move the endpoint mainly transverse to the
arm, while inward radial motion requires first creating elbow bend and then
using the coupled configuration. This makes departure from the reset posture
qualitatively different from motion after the arm has bent. The Jacobian also
varies across the annulus, so the same Cartesian error can require different
joint torques and produce different endpoint velocities.

### Coupled reach, convergence, and hold

The action affects joint acceleration, not endpoint position directly. A
large command can reduce travel time but also create velocity that must be
removed inside a 1 cm ball. Damping dissipates motion, but with gravity and
external contact absent, a stationary configuration needs little or no torque
to persist. The difficult transition is therefore from commanded movement to
low-speed stabilization, not maintenance against a persistent load.

A successful behavior must:

- escape the initially extended configuration;
- select a reachable shoulder/elbow configuration;
- generate a trajectory that arrives without excessive residual velocity;
- correct endpoint error using the local, configuration-dependent Jacobian;
- keep every sampled endpoint inside the tolerance for 100 consecutive
  control intervals.

These requirements interact. Overshoot, oscillation, or a single corrective
action that crosses the boundary destroys all accumulated hold progress.
Targets near 6 cm require a deeply folded elbow, while targets near 20 cm are
closer to extension; target angle changes the required shoulder orientation
and the direction in which each motor must act. A fast reach can therefore
have worse episode success than a slower reach with a reliable settling
margin.

The physical state and target are largely observable from the supplied
features, but the task automaton is not: the policy cannot tell from one
observation how many consecutive in-tolerance steps have already elapsed.
The controller must either maintain a robust equilibrium indefinitely or use
internal memory. A policy that merely reaches the tolerance intermittently
will not satisfy the episode criterion.

Meaningful measurements of the complete behavior are target radius and angle,
chosen IK branch, initial and final distance, time to first enter tolerance,
endpoint velocity at entry, settling and oscillation behavior, peak and
steady action magnitude, joint-limit proximity, longest consecutive hold, and
the timing and magnitude of hold interruptions. Success percentage alone
cannot distinguish a failure to reach from a failure to stabilize.

## Unknowns

- The effective joint-space inertia, acceleration response, and settling time
  over the full configuration space have not been measured. The XML fixes
  damping, armature, geometry, timestep, and gear, but leaves mass density
  implicit, so the generated inertias are a model-default dependency rather
  than a calibrated physical statement.
- The action-to-motion response near the initial Jacobian singularity and
  near the folded and extended portions of the target annulus is unresolved.
  In particular, it is not known whether the available torque margin permits
  fast arrival and a comfortable braking margin for every target.
- It is unknown whether one IK branch is systematically easier to stabilize,
  whether the learned controller will switch branches during an episode, and
  how branch choice interacts with target angle and joint limits.
- The simulator samples hold status only every 20 ms. Any excursion outside
  the tolerance between checks, and the resulting difference between sampled
  and truly continuous physical holding, is not represented in the recorded
  success state.
- The observation omits hold progress, action history, and force-like
  quantities. Whether a feed-forward controller can achieve the required
  robustness from the current state features alone, or needs useful temporal
  memory, is unresolved before training evidence.
- The frequency and consequence of any arm-geometry self-contact in folded
  configurations has not been characterized. It is not part of the target or
  floor interaction and cannot be inferred solely from endpoint reachability.
