# Scientific model of the two-joint arm reach-and-hold task

## System boundary and task

The robot is a planar two-link serial arm whose shoulder is fixed at the world
origin in the horizontal plane at `z = 0.02 m`. The upper arm has length
`L1 = 0.12 m` and the forearm has length `L2 = 0.10 m`. The end-effector site
is at the distal end of the forearm. The target is a noncontacting mocap body in
the same plane, sampled by radius and angle. The operational target distribution
in the shared environment is `r ~ Uniform(0.06, 0.20) m` and
`theta ~ Uniform(-pi, pi)`.

The episode begins from `q = (0, 0)` and `qdot = (0, 0)`. Thus the arm starts
fully extended along positive x, with the end effector at `(0.22, 0, 0.02) m`.
The target is then placed at `(r cos(theta), r sin(theta), 0.02)`. The target
does not move thereafter. Success is not merely reaching: after the end
effector is within `0.01 m` of the target, it must remain within that tolerance
at 100 consecutive control checks, corresponding to 2 seconds at the official
timing. An episode can last at most 500 control steps.

## Morphology and kinematics

Let `q1` be the shoulder angle and `q2` the elbow angle relative to the upper
arm. The forward kinematics in the task plane are

```text
x = L1 cos(q1) + L2 cos(q1 + q2)
y = L1 sin(q1) + L2 sin(q1 + q2)
z = 0.02 m.
```

Both joints are hinges about the z axis with limits `[-170, 170]` degrees.
Without those limits, the two-link radial workspace is the annulus
`|L1-L2| <= r <= L1+L2`, or `0.02 <= r <= 0.22 m`. The official radii
`0.06 <= r <= 0.20 m` are strictly inside this annulus, so the task does not
require the inner or outer kinematic singular boundary.

For a target at radius `r`, inverse kinematics has the two usual elbow branches
when the target is interior to the annulus:

```text
cos(q2) = (r^2 - L1^2 - L2^2) / (2 L1 L2)
q2 = +/- acos(cos(q2))
q1 = theta - atan2(L2 sin(q2), L1 + L2 cos(q2)).
```

Across the official radial interval, the magnitude of `q2` is approximately
49.5 to 150.5 degrees. At least one branch remains within both joint limits
for every target angle in the stated range; the other branch can be less
convenient near a shoulder-limit boundary. The arm therefore has a discrete
elbow-up/elbow-down choice in addition to continuous motion, and a policy can
reach the same target through qualitatively different joint trajectories.
Nearer the inner radius, the two branches are more folded; nearer the outer
radius, they are more extended. The target distribution avoids exact
straight-arm and fully folded singularities, but it still spans substantially
different Jacobians and joint-limit margins.

## Actuation, timing, and dynamics

Each joint has a MuJoCo motor with control range `[-1, 1]` and gear `5`.
The policy action is passed through unchanged and clipped to this range before
being assigned to the two actuator controls. The action is therefore a bounded
motor command, not a desired joint angle or a Cartesian displacement. Its
generalized actuator contribution is scaled by the gear, while the actual
motion also depends on the configuration-dependent two-link inertia and
damping.

The physics timestep is `0.002 s`. Each policy action is held while MuJoCo
performs 10 physics steps, giving a `0.020 s` control interval and 50 control
updates per second. The explicit joint damping is `0.5` on each hinge and the
explicit joint armature is `0.01`; gravity is disabled. The links are capsules
and the plane, base, and target are non-task-contacting geometry. Consequently
there is no gravitational sag to compensate and no contact strategy available
or required. With zero velocity, zero control is compatible with a static
configuration in the ideal model; the stabilization problem is instead to
remove residual velocity and prevent actuator-driven oscillation or drift
around the tolerance boundary.

The two joints are dynamically coupled: shoulder motion moves the entire arm,
whereas elbow motion moves only the forearm, and the distal mass contributes to
both joint inertias. The same bounded command can therefore produce different
angular acceleration at different configurations. Damping dissipates motion but
does not provide position restoration. Reaching is consequently a transient
control problem followed by a high-precision low-velocity regulation problem.
The 2-second requirement makes the latter decisive: a trajectory that crosses
the target once but retains enough velocity to leave the 1 cm ball is a
failure.

The implementation evaluates distance after each 20 ms action interval. Thus
the authoritative operational meaning of “continuous” is 100 consecutive
in-tolerance control samples; excursions occurring entirely between checks are
not separately observed by the task logic. Once the 100th sample is reached,
the episode terminates immediately.

## Initial condition and task geometry

The initial fully extended state makes the target geometry asymmetric in time.
Targets near `(0.20, 0, 0.02)` are close in Cartesian distance but require
fine motion from a near-singular-looking extended posture, while targets on the
opposite side or at smaller radius require larger reorientation and folding.
The initial end-effector-to-target distance ranges from approximately `0.02 m`
to `0.42 m` over the official set. The first control problem is therefore
target-dependent: infer the required direction and branch, accelerate without
overshoot, then decelerate before entering or while entering the tolerance
region.

The target marker's visual radius is `0.012 m`, but success uses the distance
between the end-effector site and the target center with a `0.01 m` threshold.
The marker does not create a physical contact or collision constraint. Since the
target and end effector share z, the three-dimensional success distance reduces
to the planar position error for this model.

## Observation, action, and outcome coupling

The policy receives 11 values: the two joint positions, two joint velocities,
the three-dimensional end-effector-minus-target displacement, and four wrapped
angle errors to the two analytic inverse-kinematic branches. The target
position is not supplied as a separate absolute vector, but the joint positions
and known link geometry reconstruct the end-effector position, so the relative
displacement makes the relevant planar target location observable. The
observation contains no explicit acceleration, actuator torque, contact force,
or future target information. No external disturbance is defined, so these
unobserved quantities are not currently needed to specify the nominal state,
but they matter when diagnosing transient response or numerical effects.

At each decision, the observation determines a bounded two-joint command.
MuJoCo advances the arm under that held command, producing new joint state and
end-effector error. The task then tests the new distance. Entering tolerance
starts or increments a hold counter; any checked exit resets it to zero.
Therefore the behavior must jointly solve target-conditioned inverse
kinematics, dynamically feasible acceleration and braking, branch selection,
and regulation with sufficiently small sampled error and velocity. The
learning reward provides progress, closeness, hold-progress, completion, and
small action-cost signals, but those are training signals rather than the
physical outcome: only uninterrupted completion of the hold is success.

## Scientifically meaningful quantities

The complete behavior is best characterized by quantities that separate
geometry, transient control, and hold stability:

* target radius and angle, chosen IK branch, joint-limit margin, and the
  kinematic distance from the initial posture;
* end-effector distance at every control sample, signed/radial and tangential
  target error, minimum distance, first entry time, and final distance;
* joint positions, joint velocities, end-effector velocity, and action/torque
  magnitude during approach and hold;
* time spent in tolerance, longest uninterrupted hold, number and timing of
  hold interruptions, and whether failure was caused by truncation or an exit;
* approach overshoot, settling time, branch switching, and variation of all of
  the above with target radius and angle.

These measurements distinguish an unreachable or poorly conditioned target
from a policy that reaches it but cannot dissipate motion or maintain a
one-centimeter margin.

## Established facts

* The human task requires a 1 cm end-effector-center tolerance held
  uninterrupted for 2 seconds, operationally 100 control steps, with a maximum
  episode length of 500 control steps.
* The robot is a two-link planar arm with link lengths 12 cm and 10 cm,
  shoulder and elbow ranges of +/-170 degrees, zero gravity, hinge damping
  0.5, armature 0.01, and motor gear 5 with controls in `[-1, 1]`.
* The physics timestep is 2 ms and the environment advances 10 physics steps
  per action, so actions are held for 20 ms.
* Reset sets both joint positions and velocities to zero before sampling a
  stationary target in the arm plane. The target radius and angle are sampled
  independently and uniformly in the shared scenario implementation.
* The action mapping is identity apart from environment clipping. Success is
  computed from the three-dimensional site-to-target-center distance after each
  action interval; target and arm geometry do not physically interact.
* The observation has 11 components: joint position, joint velocity,
  end-effector relative displacement, and errors to two analytic IK branches.

## Physical consequences

* Every official target is inside the unconstrained two-link radial workspace,
  and the target set has valid joint-limited solutions, but it presents two
  branch choices and different conditioning and joint-limit margins.
* Because gravity and contact are absent, holding is primarily a velocity and
  feedback-regulation problem, not a load-bearing or collision-avoidance
  problem.
* A successful policy must coordinate reaching and braking. Position accuracy
  alone is insufficient: residual velocity can produce a checked exit and
  reset the entire hold counter.
* The shoulder and elbow commands have configuration-dependent effects through
  coupled inertia, so a single action scale does not imply uniform Cartesian
  motion across target locations or IK branches.
* The initial posture favors neither target angle globally and makes approach
  difficulty depend on both angular displacement and required folding. The
  official distribution therefore tests a family of transients, not one
  memorized endpoint.
* The relative target observation plus joint state makes the nominal planar
  target geometrically identifiable, while velocities provide the principal
  information needed to decide whether the arm is converging or will overshoot.
* The decisive behavioral distinction is between first entry and uninterrupted
  completion. Development metrics that report only minimum distance or time to
  first reach cannot establish the campaign objective.

## Unknowns

* The XML does not explicitly state body masses, inertias, geom densities,
  solver/integrator settings, or numerical tolerances. The compiled MuJoCo
  model determines the exact acceleration, natural response, and numerical
  stability, so these should not be inferred from link lengths alone.
* The precise transient response to each bounded command, including peak
  acceleration, settling time, and overshoot as a function of configuration,
  is unknown before measurement.
* The relative scientific difficulty of the two IK branches and of different
  radius-angle regions is not established. Kinematic reachability does not
  imply equal dynamic controllability or equal learned-policy reliability.
* It is not yet known how much sampled hold margin is required to make a
  100-sample completion robust to the arm's residual velocity and discrete
  checking, nor whether failures will be dominated by late hold exits,
  approach errors, or episode truncation.
* The observation exposes nominal state and target geometry, but the practical
  observability of the quantities most predictive of imminent boundary exit
  has not been demonstrated under the learned controller; in particular,
  acceleration and actuator response must be inferred from temporal sequences.
* Pre-campaign reasoning establishes a feasible physical solution set, not a
  learned success rate. The 98% objective and the official 200-episode result
  remain empirical claims to be tested with a frozen policy under the protected
  task distribution.
