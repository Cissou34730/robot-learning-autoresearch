# Scientific model of the two-joint arm reach-and-hold task

This is the campaign-start model, constructed before training or campaign
evidence. It separates repository facts from their physical implications and
from quantities that remain unresolved.

## Established facts

### Morphology and kinematics

The robot is a planar serial two-revolute-joint arm. The shoulder rotates about
the vertical z axis at the base; the elbow rotates about the same axis at the
end of the 0.12 m upper arm. The forearm is 0.10 m long, so the end-effector
site is at the end of a two-link chain with link lengths
\(L_1=0.12\) m and \(L_2=0.10\) m. Its motion is confined to the horizontal
plane at \(z=0.02\) m. The capsule and base visuals do not participate in
contact: all listed geoms have collision disabled, as does the target sphere.

With shoulder angle \(q_1\) and relative elbow angle \(q_2\), the endpoint
position relative to the base is

\[
x=L_1\cos q_1+L_2\cos(q_1+q_2),\qquad
y=L_1\sin q_1+L_2\sin(q_1+q_2).
\]

The declared range of each hinge is -170 to 170 degrees. Without those limits,
the geometric workspace is the annulus from \(|L_1-L_2|=0.02\) m to
\(L_1+L_2=0.22\) m. Official targets lie in the interior annulus
0.06--0.20 m and cover the complete polar angle. For a target radius \(r\),
inverse kinematics gives

\[
\cos q_2=\frac{r^2-L_1^2-L_2^2}{2L_1L_2}.
\]

Across the official radial range, the two elbow branches have
\(|q_2|\) from about 49.5 to 150.5 degrees. Thus both elbow signs are within
the declared elbow range. The corresponding shoulder solutions also have at
least one configuration within the declared shoulder range for every official
target angle. Official geometry is therefore reachable, but it offers two
discrete elbow-up/elbow-down solutions rather than a single prescribed posture.

### Actuation, timing, and simulated dynamics

The two actions are passed directly to the two MuJoCo motor controls and clipped
to [-1, 1]. Each motor has gear 5, so the nominal joint torque command is
approximately \(5\,a_i\) in the actuator's torque convention, with a nominal
range of -5 to 5 torque units. There is no position controller, action
interpolation, or action-to-angle conversion in the policy interface.

The simulator timestep is 0.002 s. One policy action is held constant for ten
MuJoCo steps, giving a 0.020 s control interval and a 50 Hz decision rate.
The official two-second hold consequently requires 100 consecutive control
intervals. An episode may run for at most 500 control intervals, or 10 seconds.

Gravity is explicitly zero. Each hinge has damping 0.5 and armature 0.01.
Consequently, motion is governed by torque, configuration-dependent coupled
link inertia, armature inertia, and velocity damping, without gravitational
loading, contact reaction, or environmental disturbance. The XML does not
state link masses or inertias explicitly; those values are supplied by MuJoCo
model compilation from the geometry/default material parameters. The exact
compiled inertial parameters and any unspecified integrator defaults are not
stated in the human-authored XML.

### Initial state and task geometry

Every reset sets both joint positions and velocities to zero and forwards the
model before sampling the target. The arm therefore starts straight along the
positive x axis, with the endpoint at approximately (0.22, 0, 0.02) m and zero
velocity. The target is static after reset, lies at the same z coordinate, and
is sampled with angle uniform on [-pi, pi] and radius uniform on [0.06, 0.20]
m. This is uniform in radius and angle, not uniform in area.

The initial endpoint-target distance varies with target angle and radius. It is
smallest for a 0.20 m target on the initial +x ray (2 cm) and largest for a
0.20 m target on the opposite ray (42 cm). The endpoint is therefore outside
the 1 cm success tolerance at reset for every official target.

An episode succeeds only when the endpoint distance is at most 0.01 m for 100
successive post-action observations. Any sampled distance above the tolerance
resets the hold counter to zero. The target is not moved and the endpoint is
not subject to contact constraints. The official outcome is consequently a
free-space reach followed by an uninterrupted sampled hold, not a contact or
force-control task.

### Observation and policy interface

The observation has 11 values:

* the two joint positions and two joint velocities;
* the three-dimensional endpoint-minus-target vector;
* four wrapped angular residuals from the current posture to the two computed
  inverse-kinematic branches, two residuals for each branch.

The target is not supplied as a separate field, but it can be reconstructed
from the endpoint position and endpoint-minus-target vector. The target's
position is therefore observable for this deterministic task. Joint position,
velocity, endpoint error, and both candidate branch errors provide nearly all
instantaneous mechanical state needed for feedback. The z error is structurally
zero because both bodies remain in the same plane.

There is no specified sensor noise, actuator noise, disturbance, or target
motion. The observation does not include the hidden hold counter, prior
in-tolerance history, applied torque, or a continuous-time record between
control observations. The wrapped residuals also have the usual angle
discontinuity at the -pi/pi representation boundary. A feed-forward policy
therefore observes the current physical state but not explicitly how long the
current hold has lasted; a recurrent policy could additionally encode history.

## Physical consequences

The task decomposes into coupled behaviors rather than independent reach and
hold subtasks. The controller must infer the target error, choose one of the
two valid inverse-kinematic branches, accelerate the coupled arm toward that
configuration, reduce joint and endpoint velocity, and then supply sufficiently
small corrective torques to remain in the tolerance disk. A reach policy that
arrives with residual velocity can fail the task even when its minimum distance
is excellent. Conversely, a stable posture is irrelevant if the policy cannot
reach it within the 500-step budget.

The two branches are physically equivalent in endpoint position but not in
trajectory. Starting from \(q_2=0\), choosing the positive or negative elbow
branch requires motion in opposite elbow directions and generally different
shoulder motion and torque coupling. Branch choice can therefore change
settling time, peak speed, proximity to joint limits, and sensitivity to
correction. A branch switch near the target is not a harmless representation
change: it requires a large configuration change and will normally leave the
tolerance disk before reacquiring it.

The Jacobian maps joint velocity and correction into endpoint velocity. Its
determinant is proportional to \(L_1L_2\sin q_2\), so the official annulus
avoids the exact fully extended and fully folded singularities but includes
configurations whose conditioning varies substantially with radius. Near the
outer radial boundary, small joint changes have an increasingly anisotropic
Cartesian effect. The same action noise or policy error can therefore produce
different endpoint excursions at different target radii and on different
branches. The one-centimeter disk is a small terminal set whose effective size
in joint coordinates depends on this local Jacobian.

Zero gravity and absent contact make the terminal problem an inertial
stabilization problem. There is no surface to catch the arm and no gravity to
pull it away; damping removes velocity, while any continuing or poorly timed
torque can create oscillation. Because actions are held for 20 ms, the policy
cannot correct continuously. The relevant failure boundary is the endpoint
after each control interval, and the controller must tolerate the plant's
within-interval motion while maintaining the next sampled endpoint inside the
disk.

The implementation tests the tolerance after each ten-substep integration
block. Thus “uninterrupted” is operationally 100 consecutive in-tolerance
control samples; a transient excursion that begins and ends between samples is
not represented in the success state. This makes the sampled control loop,
rather than an ideal continuous trajectory, the authoritative task interface.

The main qualitatively different failure classes are:

1. **Geometric or branch failure:** the policy selects an inadmissible or
   poorly conditioned posture despite an available official solution.
2. **Transit failure:** torque saturation, coupled inertia, joint limits, or
   inefficient motion prevents timely arrival.
3. **Settling failure:** the endpoint reaches the disk with excess velocity or
   the policy oscillates across its boundary.
4. **Hold failure:** the policy appears stationary but accumulated corrections
   or model mismatch produce one out-of-tolerance sample, restarting the full
   100-step requirement.
5. **Representation or observability failure:** wrapped angular residuals,
   branch changes, or the absence of explicit hold history causes inconsistent
   actions at otherwise similar terminal states.

## Unknowns

No campaign evidence yet establishes the following quantities or mechanisms:

* the compiled link masses, centers of mass, inertia tensors, and the exact
  numerical joint-space inertia and damping behavior;
* the effective actuator torque convention after MuJoCo compilation, including
  the realized relationship between control, gear, and joint acceleration;
* the amount of endpoint overshoot and settling time produced by saturated,
  moderate, or near-zero commands at each target radius and branch;
* whether one elbow branch is systematically easier under the available torque
  and timing, or whether the best branch depends on target angle and radius;
* the frequency and size of within-interval excursions that are invisible to
  the endpoint-only hold test;
* whether the wrapped branch features cause meaningful policy discontinuities
  at angular representation boundaries;
* the distribution of first-arrival time, peak joint velocity, peak endpoint
  velocity, torque usage, endpoint error, and hold interruptions under a
  learned policy;
* whether the current observation is sufficient in practice for robust
  stabilization, or whether hidden hold history and action history matter for
  achieving 98% episode success;
* how success and failure rates vary jointly with target radius, target angle,
  selected elbow branch, approach direction, and time remaining.

The scientifically meaningful state and outcome quantities are target radius
and angle; joint positions, velocities, and branch sign; endpoint error and
velocity; Jacobian conditioning; applied action/torque and its variation;
first-arrival and settling time; peak speed and overshoot; longest consecutive
in-tolerance run; interruption count; and remaining episode time. Together
these quantities distinguish geometric reachability from dynamic transit,
stabilization, and complete-hold failure without treating episode success
alone as an explanation.
