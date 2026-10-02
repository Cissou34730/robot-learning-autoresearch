# Scientific model of the two-joint reach-and-hold task

This is the pre-campaign physical model. It separates quantities stated by the
human-authored task and robot implementation from deductions about the coupled
robot, controller, and success condition. It contains no campaign evidence and
does not assume that the current learning recipe is effective.

## System model

The robot is a fixed-base planar serial manipulator with two revolute degrees of
freedom. Let \(q_1\) be the shoulder angle and \(q_2\) the elbow angle, both
measured about the vertical \(z\)-axis. The upper arm has length \(l_1=0.12\) m
and the forearm has length \(l_2=0.10\) m. The end-effector position is therefore

\[
p(q)=\begin{bmatrix}
0.12\cos q_1+0.10\cos(q_1+q_2)\\
0.12\sin q_1+0.10\sin(q_1+q_2)\\
0.02
\end{bmatrix}.
\]

The arm starts at \(q=(0,0)\), with zero velocity, so it is fully extended along
positive \(x\) and the end effector starts at radius 0.22 m. Each joint is
limited to \([-170^\circ,170^\circ]\). The target is moved into the same
\(z=0.02\) plane, so the three-dimensional distance used by the task is
effectively planar.

An episode samples target angle over the full circle and target radius uniformly
between 0.06 m and 0.20 m for official evaluation. The target is a non-contact
mocap marker; the plane, base, links, and target do not impose a manipulation or
collision objective. The objective is purely positional: after entering the
1-cm Euclidean tolerance, the end effector must remain there for 2 seconds,
implemented as 100 consecutive control updates, within a maximum of 500
updates.

## Established facts

These are direct repository facts, not measurements of learned behavior.

- The mechanism has two independently actuated hinge joints and no gravity. Each
  joint has damping 0.5 and armature 0.01 in the MuJoCo model. Link dimensions
  and the end-effector site are fixed by the XML geometry.
- The MuJoCo integration step is 0.002 s. Each policy action is clipped to
  \([-1,1]^2\), passed through unchanged, and held for 10 integration steps.
  Thus the policy acts at 0.020 s intervals (50 Hz), while the physical state
  evolves at 500 Hz. The two motor actuators have gear 5, giving a nominal
  gear-scaled joint command of up to 5 actuator force units per joint.
- Reset explicitly sets both joint positions and velocities to zero, advances
  the model, samples the target, and advances again. The target is sampled with
  independent radius and angle draws; the training constructor currently uses
  only radii 0.14--0.20 m, whereas the official distribution includes
  0.06--0.20 m.
- The success distance is measured after each 10-substep action. A distance at
  or below 0.01 m increments the hold counter; one distance above tolerance
  resets it to zero. Completion occurs at 100 consecutive in-tolerance updates.
  The policy is not given the hold counter or the outside-after-hold state.
- The 11-element observation contains the two joint positions, two joint
  velocities, the three-dimensional end-effector-to-target displacement, and
  four wrapped angular errors to the two analytic inverse-kinematic branches
  (positive and negative elbow solutions).
- The observation exposes the physical configuration, velocity, and relative
  target location, but not forces, accelerations, actuator state, target
  radius/angle as separate variables, elapsed hold time, or whether a prior
  in-tolerance run was interrupted. The target location is nevertheless
  recoverable geometrically from the relative displacement and current
  end-effector position.

## Physical consequences

Ignoring joint limits, the two-link position workspace is the annulus from
\(|l_1-l_2|=0.02\) m to \(l_1+l_2=0.22\) m. The official radial band lies
inside this annulus, so failure is not explained by a target that is outside
the unconstrained geometric reach. The angular joint limits still trim the
configuration representation near their boundaries, but the two-link geometry
provides the usual elbow-up and elbow-down alternatives across the official
band. For a target \(x,y\), the branch solutions satisfy

\[
\cos q_2=\frac{x^2+y^2-l_1^2-l_2^2}{2l_1l_2},
\]

with \(q_2\) of either sign and a corresponding shoulder angle. The policy
therefore has a discrete configuration choice in addition to continuous
trajectory control. The two branches can have different joint velocities,
torques, and proximity to limits even when their end-effector error is
identical.

The action is a torque-like direct motor command rather than a desired joint
position or velocity. Reaching is consequently a dynamic maneuver: the policy
must coordinate both joints, dissipate or reverse momentum, and stop with
enough margin that damping and residual motion do not carry the end effector
outside a 1-cm disk. Since gravity and contact forces are absent, there is no
static load to balance at the target; the main stabilization problem is
inertial motion, joint damping, actuator authority, and the configuration
dependent Jacobian. The 20-ms zero-order hold makes each decision a short
open-loop burst, so high-frequency corrections are unavailable to the policy
even though the simulator integrates ten finer steps between decisions.

The task has two coupled phases rather than a reach-only objective. The first
is convergence from the reset state to the target, including branch selection
and transient control. The second is a low-velocity invariant behavior inside
the tolerance disk. A trajectory can have an excellent minimum distance and
still fail because it crosses the boundary once during the hold. Conversely,
arriving early is valuable because it leaves more of the 500-step horizon for
the 100-step hold. Scientifically meaningful whole-episode quantities therefore
include time to first tolerance entry, joint position and velocity at entry,
distance and signed radial/tangential error through the hold, maximum held run,
number and timing of hold interruptions, action saturation, torque work, and
the Jacobian conditioning along the trajectory. These distinguish geometric
reach failure, transient overshoot, poor convergence, and terminal
stabilization failure.

The physical state is close to Markov from the observation because positions,
velocities, and target displacement are supplied. The task state is not fully
Markov for a feed-forward policy: two identical physical observations can carry
different hidden hold counters. The policy can maintain the physical condition
without knowing the exact remaining duration, but it cannot directly observe
the episode-level progress variable that determines when success will
terminate. The wrapped branch errors also introduce angular representation
boundaries even though the underlying target geometry is continuous.

Operationally, "uninterrupted" is tested at the 50-Hz control boundaries, not
by recording the tolerance predicate at every 0.002-s integration substep.
The simulator still evolves between checks, so a brief substep excursion that
returns before the next check is not separately represented in the success
counter. This is part of the current interaction semantics and must be
distinguished from a claim about continuous physical containment.

## Unknowns

These quantities are unresolved before campaign evidence and should not be
treated as known policy capabilities:

- The XML does not explicitly state link density, masses, centers of mass,
  inertias, or the resulting configuration-dependent mass matrix. The
  effective inertia and acceleration under a saturated command therefore
  remain numerical properties of the instantiated MuJoCo model, not values
  justified by the dimensions alone.
- The resulting transient response is unknown: settling time, overshoot,
  oscillation, minimum achievable steady-state error, and the amount of
  control authority remaining near joint limits or awkward Jacobian
  configurations have not been measured.
- The exact joint-limit-trimmed workspace and conditioning over every official
  target, including the most difficult angular and radial cases, has not been
  enumerated. Geometric reachability does not establish dynamically reliable
  reachability within the 10-second horizon.
- It is unknown which IK branch a learned policy will select, whether it can
  switch branches safely, and whether branch preference correlates with target
  angle, radius, saturation, or hold stability.
- It is unknown whether the supplied state and analytic branch residuals are
  sufficient for the chosen policy class to infer a robust stabilizing action
  under the hidden hold counter, and unknown how much performance is lost on the
  official inner-radius band that is absent from the current training range.
- No pre-campaign claim can be made about success percentage, failure-class
  frequencies, or attainment of the required 196 successes out of 200 official
  episodes. Those are empirical properties of the learned closed-loop system,
  not consequences of the robot's geometric reach.
