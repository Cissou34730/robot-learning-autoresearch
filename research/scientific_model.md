# Scientific model of the two-joint arm reach-and-hold task

The system is a deterministic planar manipulation problem in which a policy
must move a two-link arm from one fixed posture to a randomly selected
stationary point, then regulate the end effector tightly enough for a complete
hold. The task is not only inverse kinematics: the policy must select and
execute a dynamically feasible trajectory, dissipate motion, and remain inside
the tolerance under the simulator's sampled control loop.

## Established facts

### Robot, geometry, and state

The robot is a serial two-revolute-joint arm. The shoulder and elbow axes are
parallel and normal to the horizontal arm plane. The upper arm is 0.12 m and
the forearm is 0.10 m, so the end-effector position for joint angles
\(q=(q_1,q_2)\) is

\[
x = 0.12\cos q_1 + 0.10\cos(q_1+q_2),\qquad
y = 0.12\sin q_1 + 0.10\sin(q_1+q_2).
\]

The arm plane is at \(z=0.02\) m. The configured joint ranges are
\([-170,170]\) degrees for both joints. The geometric reachable annulus is
between 0.02 m and 0.22 m from the base. The base is fixed; there are no
other arm degrees of freedom.

At reset, both joint angles and velocities are zero. The arm is therefore
straight along positive \(x\), with the end effector at \((0.22,0,0.02)\).
The target is a non-actuated mocap body with no contact interaction. On every
reset its \(x,y\) position is sampled with an angle uniformly over
\([-\mathop{\rm pi},\mathop{\rm pi}]\) and a radius uniformly over
\([0.06,0.20]\) m, and its \(z\) coordinate is set to the arm plane. Thus the
implementation is uniform in radius, not uniform in disk area. The target is
stationary during an episode.

### Actuation, timing, and simulator dynamics

The MuJoCo model has zero gravity and a physics timestep of 0.002 s. Each
policy action is clipped to two values in \([-1,1]\), applied directly to the
two motor controls, and held for 10 physics steps. The policy therefore acts
at 0.02 s intervals (50 Hz), while the physical state evolves at 500 Hz.
Each motor has gear 5, giving a nominal joint torque command in the range
\([-5,5]\) in the model's torque units. There is no position or velocity
servo between the policy and the joints.

Both joints have damping 0.5 and armature 0.01. Link masses and inertias are
compiler-derived from the capsule geometries rather than explicitly written
as body inertials. In the loaded model, the upper-arm body has mass
0.09896 kg and principal inertia approximately
\((1.6827,1.6827,0.1081)\mathord{\times}10^{-3}\) kg m2; the forearm body has
mass 0.05248 kg and principal inertia approximately
\((0.6110,0.6110,0.0367)\mathord{\times}10^{-3}\) kg m2. The fixed base and
mocap target have no dynamic effect on the arm motion. The non-colliding plane
and target mean that contact forces, friction, and impact dynamics do not
participate in the official task.

The physical state is consequently the two joint positions and two joint
velocities, propagated by inertial, motor, and damping dynamics. With gravity
absent, every stationary configuration is an equilibrium at zero velocity and
zero motor command; the control challenge is to create motion and then remove
its velocity accurately, not to counteract a load while holding.

### Task outcome and policy interface

The end-effector-to-target Euclidean distance is evaluated after each 0.02 s
control interval. A sample is inside the tolerance when that distance is at
most 0.01 m. Success requires 100 consecutive inside-tolerance samples, which
corresponds to 2 s, and an episode is truncated after 500 control steps
(10 s). A single outside sample resets the hold counter; reaching the target
without completing the counter is a failure.

The observation has 11 values: the two joint positions, two joint velocities,
the three-dimensional end-effector-to-target displacement, and four wrapped
angular residuals to the two analytic inverse-kinematic branches. For target
radius \(r\), the branches use

\[
q_2 = \mathord{\pm}\arccos
\left(\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}\right),
\]

with the corresponding shoulder angle computed from the target direction.
The observation therefore exposes the current motion state and target-relative
error, while explicitly representing elbow-open and elbow-folded solutions.
The target is not moving and there are no force, contact, or noise sensors.
Because joint configuration and the end-effector-relative vector are both
observed and the kinematics are known, the target's planar location is
reconstructible in principle; target velocity and any unmeasured disturbance
are not.

The official assessment uses 200 independently seeded target episodes, at most
500 control steps each. The campaign goal is at least 196 complete holds, or
98% episode success.

## Physical consequences

The official target annulus lies inside the arm's geometric annulus, so the
central physical problem is not static reachability. For the smallest target
radius, the elbow angle is about 150 degrees in magnitude; for the largest it
is about 50 degrees. Both elbow branches are therefore geometrically
available, subject to representing the shoulder angle within its configured
range. The two branches correspond to qualitatively different paths around
the arm's base, and a policy can switch neither branch instantaneously without
passing through a different configuration trajectory.

The reset posture is the fully extended outer-boundary configuration. At this
posture the planar end-effector Jacobian is rank one: first-order joint motion
primarily produces tangential motion, while reducing the maximum reach requires
the arm to bend. This makes the early trajectory different from a simple
independent Cartesian correction, especially for targets close to the initial
radius or at large angular offsets. Nearer targets require more folding and
usually more joint displacement before convergence.

Reaching, braking, and holding are coupled. A large torque can reduce
position error quickly but creates joint velocity that must be removed before
the end effector can stay within a 1 cm disk. Since commands are held for
20 ms and damping is finite, late corrections can produce overshoot or
oscillation. Conversely, once a configuration is settled, zero gravity makes
the required steady torque small; the difficult part of the hold is
maintaining low velocity and avoiding corrections that drive the endpoint back
outside the disk. The 2 s requirement thus tests closed-loop convergence and
stabilization, not merely whether an inverse-kinematic pose was reached.

The Cartesian tolerance has different angular consequences across the task.
At a 6 cm target radius, a 1 cm tangential error is roughly 9.6 degrees of
target-direction error; at 20 cm it is roughly 2.9 degrees. The same distance
criterion therefore demands finer angular regulation at larger radii, while
near the workspace boundary the kinematic Jacobian is more poorly conditioned.
Radial and tangential error should not be expected to have equal control
difficulty.

The sampled success test is strict at the control times but does not inspect
the ten intermediate MuJoCo states separately. An excursion between two
samples that returns inside by the next sample is invisible to the task
predicate, whereas one sampled outside point destroys the entire accumulated
hold. This creates a distinction between physical continuous-time stability
and the implemented 50 Hz success semantics. There are no collisions or
external perturbations to expose that distinction beyond the arm's own
inertial transients and numerical integration.

The meaningful failure classes are consequently separable in principle:
failure to choose a feasible elbow/shoulder configuration, slow or poorly
directed transit, overshoot caused by insufficient braking, and intermittent
or sustained hold loss. The target distribution also makes failures
angle-dependent and radius-dependent even though the physical model itself is
rotationally symmetric; the fixed initial posture and joint limits break the
practical symmetry of the control problem.

## Unknowns

Before campaign evidence exists, the following quantities are unresolved:

* The closed-loop time and torque required to move from the reset posture to
  each target region, including how strongly the initial near-singularity
  affects transit and how action saturation limits fast corrections.
* The amount of overshoot and settling time produced by plausible control
  sequences at different radii, angles, and elbow branches. The model
  parameters are specified, but their policy-level consequences have not
  been measured.
* Whether the observation's two branch residuals lead a learned policy to
  select one stable branch, switch branches, or use a dynamically convenient
  path that is not well described by a single branch residual.
* How much of the 1 cm margin is consumed by residual joint velocity and
  discrete action holding, and whether a policy that appears settled at
  control samples has appreciable unobserved between-sample excursions.
* How performance varies over the full angle-radius distribution, especially
  near the initial outer boundary, at small radii requiring deep folding, and
  near joint-limit representations. No symmetry or branch preference should
  be assumed for a learned policy.
* Whether the 11-value representation is sufficient for reliable target
  conditioning under learning. The target-relative state is theoretically
  reconstructive with known kinematics, but learning may still be sensitive
  to wrapped angular residuals, velocity scale, or branch ambiguity.
* The degree to which success is limited by physical control and the degree
  to which it is limited by policy optimization, exploration, or
  normalization. No training or campaign result yet identifies a dominant
  cause.

The most scientifically informative quantities for later interpretation are
target radius and angle; joint positions, velocities, and accelerations;
command and torque saturation; end-effector radial and tangential error;
minimum distance; first entry time; longest consecutive in-tolerance run;
hold interruptions; and the selected inverse-kinematic branch. Together these
quantities distinguish geometric choice, trajectory execution, convergence,
and stabilization without treating episode success alone as a mechanism.
