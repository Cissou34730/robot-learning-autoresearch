# Scientific model of the two-joint reach-and-hold system

This is the pre-campaign physical model. It separates facts implemented by the
scenario from their mechanical consequences and from quantities that cannot be
known until the compiled system or learned behavior is measured.

## Established facts

- The robot is a planar two-revolute-joint arm. The shoulder and elbow axes are
  both the world `z` axis. The upper arm is 0.12 m long and the forearm is
  0.10 m long, so the end-effector point is 0.22 m from the base at maximum
  extension. The elbow angle is relative to the upper arm because the forearm
  body is nested under it; the shoulder angle is the arm's absolute planar
  orientation. Both joints are limited to -170 to 170 degrees.
- The base is at the world origin. The arm moves in the horizontal plane at
  `z = 0.02` m. The target is a non-contacting mocap sphere whose `z` coordinate
  is set to the end-effector plane. The target is static during an episode.
- Official targets have radius 0.06--0.20 m and angle spanning the complete
  circle. The implementation samples angle and radius independently and
  uniformly. The target is therefore planar and fixed, but its direction is
  not restricted to a convenient workspace sector.
- Reset sets both joint positions and velocities to zero before sampling the
  target. The initial end effector is consequently at `(0.22, 0, 0.02)` m,
  fully extended along positive `x`.
- The MuJoCo integration timestep is 0.002 s and gravity is zero. An action has
  two components in `[-1, 1]`; it is clipped, assigned to the two motor
  actuators, and held while the physics advances. Under the official timing,
  one control step is 0.020 s, or ten physics integration steps.
- Each motor has gear 5 and a `[-1, 1]` control range, with joint damping 0.5
  and armature 0.01. The links are capsule geoms; no explicit link masses or
  inertias are specified in the XML. All listed geoms have collision disabled,
  so the task contains no arm-target or arm-ground contact.
- Success is based on the Euclidean end-effector-to-target distance. The
  end-effector must be within 0.01 m for 100 consecutive control steps
  (2 seconds), without an intervening outside step. The episode may run for at
  most 500 control steps.
- The scenario observation has 11 values: two joint positions, two joint
  velocities, the three-dimensional end-effector-to-target displacement, and
  four wrapped joint-angle errors to the two inverse-kinematic solutions
  (open-elbow and folded-elbow). The action mapping is identity apart from the
  environment's clipping.

## Physical consequences

### Kinematics and available configurations

With shoulder angle \(q_1\) and relative elbow angle \(q_2\), the planar
end-effector position is

\[
x = 0.12\cos q_1 + 0.10\cos(q_1+q_2),\qquad
y = 0.12\sin q_1 + 0.10\sin(q_1+q_2).
\]

The unconstrained workspace is an annulus from 0.02 m to 0.22 m. The official
radial interval lies inside this annulus, so every official target is
geometrically reachable rather than requiring an impossible radius. For a
target at radius \(r\), the two nominal elbow solutions are

\[
q_2 = \mathord{\pm}\arccos
\frac{r^2-0.12^2-0.10^2}{2(0.12)(0.10)}.
\]

The corresponding shoulder angle rotates the two-link shape to the target
direction. Over 0.06--0.20 m, both branches have elbow magnitudes below 170
degrees and can be represented with shoulder angles within the joint limits;
the official geometry therefore offers two physically distinct postures for
each target, barring the usual convergence at a workspace singularity.

The task's one-centimetre acceptance region is a planar disk because target and
end effector share `z`. It is a software success region, not a mechanical
fixture: nothing constrains the arm once it enters the disk. The target is
closest to the reset posture when it is near the positive `x` direction and
largest in radius, while targets elsewhere require substantial reorientation
from the initially extended state.

### Actuation and dynamics

The motor commands produce bounded generalized joint torques with nominal
gear-scaled magnitude up to 5 in the MuJoCo actuator convention. The command is
piecewise constant for 20 ms, so the policy controls a sampled-data mechanical
system rather than continuously selecting torque. The zero-gravity model
removes gravitational loading: at a stationary target posture with zero joint
velocity, no torque is needed to oppose gravity. During motion, torque must
accelerate the links, overcome velocity damping, and brake the coupled arm.

The arm's inertia is configuration-dependent. Shoulder motion moves both links,
whereas elbow motion primarily redistributes the forearm; consequently the same
action can have different angular and Cartesian effects at different postures.
The 0.01 armature adds effective rotational inertia at each actuated joint, and
the 0.5 damping terms dissipate motion. The capsule geometry and MuJoCo's
compiled defaults determine the remaining mass and inertia. With no contacts,
there is no external impact or load to stabilize against, but residual velocity
and the policy's own torque can carry the end effector across the tolerance
boundary.

The two-link Jacobian changes rank near full extension and full folding. Radial
motion near full extension is especially dependent on coordinated changes in
both joints, while tangential motion is more directly produced by orientation
changes. The official maximum radius, 0.20 m, is close to the 0.22 m reach
limit, so some targets require a relatively extended configuration even though
they are not exactly singular. Near the inner part of the distribution, the
arm instead uses a strongly folded elbow configuration. Thus target radius
changes both the inverse-kinematic posture and the local control sensitivity;
target angle changes the required shoulder orientation and the direction in
which actuator effort must be coordinated.

### Coupled behavior required for success

An episode requires a sequence of coupled capabilities, not merely a small
instantaneous position error:

1. The policy must infer the target-relative geometry and select or reach one
   of the feasible posture branches.
2. It must generate a time-ordered joint trajectory from the reset posture,
   using enough torque to rotate and accelerate the links without losing the
   target through the finite control interval.
3. It must reduce joint velocity and Cartesian error before or while entering
   the one-centimetre disk. Reaching the disk with substantial momentum is not
   success in a dynamical sense because the disk has no physical containment.
4. It must maintain a locally stable, low-velocity behavior for 100 sampled
   observations. Any one step outside the disk resets the hold counter to zero,
   so a transient overshoot converts an otherwise good reach into a failed
   episode.

The observation contains the current velocity, so braking and stabilization can
in principle be state-based rather than inferred only from history. In the
absence of disturbances, a zero-velocity target posture can be maintained with
zero gravity-compensation torque; the difficult part is reaching that
condition without oscillation and preserving it under the policy's discrete
updates. The training reward also supplies progress, closeness, hold-progress,
completion, and action-cost terms, but the episode outcome remains the
uninterrupted physical tolerance condition rather than the accumulated reward.

### Sensing, control, and outcome

The raw scenario observation exposes the joint state and the Cartesian error.
Because the target-relative displacement and end-effector position are
available through the observation construction, the target position is not
hidden from a memoryless policy in this deterministic model. The four
inverse-kinematic error values make both candidate postures explicit, although
the policy still has to decide whether to stay on one branch and how to move
between configurations. Joint positions and angular errors use different
representations: the latter are wrapped to \([-\pi,\pi)\), so equivalent
postures near an angle boundary can have a representation discontinuity even
when their physical displacement is small.

At each control step, the policy action becomes motor control, the simulator
advances the coupled joint state, and the resulting end-effector distance
updates the hold state. The target is not physically sensed through contact,
and the observation contains no force, torque, acceleration, or disturbance
measurement. There is also no configured sensor noise in the scenario code.
The principal failure classes are therefore: choosing an ineffective or
poorly conditioned posture, insufficient or excessive actuation during the
reach, entering the tolerance disk with unrecovered velocity, oscillating
across its boundary during the hold, and failing to complete the hold before
the 500-step horizon.

Quantities that are physically meaningful across the complete behavior are
target radius and angle; joint positions, velocities, and accelerations;
commanded and realized joint torques; end-effector position and velocity;
distance to target; time and velocity at first entry; minimum distance;
continuous in-tolerance duration; number and timing of hold interruptions;
and which inverse-kinematic branch the trajectory approaches. The existing
evaluation diagnostics directly preserve target geometry, minimum and final
distance, first reach step, maximum held duration, total in-tolerance steps,
and interruptions, which separate reach quality from hold reliability.

## Unknowns

- The compiled link masses, centers of mass, and inertia tensors are not
  explicit in the XML. Their values, and the exact actuator force/torque
  scaling after MuJoCo compilation, determine the available acceleration and
  braking authority.
- The resulting closed-loop settling time, overshoot, residual velocity, and
  tolerance-boundary margin are unknown for every target geometry. In
  particular, it is not yet known whether the near-extended and strongly
  folded portions of the distribution produce distinct failure rates.
- No campaign evidence exists about whether a learned policy reliably chooses
  one inverse-kinematic branch, switches branches, or becomes unstable near
  representation and Jacobian singularities.
- The sensitivity of uninterrupted holding to the 20 ms action interval,
  damping, armature, action saturation, and the policy's temporal behavior is
  unresolved. The absence of external disturbances makes this a question of
  learned feedback and numerical dynamics, not disturbance rejection.
- The observation is physically sufficient for the modeled target and joint
  state, but the effect of any policy-runtime state or preprocessing on the
  controller's effective information and action distribution has not been
  established here.
- The reward's relationship to the eventual episode objective is only
  specified mathematically; there is no evidence yet that optimizing its
  progress and hold terms produces at least 196 successes out of the official
  200 episodes. That success rate remains an empirical campaign question.
