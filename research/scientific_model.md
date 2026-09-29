# Scientific model of the two-joint reach-and-hold system

## System model

The task is a planar, two-degree-of-freedom serial arm whose endpoint must
reach a stationary target and remain there. The shoulder and elbow rotate about
parallel vertical axes, so the relevant motion is in the horizontal x-y plane.
The arm is mounted at z = 0.02 m; the target is placed at that same height.
There is no gravity. Consequently, the task is not a gravity-compensation
problem: it is a problem of geometric inversion, transient control, and
maintaining a low-velocity state inside a small Cartesian tolerance.

With shoulder angle q1 and elbow angle q2 (the elbow angle is relative to the
upper arm), the endpoint position relative to the base is

    x = 0.12 cos(q1) + 0.10 cos(q1 + q2)
    y = 0.12 sin(q1) + 0.10 sin(q1 + q2).

The initial configuration is q1 = q2 = 0 with zero joint velocity, so the
endpoint starts at (0.22, 0, 0.02). Each episode then places a fixed target at
radius 0.06-0.20 m and an angle spanning -pi to pi. The implementation samples
radius and angle independently and uniformly; this is uniform in radius, not
uniform in target area.

## Established facts

The repository defines a fixed planar two-link robot, a bounded motor interface,
and an official target-and-hold contract. The following facts are directly
established by that implementation rather than inferred from campaign behavior.

### Morphology, geometry, and constraints

- The arm has two revolute joints, link lengths 0.12 m and 0.10 m, and an
  endpoint site at the distal end of the forearm. The shoulder and elbow
  ranges are both -170 to 170 degrees.
- Its unconstrained planar radial workspace is from 0.02 m to 0.22 m. The
  official target annulus, 0.06-0.20 m, lies inside this radial workspace.
- The target is a mocap body used as a position marker. The success test uses
  the Euclidean distance between the endpoint site and the target position;
  the target sphere's visual size is not the success tolerance.
- The world plane, base, and target are non-contacting in the XML. No
  environmental obstacle or manipulation contact is part of the task.

### Actuation, simulation, and timing

- Each joint is driven by a MuJoCo motor with control in [-1, 1] and gear 5.
  The action is therefore a bounded direct joint command with nominal
  gear-scaled torque authority, not a position or velocity command.
- The physics timestep is 0.002 s. The policy command is held while ten
  physics steps execute, giving a 0.020 s control interval and a 50 Hz
  policy-to-physics interface.
- Each joint has damping 0.5 and armature 0.01. Gravity is explicitly zero.
  No joint spring or actuator state is specified.
- At reset, both joint positions and velocities are set to zero, forward
  kinematics are recomputed, and a new target is sampled. The target remains
  fixed during the episode.
- The official episode ends successfully only after 100 consecutive control
  intervals inside 0.01 m, which is 2 seconds at the stated timing. It is
  truncated at 500 control intervals if that streak is not achieved.

### Sensing and policy interface

The default policy observation has 11 float components:

1. the two joint positions;
2. the two joint velocities;
3. the three-dimensional endpoint-to-target displacement;
4. the joint errors to the positive-elbow inverse-kinematic solution; and
5. the joint errors to the negative-elbow inverse-kinematic solution.

The inverse-kinematic errors use wrapped angular differences. Thus the policy
receives both the current physical state and target-relative Cartesian error,
plus explicit information about both nominal elbow branches. It does not
receive the hidden hold counter, an explicit acceleration, the prior action,
or a direct physical measurement of torque. The official evaluator applies the
same action bounds and simulation timing, but the official outcome depends
only on the uninterrupted distance streak, not on training reward.

## Physical consequences

Given those established mechanics, the following consequences follow from
kinematics, dynamics, timing, and the success definition before any policy has
been trained. They are physical implications, not measurements of campaign
performance.

### Reachability and inverse kinematics

For target radius r, the elbow solutions satisfy

    cos(q2) = (r^2 - 0.12^2 - 0.10^2) / (2 * 0.12 * 0.10).

The official annulus gives approximately 49 degrees <= |q2| <= 150
degrees for the two branches. Both values are within the elbow limit. The
corresponding shoulder angle is the target bearing minus the link-vector
offset, with opposite offsets for the two elbow signs. Therefore the target
distribution is geometrically reachable, but the shoulder limits can remove
one branch for some combinations of target bearing and radius near the
angular limits. A policy can in principle choose an elbow-up or elbow-down
route, and route choice changes both transient geometry and joint-limit
margin.

The endpoint Jacobian is configuration-dependent. Near stretched
configurations it loses authority in the radial direction: a small joint
change can produce relatively little radial endpoint motion, while tangential
motion remains more directly available. Near folded configurations, the
mapping and required joint motion also change rapidly with target radius.
Thus equal Cartesian errors do not imply equal torque demands, velocities, or
settling times across the target annulus.

### Motion and holding

The action produces torque and the arm retains state across the ten
microsteps. A command that is useful for accelerating toward the target also
creates momentum that must be removed before or while entering the 1 cm
tolerance. Damping dissipates velocity but does not create a target-centered
restoring force. At a stationary exact configuration, zero command is
physically sufficient in this zero-gravity, no-contact model; away from that
state, feedback must regulate both position and velocity.

The 2-second criterion is consequently a connected trajectory requirement, not
100 independent successes. A small overshoot, oscillation, branch-crossing
maneuver, or noise-like action correction can reset the streak even when the
endpoint repeatedly visits the tolerance. The policy must coordinate:

- selecting a reachable joint configuration;
- moving there with enough control authority to finish within 500 updates;
- reducing endpoint and joint velocity before the tolerance boundary is
  crossed;
- keeping the endpoint inside the tolerance despite discrete action updates;
  and
- avoiding joint-limit or near-singular configurations that make the last
  centimeter difficult to regulate.

Target radius and bearing couple these demands. A target near the initial
straight configuration may require little translation but careful braking,
whereas a target at small radius requires a more folded posture and larger
joint reorientation. Targets near the workspace boundary have reduced
kinematic margin and can amplify the effect of residual motion. Since the
target is fixed, the difficulty is not target tracking against a moving
object; it is state estimation from the current observation followed by
transient convergence and invariant-set-like holding.

### Observation-action-outcome relationship

The observation exposes enough information to reconstruct the instantaneous
planar target error and current joint state, and the two branch errors make
the principal kinematic alternatives explicit. It does not directly reveal
how much endpoint motion a bounded torque will produce from the current
configuration. The policy must infer that configuration-dependent dynamics
from interaction. Its action is held open-loop for 20 ms, so the effective
closed-loop bandwidth is limited by the control interval and by the arm's
inertia and damping.

During an episode, the simulator integrates the commanded torques, the
endpoint distance is evaluated only after each 20 ms interval, and the hold
counter is incremented or reset from that sampled distance. The observed
distance is therefore a consequence of both continuous microstep motion and
discrete success sampling. Training reward may shape approach and hold
progress in the research environment, but the scientific outcome is the
binary completion of one uninterrupted 100-sample streak.

## Unknowns

The XML and task contract do not by themselves establish the effective
quantities that determine the transient response. Before campaign evidence,
the following remain unresolved:

- the compiled link and base masses, center-of-mass locations, and generalized
  inertia matrix, including the contribution of MuJoCo's model defaults;
- the exact numerical integration behavior and resulting discrete-time poles
  under the compiled MuJoCo model;
- the endpoint response, peak velocity, overshoot, and settling time produced
  by saturated and intermediate joint torques at different configurations;
- how much damping is sufficient to suppress oscillation inside the 1 cm
  boundary, and whether the 20 ms action hold creates a materially different
  response near the boundary than the microstep dynamics suggest;
- the extent to which shoulder/elbow limits, kinematic conditioning, and the
  two inverse-kinematic branches divide the official distribution into
  qualitatively different control regimes;
- whether the 11-dimensional observation is practically sufficient for a
  policy to infer the dynamics and select a stable branch without action
  history or a hold-counter signal; and
- which target radii and bearings dominate failures once reach and hold are
  measured separately. No campaign evidence yet supports attributing failure
  to reachability, braking, observation ambiguity, branch choice, or
  long-horizon stabilization.

The most scientifically meaningful quantities over a complete behavior are
target radius and bearing; joint positions, velocities, and distance to joint
limits; commanded actions and their changes; endpoint radial and tangential
error; endpoint and joint speed; first entry time; peak overshoot and settling
time; longest consecutive in-tolerance streak; number and timing of
interruptions; and the final held distance. Together these distinguish a
failure to reach from a failure to converge, a failure to stabilize, and a
failure caused by the discrete hold boundary, without replacing the official
binary episode criterion.
