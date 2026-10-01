# Scientific model of the two-joint reach-and-hold task

The system is a deterministic planar two-link arm whose only randomized
condition is the target location. The learned controller does not make contact
with or manipulate the target: it must move the end effector into a small
Cartesian neighborhood and keep it there. Consequently, success is a coupled
problem of inverse kinematics, transient motion, and disturbance-free
stabilization rather than merely reaching the target once.

## Established facts

### Morphology and kinematics

The arm has two serial hinge joints, shoulder and elbow, both rotating about
the world z axis. The upper arm length is 0.12 m and the forearm length is
0.10 m. Their joint axes and link geometry place the end effector in the
horizontal plane at z = 0.02 m. With joint coordinates
\(q=(q_s,q_e)\), the end-effector position relative to the base is

```text
x = 0.12 cos(q_s) + 0.10 cos(q_s + q_e)
y = 0.12 sin(q_s) + 0.10 sin(q_s + q_e)
z = 0.02
```

At the reset posture \(q=(0,0)\), the links are straight along +x and the
end effector is at (0.22, 0, 0.02). The model declares both joint ranges as
-170 to +170 degrees. In the absence of those limits, the two-link workspace
is the annulus from \(|0.12-0.10|=0.02\) m to \(0.22\) m. The official target
annulus, 0.06--0.20 m, is inside this geometric workspace.

For a target at polar coordinates \((r,\theta)\), the implementation computes
the two standard planar inverse-kinematic elbow branches:

```text
q_e = +/- acos((r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10))
q_s = theta - atan2(0.10 sin(q_e), 0.12 + 0.10 cos(q_e))
```

The observation exposes errors to both branches. Thus the physical task
contains a branch choice, although the two configurations reach the same
Cartesian point and may have different joint-limit margins, velocities, and
transient responses.

### Actuation, timing, and state evolution

Each joint is driven by a direct MuJoCo motor with control range [-1, 1] and
gear 5. The policy action is passed through unchanged and then clipped to
that range; there is no scenario-level position servo or action filtering.
The commanded motor values are held constant for ten MuJoCo steps. The
simulation timestep is 0.002 s, so one policy action advances the physical
system by 0.020 s and the policy operates at 50 Hz. The official two-second
hold therefore requires 100 consecutive post-action checks.

Gravity is explicitly zero. Each hinge declares damping 0.5 and armature
0.01. The arm and target are not physically coupled: the target is a mocap
body, and the plane, base, and target geoms have collision disabled. The
success test uses the Euclidean three-dimensional distance between the
end-effector site and the mocap position, with threshold 0.01 m. Because the
motion is planar and the target is placed in the same z plane, this is
effectively a two-dimensional Cartesian error.

The official target is sampled with angle uniform on [-pi, pi] and radius
uniform on [0.06, 0.20] m. This is uniform in radius and angle, not uniform
in area. The initial joint positions and velocities are reset exactly to
zero before the target is sampled. An episode permits at most 500 control
steps, or 10 s, unless the uninterrupted hold terminates it earlier.

### Sensing and policy interface

The policy receives 11 float observations:

1. the two joint positions and two joint velocities;
2. the three components of end-effector minus target position; and
3. four wrapped angular errors, two for each of the open and folded inverse
   kinematic solutions.

The direct action mapping means these observations are converted to physical
joint motor commands without a scenario-owned change of units. Joint state,
Cartesian error, and the fixed geometry together make the target location
recoverable in principle, even though target coordinates are not separately
listed. The wrapped branch errors introduce a representation discontinuity at
the angle wrap boundary, and the two branch descriptions are redundant with
the current kinematics.

Success requires the measured distance to be at most 1 cm after every one of
100 consecutive control intervals. Any single outside measurement resets the
hold counter. The final benchmark tests one frozen policy on 200 fixed-seed
episodes and requires at least 196 successes.

## Physical consequences

The arm can reach every official target geometrically through at least one
configuration branch expected to remain within the declared joint ranges.
The target distribution nevertheless spans substantially different
configurations: targets near the maximum radius favor relatively extended
postures, while targets near the minimum radius require a more folded elbow.
The shoulder angle and branch that are comfortable for one target direction
can be close to a joint limit or dynamically different in another direction.

The reset condition creates a direction- and radius-dependent transient. The
arm always starts extended toward +x, while the target can be anywhere around
the base. The initial distance ranges from nearly 2 cm for a target near
(0.20, 0) to about 42 cm for a target near (-0.20, 0). A policy must therefore
first generate a large, coordinated angular motion for some episodes, not
merely make local corrections around a common starting target.

The two joint torques are coupled through the serial-link inertia: shoulder
motion moves both links, while elbow motion moves only the forearm. Motor
commands therefore do not map independently to Cartesian x and y motion.
The Jacobian also changes with posture, so the same joint velocity or torque
can produce very different Cartesian motion in different branches. Near
extended or folded configurations, one Cartesian direction can become more
sensitive or less controllable than another. The official annulus avoids the
exact kinematic singular radii, but it does not make the conditioning
identical across targets.

Zero gravity removes a major source of posture-dependent torque. Damping
dissipates velocity, but it does not create a restoring force toward the
target. Once the arm is stationary at a target, zero command can preserve
that posture in the ideal model; while it is moving, however, residual
momentum and the 20 ms action hold can carry the end effector across the
1 cm boundary. A successful controller must therefore converge with low
Cartesian velocity and continue correcting position without inducing
oscillation. It cannot rely on a one-time entry into the tolerance region.

The hold criterion turns small transient errors into categorical failure.
Overshoot, branch switching, motor saturation, delayed corrections, or
numerical motion that would be harmless under a point-reaching metric can
break the entire episode if they cause one sampled distance to exceed 1 cm.
The meaningful control phases are consequently: leave the reset posture,
select and approach a feasible configuration, reduce Cartesian and joint
velocity, enter the tolerance region, and maintain a low-error trajectory
for 2 s. These phases are physically coupled: an aggressive approach can
shorten travel time but increases the stabilization burden, while premature
low-amplitude corrections may fail to overcome the distance and damping
during the approach.

The observation contains enough instantaneous state for a deterministic
closed-loop controller to distinguish position error from velocity and to
compare the two inverse-kinematic branches. It does not directly expose
future target motion because the target is fixed, nor does it expose a
separate actuator state because the actuator is an immediate motor command.
The target is static and there is no exogenous disturbance in the defined
task, so the principal uncertainty is the policy's ability to infer and
control the system's transient response rather than to estimate a changing
world.

## Unknowns

The XML does not explicitly specify link masses, inertias, density, friction
other than hinge damping, solver settings, or the integrator. MuJoCo resolves
these through model defaults and compiled geometry. Their resulting numeric
values determine acceleration, coupled shoulder/elbow response, damping time,
and how much of the available motor authority remains after inertial effects.
They are not established by the source text alone.

The source declares joint ranges but does not by itself establish the
compiled model's exact limit-constraint behavior, solver forces, or whether
any link self-collision can become active. These details could create
qualitatively different failures near a limit or during a fast branch change.
The task geometry and success calculation do not themselves reveal those
runtime effects.

The available motor range is known, but the time required to move from the
reset state, the maximum attainable Cartesian speed, the settling time at
each radius and angle, and the amount of overshoot under a held command are
unknown. They are the quantities that determine whether a 500-step episode
leaves enough margin for 100 consecutive hold checks.

It is also unresolved how the two feasible branches differ in compiled
dynamic cost and numerical robustness over the full target annulus, including
near the shoulder's angular limits. The observation presents both branches,
but their actual success probabilities and basin sizes are not implied by
kinematics alone.

Finally, a scalar episode result will not identify the mechanism of failure.
For scientific interpretation, the complete behavior should be characterized
by target radius and angle, chosen branch, joint positions and velocities,
motor commands and saturation, end-effector distance and Cartesian speed,
time to first entry, longest consecutive in-band run, number and timing of
exits, and the error and velocity distribution during the successful hold.
These quantities distinguish unreachable or limit-constrained motion,
insufficient control authority, poor convergence, overshoot, and failure to
stabilize, while remaining tied to the physical success condition.
